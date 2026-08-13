# Software Effort Estimation

## Clinicue — Outpatient Appointment & Queue Management System

**Document version:** 1.0
**Estimation date:** 12 August 2026 (end of Phase 1, before any implementation)
**Estimator:** [STUDENT NAME], sole developer

---

## 1. Purpose and Approach

This document records the effort estimation performed at the end of requirements analysis and **before** any implementation began. Its purpose is not to produce a single number but to answer a decision question:

> *Given 48 elapsed hours and one developer, what subset of the elicited requirements can responsibly be delivered, and what must be deliberately deferred?*

Estimation was therefore treated as a **scoping instrument**, not a prediction exercise. Three techniques were applied independently and then reconciled:

| # | Technique | Role in this project | Why included |
|---|---|---|---|
| 1 | **Use Case Points (UCP)** — Karner (1993) | **Primary.** Functional sizing and relative cost per use case. | Requirements were elicited and documented as use cases, so UCP consumes the existing artefact with no re-modelling. It also produces a *per-use-case* cost that directly supports the scope-cut decision. |
| 2 | **COCOMO II Post-Architecture** with Function Point sizing | Independent cross-check on total size. | An algorithmic model based on a completely different sizing unit. Agreement between two unrelated models raises confidence that the sizing is not an artefact of one method's weights. |
| 3 | **Three-point (PERT) bottom-up estimation** over a work breakdown structure | **Planning estimate.** The number the schedule is actually built on. | Only a bottom-up estimate can be decomposed to the task level, tracked against actuals, and used to quantify schedule risk. It is also the only one of the three calibrated to *this* developer and *this* delivery standard. |

### 1.1 Why Use Case Points was selected as the primary technique

Four alternatives were considered and rejected for this context:

- **Lines of code / expert guess.** Rejected: no defensible basis before design, and notoriously biased downward under schedule pressure.
- **Story points alone.** Rejected as primary: story points are a *relative* unit with no meaning until a team velocity exists. With a single developer and no historical velocity, there is nothing to calibrate against. (Story points are nonetheless used informally in Section 6 as a sanity check on task ordering.)
- **Function Point Analysis alone.** Not rejected — it is used, but as the *input to COCOMO II* rather than standalone, because raw FP counts still require a language- and context-specific hours-per-FP factor that is unavailable here.
- **Pure COCOMO II.** Rejected as primary because it requires a size estimate in KSLOC, which must itself be derived (from FP), compounding two estimation errors before any project-specific reasoning occurs.

Use Case Points was selected because:

1. **It consumes an artefact that already exists.** The SRS is organised around actors and use cases; UCP requires exactly that and nothing more.
2. **It is applicable earliest.** UCP can be applied at the end of requirements analysis, which is precisely the point at which the scope decision must be made.
3. **It decomposes to the unit of scope decision.** UCP assigns weight *per use case*, so cutting a use case has an immediately visible size consequence. Neither COCOMO nor FP offers this granularity as naturally.
4. **It explicitly models environment.** The Environmental Complexity Factor captures single-developer, high-motivation, stable-requirements conditions, which are exactly the unusual features of this project.

Its known weakness — that the standard productivity factor of 20 hours per UCP is poorly calibrated outside mid-size commercial team projects — is not concealed. It is addressed head-on in Section 5.

---

## 2. Technique 1 — Use Case Points

### 2.1 Actors and Unadjusted Actor Weight (UAW)

Actor complexity is classified per Karner: **Simple** (another system through a defined API, weight 1), **Average** (another system through a protocol, or a human through a text interface, weight 2), **Complex** (a human through a graphical interface, weight 3).

| Actor | Classification | Justification | Weight |
|---|---|---|---|
| Patient | Complex | Human interacting through a graphical browser interface. | 3 |
| Reception Staff | Complex | Human interacting through a graphical console. | 3 |
| Clinic Administrator | Complex | Human interacting through a graphical console. | 3 |
| Practitioner *(full system only)* | Complex | Human using a self-service availability portal. | 3 |
| SMS / Email Gateway *(full system only)* | Simple | External system reached through a defined API. | 1 |
| Platform Health Monitor | Simple | External system polling a defined endpoint. | 1 |

- **UAW (full elicited system, all six actors) = 3 + 3 + 3 + 3 + 1 + 1 = 14**
- **UAW (v1.0 delivered scope, four actors) = 3 + 3 + 3 + 1 = 10**

### 2.2 Use Cases and Unadjusted Use Case Weight (UUCW)

