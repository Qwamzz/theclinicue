# TheClinicue

**Outpatient appointment booking and patient queue management for community clinics.**

TheClinicue replaces the paper-and-shouting outpatient queue with real appointment slots, a digital
check-in with ticket numbers, and operational reporting the clinic manager can act on. It stores
no clinical data — that boundary is deliberate.

[![tests](https://img.shields.io/badge/tests-334%20passing-brightgreen)]()
[![coverage](https://img.shields.io/badge/coverage-92%25-brightgreen)]()
[![python](https://img.shields.io/badge/python-3.11%2B-blue)]()

---

## What it does

| Role | Capabilities |
|---|---|
| **Patient** | Register, browse real availability, book and cancel appointments, see their live queue position and ticket number. |
| **Reception staff** | Work the day sheet, check patients in, issue tickets, call the next patient, complete consultations, record no-shows, register walk-ins. |
| **Administrator** | Manage services, clinicians, weekly availability, user accounts and roles; read the audit log; view attendance, no-show and utilisation reports. |

---

## Quick start

```bash
git clone <repository-url> theclinicue
cd theclinicue

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # or requirements-test.txt for tests only

python -m app.seed               # load demonstration data
python wsgi.py                   # http://localhost:8000
```

### Demonstration accounts

| Role | Email | Password |
|---|---|---|
| Patient | `patient@theclinicue.com` | `Patient#2026` |
| Reception staff | `staff@theclinicue.com` | `Staff#2026` |
| Administrator | `admin@theclinicue.com` | `Admin#2026` |

These are safe to publish precisely because the demonstration deployment holds no real patient data.

---

## Tests

```bash
python -m pytest                                  # 334 tests, ~33 s
python -m pytest --cov=app --cov-report=term      # with coverage (92%)
python tools/perf_check.py                        # performance budgets
python tools/smoke.py                             # end-to-end smoke run
```

---

## Architecture

Four layers, deployed as one WSGI process. The load-bearing rule is that **no Flask object crosses
into the domain layer, and no SQL appears above the data access layer** — which is what makes the
service layer testable without a web request, and what confines SQLite to a single module.

```
Browser (no build step, no framework)
   │  HTTPS · JSON · session cookie + X-CSRF-Token
   ▼
app/api/*.py          Flask blueprints — HTTP concerns only
   │  @require_auth → @require_role → @require_csrf → validate()
   ▼
app/services/*.py     all business rules; imports no framework
   │
   ▼
app/db.py             connections, transactions, parameterised SQL, audit
   ▼
SQLite (WAL, foreign keys on)
```

| Path | Purpose |
|---|---|
| `app/domain.py` | Enumerations, the appointment state machine, pure helpers |
| `app/services/scheduling.py` | Slot generation, booking, cancellation |
| `app/services/queue.py` | Check-in, ticketing, call, complete, no-show |
| `app/services/reports.py` | Daily summary, utilisation, waiting time |
| `app/security.py` | Hashing, JWT sessions, CSRF, RBAC, rate limiting |
| `app/validators.py` | Declarative request validation |
| `app/schema.sql` | Schema, constraints and indexes |
| `app/static/` | The client: HTML, CSS, ES modules — 82 KB total |
| `docs/` | SRS, effort estimation, design, testing, technical debt |

---

## Deployment

### Docker

```bash
docker build -t theclinicue .
docker run -p 8000:8000 \
  -e TC_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  -v theclinicue-data:/data \
  theclinicue
```

The `-v` is not optional for real use: without a mounted volume the database is destroyed on every
restart (technical debt **TD-01**).

### Azure App Service

Production runs on Azure App Service (Linux, Python 3.12), served at
**https://theclinicue.com**. Provision it in one command:

```bash
az login
bash azure-setup.sh
```

That creates the resource group, plan and web app; generates and stores `TC_SECRET_KEY`; sets the
startup command, health check, HTTPS enforcement and logging; and prints the publish profile plus
the DNS records for the custom domain.

Push to `main` and GitHub Actions runs the full suite, the seven-day date matrix and the production
configuration check — then deploys only if all three pass, and smoke-tests `/api/health` afterwards.

Full walkthrough, including the custom domain and the free managed TLS certificate, is in
[DEPLOY.md](DEPLOY.md).

> Azure persists `/home`, so bookings survive restarts and redeploys. But `/home` is an SMB share,
> where SQLite's WAL journal is unreliable — hence `TC_SQLITE_JOURNAL=DELETE`. That is a workaround;
> the fix is **TD-01**, migrating to Azure Database for PostgreSQL.

### Configuration

All configuration is environment variables — see [`.env.example`](.env.example). In production the
application **refuses to start** without `TC_SECRET_KEY`, rather than generating one that would
differ between workers and be discarded on restart.

---

## Security

| Control | Implementation |
|---|---|
| Password storage | PBKDF2-HMAC-SHA256, 600,000 iterations, per-user salt |
| Sessions | Signed JWT in an `HttpOnly`, `SameSite=Lax`, `Secure` cookie |
| CSRF | Double-submit token bound to the signed session, enforced centrally on every unsafe verb |
| Authorisation | Server-side role checks on every protected endpoint; client-side checks are presentation only |
| Object access | Another patient's record returns 404, not 403, so ids cannot be enumerated |
| Injection | Every statement parameterised; no string-interpolated SQL in the codebase |
| XSS | The client's only element factory assigns text through `textContent` — raw HTML is rejected by design |
| Brute force | Per-identity and per-address login throttling |
| Audit | Append-only log of every security-relevant and state-changing action |
| Headers | CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, HSTS in production |

Found a security issue? Please report it privately rather than opening a public issue.

---

## Documentation

| Document | Contents |
|---|---|
| `docs/SRS.md` | Problem, stakeholders, 58 functional and 26 non-functional requirements, scope |
| `docs/Effort_Estimation.md` | Use Case Points, COCOMO II, PERT, and how the estimate cut the scope |
| `docs/System_Design.md` | Architecture, database design, API contract, security design |
| `docs/Testing_Report.md` | Test strategy, results, defect log, UAT |
| `docs/Technical_Debt_Plan.md` | 18 debt items with cause, impact, priority and a repayment schedule |
| `docs/User_Manual.md` | Task-based guide for each role |
| `docs/diagrams/` | Architecture, use case, ERD, class, sequence, state machine, activity, wireframes |

---

## Known limitations

These are documented rather than hidden. The full analysis is in `docs/Technical_Debt_Plan.md`.

- **SQLite on an ephemeral filesystem (TD-01)** — data is lost on redeploy unless a volume is mounted. *No real patient data until this is repaid.*
- **No schema migrations (TD-02)** — the first schema change after go-live is a manual operation.
- **Sessions cannot be revoked (TD-03)** — logout clears the cookie but the token stays valid until it expires. Deactivating the user *does* take effect immediately.
- **The live queue does not refresh itself (TD-14)** — reload to see changes.
- **Utilisation figures are approximate (TD-11)** — capacity is computed from current availability applied retrospectively.
- **UTC only (TD-17)** — correct for Ghana (GMT+0); wrong anywhere else.

---

## Acknowledgements

Built with [Flask](https://flask.palletsprojects.com/), [Werkzeug](https://werkzeug.palletsprojects.com/),
[PyJWT](https://pyjwt.readthedocs.io/), [Gunicorn](https://gunicorn.org/), [SQLite](https://sqlite.org/)
and [pytest](https://docs.pytest.org/). Password hashing follows the
[OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html);
the threat model follows [OWASP ASVS 4.0](https://owasp.org/www-project-application-security-verification-standard/).
No third-party CSS or JavaScript is used — the client is hand-written.

## Licence

Academic coursework. Not licensed for clinical use.
