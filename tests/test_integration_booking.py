"""Integration tests for slot discovery, booking and cancellation
(TC-I-14 … TC-I-28 / FR-19 … FR-33)."""

from __future__ import annotations

import sqlite3

from app.db import get_db
from app.domain import add_days, today_iso


class TestCatalogue:
    def test_services_listed_for_authenticated_users(self, patient):
        response = patient.get("/api/services")
        assert response.status_code == 200
        items = response.get_json()["items"]
        assert len(items) == 5
        assert all("duration_min" in s for s in items)

    def test_practitioners_listed(self, patient):
        response = patient.get("/api/practitioners")
        assert response.status_code == 200
        assert len(response.get_json()["items"]) == 3

    def test_catalogue_requires_authentication(self, anon):
        assert anon.get("/api/services").status_code == 401
        assert anon.get("/api/practitioners").status_code == 401

    def test_deactivated_service_disappears(self, app, patient, admin):
        admin.patch("/api/admin/services/1", {"is_active": False})
        names = [s["id"] for s in patient.get("/api/services").get_json()["items"]]
        assert 1 not in names


class TestSlots:
    def test_slots_returned_for_a_working_day(self, patient, free_slot):
        response = patient.get(
            f"/api/slots?practitioner_id=1&service_id=1&date={free_slot['date']}")
        assert response.status_code == 200
        body = response.get_json()
        assert body["duration_min"] == 30
        assert all("start_time" in s and "end_time" in s for s in body["slots"])

    def test_past_dates_rejected(self, patient):
        """FR-22."""
        past = add_days(today_iso(), -1)
        response = patient.get(f"/api/slots?practitioner_id=1&service_id=1&date={past}")
        assert response.status_code == 400
        assert "date" in response.get_json()["fields"]

    def test_beyond_the_horizon_rejected(self, patient):
        """FR-23."""
        far = add_days(today_iso(), 90)
        response = patient.get(f"/api/slots?practitioner_id=1&service_id=1&date={far}")
        assert response.status_code == 400
        assert "date" in response.get_json()["fields"]

    def test_unknown_practitioner_is_not_found(self, patient):
        response = patient.get(
            f"/api/slots?practitioner_id=999&service_id=1&date={add_days(today_iso(), 3)}")
        assert response.status_code == 404

    def test_malformed_date_rejected(self, patient):
        response = patient.get("/api/slots?practitioner_id=1&service_id=1&date=12-08-2026")
        assert response.status_code == 400

    def test_missing_parameters_rejected(self, patient):
        response = patient.get("/api/slots")
        assert response.status_code == 400
        assert set(response.get_json()["fields"]) >= {"practitioner_id", "service_id", "date"}

    def test_a_day_with_no_availability_returns_an_empty_list(self, patient):
        """Sunday: the clinic is closed. An empty list, not an error — the UI
        needs to say 'closed', not 'something went wrong'."""
        date_iso = today_iso()
        for _ in range(8):
            date_iso = add_days(date_iso, 1)
            from datetime import date as _date

            if _date.fromisoformat(date_iso).weekday() == 6:
                break
        response = patient.get(f"/api/slots?practitioner_id=1&service_id=1&date={date_iso}")
        assert response.status_code == 200
        assert response.get_json()["slots"] == []


