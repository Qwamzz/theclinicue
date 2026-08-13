# Technical Debt Register and Repayment Plan

## Clinicue — Outpatient Appointment & Queue Management System

**Document version:** 1.0
**Register date:** 12 August 2026
**Owner:** [STUDENT NAME] (developer and maintainer)

---

## 1. Purpose and Method

Technical debt is a deliberate or accidental shortfall between the system as built and the system as it should be, which is cheap now and expensive later. The metaphor is exact: an item has a **principal** (the cost of fixing it) and an **interest rate** (the recurring cost of not fixing it). An item whose interest is near zero can be carried indefinitely; an item whose interest compounds must be repaid early.

This register was **not** assembled retrospectively. Six items (TD-01, TD-02, TD-04, TD-05, TD-06, TD-07) were identified during design, before implementation began, and are recorded in System Design §8. Four of them exist because the effort estimate showed a 7.6-hour overrun and specific shortcuts were taken to close it — the traceability runs *estimate → shortcut → debt item*, which is documented in Effort Estimation §4.2.

### 1.1 Classification scheme

| Class | Meaning | Action |
|---|---|---|
| **CRITICAL** | Causes data loss, security exposure or user harm in normal operation. | Must be repaid before any real clinic uses the system with real patients. |
| **SCHEDULED** | Genuine cost that compounds, but tolerable in a pilot. | Assigned to a named release. |
| **ACCEPTABLE** | Low interest. Correct decision for this scale; revisit only if scale changes. | Monitored against a stated trigger. |

### 1.2 How each item is scored

- **Principal** — estimated effort to repay, in hours.
- **Interest** — what it costs while unpaid, per unit time or per event.
- **Trigger** — the observable condition that forces repayment. An item without a trigger is a wish, not a plan.

### 1.3 Register summary

| Class | Items | Total principal |
|---|---|---|
| CRITICAL | 3 | 21 h |
| SCHEDULED | 9 | 63 h |
| ACCEPTABLE | 6 | 46 h (deferred, may never be paid) |
| **Total** | **18** | **130 h** |

The whole delivered system took 48 hours. The register says that making it production-grade costs another **84 hours** of critical and scheduled work — a ratio of roughly 1.75 : 1. That is a normal, honest ratio for a prototype, and stating it is more useful than pretending the debt does not exist.

---

## 2. CRITICAL Items — repay before real patient data

### TD-01 — SQLite on an ephemeral container filesystem

| Field | Detail |
|---|---|
| **Debt** | The production datastore is a single SQLite file inside the application container. On a free hosting tier the container filesystem is ephemeral, so **every redeploy or platform restart destroys all data**. SQLite also serialises writers, so concurrent writes queue behind one lock. |
| **Cause** | Constraint C-02: no budget for a managed database in v1.0. The decision was recorded at design time, not discovered later. |
| **Impact** | **Catastrophic and silent.** A clinic that has taken 400 bookings loses all of them at the next deploy, with no error and no warning. The write serialisation is a lesser but real issue: the performance run measured contention failures under concurrent writes, which is what motivated TD-14's 503 handling. |
| **Interest** | Compounds with every booking taken. Grows with usage — the longer the system runs successfully, the worse the eventual loss. |
| **Priority** | **CRITICAL** |
| **Trigger** | Any deployment intended to hold real patient bookings. Already tripped for pilot use. |
| **Resolution** | Migrate to managed PostgreSQL. The data access layer (`app/db.py`) is the only module that touches SQLite, which is precisely why it was written that way: the change is bounded to one module plus the connection setup. Steps: (1) add `psycopg`; (2) parameter-style shim (`?` → `%s`); (3) replace the two SQLite-specific partial indexes with PostgreSQL equivalents (identical syntax — both support partial unique indexes); (4) `BEGIN IMMEDIATE` → `SELECT … FOR UPDATE` or serialisable isolation; (5) point `CQ_DATABASE_PATH` at a `DATABASE_URL`. |
| **Principal** | 10 h |
| **Verification** | Full test suite green against PostgreSQL; a redeploy with data present leaves the data present; concurrent-booking test still yields exactly one winner. |

### TD-02 — No schema migration tooling

