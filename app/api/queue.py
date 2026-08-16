"""Check-in and consultation queue endpoints (FR-34 to FR-44)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..db import get_db
from ..domain import today_iso
from ..security import client_ip, current_user, require_auth, require_staff
from ..services import queue as queue_service
from ..validators import Validator

bp = Blueprint("queue", __name__, url_prefix="/api/queue")


def _appointment_id_from_body() -> int:
    v = Validator(request.get_json(silent=True))
    appointment_id = v.integer("appointment_id", minimum=1)
    v.raise_if_invalid()
    assert appointment_id is not None
    return appointment_id


@bp.post("/check-in")
@require_staff
def check_in():
    """FR-34 to FR-37."""
    user = current_user()
    assert user is not None
    result = queue_service.check_in(
        get_db(), _appointment_id_from_body(), actor_id=user["id"], ip_address=client_ip()
    )
    return jsonify(result), 201


@bp.post("/call-next")
@require_staff
def call_next():
    """FR-38, FR-39. An empty queue is a 200 with a null entry, not an error."""
    user = current_user()
    assert user is not None
    v = Validator(request.get_json(silent=True))
    practitioner_id = v.integer("practitioner_id", minimum=1)
    v.raise_if_invalid()

    result = queue_service.call_next(
        get_db(), practitioner_id, actor_id=user["id"], ip_address=client_ip()
    )
    if result is None:
        return jsonify({"called": None, "message": "Nobody is waiting for this practitioner."})
    return jsonify({"called": result})


@bp.post("/complete")
@require_staff
def complete():
    """FR-40."""
    user = current_user()
    assert user is not None
    return jsonify(
        queue_service.complete(
            get_db(), _appointment_id_from_body(), actor_id=user["id"], ip_address=client_ip()
        )
    )


@bp.post("/no-show")
@require_staff
def no_show():
    """FR-41."""
    user = current_user()
    assert user is not None
    return jsonify(
        queue_service.mark_no_show(
            get_db(), _appointment_id_from_body(), actor_id=user["id"], ip_address=client_ip()
        )
    )


@bp.get("")
@require_auth
def live():
    """FR-42. Visible to any authenticated user; patient names are masked."""
    v = Validator(request.args.to_dict())
    practitioner_id = v.integer("practitioner_id", minimum=1)
    date_iso = v.date("date", required=False, default=today_iso()) or today_iso()
    v.raise_if_invalid()

    return jsonify(queue_service.live_queue(get_db(), practitioner_id, date_iso=date_iso))


@bp.get("/my-position")
@require_auth
def my_position():
    """FR-44."""
    user = current_user()
    assert user is not None
    position = queue_service.position_for_patient(get_db(), user["id"])
    return jsonify({"position": position})
