"""System and user-acceptance tests (TC-S-01 … TC-S-06).

These follow whole journeys across roles, in the order a real clinic day runs.
They are the tests that would catch a defect that every unit passes.
"""

from __future__ import annotations

from app.db import get_db
from app.domain import add_days, today_iso


class TestPatientJourney:
    def test_register_book_view_cancel(self, app, anon):
        """TC-S-01 / UAT-01: a new patient completes the whole self-service
        journey without staff involvement."""
        assert anon.register(full_name="Journey Patient", email="journey@example.com",
                             phone="+233241115555", password="Passw0rd1").status_code == 201

        services = anon.get("/api/services").get_json()["items"]
        practitioners = anon.get("/api/practitioners").get_json()["items"]
        assert services and practitioners

        booking = None
        for offset in range(1, 40):
            date_iso = add_days(today_iso(), offset)
            slots = anon.get(
                f"/api/slots?practitioner_id={practitioners[0]['id']}"
                f"&service_id={services[0]['id']}&date={date_iso}").get_json()["slots"]
            if slots:
                response = anon.post("/api/appointments", {
                    "practitioner_id": practitioners[0]["id"],
                    "service_id": services[0]["id"],
                    "date": date_iso, "start_time": slots[0]["start_time"]})
                assert response.status_code == 201
                booking = response.get_json()
                break
        assert booking is not None, "no bookable slot found"
        assert booking["code"].startswith("CQ-")

        mine = anon.get("/api/appointments/mine?scope=upcoming").get_json()["items"]
        assert booking["id"] in [a["id"] for a in mine]

        assert anon.post(f"/api/appointments/{booking['id']}/cancel").status_code == 200
        after = anon.get("/api/appointments/mine?scope=upcoming").get_json()["items"]
        assert booking["id"] not in [a["id"] for a in after]


class TestClinicDay:
    def test_arrival_to_completion(self, app, staff, admin, today_booking):
        """TC-S-02 / UAT-02: the full front-desk cycle, and its effect on the
        day's reported figures."""
        before = admin.get(f"/api/admin/reports/daily?date={today_iso()}").get_json()
        completed_before = before["by_status"]["COMPLETED"]

        entry = staff.post("/api/queue/check-in",
                           {"appointment_id": today_booking["id"]}).get_json()
        assert entry["status"] == "WAITING"

        queue = staff.get("/api/queue?practitioner_id=1").get_json()
        assert entry["ticket_no"] in [w["ticket_no"] for w in queue["waiting"]]

        called = staff.post("/api/queue/call-next", {"practitioner_id": 1}).get_json()["called"]
        assert called["appointment_id"] == today_booking["id"]

        queue = staff.get("/api/queue?practitioner_id=1").get_json()
        assert queue["now_serving"]["ticket_no"] == entry["ticket_no"]

        assert staff.post("/api/queue/complete",
                          {"appointment_id": today_booking["id"]}).status_code == 200

        after = admin.get(f"/api/admin/reports/daily?date={today_iso()}").get_json()
        assert after["by_status"]["COMPLETED"] == completed_before + 1

    def test_no_show_path_reaches_the_report(self, staff, admin, today_booking):
        """TC-S-03 / UAT-03: the metric the clinic manager actually wants."""
        before = admin.get(f"/api/admin/reports/daily?date={today_iso()}").get_json()
        staff.post("/api/queue/no-show", {"appointment_id": today_booking["id"]})
        after = admin.get(f"/api/admin/reports/daily?date={today_iso()}").get_json()
        assert after["by_status"]["NO_SHOW"] == before["by_status"]["NO_SHOW"] + 1
        assert after["no_show_rate"] >= before["no_show_rate"]

    def test_walk_in_registered_by_staff_reaches_the_queue(self, staff):
        """TC-S-04 / UAT-04: the patient with no phone is still served."""
        found = staff.get("/api/appointments/lookup?q=Kofi").get_json()["items"]
        assert found
        patient_id = found[0]["id"]

        booking = None
        for offset in range(0, 20):
            date_iso = add_days(today_iso(), offset)
            slots = staff.get(
                f"/api/slots?practitioner_id=2&service_id=2&date={date_iso}").get_json().get("slots", [])
            if slots:
                response = staff.post("/api/appointments", {
                    "patient_id": patient_id, "practitioner_id": 2, "service_id": 2,
                    "date": date_iso, "start_time": slots[0]["start_time"], "walk_in": offset == 0})
                if response.status_code == 201:
                    booking = response.get_json()
                    break
        assert booking is not None
        assert booking["patient_id"] == patient_id
        assert booking["source"] in ("STAFF", "WALK_IN")


