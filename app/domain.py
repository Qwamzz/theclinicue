"""Domain vocabulary, invariants and pure helpers.

This module deliberately imports nothing from Flask or sqlite3. It holds the
enumerations, the appointment state machine (the single source of truth for
FR-43) and small pure functions shared across the service layer.
"""

from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta, timezone

# --------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------

ROLE_PATIENT = "PATIENT"
ROLE_STAFF = "STAFF"
ROLE_ADMIN = "ADMIN"
ROLES = (ROLE_PATIENT, ROLE_STAFF, ROLE_ADMIN)

#: Roles permitted to operate the front desk. Admins are a superset of staff.
STAFF_ROLES = (ROLE_STAFF, ROLE_ADMIN)

BOOKED = "BOOKED"
CHECKED_IN = "CHECKED_IN"
IN_PROGRESS = "IN_PROGRESS"
COMPLETED = "COMPLETED"
CANCELLED = "CANCELLED"
NO_SHOW = "NO_SHOW"
APPOINTMENT_STATUSES = (BOOKED, CHECKED_IN, IN_PROGRESS, COMPLETED, CANCELLED, NO_SHOW)

Q_WAITING = "WAITING"
Q_CALLED = "CALLED"
Q_DONE = "DONE"
Q_SKIPPED = "SKIPPED"
QUEUE_STATUSES = (Q_WAITING, Q_CALLED, Q_DONE, Q_SKIPPED)

SOURCE_SELF = "SELF"
SOURCE_STAFF = "STAFF"
SOURCE_WALK_IN = "WALK_IN"
SOURCES = (SOURCE_SELF, SOURCE_STAFF, SOURCE_WALK_IN)

#: Statuses that still occupy a slot in the practitioner's diary.
OCCUPYING_STATUSES = (BOOKED, CHECKED_IN, IN_PROGRESS, COMPLETED, NO_SHOW)

# --------------------------------------------------------------------------
# The appointment state machine — see diagrams/statechart_appointment.svg
# --------------------------------------------------------------------------

TRANSITIONS: dict[str, frozenset[str]] = {
    BOOKED: frozenset({CHECKED_IN, CANCELLED, NO_SHOW}),
    CHECKED_IN: frozenset({IN_PROGRESS, NO_SHOW}),
    IN_PROGRESS: frozenset({COMPLETED}),
    COMPLETED: frozenset(),
    CANCELLED: frozenset(),
    NO_SHOW: frozenset(),
}


def can_transition(current: str, target: str) -> bool:
    """True when moving from `current` to `target` is permitted (FR-43)."""
    return target in TRANSITIONS.get(current, frozenset())


# --------------------------------------------------------------------------
# Time helpers. Times are 'HH:MM' strings; minutes-since-midnight integers are
# used for arithmetic because they make slot generation trivial to reason about.
# --------------------------------------------------------------------------

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_time(value: str) -> bool:
    return bool(_TIME_RE.match(value or ""))


def is_date(value: str) -> bool:
    if not _DATE_RE.match(value or ""):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def to_minutes(hhmm: str) -> int:
    """'09:30' -> 570. Raises ValueError on a malformed time."""
    match = _TIME_RE.match(hhmm or "")
    if not match:
        raise ValueError(f"not a valid HH:MM time: {hhmm!r}")
    return int(match.group(1)) * 60 + int(match.group(2))


def to_hhmm(minutes: int) -> str:
    """570 -> '09:30'. Wraps at 24 h are not expected and are not silently hidden."""
    if not 0 <= minutes <= 24 * 60:
        raise ValueError(f"minutes out of range: {minutes}")
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp(moment: datetime | None = None) -> str:
    """ISO-8601 second-resolution UTC timestamp, used for every stored time."""
    return (moment or utc_now()).replace(microsecond=0, tzinfo=None).isoformat(sep="T")


def parse_stamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def today_iso() -> str:
    return utc_now().date().isoformat()


def weekday_of(date_iso: str) -> int:
    """0 = Monday … 6 = Sunday, matching availability_rules.weekday."""
    return date.fromisoformat(date_iso).weekday()


def add_days(date_iso: str, days: int) -> str:
    return (date.fromisoformat(date_iso) + timedelta(days=days)).isoformat()


# --------------------------------------------------------------------------
# Presentation helpers
# --------------------------------------------------------------------------

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1 — spoken aloud at a desk


def new_appointment_code() -> str:
    """Human-readable booking reference, e.g. 'CQ-7F3A21' (FR-25)."""
    body = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
    return f"CQ-{body}"


def mask_name(full_name: str) -> str:
    """'Yaw Darko' -> 'Y. D****'.

    Used wherever a patient's name would be visible to other patients
    (NFR-LEG-03). Deliberately lossy: it must not be reversible by inspection.
    """
    parts = [p for p in (full_name or "").strip().split() if p]
    if not parts:
        return "Patient"
    initial = f"{parts[0][0].upper()}."
    if len(parts) == 1:
        return f"{initial}****"
    surname = parts[-1]
    return f"{initial} {surname[0].upper()}****"


def ticket_label(practitioner_id: int, ticket_no: int) -> str:
    """Ticket numbers are shown per practitioner: practitioner 2 -> 'B-07'."""
    letter = chr(ord("A") + (max(practitioner_id, 1) - 1) % 26)
    return f"{letter}-{ticket_no:02d}"
