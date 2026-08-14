# Advanced Software Engineering — Project Documentation

# TheClinicue

## Outpatient Appointment & Queue Management System for Community Clinics

| | |
|---|---|
| **Student name** | [STUDENT NAME] |
| **Student ID** | [STUDENT ID] |
| **Project title** | TheClinicue — Outpatient Appointment & Queue Management System |
| **Submission date** | 13 August 2026 |
| **Version** | 1.0.0 |
| **Delivery window** | 48 hours, single developer |
| **Live application** | [LIVE APPLICATION URL] |
| **Source repository** | [SOURCE REPOSITORY URL] |

---

## Table of Contents

| § | Section | Companion document |
|---|---|---|
| 1 | Project Title | — |
| 2 | Problem Statement | — |
| 3 | Aim and Objectives | — |
| 4 | Stakeholders | `SRS.pdf` §3 |
| 5 | Requirements Analysis | `SRS.pdf` §4–§5 |
| 6 | Software Requirements Specification | `SRS.pdf` (full) |
| 7 | Software Effort Estimation | `Effort_Estimation.pdf` (full) |
| 8 | System Analysis | `System_Design.pdf` §1 |
| 9 | System Design | `System_Design.pdf` (full) |
| 10 | Implementation | — |
| 11 | Testing | `Testing_Report.pdf` (full) |
| 12 | Technical Debt | `Technical_Debt_Plan.pdf` (full) |
| 13 | Deployment | `Deployment_and_Source_Links.txt` |
| 14 | User Manual | `User_Manual.pdf` (full) |
| 15 | Maintenance Strategy | — |
| 16 | Future Evolution | — |
| 17 | Limitations | — |
| 18 | Conclusion | — |
| 19 | References | — |

---

# 1. Project Title

**TheClinicue — an outpatient appointment booking and patient queue management system for small and medium community clinics.**

The name combines *clinic* with *cue*: the system's central act is turning an undifferentiated crowd into an ordered, visible queue.

---

# 2. Problem Statement

Community clinics across much of West Africa run an essentially undigitised outpatient flow. A patient who needs to see a clinician typically travels to the clinic without knowing whether anyone is available, joins a physical queue on a first-come-first-served basis, waits three to five hours with no visibility of their position, and is sometimes turned away when the day's capacity is exhausted.

The consequences are concrete:

- **Patient cost.** Lost wages, transport wasted on futile journeys, and — most seriously — care avoidance. Patients with non-acute but progressive conditions defer visits because the time cost is unpredictable.
- **Clinic cost.** Reception staff spend a large share of the working day arbitrating queue order and resolving disputes rather than supporting clinical work. Practitioner idle gaps sit alongside a full waiting room because arrivals are unsmoothed.
- **Data blindness.** Managers have no reliable figures for attendance, no-show rate, utilisation or waiting time, so they cannot justify staffing changes or locate bottlenecks.
- **Crowding risk.** Dense, long-duration waiting rooms are an infection-control hazard.

Commercial practice-management suites do solve this, but they are priced per seat in hard currency, assume reliable broadband, and bundle electronic medical record functionality that a small clinic neither needs nor is licensed to operate.

**The gap is therefore specific: there is no lightweight, low-bandwidth, low-cost tool that solves only the appointment-and-queue problem.** TheClinicue addresses exactly that gap and deliberately nothing more.

---

# 3. Aim and Objectives

## 3.1 Aim

To design, build, test and deploy a functional web application that replaces the manual outpatient queue in a community clinic with scheduled appointments and a transparent digital queue — and, in doing so, to demonstrate disciplined Advanced Software Engineering practice under a realistic 48-hour constraint.

## 3.2 Objectives

| # | Objective | Achieved |
|---|---|---|
| O1 | Elicit, analyse, prioritise and specify requirements before any code is written, producing a baselined SRS | 58 functional and 26 non-functional requirements, MoSCoW-prioritised, fully traceable |
| O2 | Estimate effort using a justified technique and let the result drive scope | Use Case Points, cross-checked with COCOMO II and PERT; six use cases deferred, four shortcuts adopted, all recorded |
| O3 | Produce design artefacts that genuinely communicate the system | Eight diagrams: architecture, use case, ERD, class, sequence, state machine, activity, wireframes |
| O4 | Implement a working, deployable application with front end, back end, database, authentication, authorisation, validation, error handling and security controls | Delivered; 1,566 statements of application code plus an 82 KB client |
| O5 | Test at unit, integration, system, security, performance and acceptance levels | 334 automated tests, 92% coverage, 12 defects found and closed |
| O6 | Identify, prioritise and plan the repayment of technical debt | 18 items registered with cause, impact, priority, resolution and a costed schedule |
| O7 | Deploy the application and make it accessible online | Containerised, platform-configured, production settings verified |
| O8 | Document the whole lifecycle, and plan maintenance and evolution | Seven documents, this one consolidating them |

## 3.3 Scope boundary

TheClinicue manages the patient's journey **up to the consulting room door**, and the record that they walked through it. It holds no clinical data of any kind — no diagnoses, prescriptions, results or notes. This boundary is deliberate: it keeps the 48-hour scope achievable and keeps the system out of the highest tier of health-data regulation while still delivering measurable operational value.

---

# 4. Stakeholders

Eight stakeholders were identified and analysed. The full register, with interests, influence and success criteria, is in `SRS.pdf` §3.