class TestBooking:
    def test_successful_booking(self, patient, free_slot):
        """TC-I-20 / FR-24, FR-25."""
        response = patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"],
        })
        assert response.status_code == 201
        body = response.get_json()
        assert body["status"] == "BOOKED"
        assert body["code"].startswith("TC-")
        assert body["start_time"] == free_slot["start_time"]
        assert body["end_time"] != body["start_time"]

    def test_booked_slot_is_withdrawn_from_the_list(self, patient, free_slot):
        """TC-I-21 / FR-21."""
        patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]})
        remaining = patient.get(
            f"/api/slots?practitioner_id=1&service_id=1&date={free_slot['date']}"
        ).get_json()["slots"]
        assert free_slot["start_time"] not in [s["start_time"] for s in remaining]

    def test_double_booking_the_same_slot_is_refused(self, app, patient, free_slot):
        """TC-I-22 / FR-26. A second patient attempts the slot the first just took."""
        patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]})

        rival = type(patient)(app)
        rival.register(full_name="Rival Patient", email="rival@example.com",
                       phone="+233241119999", password="Passw0rd1")
        response = rival.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]})
        assert response.status_code == 409
        assert response.get_json()["error"] == "SLOT_TAKEN"

    def test_database_constraint_blocks_double_booking_independently(self, app, free_slot):
        """The application check is for the message; this index is the actual
        guarantee (FR-21). Bypassing the service layer must still fail."""
        with app.app_context():
            conn = get_db()
            values = ("TC-DIRECT1", 3, 1, 1, free_slot["date"], free_slot["start_time"],
                      "23:59", "BOOKED", "SELF", "", 2, "2026-01-01T00:00:00", "2026-01-01T00:00:00")
            conn.execute(
                """INSERT INTO appointments (code, patient_id, practitioner_id, service_id,
                     appt_date, start_time, end_time, status, source, notes, created_by,
                     created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", values)
            conn.commit()
            try:
                conn.execute(
                    """INSERT INTO appointments (code, patient_id, practitioner_id, service_id,
                         appt_date, start_time, end_time, status, source, notes, created_by,
                         created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    ("TC-DIRECT2", 4, *values[2:]))
                raised = False
            except sqlite3.IntegrityError:
                raised = True
            conn.rollback()
        assert raised, "the partial unique index did not prevent a double booking"

    def test_same_patient_cannot_book_the_practitioner_twice_in_a_day(self, patient, free_slot):
        """TC-I-23 / FR-27."""
        assert len(free_slot["all"]) >= 2, "need two free slots for this test"
        first = patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["all"][0]})
        assert first.status_code == 201
        second = patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["all"][1]})
        assert second.status_code == 409
        assert second.get_json()["error"] == "DUPLICATE_BOOKING"

    def test_a_time_outside_availability_is_refused(self, patient, free_slot):
        """A hand-crafted request for 03:00 must not be honoured just because
        the client did not offer it."""
        response = patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": "03:00"})
        assert response.status_code == 409

    def test_booking_in_the_past_is_refused(self, patient):
        response = patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": add_days(today_iso(), -3), "start_time": "09:00"})
        assert response.status_code == 400

    def test_booking_requires_authentication(self, anon, free_slot):
        response = anon.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]})
        assert response.status_code == 401

    def test_a_patient_cannot_book_for_someone_else(self, patient, free_slot):
        """Privilege check: patient_id in the body is ignored for patients."""
        response = patient.post("/api/appointments", {
            "patient_id": 5, "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]})
        assert response.status_code == 201
        assert response.get_json()["patient_id"] == patient.user["id"]

    def test_staff_may_book_on_behalf_of_a_patient(self, staff, free_slot):
        """FR-32."""
        response = staff.post("/api/appointments", {
            "patient_id": 5, "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]})
        assert response.status_code == 201
        body = response.get_json()
        assert body["patient_id"] == 5
        assert body["source"] == "STAFF"

    def test_staff_booking_for_an_unknown_patient_is_rejected(self, staff, free_slot):
        response = staff.post("/api/appointments", {
            "patient_id": 9999, "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]})
        assert response.status_code == 400
        assert "patient_id" in response.get_json()["fields"]


class TestOwnAppointments:
    def test_patient_sees_only_their_own(self, patient):
        """FR-28, FR-30."""
        items = patient.get("/api/appointments/mine?scope=all").get_json()["items"]
        assert items
        assert all(a["patient_id"] == patient.user["id"] for a in items)

    def test_upcoming_and_past_are_separated(self, patient):
        upcoming = patient.get("/api/appointments/mine?scope=upcoming").get_json()["items"]
        assert all(a["date"] >= today_iso() for a in upcoming)
        assert all(a["status"] in {"BOOKED", "CHECKED_IN", "IN_PROGRESS"} for a in upcoming)

    def test_another_patients_appointment_returns_404_not_403(self, app, patient):
        """TC-I-24 / FR-30. 403 would confirm the id exists."""
        with app.app_context():
            row = get_db().execute(
                "SELECT id FROM appointments WHERE patient_id <> ? LIMIT 1",
                (patient.user["id"],)).fetchone()
        response = patient.get(f"/api/appointments/{row['id']}")
        assert response.status_code == 404

    def test_staff_may_read_any_appointment(self, app, staff):
        with app.app_context():
            row = get_db().execute("SELECT id FROM appointments LIMIT 1").fetchone()
        assert staff.get(f"/api/appointments/{row['id']}").status_code == 200


class TestCancellation:
    def test_patient_can_cancel_their_own(self, patient, free_slot):
        """TC-I-25 / FR-29."""
        booking = patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]}).get_json()
        response = patient.post(f"/api/appointments/{booking['id']}/cancel")
        assert response.status_code == 200
        assert response.get_json()["status"] == "CANCELLED"

    def test_cancellation_returns_the_slot_to_the_pool(self, patient, free_slot):
        """TC-I-26. This is what the partial unique index makes possible."""
        booking = patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]}).get_json()
        patient.post(f"/api/appointments/{booking['id']}/cancel")
        slots = patient.get(
            f"/api/slots?practitioner_id=1&service_id=1&date={free_slot['date']}"
        ).get_json()["slots"]
        assert free_slot["start_time"] in [s["start_time"] for s in slots]

    def test_the_released_slot_can_be_rebooked(self, app, patient, free_slot):
        booking = patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]}).get_json()
        patient.post(f"/api/appointments/{booking['id']}/cancel")

        other = type(patient)(app)
        other.register(full_name="Second Chance", email="second@example.com",
                       phone="+233241118888", password="Passw0rd1")
        response = other.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]})
        assert response.status_code == 201

    def test_cancelling_twice_is_refused(self, patient, free_slot):
        """FR-31."""
        booking = patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]}).get_json()
        patient.post(f"/api/appointments/{booking['id']}/cancel")
        response = patient.post(f"/api/appointments/{booking['id']}/cancel")
        assert response.status_code == 409
        assert response.get_json()["error"] == "INVALID_TRANSITION"

    def test_cancelling_someone_elses_appointment_returns_404(self, app, patient):
        """TC-I-27 / FR-30. The highest-impact IDOR in this design."""
        with app.app_context():
            row = get_db().execute(
                "SELECT id FROM appointments WHERE patient_id <> ? AND status = 'BOOKED' LIMIT 1",
                (patient.user["id"],)).fetchone()
        if row is None:
            return
        assert patient.post(f"/api/appointments/{row['id']}/cancel").status_code == 404

    def test_a_completed_appointment_cannot_be_cancelled(self, app, patient):
        """FR-31: reporting integrity depends on this."""
        with app.app_context():
            row = get_db().execute(
                "SELECT id FROM appointments WHERE patient_id = ? AND status = 'COMPLETED' LIMIT 1",
                (patient.user["id"],)).fetchone()
        if row is None:
            return
        assert patient.post(f"/api/appointments/{row['id']}/cancel").status_code == 409


class TestDaySheet:
    def test_staff_can_read_the_day_sheet(self, staff):
        """FR-33."""
        response = staff.get(f"/api/appointments?date={today_iso()}")
        assert response.status_code == 200
        assert "items" in response.get_json()

    def test_patients_cannot(self, patient):
        assert patient.get(f"/api/appointments?date={today_iso()}").status_code == 403

    def test_filters_apply(self, staff):
        body = staff.get(
            f"/api/appointments?date={today_iso()}&practitioner_id=1&status=BOOKED").get_json()
        assert all(a["practitioner_id"] == 1 for a in body["items"])
        assert all(a["status"] == "BOOKED" for a in body["items"])

    def test_unknown_status_filter_is_rejected(self, staff):
        response = staff.get(f"/api/appointments?date={today_iso()}&status=NONSENSE")
        assert response.status_code == 400

    def test_search_matches_a_patient_name(self, staff):
        body = staff.get(f"/api/appointments?date={today_iso()}&q=Kojo").get_json()
        assert all("Kojo" in a["patient_name"] for a in body["items"])
