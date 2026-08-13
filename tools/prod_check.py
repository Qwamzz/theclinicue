"""Verify the production configuration path before deploying.

Checks the two things that only differ in production: the missing-secret
startup guard, and the Secure/HSTS transport settings.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

failures = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {label}{'' if ok else f'  -> {detail}'}")
    if not ok:
        failures.append(label)


def main() -> int:
    os.environ["CQ_ENV"] = "production"
    os.environ.pop("CQ_SECRET_KEY", None)

    from app import create_app                      # noqa: E402
    from app.db import get_db                       # noqa: E402
    from app.seed import seed                       # noqa: E402

    # 1. A production app must refuse to start without a signing key.
    try:
        create_app()
        check("production refuses to start without CQ_SECRET_KEY", False, "it started")
    except RuntimeError as exc:
        check("production refuses to start without CQ_SECRET_KEY", True)
        print(f"      message: {str(exc).split('.')[0]}.")

    # 2. With a key, the transport settings must harden.
    os.environ["CQ_SECRET_KEY"] = "verification-only-key-not-for-real-use-000000"
    database = str(Path(tempfile.mkdtemp(prefix="clinicue-prod-")) / "prod.sqlite3")
    os.environ["CQ_DATABASE_PATH"] = database

    app = create_app()
    with app.app_context():
        seed(get_db())
    client = app.test_client()

    health = client.get("/api/health")
    body = health.get_json()
    check("health endpoint responds 200", health.status_code == 200, health.status_code)
    check("environment reports production", body["environment"] == "production", body["environment"])
    check("HSTS header present", "Strict-Transport-Security" in health.headers)
    check("CSP header present", "Content-Security-Policy" in health.headers)

    login = client.post("/api/auth/login",
                        json={"email": "patient@clinicue.health", "password": "Patient#2026"})
    check("login succeeds", login.status_code == 200, login.status_code)

    cookies = login.headers.getlist("Set-Cookie")
    session = next((c for c in cookies if c.startswith("cq_session=")), "")
    csrf = next((c for c in cookies if c.startswith("cq_csrf=")), "")
    check("session cookie is Secure", "Secure" in session, session[:80])
    check("session cookie is HttpOnly", "HttpOnly" in session)
    check("session cookie is SameSite=Lax", "SameSite=Lax" in session)
    check("csrf cookie is Secure", "Secure" in csrf)
    check("csrf cookie is readable by script", "HttpOnly" not in csrf)

    # 3. Password hashing must be at full production cost here.
    with app.app_context():
        row = get_db().execute(
            "SELECT password_hash FROM users WHERE email = 'patient@clinicue.health'").fetchone()
    check("passwords hashed at 600,000 PBKDF2 rounds",
          row["password_hash"].startswith("pbkdf2:sha256:600000$"),
          row["password_hash"][:32])

    print()
    if failures:
        print(f"{len(failures)} FAILED: {failures}")
        return 1
    print("production configuration verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
