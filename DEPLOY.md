# Deploying TheClinicue — complete step-by-step

Nothing here is assumed. Every command is copy-pasteable and every screen is named.

- **Destination:** Azure App Service (Linux, Python 3.12) at **https://theclinicue.com**
- **Time:** ~25 minutes of work, plus DNS propagation (up to 1 hour, usually 5–15 minutes)
- **Cost:** ~$13/month on B1 (needed for the custom domain), or $0 on F1 without it

### What you need before you start

| # | Thing | How to check you have it |
|---|---|---|
| 1 | The project folder | You are reading this file inside it |
| 2 | Git | `git --version` |
| 3 | Python 3.11+ | `python --version` |
| 4 | A GitHub account (`Qwamzz`) | Sign in at github.com |
| 5 | An Azure subscription | Sign in at portal.azure.com |
| 6 | The `theclinicue.com` domain | You said it is on Azure |
| 7 | Azure CLI *(optional but much faster)* | `az version` — install from https://aka.ms/installazurecliwindows |
| 8 | GitHub CLI *(optional, makes Step 1.2 easier)* | `gh --version` — already installed here as v2.97.0 |

---

# Part 1 — Put the code on GitHub

## Step 1.1 — Create an empty repository

> **Skip this step if you use Option A in Step 1.2** — the GitHub CLI creates the
> repository for you. This section is for the plain-Git route.

1. Go to **https://github.com/new**
2. Fill in exactly:
   - **Owner:** `Qwamzz`
   - **Repository name:** `theclinicue`
   - **Description:** `Outpatient appointment and queue management for community clinics`
   - **Public** *(so your examiner can read the source without being invited)*
3. **Leave all three tickboxes OFF** — do not add a README, .gitignore or licence.
   > This matters. If the repository has any commit in it, your push in Step 1.2 is rejected with `Updates were rejected because the remote contains work that you do not have locally`.
4. Click **Create repository**.

GitHub shows a "quick setup" page. Leave it open — you need the URL.

## Step 1.2 — Push

There are two ways to authenticate. **Option A is easier** — it uses a browser
sign-in instead of hand-creating a token. The GitHub CLI is already installed
on this machine (`gh` v2.97.0).

> **If you have already created `Qwamzz/theclinicue` on github.com** (it exists
> and is empty), skip `gh repo create` — it will fail with "Name already exists".
> The `origin` remote is already configured in this project, so all you need is:
>
> ```bash
> gh auth login          # once, in a NEW terminal
> git push -u origin main
> ```

### Option A — GitHub CLI (recommended)

```bash
gh auth login
```

Answer the prompts:

| Prompt | Answer |
|---|---|
| What account do you want to log into? | **GitHub.com** |
| What is your preferred protocol for Git operations? | **HTTPS** |
| Authenticate Git with your GitHub credentials? | **Yes** |
| How would you like to authenticate? | **Login with a web browser** |

It shows a one-time code, then opens github.com in your browser. Paste the
code, approve, and come back to the terminal.

Then create the repository and push in one command — this replaces Step 1.1
entirely, so you can skip creating it in the web UI:

```bash
gh repo create Qwamzz/theclinicue --public --source=. --remote=origin --push
```

Verify:

```bash
gh repo view Qwamzz/theclinicue --web
```

> If `gh` is not on your PATH, it lives at `C:\Program Files\GitHub CLI\gh.exe`.
> Open a **new** terminal after installing — PATH changes do not apply to
> already-open windows.

### Option B — plain Git with a Personal Access Token

Do Step 1.1 first (create the empty repository in the web UI), then:

```bash
git remote add origin https://github.com/Qwamzz/theclinicue.git
git branch -M main
git push -u origin main
```

**Username:** `Qwamzz`

**Password:** GitHub no longer accepts your account password. Create a token:

1. Go to **https://github.com/settings/tokens**
2. **Generate new token → Generate new token (classic)**
3. **Note:** `theclinicue deploy`
4. **Expiration:** 90 days
5. **Scopes:** tick **`repo`** (the top-level box selects the sub-boxes)
6. **Generate token**
7. **Copy it now** — GitHub shows it exactly once
8. Paste it as the *password* at the prompt

### Either way, verify

Refresh your repository page. You should see `app/`, `docs/`, `tests/`,
`.github/`, `README.md`, `Dockerfile`, `azure-setup.sh`.

> Nothing sensitive is pushed. `.gitignore` excludes the database, `.env`,
> coverage output and the virtual environment, and there are no secrets in the
> code — Azure generates the session key in Part 2.

## Step 1.3 — Confirm CI is running

