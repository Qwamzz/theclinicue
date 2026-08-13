"""Administrative configuration, audit browsing and reporting (FR-14 … FR-17,
FR-45 … FR-52). Every route in this blueprint is admin-only."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..db import get_db, insert, query, query_one, transaction, write_audit
from ..domain import (
    ROLES,
    add_days,
    is_time,
    to_minutes,
    today_iso,
    utc_stamp,
)
from ..errors import Conflict, Forbidden, NotFound, ValidationError
from ..security import client_ip, current_user, require_admin
from ..services import reports
from ..validators import Validator

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _audit(action: str, entity: str, entity_id: int | None, details: str = "") -> None:
    user = current_user()
    write_audit(
        get_db(),
        actor_id=user["id"] if user else None,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
        ip_address=client_ip(),
    )


# ---------------------------------------------------------------------------
# Services (FR-14, FR-16)
# ---------------------------------------------------------------------------

@bp.get("/services")
@require_admin
def services_list():
    rows = query(get_db(), "SELECT * FROM services ORDER BY name")
    return jsonify({"items": [dict(r) for r in rows]})


@bp.post("/services")
@require_admin
def services_create():
    v = Validator(request.get_json(silent=True))
    name = v.string("name", min_len=2, max_len=80)
    description = v.string("description", required=False, max_len=300, default="")
    duration = v.integer("duration_min", minimum=5, maximum=240)
    v.raise_if_invalid()

    conn = get_db()
    if query_one(conn, "SELECT id FROM services WHERE name = ?", (name,)):
        raise ValidationError(fields={"name": "A service with this name already exists."})

    with transaction(conn):
        service_id = insert(
            conn,
            """INSERT INTO services (name, description, duration_min, is_active, created_at)
               VALUES (?, ?, ?, 1, ?)""",
            (name, description, duration, utc_stamp()),
        )
        _audit("CREATE_SERVICE", "service", service_id, name)
    return jsonify(dict(query_one(conn, "SELECT * FROM services WHERE id = ?", (service_id,)))), 201


@bp.patch("/services/<int:service_id>")
@require_admin
def services_update(service_id: int):
    conn = get_db()
    row = query_one(conn, "SELECT * FROM services WHERE id = ?", (service_id,))
    if row is None:
        raise NotFound("No such service.")

    payload = request.get_json(silent=True) or {}
    v = Validator(payload)
    name = v.string("name", required=False, min_len=2, max_len=80, default=row["name"]) or row["name"]
    description = v.string("description", required=False, max_len=300, default=row["description"])
    duration = v.integer("duration_min", required=False, minimum=5, maximum=240,
                         default=row["duration_min"])
    is_active = v.boolean("is_active", required=False, default=bool(row["is_active"]))
    v.raise_if_invalid()

    with transaction(conn):
        conn.execute(
            "UPDATE services SET name = ?, description = ?, duration_min = ?, is_active = ? WHERE id = ?",
            (name, description, duration, 1 if is_active else 0, service_id),
        )
        _audit("UPDATE_SERVICE", "service", service_id, f"active={is_active}")
    return jsonify(dict(query_one(conn, "SELECT * FROM services WHERE id = ?", (service_id,))))


# ---------------------------------------------------------------------------
# Practitioners (FR-15, FR-16)
# ---------------------------------------------------------------------------

@bp.get("/practitioners")
@require_admin
def practitioners_list():
    rows = query(get_db(), "SELECT * FROM practitioners ORDER BY full_name")
    return jsonify({"items": [dict(r) for r in rows]})


@bp.post("/practitioners")
@require_admin
def practitioners_create():
    v = Validator(request.get_json(silent=True))
    full_name = v.string("full_name", min_len=2, max_len=120)
    specialty = v.string("specialty", required=False, max_len=80, default="")
    room = v.string("room", required=False, max_len=20, default="")
    v.raise_if_invalid()

    conn = get_db()
    with transaction(conn):
        practitioner_id = insert(
            conn,
            """INSERT INTO practitioners (full_name, specialty, room, is_active, created_at)
               VALUES (?, ?, ?, 1, ?)""",
            (full_name, specialty, room, utc_stamp()),
        )
        _audit("CREATE_PRACTITIONER", "practitioner", practitioner_id, full_name)
    return jsonify(dict(query_one(conn, "SELECT * FROM practitioners WHERE id = ?",
                                  (practitioner_id,)))), 201


@bp.patch("/practitioners/<int:practitioner_id>")
@require_admin
def practitioners_update(practitioner_id: int):
    conn = get_db()
    row = query_one(conn, "SELECT * FROM practitioners WHERE id = ?", (practitioner_id,))
    if row is None:
        raise NotFound("No such practitioner.")

    v = Validator(request.get_json(silent=True) or {})
    full_name = v.string("full_name", required=False, min_len=2, max_len=120,
                         default=row["full_name"]) or row["full_name"]
    specialty = v.string("specialty", required=False, max_len=80, default=row["specialty"])
    room = v.string("room", required=False, max_len=20, default=row["room"])
    is_active = v.boolean("is_active", required=False, default=bool(row["is_active"]))
    v.raise_if_invalid()

    with transaction(conn):
        conn.execute(
            "UPDATE practitioners SET full_name = ?, specialty = ?, room = ?, is_active = ? WHERE id = ?",
            (full_name, specialty, room, 1 if is_active else 0, practitioner_id),
        )
        _audit("UPDATE_PRACTITIONER", "practitioner", practitioner_id, f"active={is_active}")
    return jsonify(dict(query_one(conn, "SELECT * FROM practitioners WHERE id = ?",
                                  (practitioner_id,))))


# ---------------------------------------------------------------------------
# Availability rules (FR-17, FR-18)
# ---------------------------------------------------------------------------

@bp.get("/availability")
@require_admin
def availability_list():
    v = Validator(request.args.to_dict())
    practitioner_id = v.integer("practitioner_id", required=False, minimum=1)
    v.raise_if_invalid()

    if practitioner_id:
        rows = query(
            get_db(),
            """SELECT r.*, p.full_name AS practitioner_name
                 FROM availability_rules r
                 JOIN practitioners p ON p.id = r.practitioner_id
                WHERE r.practitioner_id = ?
                ORDER BY r.weekday, r.start_time""",
            (practitioner_id,),
        )
    else:
        rows = query(
            get_db(),
            """SELECT r.*, p.full_name AS practitioner_name
                 FROM availability_rules r
                 JOIN practitioners p ON p.id = r.practitioner_id
                ORDER BY p.full_name, r.weekday, r.start_time""",
        )
    return jsonify({"items": [dict(r) for r in rows]})


@bp.post("/availability")
@require_admin
def availability_create():
    v = Validator(request.get_json(silent=True))
    practitioner_id = v.integer("practitioner_id", minimum=1)
    weekday = v.integer("weekday", minimum=0, maximum=6)
    start_time = v.time("start_time")
    end_time = v.time("end_time")
    v.raise_if_invalid()

    # FR-18. Checked here so the user gets a field-level message rather than a
    # raw CHECK-constraint failure; the constraint remains as the backstop.
    if is_time(start_time) and is_time(end_time) and to_minutes(start_time) >= to_minutes(end_time):
        raise ValidationError(fields={"end_time": "The end time must be after the start time."})

    conn = get_db()
    if query_one(conn, "SELECT id FROM practitioners WHERE id = ?", (practitioner_id,)) is None:
        raise ValidationError(fields={"practitioner_id": "No such practitioner."})

    overlapping = query_one(
        conn,
        """SELECT id FROM availability_rules
            WHERE practitioner_id = ? AND weekday = ? AND is_active = 1
              AND start_time < ? AND ? < end_time""",
        (practitioner_id, weekday, end_time, start_time),
    )
    if overlapping is not None:
        raise Conflict("This overlaps an existing availability window for that day.")

    with transaction(conn):
        rule_id = insert(
            conn,
            """INSERT INTO availability_rules
                 (practitioner_id, weekday, start_time, end_time, is_active, created_at)
               VALUES (?, ?, ?, ?, 1, ?)""",
            (practitioner_id, weekday, start_time, end_time, utc_stamp()),
        )
        _audit("CREATE_AVAILABILITY", "availability_rule", rule_id,
               f"practitioner={practitioner_id} weekday={weekday} {start_time}-{end_time}")
    return jsonify(dict(query_one(conn, "SELECT * FROM availability_rules WHERE id = ?",
                                  (rule_id,)))), 201


@bp.delete("/availability/<int:rule_id>")
@require_admin
def availability_delete(rule_id: int):
    """Deactivates rather than deletes, so existing appointments booked under
    the rule keep their provenance."""
    conn = get_db()
    row = query_one(conn, "SELECT * FROM availability_rules WHERE id = ?", (rule_id,))
    if row is None:
        raise NotFound("No such availability rule.")
    with transaction(conn):
        conn.execute("UPDATE availability_rules SET is_active = 0 WHERE id = ?", (rule_id,))
        _audit("DELETE_AVAILABILITY", "availability_rule", rule_id)
    return jsonify({"ok": True, "id": rule_id})


# ---------------------------------------------------------------------------
# Users (FR-45 … FR-47)
# ---------------------------------------------------------------------------

@bp.get("/users")
@require_admin
def users_list():
    config = current_app.config["TC"]
    args = request.args.to_dict()
    v = Validator(args)
    limit = v.integer("limit", required=False, minimum=1, maximum=config.max_page_size, default=50)
    offset = v.integer("offset", required=False, minimum=0, default=0)
    v.raise_if_invalid()

    needle = args.get("q", "").strip()[:60]
    role = args.get("role", "").strip().upper()
    clauses: list[str] = []
    params: list[object] = []
    if needle:
        clauses.append("(full_name LIKE ? OR email LIKE ? OR phone LIKE ?)")
        params.extend([f"%{needle}%"] * 3)
    if role in ROLES:
        clauses.append("role = ?")
        params.append(role)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    conn = get_db()
    total = query_one(conn, f"SELECT COUNT(*) AS n FROM users{where}", params)
    rows = query(
        conn,
        f"""SELECT id, full_name, email, phone, role, is_active, created_at
              FROM users{where} ORDER BY id DESC LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    )
    return jsonify({"items": [dict(r) for r in rows], "total": int(total["n"]) if total else 0})


