"""Slot generation, booking and cancellation.

This is the algorithmic core of TheClinicue (SRS §8.4 identified it as the
highest-risk component, so it was built and unit-tested before any HTTP or UI
code existed).

`generate_slots` is a pure function of its arguments - no database, no clock,
no request - which is what makes the awkward cases exhaustively testable.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Sequence

from ..db import insert, query, query_one, transaction, write_audit
from ..domain import (
    BOOKED,
    CANCELLED,
    OCCUPYING_STATUSES,
    SOURCE_SELF,
    SOURCES,
    add_days,
    can_transition,
    new_appointment_code,
    to_hhmm,
    to_minutes,
    today_iso,
    utc_now,
    utc_stamp,
    weekday_of,
)
from ..errors import (
    Conflict,
    DuplicateBooking,
    InvalidTransition,
    NotFound,
    SlotUnavailable,
    ValidationError,
)

Interval = tuple[int, int]


# --------------------------------------------------------------------------
# The pure algorithm (FR-20 to FR-22)
# --------------------------------------------------------------------------

def overlaps(a: Interval, b: Interval) -> bool:
    """Half-open interval overlap: [09:00, 09:30) and [09:30, 10:00) do not overlap."""
    return a[0] < b[1] and b[0] < a[1]


def generate_slots(
    windows: Iterable[Interval],
    booked: Iterable[Interval],
    duration_min: int,
    *,
    min_start: int | None = None,
) -> list[int]:
    """Return the free slot start times, in minutes since midnight.

    windows    availability windows for the day, as (start, end) minute pairs
    booked     intervals already taken, same units
    duration   slot width, from the chosen service
    min_start  when given, drop slots starting before it (used to hide times
               that have already elapsed today - FR-22)

    A slot is emitted only when it fits *entirely* inside its window, so a
    09:00-09:50 window with a 30-minute service yields 09:00 and nothing else:
    a consultation that would overrun the practitioner's availability is not
    offered.
    """
    if duration_min <= 0:
        raise ValueError("duration_min must be positive")

    taken = list(booked)
    found: set[int] = set()

    for window_start, window_end in windows:
        if window_end <= window_start:
            continue                                    # defensive: FR-18 also guards this
        start = window_start
        while start + duration_min <= window_end:
            slot = (start, start + duration_min)
            if (min_start is None or start >= min_start) and not any(
                overlaps(slot, t) for t in taken
            ):
                found.add(start)
            start += duration_min

    return sorted(found)


# --------------------------------------------------------------------------
# Database-backed operations
# --------------------------------------------------------------------------

APPOINTMENT_SELECT = """
    SELECT a.id, a.code, a.patient_id, a.practitioner_id, a.service_id,
           a.appt_date, a.start_time, a.end_time, a.status, a.source,
           a.notes, a.created_at,
           u.full_name  AS patient_name,
           u.phone      AS patient_phone,
           p.full_name  AS practitioner_name,
           p.room       AS practitioner_room,
           s.name       AS service_name,
           s.duration_min,
           q.ticket_no, q.status AS queue_status
      FROM appointments a
      JOIN users         u ON u.id = a.patient_id
      JOIN practitioners p ON p.id = a.practitioner_id
      JOIN services      s ON s.id = a.service_id
 LEFT JOIN queue_entries q ON q.appointment_id = a.id