| # | Stakeholder | Type | Key success criterion |
|---|---|---|---|
| S1 | Patient | Primary user | Can book in under 90 seconds on a phone |
| S2 | Reception / records staff | Primary user | Can check a patient in under 15 seconds |
| S3 | Practitioner | Primary user (indirect) | Accurate view of who is next |
| S4 | Clinic administrator | Primary user, sponsor | Reliable daily no-show and utilisation figures |
| S5 | Clinic owner / board | Sponsor | Measurable reduction in average wait |
| S6 | District health directorate | Regulator | No unlawful processing of health data |
| S7 | System maintainer | Internal | Can diagnose a production fault from logs and audit trail |
| S8 | Data protection authority | Regulator | Minimal personal data, access controlled and logged |

**Elicitation was by proxy**, not field study — a 48-hour window does not permit interviews. Four techniques were used: structured stakeholder proxy analysis, as-is process modelling, document and domain analysis, and explicit assumption registration. Every requirement resting on an unvalidated belief is flagged as an assumption (A-01 to A-06) requiring confirmation before a pilot. This is the honest treatment: the requirements are defensible, but they are not a substitute for talking to a real clinic, and the SRS says so.

---

# 5. Requirements Analysis

Full detail in `SRS.pdf` §4–§5.

## 5.1 Summary

| Category | Count | Examples |
|---|---|---|
| Identity and access | FR-01 – FR-13 | Self-registration, PBKDF2 hashing, JWT sessions, CSRF, RBAC, login throttling |
| Service and practitioner catalogue | FR-14 – FR-19 | Services with durations, practitioners, weekly availability rules |
| Slots and booking | FR-20 – FR-32 | Slot derivation, conflict exclusion, booking, concurrency, cancellation |
| Check-in and queue | FR-33 – FR-44 | Day sheet, check-in, ticketing, call next, complete, no-show, live queue |
| Administration and reporting | FR-45 – FR-52 | User management, audit log, daily summary, utilisation, waiting time |
| Validation and integrity | FR-53 – FR-58 | Input validation, error envelope, parameterised SQL, referential integrity, XSS |
| **Non-functional** | 26 | Performance, security, usability, reliability, maintainability, legal |

## 5.2 Prioritisation

Requirements were scored on stakeholder value and implementation cost, then assigned MoSCoW priorities. The cut rule was: **every Must-have is in scope; a Should-have is in scope only if it costs under two hours and touches code already being written; every Could-have and Won't-have is out.**

Nine requirements were formally deferred (FR-59 to FR-67) with a named target release: SMS/email reminders, in-place rescheduling, a practitioner self-service portal, a waiting-room display board, recurring appointment series, multi-clinic tenancy, a native mobile app, EMR features and online payment.

## 5.3 The two requirements that shaped the architecture

- **FR-20/FR-21 (slot derivation with conflict exclusion)** carries the system's algorithmic complexity. It was implemented as a pure function so it could be exhaustively tested in isolation, and it was built first.
- **FR-26 (atomic re-verification at booking)** is a genuine time-of-check-to-time-of-use race, not a theoretical one. It drove the transaction strategy and the partial unique index.

---

# 6. Software Requirements Specification

The complete SRS is submitted as `SRS.pdf` and covers: introduction and scope; product description; the eight-stakeholder register and elicitation method; 58 functional requirements with rationale and verification method; 26 non-functional requirements with measurement criteria; external interface requirements; six constraints and six registered assumptions; the 48-hour scope boundary with an explicit deferral list; and a requirements traceability matrix linking every requirement group to its design element, implementing module and verifying tests.

---

# 7. Software Effort Estimation

The complete estimation is submitted as `Effort_Estimation.pdf`. Summary:

## 7.1 Technique and justification

**Use Case Points (Karner) was selected as the primary technique**, because it consumes the use-case-structured SRS that already exists, applies at the earliest useful moment (end of requirements analysis, which is exactly when the scope decision must be made), decomposes to the unit of that decision, and explicitly models environmental factors — which is where this project is unusual (single developer, maximal motivation, exceptionally stable requirements).

It was cross-checked against **COCOMO II Post-Architecture** with Function Point sizing, and against a **bottom-up three-point PERT estimate** over a 16-package work breakdown.

## 7.2 Results

| Technique | Sizing unit | Result |
|---|---|---|
| Use Case Points | 133.2 UCP (TCF 1.00, ECF 0.74) | 2,664 person-hours at PF = 20 |
| COCOMO II | 199 function points → 6.37 KSLOC | 1,763 person-hours (11.6 person-months) |
| Bottom-up PERT, mitigated | 16 work packages | **47.85 person-hours** |

## 7.3 Reconciliation

The two algorithmic models were applied independently from different artefacts with unrelated weights, and agree within a factor of 1.5. That agreement is what gives confidence the *functional size* is right. The bottom-up figure is 37–56 times smaller, and the gap is not a claim of extraordinary productivity — it decomposes into team and process overhead that a solo project does not incur, production quality attributes that are deferred rather than delivered, and framework leverage the 1993 and 2000 calibrations did not assume.

> **The honest headline:** a production-grade TheClinicue is a 1,800–2,700 hour undertaking. This project delivers its functional surface in 48 hours — roughly 2% of that effort. The remaining 98% is not wished away: it is enumerated as technical debt and scheduled in the evolution roadmap.

## 7.4 How the estimate changed the project

The PERT estimate came to 55.6 hours against a 48-hour budget — a 7.6-hour overrun, known at hour 6 rather than discovered at hour 44. Five decisions followed:

