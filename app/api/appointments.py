"""Appointment booking, listing and cancellation (FR-24 … FR-33)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..db import get_db, query_one
from ..domain import (
    APPOINTMENT_STATUSES,
    ROLE_PATIENT,
    SOURCE_SELF,
    SOURCE_STAFF,
    SOURCE_WALK_IN,
    today_iso,
)
from ..errors import Forbidden, NotFound, ValidationError
from ..security import client_ip, current_user, is_staff, require_auth, require_staff
from ..services import scheduling
from ..validators import Validator

bp = Blueprint("appointments", __name__, url_prefix="/api/appointments")


@bp.post("")
def create():
    """FR-24 … FR-27, and FR-32 when staff book for someone else.

    A patient may only book for themselves. Staff may name any patient — the
    branch below is the whole of that distinction, and it is server-side.
    """
    config = current_app.config["TC"]
    user = current_user()
    if user is None:
        from ..errors import Unauthenticated

        raise Unauthenticated()

    payload = request.get_json(silent=True)
    v = Validator(payload)
    practitioner_id = v.integer("practitioner_id", minimum=1)
    service_id = v.integer("service_id", minimum=1)
    date_iso = v.date("date")
    start_time = v.time("start_time")
    notes = v.string("notes", required=False, max_len=500, default="")
    requested_patient = v.integer("patient_id", required=False, minimum=1)
    v.raise_if_invalid()

    if is_staff(user):
        patient_id = requested_patient or user["id"]
        source = SOURCE_WALK_IN if bool((payload or {}).get("walk_in")) else SOURCE_STAFF
        if patient_id != user["id"]:
            patient = query_one(
                get_db(),
                "SELECT id, is_active FROM users WHERE id = ? AND role = ?",
                (patient_id, ROLE_PATIENT),
            )
            if patient is None:
                raise ValidationError(fields={"patient_id": "No such patient."})
            if not patient["is_active"]:
                raise ValidationError(fields={"patient_id": "That patient account is inactive."})
    else:
        # Silently ignoring a patient_id supplied by a patient would be a
        # privilege-escalation hole; it is simply not read.
        patient_id = user["id"]
        source = SOURCE_SELF

    result = scheduling.book_appointment(
        get_db(),
        patient_id=patient_id,
        practitioner_id=practitioner_id,
        service_id=service_id,
        date_iso=date_iso,
        start_time=start_time,
        created_by=user["id"],
        source=source,
        notes=notes,
        horizon_days=config.booking_horizon_days,
        ip_address=client_ip(),
    )
    return jsonify(result), 201


@bp.get("/mine")
@require_auth
def mine():
    """FR-28."""
    user = current_user()
    assert user is not None
    scope = request.args.get("scope", "upcoming").lower()
    if scope not in {"upcoming", "past", "all"}:
        scope = "upcoming"
    items = scheduling.list_for_patient(get_db(), user["id"], scope=scope)
    return jsonify({"items": items, "total": len(items), "scope": scope})


@bp.get("")
@require_staff
def day_sheet():
    """FR-33. Staff only."""
    config = current_app.config["TC"]
    args = request.args.to_dict()
    v = Validator(args)
    date_iso = v.date("date", required=False, default=today_iso()) or today_iso()
    practitioner_id = v.integer("practitioner_id", required=False, minimum=1)
    limit = v.integer("limit", required=False, minimum=1, maximum=config.max_page_size, default=100)
    offset = v.integer("offset", required=False, minimum=0, default=0)
    status = args.get("status", "").strip().upper()
    if status and status not in APPOINTMENT_STATUSES:
        v.add_error("status", "Unknown status.")
    v.raise_if_invalid()

    result = scheduling.list_for_date(
        get_db(),
        date_iso,
        practitioner_id=practitioner_id,
        status=status or None,
        search=args.get("q", "").strip()[:60],
        limit=limit or 100,
        offset=offset or 0,
    )
    result["date"] = date_iso
    return jsonify(result)


@bp.get("/<int:appointment_id>")
@require_auth
def detail(appointment_id: int):
    """FR-30: ownership enforced in the service layer."""
    user = current_user()
    assert user is not None
    return jsonify(
        scheduling.get_for_actor(
            get_db(), appointment_id, actor_id=user["id"], actor_is_staff=is_staff(user)
        )
    )


@bp.post("/<int:appointment_id>/cancel")
@require_auth
def cancel(appointment_id: int):
    """FR-29, FR-31."""
    user = current_user()
    assert user is not None
    return jsonify(
        scheduling.cancel_appointment(
            get_db(),
            appointment_id,
            actor_id=user["id"],
            actor_is_staff=is_staff(user),
            ip_address=client_ip(),
        )
    )


@bp.get("/lookup")
@require_staff
def lookup():
    """Find a patient by name, phone or email so staff can book on their
    behalf (supports FR-32)."""
    from ..db import query

    needle = request.args.get("q", "").strip()
    if len(needle) < 2:
        raise ValidationError(fields={"q": "Enter at least two characters."})
    rows = query(
        get_db(),
        """SELECT id, full_name, email, phone FROM users
            WHERE role = 'PATIENT' AND is_active = 1
              AND (full_name LIKE ? OR phone LIKE ? OR email LIKE ?)
            ORDER BY full_name LIMIT 20""",
        (f"%{needle}%", f"%{needle}%", f"%{needle}%"),
    )
    return jsonify({"items": [dict(r) for r in rows]})
