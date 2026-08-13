"""Run the whole test suite once per weekday to prove date-independence.

A clinic scheduler is full of weekday logic — availability rules, closed
weekends, "today" comparisons — so a suite that only runs on the current date
tests one seventh of the behaviour. This runs seven consecutive days.

    python tools/date_matrix.py [--start YYYY-MM-DD] [--days 7]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=date.today().isoformat())
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    failures: list[str] = []

    for offset in range(args.days):
        day = start + timedelta(days=offset)
        env = {**os.environ, "TC_TEST_TODAY": day.isoformat()}
        label = f"{day.isoformat()} ({WEEKDAYS[day.weekday()]})"

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--no-header", "-p", "no:cacheprovider"],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        summary = ""
        lines = (result.stdout or "").splitlines() + (result.stderr or "").splitlines()
        for line in reversed([ln for ln in lines if ln.strip()]):
            if "passed" in line or "failed" in line or "error" in line:
                summary = line.strip()
                break

        if result.returncode == 0:
            print(f"ok    {label:<28} {summary}")
        else:
            print(f"FAIL  {label:<28} {summary}")
            failures.append(label)
            for line in result.stdout.splitlines():
                if line.startswith("FAILED") or line.startswith("ERROR"):
                    print(f"        {line}")

    print()
    if failures:
        print(f"{len(failures)} of {args.days} days failed: {failures}")
        return 1
    print(f"suite is date-independent across {args.days} consecutive days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