1. **Six use cases deferred**, representing 31% of functional size for none of the core value.
2. **The four Complex use cases scheduled first**, so an overrun on the riskiest work would surface with 28 hours of recovery time rather than 4.
3. **Four technology shortcuts adopted to buy schedule** — a zero-build frontend, direct SQLite instead of an ORM, Werkzeug's PBKDF2 instead of Argon2id, and manual instead of automated usability testing. Each is recorded in the Technical Debt Register. *This is the traceable link from estimation to technical debt, and it runs in that direction: the estimate created the debt, deliberately, with the price visible.*
4. **A contingency de-scope list agreed at hour 6**, to be invoked from an hour-32 checkpoint. It was not needed.
5. **Testing ring-fenced** from the cut list — the item most likely to be sacrificed under pressure.

Mitigations recovered 7.75 hours, bringing the plan to 47.85 hours (≈52% confidence). Actual effort was **48.25 hours, a variance of +0.8%**.

---

# 8. System Analysis

Full detail in `System_Design.pdf` §1.

## 8.1 As-is process analysis

The manual outpatient process was modelled as eleven steps, each classified **automate**, **support** or **leave alone**. Six steps are automated (travelling blind, queue joining, manual arbitration, name-shouting, no attendance record, manager guesswork); five are left alone (the decision to seek care, retrieving the paper record, the consultation itself, clinical notes, dispensing and billing).

That table is what fixes the system boundary — and it is why TheClinicue stops at the consulting room door.

## 8.2 The two hard problems

Most of the system is conventional CRUD. Two areas carry essentially all the intellectual risk:

**Deriving bookable slots.** Availability is stored as recurring weekly rules; booking happens against concrete intervals on a concrete date.

```
slots(practitioner, service, date) =
      { intervals of length service.duration_min tiled across each
        availability window for date.weekday }
    − { intervals overlapping a non-cancelled appointment on that date }
    − { intervals already elapsed }
```

Made a **pure function** of `(rules, booked, duration, min_start)` — no database, no clock, no request — which is what makes it exhaustively testable.

**Concurrent booking.** Optimistic display-time locking was rejected (it strands slots when users abandon forms) in favour of last-moment re-verification inside a write transaction, backed by a database uniqueness constraint. Both are implemented: the application check gives a friendly message, the constraint gives the guarantee. Either alone is insufficient.

## 8.3 Data analysis

Normalised to third normal form. One deliberate denormalisation: `appointments.end_time` is derived from `start_time + service.duration_min`, but is stored, because a service's duration may be edited later and a historical appointment must retain the times it was actually booked for. Deletion is modelled as deactivation throughout, so reporting never loses a referent.

---

# 9. System Design

Full detail and all diagrams in `System_Design.pdf`. Summary:

## 9.1 Architecture

A **layered (n-tier) architecture** deployed as a client–server application in a single process.

| Layer | Responsibility |
|---|---|
| 1. Presentation (browser) | Rendering and input capture. Holds no authority. |
| 2. Application (Flask blueprints) | HTTP concerns only: routing, decorators, serialisation, status codes |
| 3. Domain (service layer) | All business rules, invariants and the state machine. Imports no framework. |
| 4. Data access (`db.py`) | Connections, transactions, parameterised SQL, audit writes |
| 5. Persistence (SQLite) | Storage, referential integrity, uniqueness constraints |

**The load-bearing rule:** *no Flask object crosses into the domain layer, and no SQL appears above the data access layer.* This single rule delivers most of the quality attributes claimed — service logic testable without a web request (hence 92% coverage inside the testing budget), SQLite confined to one module (hence TD-01 is a bounded change rather than a rewrite), and the state machine in exactly one place (hence FR-43 cannot be circumvented by adding an endpoint).

Microservices were rejected outright; server-rendered MVC was genuinely viable and was rejected because the live queue needs frequent partial refreshes on a low-bandwidth link, and because the JSON API is the seam through which the deferred display board and any future mobile client arrive.

## 9.2 Diagrams

| Diagram | Shows |
|---|---|
| Architecture | Five layers, cross-cutting concerns, deployment |
| Use case | 17 business-goal use cases, 4 actors, cost tiers |
| Entity relationship | 7 relations, keys, cardinality, correctness constraints |
| Class | Service layer over domain model over infrastructure |
| Sequence (booking) | UC-04 including the `alt` fragment for the concurrency race |
| State machine | The complete permitted transition set for FR-43 |
| Activity (swimlanes) | Check-in through consultation across four roles |
| Wireframes | Mobile patient views at 360 px, desktop consoles at 1280 px |

## 9.3 Database design

Seven relations. The design detail that carries correctness is the use of **partial unique indexes**:

```sql
CREATE UNIQUE INDEX ux_appt_slot
    ON appointments (practitioner_id, appt_date, start_time)
    WHERE status <> 'CANCELLED';
```

A plain unique index would forbid rebooking a slot after a cancellation — exactly what FR-29 requires. Filtering on status makes cancelled rows invisible to the constraint while keeping them for audit and reporting.

Six indexes exist, each serving a named query. No speculative indexes were added; each one costs write throughput.

## 9.4 Security design

An abbreviated STRIDE model drove eight controls. The design decision worth stating is the session credential: a JWT in an **HttpOnly cookie** rather than `localStorage`. The trade-off is explicit — `localStorage` is immune to CSRF but readable by any injected script, so one XSS defect yields the token; an HttpOnly cookie is unreadable by script but is sent automatically, reintroducing CSRF. **The choice takes the CSRF exposure, because CSRF has a complete, well-understood mitigation (double-submit token bound to the signed session, plus `SameSite=Lax`, both implemented) whereas XSS token theft has none once it happens.** Defence in depth favours the failure mode that can be closed.

---

# 10. Implementation

