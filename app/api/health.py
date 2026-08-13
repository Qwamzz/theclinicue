"""Liveness probe (NFR-REL-03).

Unauthenticated by design: the hosting platform's health check has no
credentials. It therefore reveals nothing beyond whether the service and its
database are reachable.
"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from ..db import get_db, scalar
from ..domain import utc_stamp

bp = Blueprint("health", __name__, url_prefix="/api")

_BUILD_FILE = Path(__file__).resolve().parent.parent / "_build_info.json"


def _build_info() -> dict:
    """Which commit is actually serving.

    Added after a deployment reported success while the previous build kept
    serving, which took two diagnostic cycles to spot. A hand-maintained
    version string cannot answer "is my code live?"; a commit stamp written
    at build time can.
    """
    try:
        return json.loads(_BUILD_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"commit": "unknown", "built_at": "unknown"}


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
        "build": _build_info(),
        "time": utc_stamp(),
    }
    return jsonify(payload), (200 if database_ok else 503)
