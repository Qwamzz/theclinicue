"""Integration tests for administration, audit and reporting
(TC-I-39 … TC-I-47 / FR-14 … FR-18, FR-45 … FR-52)."""

from __future__ import annotations

from app.db import get_db
from app.domain import add_days, today_iso


class TestServiceManagement:
    def test_admin_can_create_a_service(self, admin):
        """FR-14, FR-16."""
        response = admin.post("/api/admin/services", {
            "name": "Eye Screening", "description": "Vision check", "duration_min": 25})
        assert response.status_code == 201
        assert response.get_json()["duration_min"] == 25

    def test_duplicate_service_name_rejected(self, admin):
        response = admin.post("/api/admin/services", {
            "name": "General Consultation", "duration_min": 30})
        assert response.status_code == 400
        assert "name" in response.get_json()["fields"]

    def test_out_of_range_duration_rejected(self, admin):
        for duration in (2, 500):
            response = admin.post("/api/admin/services", {
                "name": f"Bad {duration}", "duration_min": duration})
            assert response.status_code == 400

    def test_service_can_be_retired_and_restored(self, admin):
        assert admin.patch("/api/admin/services/1", {"is_active": False}).get_json()["is_active"] == 0
        assert admin.patch("/api/admin/services/1", {"is_active": True}).get_json()["is_active"] == 1

    def test_staff_cannot_manage_services(self, staff):
        assert staff.get("/api/admin/services").status_code == 403
        assert staff.post("/api/admin/services", {"name": "X", "duration_min": 30}).status_code == 403


class TestPractitionerManagement:
    def test_admin_can_create_a_practitioner(self, admin):
        """FR-15."""
        response = admin.post("/api/admin/practitioners", {
            "full_name": "Dr Nana Amoah", "specialty": "Dermatology", "room": "Room 7"})
        assert response.status_code == 201
        assert response.get_json()["full_name"] == "Dr Nana Amoah"

    def test_deactivated_practitioner_cannot_be_booked(self, admin, patient):
        admin.patch("/api/admin/practitioners/1", {"is_active": False})
        response = patient.get(
            f"/api/slots?practitioner_id=1&service_id=1&date={add_days(today_iso(), 3)}")
        assert response.status_code == 404

    def test_short_name_rejected(self, admin):
        response = admin.post("/api/admin/practitioners", {"full_name": "X"})
        assert response.status_code == 400


