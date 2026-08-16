"""Integration tests for registration, login and sessions
(TC-I-01 to TC-I-13 / FR-01 to FR-13)."""

from __future__ import annotations

from app.db import get_db
from app.security import rate_limiter


class TestRegistration:
    def test_valid_registration_succeeds_and_signs_in(self, anon):
        response = anon.register(full_name="New Patient", email="new@example.com",
                                 phone="+233241110000", password="Passw0rd1")
        assert response.status_code == 201
        body = response.get_json()
        assert body["user"]["role"] == "PATIENT"
        assert "csrf_token" in body
        assert anon.get("/api/auth/me").status_code == 200

    def test_password_hash_is_never_returned(self, anon):
        """FR-04. A leaked hash is a leaked password given enough time."""
        response = anon.register(full_name="Hash Check", email="hash@example.com",
                                 phone="+233241110001", password="Passw0rd1")
        assert "password" not in response.get_data(as_text=True).lower()

    def test_password_is_stored_salted_and_one_way(self, app, anon):
        """FR-04: never plaintext, never reversible, and salted per user."""
        anon.register(full_name="Hash Check", email="hash2@example.com",
                      phone="+233241110002", password="Passw0rd1")
        with app.app_context():
            row = get_db().execute(
                "SELECT password_hash FROM users WHERE email = ?", ("hash2@example.com",)
            ).fetchone()
        algorithm, salt, digest = row["password_hash"].split("$")
        assert algorithm.startswith("pbkdf2:sha256:")
        assert len(salt) >= 8                       # a per-user salt is present
        assert len(digest) >= 32
        assert "Passw0rd1" not in row["password_hash"]

    def test_two_users_with_the_same_password_get_different_hashes(self, app):
        """Proves the salt is per-user: without it, one rainbow table would
        crack every account that shares a password."""
        from tests.conftest import Client

        Client(app).register(full_name="Same One", email="same1@example.com",
                             phone="+233241110010", password="Passw0rd1")
        Client(app).register(full_name="Same Two", email="same2@example.com",
                             phone="+233241110011", password="Passw0rd1")
        with app.app_context():
            hashes = [r["password_hash"] for r in get_db().execute(
                "SELECT password_hash FROM users WHERE email IN ('same1@example.com','same2@example.com')")]
        assert len(hashes) == 2
        assert hashes[0] != hashes[1]

    def test_production_uses_600000_pbkdf2_iterations(self):
        """NFR-SEC-02 by inspection. The test environment deliberately lowers
        the cost, so this asserts the setting the deployment actually gets -
        which is the thing the requirement is about."""
        from app.config import PRODUCTION_HASH_METHOD, load_config

        assert PRODUCTION_HASH_METHOD == "pbkdf2:sha256:600000"
        assert load_config(env="development").password_hash_method == PRODUCTION_HASH_METHOD

    def test_a_production_grade_hash_still_verifies(self, app):
        """The lowered test cost must not hide a broken verification path:
        a hash written at 600,000 rounds has to keep working."""
        from app.security import hash_password, verify_password

        with app.app_context():
            stored = hash_password("Passw0rd1", "pbkdf2:sha256:600000")
        assert stored.startswith("pbkdf2:sha256:600000$")
        assert verify_password(stored, "Passw0rd1")
        assert not verify_password(stored, "WrongPass1")

    def test_duplicate_email_rejected_without_confirming_the_account(self, anon):
        """FR-02: the message must not reveal whether the account is active."""
        response = anon.register(full_name="Copy Cat", email="patient@theclinicue.com",
                                 phone="+233241110003", password="Passw0rd1")
        assert response.status_code == 400
        body = response.get_json()
        assert body["error"] == "VALIDATION_ERROR"
        assert "already registered" in body["fields"]["email"]

    def test_weak_password_rejected(self, anon):
        response = anon.register(full_name="Weak Pass", email="weak@example.com",
                                 phone="+233241110004", password="abcdefgh")
        assert response.status_code == 400
        assert "password" in response.get_json()["fields"]

    def test_role_cannot_be_chosen_by_the_registrant(self, anon):
        """Privilege escalation attempt: the role in the body is ignored."""
        response = anon.register(full_name="Sneaky", email="sneaky@example.com",
                                 phone="+233241110005", password="Passw0rd1", role="ADMIN")
        assert response.status_code == 201
        assert response.get_json()["user"]["role"] == "PATIENT"

    def test_missing_fields_reported_together(self, anon):
        response = anon.register(email="bad")
        assert response.status_code == 400
        assert set(response.get_json()["fields"]) >= {"full_name", "phone", "password"}


