"""Runtime configuration.

All configuration comes from environment variables with safe development
defaults (NFR-MNT-04). Nothing secret is committed to the repository
(NFR-SEC-05); in production a missing SECRET_KEY is a hard startup failure
rather than a silently generated key, because a generated key would
invalidate every session on each worker restart.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

#: NFR-SEC-02. PBKDF2-HMAC-SHA256 at 600,000 iterations, per OWASP guidance.
PRODUCTION_HASH_METHOD = "pbkdf2:sha256:600000"

#: Same algorithm, fewer rounds — used only when env == "testing".
TESTING_HASH_METHOD = "pbkdf2:sha256:10000"


def on_app_service() -> bool:
    """True when running on Azure App Service.

    WEBSITE_SITE_NAME is injected by the platform and is not something a
    developer sets by hand, so it is a reliable signal.
    """
    return bool(os.environ.get("WEBSITE_SITE_NAME"))


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Immutable application configuration."""

    env: str = "development"
    secret_key: str = ""
    database_path: str = ""

    # Session and security
    session_hours: int = 8                # NFR-SEC-03
    cookie_secure: bool = False           # NFR-SEC-01, forced True in production
    session_cookie: str = "tc_session"
    csrf_cookie: str = "tc_csrf"
    csrf_header: str = "X-CSRF-Token"

    # Login throttling (FR-08)
    login_max_attempts: int = 5
    login_window_seconds: int = 900

    #: SQLite journal mode. WAL is right on a local disk: it lets readers
    #: proceed while a booking holds the write lock. It is NOT safe on an SMB
    #: share, which is what Azure App Service's persistent /home is, so the
    #: Azure deployment sets this to DELETE. See TD-01.
    sqlite_journal_mode: str = "WAL"

    #: Seed demonstration data at start-up when the database has no users.
    #: App Service's Oryx builder starts its own gunicorn and ignores a
    #: custom startup command in some configurations, which leaves the
    #: catalogue empty and the application unusable. This flag is a lever
    #: that does not depend on the platform honouring startup.sh.
    #: Safe to leave on: seeding is skipped whenever any user already exists.
    seed_on_start: bool = False

    # Scheduling policy
    booking_horizon_days: int = 60        # FR-23
    max_page_size: int = 100

    # Password policy (FR-03) and hashing cost (NFR-SEC-02)
    password_min_length: int = 8
    #: Werkzeug's default iteration count trails OWASP guidance, so it is
    #: pinned explicitly rather than inherited. Lowered only under `testing`,
    #: where 600,000 rounds per seeded user would make the suite take minutes
    #: without testing anything the algorithm choice does not already cover.
    password_hash_method: str = PRODUCTION_HASH_METHOD

    extras: dict = field(default_factory=dict)

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_testing(self) -> bool:
        return self.env == "testing"


def _journal_mode(database_path: str = "") -> str:
    """Validated against a whitelist: this value is interpolated into a PRAGMA,
    which cannot be parameterised, so it must never come straight from the
    environment.

    Defaults to DELETE on network storage. WAL is unreliable over SMB, which is
    what App Service's /home is.
    """
    network_storage = on_app_service() or database_path.startswith("/home/")
    default = "DELETE" if network_storage else "WAL"
    requested = os.environ.get("TC_SQLITE_JOURNAL", default).strip().upper()
    return requested if requested in {"WAL", "DELETE", "TRUNCATE", "PERSIST"} else default


def load_config(**overrides: object) -> Config:
    """Build configuration from the environment, then apply explicit overrides.

    Overrides exist so the test suite can construct an isolated app without
    mutating process-wide environment state.
    """
    env = str(overrides.pop("env", os.environ.get("TC_ENV", "development"))).lower()
    if env not in {"development", "testing", "production"}:
        env = "development"

    secret = os.environ.get("TC_SECRET_KEY", "").strip()
    if not secret:
        if env == "production":
            raise RuntimeError(
                "TC_SECRET_KEY must be set in production. Refusing to start with a "
                "generated key: sessions would be invalidated on every restart and "
                "would differ between workers."
            )
        # Development and testing: a per-process key is fine and avoids a
        # committed default that could reach production by accident.
        secret = secrets.token_urlsafe(48)

    # Platform-aware defaults. An explicit environment variable always wins;
    # these only fill the gaps, and they exist because getting them wrong on
    # App Service is silently destructive rather than merely inconvenient.
    azure = on_app_service()

    # /home is the only directory App Service preserves across restarts and
    # deployments. The package-relative default would be wiped by every deploy,
    # losing every booking without any error being raised.
    default_db = ("/home/data/theclinicue.sqlite3" if azure
                  else str(BASE_DIR / "data" / "theclinicue.sqlite3"))
    db_path = os.environ.get("TC_DATABASE_PATH", default_db).strip() or default_db

    config = Config(
        env=env,
        secret_key=secret,
        database_path=db_path,
        session_hours=_int("TC_SESSION_HOURS", 8),
        # App Service terminates TLS in front of the app, so cookies can and
        # should carry the Secure flag there even before TC_ENV is set.
        cookie_secure=_flag("TC_COOKIE_SECURE", env == "production" or azure),
        login_max_attempts=_int("TC_LOGIN_MAX_ATTEMPTS", 5),
        login_window_seconds=_int("TC_LOGIN_WINDOW_SECONDS", 900),
        booking_horizon_days=_int("TC_BOOKING_HORIZON_DAYS", 60),
        password_hash_method=TESTING_HASH_METHOD if env == "testing" else PRODUCTION_HASH_METHOD,
        sqlite_journal_mode=_journal_mode(db_path),
        # On App Service the platform's own gunicorn can bypass startup.sh, so
        # the seed step never runs and the catalogue comes up empty. Seeding is
        # skipped whenever any user already exists, so this cannot clobber data.
        seed_on_start=_flag("TC_SEED_ON_START", azure),
    )

    if overrides:
        config = Config(**{**config.__dict__, **overrides})
    return config