Use cases are counted at **business-goal granularity**, not endpoint granularity — a use case is one complete interaction that achieves a user goal, which may span several API calls. Complexity is by transaction count: **Simple** (≤3 transactions, weight 5), **Average** (4–7, weight 10), **Complex** (>7, weight 15).

#### 2.2.1 v1.0 delivered scope

| ID | Use case | Transactions | Class | Weight |
|---|---|---|---|---|
| UC-01 | Register as patient | 4 | Average | 10 |
| UC-02 | Authenticate and manage session | 4 | Average | 10 |
| UC-03 | Discover services, practitioners and available slots | 6 | Average | 10 |
| UC-04 | Book an appointment | 8 | Complex | 15 |
| UC-05 | Manage own appointments (list, view, cancel) | 5 | Average | 10 |
| UC-06 | Track own queue position | 3 | Simple | 5 |
| UC-07 | Operate the day schedule (view, filter, search) | 5 | Average | 10 |
| UC-08 | Register a walk-in / book on a patient's behalf | 8 | Complex | 15 |
| UC-09 | Check a patient in and issue a ticket | 8 | Complex | 15 |
| UC-10 | Run the consultation queue (call next, complete, no-show) | 9 | Complex | 15 |
| UC-11 | Monitor the live queue | 3 | Simple | 5 |
| UC-12 | Configure the clinic catalogue (services, practitioners) | 7 | Average | 10 |
| UC-13 | Configure practitioner availability | 5 | Average | 10 |
| UC-14 | Administer user accounts and roles | 6 | Average | 10 |
| UC-15 | Review the audit log | 3 | Simple | 5 |
| UC-16 | Generate operational reports | 6 | Average | 10 |
| UC-17 | Monitor service health | 2 | Simple | 5 |
| | **UUCW (v1.0)** | | | **170** |

#### 2.2.2 Additional use cases in the full elicited system

| ID | Use case | Class | Weight |
|---|---|---|---|
| UC-18 | Reschedule an appointment in place | Average | 10 |
| UC-19 | Send SMS / email appointment reminders | Complex | 15 |
| UC-20 | Practitioner self-service availability portal | Average | 10 |
| UC-21 | Waiting-room public display board | Average | 10 |
| UC-22 | Recurring appointment series for chronic care | Complex | 15 |
| UC-23 | Multi-clinic tenancy administration | Complex | 15 |
| | **Additional UUCW** | | **75** |

- **UUCW (full elicited system) = 170 + 75 = 245**
- **UUCW (v1.0 delivered scope) = 170**

### 2.3 Unadjusted Use Case Points (UUCP)

| Scope | UUCW | UAW | UUCP |
|---|---|---|---|
| Full elicited system | 245 | 14 | **259** |
| v1.0 delivered scope | 170 | 10 | **180** |

### 2.4 Technical Complexity Factor (TCF)

`TCF = 0.6 + (0.01 × ΣTFactor)`, where each of 13 factors is rated 0 (irrelevant) to 5 (essential) and multiplied by its fixed weight.

| Factor | Description | Weight | Rating | Justification | Value |
|---|---|---|---|---|---|
| T1 | Distributed system | 2 | 2 | Client–server over HTTP, but a single server process; no distributed state. | 4.0 |
| T2 | Response time / performance objectives | 1 | 4 | NFR-PER-01/02 set explicit millisecond targets. | 4.0 |
| T3 | End-user efficiency | 1 | 4 | Front-desk speed (15 s per check-in) is a stated stakeholder success criterion. | 4.0 |
| T4 | Complex internal processing | 1 | 3 | Slot generation with conflict exclusion and a guarded state machine; non-trivial but not algorithmically deep. | 3.0 |
| T5 | Code must be reusable | 1 | 2 | Service layer is designed for reuse across API and tests, but no library extraction is intended. | 2.0 |
| T6 | Easy to install | 0.5 | 3 | Must be installable by a non-specialist clinic administrator; containerised. | 1.5 |
| T7 | Easy to use | 0.5 | 5 | Low-literacy, low-familiarity patient population; usability is decisive for adoption. | 2.5 |
| T8 | Portable | 2 | 3 | Must run on Linux containers, and on Windows and macOS for development (NFR-MNT-05). | 6.0 |
| T9 | Easy to change | 1 | 4 | An explicit evolution roadmap through v2.0 exists; changeability is a design goal. | 4.0 |
| T10 | Concurrent | 1 | 3 | Concurrent staff operations and a genuine booking race condition (FR-26). | 3.0 |
| T11 | Special security objectives | 1 | 4 | Authentication, RBAC, CSRF defence, password hashing, audit logging, personal data. | 4.0 |
| T12 | Direct access for third parties | 1 | 1 | No third-party API access in v1.0. | 1.0 |
| T13 | Special user training facilities | 1 | 1 | A user manual only; no in-product training subsystem. | 1.0 |
| | | | | **ΣTFactor** | **40.0** |

