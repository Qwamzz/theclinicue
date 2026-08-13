"""Performance verification for NFR-PER-01, NFR-PER-02 and NFR-PER-04.

Measures server-side handling time (the request/response cycle inside the WSGI
app, excluding network) against a seeded dataset, and reports the 95th
percentile per endpoint. Run:  python tools/perf_check.py
"""

from __future__ import annotations

import shutil
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app                                  # noqa: E402
from app.db import get_db                                   # noqa: E402
from app.domain import add_days, today_iso, utc_stamp       # noqa: E402
from app.seed import seed                                   # noqa: E402

READ_BUDGET_MS = 200      # NFR-PER-01
WRITE_BUDGET_MS = 400     # NFR-PER-02
TARGET_ROWS = 1000
ITERATIONS = 60


def inflate(app, target: int) -> int:
    """Grow the dataset to at least `target` appointments, as NFR-PER-01
    specifies, without tripping the one-per-patient-per-day constraint."""
    with app.app_context():
        conn = get_db()
        have = conn.execute("SELECT COUNT(*) AS n FROM appointments").fetchone()["n"]
        patients = [r["id"] for r in conn.execute("SELECT id FROM users WHERE role = 'PATIENT'")]
        stamp = utc_stamp()
        index = 0
        day_offset = -400
        while have < target:
            day = add_days(today_iso(), day_offset)
            for practitioner_id in (1, 2, 3):
                for patient_id in patients:
                    if have >= target:
                        break
                    minute = (index * 15) % (10 * 60) + 8 * 60
                    start = f"{minute // 60:02d}:{minute % 60:02d}"
                    end = f"{(minute + 15) // 60:02d}:{(minute + 15) % 60:02d}"
                    try:
                        conn.execute(
                            """INSERT INTO appointments (code, patient_id, practitioner_id,
                                 service_id, appt_date, start_time, end_time, status, source,
                                 notes, created_by, created_at, updated_at)
                               VALUES (?, ?, ?, 1, ?, ?, ?, 'COMPLETED', 'SELF', '', 1, ?, ?)""",
                            (f"TC-P{index:06d}", patient_id, practitioner_id, day,
                             start, end, stamp, stamp))
                        have += 1
                    except Exception:            # noqa: BLE001 - constraint clash, just skip
                        pass
                    index += 1
            day_offset += 1
        conn.commit()
        return have


def measure(client, method, path, body=None, csrf=None, iterations=ITERATIONS):
    timings, statuses = [], set()
    headers = {"X-CSRF-Token": csrf} if csrf else {}
    for _ in range(iterations):
        started = time.perf_counter()
        response = getattr(client, method)(path, headers=headers, **({"json": body} if body else {}))
        timings.append((time.perf_counter() - started) * 1000)
        statuses.add(response.status_code)
    timings.sort()
    return {
        "p50": statistics.median(timings),
        "p95": timings[int(len(timings) * 0.95) - 1],
        "max": timings[-1],
        "statuses": statuses,
    }


