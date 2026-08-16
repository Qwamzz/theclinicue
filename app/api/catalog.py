"""Read-only catalogue and slot discovery (FR-19 to FR-23)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..db import get_db, query
from ..security import require_auth
from ..services import scheduling
from ..validators import Validator

bp = Blueprint("catalog", __name__, url_prefix="/api")


@bp.get("/services")
@require_auth
def list_services():
    rows = query(
        get_db(),
        """SELECT id, name, description, duration_min FROM services
            WHERE is_active = 1 ORDER BY name""",
    )
    return jsonify({"items": [dict(r) for r in rows]})


@bp.get("/practitioners")
@require_auth
def list_practitioners():
    rows = query(
        get_db(),
        """SELECT id, full_name, specialty, room FROM practitioners
            WHERE is_active = 1 ORDER BY full_name""",
    )
    return jsonify({"items": [dict(r) for r in rows]})


@bp.get("/availability")
@require_auth
def list_availability():
    """Which weekdays a practitioner works - lets the client grey out
    impossible dates before the user picks one."""
    v = Validator(request.args.to_dict())
    practitioner_id = v.integer("practitioner_id", minimum=1)
    v.raise_if_invalid()

    rows = query(
        get_db(),
        """SELECT weekday, start_time, end_time FROM availability_rules
            WHERE practitioner_id = ? AND is_active = 1
            ORDER BY weekday, start_time""",
        (practitioner_id,),
    )
    return jsonify({
        "practitioner_id": practitioner_id,
        "items": [dict(r) for r in rows],
        "weekdays": sorted({r["weekday"] for r in rows}),
    })


@bp.get("/slots")
@require_auth
def list_slots():
    """FR-20 to FR-23."""
    config = current_app.config["TC"]
    v = Validator(request.args.to_dict())
    practitioner_id = v.integer("practitioner_id", minimum=1)
    service_id = v.integer("service_id", minimum=1)
    date_iso = v.date("date")
    v.raise_if_invalid()

    result = scheduling.list_slots(
        get_db(),
        practitioner_id,
        service_id,
        date_iso,
        horizon_days=config.booking_horizon_days,
    )
    return jsonify(result)