| Field | Detail |
|---|---|
| **Debt** | `init_schema()` runs `schema.sql`, which is entirely `CREATE TABLE IF NOT EXISTS`. It can create a schema from nothing; it cannot **change** one. Adding a column to a populated production database currently requires hand-written SQL executed manually. |
| **Cause** | Estimation mitigation M2: an ORM plus migration framework was costed at 1.5 h of the 7.6 h that had to be found. |
| **Impact** | The first schema change after go-live is a manual, unversioned, untested, unrepeatable operation on live data — the single most common cause of production data corruption in small systems. It also blocks confident iteration: the team becomes reluctant to change the schema at all, which is how a data model ossifies. |
| **Interest** | Zero until the first schema change; very high from that moment on. Steps sharply rather than compounding. |
| **Priority** | **CRITICAL** (because it must be in place *before* it is needed, not after) |
| **Trigger** | The first schema change after the first real deployment. |
| **Resolution** | Adopt Alembic. Baseline the current schema as revision 0001 so existing databases stamp cleanly, then require every subsequent change to ship as a migration with an `upgrade` and a tested `downgrade`. Pairs naturally with TD-01 — do both in one piece of work. |
| **Principal** | 6 h |
| **Verification** | A migration applied to a copy of production data, then rolled back, leaves the database byte-identical. |

### TD-03 — Session tokens cannot be revoked

| Field | Detail |
|---|---|
| **Debt** | Sessions are stateless JWTs. Logout clears the cookie in the browser but the token itself remains cryptographically valid until it expires — up to 8 hours. There is no server-side revocation. |
| **Cause** | Stateless sessions were chosen to avoid a session store; the revocation gap was not fully priced at the time. This is the one critical item that was **not** anticipated at design time — it emerged while writing the security tests. |
| **Impact** | If a token is captured (a shared clinic PC, a shoulder-surfed device, a lost phone), signing out does not protect the account. Deactivating the user *does* close it immediately — `current_user()` re-reads `is_active` on every request, which is verified by `test_deactivation_invalidates_a_live_session` — so the exposure is bounded and there is a working manual remedy. That mitigation is what keeps this from being an emergency. |
| **Interest** | Low frequency, high severity per event. Rises with the number of shared devices in use. |
| **Priority** | **CRITICAL** (security) |
| **Trigger** | Deployment to any site using shared devices — which is every clinic front desk. |
| **Resolution** | Add a `revoked_tokens` table keyed on the JWT `jti` claim (already issued, currently unused), with expiry-based cleanup. Check it in `decode_token`. Cheaper interim measure available immediately: cut `CQ_SESSION_HOURS` from 8 to 2, which shrinks the window at the cost of more frequent logins. |
| **Principal** | 5 h |
| **Verification** | A token captured before logout is rejected after logout. |

---

## 3. SCHEDULED Items

### TD-04 — Dates and times stored as unvalidated TEXT

| Field | Detail |
|---|---|
| **Debt** | SQLite has no date or time type. Dates are `'YYYY-MM-DD'` and times `'HH:MM'` strings. Nothing in the database prevents `'not-a-date'`; only application validation does. |
| **Cause** | SQLite's type system. |
| **Impact** | A defect or a direct SQL edit that bypasses the validators can write a malformed value, which then breaks slot generation for that practitioner with a `ValueError`. Correctness currently depends on every write path going through `validators.py` — true today, but an invariant with no enforcement is an invariant waiting to be broken. |
| **Interest** | Low now (one validation layer, well tested), rising with every new write path. |
| **Priority** | SCHEDULED — **v1.1**, folded into the TD-01 migration |
| **Trigger** | Repaid automatically by the PostgreSQL move, which has real `DATE` and `TIME` types. |
| **Resolution** | Native column types in PostgreSQL; add `CHECK` constraints with date regexes as an interim measure if the migration slips. |
| **Principal** | 3 h (≈ 0 if done with TD-01) |

### TD-05 — No frontend component model

