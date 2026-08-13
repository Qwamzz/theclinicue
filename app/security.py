"""Authentication, authorisation and session security.

Implements FR-04 to FR-13 and NFR-SEC-01 to NFR-SEC-06. See
docs/System_Design.md §5 for the threat model and for why the session token
lives in an HttpOnly cookie rather than in localStorage.
"""

from __future__ import annotations

import functools
import hmac
import secrets
import threading
import time
from typing import Any, Callable, Iterable

import jwt
from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from .config import PRODUCTION_HASH_METHOD
from .db import get_db, query_one
from .domain import ROLE_ADMIN, ROLE_STAFF, STAFF_ROLES, utc_now
from .errors import CsrfInvalid, Forbidden, RateLimited, Unauthenticated

#: NFR-SEC-02. Re-exported from config so callers have one name to import.
PBKDF2_METHOD = PRODUCTION_HASH_METHOD

# Verbs that change state and therefore require a CSRF token (FR-07).
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


# --------------------------------------------------------------------------
# Passwords (FR-04)
# --------------------------------------------------------------------------

def hash_password(plaintext: str, method: str | None = None) -> str:
    """Hash a password with the configured KDF.

    The cost falls back to the production setting outside an application
    context, so a script that forgets to build an app cannot accidentally
    write a cheap hash into a real database.
    """
    if method is None:
        try:
            method = current_app.config["CQ"].password_hash_method
        except RuntimeError:
            method = PRODUCTION_HASH_METHOD
    return generate_password_hash(plaintext, method=method)


def verify_password(password_hash: str, plaintext: str) -> bool:
    if not password_hash or not plaintext:
        return False
    try:
        return check_password_hash(password_hash, plaintext)
    except (ValueError, TypeError):
        # A corrupt or unrecognised hash must fail closed, not raise.
        return False


# --------------------------------------------------------------------------
# Session tokens (FR-06)
# --------------------------------------------------------------------------