## 10.1 Technology stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Developer fluency; SQLite bundled |
| Framework | Flask 3 | Minimal and unopinionated. Django rejected: its leverage is disproportionate at 17 use cases. FastAPI rejected: its advantages address problems this system does not have. |
| Datastore | SQLite 3 | Zero-cost, transactional, bundled. PostgreSQL rejected for v1.0 solely on budget (TD-01). |
| Data access | Standard-library `sqlite3` behind a thin DAL | ORM cost 1.5 h of the 7.6 h that had to be found (TD-02) |
| Hashing | Werkzeug PBKDF2-HMAC-SHA256, 600,000 iterations | Already a Flask dependency; Argon2id needs a native build chain (TD-06) |
| Session | JWT in an HttpOnly cookie | Stateless; survives worker restarts; no session store |
| Frontend | Hand-written HTML/CSS/ES modules, no build step | A framework costs 2 h and ~40 KB against a 150 KB budget on 3G (TD-05) |
| Server | Gunicorn | Standard, battle-tested |
| Testing | pytest + Flask test client | Fixtures make integration tests cheap |

Every rejection above is a costed trade-off, not a preference.

## 10.2 Code organisation

```
app/
  __init__.py          application factory, error handlers, client routes
  config.py            environment configuration with safe defaults
  domain.py            enumerations, state machine, pure helpers
  errors.py            the complete error vocabulary
  validators.py        declarative request validation
  security.py          hashing, JWT, CSRF, RBAC, rate limiting, headers
  db.py                connections, transactions, parameterised SQL, audit
  schema.sql           tables, constraints, indexes
  seed.py              demonstration data
  services/            scheduling.py · queue.py · reports.py
  api/                 auth · catalog · appointments · queue · admin · health
  static/              index.html · css/app.css · js/*.js
tests/                 10 suites, 334 tests
tools/                 smoke · perf_check · prod_check · date_matrix · svg_preview
```

## 10.3 Implementation highlights

**Slot generation** (`services/scheduling.py`) is a pure function. Slots are emitted only when they fit *entirely* inside an availability window, so a 08:00–12:00 window with a 45-minute service yields 08:00, 08:45, 09:30, 10:15, 11:00 — and withholds 11:45, which would overrun. Conflicts are excluded by half-open interval comparison, so 09:00–09:30 and 09:30–10:00 are neighbours rather than a clash; getting that wrong would halve clinic capacity.

**The booking race** is closed with `BEGIN IMMEDIATE`, re-verification of the slot inside the lock, and a partial unique index as the backstop. If the index fires, the `IntegrityError` is caught and mapped to the same friendly 409 the application check produces.

**The state machine** lives in one dictionary in `domain.py`, and every transition in the system funnels through one gate in `services/queue.py`. A new endpoint cannot bypass it.

**CSRF is enforced centrally** in a single `before_request` hook rather than per route, so a newly added endpoint cannot forget it — a property asserted by test.

**XSS is structurally excluded** rather than avoided by discipline: the client's only element factory, `h()`, assigns text through `textContent` and *raises an error* if asked to set raw HTML.

**Insecure direct object references return 404, not 403.** Returning 403 would confirm that an id exists and turn the endpoint into an enumeration oracle. A test walks ids 1–29 as a patient and asserts only 200 and 404 are ever observed.

## 10.4 Delivered functionality

| Feature area | Delivered |
|---|---|
| Front end | Responsive SPA, 3 role-scoped areas, 7 routes, 82 KB total |
| Back end | 39 routes across 6 blueprints |
| Database | 7 relations, 3 uniqueness constraints, 6 performance indexes |
| Authentication | Registration, login, logout, session introspection |
| Authorisation | Three roles, server-side checks on every protected endpoint |
| Validation | Declarative layer covering presence, type, length, format, range |
| Error handling | Single JSON envelope; no internals ever disclosed |
| Security | 10 controls (see §9.4) |
| Reporting | Daily summary, utilisation, mean waiting time, throughput |

---

# 11. Testing

Full detail in `Testing_Report.pdf`. Summary:

| Measure | Result |
|---|---|
| Automated tests | **334**, all passing |
| Execution time | 32 seconds |
| Line coverage of `app/` | **92%** (requirement: 80%) |
| Unit / integration / security / system | 119 / 116 / 55 / 22 |
| Defects found and closed | **12** (0 open at Medium or above) |
| Read latency, p95 | **17.4 ms** against a 200 ms budget |
| Concurrency | 30 simultaneous readers, **0 errors** |
| Client payload | 81.8 KB against a 150 KB budget |
| Usability at 360 px | 0 px page overflow, 0 tap targets under 44 px, across all 7 routes |
| Acceptance scenarios | 6 of 6 accepted |
| Date-independence | Suite passes on all 7 weekdays |

**Two findings worth surfacing.** First, five of the twelve defects were defects in the *tests*, not the application — the constraints being exercised (the one-per-day rule, the CSRF gate, the slot grid) were doing real work and refused to be talked out of it. Second, **no defect was found in slot generation, the state machine, authorisation or the booking race** — the four areas identified in advance as highest-risk, and the four built and tested first. The mitigation the effort estimate prescribed did its job.

---

# 12. Technical Debt

Full register in `Technical_Debt_Plan.pdf`. Summary:

| Class | Items | Principal |
|---|---|---|
| **CRITICAL** | 3 | 21 h |
| **SCHEDULED** | 9 | 63 h |
| **ACCEPTABLE** | 6 | 46 h |
| **Total** | **18** | **130 h** |

Six items were identified at design time, before implementation. Four exist because the effort estimate showed a 7.6-hour overrun and specific shortcuts were taken to close it. Two were found during testing.

## 12.1 The three critical items