| Field | Detail |
|---|---|
| **Debt** | The client is hand-written DOM construction with no framework. There is no component abstraction, no reactive state and no client-side test suite. View modules manually re-render whole regions after every mutation. |
| **Cause** | Estimation mitigation M1: a toolchain was costed at 2 h and ~40 KB of payload against a 150 KB budget on 3G connections. |
| **Impact** | Real but bounded. Adding a screen means writing DOM code by hand. State that appears in two places (the day sheet and the queue panel) is refreshed by calling both loaders — a pattern that works but must be remembered. The `h()` helper does prevent the worst failure mode by making `textContent` the only text path, so XSS is structurally excluded rather than merely avoided. |
| **Interest** | Grows roughly linearly with the number of screens. Currently 7 screens; painful somewhere past 15. |
| **Priority** | SCHEDULED — **v1.2** |
| **Trigger** | The screen count passing 12, or the first defect caused by two views disagreeing about state. |
| **Resolution** | Introduce Preact with htm (no build step, ~4 KB) rather than React with a bundler — this keeps the zero-build property and the payload budget while adding a genuine component model. Migrate one view at a time; the API needs no change. |
| **Principal** | 12 h |

### TD-06 — PBKDF2 rather than a memory-hard KDF

| Field | Detail |
|---|---|
| **Debt** | Passwords use PBKDF2-HMAC-SHA256 at 600,000 iterations. This meets current OWASP guidance, but PBKDF2 is not memory-hard and is therefore far cheaper to attack on GPUs than Argon2id. |
| **Cause** | Estimation mitigation M3: Argon2id needs a native build chain, costed at 0.75 h plus deployment risk. |
| **Impact** | Only material if the password table is exfiltrated. In that scenario, offline cracking is perhaps an order of magnitude cheaper than it would be against Argon2id. Salting is per-user (verified by test), so precomputation is not available to the attacker. |
| **Interest** | Zero unless a breach occurs; significant in that event. |
| **Priority** | SCHEDULED — **v1.1** |
| **Trigger** | Any move to hold data beyond scheduling, or the first security review. |
| **Resolution** | Add `argon2-cffi`; hash new and changed passwords with Argon2id; rehash existing passwords transparently on next successful login (the code already verifies whatever algorithm the stored hash declares, so both can coexist during transition). |
| **Principal** | 3 h |

### TD-07 — Rate-limit state is per-process and volatile

| Field | Detail |
|---|---|
| **Debt** | `RateLimiter` holds failure counts in a Python dictionary. State is lost on restart and is **not shared between Gunicorn workers**. |
| **Cause** | Simplicity under time pressure; a shared store was not justifiable at one instance. |
| **Impact** | With N workers the effective limit is up to N × 5 attempts rather than 5, because an attacker's requests are spread across workers. With 2 workers that is 10 attempts per 15 minutes — still a meaningful brake, but weaker than specified in FR-08. A restart clears all counters. |
| **Interest** | Proportional to worker count. At 2 workers, modest. |
| **Priority** | SCHEDULED — **v1.2**, or immediately if worker count rises |
| **Trigger** | Scaling past 2 workers, or evidence of credential-stuffing in the audit log. |
| **Resolution** | Move counters to Redis with a sliding-window script; keep the in-memory implementation as a fallback for single-process development. The `RateLimiter` interface is already narrow (`check`, `record_failure`, `clear`), so this is a drop-in replacement. |
| **Principal** | 5 h |

### TD-08 — Demonstration data doubles as the test fixture

| Field | Detail |
|---|---|
| **Debt** | `app/seed.py` populates both the demonstration deployment and every integration test. Tests therefore depend on the shape of the demo data, including its pseudo-random appointment fill. |
| **Cause** | Estimation mitigation M5, worth 0.8 h. |
| **Impact** | Concrete and already felt: three test fixtures had to be written defensively to search for a free slot rather than assume one, precisely because the seed's random fill varies by weekday. A change to the demo data can break unrelated tests. The seed is at least deterministic (fixed RNG seed), which contains the damage. |
| **Interest** | Moderate. Every new test either couples to the seed or works around it. |
| **Priority** | SCHEDULED — **v1.1** |
| **Trigger** | The next time a seed change breaks a test that has nothing to do with seeding. |
| **Resolution** | Separate the concerns: keep `seed.py` for demonstration, add explicit factory helpers (`make_patient`, `make_appointment`, `make_availability`) for tests, and build each test's world from an empty database. |
| **Principal** | 8 h |