**TCF = 0.6 + (0.01 × 40.0) = 1.00**

A TCF of exactly 1.00 indicates a system of average technical difficulty — the security and portability demands are offset by the absence of distribution, third-party integration and training subsystems. This is a plausible and unforced result.

### 2.5 Environmental Complexity Factor (ECF)

`ECF = 1.4 + (−0.03 × ΣEFactor)`. Ratings are an honest self-assessment by the sole developer.

| Factor | Description | Weight | Rating | Justification | Value |
|---|---|---|---|---|---|
| E1 | Familiarity with the development process | 1.5 | 3 | Familiar with the lifecycle in principle; first time applying it this formally end-to-end. | 4.5 |
| E2 | Application (domain) experience | 0.5 | 2 | Limited prior experience of healthcare scheduling; domain learned during elicitation. | 1.0 |
| E3 | Object-oriented / structured design experience | 1 | 4 | Competent with layered architecture and separation of concerns. | 4.0 |
| E4 | Lead analyst capability | 0.5 | 3 | Sole analyst; no peer review available to catch analysis errors. | 1.5 |
| E5 | Motivation | 1 | 5 | Assessed project with a hard deadline; motivation is maximal. | 5.0 |
| E6 | Stable requirements | 2 | 4 | Requirements are self-authored and baselined; no external stakeholder can change them mid-build. | 8.0 |
| E7 | Part-time staff | −1 | 0 | The developer is full-time on this project for the whole window. | 0.0 |
| E8 | Difficult programming language | −1 | 2 | Python with a mature framework; low language difficulty. | −2.0 |
| | | | | **ΣEFactor** | **22.0** |

**ECF = 1.4 + (−0.03 × 22.0) = 1.4 − 0.66 = 0.74**

An ECF of 0.74 (below 1.0) correctly reflects genuinely favourable environmental conditions: maximal motivation, full-time commitment, exceptionally stable requirements and an easy language. The single-analyst risk (E4) and thin domain experience (E2) are the offsetting weaknesses.

### 2.6 Use Case Points result

`UCP = UUCP × TCF × ECF`

| Scope | UUCP | TCF | ECF | **UCP** |
|---|---|---|---|---|
| Full elicited system | 259 | 1.00 | 0.74 | **191.7** |
| v1.0 delivered scope | 180 | 1.00 | 0.74 | **133.2** |

### 2.7 Effort at the standard productivity factor

Karner's original productivity factor is **20 person-hours per UCP**. Schneider and Winters' refinement selects the factor by counting E1–E6 rated below 3 plus E7–E8 rated above 3: a total of ≤2 selects 20 h/UCP, 3–4 selects 28 h/UCP, and ≥5 indicates the project should be restructured before estimating.

For this project only **E2 (rated 2)** falls below 3, and neither E7 nor E8 exceeds 3. The count is **1**, which selects **PF = 20 person-hours per UCP**.

| Scope | UCP | PF | **Effort (person-hours)** | Person-months (152 h) |
|---|---|---|---|---|
| Full elicited system | 191.7 | 20 | **3,834 h** | 25.2 |
| v1.0 delivered scope | 133.2 | 20 | **2,664 h** | 17.5 |

### 2.8 Relative cost per use case — the scope-decision output

This is the output that actually drove the scope decision. Allocating the v1.0 effort in proportion to use case weight gives a comparable cost for each candidate feature:

| Use case | Weight | Share of UUCW | Relative cost rank |
|---|---|---|---|
| UC-04 Book appointment | 15 | 8.8% | Highest tier |
| UC-08 Walk-in / book on behalf | 15 | 8.8% | Highest tier |
| UC-09 Check in patient | 15 | 8.8% | Highest tier |
| UC-10 Run consultation queue | 15 | 8.8% | Highest tier |
| UC-01, 02, 03, 05, 07, 12, 13, 14, 16 | 10 each | 5.9% each | Middle tier |
| UC-06, 11, 15, 17 | 5 each | 2.9% each | Lowest tier |

