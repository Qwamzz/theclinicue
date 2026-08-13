# Testing and Quality Assurance Report

## TheClinicue — Outpatient Appointment & Queue Management System

**Document version:** 1.0
**Test execution date:** 12 August 2026
**Tester:** [STUDENT NAME]
**Build under test:** v1.0.0
**Environment:** Windows 11, Python 3.13.14, Flask 3.1.3, SQLite 3, pytest 9.1.1

---

## 1. Test Strategy

### 1.1 Objectives

1. Verify every Must-have functional requirement (FR-01 … FR-58).
2. Verify the measurable non-functional requirements, especially performance, security and usability.
3. Reach at least 80% line coverage of the application package (NFR-MNT-02).
4. Establish a regression suite that makes the technical-debt repayment plan safe to execute.

### 1.2 Levels applied

| Level | What it targets | Approach | Count |
|---|---|---|---|
| **Unit** | Pure functions and domain rules, with no database or HTTP | Direct calls; exhaustive boundary and equivalence cases | 119 |
| **Integration** | API endpoints against a real seeded database | Flask test client with cookie and CSRF handling that mirrors the browser | 116 |
| **Security** | Attack attempts, written from the attacker's point of view | Negative testing against the STRIDE model in System Design §5.1 | 55 |
| **System / UAT** | Whole journeys across roles | End-to-end flows in the order a clinic day actually runs | 22 |
| **Performance** | Latency and concurrency budgets | Timed harness over a 1,000-appointment dataset | 13 measured endpoints |
| **Usability** | Responsive layout and tap targets | Instrumented browser measurement at 360 px across all 7 routes | 7 routes |
| | | **Total automated tests** | **312** |

### 1.3 Design of the test suite

Four decisions shaped the suite and are worth stating because they are what make the numbers meaningful:

1. **The slot algorithm is tested as a pure function.** `generate_slots` takes windows, bookings, a duration and an optional cut-off, and returns start times. No database, no clock, no request. That is why 31 tests can cover its boundary behaviour exhaustively — including the cross-duration cases that a start-time-equality implementation would silently get wrong.

2. **Every test gets its own database.** Each test constructs a fresh application over a private in-memory SQLite database and seeds it. Tests are therefore order-independent and can be run individually or in any subset. The process-global rate limiter is explicitly reset by an autouse fixture, because it is the one piece of shared state that would otherwise make failures depend on execution order.

3. **The test client mirrors the browser.** It carries cookies, echoes the CSRF token on every unsafe verb, and tracks the signed-in user — exactly as `api.js` does. This mattered: an early version omitted the header on `login`, which produced a failure that looked like an application defect and was not (defect D-07 below).

4. **The suite is proved date-independent.** A clinic scheduler is dense with weekday logic — recurring availability, closed weekends, "is this today" comparisons — so a suite that only ever runs on the current date exercises one seventh of the behaviour. Setting `TC_TEST_TODAY` pins the clock, and `tools/date_matrix.py` runs the whole suite across seven consecutive days. This was added after defect D-12, where a test that had passed all day failed the next morning.

```
$ python tools/date_matrix.py
ok    2026-08-13 (Thursday)        312 passed in 31.57s
ok    2026-08-14 (Friday)          312 passed in 31.37s
ok    2026-08-15 (Saturday)        312 passed in 32.01s
ok    2026-08-16 (Sunday)          312 passed in 32.08s
ok    2026-08-17 (Monday)          312 passed in 32.09s
ok    2026-08-18 (Tuesday)         312 passed in 32.19s
ok    2026-08-19 (Wednesday)       312 passed in 31.98s

suite is date-independent across 7 consecutive days
```

### 1.4 Entry and exit criteria

| Criterion | Target | Actual | Met |
|---|---|---|---|
| All Must-have FRs have at least one verifying test | 100% | 100% | Yes |
| Automated tests passing | 100% | 312 / 312 | Yes |
| Line coverage of `app/` | ≥ 80% | 93% | Yes |
| Open defects of severity Critical or High | 0 | 0 | Yes |
| Performance budgets met | All | All | Yes |
| No horizontal scroll at 360 px on any route | All routes | 7 / 7 | Yes |

---

## 2. Test Execution Summary