### TD-09 — No automated accessibility or load testing

| Field | Detail |
|---|---|
| **Debt** | Accessibility and performance were verified by documented manual procedure (recorded in the Testing Report) rather than by tooling in a pipeline. |
| **Cause** | Estimation mitigation M6, worth 1.2 h. |
| **Impact** | Manual checks are real evidence but they are a snapshot, not a guarantee: nothing prevents a future change from reintroducing a 34 px tap target or a horizontal overflow. Both defects were in fact found and fixed manually during this build, which demonstrates both that the manual check works and that the regression risk is real. |
| **Interest** | Grows with change rate. |
| **Priority** | SCHEDULED — **v1.2** |
| **Trigger** | The first accessibility regression reaching a user, or a formal WCAG commitment. |
| **Resolution** | Add axe-core in a headless browser check and a Locust load profile, both run in CI (see TD-13). |
| **Principal** | 8 h |

### TD-10 — The audit log is append-only by convention only

| Field | Detail |
|---|---|
| **Debt** | No application code updates or deletes `audit_log`, but nothing enforces that. Anyone with database access can rewrite history. |
| **Cause** | Enforcement needs triggers or a separate append-only store; not affordable in the window. |
| **Impact** | Weakens the audit trail exactly where it matters most — an insider. For the trail's operational purpose (diagnosing what happened) it is fine; for its evidential purpose it is not. |
| **Interest** | Low, but this is the control that all the accountability claims rest on. |
| **Priority** | SCHEDULED — **v1.2** |
| **Trigger** | Any regulatory or disciplinary reliance on the audit trail. |
| **Resolution** | `BEFORE UPDATE` and `BEFORE DELETE` triggers raising an exception, plus a database role for the application that lacks `UPDATE`/`DELETE` on the table. Longer term, ship logs to an append-only external sink. |
| **Principal** | 4 h |

### TD-11 — Utilisation applies current availability retrospectively

| Field | Detail |
|---|---|
| **Debt** | `reports.utilisation()` computes "slots offered" from the availability rules **as they are now**, then applies that to a historical date range. It also divides by the mean duration of active services rather than by the services actually booked. |
| **Cause** | Correct calculation needs dated availability snapshots — a schema change that was out of scope. |
| **Impact** | The utilisation percentage is an approximation. If a clinician's hours changed mid-period, the figure is simply wrong for the earlier part, and nothing in the UI says so. This is the most misleading item in the register, because a wrong number presented confidently is worse than no number. |
| **Interest** | Rises every time availability is edited. |
| **Priority** | SCHEDULED — **v1.1** |
| **Trigger** | The first availability change after go-live. |
| **Resolution** | Two parts. Immediately (0.5 h): label the figure "approximate" in the UI and in this document. Properly (6 h): add `valid_from` / `valid_to` to `availability_rules` and compute capacity from the rules in force on each date; derive slot width from each appointment's own service. |
| **Principal** | 6 h |

### TD-12 — No automated backup

| Field | Detail |
|---|---|
| **Debt** | There is no backup of any kind. Recovery from data loss is impossible. |
| **Cause** | Follows directly from TD-01: there is nothing durable to back up. |
| **Impact** | No recovery point, no recovery time. Combined with TD-01 this is the difference between an inconvenience and the end of the pilot. |
| **Interest** | Compounds with data volume. |
| **Priority** | SCHEDULED — **v1.1**, immediately after TD-01 |
| **Trigger** | The moment the datastore becomes durable. |
| **Resolution** | Managed PostgreSQL automated daily backups with 7-day retention, plus a documented, *rehearsed* restore. An unrehearsed backup is not a backup. |
| **Principal** | 4 h |

### TD-13 — No continuous integration pipeline