"""


def appointment_view(row: sqlite3.Row) -> dict[str, Any]:
    """Serialise an appointment for the API. Never exposes internal user ids
    beyond the patient id the caller is already entitled to see."""
    return {
        "id": row["id"],
        "code": row["code"],
        "patient_id": row["patient_id"],
        "patient_name": row["patient_name"],
        "patient_phone": row["patient_phone"],
        "practitioner_id": row["practitioner_id"],
        "practitioner_name": row["practitioner_name"],
        "room": row["practitioner_room"],
        "service_id": row["service_id"],
        "service_name": row["service_name"],
        "duration_min": row["duration_min"],
        "date": row["appt_date"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "status": row["status"],
        "source": row["source"],
        "notes": row["notes"],
        "ticket_no": row["ticket_no"],
        "queue_status": row["queue_status"],
        "created_at": row["created_at"],
    }


def _require_active_practitioner(conn: sqlite3.Connection, practitioner_id: int) -> sqlite3.Row:
    row = query_one(
        conn, "SELECT * FROM practitioners WHERE id = ? AND is_active = 1", (practitioner_id,)
    )
    if row is None:
        raise NotFound("That practitioner is not available.")
    return row


def _require_active_service(conn: sqlite3.Connection, service_id: int) -> sqlite3.Row:
    row = query_one(
        conn, "SELECT * FROM services WHERE id = ? AND is_active = 1", (service_id,)
    )
    if row is None:
        raise NotFound("That service is not available.")
    return row


def _booked_intervals(
    conn: sqlite3.Connection, practitioner_id: int, date_iso: str
) -> list[Interval]:
    placeholders = ",".join("?" for _ in OCCUPYING_STATUSES)
    rows = query(
        conn,
        f"""SELECT start_time, end_time FROM appointments
             WHERE practitioner_id = ? AND appt_date = ?
               AND status IN ({placeholders})""",
        (practitioner_id, date_iso, *OCCUPYING_STATUSES),
    )
    return [(to_minutes(r["start_time"]), to_minutes(r["end_time"])) for r in rows]


def _availability_windows(
    conn: sqlite3.Connection, practitioner_id: int, date_iso: str
) -> list[Interval]:
    rows = query(
        conn,
        """SELECT start_time, end_time FROM availability_rules
            WHERE practitioner_id = ? AND weekday = ? AND is_active = 1
            ORDER BY start_time""",
        (practitioner_id, weekday_of(date_iso)),
    )
    return [(to_minutes(r["start_time"]), to_minutes(r["end_time"])) for r in rows]


def assert_bookable_date(date_iso: str, horizon_days: int) -> None:
    """FR-22 and FR-23: not in the past, not beyond the planning horizon."""
    today = today_iso()
    if date_iso < today:
        raise ValidationError(fields={"date": "This date has already passed."})
    if date_iso > add_days(today, horizon_days):
        raise ValidationError(
            fields={"date": f"Bookings open only {horizon_days} days ahead."}
        )


def list_slots(
    conn: sqlite3.Connection,
    practitioner_id: int,
    service_id: int,
    date_iso: str,
    *,
    horizon_days: int = 60,
) -> dict[str, Any]:
    """Free slots for one practitioner, service and date (FR-20 to FR-23)."""
    assert_bookable_date(date_iso, horizon_days)
    practitioner = _require_active_practitioner(conn, practitioner_id)
    service = _require_active_service(conn, service_id)

    duration = int(service["duration_min"])
    windows = _availability_windows(conn, practitioner_id, date_iso)
    booked = _booked_intervals(conn, practitioner_id, date_iso)

    # Only hide elapsed times when the date in question is actually today.
    min_start = None
    if date_iso == today_iso():
        now = utc_now()
        min_start = now.hour * 60 + now.minute

    starts = generate_slots(windows, booked, duration, min_start=min_start)
    return {
        "date": date_iso,
        "practitioner_id": practitioner_id,
        "practitioner_name": practitioner["full_name"],
        "service_id": service_id,
        "service_name": service["name"],
        "duration_min": duration,
        "slots": [
            {"start_time": to_hhmm(s), "end_time": to_hhmm(s + duration)} for s in starts
        ],
    }


def book_appointment(
    conn: sqlite3.Connection,
    *,
    patient_id: int,
    practitioner_id: int,
    service_id: int,
    date_iso: str,
    start_time: str,
    created_by: int,
    source: str = SOURCE_SELF,
    notes: str = "",
    horizon_days: int = 60,
    ip_address: str = "",
) -> dict[str, Any]:
    """Create an appointment, re-verifying the slot inside the write lock.

    The re-verification (FR-26) closes the window between the client seeing a
    slot and submitting it. The partial unique index is the actual guarantee;
    the check exists so the common case gets a helpful message rather than a
    constraint violation.
    """
    if source not in SOURCES:
        raise ValidationError(fields={"source": "Unknown booking source."})

    assert_bookable_date(date_iso, horizon_days)
    service = _require_active_service(conn, service_id)
    _require_active_practitioner(conn, practitioner_id)

    duration = int(service["duration_min"])
    try:
        start_minutes = to_minutes(start_time)
    except ValueError:
        raise ValidationError(fields={"start_time": "Use the 24-hour format HH:MM."}) from None
    end_time = to_hhmm(start_minutes + duration)

    with transaction(conn, immediate=True):
        # Re-check availability now that we hold the write lock.
        windows = _availability_windows(conn, practitioner_id, date_iso)
        booked = _booked_intervals(conn, practitioner_id, date_iso)
        min_start = None
        if date_iso == today_iso():
            now = utc_now()
            min_start = now.hour * 60 + now.minute
        if start_minutes not in generate_slots(windows, booked, duration, min_start=min_start):
            raise SlotUnavailable()

        # FR-27: one live appointment per patient, practitioner and day.
        clash = query_one(
            conn,
            """SELECT id FROM appointments
                WHERE patient_id = ? AND practitioner_id = ? AND appt_date = ?
                  AND status <> ?""",
            (patient_id, practitioner_id, date_iso, CANCELLED),
        )
        if clash is not None:
            raise DuplicateBooking()

        stamp = utc_stamp()
        appointment_id = 0
        for attempt in range(5):            # code collisions are astronomically unlikely
            code = new_appointment_code()
            try:
                appointment_id = insert(
                    conn,
                    """INSERT INTO appointments
                         (code, patient_id, practitioner_id, service_id, appt_date,
                          start_time, end_time, status, source, notes, created_by,
                          created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (code, patient_id, practitioner_id, service_id, date_iso,
                     start_time, end_time, BOOKED, source, notes, created_by,
                     stamp, stamp),
                )
                break
            except sqlite3.IntegrityError as exc:
                message = str(exc)
                if "appointments.code" in message or "ux_appt_code" in message:
                    if attempt == 4:
                        raise Conflict("Could not allocate a booking reference.") from exc
                    continue
                if "ux_appt_slot" in message:
                    raise SlotUnavailable() from exc
                if "ux_patient_day" in message:
                    raise DuplicateBooking() from exc
                raise

        write_audit(
            conn,
            actor_id=created_by,
            action="BOOK_APPOINTMENT",
            entity="appointment",
            entity_id=appointment_id,
            details=f"{date_iso} {start_time} practitioner={practitioner_id} source={source}",
            ip_address=ip_address,
        )

    row = query_one(conn, APPOINTMENT_SELECT + " WHERE a.id = ?", (appointment_id,))
    assert row is not None
    return appointment_view(row)