@bp.patch("/users/<int:user_id>")
@require_admin
def users_update(user_id: int):
    """FR-46, FR-47."""
    actor = current_user()
    assert actor is not None
    conn = get_db()
    row = query_one(conn, "SELECT * FROM users WHERE id = ?", (user_id,))
    if row is None:
        raise NotFound("No such user.")

    v = Validator(request.get_json(silent=True) or {})
    role = v.choice("role", ROLES, required=False, default=row["role"])
    is_active = v.boolean("is_active", required=False, default=bool(row["is_active"]))
    v.raise_if_invalid()

    # FR-47: an administrator cannot demote or disable themselves. Without this
    # the last admin can lock everyone out of configuration irreversibly.
    if user_id == actor["id"] and (role != row["role"] or not is_active):
        raise Forbidden(
            "You cannot change your own role or deactivate your own account. "
            "Ask another administrator to do it."
        )

    with transaction(conn):
        conn.execute(
            "UPDATE users SET role = ?, is_active = ? WHERE id = ?",
            (role, 1 if is_active else 0, user_id),
        )
        _audit("UPDATE_USER", "user", user_id, f"role={role} active={is_active}")

    updated = query_one(
        conn, "SELECT id, full_name, email, phone, role, is_active FROM users WHERE id = ?",
        (user_id,),
    )
    return jsonify(dict(updated))