| Field | Detail |
|---|---|
| **Debt** | Tests run when the developer remembers. Nothing prevents a commit with failing tests, and nothing enforces the 80% coverage requirement (NFR-MNT-02). |
| **Cause** | Not in the 48-hour scope. |
| **Impact** | The 312-test suite is a real asset whose value depends entirely on being run. A suite that is not run automatically decays. |
| **Interest** | Grows with contributor count and time since the last manual run. |
| **Priority** | SCHEDULED — **v1.1** |
| **Trigger** | The second contributor, or the first "it worked on my machine". |
| **Resolution** | GitHub Actions: run pytest with coverage on every push, fail below 80%, block merge on red. Add `ruff` for linting. |
| **Principal** | 4 h |

### TD-14 — The live queue does not update itself

| Field | Detail |
|---|---|
| **Debt** | The queue view is a snapshot. Staff and patients must reload the page to see changes. |
| **Cause** | Polling or websockets were out of the 48-hour scope. |
| **Impact** | The most user-visible item in the register. A patient watching their position sees a stale number, which undermines the core value proposition ("know how long you will wait"). Staff may act on a stale day sheet, though the server's state-machine checks mean a stale click produces a clear 409 rather than corruption. |
| **Interest** | High in user-perceived quality; zero in correctness. |
| **Priority** | SCHEDULED — **v1.1** |
| **Trigger** | First pilot feedback — this is confidently predicted to be the first complaint. |
| **Resolution** | Start with 15-second polling of `/api/queue` when that view is visible (2 h, no server change). Move to server-sent events if bandwidth cost proves material — polling is the right first answer on intermittent mobile connections because it survives disconnection without reconnect logic. |
| **Principal** | 5 h |

### TD-15 — Duplicated CRUD shape across admin endpoints

| Field | Detail |
|---|---|
| **Debt** | The services, practitioners and availability endpoints in `app/api/admin.py` repeat the same list/create/update structure with different field names. Roughly 60 lines of near-identical code. |
| **Cause** | Written under time pressure; the third instance was copied from the second. |
| **Impact** | Mild. A change to the CRUD pattern (adding pagination, or a common audit shape) must be made three times, and one will be forgotten. This is ordinary duplication, not a design flaw. |
| **Interest** | Low, linear in the number of managed entity types. |
| **Priority** | SCHEDULED — **v1.2** |
| **Trigger** | Adding a fourth managed entity type. |
| **Resolution** | A small declarative resource helper taking an entity name, a validator specification and an audit action. Deliberately *not* done now: with three instances the abstraction would be guessed rather than derived, and a wrong abstraction costs more than the duplication. |
| **Principal** | 4 h |

---

## 4. ACCEPTABLE Items — carried deliberately

These are correct decisions at the current scale. Each has a stated trigger that would change the answer.

| ID | Debt | Cause | Impact | Trigger for revisiting | Principal |
|---|---|---|---|---|---|
| TD-16 | **No API versioning.** Endpoints are `/api/...` with no version segment. | Single client, shipped together with the server. | A breaking API change would break any client not deployed in lockstep. | The first third-party or mobile client (deferred FR-62/FR-65). | 3 h |
| TD-17 | **UTC only, no timezone handling.** All dates and times are UTC. | The target deployment is Ghana (GMT+0), where UTC *is* local time, so this is correct today rather than merely convenient. | Any deployment outside GMT would show and book wrong times. This would be a serious defect — it is acceptable only because of where the system runs. | The first deployment outside GMT+0. | 8 h |
| TD-18 | **No email or SMS notification.** Bookings and reminders are screen-only. | Constraint C-03: no gateway budget. Deferred as FR-59. | No reminders means a higher no-show rate — the very metric the system exists to reduce. Genuinely limits value, but is a *missing feature* rather than a flaw in what was built. | Pilot data showing no-show rates remain high. | 12 h |
| TD-19 | **`X-Forwarded-For` is trusted for audit IPs.** A direct caller can spoof the header. | The app sits behind a platform proxy that terminates TLS. | Audit IP addresses could be falsified. Contained by design: this value is used for audit context only and never for an authorisation decision. | Running without a trusted proxy in front. | 2 h |
| TD-20 | **No soft-delete or retention policy.** Records are kept forever. | Out of scope. | Personal data accumulates indefinitely, which is in tension with data-minimisation principles (NFR-LEG-01). | A formal data protection review, or the first erasure request. | 6 h |
| TD-21 | **Coverage gaps in `seed.py` (77%).** The demo-data generator is the least-tested module. | It is a development tool, not production code on the request path. | Low: a seeding failure is loud and immediate. | If seeding ever becomes part of a production provisioning flow. | 3 h |

