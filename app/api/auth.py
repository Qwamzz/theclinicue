"""Registration, login, logout and session introspection (FR-01 … FR-13)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..db import get_db, query_one, transaction, write_audit
from ..domain import ROLE_PATIENT, utc_stamp
from ..errors import ApiError, Unauthenticated, ValidationError
from ..security import (
    clear_session_cookies,
    client_ip,
    current_user,
    hash_password,
    issue_token,
    new_csrf_token,
    rate_limiter,
    require_auth,
    set_session_cookies,
    verify_password,
)
from ..validators import Validator

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _public_user(row) -> dict:
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "phone": row["phone"],
        "role": row["role"],
    }


@bp.post("/register")
def register():
    """FR-01 … FR-04. Self-registration always creates a PATIENT; the role is
    never taken from the request body, or anyone could mint an administrator."""
    config = current_app.config["CQ"]
    payload = request.get_json(silent=True)

    v = Validator(payload)
    full_name = v.string("full_name", min_len=2, max_len=120)
    email = v.email("email")
    phone = v.phone("phone")
    password = v.password("password", min_length=config.password_min_length)
    v.raise_if_invalid()

    conn = get_db()
    existing = query_one(conn, "SELECT id FROM users WHERE email = ?", (email,))
    if existing is not None:
        # FR-02: identical wording whether or not the account is active, so the
        # endpoint cannot be used to test which addresses are registered.
        raise ValidationError(
            fields={"email": "This email address is already registered. Try signing in."}
        )

    with transaction(conn):
        cursor = conn.execute(
            """INSERT INTO users (full_name, email, phone, password_hash, role,
                                  is_active, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (full_name, email, phone, hash_password(password), ROLE_PATIENT, utc_stamp()),
        )
        user_id = int(cursor.lastrowid or 0)
        write_audit(
            conn,
            actor_id=user_id,
            action="REGISTER",
            entity="user",
            entity_id=user_id,
            ip_address=client_ip(),
        )

    row = query_one(conn, "SELECT * FROM users WHERE id = ?", (user_id,))
    csrf = new_csrf_token()
    token = issue_token(user_id, ROLE_PATIENT, csrf)
    response = jsonify({"user": _public_user(row), "csrf_token": csrf})
    response.status_code = 201
    return set_session_cookies(response, token, csrf)


@bp.post("/login")
def login():
    """FR-05 … FR-08, FR-13."""
    config = current_app.config["CQ"]
    payload = request.get_json(silent=True)

    v = Validator(payload)
    email = v.email("email")
    supplied = payload.get("password") if isinstance(payload, dict) else None
    if not isinstance(supplied, str) or not supplied:
        v.add_error("password", "This is required.")
    v.raise_if_invalid()

    ip = client_ip()
    identity_key = f"login:{email}"
    address_key = f"login-ip:{ip}"
    # Throttle by account and by source address: the first stops a single
    # account being ground down, the second stops one host spraying many
    # accounts.
    rate_limiter.check(identity_key, limit=config.login_max_attempts,
                       window=config.login_window_seconds)
    rate_limiter.check(address_key, limit=config.login_max_attempts * 4,
                       window=config.login_window_seconds)

    conn = get_db()
    row = query_one(conn, "SELECT * FROM users WHERE email = ?", (email,))

    # Always run a verification, even for an unknown address, so that response
    # time does not reveal whether the account exists. The decoy carries the
    # configured cost so it takes the same time as a genuine check.
    stored_hash = (
        row["password_hash"] if row is not None
        else f"{config.password_hash_method}${'decoysalt'}${'0' * 64}"
    )
    password_ok = verify_password(stored_hash, supplied)

    if row is None or not password_ok or not row["is_active"]:
        rate_limiter.record_failure(identity_key, window=config.login_window_seconds)
        rate_limiter.record_failure(address_key, window=config.login_window_seconds)
        with transaction(conn):
            write_audit(
                conn,
                actor_id=row["id"] if row is not None else None,
                action="LOGIN_FAILED",
                entity="user",
                entity_id=row["id"] if row is not None else None,
                details="inactive account" if (row is not None and not row["is_active"]) else "bad credentials",
                ip_address=ip,
            )
        raise Unauthenticated("Email or password is incorrect.")

    rate_limiter.clear(identity_key)
    with transaction(conn):
        write_audit(
            conn,
            actor_id=row["id"],
            action="LOGIN",
            entity="user",
            entity_id=row["id"],
            ip_address=ip,
        )

    csrf = new_csrf_token()
    token = issue_token(row["id"], row["role"], csrf)
    response = jsonify({"user": _public_user(row), "csrf_token": csrf})
    return set_session_cookies(response, token, csrf)


@bp.post("/logout")
def logout():
    """FR-09. Idempotent: logging out when already anonymous is a success."""
    user = current_user()
    if user is not None:
        conn = get_db()
        with transaction(conn):
            write_audit(
                conn,
                actor_id=user["id"],
                action="LOGOUT",
                entity="user",
                entity_id=user["id"],
                ip_address=client_ip(),
            )
    return clear_session_cookies(jsonify({"ok": True}))


@bp.get("/me")
@require_auth
def me():
    """FR-10. Lets the client render role-appropriate navigation."""
    user = current_user()
    assert user is not None
    return jsonify({
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "phone": user["phone"],
            "role": user["role"],
        },
        "csrf_token": user.get("_csrf", ""),
    })


@bp.get("/session")
def session_state():
    """Unauthenticated probe used by the client on first paint, so an anonymous
    visitor does not see a 401 in the console on every page load."""
    user = current_user()
    if user is None:
        return jsonify({"authenticated": False, "user": None})
    return jsonify({
        "authenticated": True,
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"],
        },
        "csrf_token": user.get("_csrf", ""),
    })


__all__ = ["bp", "ApiError"]