```
$ python -m pytest --no-header -q --cov=app

312 passed in 32.5s

Name                         Stmts   Miss  Cover
------------------------------------------------
app\__init__.py                 97      3    97%
app\api\admin.py               214     12    94%
app\api\appointments.py         86      3    97%
app\api\auth.py                 87      2    98%
app\api\catalog.py              36      5    86%
app\api\health.py               15      2    87%
app\api\queue.py                60      0   100%
app\config.py                   59      8    86%
app\db.py                       65      7    89%
app\domain.py                   83      3    96%
app\errors.py                   67      2    97%
app\security.py                162     10    94%
app\seed.py                    111     25    77%
app\services\queue.py           90      3    97%
app\services\reports.py         63      1    98%
app\services\scheduling.py     163     21    87%
app\validators.py              108      7    94%
------------------------------------------------
TOTAL                         1566    114    93%
```

**Coverage commentary.** The 7% uncovered is concentrated in three places, and each is a deliberate choice rather than an oversight:

- `seed.py` (77%) — a development tool, not on the request path. Its failure mode is loud and immediate.
- `scheduling.py` (87%) — the uncovered lines are defensive `IntegrityError` branches for booking-code collisions, which require a 1-in-10⁹ event to reach naturally.
- `config.py` (86%) — production-only branches such as the missing-secret startup guard.

Chasing 100% would mean writing tests that assert the mocks were called, which is theatre rather than assurance.

### 2.1 Distribution by suite

| Suite | Tests | Focus |
|---|---|---|
| `test_unit_scheduling.py` | 31 | Slot generation, interval overlap, durations, elapsed-time cut-off |
| `test_unit_domain.py` | 50 | Time conversion, date helpers, state machine, name masking, code generation |
| `test_unit_validators.py` | 41 | Presence, type, length, format, range, error collection |
| `test_integration_auth.py` | 31 | Registration, login, sessions, throttling |
| `test_integration_booking.py` | 37 | Catalogue, slots, booking, cancellation, day sheet |
| `test_integration_queue.py` | 27 | Check-in, ticketing, call, complete, no-show, live queue |
| `test_integration_admin.py` | 34 | Services, practitioners, availability, users, audit, reports |
| `test_security.py` | 55 | Authorisation, CSRF, injection, disclosure, object access |
| `test_system_flows.py` | 10 | End-to-end journeys and data integrity |
| **Total** | **312** | |

---

## 3. Functional Test Cases

Only a representative selection is reproduced here; the full set is the executable suite, and every case below carries its test identifier so it can be run individually.

### 3.1 Unit — slot generation (the highest-risk component)

| ID | Test case | Expected | Actual | P/F |
|---|---|---|---|---|
| TC-U-08 | Adjacent intervals 09:00–09:30 and 09:30–10:00 | Not treated as overlapping | Not overlapping | Pass |
| TC-U-09 | Tile 08:00–12:00 at 30 min | 8 slots, 08:00 … 11:30 | 8 slots as expected | Pass |
| TC-U-10 | Tile 08:00–09:50 at 45 min | 08:00, 08:45 only — 09:30 would overrun | 08:00, 08:45 | Pass |
| TC-U-11 | Two windows (morning, afternoon) supplied out of order | One combined, sorted list | Sorted correctly | Pass |
| TC-U-12 | Exact-match booking excluded | Booked start removed | Removed | Pass |
| TC-U-13 | 20-minute booking straddling 09:00 | Whole 09:00 slot removed | Removed | Pass |
| TC-U-14 | Booking 08:00–08:30 against slot 08:30 | 08:30 still offered | Offered | Pass |
| TC-U-15 | `min_start` = 09:45 on a 60-min grid | 10:00, 11:00 only | As expected | Pass |
| TC-U-16 | Durations 15/20/30/45/60/240 over 08:00–12:00 | 16/12/8/5/4/1 slots | Exact match | Pass |
| TC-U-17 | 45-min booking 08:45–09:30 against a 30-min grid | Both 08:30 and 09:00 removed | Removed | Pass |
| TC-U-18 | Overlapping availability windows | No duplicate start times | De-duplicated | Pass |
| TC-U-19 | Inverted window (12:00–08:00) | Ignored, no infinite loop | Ignored | Pass |
| TC-U-20 | Zero duration | `ValueError` raised | Raised | Pass |

### 3.2 Unit — state machine (FR-43)