def issue_token(user_id: int, role: str, csrf_token: str) -> str:
    config = current_app.config["CQ"]
    now = utc_now()
    payload = {
        "sub": str(user_id),
        "role": role,
        "csrf": csrf_token,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + config.session_hours * 3600,
        "jti": secrets.token_urlsafe(8),
    }
    return jwt.encode(payload, config.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    config = current_app.config["CQ"]
    try:
        return jwt.decode(
            token,
            config.secret_key,
            algorithms=["HS256"],           # pinned: never trust the header's alg
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def set_session_cookies(response, token: str, csrf_token: str):
    """Attach both cookies.

    The session cookie is HttpOnly so script cannot read it; the CSRF cookie
    deliberately is not, because the client must echo it in a header.
    """
    config = current_app.config["CQ"]
    max_age = config.session_hours * 3600
    response.set_cookie(
        config.session_cookie,
        token,
        max_age=max_age,
        httponly=True,
        secure=config.cookie_secure,
        samesite="Lax",
        path="/",
    )
    response.set_cookie(
        config.csrf_cookie,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=config.cookie_secure,
        samesite="Lax",
        path="/",
    )
    return response


def clear_session_cookies(response):
    config = current_app.config["CQ"]
    response.delete_cookie(config.session_cookie, path="/")
    response.delete_cookie(config.csrf_cookie, path="/")
    return response


# --------------------------------------------------------------------------
# Current user resolution
# --------------------------------------------------------------------------

def _load_user(user_id: int) -> dict[str, Any] | None:
    row = query_one(
        get_db(),
        "SELECT id, full_name, email, phone, role, is_active FROM users WHERE id = ?",
        (user_id,),
    )
    return None if row is None else {key: row[key] for key in row.keys()}


def current_user() -> dict[str, Any] | None:
    """Resolve the caller from the session cookie, or None.

    The result is memoised per request; `False` is used as the negative cache
    marker so an anonymous request does not re-decode the token on every call.
    """
    if "current_user" in g:
        return g.current_user or None

    config = current_app.config["CQ"]
    token = request.cookies.get(config.session_cookie, "")
    claims = decode_token(token) if token else None
    user = None
    if claims:
        try:
            user = _load_user(int(claims["sub"]))
        except (KeyError, TypeError, ValueError):
            user = None
        # A deactivated account must lose its session immediately (FR-13),
        # not merely be refused at the next login.
        if user and not user["is_active"]:
            user = None
        if user:
            user["_csrf"] = claims.get("csrf", "")

    g.current_user = user or False
    return user


def require_user() -> dict[str, Any]:
    user = current_user()
    if user is None:
        raise Unauthenticated()
    return user


# --------------------------------------------------------------------------
# Decorators
# --------------------------------------------------------------------------

def require_auth(view: Callable) -> Callable:
    """Reject anonymous callers with 401 (FR-11)."""

    @functools.wraps(view)
    def wrapper(*args: Any, **kwargs: Any):
        require_user()
        return view(*args, **kwargs)

    return wrapper


def require_role(*roles: str) -> Callable:
    """Reject callers whose role is not listed, with 403, and log it (FR-12)."""
    allowed = frozenset(roles)

    def decorator(view: Callable) -> Callable:
        @functools.wraps(view)
        def wrapper(*args: Any, **kwargs: Any):
            user = require_user()
            if user["role"] not in allowed:
                from .db import write_audit  # local import avoids a cycle at module load

                write_audit(
                    get_db(),
                    actor_id=user["id"],
                    action="ACCESS_DENIED",
                    entity="endpoint",
                    details=f"{request.method} {request.path} requires {sorted(allowed)}",
                    ip_address=client_ip(),
                )
                get_db().commit()
                raise Forbidden()
            return view(*args, **kwargs)

        return wrapper

    return decorator


def require_staff(view: Callable) -> Callable:
    return require_role(*STAFF_ROLES)(view)


def require_admin(view: Callable) -> Callable:
    return require_role(ROLE_ADMIN)(view)


def verify_csrf() -> None:
    """Double-submit check on every state-changing request (FR-07).

    Stronger than a plain double-submit: the expected value is carried inside
    the signed session token, so an attacker who can set a cookie but cannot
    forge the JWT still fails.
    """
    if request.method not in UNSAFE_METHODS:
        return
    user = current_user()
    if user is None:
        return                      # anonymous POSTs (login, register) are exempt
    config = current_app.config["CQ"]
    supplied = request.headers.get(config.csrf_header, "")
    expected = user.get("_csrf", "")
    if not supplied or not expected or not hmac.compare_digest(supplied, expected):
        raise CsrfInvalid()


# --------------------------------------------------------------------------
# Login throttling (FR-08)
# --------------------------------------------------------------------------

class RateLimiter:
    """Fixed-window failure counter held in process memory.

    Adequate for a single-instance clinic deployment and nothing more: the
    state is per-worker and is lost on restart, so a determined attacker can
    dilute it across workers. That limitation is TD-07; the fix is a shared
    store (Redis) once the deployment has more than one instance.
    """

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, window: int, now: float) -> list[float]:
        recent = [t for t in self._hits.get(key, []) if now - t < window]
        if recent:
            self._hits[key] = recent
        else:
            self._hits.pop(key, None)
        return recent

    def check(self, key: str, *, limit: int, window: int) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._prune(key, window, now)) >= limit:
                raise RateLimited()

    def record_failure(self, key: str, *, window: int) -> None:
        now = time.monotonic()
        with self._lock:
            recent = self._prune(key, window, now)
            recent.append(now)
            self._hits[key] = recent

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter()


def client_ip() -> str:
    """Best-effort client address.

    X-Forwarded-For is honoured because the app runs behind a platform proxy
    that terminates TLS. The header is spoofable by a direct caller, so this
    value is used for audit context only and never for an authorisation
    decision.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.remote_addr or "")[:64]


def security_headers(response):
    """NFR-SEC-04.

    The CSP allows inline styles because a handful of dynamic width values are
    set as style attributes; scripts are restricted to 'self', which is what
    actually matters for XSS containment.
    """
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'self'; form-action 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if current_app.config["CQ"].cookie_secure:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


def is_staff(user: dict[str, Any] | None) -> bool:
    return bool(user) and user["role"] in STAFF_ROLES


def is_admin(user: dict[str, Any] | None) -> bool:
    return bool(user) and user["role"] == ROLE_ADMIN


__all__: Iterable[str] = (
    "hash_password", "verify_password", "issue_token", "decode_token",
    "new_csrf_token", "set_session_cookies", "clear_session_cookies",
    "current_user", "require_user", "require_auth", "require_role",
    "require_staff", "require_admin", "verify_csrf", "rate_limiter",
    "client_ip", "security_headers", "is_staff", "is_admin",
    "ROLE_ADMIN", "ROLE_STAFF",
)