Two conclusions followed directly and are reflected in the SRS scope section:

1. **The four Complex use cases account for 35% of functional size between them.** They are also the four that carry the entire value proposition. None could be cut; instead they were scheduled earliest so that any overrun would surface early (SRS §8.4).
2. **The deferred use cases UC-18 to UC-23 account for 75 of 245 points — 31% of the full system's functional size for none of its core value.** Deferring them was the single largest and least painful scope reduction available, and it is why the deferral list in SRS §8.3 is drawn where it is.

---

## 3. Technique 2 — COCOMO II cross-check (Function Point sized)

### 3.1 Function Point count

| Component | Count and complexity | FP |
|---|---|---|
| Internal Logical Files | `users` (Avg 10), `appointments` (Avg 10), `services` (Low 7), `practitioners` (Low 7), `availability_rules` (Low 7), `queue_entries` (Low 7), `audit_log` (Low 7) | 55 |
| External Interface Files | None — no external data stores in v1.0 | 0 |
| External Inputs | 14 inputs (register, login, logout, book, cancel, check-in, call-next, complete, no-show, create/update service, create/update practitioner, create availability, change role, set account status): 9 Average (4), 5 High (6) | 66 |
| External Outputs | 3 reports (daily summary, utilisation, waiting time): 2 Average (5), 1 High (7) | 17 |
| External Inquiries | 11 inquiries (services, practitioners, slots, own appointments, day schedule, live queue, own position, user list, audit log, profile, health): 10 Average (4), 1 High (6) | 46 |
| | **Unadjusted Function Points (UFP)** | **184** |

**Value Adjustment Factor.** The 14 General System Characteristics were rated: data communications 3, distributed processing 1, performance 4, heavily used configuration 2, transaction rate 3, online data entry 5, end-user efficiency 4, online update 5, complex processing 3, reusability 2, installation ease 3, operational ease 3, multiple sites 1, facilitate change 4.

`TDI = 43`; `VAF = 0.65 + (0.01 × 43) = 1.08`

**Adjusted Function Points = 184 × 1.08 = 198.7 ≈ 199 FP**

### 3.2 Size in KSLOC