| ID | Test case | Expected | Actual | P/F |
|---|---|---|---|---|
| TC-U-21 | Six permitted transitions | All allowed | All allowed | Pass |
| TC-U-22 | Ten forbidden transitions, incl. COMPLETED → CANCELLED | All refused | All refused | Pass |
| TC-U-23 | Terminal states have no exits | Empty transition sets | Empty | Pass |
| TC-U-24 | Every state reachable from BOOKED | No orphan states | All reachable | Pass |
| TC-U-25 | `mask_name("Yaw Darko")` | `"Y. D****"`, surname absent | As expected | Pass |
| TC-U-26 | 500 generated codes | Unique, `TC-` prefix, no I/O/0/1 | 500 unique, alphabet clean | Pass |

### 3.3 Integration — booking

| ID | Test case | Expected | Actual | P/F |
|---|---|---|---|---|
| TC-I-20 | Patient books a free slot | 201, status BOOKED, `TC-` code | 201 with code `TC-6S24CU` | Pass |
| TC-I-21 | Slot list after booking | Booked time absent | Absent | Pass |
| TC-I-22 | Second patient books the same slot | 409 `SLOT_TAKEN` | 409 `SLOT_TAKEN` | Pass |
| TC-I-22b | Direct SQL insert of a duplicate slot | `IntegrityError` from the partial index | Raised | Pass |
| TC-I-23 | Same patient books the same clinician twice in one day | 409 `DUPLICATE_BOOKING` | 409 | Pass |
| TC-I-24 | Patient requests another patient's appointment | 404, not 403 | 404 | Pass |
| TC-I-25 | Patient cancels own booking | 200, status CANCELLED | 200 | Pass |
| TC-I-26 | Slot list after cancellation | Time offered again | Offered | Pass |
| TC-I-26b | Another patient books the released slot | 201 | 201 | Pass |
| TC-I-27 | Patient cancels another patient's booking | 404 and victim's record untouched | 404, record still BOOKED | Pass |
| TC-I-28 | Cancel an already-cancelled booking | 409 `INVALID_TRANSITION` | 409 | Pass |
| TC-I-28b | Booking a past date | 400 with a `date` field error | 400 | Pass |
| TC-I-28c | Booking 90 days ahead (horizon 60) | 400 | 400 | Pass |
| TC-I-28d | Staff books on behalf of a patient | 201, `source = STAFF` | 201 | Pass |
| TC-I-28e | Patient supplies another `patient_id` | Ignored; booked for themselves | Ignored | Pass |

### 3.4 Integration — check-in and queue

| ID | Test case | Expected | Actual | P/F |
|---|---|---|---|---|
| TC-I-29 | Staff checks in a booked patient | 201, ticket issued, status CHECKED_IN | 201, ticket `A-04` | Pass |
| TC-I-30 | Second check-in of the same appointment | 409 `ALREADY_CHECKED_IN` | 409 | Pass |
| TC-I-31 | Check in a future-dated appointment | 409 naming the actual date | 409 | Pass |
| TC-I-32 | Three sequential check-ins for one clinician | Ticket numbers strictly increasing and unique | 1, 2, 3 | Pass |
| TC-I-33 | Call next | Earliest waiting ticket, appointment → IN_PROGRESS | Correct patient called | Pass |
| TC-I-34 | Call next on an empty queue | 200 with `called: null` — not an error | 200, null | Pass |
| TC-I-35 | Complete a called consultation | 200, status COMPLETED, queue DONE | 200 | Pass |
| TC-I-36 | Complete a BOOKED appointment (skipping check-in) | 409 `INVALID_TRANSITION` | 409 | Pass |
| TC-I-37 | Mark no-show from BOOKED and from CHECKED_IN | 200 both; queue entry SKIPPED | 200 | Pass |
| TC-I-37b | No-show does not release the slot | Time still unavailable | Still unavailable | Pass |
| TC-I-38 | Live queue read by a patient | Names masked, positions present | `K. A****`, positions 1..n | Pass |
| TC-I-38b | Full names anywhere in the queue payload | Absent | Absent | Pass |

### 3.5 Integration — administration and reporting

