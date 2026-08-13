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
    session_cookie: str = "cq_session"
    csrf_cookie: str = "cq_csrf"
    csrf_header: str = "X-CSRF-Token"

    # Login throttling (FR-08)
    login_max_attempts: int = 5
    login_window_seconds: int = 900

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


def load_config(**overrides: object) -> Config:
    """Build configuration from the environment, then apply explicit overrides.

    Overrides exist so the test suite can construct an isolated app without
    mutating process-wide environment state.
    """
    env = str(overrides.pop("env", os.environ.get("CQ_ENV", "development"))).lower()
    if env not in {"development", "testing", "production"}:
        env = "development"

    secret = os.environ.get("CQ_SECRET_KEY", "").strip()
    if not secret:
        if env == "production":
            raise RuntimeError(
                "CQ_SECRET_KEY must be set in production. Refusing to start with a "
                "generated key: sessions would be invalidated on every restart and "
                "would differ between workers."
            )
        # Development and testing: a per-process key is fine and avoids a
        # committed default that could reach production by accident.
        secret = secrets.token_urlsafe(48)

    default_db = str(BASE_DIR / "data" / "clinicue.sqlite3")
    db_path = os.environ.get("CQ_DATABASE_PATH", default_db).strip() or default_db

    config = Config(
        env=env,
        secret_key=secret,
        database_path=db_path,
        session_hours=_int("CQ_SESSION_HOURS", 8),
        cookie_secure=_flag("CQ_COOKIE_SECURE", env == "production"),
        login_max_attempts=_int("CQ_LOGIN_MAX_ATTEMPTS", 5),
        login_window_seconds=_int("CQ_LOGIN_WINDOW_SECONDS", 900),
        booking_horizon_days=_int("CQ_BOOKING_HORIZON_DAYS", 60),
        password_hash_method=TESTING_HASH_METHOD if env == "testing" else PRODUCTION_HASH_METHOD,
    )

    if overrides:
        config = Config(**{**config.__dict__, **overrides})
    return config