def get_for_actor(
    conn: sqlite3.Connection, appointment_id: int, *, actor_id: int, actor_is_staff: bool
) -> dict[str, Any]:
    """Fetch one appointment, enforcing ownership (FR-30).

    A patient asking for someone else's appointment gets 404, not 403, so the
    endpoint cannot be used to discover which ids exist.
    """
    row = query_one(conn, APPOINTMENT_SELECT + " WHERE a.id = ?", (appointment_id,))
    if row is None:
        raise NotFound("We could not find that appointment.")
    if not actor_is_staff and row["patient_id"] != actor_id:
        raise NotFound("We could not find that appointment.")
    return appointment_view(row)


def list_for_patient(
    conn: sqlite3.Connection, patient_id: int, *, scope: str = "upcoming"
) -> list[dict[str, Any]]:
    """FR-28. `scope` is one of 'upcoming', 'past' or 'all'."""
    today = today_iso()
    if scope == "upcoming":
        clause = "AND a.appt_date >= ? AND a.status IN ('BOOKED','CHECKED_IN','IN_PROGRESS')"
        params: Sequence[Any] = (patient_id, today)
        order = "ORDER BY a.appt_date ASC, a.start_time ASC"
    elif scope == "past":
        clause = "AND (a.appt_date < ? OR a.status IN ('COMPLETED','CANCELLED','NO_SHOW'))"
        params = (patient_id, today)
        order = "ORDER BY a.appt_date DESC, a.start_time DESC"
    else:
        clause = ""
        params = (patient_id,)
        order = "ORDER BY a.appt_date DESC, a.start_time DESC"

    rows = query(
        conn,
        f"{APPOINTMENT_SELECT} WHERE a.patient_id = ? {clause} {order} LIMIT 200",
        params,
    )
    return [appointment_view(r) for r in rows]