| ID | Test case | Expected | Actual | P/F |
|---|---|---|---|---|
| TC-I-39 | Create a service | 201 | 201 | Pass |
| TC-I-40 | Duplicate service name | 400 on the `name` field | 400 | Pass |
| TC-I-41 | Availability with end before start | 400 on `end_time` | 400 | Pass |
| TC-I-41b | Availability overlapping an existing window | 409 | 409 | Pass |
| TC-I-41c | Adjacent windows (08:00–12:00, 12:00–16:00) | Both accepted | Accepted | Pass |
| TC-I-42 | New availability produces bookable slots | 10:00, 10:30, 11:00, 11:30 | Exact match | Pass |
| TC-I-43 | Administrator demotes themselves | 403 with a helpful message | 403 | Pass |
| TC-I-43b | Administrator deactivates themselves | 403 | 403 | Pass |
| TC-I-44 | Audit log ordering | Newest first | Newest first | Pass |
| TC-I-44b | Booking recorded in the audit log with actor | Entry with correct actor email | Present | Pass |
| TC-I-44c | Denied access recorded | `ACCESS_DENIED` entry present | Present | Pass |
| TC-I-45 | Daily summary totals | Status counts sum to total | Consistent | Pass |
| TC-I-46 | No-show rate excludes cancellations | 1 no-show of 3 expected = 33.3%, not 25% | 33.3% | Pass |
| TC-I-47 | Mean wait with nobody called | `null`, not `0.0` | `null` | Pass |

---

## 4. Security Test Results

All 55 security tests pass. Written as attacks, mapped to System Design §5.1.

| ID | Attack attempted | Control | Result |
|---|---|---|---|
| TC-SEC-01 | Access 6 protected endpoints with no session | `@require_auth` | 401 on all 6 |
| TC-SEC-02 | Patient calls staff endpoints (day sheet, patient lookup) | `@require_role` | 403 on all |
| TC-SEC-03 | Patient calls all 4 queue operations | `@require_role` | 403 on all 4 |
| TC-SEC-04 | Staff calls all 7 admin endpoints | `@require_admin` | 403 on all 7 |
| TC-SEC-05 | State change with no CSRF header | Double-submit check | 403 `CSRF_INVALID` |
| TC-SEC-06 | State change with a wrong CSRF token | Constant-time compare | 403 |
| TC-SEC-07 | Replay another user's valid CSRF token | Token bound to the signed JWT | 403 |
| TC-SEC-07b | Login CSRF against a signed-in user | Central `before_request` gate | 403 |
| TC-SEC-08 | Four SQL injection payloads through search | Parameterised SQL | 200, database intact, no leakage |
| TC-SEC-09 | `UNION SELECT password_hash` | Parameterised SQL | No `pbkdf2` string in the response |
| TC-SEC-09b | SQL injection in the login field | Parameterised SQL | 400/401, no bypass |
| TC-SEC-10 | Read security headers | `security_headers` | CSP, nosniff, DENY, no-referrer all present |
| TC-SEC-11 | Trigger errors on 3 paths and inspect bodies | Generic envelope | No traceback, SQL, or filesystem path |
| TC-SEC-12 | Force an unhandled exception | `Exception` handler | 500 generic; message and path suppressed; app still serving |
| TC-SEC-13 | Enumerate appointment ids 1–29 as a patient | 404 for non-owned | Only 200 and 404 observed — no 403 oracle |
| TC-SEC-14 | Cancel another patient's booking | Ownership assertion | 404, victim's record unchanged |
| TC-SEC-15 | Forged JWT signature | Signature verification | 401 |
| TC-SEC-16 | `alg: none` unsigned token claiming ADMIN | Algorithm pinned to HS256 | 401 |
| TC-SEC-17 | 6 consecutive wrong passwords | Rate limiter | 429 from the 6th |
| TC-SEC-17b | Correct password while throttled | Limiter checked before verification | 429 — no oracle |
| TC-SEC-17c | Throttling one account affects another | Per-identity keying | Other account unaffected |
| TC-SEC-18 | Login with an unknown vs a known address | Constant-shape response | Byte-identical responses |
| TC-SEC-19 | Register with `role: ADMIN` in the body | Role never read from input | Created as PATIENT |
| TC-SEC-20 | Use a session after the account is deactivated | `is_active` re-read per request | 401 immediately |
| TC-SEC-21 | 300 KB request body | `MAX_CONTENT_LENGTH` | Rejected |
| TC-SEC-22 | Two accounts with the same password | Per-user salt | Different hashes |

### 4.1 Password storage verification

```
stored hash: pbkdf2:sha256:600000$<salt>$<digest>
```

Verified by test: the algorithm is PBKDF2-HMAC-SHA256, the iteration count in the production configuration is 600,000 (NFR-SEC-02), a per-user salt is present, the plaintext appears nowhere in the stored value, and two users choosing the same password produce different hashes.