# ---------------------------------------------------------------------------
# Audit log (FR-49)
# ---------------------------------------------------------------------------

@bp.get("/audit")
@require_admin
def audit_list():
    config = current_app.config["TC"]
    args = request.args.to_dict()
    v = Validator(args)
    limit = v.integer("limit", required=False, minimum=1, maximum=config.max_page_size, default=50)
    offset = v.integer("offset", required=False, minimum=0, default=0)
    actor_id = v.integer("actor_id", required=False, minimum=1)
    v.raise_if_invalid()

    clauses: list[str] = []
    params: list[object] = []
    if actor_id:
        clauses.append("a.actor_id = ?")
        params.append(actor_id)
    action = args.get("action", "").strip().upper()[:40]
    if action:
        clauses.append("a.action = ?")
        params.append(action)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    conn = get_db()
    total = query_one(conn, f"SELECT COUNT(*) AS n FROM audit_log a{where}", params)
    rows = query(
        conn,
        f"""SELECT a.id, a.action, a.entity, a.entity_id, a.details, a.ip_address,
                   a.created_at, u.email AS actor_email, u.full_name AS actor_name
              FROM audit_log a
         LEFT JOIN users u ON u.id = a.actor_id
            {where}
          ORDER BY a.id DESC LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    )
    return jsonify({"items": [dict(r) for r in rows], "total": int(total["n"]) if total else 0})


# ---------------------------------------------------------------------------
# Reports (FR-50 … FR-52)
# ---------------------------------------------------------------------------

@bp.get("/reports/daily")
@require_admin
def report_daily():
    v = Validator(request.args.to_dict())
    date_iso = v.date("date", required=False, default=today_iso()) or today_iso()
    v.raise_if_invalid()
    summary = reports.daily_summary(get_db(), date_iso)
    summary["throughput"] = reports.throughput(get_db(), date_iso)["items"]
    return jsonify(summary)


@bp.get("/reports/utilisation")
@require_admin
def report_utilisation():
    v = Validator(request.args.to_dict())
    to_date = v.date("to", required=False, default=today_iso()) or today_iso()
    from_date = v.date("from", required=False, default=add_days(to_date, -13)) or add_days(to_date, -13)
    v.raise_if_invalid()
    if from_date > to_date:
        raise ValidationError(fields={"from": "The start date must not be after the end date."})
    return jsonify(reports.utilisation(get_db(), from_date, to_date))