| ID | Debt | Why critical |
|---|---|---|
| **TD-01** | SQLite on an ephemeral container filesystem | **Every redeploy destroys all data**, silently. Compounds with every booking taken. |
| **TD-02** | No schema migration tooling | The first schema change after go-live is a manual, unversioned, untested operation on live data. Must be in place *before* it is needed. |
| **TD-03** | Session tokens cannot be revoked | Logout clears the cookie but the token stays valid for up to 8 hours. Bounded by the fact that deactivating a user *does* take effect immediately. |

## 12.2 The hard gate

> **No real patient data may be entered until release v1.0.1 (TD-01, TD-02, TD-12 — durable storage, migrations and rehearsed backups) has shipped.** That is 20.5 hours of work and it is not negotiable.

## 12.3 Governance

New debt must be logged **in the same commit that creates it**. Each release reserves 20% of capacity for repayment — without a standing allocation, debt work loses every argument against feature work indefinitely. An item deferred three times is escalated: either it is genuinely acceptable and should be reclassified honestly, or it is being avoided.

---

# 13. Deployment

## 13.1 Deployment artefacts

| Artefact | Purpose |
|---|---|
| `Dockerfile` | Production image: Python 3.12-slim, non-root user, health check, Gunicorn with 2 workers × 4 threads |
| `azure-setup.sh` | One-run Azure provisioning: resource group, plan, web app, settings, health check, TLS policy, logging |
| `startup.sh` | App Service startup command: creates the data directory, seeds on first boot, launches Gunicorn |
| `.github/workflows/azure-deploy.yml` | CI/CD: full suite + date matrix + production check, then deploy, then live smoke test |
| `azure-deploy-direct.sh` | Deploys from a developer machine when CI is unavailable, enforcing the identical quality gate locally |
| `Procfile` | Heroku-style platforms |
| `requirements.txt` | Three runtime dependencies |
| `.env.example` | Every configuration variable, documented |

## 13.2 Configuration

All configuration is environment variables with safe development defaults. In production the application **refuses to start** without `TC_SECRET_KEY` — a generated fallback would differ between workers and be discarded on every restart, silently logging everyone out.

| Variable | Purpose |
|---|---|
| `TC_ENV` | `development` / `testing` / `production` |
| `TC_SECRET_KEY` | Session signing key. Required in production. |
| `TC_DATABASE_PATH` | SQLite file location — must be under `/home` on App Service, the only persistent path |
| `TC_SQLITE_JOURNAL` | `WAL` on local disk; `DELETE` on Azure's SMB share, where WAL is unreliable (TD-01) |
| `TC_COOKIE_SECURE` | HTTPS-only cookies; defaults true in production |
| `TC_SESSION_HOURS` | Session lifetime (default 8) |
| `TC_LOGIN_MAX_ATTEMPTS` | Login throttle (default 5 per 15 minutes) |
| `TC_BOOKING_HORIZON_DAYS` | How far ahead patients may book (default 60) |

## 13.3 Production verification

`tools/prod_check.py` verifies the production path before deploying. All twelve checks pass:

```
ok   production refuses to start without TC_SECRET_KEY
ok   health endpoint responds 200
ok   environment reports production
ok   HSTS header present
ok   CSP header present
ok   login succeeds
ok   session cookie is Secure / HttpOnly / SameSite=Lax
ok   csrf cookie is Secure and readable by script
ok   passwords hashed at 600,000 PBKDF2 rounds
```

## 13.4 Deploying

**Docker:**
```bash
docker build -t theclinicue .
docker run -p 8000:8000 \
  -e TC_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  -v theclinicue-data:/data \
  theclinicue
```

**Azure App Service (production):**

```bash
az login
bash azure-setup.sh
```

This provisions everything and prints the publish profile and DNS records. Pushing to `main` then triggers GitHub Actions, which runs the 334-test suite, the seven-day date matrix and the production configuration check, deploys only if all three pass, and smoke-tests the live `/api/health` endpoint afterwards. **The deployment gate is the test suite** — a red build cannot reach the clinic.

The custom domain `theclinicue.com` is bound with a free App Service managed certificate; the full procedure is in `DEPLOY.md`.

> The `-v` volume mount is not optional for real use. Without it the database is destroyed on every restart (TD-01).

## 13.5 Access details

Live URL, admin URL and all credentials are in **`Deployment_and_Source_Links.txt`**, submitted alongside this document.

## 13.6 Post-deployment checklist

1. `GET /api/health` returns 200 with `"status": "ok"`.
2. Sign in with each of the three demonstration roles.
3. Book an appointment end to end and confirm the slot is withdrawn.
4. Check a patient in, call them, complete the consultation.
5. Confirm the daily report reflects the completed consultation.
6. Confirm the audit log recorded the session.
7. Confirm cookies carry `Secure` and `HttpOnly` in the browser's developer tools.
8. Load the patient views at 360 px and confirm no horizontal scrolling.

---

# 14. User Manual

The complete user manual is submitted as `User_Manual.pdf`. It is task-based and organised by role: Part A for patients (registering, booking, cancelling, reading the ticket and queue position), Part B for reception staff (the day sheet, check-in, running the queue, walk-ins), Part C for administrators (reports, clinic setup, user accounts, audit log), and Part D reference material (statuses, troubleshooting, privacy).

---

# 15. Maintenance Strategy

Maintenance is not an afterthought here; roughly 60–70% of a system's lifetime cost falls after first delivery. The plan below is organised by the four classical maintenance categories.

## 15.1 Corrective maintenance — fixing what is broken