class TestAvailability:
    def test_admin_can_add_a_window(self, admin):
        """FR-17."""
        response = admin.post("/api/admin/availability", {
            "practitioner_id": 2, "weekday": 5, "start_time": "09:00", "end_time": "12:00"})
        assert response.status_code == 201

    def test_end_before_start_is_rejected_with_a_field_message(self, admin):
        """TC-I-41 / FR-18. The CHECK constraint is the backstop, but the user
        deserves a message naming the field."""
        response = admin.post("/api/admin/availability", {
            "practitioner_id": 2, "weekday": 5, "start_time": "12:00", "end_time": "09:00"})
        assert response.status_code == 400
        assert "end_time" in response.get_json()["fields"]

    def test_equal_start_and_end_rejected(self, admin):
        response = admin.post("/api/admin/availability", {
            "practitioner_id": 2, "weekday": 5, "start_time": "09:00", "end_time": "09:00"})
        assert response.status_code == 400

    def test_overlapping_window_rejected(self, admin):
        """Overlapping rules would generate the same slot twice in the diary
        and make utilisation meaningless."""
        admin.post("/api/admin/availability", {
            "practitioner_id": 2, "weekday": 6, "start_time": "09:00", "end_time": "12:00"})
        response = admin.post("/api/admin/availability", {
            "practitioner_id": 2, "weekday": 6, "start_time": "11:00", "end_time": "14:00"})
        assert response.status_code == 409

    def test_adjacent_windows_are_allowed(self, admin):
        """08:00-12:00 followed by 12:00-16:00 is a lunch-free day, not a clash."""
        admin.post("/api/admin/availability", {
            "practitioner_id": 2, "weekday": 4, "start_time": "08:00", "end_time": "12:00"})
        response = admin.post("/api/admin/availability", {
            "practitioner_id": 2, "weekday": 4, "start_time": "12:00", "end_time": "16:00"})
        assert response.status_code == 201

    def test_new_availability_produces_bookable_slots(self, admin, patient):
        """End-to-end proof that availability is genuinely the source of slots."""
        from datetime import date

        target = add_days(today_iso(), 1)
        for _ in range(7):
            if date.fromisoformat(target).weekday() == 6:
                break
            target = add_days(target, 1)

        before = patient.get(
            f"/api/slots?practitioner_id=2&service_id=1&date={target}").get_json()["slots"]
        assert before == []

        admin.post("/api/admin/availability", {
            "practitioner_id": 2, "weekday": 6, "start_time": "10:00", "end_time": "12:00"})
        after = patient.get(
            f"/api/slots?practitioner_id=2&service_id=1&date={target}").get_json()["slots"]
        assert [s["start_time"] for s in after] == ["10:00", "10:30", "11:00", "11:30"]

    def test_removing_a_window_withdraws_its_slots(self, admin, patient):
        rules = admin.get("/api/admin/availability?practitioner_id=1").get_json()["items"]
        rule = rules[0]
        assert admin.delete(f"/api/admin/availability/{rule['id']}").status_code == 200
        remaining = admin.get("/api/admin/availability?practitioner_id=1").get_json()["items"]
        assert next(r for r in remaining if r["id"] == rule["id"])["is_active"] == 0


class TestUserAdministration:
    def test_admin_can_list_users(self, admin):
        """FR-45."""
        body = admin.get("/api/admin/users").get_json()
        assert body["total"] >= 11
        assert all("password_hash" not in u for u in body["items"])

    def test_search_and_role_filter(self, admin):
        body = admin.get("/api/admin/users?role=STAFF").get_json()
        assert all(u["role"] == "STAFF" for u in body["items"])
        body = admin.get("/api/admin/users?q=Kojo").get_json()
        assert body["items"]

    def test_admin_can_promote_a_patient_to_staff(self, admin):
        """FR-46."""
        response = admin.patch("/api/admin/users/4", {"role": "STAFF", "is_active": True})
        assert response.status_code == 200
        assert response.get_json()["role"] == "STAFF"

    def test_admin_can_deactivate_an_account(self, admin, app):
        assert admin.patch("/api/admin/users/4", {"is_active": False}).get_json()["is_active"] == 0
        client = type(admin)(app)
        assert client.login("kofi.boateng@example.com", "Patient#2026").status_code == 401

    def test_admin_cannot_demote_themselves(self, admin):
        """TC-I-43 / FR-47. Without this the last administrator can lock the
        clinic out of its own configuration, irreversibly."""
        response = admin.patch(f"/api/admin/users/{admin.user['id']}", {"role": "PATIENT"})
        assert response.status_code == 403
        assert "another administrator" in response.get_json()["message"]

    def test_admin_cannot_deactivate_themselves(self, admin):
        response = admin.patch(f"/api/admin/users/{admin.user['id']}", {"is_active": False})
        assert response.status_code == 403

    def test_invalid_role_rejected(self, admin):
        response = admin.patch("/api/admin/users/4", {"role": "SUPERUSER"})
        assert response.status_code == 400

    def test_staff_cannot_manage_users(self, staff):
        assert staff.get("/api/admin/users").status_code == 403
        assert staff.patch("/api/admin/users/4", {"role": "ADMIN"}).status_code == 403


