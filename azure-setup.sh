#!/usr/bin/env bash
# Provision TheClinicue on Azure App Service (Linux) in one run.
#
# Everything this script does can also be clicked through in the portal —
# DEPLOY.md documents both routes. Using the CLI is faster and, more usefully,
# it is repeatable: infrastructure that exists only as a sequence of clicks
# cannot be rebuilt after a mistake.
#
#   az login
#   bash azure-setup.sh
#
# Requires the Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli

set -euo pipefail

# ---------------------------------------------------------------- settings
RESOURCE_GROUP="${RESOURCE_GROUP:-theclinicue-rg}"
LOCATION="${LOCATION:-westeurope}"          # closest low-latency region to Ghana
PLAN_NAME="${PLAN_NAME:-theclinicue-plan}"
APP_NAME="${APP_NAME:-theclinicue}"          # must be globally unique
SKU="${SKU:-B1}"                             # B1 supports custom domains + TLS
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
CUSTOM_DOMAIN="${CUSTOM_DOMAIN:-theclinicue.com}"

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

say "Signed-in account"
az account show --query "{subscription:name, id:id}" -o table

# ------------------------------------------------------------ resource group
say "Resource group: $RESOURCE_GROUP ($LOCATION)"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" -o none
echo "ok"

# --------------------------------------------------------------- app service
# B1 is the cheapest tier that allows a custom domain and a free managed
# certificate. F1 (free) cannot bind theclinicue.com, so it is not an option
# here. If cost is the priority, use F1 and demonstrate on the
# *.azurewebsites.net URL instead.
say "App Service plan: $PLAN_NAME ($SKU, Linux)"
az appservice plan create \
    --name "$PLAN_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku "$SKU" \
    --is-linux -o none
echo "ok"

say "Web app: $APP_NAME (Python $PYTHON_VERSION)"
az webapp create \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --plan "$PLAN_NAME" \
    --runtime "PYTHON:$PYTHON_VERSION" -o none
echo "ok  https://$APP_NAME.azurewebsites.net"

# -------------------------------------------------------------- app settings
SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"

say "Application settings"
az webapp config appsettings set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
        TC_ENV=production \
        TC_SECRET_KEY="$SECRET_KEY" \
        TC_COOKIE_SECURE=true \
        TC_SESSION_HOURS=8 \
        TC_BOOKING_HORIZON_DAYS=60 \
        TC_DATABASE_PATH=/home/data/theclinicue.sqlite3 \
        TC_SQLITE_JOURNAL=DELETE \
        SCM_DO_BUILD_DURING_DEPLOYMENT=true \
        WEBSITES_ENABLE_APP_SERVICE_STORAGE=true \
        PYTHONUNBUFFERED=1 -o none
echo "ok  secret generated and stored in Azure, not in the repository"

# TC_DATABASE_PATH points at /home, the only path App Service persists across
# restarts and deployments. It is an SMB share, where SQLite's WAL journal is
# unreliable, so TC_SQLITE_JOURNAL=DELETE selects the rollback journal instead.
# This is a workaround, not a fix; the fix is TD-01 (managed PostgreSQL).

say "Startup command and health check"
az webapp config set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --startup-file "bash startup.sh" \
    --always-on true \
    --http20-enabled true \
    --min-tls-version 1.2 \
    --ftps-state Disabled -o none

az webapp update \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --https-only true -o none

az webapp config set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --generic-configurations '{"healthCheckPath": "/api/health"}' -o none
echo "ok  HTTPS enforced, TLS 1.2 minimum, FTP disabled, health check wired"

# ------------------------------------------------------------------ logging
say "Diagnostic logging"
az webapp log config \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --application-logging filesystem \
    --docker-container-logging filesystem \
    --level information -o none
echo "ok  stream with: az webapp log tail -n $APP_NAME -g $RESOURCE_GROUP"

# ------------------------------------------------------------ publish profile
say "Publish profile for GitHub Actions"
echo "Copy everything between the lines into a GitHub repository secret named"
echo "AZURE_WEBAPP_PUBLISH_PROFILE  (Settings -> Secrets and variables -> Actions)."
echo "------------------------------------------------------------------"
az webapp deployment list-publishing-profiles \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --xml
echo "------------------------------------------------------------------"

# -------------------------------------------------------------------- domain
cat <<EOF

$(printf '\033[1m==> Custom domain (%s)\033[0m' "$CUSTOM_DOMAIN")

Add these DNS records at whoever hosts the zone for $CUSTOM_DOMAIN
(Azure DNS, or your registrar):

  Type   Name   Value
  ----   ----   -----------------------------------------
  TXT    asuid  $(az webapp show -n "$APP_NAME" -g "$RESOURCE_GROUP" --query customDomainVerificationId -o tsv)
  CNAME  www    $APP_NAME.azurewebsites.net
  A      @      $(az webapp show -n "$APP_NAME" -g "$RESOURCE_GROUP" --query inboundIpAddress -o tsv)

Then bind the domain and issue a free managed certificate:

  az webapp config hostname add -g $RESOURCE_GROUP --webapp-name $APP_NAME \\
      --hostname $CUSTOM_DOMAIN
  az webapp config hostname add -g $RESOURCE_GROUP --webapp-name $APP_NAME \\
      --hostname www.$CUSTOM_DOMAIN

  az webapp config ssl create -g $RESOURCE_GROUP --name $APP_NAME \\
      --hostname $CUSTOM_DOMAIN
  az webapp config ssl bind -g $RESOURCE_GROUP --name $APP_NAME \\
      --certificate-thumbprint <thumbprint-from-the-previous-command> \\
      --ssl-type SNI

DNS can take up to an hour to propagate. Verify with:
  nslookup $CUSTOM_DOMAIN

$(printf '\033[1m==> Done\033[0m')

  Default URL : https://$APP_NAME.azurewebsites.net
  Health check: https://$APP_NAME.azurewebsites.net/api/health
  Final URL   : https://$CUSTOM_DOMAIN  (once DNS and the certificate are in place)

Next: push to GitHub. The Actions workflow runs the tests and deploys.
EOF