def list_for_date(
    conn: sqlite3.Connection,
    date_iso: str,
    *,
    practitioner_id: int | None = None,
    status: str | None = None,
    search: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """The front desk day sheet (FR-33)."""
    clauses = ["a.appt_date = ?"]
    params: list[Any] = [date_iso]

    if practitioner_id:
        clauses.append("a.practitioner_id = ?")
        params.append(practitioner_id)
    if status:
        clauses.append("a.status = ?")
        params.append(status)
    if search:
        clauses.append("(u.full_name LIKE ? OR a.code LIKE ? OR u.phone LIKE ?)")
        needle = f"%{search}%"
        params.extend([needle, needle, needle])

    where = " WHERE " + " AND ".join(clauses)
    total = query_one(
        conn,
        f"""SELECT COUNT(*) AS n FROM appointments a
              JOIN users u ON u.id = a.patient_id {where}""",
        params,
    )
    rows = query(
        conn,
        f"{APPOINTMENT_SELECT}{where} ORDER BY a.start_time ASC, a.id ASC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    )
    return {
        "items": [appointment_view(r) for r in rows],
        "total": int(total["n"]) if total else 0,
    }


def cancel_appointment(
    conn: sqlite3.Connection,
    appointment_id: int,
    *,
    actor_id: int,
    actor_is_staff: bool,
    ip_address: str = "",
) -> dict[str, Any]:
    """FR-29 and FR-31. Releases the slot by moving the row to CANCELLED,
    which the partial unique index then ignores."""
    with transaction(conn, immediate=True):
        row = query_one(
            conn, "SELECT id, patient_id, status FROM appointments WHERE id = ?", (appointment_id,)
        )
        if row is None:
            raise NotFound("We could not find that appointment.")
        if not actor_is_staff and row["patient_id"] != actor_id:
            raise NotFound("We could not find that appointment.")
        if not can_transition(row["status"], CANCELLED):
            raise InvalidTransition(
                f"An appointment that is {row['status'].replace('_', ' ').lower()} "
                "can no longer be cancelled."
            )

        conn.execute(
            "UPDATE appointments SET status = ?, updated_at = ? WHERE id = ?",
            (CANCELLED, utc_stamp(), appointment_id),
        )
        conn.execute(
            "UPDATE queue_entries SET status = 'SKIPPED' WHERE appointment_id = ?",
            (appointment_id,),
        )
        write_audit(
            conn,
            actor_id=actor_id,
            action="CANCEL_APPOINTMENT",
            entity="appointment",
            entity_id=appointment_id,
            details=f"from={row['status']}",
            ip_address=ip_address,
        )

    result = query_one(conn, APPOINTMENT_SELECT + " WHERE a.id = ?", (appointment_id,))
    assert result is not None
    return appointment_view(result)