Click the **Actions** tab. A workflow named **Test and deploy to Azure** should be running.

The `test` job will pass (it runs the 312 tests, the seven-day date matrix and the production config check). The `deploy` job will **fail** — that is expected and correct at this point, because you have not yet created the Azure app or added the publish profile. You fix that in Part 2 and Part 3.

---

# Part 2 — Create the Azure app

Choose **either** Option A (one command) **or** Option B (portal clicks). They produce the same result.

## Option A — Azure CLI (recommended, ~3 minutes)

```bash
az login
```

A browser opens; sign in. Then, from the project folder:

```bash
bash azure-setup.sh
```

That single script:

- creates resource group `theclinicue-rg` in West Europe
- creates a Linux App Service plan on B1
- creates the web app `theclinicue`
- generates a strong `TC_SECRET_KEY` and stores it **in Azure**, never in your repo
- sets every application setting the app needs
- sets the startup command, health check path, HTTPS-only, TLS 1.2 minimum, and disables FTP
- turns on log streaming
- **prints your publish profile** (needed in Part 3) and **your exact DNS records** (needed in Part 4)

**Keep that output.** Copy it into a scratch file — you need two pieces of it later.

To change any default:

```bash
APP_NAME=theclinicue-prod LOCATION=uksouth SKU=B1 bash azure-setup.sh
```

> If `theclinicue` is already taken globally, the script fails at the web-app step. Re-run it with `APP_NAME=theclinicue-gh` or similar, and remember to update `AZURE_WEBAPP_NAME` in `.github/workflows/azure-deploy.yml`.

Skip to **Part 3**.

## Option B — Azure Portal (~10 minutes)

### 2.1 Create the Web App

1. **https://portal.azure.com** → **Create a resource** → search **Web App** → **Create**
2. **Basics** tab:
   - **Subscription:** your subscription
   - **Resource group:** **Create new** → `theclinicue-rg`
   - **Name:** `theclinicue` → this becomes `theclinicue.azurewebsites.net`, which must be globally unique. If it shows a red cross, try `theclinicue-gh`.
   - **Publish:** `Code`
   - **Runtime stack:** `Python 3.12`
   - **Operating System:** `Linux`
   - **Region:** `West Europe`
   - **Pricing plan:** click **Explore pricing plans** → **Basic B1** → **Select**
     > **F1 Free cannot bind a custom domain.** If you do not need theclinicue.com, F1 is fine and everything else in this guide still applies except Part 4.
3. **Review + create** → **Create**
4. Wait for "Your deployment is complete" → **Go to resource**

### 2.2 Add the application settings

In the Web App: left menu → **Settings → Environment variables** (older portals: **Configuration → Application settings**).

Click **+ Add** once per row:

| Name | Value |
|---|---|
| `TC_ENV` | `production` |
| `TC_SECRET_KEY` | *(see below)* |
| `TC_COOKIE_SECURE` | `true` |
| `TC_SESSION_HOURS` | `8` |
| `TC_BOOKING_HORIZON_DAYS` | `60` |
| `TC_DATABASE_PATH` | `/home/data/theclinicue.sqlite3` |
| `TC_SQLITE_JOURNAL` | `DELETE` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE` | `true` |

For `TC_SECRET_KEY`, generate one locally and paste the output:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then click **Apply** / **Save** and confirm the restart.

> **Why these two are not optional:**
> `TC_DATABASE_PATH` points inside `/home`, the **only** directory App Service keeps across restarts. Anything written elsewhere is destroyed when the container recycles.
> `/home` is an **SMB file share**, and SQLite's WAL journal is not reliable over SMB. `TC_SQLITE_JOURNAL=DELETE` selects the older rollback journal, which is. This is technical debt **TD-01**; the real fix is PostgreSQL.

### 2.3 Set the startup command

Left menu → **Settings → Configuration → General settings**:

- **Startup Command:** `bash startup.sh`
- **Always on:** `On`
- **HTTP version:** `2.0`
- **Minimum Inbound TLS Version:** `1.2`
- **FTP state:** `Disabled`

**Save.**

> Without the startup command Azure runs its default `gunicorn app:app`, which is wrong — the WSGI callable here is `wsgi:app`, and the database needs seeding on first boot.

### 2.4 Turn on HTTPS-only and the health check

- **Settings → Configuration → General settings → HTTPS Only:** `On` → **Save**
- **Monitoring → Health check:** `Enable` → **Path:** `/api/health` → **Save**

---

# Part 3 — Connect GitHub to Azure

## Step 3.1 — Get the publish profile

**Portal route:** Web App → **Overview** → top toolbar → **Download publish profile**. It saves a `.PublishSettings` file. Open it in Notepad and copy **everything**.

**CLI route:**

```bash
az webapp deployment list-publishing-profiles \
  --name theclinicue --resource-group theclinicue-rg --xml
