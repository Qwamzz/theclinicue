"""End-to-end smoke run against an in-process app. Not part of the test suite;
this is the quick manual sanity check used during development."""

from __future__ import annotations

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from app import create_app                      # noqa: E402
from app.db import get_db                       # noqa: E402
from app.domain import add_days, today_iso      # noqa: E402
from app.seed import seed                       # noqa: E402


def call(client, method, path, csrf=None, **kwargs):
    headers = {"X-CSRF-Token": csrf} if csrf else {}
    response = getattr(client, method)(path, headers=headers, **kwargs)
    return response.status_code, response.get_json()


def main() -> int:
    app = create_app(env="testing", database_path=":memory:")
    with app.app_context():
        seed(get_db())

    failures = []

    def check(label, condition, detail=""):
        mark = "ok  " if condition else "FAIL"
        print(f"{mark} {label}{(' — ' + str(detail)) if detail and not condition else ''}")
        if not condition:
            failures.append(label)

    patient = app.test_client()
    staff = app.test_client()
    admin = app.test_client()

    # --- login -----------------------------------------------------------
    status, body = call(patient, "post", "/api/auth/login",
                        json={"email": "patient@clinicue.health", "password": "Patient#2026"})
    check("patient login", status == 200, body)
    p_csrf = body["csrf_token"]

    status, body = call(staff, "post", "/api/auth/login",
                        json={"email": "staff@clinicue.health", "password": "Staff#2026"})
    check("staff login", status == 200, body)
    s_csrf = body["csrf_token"]

    status, body = call(admin, "post", "/api/auth/login",
                        json={"email": "admin@clinicue.health", "password": "Admin#2026"})
    check("admin login", status == 200, body)
    a_csrf = body["csrf_token"]

    # --- RBAC ------------------------------------------------------------
    status, body = call(patient, "get", "/api/appointments?date=" + today_iso())
    check("patient blocked from day sheet (403)", status == 403, (status, body))

    status, body = call(staff, "get", "/api/admin/users")
    check("staff blocked from admin users (403)", status == 403, (status, body))

    status, body = call(admin, "get", "/api/admin/users")
    check("admin can list users", status == 200 and body["total"] >= 11, (status, body))

    # --- CSRF ------------------------------------------------------------
    status, body = call(staff, "post", "/api/queue/call-next", json={"practitioner_id": 1})
    check("state change without CSRF header rejected", status == 403 and body["error"] == "CSRF_INVALID",
          (status, body))

    # --- slots and booking ------------------------------------------------
    target = add_days(today_iso(), 7)
    for _ in range(10):
        status, body = call(patient, "get",
                            f"/api/slots?practitioner_id=1&service_id=1&date={target}")
        if status == 200 and body["slots"]:
            break
        target = add_days(target, 1)
    check("slots returned", status == 200 and len(body["slots"]) > 0, (status, body))
    slot = body["slots"][0]["start_time"]

    status, booking = call(patient, "post", "/api/appointments", csrf=p_csrf,
                           json={"practitioner_id": 1, "service_id": 1,
                                 "date": target, "start_time": slot})
    check("booking created", status == 201 and booking["code"].startswith("CQ-"), (status, booking))

    # slot must disappear
    status, body = call(patient, "get", f"/api/slots?practitioner_id=1&service_id=1&date={target}")
    check("booked slot no longer offered",
          slot not in [s["start_time"] for s in body["slots"]], body)

    # duplicate booking blocked
    status, body = call(patient, "post", "/api/appointments", csrf=p_csrf,
                        json={"practitioner_id": 1, "service_id": 1,
                              "date": target, "start_time": slot})
    check("duplicate rejected with 409", status == 409, (status, body))

    # --- IDOR -------------------------------------------------------------
    other = app.test_client()
    call(other, "post", "/api/auth/register",
         json={"full_name": "Nosey Parker", "email": "nosey@example.com",
               "phone": "+233240000999", "password": "Passw0rd1"})
    status, body = call(other, "get", f"/api/appointments/{booking['id']}")
    check("other patient cannot read the appointment (404)", status == 404, (status, body))

    # --- check-in and queue ----------------------------------------------
    status, body = call(staff, "post", "/api/queue/check-in", csrf=s_csrf,
                        json={"appointment_id": booking["id"]})
    check("future appointment cannot be checked in", status == 409, (status, body))

    today_sheet_status, sheet = call(staff, "get", f"/api/appointments?date={today_iso()}&status=BOOKED")
    check("day sheet readable by staff", today_sheet_status == 200, sheet)

    if sheet.get("items"):
        appt = sheet["items"][0]
        status, entry = call(staff, "post", "/api/queue/check-in", csrf=s_csrf,
                             json={"appointment_id": appt["id"]})
        check("check-in succeeds", status == 201 and entry["ticket_no"] >= 1, (status, entry))

        status, body = call(staff, "post", "/api/queue/check-in", csrf=s_csrf,
                            json={"appointment_id": appt["id"]})
        check("double check-in rejected", status == 409, (status, body))

        status, body = call(staff, "post", "/api/queue/call-next", csrf=s_csrf,
                            json={"practitioner_id": appt["practitioner_id"]})
        check("call next returns a patient", status == 200 and body.get("called"), (status, body))

        called_id = body["called"]["appointment_id"]
        status, body = call(staff, "post", "/api/queue/complete", csrf=s_csrf,
                            json={"appointment_id": called_id})
        check("complete succeeds", status == 200 and body["status"] == "COMPLETED", (status, body))

        status, body = call(staff, "post", "/api/queue/complete", csrf=s_csrf,
                            json={"appointment_id": called_id})
        check("completing twice rejected", status == 409, (status, body))

        status, body = call(patient, "get", f"/api/queue?practitioner_id={appt['practitioner_id']}")
        check("live queue readable", status == 200, (status, body))
        names = [w["name"] for w in body["waiting"]]
        check("queue names are masked", all("*" in n for n in names) if names else True, names)

    # --- reports ----------------------------------------------------------
    status, body = call(admin, "get", "/api/admin/reports/daily")
    check("daily report", status == 200 and "no_show_rate" in body, (status, body))

    status, body = call(admin, "get", "/api/admin/reports/utilisation")
    check("utilisation report", status == 200 and body["items"], (status, body))

    status, body = call(admin, "get", "/api/admin/audit?limit=5")
    check("audit log populated", status == 200 and body["total"] > 0, (status, body))

    # --- self-demotion guard ---------------------------------------------
    status, body = call(admin, "patch", "/api/admin/users/1", csrf=a_csrf,
                        json={"role": "PATIENT", "is_active": True})
    check("admin cannot demote self", status == 403, (status, body))

    # --- cancellation -----------------------------------------------------
    status, body = call(patient, "post", f"/api/appointments/{booking['id']}/cancel", csrf=p_csrf)
    check("cancel succeeds", status == 200 and body["status"] == "CANCELLED", (status, body))

    status, body = call(patient, "get", f"/api/slots?practitioner_id=1&service_id=1&date={target}")
    check("cancelled slot returns to the pool",
          slot in [s["start_time"] for s in body["slots"]], body["slots"])

    print()
    if failures:
        print(f"{len(failures)} FAILED: {failures}")
        return 1
    print("all smoke checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
