"""Check-in, ticketing and the consultation queue (FR-34 … FR-44).

Every state change funnels through `_transition`, so the state machine in
domain.TRANSITIONS cannot be bypassed by adding a new endpoint (FR-43).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from ..db import insert, query, query_one, scalar, transaction, write_audit
from ..domain import (
    CHECKED_IN,
    COMPLETED,
    IN_PROGRESS,
    NO_SHOW,
    Q_CALLED,
    Q_DONE,
    Q_SKIPPED,
    Q_WAITING,
    can_transition,
    mask_name,
    parse_stamp,
    ticket_label,
    today_iso,
    utc_stamp,
)
from ..errors import AlreadyCheckedIn, Conflict, InvalidTransition, NotFound


def _load_appointment(conn: sqlite3.Connection, appointment_id: int) -> sqlite3.Row:
    row = query_one(conn, "SELECT * FROM appointments WHERE id = ?", (appointment_id,))
    if row is None:
        raise NotFound("We could not find that appointment.")
    return row


def _transition(conn: sqlite3.Connection, appointment_id: int, current: str, target: str) -> None:
    """The single gate for every appointment status change (FR-43)."""
    if not can_transition(current, target):
        raise InvalidTransition(
            f"Cannot move an appointment from {current.replace('_', ' ').lower()} "
            f"to {target.replace('_', ' ').lower()}."
        )
    conn.execute(
        "UPDATE appointments SET status = ?, updated_at = ? WHERE id = ?",
        (target, utc_stamp(), appointment_id),
    )


def _next_ticket(conn: sqlite3.Connection, practitioner_id: int, date_iso: str) -> int:
    """Next sequential ticket for this practitioner and day (FR-35).

    Safe because every caller runs inside a BEGIN IMMEDIATE transaction, and
    the unique index on (practitioner_id, queue_date, ticket_no) is the
    backstop if that ever stops being true.
    """
    highest = scalar(
        conn,
        "SELECT MAX(ticket_no) FROM queue_entries WHERE practitioner_id = ? AND queue_date = ?",
        (practitioner_id, date_iso),
        default=0,
    )
    return int(highest) + 1


def check_in(
    conn: sqlite3.Connection,
    appointment_id: int,
    *,
    actor_id: int,
    ip_address: str = "",
) -> dict[str, Any]:
    """Admit a booked patient to today's queue (FR-34 … FR-37)."""
    with transaction(conn, immediate=True):
        appointment = _load_appointment(conn, appointment_id)

        if appointment["appt_date"] != today_iso():                     # FR-37
            raise Conflict(
                "Only appointments scheduled for today can be checked in. "
                f"This one is for {appointment['appt_date']}."
            )

        existing = query_one(
            conn, "SELECT id FROM queue_entries WHERE appointment_id = ?", (appointment_id,)
        )
        if existing is not None:                                        # FR-36
            raise AlreadyCheckedIn()

        _transition(conn, appointment_id, appointment["status"], CHECKED_IN)

        ticket_no = _next_ticket(conn, appointment["practitioner_id"], appointment["appt_date"])
        stamp = utc_stamp()
        try:
            entry_id = insert(
                conn,
                """INSERT INTO queue_entries
                     (appointment_id, practitioner_id, queue_date, ticket_no,
                      status, checked_in_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (appointment_id, appointment["practitioner_id"], appointment["appt_date"],
                 ticket_no, Q_WAITING, stamp),
            )
        except sqlite3.IntegrityError as exc:
            # Two staff members clicked at once; the index caught the loser.
            raise AlreadyCheckedIn(
                "That patient was checked in a moment ago. Refresh the day sheet."
            ) from exc

        write_audit(
            conn,
            actor_id=actor_id,
            action="CHECK_IN",
            entity="appointment",
            entity_id=appointment_id,
            details=f"ticket={ticket_no}",
            ip_address=ip_address,
        )

    return {
        "queue_entry_id": entry_id,
        "appointment_id": appointment_id,
        "practitioner_id": appointment["practitioner_id"],
        "ticket_no": ticket_no,
        "ticket": ticket_label(appointment["practitioner_id"], ticket_no),
        "status": Q_WAITING,
        "checked_in_at": stamp,
    }


def call_next(
    conn: sqlite3.Connection,
    practitioner_id: int,
    *,
    actor_id: int,
    date_iso: str | None = None,
    ip_address: str = "",
) -> dict[str, Any] | None:
    """Call the longest-waiting patient (FR-38, FR-39).

    Returns None when the queue is empty — an empty queue is a normal outcome,
    not an error, so the caller gets 200 with a null payload rather than a 404.
    """
    queue_date = date_iso or today_iso()

    with transaction(conn, immediate=True):
        entry = query_one(
            conn,
            """SELECT q.*, a.status AS appt_status, u.full_name
                 FROM queue_entries q
                 JOIN appointments a ON a.id = q.appointment_id
                 JOIN users u        ON u.id = a.patient_id
                WHERE q.practitioner_id = ? AND q.queue_date = ? AND q.status = ?
                ORDER BY q.ticket_no ASC
                LIMIT 1""",
            (practitioner_id, queue_date, Q_WAITING),
        )
        if entry is None:
            return None

        _transition(conn, entry["appointment_id"], entry["appt_status"], IN_PROGRESS)
        stamp = utc_stamp()
        conn.execute(
            "UPDATE queue_entries SET status = ?, called_at = ? WHERE id = ?",
            (Q_CALLED, stamp, entry["id"]),
        )
        write_audit(
            conn,
            actor_id=actor_id,
            action="CALL_NEXT",
            entity="appointment",
            entity_id=entry["appointment_id"],
            details=f"ticket={entry['ticket_no']}",
            ip_address=ip_address,
        )

    return {
        "queue_entry_id": entry["id"],
        "appointment_id": entry["appointment_id"],
        "ticket_no": entry["ticket_no"],
        "ticket": ticket_label(practitioner_id, entry["ticket_no"]),
        "patient_name": entry["full_name"],
        "called_at": stamp,
    }


def complete(
    conn: sqlite3.Connection,
    appointment_id: int,
    *,
    actor_id: int,
    ip_address: str = "",
) -> dict[str, Any]:
    """Close a consultation (FR-40)."""
    with transaction(conn, immediate=True):
        appointment = _load_appointment(conn, appointment_id)
        _transition(conn, appointment_id, appointment["status"], COMPLETED)
        stamp = utc_stamp()
        conn.execute(
            "UPDATE queue_entries SET status = ?, completed_at = ? WHERE appointment_id = ?",
            (Q_DONE, stamp, appointment_id),
        )
        write_audit(
            conn,
            actor_id=actor_id,
            action="COMPLETE_CONSULTATION",
            entity="appointment",
            entity_id=appointment_id,
            ip_address=ip_address,
        )
    return {"appointment_id": appointment_id, "status": COMPLETED, "completed_at": stamp}


def mark_no_show(
    conn: sqlite3.Connection,
    appointment_id: int,
    *,
    actor_id: int,
    ip_address: str = "",
) -> dict[str, Any]:
    """Record that a patient never attended (FR-41)."""
    with transaction(conn, immediate=True):
        appointment = _load_appointment(conn, appointment_id)
        _transition(conn, appointment_id, appointment["status"], NO_SHOW)
        conn.execute(
            "UPDATE queue_entries SET status = ? WHERE appointment_id = ?",
            (Q_SKIPPED, appointment_id),
        )
        write_audit(
            conn,
            actor_id=actor_id,
            action="MARK_NO_SHOW",
            entity="appointment",
            entity_id=appointment_id,
            details=f"from={appointment['status']}",
            ip_address=ip_address,
        )
    return {"appointment_id": appointment_id, "status": NO_SHOW}


def live_queue(
    conn: sqlite3.Connection, practitioner_id: int, *, date_iso: str | None = None
) -> dict[str, Any]:
    """The shared queue view (FR-42).

    Patient names are masked because this view is visible to other patients
    (NFR-LEG-03).
    """
    queue_date = date_iso or today_iso()
    rows = query(
        conn,
        """SELECT q.ticket_no, q.status, q.checked_in_at, q.called_at, u.full_name
             FROM queue_entries q
             JOIN appointments a ON a.id = q.appointment_id
             JOIN users u        ON u.id = a.patient_id
            WHERE q.practitioner_id = ? AND q.queue_date = ?
              AND q.status IN (?, ?)
            ORDER BY CASE q.status WHEN 'CALLED' THEN 0 ELSE 1 END, q.ticket_no ASC""",
        (practitioner_id, queue_date, Q_WAITING, Q_CALLED),
    )

    now_serving = None
    waiting: list[dict[str, Any]] = []
    position = 0
    for row in rows:
        item = {
            "ticket_no": row["ticket_no"],
            "ticket": ticket_label(practitioner_id, row["ticket_no"]),
            "name": mask_name(row["full_name"]),
            "status": row["status"],
            "waiting_minutes": _minutes_since(row["checked_in_at"]),
        }
        if row["status"] == Q_CALLED and now_serving is None:
            now_serving = item
        else:
            position += 1
            item["position"] = position
            waiting.append(item)

    return {
        "practitioner_id": practitioner_id,
        "date": queue_date,
        "now_serving": now_serving,
        "waiting": waiting,
        "waiting_count": len(waiting),
    }


def position_for_patient(
    conn: sqlite3.Connection, patient_id: int, *, date_iso: str | None = None
) -> dict[str, Any] | None:
    """The patient's own ticket and how many are ahead (FR-44)."""
    queue_date = date_iso or today_iso()
    row = query_one(
        conn,
        """SELECT q.ticket_no, q.status, q.practitioner_id, q.checked_in_at,
                  p.full_name AS practitioner_name, p.room
             FROM queue_entries q
             JOIN appointments a ON a.id = q.appointment_id
             JOIN practitioners p ON p.id = q.practitioner_id
            WHERE a.patient_id = ? AND q.queue_date = ? AND q.status IN (?, ?)
            ORDER BY q.ticket_no ASC LIMIT 1""",
        (patient_id, queue_date, Q_WAITING, Q_CALLED),
    )
    if row is None:
        return None

    ahead = scalar(
        conn,
        """SELECT COUNT(*) FROM queue_entries
            WHERE practitioner_id = ? AND queue_date = ? AND status = ?
              AND ticket_no < ?""",
        (row["practitioner_id"], queue_date, Q_WAITING, row["ticket_no"]),
        default=0,
    )
    serving = query_one(
        conn,
        """SELECT ticket_no FROM queue_entries
            WHERE practitioner_id = ? AND queue_date = ? AND status = ?
            ORDER BY called_at DESC LIMIT 1""",
        (row["practitioner_id"], queue_date, Q_CALLED),
    )

    return {
        "ticket_no": row["ticket_no"],
        "ticket": ticket_label(row["practitioner_id"], row["ticket_no"]),
        "status": row["status"],
        "practitioner_name": row["practitioner_name"],
        "room": row["room"],
        "ahead": int(ahead),
        "now_serving": ticket_label(row["practitioner_id"], serving["ticket_no"]) if serving else None,
        "waiting_minutes": _minutes_since(row["checked_in_at"]),
    }


def _minutes_since(stamp: str | None) -> int | None:
    from ..domain import utc_now

    moment = parse_stamp(stamp)
    if moment is None:
        return None
    delta = utc_now().replace(tzinfo=None) - moment
    return max(0, int(delta.total_seconds() // 60))