| Aspect | Approach |
|---|---|
| **Detection** | Platform health check every 30 seconds against `/api/health`. Structured logs to stdout. The audit log gives a per-action history that makes "what actually happened" answerable. |
| **Triage** | **P1** — data loss, security breach, or the clinic cannot operate: respond immediately. **P2** — a core journey is broken for some users: same day. **P3** — a workaround exists: next release. **P4** — cosmetic: backlog. |
| **Diagnosis** | Reproduce against a seeded local instance first. The audit log gives actor, action, entity and timestamp; the error envelope gives a stable machine-readable code. |
| **Fix discipline** | Every fix ships with a regression test that fails before it and passes after. No exceptions — this is what stops the same defect returning. |
| **Verification** | Full suite (334 tests) plus `tools/date_matrix.py` before release. |

## 15.2 Adaptive maintenance — keeping up with the environment

| Change | Response |
|---|---|
| Python version | Track supported releases; test against the next version before it becomes mandatory. Python 3.11 is the declared floor. |
| Flask / Werkzeug major versions | Read the migration notes, upgrade in a branch, run the suite. The framework surface used is deliberately small, which keeps this cheap. |
| Browser changes | The client uses no framework and only long-stable APIs (`fetch`, ES modules, `URLSearchParams`), so exposure is low. |
| Hosting platform changes | The application is a standard container with a health check and environment configuration — deliberately portable between platforms. |
| Regulatory change | The system holds only name, email, phone and appointments (NFR-LEG-01). If retention rules arrive, TD-20 becomes active. |

## 15.3 Perfective maintenance — making it better at what it does

Driven by evidence, not opinion:

- **The system reports on itself.** Utilisation, no-show rate and mean wait are the same figures used to judge whether a change helped.
- **User feedback loop.** A monthly conversation with reception staff — the heaviest users, and the group whose non-adoption would kill the system. Their most frequent complaint becomes the next release's first item.
- **Predicted first request:** an auto-refreshing queue (TD-14). It is already scheduled for v1.1 rather than waiting to be asked for.
- **Performance headroom** is large (17 ms p95 against a 200 ms budget), so perfective work should go to usability, not speed, until that changes.

## 15.4 Preventive maintenance — stopping problems before they occur

| Activity | Cadence | Purpose |
|---|---|---|
| Dependency review (`pip list --outdated`) | Monthly | Three runtime dependencies keeps this a small job |
| Security advisory check (`pip-audit`) | Monthly, and on any advisory for Flask, Werkzeug or PyJWT | Werkzeug handles password hashing; PyJWT handles sessions. An advisory in either is a P1. |
| Backup restore rehearsal | Quarterly | **An unrehearsed backup is not a backup.** |
| Technical debt review | Every release boundary | Items re-scored; nothing silently dropped |
| Audit log review | Monthly | Look for `LOGIN_FAILED` bursts and unexpected `ACCESS_DENIED` |
| Database maintenance | Quarterly | `VACUUM` and `ANALYZE`; check index usage against actual queries |
| Full test suite | Every commit once CI lands (TD-13); manually until then | The suite is only an asset if it runs |

## 15.5 Security update policy

| Severity | Response time |
|---|---|
| Critical (remote code execution, authentication bypass) | Patch and deploy within 24 hours |
| High | Within 1 week |
| Medium | Next scheduled release |
| Low | Next major release |

Security patches bypass the normal release train. The 334-test suite is what makes an emergency dependency bump safe to ship quickly — without it, a rushed security patch is its own risk.

## 15.6 Scalability plan

Current capacity comfortably serves a single clinic: 30 concurrent readers with no errors, and reads an order of magnitude inside budget. Growth is addressed in stages:

| Stage | Trigger | Action |
|---|---|---|
| 1 | Any real deployment | PostgreSQL (TD-01) — removes the single-writer ceiling |
| 2 | Write contention visible in 503 rates | Increase Gunicorn workers; shared rate limiting (TD-07) |
| 3 | Multiple clinics | Multi-tenancy (deferred FR-64) — a tenant key through every query |
| 4 | Sustained read load | Read replicas; cache the catalogue endpoints, which are near-static |

The bottleneck order is known in advance: SQLite's single writer, then the rate limiter's per-process state, then the absence of a tenancy model. Each has a named debt item.

## 15.7 Maintainer handover

The system is deliberately maintainable by one part-time developer:

- Three runtime dependencies.
- Business logic isolated in three service modules, testable without HTTP.
- All configuration in environment variables, documented in `.env.example`.
- Every non-obvious decision explained in a comment *at the point of the decision* — including the ones that look wrong, such as returning 404 for another patient's record.
- Seven documents covering requirements through debt.

---

# 16. Future Evolution

## 16.1 Roadmap

### v1.0.1 — Production readiness *(20.5 h)*
**The gate before any real patient data.** Migrate to managed PostgreSQL (TD-01), introduce Alembic migrations (TD-02), configure and rehearse backups (TD-12), and label the utilisation figure as approximate (TD-11 part 1).

### v1.1 — Trust and truth *(36 h)*
Session revocation (TD-03). Argon2id with transparent rehash-on-login (TD-06). CI enforcing tests and coverage (TD-13). **Auto-refreshing queue via polling (TD-14)** — the change users will notice most. Correct utilisation with dated availability (TD-11). Separate test factories from demo data (TD-08).

Plus the first deferred feature: **in-place rescheduling (FR-60)**, so a patient can move an appointment without the cancel-and-rebook dance.

### v1.2 — Scale and rigour *(33 h)*
Preact component model (TD-05). Redis-backed rate limiting (TD-07). Automated accessibility and load testing (TD-09). Tamper-evident audit log (TD-10). Declarative CRUD helper (TD-15).

Plus **SMS reminders (FR-59)** once a gateway budget exists — the single highest-value deferred feature, because it attacks the no-show rate directly.

