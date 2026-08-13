"""Security tests (TC-SEC-01 … TC-SEC-14).

These map to the STRIDE table in docs/System_Design.md §5.1. Each one is an
attack attempt written from the attacker's point of view, not a feature check.
"""

from __future__ import annotations

import pytest

from app.db import get_db
from app.domain import add_days, today_iso


class TestAuthorisation:
    """TC-SEC-01 … TC-SEC-04 / FR-11, FR-12, NFR-SEC-06."""

    PROTECTED = [
        ("get", "/api/services"),
        ("get", "/api/practitioners"),
        ("get", "/api/appointments/mine"),
        ("get", "/api/queue?practitioner_id=1"),
        ("get", "/api/queue/my-position"),
        ("get", "/api/auth/me"),
    ]

    @pytest.mark.parametrize("method,path", PROTECTED)
    def test_anonymous_access_is_refused(self, anon, method, path):
        assert getattr(anon, method)(path).status_code == 401

    STAFF_ONLY = [
        ("get", f"/api/appointments?date={today_iso()}"),
        ("get", "/api/appointments/lookup?q=ko"),
    ]

    @pytest.mark.parametrize("method,path", STAFF_ONLY)
    def test_patients_are_refused_staff_endpoints(self, patient, method, path):
        assert getattr(patient, method)(path).status_code == 403

    STAFF_WRITE = [
        "/api/queue/check-in", "/api/queue/call-next",
        "/api/queue/complete", "/api/queue/no-show",
    ]

    @pytest.mark.parametrize("path", STAFF_WRITE)
    def test_patients_are_refused_queue_operations(self, patient, path):
        assert patient.post(path, {"appointment_id": 1, "practitioner_id": 1}).status_code == 403

    ADMIN_ONLY = [
        "/api/admin/users", "/api/admin/services", "/api/admin/practitioners",
        "/api/admin/availability", "/api/admin/audit",
        "/api/admin/reports/daily", "/api/admin/reports/utilisation",
    ]

    @pytest.mark.parametrize("path", ADMIN_ONLY)
    def test_staff_are_refused_admin_endpoints(self, staff, path):
        assert staff.get(path).status_code == 403

    @pytest.mark.parametrize("path", ADMIN_ONLY)
    def test_patients_are_refused_admin_endpoints(self, patient, path):
        assert patient.get(path).status_code == 403


class TestCsrf:
    """TC-SEC-05 … TC-SEC-07 / FR-07."""

    def test_state_change_without_a_token_is_refused(self, staff):
        response = staff.post("/api/queue/call-next", {"practitioner_id": 1}, csrf=False)
        assert response.status_code == 403
        assert response.get_json()["error"] == "CSRF_INVALID"

    def test_a_wrong_token_is_refused(self, staff):
        staff.csrf = "not-the-right-token"
        assert staff.post("/api/queue/call-next", {"practitioner_id": 1}).status_code == 403

    def test_a_token_from_another_session_is_refused(self, app, staff, admin):
        """The token is bound to the signed session, so replaying another
        user's token does not work — this is stronger than plain double-submit."""
        staff.csrf = admin.csrf
        assert staff.post("/api/queue/call-next", {"practitioner_id": 1}).status_code == 403

    def test_safe_verbs_do_not_require_a_token(self, staff):
        staff.csrf = "irrelevant-for-get"
        assert staff.get(f"/api/appointments?date={today_iso()}").status_code == 200

    def test_anonymous_login_is_exempt(self, anon):
        """An anonymous POST has no session to ride, so requiring a token would
        make sign-in impossible."""
        assert anon.login("patient@theclinicue.com", "Patient#2026").status_code == 200

    def test_re_login_while_signed_in_still_needs_a_token(self, app, patient):
        """Once a session exists, /auth/login is a state-changing request like
        any other and is covered — this mitigates login CSRF, where an attacker
        silently signs the victim into an account the attacker controls."""
        response = patient._client.post(
            "/api/auth/login",
            json={"email": "staff@theclinicue.com", "password": "Staff#2026"},
        )
        assert response.status_code == 403
        assert response.get_json()["error"] == "CSRF_INVALID"

    @pytest.mark.parametrize("path,body", [
        ("/api/appointments", {"practitioner_id": 1, "service_id": 1,
                               "date": "2026-12-01", "start_time": "09:00"}),
        ("/api/queue/check-in", {"appointment_id": 1}),
        ("/api/admin/services", {"name": "X", "duration_min": 30}),
    ])
    def test_every_write_path_is_covered(self, admin, path, body):
        """CSRF is enforced in one before_request hook, so a new endpoint
        cannot forget it. This asserts that property."""
        assert admin.post(path, body, csrf=False).status_code == 403