class TestAudit:
    def test_audit_log_is_readable_by_admin(self, admin):
        """FR-49."""
        body = admin.get("/api/admin/audit").get_json()
        assert body["total"] > 0
        assert {"action", "created_at", "ip_address"} <= set(body["items"][0])

    def test_audit_is_newest_first(self, admin):
        items = admin.get("/api/admin/audit?limit=20").get_json()["items"]
        assert [i["id"] for i in items] == sorted((i["id"] for i in items), reverse=True)

    def test_actions_are_recorded(self, admin, patient, free_slot):
        """FR-48: the booking must leave a trace naming the actor."""
        patient.post("/api/appointments", {
            "practitioner_id": 1, "service_id": 1,
            "date": free_slot["date"], "start_time": free_slot["start_time"]})
        items = admin.get("/api/admin/audit?action=BOOK_APPOINTMENT").get_json()["items"]
        assert items
        assert items[0]["actor_email"] == "patient@clinicue.health"

    def test_denied_access_is_recorded(self, admin, patient):
        """FR-12: a failed authorisation attempt is exactly what a reviewer
        needs to see."""
        patient.get(f"/api/appointments?date={today_iso()}")
        items = admin.get("/api/admin/audit?action=ACCESS_DENIED").get_json()["items"]
        assert items

    def test_staff_cannot_read_the_audit_log(self, staff):
        assert staff.get("/api/admin/audit").status_code == 403


class TestReports:
    def test_daily_summary_shape(self, admin):
        """FR-50."""
        body = admin.get("/api/admin/reports/daily").get_json()
        assert {"total", "by_status", "no_show_rate", "mean_wait_minutes"} <= set(body)
        assert sum(body["by_status"].values()) == body["total"]

    def test_no_show_rate_excludes_cancellations(self, app, admin):
        """The denominator is people who were expected to attend. Including
        cancellations would flatter the figure and mislead staffing decisions."""
        from app.db import get_db as db
        from app.services.reports import daily_summary

        with app.app_context():
            conn = db()
            conn.execute("DELETE FROM queue_entries")
            conn.execute("DELETE FROM appointments")
            stamp = "2026-08-12T09:00:00"
            # A distinct patient per row: FR-27 allows only one live
            # appointment per patient, practitioner and day.
            for index, status in enumerate(["COMPLETED", "COMPLETED", "NO_SHOW", "CANCELLED"]):
                conn.execute(
                    """INSERT INTO appointments (code, patient_id, practitioner_id, service_id,
                         appt_date, start_time, end_time, status, source, notes, created_by,
                         created_at, updated_at)
                       VALUES (?, ?, 1, 1, ?, ?, ?, ?, 'SELF', '', 2, ?, ?)""",
                    (f"CQ-RPT{index:03d}", 3 + index, today_iso(), f"{8 + index:02d}:00",
                     f"{8 + index:02d}:30", status, stamp, stamp))
            conn.commit()
            summary = daily_summary(conn, today_iso())

        # 3 expected (2 completed + 1 no-show); 1/3 = 33.3%, not 1/4 = 25%.
        assert summary["total"] == 4
        assert summary["expected"] == 3
        assert summary["no_show_rate"] == 33.3

    def test_mean_wait_is_null_when_nobody_has_been_called(self, app):
        """'No data' and 'no wait' are different facts."""
        from app.db import get_db as db
        from app.services.reports import mean_wait_minutes

        with app.app_context():
            conn = db()
            conn.execute("DELETE FROM queue_entries")
            conn.commit()
            assert mean_wait_minutes(conn, today_iso()) is None

    def test_utilisation_report(self, admin):
        """FR-51."""
        body = admin.get("/api/admin/reports/utilisation").get_json()
        assert body["items"]
        for row in body["items"]:
            assert {"slots_offered", "appointments", "utilisation_pct"} <= set(row)

    def test_utilisation_rejects_a_reversed_range(self, admin):
        response = admin.get(
            f"/api/admin/reports/utilisation?from={today_iso()}&to={add_days(today_iso(), -5)}")
        assert response.status_code == 400

    def test_reports_are_admin_only(self, staff, patient):
        assert staff.get("/api/admin/reports/daily").status_code == 403
        assert patient.get("/api/admin/reports/daily").status_code == 403