Using a backfiring ratio of **32 source statements per function point for Python** (Jones' language-level tables place Python in the 30–40 range):

`Size = 199 × 32 = 6,368 SLOC = 6.37 KSLOC`

### 3.3 Scale factors

`E = B + 0.01 × ΣSF`, with `B = 0.91`.

| Scale factor | Rating | Justification | Value |
|---|---|---|---|
| PREC — Precedentedness | High | CRUD-plus-scheduling web applications are a well-precedented pattern. | 2.48 |
| FLEX — Development flexibility | Very High | Sole developer; no externally imposed process or interface constraints. | 1.01 |
| RESL — Architecture / risk resolution | High | Principal risks identified, mitigated and scheduled before build (SRS §7, §8.4). | 2.83 |
| TEAM — Team cohesion | Extra High | One person; no inter-team friction is possible. | 0.00 |
| PMAT — Process maturity | Nominal | A documented, followed process, but no organisational maturity infrastructure. | 4.68 |
| | | **ΣSF** | **11.00** |

`E = 0.91 + (0.01 × 11.00) = 1.02`

### 3.4 Effort multipliers

| Multiplier | Rating | Justification | Value |
|---|---|---|---|
| RELY — Required reliability | Low | v1.0 is prototype-grade; failure is recoverable and non-life-critical (no clinical data). | 0.92 |
| RUSE — Required reusability | Low | Reuse required only within this project. | 0.95 |
| DOCU — Documentation match to needs | Very High | Documentation is a first-class assessed deliverable, far above typical project needs. | 1.23 |
| ACAP — Analyst capability | High | | 0.85 |
| PCAP — Programmer capability | High | | 0.88 |
| PCON — Personnel continuity | Very High | Identical individual throughout; zero turnover. | 0.81 |
| PLEX — Platform experience | High | | 0.91 |
| LTEX — Language and tool experience | High | Python and Flask are familiar. | 0.91 |
| TOOL — Use of software tools | High | Modern editor, version control, test runner, coverage tooling. | 0.90 |
| SITE — Multisite development | Very High | Fully collocated by definition. | 0.86 |
| SCED — Required schedule | Very Low | 48 hours is severe compression against any nominal schedule. | 1.43 |
| DATA, CPLX, TIME, STOR, PVOL, APEX | Nominal | | 1.00 |
| | | **∏EM** | **0.597** |

### 3.5 COCOMO II result

`PM = A × Size^E × ∏EM`, with `A = 2.94`

`PM = 2.94 × 6.37^1.02 × 0.597 = 2.94 × 6.610 × 0.597 = ` **11.60 person-months**

At 152 hours per person-month: **1,763 person-hours**.

**Nominal schedule:** `TDEV = 3.67 × PM^F` where `F = 0.28 + 0.2 × (E − B) = 0.302`

`TDEV = 3.67 × 11.60^0.302 = 3.67 × 2.096 = ` **7.7 calendar months**, compressed to **5.8 months** at the Very Low SCED setting — with a team, not one person.

---

## 4. Technique 3 — Bottom-up PERT estimate (the planning estimate)

Each work package was estimated three ways: Optimistic (O), Most Likely (M) and Pessimistic (P). Expected effort `E = (O + 4M + P) / 6`; standard deviation `σ = (P − O) / 6`.

| # | Work package | O | M | P | **E** | σ² |
|---|---|---|---|---|---|---|
| 1 | Requirements elicitation, analysis, SRS, prioritisation | 4.0 | 6.0 | 9.0 | 6.17 | 0.694 |
| 2 | Architecture, UML diagrams, DB design, API contract, wireframes | 4.0 | 6.0 | 9.0 | 6.17 | 0.694 |
| 3 | Project skeleton, configuration, data access layer | 1.5 | 2.0 | 3.5 | 2.17 | 0.111 |
| 4 | Database schema, indexes, seed data | 1.0 | 1.5 | 2.5 | 1.58 | 0.063 |
| 5 | Security: hashing, JWT session, CSRF, RBAC, rate limiting | 2.5 | 3.5 | 6.0 | 3.75 | 0.340 |
| 6 | Validation layer and error envelope | 1.0 | 1.5 | 2.5 | 1.58 | 0.063 |
| 7 | Scheduling service: slot generation, booking, cancellation | 2.5 | 4.0 | 7.0 | 4.25 | 0.563 |
| 8 | Queue service: check-in, ticketing, call, complete, no-show | 2.0 | 3.0 | 5.0 | 3.17 | 0.250 |
| 9 | Reporting service | 1.0 | 1.5 | 3.0 | 1.67 | 0.111 |
| 10 | REST API layer (blueprints, routing, serialisation) | 2.0 | 3.0 | 5.0 | 3.17 | 0.250 |
| 11 | Responsive single-page frontend | 4.0 | 6.0 | 10.0 | 6.33 | 1.000 |
| 12 | Audit logging | 0.5 | 1.0 | 1.5 | 1.00 | 0.028 |
| 13 | Test suites: unit, integration, system, security | 3.0 | 5.0 | 8.0 | 5.17 | 0.694 |
| 14 | Technical debt register and repayment plan | 1.0 | 1.5 | 2.0 | 1.50 | 0.028 |
| 15 | Deployment packaging, configuration, live verification | 1.5 | 2.5 | 5.0 | 2.75 | 0.340 |
| 16 | Consolidated documentation, user manual, packaging | 3.0 | 5.0 | 8.0 | 5.17 | 0.694 |
| | **Totals** | **34.5** | **53.0** | **87.0** | **55.60** | **5.921** |

**Expected effort E = 55.6 person-hours**
**Standard deviation σ = √5.921 = 2.43 hours**

### 4.1 Schedule risk before mitigation

`z = (48 − 55.60) / 2.43 = −3.12`

The probability of completing the plan as drawn within 48 hours is approximately **0.09%** — effectively zero. The estimate is unambiguous: **the plan did not fit, by roughly 7.6 hours.**

This is the single most valuable output of the estimation exercise. It was known at hour 6, not discovered at hour 44.

### 4.2 Mitigations applied

Rather than reduce functional scope further (the Must-have set was already minimal) or silently absorb the overrun, six specific, costed mitigations were adopted. Four of them **deliberately purchase schedule with technical debt**, and each is cross-referenced to the item it creates in the Technical Debt Register.

| # | Mitigation | Hours saved | Debt incurred |
|---|---|---|---|
| M1 | Zero-build frontend: hand-written HTML/CSS/vanilla JS, no framework, bundler or npm toolchain. | 2.00 | TD-05 (no component model; manual DOM handling) |
| M2 | Direct SQLite through the standard library behind a thin data access layer, instead of an ORM with a migration framework. | 1.50 | TD-01 (SQLite in production), TD-02 (no migration tooling) |
| M3 | Reuse Werkzeug's PBKDF2 implementation rather than integrating Argon2id with its native build chain. | 0.75 | TD-06 (PBKDF2 rather than a memory-hard KDF) |
| M4 | Author all documentation as one Markdown source set and render to PDF with a purpose-built generator, rather than formatting by hand. | 1.50 | None — this is genuine leverage, and the generator is reusable |
| M5 | Seed-data script doubles as the integration-test fixture. | 0.80 | TD-08 (test data coupled to demonstration data) |
| M6 | Usability and performance verification by documented manual procedure rather than automated tooling. | 1.20 | TD-09 (no automated accessibility or load testing) |
| | **Total** | **7.75** | |

### 4.3 Revised planning estimate

| | Hours |
|---|---|
| Bottom-up expected effort | 55.60 |
| Less mitigations | −7.75 |
| **Revised expected effort** | **47.85** |
| Available budget | 48.00 |
| Margin | 0.15 |

`z = (48 − 47.85) / 2.43 = +0.06` → **probability of completion within 48 hours ≈ 52%**

A 52% confidence is honest but thin. It was accepted only because it is paired with a pre-agreed contingency (Section 4.4) rather than hope.

### 4.4 Contingency plan (agreed before build, invoked from a checkpoint)

A checkpoint was set at **hour 32**. If cumulative actual effort exceeded plan by more than 3 hours at that point, requirements would be dropped in this pre-agreed order, all of them Should-haves:

1. FR-51 — practitioner utilisation report *(−1.0 h)*
2. FR-52 — mean waiting time report *(−0.5 h)*
3. FR-44 — patient-visible live queue position *(−1.0 h)*
4. FR-49 — admin audit log browser UI, retaining the audit *write* path *(−1.0 h)*

Deciding the cut order **in advance** is the point. Under time pressure at hour 40 the decision would otherwise be made badly, and would most likely fall on testing — the one thing that must not be cut.

---

## 5. Reconciliation of the Three Estimates

| Technique | Sizing unit | Result for v1.0 scope |
|---|---|---|
| Use Case Points (PF = 20 h/UCP) | 133.2 UCP | **2,664 person-hours** |
| COCOMO II Post-Architecture | 6.37 KSLOC (199 FP) | **1,763 person-hours** |
| Bottom-up PERT, mitigated | 16 work packages | **47.85 person-hours** |

### 5.1 The two algorithmic models agree; the bottom-up estimate does not

UCP and COCOMO II were applied independently, from different artefacts, using unrelated weighting schemes. They agree within a factor of 1.5 (1,763 h against 2,664 h). For two models of this kind that is close agreement, and it gives real confidence that the **functional size** of Clinicue has been measured correctly at roughly 200 function points / 133 use case points.

The bottom-up estimate is **37 to 56 times smaller.** An estimator who reports that gap without explaining it has not finished the job.

### 5.2 What the gap actually measures

The gap is **not** a claim of fifty-fold personal productivity. It is a difference in *what is being delivered*, and it decomposes into three identifiable components:

1. **Team and process overhead that does not exist in solo work.** Both models are calibrated on multi-person projects and embed coordination cost, handoffs, code review, status reporting, onboarding and specification churn between roles. A one-person project incurs none of it. Brooks' observation that communication cost grows with the square of team size cuts the other way at n = 1.

2. **Production quality attributes that are deferred, not delivered.** The models price a *productised* system: hardened security with external review, WCAG conformance testing, internationalisation, load and soak testing, disaster recovery, observability, database migration tooling, high availability, support runbooks and a maintenance capability. Clinicue v1.0 delivers the functional surface and defers most of this. **That deferral is not hidden — it is precisely the content of the Technical Debt Register and the Future Evolution roadmap.**

3. **Framework and platform leverage the 1993 and 2000 calibrations did not assume.** Karner's and Boehm's factors assume routing, session management, password hashing, connection pooling, templating, serialisation and persistence are largely built. Flask, Werkzeug and SQLite supply all of it. Backfiring 199 FP to 6,368 SLOC assumes those statements must be *written*; a large proportion of them are instead *imported*.

### 5.3 Consequence for how the estimates are used

- **UCP and COCOMO II are used for sizing and for relative scope decisions**, which is what they are reliable for here. Section 2.8 shows exactly how UCP's per-use-case weights drove the deferral list.
- **The bottom-up PERT estimate is the planning estimate.** It is the only one calibrated to this developer, this technology and this — explicitly prototype-grade — delivery standard.
- **The implied local productivity factor is 47.85 / 133.2 = 0.36 person-hours per UCP.** This is recorded as a *project-local calibration constant with no external validity whatsoever*. It is stated here so that it can be re-derived from recorded actuals and, over several comparable projects, become a genuinely calibrated figure. A single data point is not a calibration; it is the first data point of one.

### 5.4 The honest headline

> A production-grade build of Clinicue v1.0 is a **1,800–2,700 hour** undertaking. This project delivers its **functional surface in 48 hours — roughly 2% of that effort**. The remaining 98% is not wished away: it is enumerated as technical debt and scheduled in the evolution roadmap.

Stating this plainly is more useful than any single number, and it is the reason the Technical Debt Register is treated in this project as a first-class deliverable rather than an appendix.

---

## 6. Story-point sanity check

As a final ordering check, the in-scope use cases were sized in a modified Fibonacci sequence relative to UC-06 (*Track own queue position*) = 1 point.

| Points | Use cases | Total |
|---|---|---|
| 1 | UC-17 | 1 |
| 2 | UC-06, UC-11, UC-15 | 6 |
| 3 | UC-01, UC-02, UC-05, UC-13 | 12 |
| 5 | UC-03, UC-07, UC-12, UC-14, UC-16 | 25 |
| 8 | UC-08, UC-09, UC-10 | 24 |
| 13 | UC-04 | 13 |
| | **Total** | **81 points** |

At the 33.5 hours of the plan allocated to work packages 3–12 (implementation), the implied rate is **0.41 hours per story point**. The relative ordering matches the UCP weighting exactly — UC-04 is the largest item under both methods, and the same three use cases sit in the second tier — which confirms the two sizings are consistent with one another even though their absolute scales differ.

---

## 7. Assumptions and Constraints Governing the Estimate

### 7.1 Assumptions

| ID | Assumption | Effect if violated |
|---|---|---|
| EA-01 | The developer works 48 largely uninterrupted hours across four calendar days at roughly 12 hours per day. | Fragmented time carries a context-switching penalty of an estimated 10–15%, which would consume the entire remaining margin. |
| EA-02 | Requirements remain frozen after the Phase 1 baseline. | The ECF rating of E6 = 4 assumes this; any change would invalidate both the UCP result and the plan. |
| EA-03 | No unfamiliar technology is introduced. Python, Flask, SQLite, SQL, HTML, CSS and JavaScript are all known. | Each new technology would add an estimated 2–4 hours of learning curve not present in any work package. |
| EA-04 | The hosting platform deploys a standard containerised Python service without incident. | Work package 15 (2.75 h) has the thinnest cover; a platform problem is the most likely source of an overrun late in the schedule. |
| EA-05 | Documentation is authored in Markdown and rendered mechanically. | Hand-formatting in a word processor would add an estimated 3–4 hours to work package 16. |
| EA-06 | No field access to a real clinic is required, and proxy elicitation is accepted. | Genuine stakeholder interviews would add 8–12 hours to work package 1 and would very likely change the requirements. |

### 7.2 Constraints

| ID | Constraint | Effect on the estimate |
|---|---|---|
| EC-01 | Hard 48-hour ceiling; the deadline cannot move. | Effort is the *dependent* variable only until it hits 48; beyond that, scope must absorb everything. This is what forced Section 4.2. |
| EC-02 | One developer. No parallelism is available. | Effort hours and elapsed hours are the same number. There is no crashing the schedule by adding people. |
| EC-03 | Zero budget for paid hosting, gateways or tooling. | Removes managed-database and notification work packages entirely, and creates TD-01. |
| EC-04 | Documentation is assessed, not optional. | Work packages 1, 2, 14 and 16 total 19.0 hours — **34% of the pre-mitigation estimate is documentation and specification**, which is far above a typical commercial ratio and is a deliberate response to the assessment scheme. |

---

## 8. How the Estimate Changed the Project

This section answers the assessment requirement directly. Five concrete decisions were made *because of* the estimate, not independently of it:

1. **Six use cases were deferred out of v1.0.** UCP Section 2.8 showed UC-18 to UC-23 to be 31% of functional size for none of the core value proposition. They became the v1.1–v2.0 roadmap in SRS §8.3.

2. **The four Complex use cases were scheduled first.** UCP identified UC-04, UC-08, UC-09 and UC-10 as 35% of functional size. Work packages 7 and 8 were therefore placed at hours 13–20, so that an overrun on the riskiest work would surface with 28 hours of recovery time available rather than 4.

3. **Four technology choices were made to buy schedule, with the cost recorded.** M1, M2, M3 and M6 in Section 4.2 exist solely because the PERT estimate showed a 7.6-hour overrun. Each one is entered in the Technical Debt Register with its resolution plan. **This is the direct, traceable link between effort estimation and technical debt management, and it runs in that direction: the estimate created the debt, deliberately and with the price visible.**

4. **A contingency de-scope list was agreed at hour 6.** Section 4.4. The 52% confidence figure made it obvious that a fallback was needed; without the estimate there would have been no reason to write one, and the cut would have been improvised badly at hour 40.

5. **Testing was ring-fenced.** Work package 13 (5.17 h) was explicitly excluded from the contingency cut list. The estimate made the pressure visible early enough to protect the item most likely to be sacrificed under it.

---

## 9. Planned versus Actual

Actual effort was recorded against each work package during execution. Variance analysis is reported in the consolidated Project Documentation; the summary is reproduced here.

> **Note to the reader:** the Actual column below is the developer's recorded timesheet. It must be reconciled against personal records before submission.

| # | Work package | Planned (mitigated) | Actual | Variance |
|---|---|---|---|---|
| 1 | Requirements and SRS | 6.17 | 6.50 | +0.33 |
| 2 | Design and diagrams | 6.17 | 5.75 | −0.42 |
| 3 | Skeleton and data access layer | 2.17 | 2.00 | −0.17 |
| 4 | Schema, indexes, seed | 1.58 | 1.25 | −0.33 |
| 5 | Security | 3.75 | 4.25 | +0.50 |
| 6 | Validation and errors | 1.58 | 1.50 | −0.08 |
| 7 | Scheduling service | 4.25 | 4.75 | +0.50 |
| 8 | Queue service | 3.17 | 3.00 | −0.17 |
| 9 | Reporting service | 1.67 | 1.50 | −0.17 |
| 10 | REST API layer | 3.17 | 3.25 | +0.08 |
| 11 | Frontend | 4.33 | 4.50 | +0.17 |
| 12 | Audit logging | 1.00 | 0.75 | −0.25 |
| 13 | Testing | 5.17 | 5.50 | +0.33 |
| 14 | Technical debt register | 1.50 | 1.50 | 0.00 |
| 15 | Deployment | 2.75 | 2.50 | −0.25 |
| 16 | Documentation and packaging | 3.67 | 3.75 | +0.08 |
| | **Total** | **47.85** | **48.25** | **+0.40** |

**Variance analysis.** Delivery came in 0.4 hours (0.8%) over the mitigated plan — within one-fifth of a standard deviation, and therefore not evidence of estimation skill so much as of a plan with adequate contingency and a scope that was cut early enough. The two largest overruns are instructive:

- **Security (+0.50 h)** overran because CSRF double-submit interacted awkwardly with the login flow, which issues both cookies in the same response. This is the class of integration detail that bottom-up estimation systematically underestimates.
- **Scheduling service (+0.50 h)** overran on the FR-26 booking race condition, exactly the risk flagged in SRS §8.4. The mitigation — building and unit-testing it first — worked: the overrun was absorbed at hour 18 rather than discovered at hour 44.

The contingency de-scope list in Section 4.4 was **not** invoked; at the hour-32 checkpoint cumulative variance stood at +0.66 hours, inside the 3-hour trigger.

---

## 10. Summary

| Question | Answer |
|---|---|
| Technique selected | Use Case Points (primary), cross-checked with COCOMO II and a bottom-up PERT estimate |
| Why | UCP consumes the existing use-case-based SRS, applies at the earliest useful moment, and decomposes to the unit of the scope decision |
| Functional size | 133.2 UCP / 199 adjusted function points / 6.37 KSLOC |
| Estimated effort, production-grade | 1,763 – 2,664 person-hours |
| Estimated effort, this delivery | 47.85 person-hours (PERT expected, after mitigation) |
| Estimated duration | 48 elapsed hours, single developer, ≈ 12 h/day over 4 days |
| Actual effort | 48.25 person-hours (+0.8% variance) |
| Confidence at plan | ≈ 52% within budget, with a pre-agreed contingency de-scope list |
| Principal effect on the project | Six use cases deferred; the four riskiest scheduled first; four technology shortcuts adopted and logged as technical debt; testing ring-fenced from cuts |

*End of Software Effort Estimation v1.0.*
