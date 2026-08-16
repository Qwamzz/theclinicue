"""Integration tests for check-in and the consultation queue
(TC-I-29 to TC-I-38 / FR-34 to FR-44)."""

from __future__ import annotations

from app.db import get_db
from app.domain import add_days, today_iso


class TestCheckIn:
    def test_staff_can_check_a_patient_in(self, staff, today_booking):
        """TC-I-29 / FR-34, FR-35."""
        response = staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        assert response.status_code == 201
        body = response.get_json()
        assert body["ticket_no"] >= 1
        assert body["status"] == "WAITING"
        assert body["ticket"].startswith("A-")

    def test_check_in_moves_the_appointment_to_checked_in(self, staff, today_booking):
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        detail = staff.get(f"/api/appointments/{today_booking['id']}").get_json()
        assert detail["status"] == "CHECKED_IN"

    def test_double_check_in_is_refused(self, staff, today_booking):
        """TC-I-30 / FR-36. Duplicate queue entries corrupt ordering and the
        waiting-time metric."""
        assert staff.post("/api/queue/check-in",
                          {"appointment_id": today_booking["id"]}).status_code == 201
        response = staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        assert response.status_code == 409
        assert response.get_json()["error"] == "ALREADY_CHECKED_IN"

    def test_a_future_appointment_cannot_be_checked_in(self, app, staff, patient, free_slot):
        """TC-I-31 / FR-37."""
        booking = patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]}).get_json()
        response = staff.post("/api/queue/check-in", {"appointment_id": booking["id"]})
        assert response.status_code == 409
        assert free_slot["date"] in response.get_json()["message"]

    def test_patients_cannot_check_themselves_in(self, patient, today_booking):
        """FR-12: check-in is a front-desk act; self check-in would let a
        patient jump the queue from the car park."""
        assert patient.post("/api/queue/check-in",
                            {"appointment_id": today_booking["id"]}).status_code == 403

    def test_unknown_appointment_is_not_found(self, staff):
        assert staff.post("/api/queue/check-in", {"appointment_id": 999999}).status_code == 404

    def test_missing_appointment_id_is_a_validation_error(self, staff):
        response = staff.post("/api/queue/check-in", {})
        assert response.status_code == 400
        assert "appointment_id" in response.get_json()["fields"]

    def test_ticket_numbers_increase_within_a_practitioner_and_day(self, app, staff):
        """TC-I-32 / FR-35.

        Practitioner 2's diary for today is cleared first. Reusing whatever the
        seed happened to generate makes the test depend on the weekday it runs
        on: FR-27 allows one live appointment per patient, practitioner and day,
        so a seeded clash raises IntegrityError on some days and not others.
        (This test did exactly that when the date rolled over - see TD-08.)
        """
        from app.domain import to_hhmm, utc_stamp

        ids = []
        with app.app_context():
            conn = get_db()
            conn.execute(
                """DELETE FROM queue_entries WHERE appointment_id IN
                     (SELECT id FROM appointments
                       WHERE practitioner_id = 2 AND appt_date = ?)""",
                (today_iso(),))
            conn.execute(
                "DELETE FROM appointments WHERE practitioner_id = 2 AND appt_date = ?",
                (today_iso(),))

            start = 9 * 60
            for index, patient_id in enumerate((3, 4, 5)):
                stamp = utc_stamp()
                cursor = conn.execute(
                    """INSERT INTO appointments (code, patient_id, practitioner_id, service_id,
                         appt_date, start_time, end_time, status, source, notes, created_by,
                         created_at, updated_at)
                       VALUES (?, ?, 2, 2, ?, ?, ?, 'BOOKED', 'STAFF', '', 2, ?, ?)""",
                    (f"TC-SEQ{index:03d}", patient_id, today_iso(),
                     to_hhmm(start + index * 45), to_hhmm(start + (index + 1) * 45), stamp, stamp))
                ids.append(int(cursor.lastrowid))
            conn.commit()

        tickets = [staff.post("/api/queue/check-in", {"appointment_id": i}).get_json()["ticket_no"]
                   for i in ids]
        assert tickets == sorted(tickets)
        assert len(set(tickets)) == 3


class TestCallNext:
    def test_call_next_serves_the_earliest_ticket(self, staff, today_booking):
        """TC-I-33 / FR-38."""
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        response = staff.post("/api/queue/call-next", {"practitioner_id": 1})
        assert response.status_code == 200
        called = response.get_json()["called"]
        assert called["appointment_id"] == today_booking["id"]

    def test_calling_moves_the_appointment_to_in_progress(self, staff, today_booking):
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        staff.post("/api/queue/call-next", {"practitioner_id": 1})
        detail = staff.get(f"/api/appointments/{today_booking['id']}").get_json()
        assert detail["status"] == "IN_PROGRESS"

    def test_an_empty_queue_is_not_an_error(self, staff):
        """TC-I-34 / FR-39. 'Nobody is waiting' is normal operation."""
        response = staff.post("/api/queue/call-next", {"practitioner_id": 3})
        assert response.status_code == 200
        assert response.get_json()["called"] is None
        assert "waiting" in response.get_json()["message"].lower()

    def test_the_same_patient_is_not_called_twice(self, staff, today_booking):
        """FR-39: a second click must not re-call the person already in the room."""
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        first = staff.post("/api/queue/call-next", {"practitioner_id": 1}).get_json()["called"]
        second = staff.post("/api/queue/call-next", {"practitioner_id": 1}).get_json()["called"]
        assert first is not None
        assert second is None or second["appointment_id"] != first["appointment_id"]

    def test_patients_cannot_call_the_queue(self, patient):
        assert patient.post("/api/queue/call-next", {"practitioner_id": 1}).status_code == 403