---

## 5. Repayment Plan

### 5.1 Release schedule

| Release | Theme | Items | Effort | Outcome |
|---|---|---|---|---|
| **v1.0.1** — before any pilot with real patients | Stop the bleeding | TD-01, TD-02, TD-12, plus the 0.5 h labelling half of TD-11 | **20.5 h** | Data survives a redeploy, schema changes are versioned, backups exist and have been restored once. **Non-negotiable: no real patient data before this ships.** |
| **v1.1** — first month of pilot | Trust and truth | TD-03, TD-06, TD-13, TD-14, TD-11 (full), TD-08 | **36 h** | Sessions can be revoked, passwords are memory-hard, CI enforces the suite, the queue updates itself, utilisation figures are actually correct. |
| **v1.2** — quarter two | Scale and rigour | TD-05, TD-07, TD-09, TD-10, TD-15 | **33 h** | Component model, shared rate limiting, automated accessibility and load testing, tamper-evident audit. |
| **v2.0** — as scale demands | Reach | TD-16, TD-17, TD-18, TD-20 as triggers fire | **29 h** | Multi-region, multi-clinic, notifications, retention policy. |

### 5.2 Ordering rationale

The order is not by size or by ease. It follows three rules:

1. **Irreversible loss first.** TD-01 and TD-12 protect data that, once gone, cannot be recovered by any later work. Everything else can be fixed after the fact; lost bookings cannot.
2. **Enabling debt before dependent debt.** TD-02 (migrations) must land *before* TD-11 and TD-04, which both need schema changes. Repaying them in the wrong order means doing the schema change twice — once by hand, once properly.
3. **Compounding before stepping.** TD-14 (stale queue) is repaid early despite being a pure quality-of-experience item, because it degrades the system's central promise and will therefore dominate pilot feedback. TD-15 (duplication) is repaid late because its interest is genuinely near zero.

### 5.3 Governance

- The register is reviewed at every release boundary. Items are added, re-scored or closed; nothing is silently dropped.
- **New debt must be logged in the same commit that creates it**, with cause, impact and a proposed resolution. Debt taken without a record is the only kind that is not allowed.
- Each release reserves **20% of its capacity** for repayment. Without a standing allocation, debt work loses every argument against feature work, indefinitely.
- An item that has been deferred three times is escalated: either it is genuinely ACCEPTABLE and should be reclassified honestly, or it is being avoided.

### 5.4 What was deliberately *not* treated as debt

Three things could be mistaken for debt and are not:

- **The deferred use cases (FR-59 to FR-67).** Rescheduling, reminders, multi-tenancy and the rest are *unbuilt features*, recorded in the evolution roadmap. Calling missing functionality "debt" inflates the register and hides the real items.
- **The absence of an EMR.** A deliberate scope boundary (constraint C-06), not a shortfall.
- **The 93% coverage figure rather than 100%.** The uncovered lines are defensive branches and error paths whose cost of testing exceeds their risk. Chasing 100% would be theatre.

---

## 6. Summary

| Question | Answer |
|---|---|
| Items identified | 18 |
| Identified before implementation | 6 (System Design §8) |
| Caused directly by effort-estimate pressure | 4 (Effort Estimation §4.2 — M1, M2, M3, M6) |
| Found during testing | 2 (TD-03 session revocation; TD-14's 503 handling, from the performance run) |
| Critical | 3 — TD-01, TD-02, TD-03 |
| Total principal | 130 h, of which 84 h is critical or scheduled |
| Ratio of repayment to build | 1.75 : 1 |
| Hard gate | **No real patient data until v1.0.1 (TD-01, TD-02, TD-12) has shipped.** |

The register's purpose is not to make the project look thorough. It is to ensure that the person who maintains this system in six months — probably the same person, with no memory of these decisions — finds out *why* each shortcut exists and *what it will cost* before they are surprised by it in production.

*End of Technical Debt Register and Repayment Plan v1.0.*