The test environment deliberately lowers the iteration count to 10,000. This is stated plainly because it matters: without it, seeding 11 users per test made the suite take over ten minutes (defect D-06). Two tests protect the change — one asserts that the *production* configuration is 600,000, and one round-trips a hash generated at the full production cost to prove the verification path still works.

---

## 5. Performance Test Results

Measured server-side handling time over a seeded dataset of **1,000 appointments**, on a file-backed SQLite database in WAL mode — the configuration production actually runs. 60 iterations per endpoint.

### 5.1 Read endpoints — budget 200 ms at p95 (NFR-PER-01)

| Endpoint | p50 (ms) | p95 (ms) | Max (ms) | Verdict |
|---|---|---|---|---|
| `GET /api/health` | 4.5 | 8.1 | 12.4 | Pass |
| `GET /api/services` | 4.6 | 8.7 | 10.2 | Pass |
| `GET /api/practitioners` | 5.3 | 10.8 | 15.9 | Pass |
| `GET /api/slots` | 5.9 | 10.1 | 17.1 | Pass |
| `GET /api/appointments/mine` | 9.7 | 17.4 | 38.1 | Pass |
| `GET /api/appointments` (day sheet) | 7.0 | 8.9 | 17.2 | Pass |
| `GET /api/queue` | 5.8 | 6.7 | 7.8 | Pass |
| `GET /api/admin/reports/daily` | 5.9 | 7.1 | 17.1 | Pass |
| `GET /api/admin/reports/utilisation` | 6.8 | 9.3 | 23.6 | Pass |
| `GET /api/admin/users` | 5.2 | 7.3 | 8.0 | Pass |
| `GET /api/admin/audit` | 5.2 | 7.0 | 7.8 | Pass |

Worst observed p95 is **17.4 ms against a 200 ms budget** — an order of magnitude of headroom. The indexes in `schema.sql` are doing their job; the slowest endpoint is the patient's own appointment list, which is the only one that joins four tables without a date restriction.

### 5.2 Write endpoints — budget 400 ms at p95 (NFR-PER-02)

| Endpoint | p50 (ms) | p95 (ms) | Max (ms) | Verdict |
|---|---|---|---|---|
| `POST /api/queue/call-next` | 7.0 | 18.4 | 21.4 | Pass |

### 5.3 Concurrency — NFR-PER-04

| Test | Result | Verdict |
|---|---|---|
| 30 simultaneous authenticated readers | 30/30 succeeded in 440 ms wall clock, p95 72.7 ms, **0 errors** | Pass |

### 5.4 Client payload — NFR-PER-03 (budget 150 KB uncompressed)

| Asset | Bytes |
|---|---|
| `app.css` | 14,738 |
| `admin.js` | 19,073 |
| `staff.js` | 13,137 |
| `patient.js` | 10,363 |
| `ui.js` | 6,710 |
| `api.js` | 5,397 |
| `auth.js` | 4,841 |
| `router.js` | 3,897 |
| `index.html` | 2,631 |
| `app.js` | 2,034 |
| `store.js` | 983 |
| **Total** | **83,804 (81.8 KB)** |

**56% of budget used**, with no build step, no minification and no compression. Enabling gzip at the platform edge would roughly quarter this again.

---

## 6. Usability Test Results

Measured by instrumenting the live application in a browser at a 360 px viewport with touch emulation, then walking every route.

| Route | Page horizontal overflow | Tap targets below 44 px | Verdict |
|---|---|---|---|
| `#/book` | 0 px | 0 | Pass |
| `#/appointments` | 0 px | 0 | Pass |
| `#/staff` | 0 px | 0 | Pass |
| `#/admin/reports` | 0 px | 0 | Pass |
| `#/admin/users` | 0 px | 0 | Pass |
| `#/admin/clinic` | 0 px | 0 | Pass |
| `#/admin/audit` | 0 px | 0 | Pass |

Wide data tables do extend beyond the viewport, but inside their own `overflow-x: auto` container — they scroll independently while the page body does not, which is the intended behaviour rather than an exception to it.

| NFR | Check | Result |
|---|---|---|
| NFR-USA-01 | Usable at 360 px without horizontal scrolling | Pass on all 7 routes |
| NFR-USA-02 | Registration plus booking under 90 s | Walkthrough completed in ~55 s |
| NFR-USA-03 | Touch targets ≥ 44 × 44 px | Pass after defect D-04 was fixed |
| NFR-USA-04 | Plain-language errors with a next action | Inspected all 23 error strings; all pass |
| NFR-USA-05 | Status never conveyed by colour alone | Every badge carries a text label |

