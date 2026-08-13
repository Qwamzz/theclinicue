"""Liveness probe (NFR-REL-03).

Unauthenticated by design: the hosting platform's health check has no
credentials. It therefore reveals nothing beyond whether the service and its
database are reachable.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from ..db import get_db, scalar
from ..domain import utc_stamp

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    config = current_app.config["TC"]
    database_ok = True
    try:
        scalar(get_db(), "SELECT 1")
    except Exception:  # noqa: BLE001 - a probe must report failure, never raise
        database_ok = False

    payload = {
        "service": "theclinicue",
        "version": current_app.config.get("TC_VERSION", "1.0.0"),
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
        "environment": config.env,
        "time": utc_stamp(),
    }
    return jsonify(payload), (200 if database_ok else 503)