class TestInjection:
    """TC-SEC-08, TC-SEC-09 / FR-56."""

    @pytest.mark.parametrize("payload", [
        "'; DROP TABLE users; --",
        "' OR '1'='1",
        "1; DELETE FROM appointments",
        "%' UNION SELECT password_hash FROM users --",
    ])
    def test_sql_injection_through_search_is_inert(self, app, staff, payload):
        response = staff.get(f"/api/appointments?date={today_iso()}&q={payload}")
        assert response.status_code == 200
        with app.app_context():
            assert get_db().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] >= 11

    def test_injection_in_the_login_field_is_inert(self, anon):
        response = anon.login("' OR 1=1 --", "anything")
        assert response.status_code in (400, 401)

    def test_no_password_hash_leaks_through_a_union_attempt(self, staff):
        raw = staff.get(
            f"/api/appointments?date={today_iso()}&q=%' UNION SELECT password_hash FROM users --"
        ).get_data(as_text=True)
        assert "pbkdf2" not in raw

    def test_stored_xss_payload_is_returned_as_data_not_markup(self, app, staff):
        """FR-58. The API returns JSON; the client renders through textContent,
        so the payload can never become executable markup."""
        from tests.conftest import Client

        attacker = Client(app)
        attacker.register(full_name="<script>alert(1)</script>", email="xss@example.com",
                          phone="+233241116666", password="Passw0rd1")
        response = staff.get(f"/api/appointments/lookup?q=script")
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("application/json")


class TestInformationDisclosure:
    """TC-SEC-10 … TC-SEC-12 / FR-55, NFR-SEC-04."""

    def test_security_headers_are_present(self, patient):
        response = patient.get("/api/services")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "no-referrer"

    def test_csp_restricts_scripts_to_self(self, patient):
        assert "script-src 'self'" in patient.get("/api/services").headers["Content-Security-Policy"]

    def test_errors_never_leak_internals(self, patient):
        """FR-55."""
        for path in ["/api/appointments/999999", "/api/slots?practitioner_id=abc",
                     "/api/nonexistent"]:
            body = patient.get(path).get_data(as_text=True).lower()
            for leak in ["traceback", "sqlite", "select ", "file \"", "c:\\", "/app/"]:
                assert leak not in body

    def test_unhandled_errors_return_a_generic_envelope(self, app, patient, monkeypatch):
        """NFR-REL-01: the worker survives and the client learns nothing."""
        from app.services import reports

        def boom(*_args, **_kwargs):
            raise RuntimeError("database melted at /secret/path.py line 42")

        monkeypatch.setattr(reports, "daily_summary", boom)
        admin = type(patient)(app)
        admin.login("admin@theclinicue.com", "Admin#2026")
        response = admin.get("/api/admin/reports/daily")
        assert response.status_code == 500
        assert response.get_json()["error"] == "INTERNAL_ERROR"
        assert "melted" not in response.get_data(as_text=True)
        assert "/secret/path.py" not in response.get_data(as_text=True)
        # And the app still works afterwards.
        assert admin.get("/api/admin/users").status_code == 200

    def test_404_is_json_for_api_paths(self, patient):
        response = patient.get("/api/does-not-exist")
        assert response.status_code == 404
        assert response.headers["Content-Type"].startswith("application/json")

    def test_write_lock_contention_is_reported_as_busy_not_broken(self, app, staff, monkeypatch):
        """Found by the performance run: SQLite serialises writers, so under
        contention a write can be refused. That is transient, so it must be a
        503 with a retry hint, not a 500 that implies the request was bad.
        Eliminating the condition altogether is TD-01."""
        import sqlite3

        from app.services import queue as queue_service

        def locked(*_args, **_kwargs):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(queue_service, "call_next", locked)
        response = staff.post("/api/queue/call-next", {"practitioner_id": 1})
        assert response.status_code == 503
        assert response.get_json()["error"] == "SERVICE_BUSY"
        assert response.headers["Retry-After"] == "1"
        assert "locked" not in response.get_data(as_text=True)

    def test_a_genuine_database_fault_is_still_a_500(self, app, staff, monkeypatch):
        """The busy handler must not swallow real faults."""
        import sqlite3

        from app.services import queue as queue_service

        def broken(*_args, **_kwargs):
            raise sqlite3.OperationalError("no such column: nonsense")

        monkeypatch.setattr(queue_service, "call_next", broken)
        response = staff.post("/api/queue/call-next", {"practitioner_id": 1})
        assert response.status_code == 500
        assert response.get_json()["error"] == "INTERNAL_ERROR"
        assert "nonsense" not in response.get_data(as_text=True)

    def test_oversized_body_is_rejected(self, staff):
        """MAX_CONTENT_LENGTH: no endpoint needs a large body, so accepting one
        is only a memory-exhaustion opportunity."""
        response = staff.post("/api/queue/check-in",
                              {"appointment_id": 1, "padding": "x" * 300_000})
        assert response.status_code in (400, 413)


