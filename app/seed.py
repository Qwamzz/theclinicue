"""Demonstration data.

Doubles as the integration-test fixture (estimation mitigation M5), which is
why it is importable as well as runnable. The coupling between demonstration
data and test data is recorded as TD-08.

    python -m app.seed            # populate if empty
    python -m app.seed --reset    # wipe and repopulate
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys

from .config import load_config
from .db import _connect, init_schema, insert, query_one, scalar
from .domain import (
    BOOKED,
    CANCELLED,
    COMPLETED,
    NO_SHOW,
    Q_DONE,
    Q_SKIPPED,
    ROLE_ADMIN,
    ROLE_PATIENT,
    ROLE_STAFF,
    SOURCE_SELF,
    add_days,
    new_appointment_code,
    to_hhmm,
    to_minutes,
    today_iso,
    utc_stamp,
    weekday_of,
)
from .security import hash_password

# Demonstration credentials. Documented in the User Manual and in
# Deployment_and_Source_Links.txt; they are safe to publish precisely because
# the deployment holds no real patient data.
DEMO_PASSWORD = {
    ROLE_ADMIN: "Admin#2026",
    ROLE_STAFF: "Staff#2026",
    ROLE_PATIENT: "Patient#2026",
}

SERVICES = [
    ("General Consultation", "Routine outpatient consultation with a clinician.", 30),
    ("Antenatal Review", "Scheduled antenatal check for expectant mothers.", 45),
    ("Child Welfare Clinic", "Growth monitoring and immunisation for under-fives.", 20),
    ("Chronic Care Review", "Follow-up for hypertension and diabetes.", 30),
    ("Minor Wound Dressing", "Dressing changes and simple wound care.", 15),
]

PRACTITIONERS = [
    ("Dr Akosua Mensah", "General Practice", "Room 2"),
    ("Dr Kwabena Owusu", "Obstetrics", "Room 5"),
    ("Nurse Adjoa Tetteh", "Child Health", "Room 1"),
]

# (practitioner index, weekdays, start, end) — 0 = Monday
AVAILABILITY = [
    (0, [0, 1, 2, 3, 4], "08:00", "12:00"),
    (0, [0, 2, 4], "13:00", "16:00"),
    (1, [1, 3], "09:00", "13:00"),
    (2, [0, 1, 2, 3, 4], "08:30", "12:30"),
]

PATIENTS = [
    ("Kofi Boateng", "kofi.boateng@example.com", "+233 24 111 2201"),
    ("Ama Serwaa", "ama.serwaa@example.com", "+233 20 555 8834"),
    ("Yaw Darko", "yaw.darko@example.com", "+233 27 402 9911"),
    ("Efua Nyarko", "efua.nyarko@example.com", "+233 55 776 3410"),
    ("Kwame Asante", "kwame.asante@example.com", "+233 24 908 1177"),
    ("Abena Frimpong", "abena.frimpong@example.com", "+233 26 330 4455"),
    ("Yaa Adjei", "yaa.adjei@example.com", "+233 50 214 6688"),
    ("Kojo Antwi", "kojo.antwi@example.com", "+233 24 667 2093"),
]


def _create_user(conn: sqlite3.Connection, name: str, email: str, phone: str, role: str,
                 hash_method: str | None = None) -> int:
    return insert(
        conn,
        """INSERT INTO users (full_name, email, phone, password_hash, role, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, 1, ?)""",
        (name, email, phone, hash_password(DEMO_PASSWORD[role], hash_method), role, utc_stamp()),
    )


def seed(conn: sqlite3.Connection, *, reset: bool = False, rng_seed: int = 20260812) -> dict:
    """Populate the database. Returns a summary of what was created."""
    init_schema(conn)
    rng = random.Random(rng_seed)          # deterministic, so tests are repeatable

    if reset:
        for table in ("queue_entries", "appointments", "availability_rules",
                      "audit_log", "practitioners", "services", "users"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence")

    if int(scalar(conn, "SELECT COUNT(*) FROM users", default=0)) > 0:
        return {"skipped": True, "reason": "database already contains users"}

    # -- accounts ----------------------------------------------------------
    admin_id = _create_user(conn, "Adjoa Mensimah", "admin@clinicue.health",
                            "+233 30 100 2000", ROLE_ADMIN)
    staff_id = _create_user(conn, "Ama Boakye", "staff@clinicue.health",
                            "+233 30 100 2001", ROLE_STAFF)
    demo_patient_id = _create_user(conn, "Kojo Mensah", "patient@clinicue.health",
                                   "+233 24 000 1234", ROLE_PATIENT)

    patient_ids = [demo_patient_id]
    for name, email, phone in PATIENTS:
        patient_ids.append(_create_user(conn, name, email, phone, ROLE_PATIENT))

    # -- catalogue ---------------------------------------------------------
    service_ids = [
        insert(
            conn,
            """INSERT INTO services (name, description, duration_min, is_active, created_at)
               VALUES (?, ?, ?, 1, ?)""",
            (name, description, duration, utc_stamp()),
        )
        for name, description, duration in SERVICES
    ]

    practitioner_ids = [
        insert(
            conn,
            """INSERT INTO practitioners (full_name, specialty, room, is_active, created_at)
               VALUES (?, ?, ?, 1, ?)""",
            (name, specialty, room, utc_stamp()),
        )
        for name, specialty, room in PRACTITIONERS
    ]

    for practitioner_index, weekdays, start, end in AVAILABILITY:
        for weekday in weekdays:
            insert(
                conn,
                """INSERT INTO availability_rules
                     (practitioner_id, weekday, start_time, end_time, is_active, created_at)
                   VALUES (?, ?, ?, ?, 1, ?)""",
                (practitioner_ids[practitioner_index], weekday, start, end, utc_stamp()),
            )

    # -- appointment history ----------------------------------------------
    # Fourteen days back gives the utilisation report something to show; three
    # days forward gives the patient portal upcoming bookings to display.
    today = today_iso()
    appointments = 0
    queue_rows = 0

    for offset in range(-14, 4):
        day = add_days(today, offset)
        weekday = weekday_of(day)
        if weekday >= 5:                                    # clinic closed at weekends
            continue

        for practitioner_index, weekdays, start, end in AVAILABILITY:
            if weekday not in weekdays:
                continue
            practitioner_id = practitioner_ids[practitioner_index]
            service_id = service_ids[practitioner_index % len(service_ids)]
            duration = SERVICES[practitioner_index % len(SERVICES)][2]

            slot = to_minutes(start)
            limit = to_minutes(end)
            ticket = int(scalar(
                conn,
                "SELECT MAX(ticket_no) FROM queue_entries WHERE practitioner_id = ? AND queue_date = ?",
                (practitioner_id, day), default=0,
            ) or 0)
            used_patients: set[int] = set()

            while slot + duration <= limit:
                # A realistic clinic is busy but not full.
                if rng.random() < 0.42:
                    slot += duration
                    continue
                candidates = [p for p in patient_ids if p not in used_patients]
                if not candidates:
                    break
                patient_id = rng.choice(candidates)
                used_patients.add(patient_id)

                if offset < 0:
                    status = rng.choices(
                        [COMPLETED, NO_SHOW, CANCELLED], weights=[80, 12, 8]
                    )[0]
                elif offset == 0:
                    status = rng.choices([COMPLETED, BOOKED], weights=[45, 55])[0]
                else:
                    status = BOOKED

                start_hhmm = to_hhmm(slot)
                end_hhmm = to_hhmm(slot + duration)
                stamp = utc_stamp()
                try:
                    appointment_id = insert(
                        conn,
                        """INSERT INTO appointments
                             (code, patient_id, practitioner_id, service_id, appt_date,
                              start_time, end_time, status, source, notes, created_by,
                              created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?)""",
                        (new_appointment_code(), patient_id, practitioner_id, service_id,
                         day, start_hhmm, end_hhmm, status, SOURCE_SELF, patient_id,
                         stamp, stamp),
                    )
                except sqlite3.IntegrityError:
                    slot += duration
                    continue

                appointments += 1

                if status in (COMPLETED, NO_SHOW):
                    ticket += 1
                    checked_in = f"{day}T{to_hhmm(max(0, slot - rng.randint(5, 40)))}:00"
                    called = f"{day}T{to_hhmm(slot)}:00"
                    finished = f"{day}T{end_hhmm}:00"
                    insert(
                        conn,
                        """INSERT INTO queue_entries
                             (appointment_id, practitioner_id, queue_date, ticket_no,
                              status, checked_in_at, called_at, completed_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (appointment_id, practitioner_id, day, ticket,
                         Q_DONE if status == COMPLETED else Q_SKIPPED,
                         checked_in,
                         called if status == COMPLETED else None,
                         finished if status == COMPLETED else None),
                    )
                    queue_rows += 1

                slot += duration

    conn.execute(
        """INSERT INTO audit_log (actor_id, action, entity, details, ip_address, created_at)
           VALUES (?, 'SEED_DATABASE', 'system', 'demonstration data loaded', '127.0.0.1', ?)""",
        (admin_id, utc_stamp()),
    )
    conn.commit()

    return {
        "skipped": False,
        "users": len(patient_ids) + 2,
        "services": len(service_ids),
        "practitioners": len(practitioner_ids),
        "appointments": appointments,
        "queue_entries": queue_rows,
        "admin_id": admin_id,
        "staff_id": staff_id,
        "patient_id": demo_patient_id,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the Clinicue database.")
    parser.add_argument("--reset", action="store_true", help="delete existing data first")
    parser.add_argument("--database", default=None, help="override the database path")
    args = parser.parse_args(argv)

    path = args.database or load_config().database_path
    conn = _connect(path)
    try:
        summary = seed(conn, reset=args.reset)
    finally:
        conn.close()

    if summary.get("skipped"):
        print(f"Nothing to do: {summary['reason']}. Use --reset to repopulate.")
        return 0

    print(f"Seeded {path}")
    for key in ("users", "services", "practitioners", "appointments", "queue_entries"):
        print(f"  {key:<15} {summary[key]}")
    print("\nDemonstration accounts:")
    print(f"  admin@clinicue.health    {DEMO_PASSWORD[ROLE_ADMIN]}")
    print(f"  staff@clinicue.health    {DEMO_PASSWORD[ROLE_STAFF]}")
    print(f"  patient@clinicue.health  {DEMO_PASSWORD[ROLE_PATIENT]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