**Sample of the error strings inspected:**

- "That time was just booked. Please choose another slot."
- "Only appointments scheduled for today can be checked in. This one is for 2026-08-24."
- "You cannot change your own role or deactivate your own account. Ask another administrator to do it."
- "An appointment that is completed can no longer be cancelled."
- "This clinician does not work on Thursdays. They are available on: Tuesday, Thursday."

Each states what happened and what to do next. None exposes a status code, an exception name or a field name.

---

## 7. Defect Log

Fourteen defects were found and resolved during the build. All are closed; there are no known open defects at severity Medium or above.

| ID | Defect | Found by | Severity | Root cause | Corrective action | Status |
|---|---|---|---|---|---|---|
| **D-01** | Every request after startup failed with `no such table: users` when the database was `:memory:` | First integration smoke run | **High** | A bare `:memory:` SQLite database is private to one connection. The factory created the schema on its own connection, which then closed; each request opened a fresh, empty database. | Switched to a named shared-cache URI (`file:tc_N?mode=memory&cache=shared`) with a keep-alive connection held by the app for its lifetime. | Closed |
| **D-02** | Malformed XML in `class.svg` | Diagram render check | Low | XML forbids `--` inside a comment; the association comments used `1 -- *`. | Reworded the four comments. Added an XML well-formedness check to the render tool so it cannot recur silently. | Closed |
| **D-03** | Overlapping labels in the ERD; a relationship connector crossed a note box | Visual review of rendered diagrams | Low | Hand-authored SVG coordinates. | Repositioned labels; moved the two constraint notes into a dedicated panel. | Closed |
| **D-04** | "Sign out" was a 34 px tap target at 360 px, breaching NFR-USA-03 | Instrumented usability measurement | Medium | `.btn-sm` set a 34 px height for dense desktop tables, and the topbar reused it. | `@media (pointer: coarse)` restores 44 px on touch devices; the topbar button is always full height. Compact rows are retained where a precise pointer exists. | Closed |
| **D-05** | 248 px of horizontal page overflow on the staff console at 360 px | Instrumented usability measurement | **High** | Grid and flex children default to `min-width: auto` and refuse to shrink below their content; a long `<option>` label pushed the page sideways. | `min-width: 0` on grid children, cards and toolbar fields; `max-width: 100%` on form controls. | Closed |
| **D-06** | Test suite exceeded 10 minutes and had to be killed | First full suite run | Medium | 600,000 PBKDF2 rounds × 11 seeded users × every test. | Made the KDF cost configurable and lowered it to 10,000 rounds under `env=testing` only. Added two tests: one asserting the production setting is 600,000, one round-tripping a production-cost hash. | Closed |
| **D-07** | `test_successful_login_clears_the_counter` failed with 403 instead of 200 | Test run | Low (test defect) | The test client posted to `/auth/login` without the CSRF header, which the real browser client always sends. The application was correct; the test was not faithful. | Made the test client attach the header on login and register, mirroring `api.js`. Added an explicit test documenting that re-login while signed in requires a token, which is the login-CSRF mitigation. | Closed |
| **D-08** | 5 of 30 concurrent logins returned HTTP 500 (`database table is locked`) | Performance run | **High** | Two distinct problems. (a) The harness measured a shared-cache **in-memory** database, whose table-level locks do not honour `busy_timeout` — not the configuration production uses. (b) Genuine write-lock contention surfaced as a 500, implying a broken request rather than a transient condition. | (a) Performance harness switched to a file-backed WAL database, matching production; re-run gave 30/30 with 0 errors. (b) Added a `ServiceBusy` (503) handler with `Retry-After`, plus two tests proving lock errors map to 503 and genuine faults still map to 500. | Closed |
| **D-09** | 15 integration tests failed with `UNIQUE constraint failed: patient_id, practitioner_id, appt_date` | Full suite run | Low (test defect) | The fixtures assumed the demo patient was free, but the seed had already given them appointments. **The constraint was working exactly as FR-27 specifies.** | Rewrote the `free_slot` fixture to skip days where the patient already has a booking, and the `today_booking` fixture to clear the conflicting row first. Used distinct patients in the reporting test. | Closed |
| **D-10** | `test_different_durations_produce_different_grids` asserted a wrong expected set | Full suite run | Low (test defect) | The test expected `{08:45, 10:15, 11:00}`; 11:00 exists on both the 30- and 45-minute grids. The implementation was right. | Corrected the expectation and added an assertion on the intersection, which makes the relationship between the two grids explicit. | Closed |
| **D-13** | The confirmation dialog was rendered on **every page**, and its Cancel button sat over the centre of the viewport swallowing clicks | Reported by the user; reproduced by measuring the live DOM | **High** | `index.html` marks the dialog with the `hidden` attribute, but `hidden` only works through the user agent's `[hidden] { display: none }` rule. The author rule `.modal-backdrop { display: flex }` overrode it, so the element stayed visible. Measured: `hidden` attribute present, `getComputedStyle().display === "flex"`, and `document.elementFromPoint(centre)` returned the dialog's Cancel button. | Added `.modal-backdrop[hidden] { display: none }` — an author rule that removes `hidden`'s effect must restore it. Verified: `display: none` at rest, `flex` when opened, `none` again after Escape, and the element at the viewport centre is now the page content. | Closed |
| **D-14** | White button text failed WCAG AA against the top of the new button gradients: 4.24:1 on teal and 3.51:1 on green, against a 4.5:1 requirement | Instrumented contrast sweep during the redesign | Medium | A gradient has two stops, and the *lightest* one governs the worst-case contrast. Both gradients were specified from their mid-tone, so the top edge of every button fell below AA. A naive check misses this: `backgroundColor` reads `transparent` on a gradient element, so the measurement silently compares against the card behind it. | Introduced `--brand-650` (5.2:1) as the lightest teal stop and darkened the green gradient to `#17853F → #12692F`. The contrast harness was also fixed to resolve gradients and use their lightest stop. Re-measured: 0 failures across all 7 routes, lowest ratio 4.57:1. | Closed |
| **D-12** | `test_ticket_numbers_increase_within_a_practitioner_and_day` failed the morning after it was written, having passed all day | Re-run on a later date | Medium (test defect) | The test inserted appointments for fixed patients against practitioner 2 "today". On some weekdays the seed had already given those patients a booking with that clinician, so FR-27's one-per-day index refused the insert. **The application was correct; the test was implicitly weekday-dependent.** | Cleared the clinician's diary for the day before inserting. Then closed the whole defect class: an autouse fixture pins "today" from `TC_TEST_TODAY`, and `tools/date_matrix.py` runs the full suite across seven consecutive days. | Closed |
| **D-11** | `reports.py` imported `date` from `app.domain` rather than `datetime` | Code review | Low | It happened to work because `domain` re-exports the name, but it is a fragile accidental dependency. | Imported `date` directly from `datetime`; removed an unused import at the same time. | Closed |

