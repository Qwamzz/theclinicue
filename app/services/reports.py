"""Operational reporting (FR-50 to FR-52).

Read-only by construction: nothing in this module writes. These are the
figures the clinic administrator was identified as needing in stakeholder
analysis (S4) - attendance, no-show rate, utilisation and waiting time.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from ..db import query, scalar
from ..domain import (
    APPOINTMENT_STATUSES,
    CANCELLED,
    COMPLETED,
    NO_SHOW,
    Q_DONE,
    parse_stamp,
    to_minutes,
    today_iso,
)


def daily_summary(conn: sqlite3.Connection, date_iso: str | None = None) -> dict[str, Any]:
    """Counts by status for one day, plus the no-show rate (FR-50)."""
    day = date_iso or today_iso()

    rows = query(
        conn,
        "SELECT status, COUNT(*) AS n FROM appointments WHERE appt_date = ? GROUP BY status",
        (day,),
    )
    counts = {status: 0 for status in APPOINTMENT_STATUSES}
    for row in rows:
        counts[row["status"]] = int(row["n"])

    total = sum(counts.values())
    # The no-show rate is measured against appointments the patient was
    # actually expected to attend, so cancellations are excluded from the
    # denominator. Counting them would flatter the figure.
    expected = total - counts[CANCELLED]
    no_show_rate = round(counts[NO_SHOW] / expected * 100, 1) if expected else 0.0

    attended = counts[COMPLETED]
    attendance_rate = round(attended / expected * 100, 1) if expected else 0.0

    return {
        "date": day,
        "total": total,
        "by_status": counts,
        "expected": expected,
        "attended": attended,
        "no_show_rate": no_show_rate,
        "attendance_rate": attendance_rate,
        "mean_wait_minutes": mean_wait_minutes(conn, day),
    }


def mean_wait_minutes(conn: sqlite3.Connection, date_iso: str | None = None) -> float | None:
    """Mean minutes between check-in and being called (FR-52).

    Returns None rather than 0.0 when nobody has been called yet - "no data"
    and "no wait" are different facts and the UI must be able to tell them
    apart.
    """
    day = date_iso or today_iso()
    rows = query(
        conn,
        """SELECT checked_in_at, called_at FROM queue_entries
            WHERE queue_date = ? AND called_at IS NOT NULL""",
        (day,),
    )
    waits: list[float] = []
    for row in rows:
        start = parse_stamp(row["checked_in_at"])
        called = parse_stamp(row["called_at"])
        if start and called and called >= start:
            waits.append((called - start).total_seconds() / 60.0)
    if not waits:
        return None
    return round(sum(waits) / len(waits), 1)


def utilisation(
    conn: sqlite3.Connection, from_date: str, to_date: str
) -> dict[str, Any]:
    """Appointments handled against slots offered, per practitioner (FR-51).

    Slots offered is computed from the *current* availability rules, so a rule
    edited mid-period is applied retrospectively across the whole range. That
    is a known inaccuracy - correcting it needs dated availability snapshots,
    which is recorded as TD-11.
    """
    practitioners = query(
        conn, "SELECT id, full_name, specialty FROM practitioners WHERE is_active = 1 ORDER BY id"
    )

    weekday_counts = _weekday_counts(from_date, to_date)
    results = []

    for practitioner in practitioners:
        pid = practitioner["id"]

        rules = query(
            conn,
            """SELECT weekday, start_time, end_time FROM availability_rules
                WHERE practitioner_id = ? AND is_active = 1""",
            (pid,),
        )
        # Slot width varies by service; the mean active service duration is the
        # fairest single divisor available without joining every appointment.
        mean_duration = scalar(
            conn, "SELECT AVG(duration_min) FROM services WHERE is_active = 1", default=30
        ) or 30
        minutes_per_week_day: dict[int, int] = {}
        for rule in rules:
            span = to_minutes(rule["end_time"]) - to_minutes(rule["start_time"])
            minutes_per_week_day[rule["weekday"]] = (
                minutes_per_week_day.get(rule["weekday"], 0) + span
            )
        offered = sum(
            (minutes // int(mean_duration)) * weekday_counts.get(weekday, 0)
            for weekday, minutes in minutes_per_week_day.items()
        )

        booked = int(scalar(
            conn,
            """SELECT COUNT(*) FROM appointments
                WHERE practitioner_id = ? AND appt_date BETWEEN ? AND ? AND status <> ?""",
            (pid, from_date, to_date, CANCELLED),
            default=0,
        ))
        completed = int(scalar(
            conn,
            """SELECT COUNT(*) FROM appointments
                WHERE practitioner_id = ? AND appt_date BETWEEN ? AND ? AND status = ?""",
            (pid, from_date, to_date, COMPLETED),
            default=0,
        ))
        no_shows = int(scalar(
            conn,
            """SELECT COUNT(*) FROM appointments
                WHERE practitioner_id = ? AND appt_date BETWEEN ? AND ? AND status = ?""",
            (pid, from_date, to_date, NO_SHOW),
            default=0,
        ))

        results.append({
            "practitioner_id": pid,
            "practitioner_name": practitioner["full_name"],
            "specialty": practitioner["specialty"],
            "slots_offered": offered,
            "appointments": booked,
            "completed": completed,
            "no_shows": no_shows,
            "utilisation_pct": round(booked / offered * 100, 1) if offered else None,
            "no_show_pct": round(no_shows / booked * 100, 1) if booked else 0.0,
        })

    return {"from": from_date, "to": to_date, "items": results}


def _weekday_counts(from_date: str, to_date: str) -> dict[int, int]:
    """How many times each weekday occurs in an inclusive date range."""
    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)
    if end < start:
        return {}
    counts: dict[int, int] = {}
    span = (end - start).days
    # Bounded so a mistyped range cannot turn into a long loop.
    for offset in range(min(span, 365) + 1):
        weekday = (start.toordinal() + offset - 1) % 7
        counts[weekday] = counts.get(weekday, 0) + 1
    return counts


def throughput(conn: sqlite3.Connection, date_iso: str | None = None) -> dict[str, Any]:
    """Consultations completed per practitioner today - the day-shift view."""
    day = date_iso or today_iso()
    rows = query(
        conn,
        """SELECT p.full_name, COUNT(q.id) AS done
             FROM practitioners p
        LEFT JOIN queue_entries q
               ON q.practitioner_id = p.id AND q.queue_date = ? AND q.status = ?
            WHERE p.is_active = 1
         GROUP BY p.id
         ORDER BY done DESC""",
        (day, Q_DONE),
    )
    return {
        "date": day,
        "items": [{"practitioner_name": r["full_name"], "completed": int(r["done"])} for r in rows],
    }