class TestObjectAccess:
    """TC-SEC-13, TC-SEC-14 / FR-30."""

    def test_appointment_ids_cannot_be_enumerated(self, app, patient):
        """A 403 would confirm which ids exist. Every id the caller does not
        own must be indistinguishable from one that does not exist."""
        statuses = set()
        for appointment_id in range(1, 30):
            statuses.add(patient.get(f"/api/appointments/{appointment_id}").status_code)
        assert statuses <= {200, 404}

    def test_a_patient_cannot_cancel_another_patients_appointment(self, app, patient):
        with app.app_context():
            row = get_db().execute(
                "SELECT id FROM appointments WHERE patient_id <> ? LIMIT 1",
                (patient.user["id"],)).fetchone()
        assert patient.post(f"/api/appointments/{row['id']}/cancel").status_code == 404

    def test_the_victims_appointment_is_untouched(self, app, patient):
        with app.app_context():
            row = get_db().execute(
                "SELECT id, status FROM appointments WHERE patient_id <> ? AND status = 'BOOKED' LIMIT 1",
                (patient.user["id"],)).fetchone()
        if row is None:
            pytest.skip("no other patient's booking available in the seed")
        patient.post(f"/api/appointments/{row['id']}/cancel")
        with app.app_context():
            after = get_db().execute(
                "SELECT status FROM appointments WHERE id = ?", (row["id"],)).fetchone()
        assert after["status"] == "BOOKED"


class TestHealthEndpoint:
    def test_health_is_public_and_reveals_nothing_sensitive(self, anon):
        """NFR-REL-03. The platform probe has no credentials, so this must be
        open — and must therefore say nothing useful to an attacker."""
        response = anon.get("/api/health")
        assert response.status_code == 200
        body = response.get_json()
        assert body["status"] == "ok"
        assert set(body) == {"service", "version", "status", "database",
                             "environment", "build", "time"}
        # The build stamp is a short commit hash and a timestamp. Deliberately
        # public: it is what lets anyone confirm which code is actually serving,
        # and it discloses nothing an attacker cannot read in the public repo.
        assert set(body["build"]) == {"commit", "built_at"}
        assert len(body["build"]["commit"]) <= 12
        for leak in ("password", "secret", "key", "token", "/home/"):
            assert leak not in str(body).lower()