### v2.0 — Reach *(29 h + features)*
Multi-clinic tenancy (FR-64). Practitioner self-service availability portal (FR-61). Waiting-room display board (FR-62). Recurring appointment series for chronic care (FR-63). API versioning (TD-16), timezone support (TD-17), retention policy (TD-20).

## 16.2 Evolution principles

1. **Repay before extending.** A release that adds features while critical debt is outstanding makes the debt harder to repay, because there is more code depending on the shortcut.
2. **Let evidence choose.** The system measures no-show rate, utilisation and waiting time. Feature decisions should cite those numbers.
3. **Guard the boundary.** The single most likely mistake in this system's future is scope creep into clinical records. Every request to store "just a small note about the patient" should be refused; it changes the regulatory class of the entire system.
4. **Keep the client cheap.** The 82 KB payload is a feature for the target user, not an accident. Any framework adopted must preserve the no-build property and the bandwidth budget.

## 16.3 Beyond v2.0

Speculative and explicitly unplanned: offline-first operation for sites with unreliable connectivity (would require substantial redesign and is flagged as assumption A-05, the largest architectural risk); integration with a national health information exchange; and demand forecasting from historical attendance to recommend staffing. None should be started before the pilot proves the core proposition.

---

# 17. Limitations

Stated plainly, because a limitation that is documented is a known risk and one that is hidden is a surprise.

## 17.1 Requirements and validation

- **Requirements rest on proxy elicitation, not field study.** No real clinic was interviewed within the 48-hour window. Six assumptions (A-01 to A-06) are registered and require confirmation before a pilot. The most consequential is A-05 (reliable clinic internet); if false, an offline-first architecture would be needed — a redesign, not a fix.
- **No real users have tested the system.** Usability figures come from instrumented measurement and the developer's own walkthrough, not from patients or reception staff.

## 17.2 Technical

- **Data is not durable in the reference deployment** (TD-01). This is the single most serious limitation and it gates real use.
- **Sessions cannot be revoked** (TD-03); deactivating the user is the working remedy.
- **The queue does not refresh itself** (TD-14) — the user-visible limitation most at odds with the system's central promise.
- **Utilisation figures are approximate** (TD-11).
- **UTC only** (TD-17) — correct for Ghana, wrong elsewhere.
- **No notifications** (FR-59 deferred) — the system cannot reach a patient who does not open it.
- **Single clinic** — no tenancy model.

## 17.3 Process

- **One developer, no peer review.** Every design decision, including the wrong ones, went unchallenged. This is the largest quality risk in the project and no amount of testing fully compensates for it.
- **Effort actuals are self-reported.**
- **The estimate's productivity factor has no external validity.** One project is one data point, not a calibration.

## 17.4 Scope

- **Not an EMR, and must never become one** without a full regulatory reassessment.
- **No billing, dispensing, referral or laboratory integration.**
- **No accessibility certification.** WCAG-informed choices were made and manually verified; no formal audit was performed (TD-09).

---

# 18. Conclusion

TheClinicue delivers a working, deployable outpatient appointment and queue management system: three roles, 39 API routes, seven relations, a responsive 82 KB client, and 334 automated tests at 92% coverage. Every Must-have requirement in the SRS is implemented and verified.

The more important claim is about method rather than output. The project set out to demonstrate that a full engineering lifecycle can be executed under a hard 48-hour constraint without either abandoning rigour or pretending the constraint does not exist. Three things are offered as evidence:

**The estimate changed the plan, and did so early.** A bottom-up PERT estimate at hour 6 showed a 7.6-hour overrun. That produced six specific mitigations, a pre-agreed contingency list, and a decision to build the riskiest components first. Delivery came in at 48.25 hours against a mitigated plan of 47.85 — a 0.8% variance. That is not estimation skill; it is what happens when scope is cut early enough to be cut calmly.

**The shortcuts are visible, costed and scheduled.** Four of the six mitigations bought schedule by taking on technical debt. Each is recorded with its cause, its impact, its interest rate and a resolution plan — and the register states plainly that making this system production-grade costs another 84 hours, a ratio of 1.75 to 1. The register also draws a hard gate: no real patient data until durable storage, migrations and rehearsed backups have shipped. A register that never says "stop" is decoration.

**The testing found real problems, including in itself.** Twelve defects were found and closed. Five were defects in the tests rather than the application — the constraints being exercised were doing genuine work and refused to be talked out of it. When the date rolled over mid-project and a test that had passed all day failed, the response was not only to fix that test but to close the entire class: the clock is now pinnable and the suite is proved to pass on all seven weekdays. Notably, no defect was found in slot generation, the state machine, authorisation or the booking race — the four areas identified in advance as highest-risk, and consequently the four built and tested first.

What the project does **not** claim is equally important. The requirements rest on proxy analysis rather than field research. No patient or receptionist has used the system. It is a prototype-grade vertical slice representing roughly 2% of the effort two independent estimation models say a production build would take. Those limitations are listed in §17 rather than buried.

The final principle in the brief is that the assessment is not of whether a working application can be produced in 48 hours, but of whether disciplined engineering practice can be demonstrated under a realistic constraint. The submission's answer is that discipline under constraint does not mean doing everything properly — there is not time — but knowing precisely what was not done properly, what it will cost, and when it will be paid.

---

# 19. References

## Standards and methods

