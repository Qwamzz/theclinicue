#!/usr/bin/env bash
# Azure App Service (Linux) startup command.
#
# Configure it in the portal under:
#   Configuration -> General settings -> Startup Command:  bash startup.sh
#
# Azure's default Python startup would run `gunicorn app:app`, which is wrong
# here: the WSGI callable lives in wsgi.py, and the database needs seeding on
# first boot.

set -euo pipefail

echo "TheClinicue starting"
echo "  env       : ${TC_ENV:-development}"
echo "  database  : ${TC_DATABASE_PATH:-<default>}"
echo "  journal   : ${TC_SQLITE_JOURNAL:-WAL}"

# /home is the only persistent path on App Service. Make sure the directory
# exists before SQLite tries to open a file inside it.
if [ -n "${TC_DATABASE_PATH:-}" ]; then
    mkdir -p "$(dirname "$TC_DATABASE_PATH")"
fi

# Seed on first boot. Idempotent: it exits early when users already exist, so
# a restart against a persistent database leaves real bookings untouched.
python -m app.seed || echo "seed skipped (database already populated)"

# Azure sets PORT; 8000 is the documented default for Linux Python apps.
exec gunicorn \
    --bind="0.0.0.0:${PORT:-8000}" \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile '-' \
    --error-logfile '-' \
    wsgi:app