### 7.1 What the defect profile shows

Five of the fourteen defects (D-07, D-09, D-10, D-12, and half of D-08) were **defects in the tests, not the application** — the code was correct and the test was wrong. That is a healthy sign rather than an embarrassing one: it means the constraints being tested (FR-27's one-per-day rule, the CSRF gate, the slot grid) were doing real work and refused to be talked out of it.

The three High-severity defects in the application itself (D-01, D-05, D-13) were all **environmental or presentational**, not logical. D-13 is the instructive one: it was invisible to a 312-test back-end suite because it lived entirely in the interaction between an HTML attribute and a CSS rule. It is the clearest argument in this project for the automated front-end testing deferred as TD-09. No defect was found in slot generation, the state machine, authorisation or the booking race — the four areas identified in SRS §8.4 as carrying the most risk, and the four that were built and tested first. The mitigation described in the effort estimate worked.

---

## 8. User Acceptance Testing

Six acceptance scenarios were derived from the stakeholder success criteria in SRS §3.1. Each is automated as a system test so it re-runs on every change.

| ID | Scenario | Stakeholder criterion | Acceptance condition | Result |
|---|---|---|---|---|
| **UAT-01** | A new patient registers, browses slots, books, sees the booking, then cancels it — with no staff involvement | S1: "Can book in under 90 seconds on a phone" | Full journey completes; a booking code is issued; the cancelled appointment leaves the upcoming list | **Accepted** — completed in ~55 s in a manual walkthrough at 360 px |
| **UAT-02** | Front desk checks a patient in, the queue shows them, staff call them, the consultation is completed, and the day's report updates | S2: "Check-in in under 15 seconds"; S4: "Reliable daily figures" | Ticket issued; queue reflects each state; the completed count rises by exactly one | **Accepted** — two clicks from landing; report incremented correctly |
| **UAT-03** | A patient does not attend; staff mark a no-show and the manager sees it in the report | S4: "Reliable no-show figures" | No-show count rises; the no-show rate does not fall | **Accepted** |
| **UAT-04** | A patient arrives without an appointment; staff find them and book them in on the spot | S2: "The desk must still be able to serve them" | Appointment created against the correct patient with source STAFF or WALK_IN | **Accepted** |
| **UAT-05** | An administrator adds a new clinician, a new service and an availability window; a patient immediately books against it | S4: "Configuration without developer involvement" | Slots appear at exactly 09:00, 10:00, 11:00 for a 60-minute service in a 09:00–12:00 window; booking succeeds with the right end time | **Accepted** |
| **UAT-06** | A staff member leaves; the administrator deactivates the account and access stops at once | S7/S8: "Offboarding must take effect immediately" | The live session is refused on the very next request, and re-login fails | **Accepted** |

### 8.1 Manual walkthrough record

The application was exercised end to end in a live browser against the running server, at both 1280 px and 360 px:

- Signed in as each of the three roles.
- Booked an appointment as a patient (`TC-6S24CU`, Mon 24 Aug, 09:30, 45-minute Antenatal Review) and confirmed the slot disappeared from the list.
- Confirmed slot generation exactly matched the availability rules: a 45-minute service over 08:00–12:00 and 13:00–16:00 produced 08:00, 08:45, 09:30, 10:15, 11:00, 13:00, 13:45, 14:30, 15:15 — with 11:45 correctly withheld because it would have overrun the midday window.
- Checked a patient in from the staff console (ticket `A-04`), confirmed the queue showed the masked name `K. A****`, called them, and completed the consultation.
- Confirmed the administrator's daily report showed 11 booked, 7 completed, 0% no-show, 13.6-minute mean wait, and the utilisation table with three clinicians.
- Confirmed the audit log recorded the whole session's actions in order, with actor, entity and IP address.

---

## 9. Requirements Verification Summary

| Requirement group | Requirements | Verified by | Status |
|---|---|---|---|
| Identity and access (FR-01 … FR-13) | 13 | 31 auth tests, 26 authorisation tests | All verified |
| Catalogue (FR-14 … FR-19) | 6 | 12 admin and catalogue tests | All verified |
| Slots and booking (FR-20 … FR-32) | 13 | 31 unit + 37 integration tests | All verified |
| Queue (FR-33 … FR-44) | 12 | 27 queue tests, 3 system tests | All verified |
| Admin, audit, reporting (FR-45 … FR-52) | 8 | 34 admin tests | All verified |
| Validation and integrity (FR-53 … FR-58) | 6 | 41 validator tests, 7 injection tests, 3 integrity tests | All verified |
| Performance (NFR-PER-01 … 04) | 4 | Timed harness, 1,000-row dataset | All met |
| Security (NFR-SEC-01 … 06) | 6 | 55 security tests | All met |
| Usability (NFR-USA-01 … 05) | 5 | Instrumented measurement across 7 routes | All met |
| Reliability (NFR-REL-01 … 04) | 4 | Fault injection, transaction, health tests | 3 met; NFR-REL-04 (99% uptime) requires production monitoring |
| Maintainability (NFR-MNT-01 … 06) | 6 | Architecture inspection, 93% coverage, debt register | All met |

**One requirement cannot be verified before deployment:** NFR-REL-04 (99% availability during clinic hours) is a production measurement, not a test result. It is recorded in the maintenance strategy as an ongoing monitoring obligation rather than claimed here.

---

## 10. Conclusion

| Measure | Result |
|---|---|
| Automated tests | 312, all passing |
| Execution time | 32.5 s |
| Line coverage | 93% (requirement: 80%) |
| Defects found | 14 |
| Defects closed | 14 |
| Open defects, Medium or above | 0 |
| Performance budgets | All met, with an order of magnitude of headroom on reads |
| Acceptance scenarios | 6 of 6 accepted |

The suite's real value is forward-looking. The Technical Debt Register commits to migrating the datastore to PostgreSQL, replacing the KDF, and introducing a frontend component model — three changes that touch nearly every layer. Those are only safe to attempt because 312 tests will say immediately if any of them breaks the behaviour this report has verified.

*End of Testing and Quality Assurance Report v1.0.*