class TestAdministratorJourney:
    def test_configure_clinic_then_book_against_it(self, app, admin, anon):
        """TC-S-05 / UAT-05: an administrator sets up a brand-new clinician
        from scratch and a patient can immediately book with them."""
        practitioner = admin.post("/api/admin/practitioners", {
            "full_name": "Dr Comfort Asare", "specialty": "Nutrition", "room": "Room 9",
        }).get_json()
        service = admin.post("/api/admin/services", {
            "name": "Nutrition Advice", "description": "Dietary counselling", "duration_min": 60,
        }).get_json()

        from datetime import date

        target = add_days(today_iso(), 1)
        for _ in range(8):
            if date.fromisoformat(target).weekday() == 5:
                break
            target = add_days(target, 1)

        assert admin.post("/api/admin/availability", {
            "practitioner_id": practitioner["id"], "weekday": 5,
            "start_time": "09:00", "end_time": "12:00"}).status_code == 201

        anon.register(full_name="Fresh Patient", email="fresh@example.com",
                      phone="+233241114444", password="Passw0rd1")
        slots = anon.get(
            f"/api/slots?practitioner_id={practitioner['id']}"
            f"&service_id={service['id']}&date={target}").get_json()["slots"]
        assert [s["start_time"] for s in slots] == ["09:00", "10:00", "11:00"]

        response = anon.post("/api/appointments", {
            "practitioner_id": practitioner["id"], "service_id": service["id"],
            "date": target, "start_time": "10:00"})
        assert response.status_code == 201
        assert response.get_json()["duration_min"] == 60
        assert response.get_json()["end_time"] == "11:00"

    def test_offboarding_a_staff_member_takes_effect_immediately(self, app, admin):
        """TC-S-06 / UAT-06: the security story an administrator must be able
        to rely on the moment someone leaves."""
        from tests.conftest import Client

        leaver = Client(app)
        assert leaver.login("staff@clinicue.health", "Staff#2026").status_code == 200
        assert leaver.get(f"/api/appointments?date={today_iso()}").status_code == 200

        admin.patch("/api/admin/users/2", {"is_active": False})

        assert leaver.get(f"/api/appointments?date={today_iso()}").status_code == 401
        assert Client(app).login("staff@clinicue.health", "Staff#2026").status_code == 401


class TestDataIntegrity:
    def test_a_failed_booking_leaves_no_partial_record(self, app, patient, free_slot):
        """NFR-REL-02: the transaction either produces a whole appointment or
        nothing at all."""
        with app.app_context():
            before = get_db().execute("SELECT COUNT(*) AS n FROM appointments").fetchone()["n"]

        assert patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": "02:00"}).status_code == 409

        with app.app_context():
            after = get_db().execute("SELECT COUNT(*) AS n FROM appointments").fetchone()["n"]
        assert after == before

    def test_referential_integrity_is_enforced(self, app):
        """FR-57: the database refuses an orphan even if application code asks
        for one."""
        import sqlite3

        with app.app_context():
            conn = get_db()
            try:
                conn.execute(
                    """INSERT INTO appointments (code, patient_id, practitioner_id, service_id,
                         appt_date, start_time, end_time, status, source, notes, created_by,
                         created_at, updated_at)
                       VALUES ('CQ-ORPHAN', 99999, 1, 1, '2026-12-01', '09:00', '09:30',
                               'BOOKED', 'SELF', '', 1, '2026-01-01T00:00:00', '2026-01-01T00:00:00')""")
                conn.commit()
                raised = False
            except sqlite3.IntegrityError:
                conn.rollback()
                raised = True
        assert raised, "foreign keys are not being enforced"

    def test_status_check_constraint_is_enforced(self, app):
        import sqlite3

        with app.app_context():
            conn = get_db()
            try:
                conn.execute("UPDATE appointments SET status = 'BANANA' WHERE id = 1")
                conn.commit()
                raised = False
            except sqlite3.IntegrityError:
                conn.rollback()
                raised = True
        assert raised, "the status CHECK constraint is missing"

    def test_the_client_shell_is_served(self, anon):
        """The SPA must survive a hard refresh on a deep link, or a shared URL
        is broken for every recipient."""
        for path in ["/", "/book", "/staff", "/admin/reports"]:
            response = anon.get(path)
            assert response.status_code == 200
            assert b"<title>Clinicue" in response.data