def main() -> int:
    # A file-backed database in WAL mode, which is what production actually
    # runs. A shared-cache in-memory database uses table-level locks that do
    # not honour busy_timeout, so measuring concurrency against it would
    # report a contention failure the deployment does not have.
    workdir = tempfile.mkdtemp(prefix="theclinicue-perf-")
    database = str(Path(workdir) / "perf.sqlite3")

    app = create_app(env="testing", database_path=database)
    with app.app_context():
        seed(get_db())
    rows = inflate(app, TARGET_ROWS)

    patient = app.test_client()
    patient.post("/api/auth/login",
                 json={"email": "patient@theclinicue.com", "password": "Patient#2026"})
    staff = app.test_client()
    staff_login = staff.post("/api/auth/login",
                             json={"email": "staff@theclinicue.com", "password": "Staff#2026"})
    staff_csrf = staff_login.get_json()["csrf_token"]
    admin = app.test_client()
    admin.post("/api/auth/login",
               json={"email": "admin@theclinicue.com", "password": "Admin#2026"})

    tomorrow = add_days(today_iso(), 1)

    reads = [
        ("health", patient, "get", "/api/health"),
        ("list services", patient, "get", "/api/services"),
        ("list practitioners", patient, "get", "/api/practitioners"),
        ("generate slots", patient, "get",
         f"/api/slots?practitioner_id=1&service_id=1&date={tomorrow}"),
        ("my appointments", patient, "get", "/api/appointments/mine?scope=all"),
        ("day sheet", staff, "get", f"/api/appointments?date={today_iso()}"),
        ("live queue", staff, "get", "/api/queue?practitioner_id=1"),
        ("daily report", admin, "get", "/api/admin/reports/daily"),
        ("utilisation report", admin, "get", "/api/admin/reports/utilisation"),
        ("user list", admin, "get", "/api/admin/users?limit=50"),
        ("audit log", admin, "get", "/api/admin/audit?limit=50"),
    ]

    print(f"Dataset: {rows} appointments\n")
    print(f"{'READ endpoint':<26}{'p50 ms':>9}{'p95 ms':>9}{'max ms':>9}   budget {READ_BUDGET_MS} ms")
    print("-" * 70)
    failures = []
    for label, client, method, path in reads:
        result = measure(client, method, path)
        verdict = "PASS" if result["p95"] < READ_BUDGET_MS else "FAIL"
        if verdict == "FAIL":
            failures.append(label)
        print(f"{label:<26}{result['p50']:>9.1f}{result['p95']:>9.1f}{result['max']:>9.1f}   {verdict}")

    print(f"\n{'WRITE endpoint':<26}{'p50 ms':>9}{'p95 ms':>9}{'max ms':>9}   budget {WRITE_BUDGET_MS} ms")
    print("-" * 70)
    writes = measure(staff, "post", "/api/queue/call-next",
                     body={"practitioner_id": 3}, csrf=staff_csrf, iterations=40)
    verdict = "PASS" if writes["p95"] < WRITE_BUDGET_MS else "FAIL"
    if verdict == "FAIL":
        failures.append("call next")
    print(f"{'call next (empty queue)':<26}{writes['p50']:>9.1f}{writes['p95']:>9.1f}"
          f"{writes['max']:>9.1f}   {verdict}")

    login = measure(app.test_client(), "post", "/api/auth/login",
                    body={"email": "patient@theclinicue.com", "password": "Patient#2026"},
                    iterations=10)
    print(f"{'login (test KDF cost)':<26}{login['p50']:>9.1f}{login['p95']:>9.1f}"
          f"{login['max']:>9.1f}   informational")
    print("  note: production uses 600,000 PBKDF2 rounds, which is deliberately slower.")

    # NFR-PER-04: concurrent readers.
    print("\nConcurrency (NFR-PER-04): 30 simultaneous readers")
    errors: list[int] = []
    latencies: list[float] = []
    lock = threading.Lock()

    def worker():
        client = app.test_client()
        client.post("/api/auth/login",
                    json={"email": "patient@theclinicue.com", "password": "Patient#2026"})
        started = time.perf_counter()
        response = client.get(f"/api/slots?practitioner_id=1&service_id=1&date={tomorrow}")
        elapsed = (time.perf_counter() - started) * 1000
        with lock:
            latencies.append(elapsed)
            if response.status_code != 200:
                errors.append(response.status_code)

    threads = [threading.Thread(target=worker) for _ in range(30)]
    start = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    wall = (time.perf_counter() - start) * 1000

    latencies.sort()
    print(f"  completed 30 requests in {wall:.0f} ms, errors: {len(errors)}, "
          f"p95 {latencies[int(len(latencies) * 0.95) - 1]:.1f} ms")
    if errors:
        failures.append("concurrency")

    for connection in list(app.extensions.get("tc_keepalive", []) or []):
        connection.close()
    shutil.rmtree(workdir, ignore_errors=True)

    print()
    if failures:
        print(f"FAILED budgets: {failures}")
        return 1
    print("all performance budgets met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
