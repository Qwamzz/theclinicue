"""Configuration and platform-aware defaults (TC-U-37 to TC-U-46).

These exist because the first hosted deployment came up silently wrong: the
database sat outside the only persistent directory, so every deploy destroyed
it, and the catalogue was empty because the platform bypassed the startup
script. Both were configuration defaults, not code defects, which is exactly
the class of problem that never shows up in a functional test.
"""

from __future__ import annotations

import pytest

from app.config import (
    PRODUCTION_HASH_METHOD,
    TESTING_HASH_METHOD,
    load_config,
    on_app_service,
)


@pytest.fixture
def clean_env(monkeypatch):
    """Remove every variable that influences configuration."""
    for name in ("WEBSITE_SITE_NAME", "TC_ENV", "TC_SECRET_KEY", "TC_DATABASE_PATH",
                 "TC_SQLITE_JOURNAL", "TC_SEED_ON_START", "TC_COOKIE_SECURE",
                 "TC_SESSION_HOURS", "TC_BOOKING_HORIZON_DAYS"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


class TestPlatformDetection:
    def test_not_on_app_service_by_default(self, clean_env):
        assert on_app_service() is False

    def test_detected_from_the_platform_variable(self, clean_env):
        """WEBSITE_SITE_NAME is injected by App Service and is not something a
        developer sets by hand, so it is a reliable signal."""
        clean_env.setenv("WEBSITE_SITE_NAME", "theclinicue")
        assert on_app_service() is True


class TestLocalDefaults:
    def test_database_is_package_relative(self, clean_env):
        """Relative to the package, not the Azure persistent share. Asserted on
        the suffix rather than the prefix: on Linux the project may legitimately
        live under /home, which is not an Azure signal."""
        path = load_config().database_path
        assert path.endswith("theclinicue.sqlite3")
        assert path != "/home/data/theclinicue.sqlite3"

    def test_wal_journal_on_local_disk(self, clean_env):
        """WAL everywhere except App Service - including a Linux host whose
        project directory happens to sit under /home."""
        assert load_config().sqlite_journal_mode == "WAL"

    def test_a_home_path_off_app_service_still_uses_wal(self, clean_env):
        """Regression guard for the heuristic CI caught: /home is an ordinary
        Linux prefix, not an Azure network share."""
        clean_env.setenv("TC_DATABASE_PATH", "/home/runner/work/app/data/x.sqlite3")
        assert load_config().sqlite_journal_mode == "WAL"

    def test_no_seeding_on_start(self, clean_env):
        assert load_config().seed_on_start is False

    def test_cookies_not_forced_secure(self, clean_env):
        """Development is usually plain HTTP; forcing Secure would make the
        session cookie silently vanish."""
        assert load_config().cookie_secure is False


class TestAppServiceDefaults:
    """The four defaults that were wrong on the first hosted deployment."""

    @pytest.fixture(autouse=True)
    def _on_azure(self, clean_env):
        clean_env.setenv("WEBSITE_SITE_NAME", "theclinicue")

    def test_database_lands_in_the_persistent_directory(self):
        """/home is the only path App Service preserves across deployments.
        Anywhere else and every deploy destroys the bookings, with no error."""
        assert load_config().database_path == "/home/data/theclinicue.sqlite3"

    def test_journal_avoids_wal_on_network_storage(self):
        """/home is an SMB share, where SQLite's write-ahead log is unreliable."""
        assert load_config().sqlite_journal_mode == "DELETE"

    def test_seeding_is_enabled(self):
        """The platform's own gunicorn can bypass startup.sh, so the seed step
        never runs and the catalogue comes up empty."""
        assert load_config().seed_on_start is True

    def test_cookies_are_secure_even_before_production_mode(self):
        """App Service terminates TLS in front of the app."""
        assert load_config().cookie_secure is True

    def test_it_does_not_promote_itself_to_production(self):
        """Deliberate. Production requires TC_SECRET_KEY, and inventing one
        would differ between workers and be discarded on restart."""
        assert load_config().env == "development"


class TestExplicitSettingsWin:
    """Platform defaults fill gaps; they must never override an operator."""

    @pytest.fixture(autouse=True)
    def _on_azure(self, clean_env):
        clean_env.setenv("WEBSITE_SITE_NAME", "theclinicue")

    def test_database_path(self, clean_env):
        clean_env.setenv("TC_DATABASE_PATH", "/mnt/data/custom.sqlite3")
        assert load_config().database_path == "/mnt/data/custom.sqlite3"

    def test_journal_mode(self, clean_env):
        clean_env.setenv("TC_SQLITE_JOURNAL", "WAL")
        assert load_config().sqlite_journal_mode == "WAL"

    def test_seeding_can_be_turned_off(self, clean_env):
        clean_env.setenv("TC_SEED_ON_START", "false")
        assert load_config().seed_on_start is False

    def test_cookie_secure_can_be_turned_off(self, clean_env):
        clean_env.setenv("TC_COOKIE_SECURE", "false")
        assert load_config().cookie_secure is False

    def test_an_unknown_journal_mode_falls_back_safely(self, clean_env):
        """The value is interpolated into a PRAGMA, which cannot be
        parameterised, so anything unrecognised must not reach SQL."""
        clean_env.setenv("TC_SQLITE_JOURNAL", "DROP TABLE users")
        assert load_config().sqlite_journal_mode == "DELETE"


class TestProductionGuards:
    def test_production_without_a_secret_refuses_to_start(self, clean_env):
        clean_env.setenv("TC_ENV", "production")
        with pytest.raises(RuntimeError, match="TC_SECRET_KEY"):
            load_config()

    def test_production_with_a_secret_is_hardened(self, clean_env):
        clean_env.setenv("TC_ENV", "production")
        clean_env.setenv("TC_SECRET_KEY", "x" * 40)
        config = load_config()
        assert config.is_production
        assert config.cookie_secure is True
        assert config.password_hash_method == PRODUCTION_HASH_METHOD

    def test_testing_lowers_only_the_hash_cost(self, clean_env):
        config = load_config(env="testing")
        assert config.password_hash_method == TESTING_HASH_METHOD
        assert config.is_testing

    def test_an_unknown_environment_falls_back_to_development(self, clean_env):
        clean_env.setenv("TC_ENV", "staging")
        assert load_config().env == "development"

    def test_seeding_is_idempotent_against_a_populated_database(self, app):
        """The safety property the App Service default depends on: seeding a
        database that already has users must not duplicate anything."""
        from app.db import get_db
        from app.seed import seed

        with app.app_context():
            before = get_db().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            result = seed(get_db())
            after = get_db().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]

        assert result["skipped"] is True
        assert after == before