class TestCompletionAndNoShow:
    def test_complete_closes_the_consultation(self, staff, today_booking):
        """TC-I-35 / FR-40."""
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        staff.post("/api/queue/call-next", {"practitioner_id": 1})
        response = staff.post("/api/queue/complete", {"appointment_id": today_booking["id"]})
        assert response.status_code == 200
        assert response.get_json()["status"] == "COMPLETED"

    def test_completing_a_booked_appointment_is_refused(self, staff, today_booking):
        """TC-I-36 / FR-43: BOOKED -> COMPLETED is not a legal transition."""
        response = staff.post("/api/queue/complete", {"appointment_id": today_booking["id"]})
        assert response.status_code == 409
        assert response.get_json()["error"] == "INVALID_TRANSITION"

    def test_completing_twice_is_refused(self, staff, today_booking):
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        staff.post("/api/queue/call-next", {"practitioner_id": 1})
        staff.post("/api/queue/complete", {"appointment_id": today_booking["id"]})
        assert staff.post("/api/queue/complete",
                          {"appointment_id": today_booking["id"]}).status_code == 409

    def test_no_show_from_booked(self, staff, today_booking):
        """TC-I-37 / FR-41."""
        response = staff.post("/api/queue/no-show", {"appointment_id": today_booking["id"]})
        assert response.status_code == 200
        assert response.get_json()["status"] == "NO_SHOW"

    def test_no_show_from_checked_in(self, staff, today_booking):
        """A patient who left before being called."""
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        assert staff.post("/api/queue/no-show",
                          {"appointment_id": today_booking["id"]}).status_code == 200

    def test_no_show_after_completion_is_refused(self, staff, today_booking):
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        staff.post("/api/queue/call-next", {"practitioner_id": 1})
        staff.post("/api/queue/complete", {"appointment_id": today_booking["id"]})
        assert staff.post("/api/queue/no-show",
                          {"appointment_id": today_booking["id"]}).status_code == 409

    def test_no_show_marks_the_queue_entry_skipped(self, app, staff, today_booking):
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        staff.post("/api/queue/no-show", {"appointment_id": today_booking["id"]})
        with app.app_context():
            row = get_db().execute(
                "SELECT status FROM queue_entries WHERE appointment_id = ?",
                (today_booking["id"],)).fetchone()
        assert row["status"] == "SKIPPED"

    def test_a_no_show_slot_is_not_released(self, app, staff, today_booking):
        """A no-show still consumed the clinician's time; releasing the slot
        would overstate capacity and understate the cost of no-shows."""
        staff.post("/api/queue/no-show", {"appointment_id": today_booking["id"]})
        slots = staff.get(
            f"/api/slots?practitioner_id=1&service_id=1&date={today_iso()}"
        ).get_json()["slots"]
        assert today_booking["start_time"] not in [s["start_time"] for s in slots]


class TestLiveQueue:
    def test_queue_is_visible_and_names_are_masked(self, staff, patient, today_booking):
        """TC-I-38 / FR-42, NFR-LEG-03."""
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        body = patient.get("/api/queue?practitioner_id=1").get_json()
        assert body["waiting_count"] >= 1
        for entry in body["waiting"]:
            assert "*" in entry["name"]
            assert "position" in entry

    def test_full_names_never_appear_in_the_queue_payload(self, app, staff, patient, today_booking):
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        raw = patient.get("/api/queue?practitioner_id=1").get_data(as_text=True)
        with app.app_context():
            names = [r["full_name"] for r in
                     get_db().execute("SELECT full_name FROM users WHERE role = 'PATIENT'")]
        for name in names:
            assert name not in raw

    def test_now_serving_reflects_the_called_patient(self, staff, today_booking):
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        staff.post("/api/queue/call-next", {"practitioner_id": 1})
        body = staff.get("/api/queue?practitioner_id=1").get_json()
        assert body["now_serving"] is not None

    def test_queue_requires_authentication(self, anon):
        assert anon.get("/api/queue?practitioner_id=1").status_code == 401

    def test_patient_sees_their_own_position(self, app, staff, today_booking):
        """FR-44."""
        staff.post("/api/queue/check-in", {"appointment_id": today_booking["id"]})
        patient_client = type(staff)(app)
        patient_client.login("patient@theclinicue.com", "Patient#2026")
        body = patient_client.get("/api/queue/my-position").get_json()
        assert body["position"] is not None
        assert body["position"]["ticket"].startswith("A-")
        assert body["position"]["ahead"] >= 0

    def test_position_is_null_for_a_patient_not_in_the_queue(self, anon):
        """Not an error: the client uses null to decide whether to draw the
        ticket card at all."""
        anon.register(full_name="Not Queued", email="notqueued@example.com",
                      phone="+233241117777", password="Passw0rd1")
        assert anon.get("/api/queue/my-position").get_json()["position"] is None