```

Copy the whole XML output, starting at `<publishData>`.

## Step 3.2 — Store it as a GitHub secret

1. Go to **https://github.com/Qwamzz/theclinicue/settings/secrets/actions**
2. **New repository secret**
3. **Name:** `AZURE_WEBAPP_PUBLISH_PROFILE` *(exactly this — the workflow looks for it by name)*
4. **Secret:** paste the entire XML
5. **Add secret**

## Step 3.3 — If you changed the app name

Edit `.github/workflows/azure-deploy.yml`, line 12:

```yaml
  AZURE_WEBAPP_NAME: theclinicue     # <- change to your actual app name
```

## Step 3.4 — Deploy

```bash
git commit --allow-empty -m "Trigger first deployment"
git push
```

Watch **Actions** in GitHub. You will see:

1. **test** — ~4 minutes. Runs 312 tests with an 80% coverage floor, the seven-day date matrix, and the production configuration check.
2. **deploy** — ~2 minutes. Only starts if `test` passed. Ends by curling the live `/api/health` and asserting `"status":"ok"`.

**If `test` fails, nothing is deployed.** That gate is the point of having the suite.

## Step 3.5 — Verify

```bash
curl https://theclinicue.azurewebsites.net/api/health
```

Expected:

```json
{"service":"theclinicue","version":"1.0.0","status":"ok","database":"ok","environment":"production","time":"..."}
```

Open `https://theclinicue.azurewebsites.net` and sign in:

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@theclinicue.com` | `Admin#2026` |
| Reception staff | `staff@theclinicue.com` | `Staff#2026` |
| Patient | `patient@theclinicue.com` | `Patient#2026` |

**If anything is wrong, stream the logs:**

```bash
az webapp log tail --name theclinicue --resource-group theclinicue-rg
```

---

# Part 4 — Point theclinicue.com at it

Skip this whole part if you are staying on F1 / the azurewebsites.net address.

## Step 4.1 — Collect the two values you need

```bash
az webapp show --name theclinicue --resource-group theclinicue-rg \
  --query "{verificationId:customDomainVerificationId, ip:inboundIpAddress}" -o table
```

**Portal route:** Web App → **Custom domains** → **Add custom domain**. The verification ID and IP are shown on that blade.

## Step 4.2 — Add the DNS records

Go to where the `theclinicue.com` zone lives. If you bought the domain through **Azure App Service Domains**, it is in Azure DNS: **portal.azure.com → DNS zones → theclinicue.com**.

Add three records:

| Type | Name | Value | TTL |
|---|---|---|---|
| `TXT` | `asuid` | *the verificationId from Step 4.1* | 3600 |
| `A` | `@` | *the inboundIpAddress from Step 4.1* | 3600 |
| `CNAME` | `www` | `theclinicue.azurewebsites.net` | 3600 |

> In Azure DNS, `@` is entered as a blank name or `@` depending on the blade. The `asuid` TXT record is what proves to Azure that you control the domain — without it, Step 4.3 fails.

**Wait, then check propagation:**

```bash
nslookup theclinicue.com
nslookup -type=txt asuid.theclinicue.com
```

Do not continue until both return the values you set. This usually takes 5–15 minutes.

## Step 4.3 — Bind the domain

```bash
az webapp config hostname add --resource-group theclinicue-rg \
  --webapp-name theclinicue --hostname theclinicue.com

az webapp config hostname add --resource-group theclinicue-rg \
  --webapp-name theclinicue --hostname www.theclinicue.com
```

**Portal route:** **Custom domains → Add custom domain →** enter `theclinicue.com` → **Validate** → **Add**.

## Step 4.4 — Free TLS certificate

```bash
az webapp config ssl create --resource-group theclinicue-rg \
  --name theclinicue --hostname theclinicue.com
```

Copy the `thumbprint` from the output, then:

```bash
az webapp config ssl bind --resource-group theclinicue-rg \
  --name theclinicue --certificate-thumbprint <PASTE_THUMBPRINT> --ssl-type SNI
```

Repeat both commands for `www.theclinicue.com`.

**Portal route:** **Custom domains** → next to the domain, **Add binding** → **TLS/SSL type: SNI SSL** → **Certificate: Create App Service Managed Certificate** → **Add**.

> The certificate is free and auto-renews. It can only be issued **after** the hostname is bound and DNS resolves — that is why the order matters.

## Step 4.5 — Final check

