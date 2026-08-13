#!/usr/bin/env bash
# Deploy TheClinicue straight from this machine to Azure App Service.
#
# This is the fallback for when GitHub Actions is unavailable — a billing block
# on the account, a private repo without minutes, or simply wanting to ship
# without waiting for CI.
#
# It does NOT skip the quality gate. The full test suite, the seven-day date
# matrix and the production configuration check all run locally first, and the
# deployment is abandoned if any of them fail. That is the same gate the CI
# workflow enforces; only the machine running it changes.
#
#   az login
#   bash azure-deploy-direct.sh
#
# Assumes the app already exists (run azure-setup.sh first).

set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-theclinicue-rg}"
APP_NAME="${APP_NAME:-theclinicue}"
SKIP_TESTS="${SKIP_TESTS:-0}"

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
die() { printf '\n\033[1;31m!! %s\033[0m\n' "$1"; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Prefer the project virtualenv if it exists, so the tests run against the
# pinned dependencies rather than whatever is on PATH.
if [ -x ".venv/Scripts/python.exe" ]; then PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ];      then PY=".venv/bin/python"
else PY="python"; fi

# ----------------------------------------------------------- quality gate
if [ "$SKIP_TESTS" = "1" ]; then
    say "SKIPPING the quality gate (SKIP_TESTS=1) — not recommended"
else
    say "Quality gate: full test suite"
    "$PY" -m pytest --no-header -q || die "Tests failed. Nothing was deployed."

    say "Quality gate: date-independence across 7 days"
    "$PY" tools/date_matrix.py --days 7 || die "Suite is date-dependent. Nothing was deployed."

    say "Quality gate: production configuration"
    "$PY" tools/prod_check.py || die "Production configuration check failed. Nothing was deployed."

    printf '\n\033[1;32mAll gates passed.\033[0m\n'
fi

# ------------------------------------------------------------------ build
say "Building the deployment package"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# Ship only what the app needs at runtime. Tests, docs, tooling, the database
# and the virtualenv all stay behind: a smaller artefact deploys faster and
# gives a smaller attack surface.
cp -r app "$STAGE/app"
cp wsgi.py requirements.txt startup.sh "$STAGE/"
find "$STAGE" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGE" -type f \( -name '*.pyc' -o -name '*.sqlite3*' \) -delete 2>/dev/null || true

ZIP="$ROOT/.deploy.zip"
rm -f "$ZIP"
(cd "$STAGE" && "$PY" -c "
import shutil, sys
shutil.make_archive(sys.argv[1], 'zip', '.')
" "${ZIP%.zip}")
printf 'package: %s (%s KB)\n' "$(basename "$ZIP")" "$(( $(wc -c < "$ZIP") / 1024 ))"

# ----------------------------------------------------------------- deploy
say "Deploying to $APP_NAME"
az webapp deploy \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --src-path "$ZIP" \
    --type zip \
    --async false

rm -f "$ZIP"

# ------------------------------------------------------------ smoke test
say "Waiting for the app to restart"
sleep 30

URL="https://${APP_NAME}.azurewebsites.net/api/health"
say "Smoke-testing $URL"

for attempt in 1 2 3 4 5 6; do
    if BODY=$(curl -fsS --max-time 30 "$URL" 2>/dev/null); then
        echo "$BODY"
        echo "$BODY" | grep -q '"status":"ok"'          || die "health reports not ok"
        echo "$BODY" | grep -q '"database":"ok"'        || die "database unreachable"
        echo "$BODY" | grep -q '"environment":"production"' || die "not running in production mode"
        printf '\n\033[1;32mDeployment healthy.\033[0m\n'
        printf '  App     : https://%s.azurewebsites.net\n' "$APP_NAME"
        printf '  Health  : %s\n' "$URL"
        printf '  Sign in : admin@theclinicue.com / Admin#2026\n\n'
        exit 0
    fi
    echo "  attempt $attempt: not up yet, retrying in 20s"
    sleep 20
done

die "App did not become healthy. Stream the logs with:
  az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
