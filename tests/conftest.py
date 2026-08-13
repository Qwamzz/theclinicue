"""Shared fixtures.

Each test gets its own application with its own in-memory database, so tests
are order-independent and can run in any combination.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app                                    # noqa: E402
from app.db import get_db                                     # noqa: E402
from app.domain import add_days, today_iso, to_hhmm, to_minutes, utc_stamp  # noqa: E402
from app.security import rate_limiter                         # noqa: E402
from app.seed import DEMO_PASSWORD, seed                      # noqa: E402
from app.domain import ROLE_ADMIN, ROLE_PATIENT, ROLE_STAFF   # noqa: E402


class Client:
    """Test client that carries the CSRF token the way the browser does."""

    def __init__(self, app):
        self._client = app.test_client()
        self.csrf = ""
        self.user = None

    def _headers(self, method):
        if method in {"POST", "PUT", "PATCH", "DELETE"} and self.csrf:
            return {"X-CSRF-Token": self.csrf}
        return {}

    def login(self, email, password):
        # The header goes on even here, mirroring the browser: api.js attaches
        # the CSRF cookie to every unsafe verb, so an already-signed-in user
        # re-authenticating still presents a token.
        response = self._client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            headers=self._headers("POST"),
        )
        if response.status_code == 200:
            body = response.get_json()
            self.csrf = body["csrf_token"]
            self.user = body["user"]
        return response

    def register(self, **payload):
        response = self._client.post(
            "/api/auth/register", json=payload, headers=self._headers("POST"))
        if response.status_code == 201:
            body = response.get_json()
            self.csrf = body["csrf_token"]
            self.user = body["user"]
        return response

    def get(self, path, **kw):
        return self._client.get(path, **kw)

    def post(self, path, json=None, *, csrf=True, **kw):
        headers = self._headers("POST") if csrf else {}
        headers.update(kw.pop("headers", {}))
        return self._client.post(path, json=json if json is not None else {}, headers=headers, **kw)

    def patch(self, path, json=None, **kw):
        return self._client.patch(path, json=json or {}, headers=self._headers("PATCH"), **kw)

    def delete(self, path, **kw):
        return self._client.delete(path, headers=self._headers("DELETE"), **kw)


@pytest.fixture(autouse=True)
def _frozen_clock(monkeypatch):
    """Optionally pin 'today' so the suite can be proved date-independent.

    Set TC_TEST_TODAY=YYYY-MM-DD to run the whole suite as if it were that
    date. `tools/date_matrix.py` uses this to run across a full week, because a
    test that passes only on Wednesdays is not a passing test — a lesson learned
    when the date rolled over mid-project and a seeded clash broke a test that
    had been green for hours.

    Patching `app.domain.utc_now` is enough: every other date helper resolves
    it from the module's globals at call time.
    """
    pinned = os.environ.get("TC_TEST_TODAY", "").strip()
    if not pinned:
        return

    from datetime import datetime, timezone

    import app.domain as domain_module

    day = date.fromisoformat(pinned)
    real_now = domain_module.utc_now()
    frozen = datetime(day.year, day.month, day.day,
                      real_now.hour, real_now.minute, real_now.second,
                      tzinfo=timezone.utc)
    monkeypatch.setattr(domain_module, "utc_now", lambda: frozen)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The limiter is process-global state (TD-07); a leak between tests would
    make failures depend on execution order."""
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.fixture
def app():
    application = create_app(env="testing", database_path=":memory:")
    with application.app_context():
        seed(get_db())
    yield application
    # Release the handle that keeps the shared in-memory database alive;
    # without this the connections accumulate across the suite.
    keepalive = application.extensions.pop("tc_keepalive", None)
    if keepalive is not None:
        keepalive.close()


@pytest.fixture
def anon(app):
    return Client(app)


@pytest.fixture
def patient(app):
    client = Client(app)
    client.login("patient@theclinicue.com", DEMO_PASSWORD[ROLE_PATIENT])
    return client


@pytest.fixture
def staff(app):
    client = Client(app)
    client.login("staff@theclinicue.com", DEMO_PASSWORD[ROLE_STAFF])
    return client


@pytest.fixture
def admin(app):
    client = Client(app)
    client.login("admin@theclinicue.com", DEMO_PASSWORD[ROLE_ADMIN])
    return client


@pytest.fixture
def free_slot(app, patient):
    """A date with at least two slots the demo patient can actually book.

    Searching rather than hard-coding keeps the suite independent of the seed's
    pseudo-random fill and of the weekday the tests happen to run on. The
    fixture must also skip days where the demo patient already holds an
    appointment with practitioner 1, because FR-27 permits only one per
    patient, practitioner and day — a constraint that is correct behaviour and
    would otherwise look like a test failure.
    """
    patient_id = patient.user["id"]
    for offset in range(1, 45):
        date_iso = add_days(today_iso(), offset)

        with app.app_context():
            clash = get_db().execute(
                """SELECT 1 FROM appointments
                    WHERE patient_id = ? AND practitioner_id = 1 AND appt_date = ?
                      AND status <> 'CANCELLED'""",
                (patient_id, date_iso),
            ).fetchone()
        if clash:
            continue

        response = patient.get(f"/api/slots?practitioner_id=1&service_id=1&date={date_iso}")
        if response.status_code != 200:
            continue
        slots = [s["start_time"] for s in response.get_json()["slots"]]
        if len(slots) >= 2:
            return {"date": date_iso, "start_time": slots[0], "all": slots}

    pytest.fail("no date with two bookable slots found in the next 45 days")


@pytest.fixture
def today_booking(app):
    """A BOOKED appointment today for the demo patient, so check-in can run.

    Any appointment the seed already gave that patient with practitioner 1
    today is cleared first: the one-per-day constraint (FR-27) would otherwise
    block the insert.
    """
    with app.app_context():
        conn = get_db()
        conn.execute(
            """DELETE FROM queue_entries WHERE appointment_id IN
                 (SELECT id FROM appointments
                   WHERE patient_id = 3 AND practitioner_id = 1 AND appt_date = ?)""",
            (today_iso(),),
        )
        conn.execute(
            "DELETE FROM appointments WHERE patient_id = 3 AND practitioner_id = 1 AND appt_date = ?",
            (today_iso(),),
        )

        row = conn.execute(
            """SELECT MAX(start_time) AS latest FROM appointments
                WHERE practitioner_id = 1 AND appt_date = ?""",
            (today_iso(),),
        ).fetchone()
        start = to_minutes(row["latest"]) + 30 if row and row["latest"] else 8 * 60
        start_time, end_time = to_hhmm(start), to_hhmm(start + 30)
        stamp = utc_stamp()
        cursor = conn.execute(
            """INSERT INTO appointments
                 (code, patient_id, practitioner_id, service_id, appt_date, start_time,
                  end_time, status, source, notes, created_by, created_at, updated_at)
               VALUES ('TC-TESTAA', 3, 1, 1, ?, ?, ?, 'BOOKED', 'STAFF', '', 2, ?, ?)""",
            (today_iso(), start_time, end_time, stamp, stamp),
        )
        conn.commit()
        return {"id": int(cursor.lastrowid), "date": today_iso(), "start_time": start_time}