Open **https://theclinicue.com**. You should get the sign-in page with a valid padlock.

```bash
curl https://theclinicue.com/api/health
```

---

# Part 5 — Finish the submission

Substitute the live URLs into all seven PDFs and the links file:

```bash
python tools/package.py \
  --student "Nii Yartey Gidiglo" \
  --student-id "22424650" \
  --live-url "https://theclinicue.com" \
  --repo-url "https://github.com/Qwamzz/theclinicue"
```

This writes `Submission/22424650_TheClinicue.zip` — that is the file you upload to SAKAI.

---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Updates were rejected because the remote contains work` | The GitHub repo was created with a README | `git pull --rebase origin main` then push again, or delete and recreate it empty |
| Git asks for a password and rejects yours | GitHub requires a token | Use a Personal Access Token with `repo` scope (Step 1.2) |
| `Application Error` on first visit | Startup command not set | **Configuration → General settings → Startup Command** = `bash startup.sh` |
| Logs: `TC_SECRET_KEY must be set in production` | App setting missing | Add it in Environment variables. *(The app refuses to start rather than generate one — deliberate, see `app/config.py`.)* |
| Logs: `unable to open database file` | `/home` storage disabled | Set `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true` and restart |
| `database is locked` under load | WAL journal on SMB | Set `TC_SQLITE_JOURNAL=DELETE`, restart. Properly fixed by TD-01. |
| Logs: `ModuleNotFoundError: flask` | Oryx did not build | Set `SCM_DO_BUILD_DURING_DEPLOYMENT=true`, redeploy |
| Deploy succeeds, site 404s | Wrong WSGI target | Should be `wsgi:app`, not `app:app` — `startup.sh` handles it |
| GitHub Actions: `deploy` fails with `No credentials found` | Secret missing or misnamed | It must be exactly `AZURE_WEBAPP_PUBLISH_PROFILE` |
| GitHub Actions: `test` fails | A genuine test failure | Read the log — the gate is working. Fix before deploying. |
| Custom domain will not validate | `asuid` TXT missing or not propagated | `nslookup -type=txt asuid.theclinicue.com` |
| Certificate creation fails | Domain not bound, or DNS not resolving | Bind hostname first, wait for DNS, then create |
| Site slow on first hit | **Always on** off (unavailable on F1) | Turn **Always on** to `On` (needs B1+) |
| Sign-in appears to do nothing | `TC_COOKIE_SECURE=true` over plain HTTP | Turn on **HTTPS Only** and use the https:// URL |

---

# Costs and switching off

| Tier | Monthly | Custom domain | Always on |
|---|---|---|---|
| F1 Free | $0 | No | No |
| **B1 Basic** | **~$13** | Yes | Yes |

Azure student/trial credit covers B1 comfortably for an assessment period.

```bash
az webapp stop --name theclinicue --resource-group theclinicue-rg   # pause serving, keep everything
az webapp start --name theclinicue --resource-group theclinicue-rg  # resume
az group delete --name theclinicue-rg --yes                         # delete everything
```

---

# Data persistence, honestly

`/home` **is** persistent, so bookings survive restarts and redeploys.

It is still not production-grade, and the submission says so:

- SQLite over SMB has slower, less predictable locking than local disk.
- Writes serialise; under contention the app returns `503 SERVICE_BUSY` with `Retry-After` rather than failing outright.
- There is no automated backup (**TD-12**).

The Technical Debt Register keeps a hard gate: **no real patient data until TD-01 (Azure Database for PostgreSQL), TD-02 (schema migrations) and TD-12 (rehearsed backups) have shipped** — release v1.0.1, ~20.5 hours.

---

# Appendix — running it locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements-dev.txt
python -m app.seed
python wsgi.py                  # http://localhost:8000
```

| Command | What it does |
|---|---|
| `python -m pytest` | 312 tests, ~33 s |
| `python -m pytest --cov=app` | with coverage (93%) |
| `python tools/date_matrix.py` | runs the suite across 7 weekdays |
| `python tools/perf_check.py` | performance budgets |
| `python tools/prod_check.py` | production configuration |
| `python tools/smoke.py` | end-to-end smoke run |

# Appendix — Docker, if you prefer

```bash
docker build -t theclinicue .

docker run -d --name theclinicue -p 8000:8000 \
  -e TC_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  -e TC_COOKIE_SECURE=true \
  -v theclinicue-data:/data \
  --restart unless-stopped \
  theclinicue
```

The `-v` volume is what makes data survive a restart. Put TLS in front of it — `TC_COOKIE_SECURE=true` requires HTTPS, and over plain HTTP the browser silently discards the session cookie.