class TestLogin:
    def test_valid_login(self, anon):
        response = anon.login("patient@theclinicue.com", "Patient#2026")
        assert response.status_code == 200
        assert response.get_json()["user"]["role"] == "PATIENT"

    def test_session_cookie_is_httponly_and_samesite(self, anon):
        """FR-06. HttpOnly is what makes an XSS defect unable to steal the
        session."""
        response = anon.login("patient@theclinicue.com", "Patient#2026")
        cookies = response.headers.getlist("Set-Cookie")
        session = next(c for c in cookies if c.startswith("tc_session="))
        assert "HttpOnly" in session
        assert "SameSite=Lax" in session

    def test_csrf_cookie_is_readable_by_script(self, anon):
        """It must NOT be HttpOnly - the client has to echo it in a header."""
        response = anon.login("patient@theclinicue.com", "Patient#2026")
        csrf = next(c for c in response.headers.getlist("Set-Cookie") if c.startswith("tc_csrf="))
        assert "HttpOnly" not in csrf

    def test_wrong_password_rejected(self, anon):
        response = anon.login("patient@theclinicue.com", "WrongPass1")
        assert response.status_code == 401
        assert response.get_json()["error"] == "UNAUTHENTICATED"

    def test_unknown_and_known_accounts_give_the_same_answer(self, anon):
        """No account enumeration through the error message."""
        unknown = anon.login("nobody@example.com", "WrongPass1")
        known = anon.login("patient@theclinicue.com", "WrongPass1")
        assert unknown.status_code == known.status_code == 401
        assert unknown.get_json() == known.get_json()

    def test_deactivated_account_cannot_log_in(self, app, anon):
        """FR-13."""
        with app.app_context():
            conn = get_db()
            conn.execute("UPDATE users SET is_active = 0 WHERE email = ?",
                         ("patient@theclinicue.com",))
            conn.commit()
        assert anon.login("patient@theclinicue.com", "Patient#2026").status_code == 401

    def test_deactivation_invalidates_a_live_session(self, app, patient):
        """FR-13 again: offboarding must take effect immediately, not at the
        user's next login."""
        assert patient.get("/api/auth/me").status_code == 200
        with app.app_context():
            conn = get_db()
            conn.execute("UPDATE users SET is_active = 0 WHERE email = ?",
                         ("patient@theclinicue.com",))
            conn.commit()
        assert patient.get("/api/auth/me").status_code == 401

    def test_login_failure_is_audited(self, app, anon):
        anon.login("patient@theclinicue.com", "WrongPass1")
        with app.app_context():
            row = get_db().execute(
                "SELECT COUNT(*) AS n FROM audit_log WHERE action = 'LOGIN_FAILED'"
            ).fetchone()
        assert row["n"] >= 1


class TestRateLimiting:
    def test_repeated_failures_are_throttled(self, anon):
        """FR-08."""
        rate_limiter.reset()
        for _ in range(5):
            assert anon.login("patient@theclinicue.com", "WrongPass1").status_code == 401
        blocked = anon.login("patient@theclinicue.com", "WrongPass1")
        assert blocked.status_code == 429
        assert blocked.get_json()["error"] == "RATE_LIMITED"

    def test_throttle_blocks_even_the_correct_password(self, anon):
        """Otherwise the limiter is an oracle: a 429 for wrong and a 200 for
        right would confirm the password."""
        rate_limiter.reset()
        for _ in range(5):
            anon.login("patient@theclinicue.com", "WrongPass1")
        assert anon.login("patient@theclinicue.com", "Patient#2026").status_code == 429

    def test_successful_login_clears_the_counter(self, anon):
        rate_limiter.reset()
        for _ in range(3):
            anon.login("patient@theclinicue.com", "WrongPass1")
        assert anon.login("patient@theclinicue.com", "Patient#2026").status_code == 200
        for _ in range(3):
            anon.login("patient@theclinicue.com", "WrongPass1")
        assert anon.login("patient@theclinicue.com", "Patient#2026").status_code == 200

    def test_other_accounts_are_unaffected(self, anon, app):
        """A throttle keyed only on IP would let one attacker lock out an
        entire clinic."""
        rate_limiter.reset()
        for _ in range(5):
            anon.login("patient@theclinicue.com", "WrongPass1")
        other = type(anon)(app)
        assert other.login("staff@theclinicue.com", "Staff#2026").status_code == 200


class TestSession:
    def test_me_requires_authentication(self, anon):
        assert anon.get("/api/auth/me").status_code == 401

    def test_session_probe_is_anonymous_friendly(self, anon):
        """The client calls this on first paint; it must not 401."""
        response = anon.get("/api/auth/session")
        assert response.status_code == 200
        assert response.get_json()["authenticated"] is False

    def test_logout_clears_the_session(self, patient):
        assert patient.post("/api/auth/logout").status_code == 200
        assert patient.get("/api/auth/me").status_code == 401

    def test_logout_is_idempotent(self, anon):
        assert anon.post("/api/auth/logout").status_code == 200

    def test_a_forged_token_is_refused(self, app):
        """The JWT signature is the only thing standing between a cookie and
        an identity."""
        client = app.test_client()
        client.set_cookie("tc_session", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.forged")
        assert client.get("/api/auth/me").status_code == 401

    def test_alg_none_token_is_refused(self, app):
        """The classic JWT attack: an unsigned token claiming to be admin."""
        import base64
        import json

        def b64(data):
            return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

        token = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': '1', 'role': 'ADMIN', 'exp': 9999999999})}."
        client = app.test_client()
        client.set_cookie("tc_session", token)
        assert client.get("/api/auth/me").status_code == 401