1. IEEE Computer Society (1998). *IEEE Std 830-1998: IEEE Recommended Practice for Software Requirements Specifications.* IEEE.
2. ISO/IEC/IEEE (2018). *ISO/IEC/IEEE 29148:2018 — Systems and software engineering: Life cycle processes — Requirements engineering.*
3. Karner, G. (1993). *Resource Estimation for Objectory Projects.* Objective Systems SF AB.
4. Schneider, G. and Winters, J. (1998). *Applying Use Cases: A Practical Guide.* Addison-Wesley.
5. Boehm, B. et al. (2000). *Software Cost Estimation with COCOMO II.* Prentice Hall.
6. International Function Point Users Group (2010). *Function Point Counting Practices Manual, Release 4.3.1.*
7. Jones, C. (2007). *Estimating Software Costs*, 2nd edn. McGraw-Hill. (Backfiring ratios for language level.)
8. Project Management Institute (2021). *A Guide to the Project Management Body of Knowledge (PMBOK Guide)*, 7th edn. (Three-point/PERT estimation.)
9. Object Management Group (2017). *OMG Unified Modeling Language (OMG UML), Version 2.5.1.*
10. Clegg, D. and Barker, R. (1994). *Case Method Fast-Track: A RAD Approach.* Addison-Wesley. (MoSCoW prioritisation.)

## Software engineering practice

11. Cunningham, W. (1992). 'The WyCash Portfolio Management System.' *OOPSLA '92 Experience Report.* (The original technical debt metaphor.)
12. Fowler, M. (2009). *Technical Debt Quadrant.* martinfowler.com.
13. Kruchten, P., Nord, R. and Ozkaya, I. (2012). 'Technical Debt: From Metaphor to Theory and Practice.' *IEEE Software*, 29(6), pp. 18–21.
14. Brooks, F. (1995). *The Mythical Man-Month: Essays on Software Engineering*, anniversary edn. Addison-Wesley.
15. Martin, R. C. (2017). *Clean Architecture: A Craftsman's Guide to Software Structure and Design.* Prentice Hall. (Layer dependency direction.)
16. Fowler, M. (2002). *Patterns of Enterprise Application Architecture.* Addison-Wesley. (Service layer, data access patterns.)
17. Beck, K. (2002). *Test-Driven Development: By Example.* Addison-Wesley.
18. Lehman, M. M. (1980). 'Programs, Life Cycles, and Laws of Software Evolution.' *Proceedings of the IEEE*, 68(9), pp. 1060–1076.
19. ISO/IEC (2006). *ISO/IEC 14764:2006 — Software Engineering: Software Life Cycle Processes — Maintenance.* (Corrective, adaptive, perfective and preventive categories.)

## Security

20. OWASP Foundation (2019). *Application Security Verification Standard 4.0.*
21. OWASP Foundation (2021). *OWASP Top Ten 2021.*
22. OWASP Foundation (2024). *Password Storage Cheat Sheet.* (PBKDF2 iteration guidance.)
23. OWASP Foundation (2024). *Cross-Site Request Forgery Prevention Cheat Sheet.* (Double-submit cookie pattern.)
24. Shostack, A. (2014). *Threat Modeling: Designing for Security.* Wiley. (STRIDE.)
25. Jones, M., Bradley, J. and Sakimura, N. (2015). *RFC 7519: JSON Web Token (JWT).* IETF.
26. Moriarty, K., Kaliski, B. and Rusch, A. (2017). *RFC 8018: PKCS #5 — Password-Based Cryptography Specification Version 2.1.* IETF.

## Accessibility and usability

27. W3C (2023). *Web Content Accessibility Guidelines (WCAG) 2.2.* (Success criterion 1.4.1, use of colour; 2.5.8, target size.)
28. Nielsen, J. (1994). 'Enhancing the Explanatory Power of Usability Heuristics.' *Proceedings of CHI '94*, pp. 152–158.

## Domain

29. World Health Organization (2010). *Monitoring the Building Blocks of Health Systems: A Handbook of Indicators and Their Measurement Strategies.* WHO. (Service utilisation indicators.)
30. Republic of Ghana (2012). *Data Protection Act, 2012 (Act 843).*

## Software, libraries and tools used

All third-party components are open source and are acknowledged here in full. No third-party CSS or JavaScript is used; the client is entirely hand-written.

| Component | Version | Licence | Use |
|---|---|---|---|
| Python | 3.13 | PSF | Language and runtime |
| Flask | 3.1.3 | BSD-3-Clause | HTTP routing and request handling |
| Werkzeug | 3.1.8 | BSD-3-Clause | WSGI utilities; PBKDF2 password hashing |
| Jinja2 | 3.1.6 | BSD-3-Clause | Flask dependency |
| itsdangerous | 2.2.0 | BSD-3-Clause | Flask dependency |
| click | 8.4.2 | BSD-3-Clause | Flask dependency |
| MarkupSafe | 3.0.3 | BSD-3-Clause | Flask dependency |
| blinker | 1.9.0 | MIT | Flask dependency |
| PyJWT | 2.13.0 | MIT | Session token signing and verification |
| Gunicorn | 26.0.0 | MIT | Production WSGI server |
| SQLite | 3.x (bundled) | Public domain | Datastore |
| pytest | 9.1.1 | MIT | Test framework |
| pytest-cov / coverage | 7.1.0 / 7.15.4 | MIT / Apache-2.0 | Coverage measurement |
| ReportLab | 5.0.0 | BSD | PDF generation for this documentation set |
| svglib + rlPyCairo | 2.1.0 / 0.3.0 | LGPL / BSD | Embedding SVG diagrams into the PDFs |
| Pillow | 12.3.0 | MIT-CMU | Image handling for PDF generation |

**Data and content.** All demonstration data — patient names, clinician names, services and appointments — is fictitious and was written for this project. No real patient data of any kind was used at any point.

**Declaration.** This is my own individual work. No part of it has been submitted for any other assessment. No source code, specification or design document was shared with or received from another student.

---

*End of Project Documentation v1.0.*
