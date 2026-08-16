# Software Requirements Specification (SRS)

## TheClinicue: Outpatient Appointment & Queue Management System

**Document version:** 1.0
**Status:** Baselined (end of Phase 1)
**Prepared by:** [STUDENT NAME]
**Student ID:** [STUDENT ID]
**Date:** 12 August 2026
**Standard followed:** Adapted from IEEE Std 830-1998 / ISO-IEC-IEEE 29148:2018

---

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification defines the functional and non-functional requirements for **TheClinicue**, a web-based outpatient appointment booking and patient-queue management system intended for small and medium-sized community clinics and polyclinics.

The document is written for three audiences:

- **The examiner / assessor**, who requires evidence of systematic requirements engineering.
- **The developer** (the author), who uses the specification as the authoritative input to design, estimation and implementation.
- **Prospective clinic stakeholders**, who must be able to confirm that the specified behaviour matches their operational reality.

Every requirement in this document is uniquely identified, prioritised and traceable forward into design artefacts, source code and test cases. The traceability matrix in Section 9 closes that loop.

### 1.2 Scope

TheClinicue is a single deployable web application consisting of a REST API, a relational datastore and a responsive browser client. It delivers:

- Self-service appointment booking by patients against real practitioner availability.
- Automatic, conflict-free generation of bookable time slots.
- A digital check-in and calling queue that replaces the physical paper-and-shouting queue at the clinic front desk.
- Role-based operational dashboards for reception staff and clinic administrators.
- Basic operational reporting (attendance, no-show rate, utilisation, waiting time).

TheClinicue **is not** an Electronic Medical Record (EMR) system. It does not store clinical notes, diagnoses, prescriptions, laboratory results or billing data. This boundary is deliberate: it keeps the 48-hour scope achievable and keeps the system out of the highest tier of health-data regulation while still delivering measurable operational value.

### 1.3 Definitions, Acronyms and Abbreviations

| Term | Definition |
|---|---|
| Practitioner | A doctor, nurse-practitioner or other clinician who consults with patients. |
| Service | A category of consultation (e.g. General Consultation, Antenatal) with a fixed nominal duration. |
| Availability rule | A recurring weekly window during which a practitioner accepts appointments. |
| Slot | A discrete bookable time interval derived from an availability rule minus existing bookings. |
| Check-in | The act of a patient physically arriving and being admitted to the day's queue. |
| Ticket number | The sequential number assigned to a patient on check-in for a given practitioner and day. |
| Queue | The ordered list of checked-in patients awaiting consultation on a given day. |
| No-show | A booked appointment whose patient never checked in. |
| RBAC | Role-Based Access Control. |
| JWT | JSON Web Token, used here as a stateless session credential. |
| CSRF | Cross-Site Request Forgery. |
| UCP | Use Case Points, the effort-estimation technique applied in this project. |
| MoSCoW | Must have / Should have / Could have / Won't have prioritisation scheme. |
| SPA | Single Page Application. |

### 1.4 References

Full bibliographic details are given in Section 19 of the consolidated Project Documentation. Key references informing this SRS are IEEE Std 830-1998, ISO/IEC/IEEE 29148:2018, Karner's Use Case Points method (1993), and the OWASP Application Security Verification Standard v4.0.

### 1.5 Document Overview

Section 2 gives the overall product description and problem context. Section 3 identifies stakeholders. Sections 4 and 5 specify functional and non-functional requirements respectively. Section 6 states external interface requirements. Section 7 records constraints and assumptions. Section 8 defines the 48-hour scope boundary. Section 9 provides the requirements traceability matrix.

---

## 2. Overall Description

### 2.1 Problem Statement

Community clinics across much of West Africa (and in resource-constrained primary care generally) operate an essentially undigitised outpatient flow. A patient who needs to see a clinician typically:

1. Travels to the clinic without knowing whether the clinician is available that day.
2. Joins an undifferentiated physical queue on a first-come-first-served basis.
3. Waits, frequently for three to five hours, with no visibility of position or expected wait.
4. Is often turned away when the clinician's daily capacity is exhausted.

The consequences are concrete and measurable:

- **Patient cost.** Lost wages, transport spent on wasted journeys, and (critically) care avoidance. Patients with non-acute but progressive conditions defer visits because the time cost is unpredictable.
- **Clinic cost.** Reception staff spend a large fraction of the working day on manual queue arbitration and dispute resolution rather than on clinical support. Practitioner idle gaps sit alongside overflowing waiting rooms because arrival is unsmoothed.
- **Data blindness.** Clinic managers have no reliable figures for daily attendance, no-show rates, practitioner utilisation or waiting time, so they cannot justify staffing changes or identify bottlenecks.
- **Crowding risk.** Dense, long-duration waiting rooms are an infection-control hazard, a lesson reinforced across the sector since 2020.

Existing commercial practice-management suites do address this, but they are priced per-seat in hard currency, assume reliable broadband, and bundle EMR functionality that a small clinic neither needs nor is licensed to operate. The result is a genuine gap: **there is no lightweight, low-bandwidth, low-cost tool that solves only the appointment-and-queue problem.**

### 2.2 Product Perspective

TheClinicue is a new, self-contained system. It has no mandatory integration with existing clinic software, which is the correct architectural decision for the target market - most target clinics have no existing software to integrate with. It is designed to be deployable by a single non-specialist administrator onto a low-cost cloud host, and to be usable on the low-end Android devices that dominate the patient population.

The system replaces a manual process rather than an incumbent system. This means adoption risk, not migration risk, is the dominant deployment concern, and it is addressed through deliberate design choices recorded in NFR-USA-01 through NFR-USA-04.

### 2.3 Product Functions (summary)

| Function group | Summary |
|---|---|
| Identity | Patient self-registration; authenticated login for all roles; secure session management; logout. |
| Discovery | Browse active services and practitioners; view real, conflict-free bookable slots for a chosen date. |
| Booking | Create, view and cancel appointments; receive a human-readable booking reference. |
| Front desk | Check patients in, register walk-ins, view the day's schedule, search patients. |
| Queue | Assign ticket numbers, call the next patient, mark consultations in progress / complete / no-show, publish live queue state. |
| Administration | Manage users, roles and account status; manage services, practitioners and availability rules; inspect the audit log. |
| Reporting | Daily and range-based operational metrics: bookings, attendance, no-show rate, utilisation, mean wait. |

### 2.4 User Characteristics

| User class | Technical skill | Device | Frequency of use | Design implication |
|---|---|---|---|---|
| Patient | Low. Comfortable with WhatsApp; unfamiliar with form-heavy web apps. | Low-end Android phone, intermittent 3G. | Occasional (weeks apart). | Minimal fields, large tap targets, no jargon, works at 360 px width, tolerant of reload. |
| Reception staff | Moderate. Uses a computer daily. | Shared clinic desktop or tablet. | Continuous during clinic hours. | Speed over beauty; keyboard-reachable; few clicks per patient; must not lose state on refresh. |
| Clinic administrator | Moderate to high. Often the clinic manager or lead nurse. | Desktop. | Weekly configuration, daily reporting glance. | Clear, reversible configuration; visible audit trail. |

### 2.5 Operating Environment

- **Client:** Any evergreen browser (Chrome, Firefox, Safari, Edge) on Android, iOS, Windows, macOS or Linux. No installation. No client-side build artefacts.
- **Server:** Linux container running Python 3.11+ with a WSGI server (Gunicorn). Single process, multi-worker.
- **Datastore:** SQLite 3 file in the reference deployment; the data access layer is written so that migration to PostgreSQL is a bounded change (see Technical Debt item TD-01).
- **Network:** Assumed intermittent and low-bandwidth. Total initial page weight is budgeted at under 150 KB uncompressed.

---

## 3. Stakeholders

### 3.1 Stakeholder Register

| # | Stakeholder | Type | Interest in the system | Influence | Key success criterion |
|---|---|---|---|---|---|
| S1 | Patient | Primary user | Reduce time wasted; know when to arrive; avoid futile journeys. | Low individually, decisive collectively (adoption). | Can book in under 90 seconds on a phone. |
| S2 | Reception / records staff | Primary user | Remove manual queue arbitration; reduce conflict at the desk. | High - they are the daily operators; non-adoption kills the system. | Check-in a patient in under 15 seconds. |
| S3 | Practitioner (doctor / nurse) | Primary user (indirect) | Predictable, smoothed patient flow; fewer interruptions. | High - controls availability. | Accurate view of who is next. |
| S4 | Clinic administrator / manager | Primary user, sponsor | Operational visibility; staffing justification; cost control. | Decisive - approves procurement. | Reliable daily no-show and utilisation figures. |
| S5 | Clinic owner / board | Sponsor | Return on a small investment; reputation. | Decisive (budget). | Measurable reduction in average wait. |
| S6 | Ministry / district health directorate | Regulator, external | Service-quality reporting; data protection compliance. | Medium (compliance constraints). | No unlawful processing of health data. |
| S7 | System maintainer | Internal | Maintainable, debuggable, cheaply hostable code. | Medium (post-delivery cost). | Can diagnose a production fault from logs and audit trail. |
| S8 | Data protection authority | Regulator, external | Lawful handling of personal data (Ghana Data Protection Act 2012, Act 843). | Medium. | Minimal PII collected; access controlled and logged. |

### 3.2 Requirements Elicitation Method

Because a 48-hour project window does not permit a full field study, requirements were elicited using four complementary techniques, and the provenance of each requirement is recorded so that the reader can judge its confidence:

1. **Structured stakeholder proxy analysis.** For each stakeholder in the register, the author enumerated goals, pain points and failure modes from the perspective of that role, and derived candidate requirements from each pain point.
2. **Process observation and modelling.** The existing manual outpatient process was modelled as an as-is activity flow. Each manual step was classified as *automate*, *support*, or *leave alone*. Steps classified *automate* or *support* generated requirements; the remainder defined the system boundary.
3. **Document and domain analysis.** Publicly documented outpatient-flow practice and comparable systems were analysed to identify the conventional feature set, which was then filtered against the 48-hour constraint.
4. **Assumption registration.** Every requirement that rests on an unvalidated belief about clinic operation is flagged in Section 7.2 as an assumption requiring confirmation before a real pilot. This is the honest treatment of proxy elicitation: the requirements are defensible, but they are not a substitute for field validation, and the document says so.

---

## 4. Functional Requirements

### 4.1 Notation

Each requirement carries an identifier, a statement, a MoSCoW priority, a rationale and a verification method. Priorities were assigned by scoring each candidate requirement on two axes (**stakeholder value** (does removing it break the core value proposition?) and **implementation cost** (estimated person-hours)) and are the direct input to the scope decision in Section 8.

Verification methods: **T** = automated test, **D** = demonstration, **I** = inspection, **A** = analysis.

### 4.2 Identity and Access Management

| ID | Requirement | Priority | Rationale | Verify |
|---|---|---|---|---|
| FR-01 | A visitor shall be able to self-register as a Patient by supplying full name, email, phone number and password. | Must | Self-service registration is the precondition for self-service booking; staff-mediated registration would reproduce the queue it removes. | T, D |
| FR-02 | The system shall reject registration when the email is already in use, and shall report this without revealing whether the existing account is active. | Must | Prevents duplicate identities; avoids account enumeration. | T |
| FR-03 | The system shall enforce a password policy of at least 8 characters including at least one letter and one digit. | Must | Baseline credential strength (OWASP ASVS 2.1). | T |
| FR-04 | The system shall store passwords only as salted one-way hashes using PBKDF2-HMAC-SHA256. | Must | Plaintext or reversible storage is an unacceptable breach risk. | I, T |
| FR-05 | A registered user shall be able to log in with email and password and receive an authenticated session. | Must | Foundation of all authorised behaviour. | T, D |
| FR-06 | The system shall issue the session credential as a signed JWT in an HttpOnly, SameSite=Lax cookie, with the Secure flag set when served over HTTPS. | Must | Prevents session theft via XSS and limits CSRF exposure. | I, T |
| FR-07 | The system shall require a CSRF token, supplied in a request header and matching a non-HttpOnly cookie, on every state-changing request. | Must | Double-submit defence against CSRF, required because the session lives in a cookie. | T |
| FR-08 | The system shall lock out authentication attempts from an identifier after 5 consecutive failures within 15 minutes. | Should | Mitigates online password guessing. | T |
| FR-09 | A user shall be able to log out, invalidating the session cookie. | Must | User control over session lifetime on shared clinic devices. | T, D |
| FR-10 | The system shall expose an endpoint returning the authenticated user's own profile and role. | Must | Enables the client to render role-appropriate UI. | T |
| FR-11 | The system shall deny access to any protected resource when no valid session is presented, returning HTTP 401. | Must | Core access control. | T |
| FR-12 | The system shall deny access to a resource when the authenticated user's role is insufficient, returning HTTP 403 and recording the attempt. | Must | Core authorisation; separation of patient, staff and admin capability. | T |
| FR-13 | The system shall refuse authentication for a deactivated account. | Must | Enables offboarding of staff without deleting records. | T |

### 4.3 Service and Practitioner Catalogue

| ID | Requirement | Priority | Rationale | Verify |
|---|---|---|---|---|
| FR-14 | The system shall maintain a catalogue of services, each with a name, description, nominal duration in minutes and active flag. | Must | Duration drives slot generation; the active flag allows withdrawal without deleting history. | T, D |
| FR-15 | The system shall maintain a register of practitioners, each with a name, specialty, room and active flag. | Must | Slots and queues are owned by a practitioner. | T, D |
| FR-16 | An Administrator shall be able to create, update and deactivate services and practitioners. | Must | Clinic configuration changes without developer involvement. | T, D |
| FR-17 | The system shall allow an Administrator to define recurring weekly availability rules for a practitioner as (weekday, start time, end time). | Must | Availability is the source of truth from which slots are generated. | T, D |
| FR-18 | The system shall reject an availability rule whose start time is not strictly earlier than its end time. | Must | Prevents generation of an empty or inverted slot range. | T |
| FR-19 | Any authenticated user shall be able to list active services and active practitioners. | Must | Required to populate the booking form. | T |

### 4.4 Slot Generation and Appointment Booking

| ID | Requirement | Priority | Rationale | Verify |
|---|---|---|---|---|
| FR-20 | The system shall compute the bookable slots for a given practitioner, service and date by partitioning that practitioner's availability windows for that weekday into intervals of the service's nominal duration. | Must | Deterministic, explainable slot generation; the single most important algorithm in the system. | T |
| FR-21 | The system shall exclude from the returned slots any interval that overlaps an existing non-cancelled appointment for that practitioner on that date. | Must | Prevents double-booking, the primary correctness risk. | T |
| FR-22 | The system shall exclude slots for dates in the past, and slots whose start time has already elapsed on the current date. | Must | Booking into the past is meaningless and corrupts reporting. | T |
| FR-23 | The system shall reject a booking request for a date more than 60 days ahead. | Should | Bounds the planning horizon; avoids speculative bookings that inflate no-shows. | T |
| FR-24 | A Patient shall be able to book an available slot, creating an appointment with status BOOKED. | Must | The core value transaction. | T, D |
| FR-25 | The system shall assign each appointment a unique, human-readable reference code of the form TC-XXXXXX. | Must | Patients and staff need a spoken/written handle that is not a database id. | T |
| FR-26 | The system shall atomically re-verify slot availability at the moment of booking and reject the request with HTTP 409 if the slot was taken between listing and submission. | Must | Time-of-check-to-time-of-use race is a real concurrency defect, not a theoretical one. | T |
| FR-27 | The system shall prevent a patient from holding more than one non-cancelled appointment with the same practitioner on the same date. | Should | Prevents accidental duplicate bookings and slot hoarding. | T |
| FR-28 | A Patient shall be able to list their own appointments, filtered by upcoming or past. | Must | Without recall, the booking has no follow-through. | T, D |
| FR-29 | A Patient shall be able to cancel their own BOOKED appointment, releasing the slot. | Must | Cancellation is what converts a no-show into a reusable slot. | T, D |
| FR-30 | The system shall prevent a Patient from viewing, cancelling or otherwise acting on an appointment belonging to another patient. | Must | Insecure Direct Object Reference is the highest-likelihood real vulnerability in this design. | T |
| FR-31 | The system shall prevent cancellation of an appointment that is already COMPLETED, CANCELLED or NO_SHOW. | Must | Protects the integrity of the state machine and of reporting. | T |
| FR-32 | Staff shall be able to book an appointment on behalf of a patient, including for a walk-in. | Should | Not every patient has a phone; the desk must remain able to serve them. | T, D |

### 4.5 Check-in and Queue Management

| ID | Requirement | Priority | Rationale | Verify |
|---|---|---|---|---|
| FR-33 | Staff shall be able to view all appointments for a given date, optionally filtered by practitioner and status. | Must | The day sheet is the front desk's primary working view. | T, D |
| FR-34 | Staff shall be able to check in a patient whose appointment is BOOKED, transitioning it to CHECKED_IN and creating a queue entry. | Must | The transition from schedule to queue is the heart of the system. | T, D |
| FR-35 | The system shall assign each queue entry a ticket number that is sequential within a practitioner and date. | Must | A per-practitioner sequence is what makes the number meaningful to the waiting patient. | T |
| FR-36 | The system shall reject a second check-in for the same appointment. | Must | Duplicate queue entries corrupt ordering and wait-time metrics. | T |
| FR-37 | The system shall reject check-in for an appointment dated other than today. | Must | Prevents accidental check-in of a future or stale appointment. | T |
| FR-38 | Staff shall be able to call the next waiting patient for a practitioner, transitioning the earliest WAITING queue entry to CALLED and its appointment to IN_PROGRESS. | Must | Replaces shouting names across a waiting room. | T, D |
| FR-39 | The system shall complete at most one call operation per practitioner at a time, returning a clear response when the queue is empty. | Must | Deterministic behaviour under concurrent staff clicks. | T |
| FR-40 | Staff shall be able to mark a called consultation COMPLETED, recording the completion time. | Must | Closes the lifecycle and supplies the data for wait-time reporting. | T, D |
| FR-41 | Staff shall be able to mark a BOOKED or CHECKED_IN appointment as NO_SHOW. | Must | No-show rate is the metric the administrator most wants. | T, D |
| FR-42 | The system shall expose the live queue for a practitioner and date, showing ticket number, masked patient name, status and position. | Must | Shared visibility is what removes queue disputes. | T, D |
| FR-43 | The system shall enforce the appointment state machine, rejecting any transition not defined in the design. | Must | An unguarded state machine is the classic source of data corruption in scheduling systems. | T |
| FR-44 | A Patient shall be able to see their own live queue position and ticket number after check-in. | Should | Delivers the "know how long to wait" value proposition directly to the patient. | T, D |

### 4.6 Administration, Audit and Reporting

| ID | Requirement | Priority | Rationale | Verify |
|---|---|---|---|---|
| FR-45 | An Administrator shall be able to list all user accounts with role and status, paginated and searchable. | Must | Basic account governance. | T, D |
| FR-46 | An Administrator shall be able to change a user's role and activate or deactivate an account. | Must | Staff onboarding/offboarding without database access. | T, D |
| FR-47 | The system shall prevent an Administrator from deactivating or demoting their own account. | Should | Prevents the trivial and irreversible lockout of the last administrator. | T |
| FR-48 | The system shall write an immutable audit record for every security-relevant and state-changing action, capturing actor, action, entity, entity id, timestamp and IP address. | Must | Accountability; required for both regulatory defence and production debugging. | T, I |
| FR-49 | An Administrator shall be able to browse the audit log, filtered by actor and action, most recent first. | Should | An audit log that cannot be read has no value. | T, D |
| FR-50 | The system shall produce a daily operational summary for a given date: total booked, checked-in, completed, cancelled, no-show, and no-show rate. | Must | The administrator's core reporting need. | T, D |
| FR-51 | The system shall produce a practitioner utilisation report for a date range, showing appointments handled against slots offered. | Should | Supports staffing decisions, the administrator's stated success criterion. | T, D |
| FR-52 | The system shall report the mean waiting time between check-in and call for a given date. | Should | Quantifies the improvement the system is bought to deliver. | T |

### 4.7 Validation, Errors and Data Integrity

| ID | Requirement | Priority | Rationale | Verify |
|---|---|---|---|---|
| FR-53 | The system shall validate every request payload field for presence, type, length, format and permitted value range before it reaches business logic. | Must | Defence in depth; the majority of injection and corruption defects enter through unvalidated input. | T, I |
| FR-54 | The system shall return errors in a single consistent JSON envelope containing a machine-readable code, a human-readable message and, for validation failures, a per-field detail map. | Must | Consistency is what makes the client's error handling small and the API testable. | T |
| FR-55 | The system shall never disclose stack traces, SQL fragments or internal file paths in an API response. | Must | Information disclosure aids attackers and looks unprofessional to users. | T, I |
| FR-56 | The system shall parameterise every SQL statement; string-interpolated SQL shall not appear in the codebase. | Must | Eliminates SQL injection at the source rather than by filtering. | I, T |
| FR-57 | The system shall enforce referential integrity between appointments, patients, practitioners, services and queue entries at the database level. | Must | The database is the last line of defence against orphaned records. | I, T |
| FR-58 | The system shall escape or otherwise neutralise all user-supplied content when rendering it in the browser. | Must | Prevents stored XSS via names and notes. | I, T |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement | Priority | Measurement |
|---|---|---|---|
| NFR-PER-01 | 95% of read API requests shall complete server-side in under 200 ms with a seeded dataset of 1,000 appointments. | Must | Timed test over the seeded database. |
| NFR-PER-02 | 95% of write API requests shall complete server-side in under 400 ms under the same conditions. | Must | Timed test. |
| NFR-PER-03 | Initial client payload (HTML, CSS, JS) shall not exceed 150 KB uncompressed. | Should | Byte count of served static assets. |
| NFR-PER-04 | The system shall support at least 30 concurrent active users on a single 512 MB container without error. | Should | Concurrency test. |

### 5.2 Security

| ID | Requirement | Priority | Measurement |
|---|---|---|---|
| NFR-SEC-01 | All credentials shall be transmitted only over HTTPS in production. | Must | Deployment inspection; Secure cookie flag. |
| NFR-SEC-02 | Passwords shall be hashed with PBKDF2-HMAC-SHA256 at not fewer than 600,000 iterations with a per-user salt. | Must | Code inspection; hash format assertion in test. |
| NFR-SEC-03 | The session token shall expire no more than 8 hours after issue. | Must | Token claim inspection; expiry test. |
| NFR-SEC-04 | The application shall set Content-Security-Policy, X-Content-Type-Options, X-Frame-Options and Referrer-Policy response headers. | Should | Header assertion test. |
| NFR-SEC-05 | The signing secret shall be supplied by environment variable and shall never be committed to the repository. | Must | Repository inspection; startup guard in production mode. |
| NFR-SEC-06 | Authorisation shall be enforced server-side on every protected endpoint; client-side role checks are presentation only. | Must | Test suite asserts 403 for each cross-role call. |

### 5.3 Usability

| ID | Requirement | Priority | Measurement |
|---|---|---|---|
| NFR-USA-01 | The interface shall be fully usable at a viewport width of 360 px without horizontal scrolling. | Must | Responsive inspection at 360/768/1280 px. |
| NFR-USA-02 | A first-time patient shall be able to complete registration and a booking in under 90 seconds. | Should | Timed usability walkthrough. |
| NFR-USA-03 | Interactive controls shall present a touch target of at least 44 x 44 CSS pixels. | Should | Inspection. |
| NFR-USA-04 | Every error message shall state what went wrong and what the user should do next, in plain language, without technical jargon. | Must | Inspection of all error strings. |
| NFR-USA-05 | Colour shall not be the sole carrier of status information; every status badge shall also carry a text label. | Should | Inspection (WCAG 1.4.1). |

### 5.4 Reliability and Availability

| ID | Requirement | Priority | Measurement |
|---|---|---|---|
| NFR-REL-01 | An unhandled server exception shall return a generic HTTP 500 envelope and shall not terminate the worker process. | Must | Fault injection test. |
| NFR-REL-02 | Booking and check-in shall be transactional: a failure shall leave no partial record. | Must | Transaction rollback test. |
| NFR-REL-03 | The system shall expose an unauthenticated health endpoint reporting service and database status. | Must | Endpoint test; used by the platform health check. |
| NFR-REL-04 | Target availability during clinic hours (07:00-18:00) shall be 99%. | Should | Platform uptime monitoring. |

### 5.5 Maintainability and Portability

| ID | Requirement | Priority | Measurement |
|---|---|---|---|
| NFR-MNT-01 | Business logic shall reside in a service layer separate from HTTP handling, so that it is testable without a web request. | Must | Architecture inspection; service-layer unit tests exist. |
| NFR-MNT-02 | Automated test line coverage of the application package shall be at least 80%. | Must | Coverage report. |
| NFR-MNT-03 | The application shall be startable with a single documented command after installing declared dependencies. | Must | Fresh-environment run. |
| NFR-MNT-04 | All runtime configuration shall come from environment variables with safe development defaults. | Must | Code inspection. |
| NFR-MNT-05 | The system shall run unmodified on Linux, macOS and Windows. | Should | Execution on Windows and Linux container. |
| NFR-MNT-06 | Every identified item of technical debt shall be recorded in a register with cause, impact, priority and proposed resolution. | Must | Technical Debt Register exists and is current. |

### 5.6 Legal and Compliance

| ID | Requirement | Priority | Measurement |
|---|---|---|---|
| NFR-LEG-01 | The system shall collect only the personal data necessary for scheduling: name, email, phone. It shall not collect or store clinical data. | Must | Schema inspection. |
| NFR-LEG-02 | Access to personal data shall be restricted by role and every access-control decision that fails shall be logged. | Must | Test and audit-log inspection. |
| NFR-LEG-03 | Patient names shall be masked in any queue view visible to other patients. | Should | Inspection of the public queue response. |

---

## 6. External Interface Requirements

### 6.1 User Interfaces

A responsive single-page browser client with four role-scoped areas: public (login/register), patient portal, staff console and admin console. Wireframes are given in the System Design section of the consolidated documentation.

### 6.2 Application Programming Interface

A JSON-over-HTTP REST API rooted at `/api`. All requests and responses use `application/json; charset=utf-8`. Authentication is by session cookie; state-changing requests additionally require the `X-CSRF-Token` header. The full endpoint contract is specified in the System Design section.

### 6.3 Software Interfaces

| Interface | Purpose | Version |
|---|---|---|
| Python runtime | Execution environment | 3.11 or later |
| Flask | HTTP routing and request handling | 3.x |
| PyJWT | Session token signing and verification | 2.x |
| Werkzeug security | PBKDF2 password hashing | 3.x |
| SQLite 3 | Persistent datastore | Bundled with Python |
| Gunicorn | Production WSGI server | 21.x or later |

### 6.4 Communications Interfaces

HTTPS on port 443 in production (TLS terminated by the hosting platform); HTTP on a configurable port in development.

---

## 7. Constraints and Assumptions

### 7.1 Constraints

| ID | Constraint | Consequence |
|---|---|---|
| C-01 | Total development effort is capped at 48 elapsed hours by a single developer. | Scope must be cut to the Must-have set plus selected Should-haves; this is the constraint that drives Section 8. |
| C-02 | Deployment must be to a free or near-free hosting tier. | Rules out managed database services in v1.0; forces SQLite and accepts the resulting technical debt (TD-01). |
| C-03 | No budget for third-party SMS or email gateways. | Notifications cannot be delivered out-of-band in v1.0; deferred to v1.1 (FR-59, out of scope). |
| C-04 | Target users are on low-bandwidth mobile connections. | Rules out a heavy client framework; mandates a no-build, dependency-free frontend. |
| C-05 | No access to a real clinic for field elicitation within the window. | Requirements rest on proxy analysis; assumptions must be explicitly registered (7.2) and validated before a pilot. |
| C-06 | The system must not process clinical data. | Bounds regulatory exposure and excludes EMR functionality from scope. |

### 7.2 Assumptions

| ID | Assumption | Risk if false | Validation action |
|---|---|---|---|
| A-01 | Practitioner availability is stable enough to express as recurring weekly rules with occasional manual adjustment. | Slot generation would produce unbookable slots; a date-specific override model would be required. | Confirm with two pilot clinics; adds ~6 h if false. |
| A-02 | A nominal fixed duration per service is an acceptable approximation of consultation length. | Systematic schedule drift through the day. | Measure actual consultation durations during pilot. |
| A-03 | At least one member of reception staff is available to operate the console during clinic hours. | Queue state would go stale and the system would be actively misleading. | Confirm staffing model; otherwise a patient self-check-in kiosk is required. |
| A-04 | Enough patients have smartphone access for self-service booking to reduce desk load materially. | Value proposition weakens to staff-mediated booking only, which is still useful but smaller. | Sample patient device ownership at pilot site. |
| A-05 | Clinic premises have sufficiently reliable internet for the staff console during opening hours. | An offline-first architecture would be required - a substantial redesign. | Site survey; recorded as the largest single architectural risk. |
| A-06 | Patients accept a masked-name public queue display as sufficient privacy. | Would require ticket-number-only display. | Confirm with clinic and patients. |

---

## 8. Scope for the 48-Hour Delivery

### 8.1 Method

Requirements were ordered by MoSCoW priority and costed during estimation (see the Software Effort Estimation section of the consolidated documentation). Use Case Points sized the full elicited requirement set at **191.7 UCP**, and COCOMO II independently sized it at approximately **199 function points** - both models placing a production-grade build in the range of **1,800 to 2,700 person-hours**, between 37 and 56 times the available window. Scope was therefore cut deliberately and explicitly rather than by drift.

Two cut rules were applied:

1. **Functional cut.** Every Must-have is in scope; a Should-have is in scope only if it costs under two hours and touches code already being written; every Could-have and Won't-have is out. This removed six use cases representing 31% of functional size (SRS §8.3).
2. **Quality-level cut.** v1.0 is delivered explicitly as a **prototype-grade vertical slice**, not a productised system. Production hardening (WCAG conformance testing, internationalisation, load and soak testing, disaster recovery, observability, database migration tooling and high availability) is deferred. This deferral is not concealed: every item is enumerated in the Technical Debt Register with a cause, impact, priority and resolution, and scheduled in the Future Evolution roadmap.

The bottom-up PERT estimate for the resulting scope came to 55.6 person-hours - still 7.6 hours over budget. Six specific mitigations (a zero-build frontend, direct SQLite rather than an ORM, reuse of Werkzeug's PBKDF2, mechanical documentation generation, shared seed/test fixtures, and manual rather than automated usability testing) recovered 7.75 hours and brought the plan to **47.85 person-hours** against the 48-hour budget. Four of those six mitigations deliberately purchase schedule with technical debt, and each is recorded as such.

### 8.2 In Scope (v1.0, this delivery)

- All 58 Must-have and selected Should-have functional requirements FR-01 to FR-58 listed in Section 4.
- All Must-have non-functional requirements in Section 5.
- Automated unit, integration and system test suites.
- Containerised, cloud-deployable build with seeded demonstration data.

### 8.3 Explicitly Out of Scope (deferred to v1.1+)

| ID | Deferred requirement | MoSCoW | Deferred because | Target release |
|---|---|---|---|---|
| FR-59 | SMS and email appointment reminders | Could | C-03: no gateway budget; adds an external dependency and failure mode. | v1.1 |
| FR-60 | Patient-initiated rescheduling (as distinct from cancel-and-rebook) | Could | Cancel-then-rebook achieves the same outcome at zero additional cost. | v1.1 |
| FR-61 | Practitioner self-service portal for managing own availability | Could | Administrator-managed availability satisfies the need in a small clinic. | v1.2 |
| FR-62 | Waiting-room display board (public read-only screen) | Could | Requires hardware assumptions not yet validated (A-06). | v1.2 |
| FR-63 | Recurring / series appointments for chronic care | Won't | Substantial scheduling complexity for a minority of visits. | v2.0 |
| FR-64 | Multi-clinic tenancy | Won't | Requires a tenancy model through every query; a v2.0 architectural change. | v2.0 |
| FR-65 | Native mobile application | Won't | The responsive web client meets the need at a fraction of the cost. | Not planned |
| FR-66 | Clinical notes / EMR features | Won't | C-06: deliberate boundary, regulatory exposure. | Not planned |
| FR-67 | Online payment / billing | Won't | Separate regulated domain. | Not planned |

### 8.4 Scope Risk

The largest scope risk is FR-20/FR-21 (slot generation and conflict exclusion) proving more intricate than estimated, since it carries the highest algorithmic complexity in the system. The mitigation adopted was to implement and unit-test the slot algorithm as a pure function in the service layer **first**, before any HTTP or UI code, so that a cost overrun would be discovered at hour 14 rather than hour 40.

---

## 9. Requirements Traceability Matrix

The matrix links each requirement group to the design element that realises it, the source module that implements it, and the test case that verifies it. Test case identifiers are defined in the Testing Report.

| Requirement | Design element | Implementation module | Verifying tests |
|---|---|---|---|
| FR-01 - FR-04 | Registration sequence; User entity | `app/api/auth.py`, `app/security.py`, `app/validators.py` | TC-U-01 to 04, TC-I-01 to 04 |
| FR-05 - FR-09 | Authentication sequence; session design | `app/api/auth.py`, `app/security.py` | TC-U-05 to 07, TC-I-05 to 09, TC-S-05 |
| FR-10 - FR-13 | RBAC component | `app/security.py` (`require_auth`, `require_role`) | TC-I-10 to 13, TC-SEC-01 to 04 |
| FR-14 - FR-19 | Catalogue component; ERD services/practitioners | `app/api/catalog.py`, `app/api/admin.py` | TC-I-14 to 19 |
| FR-20 - FR-23 | Slot generation algorithm | `app/services/scheduling.py` | TC-U-08 to 16 |
| FR-24 - FR-32 | Booking sequence; appointment state machine | `app/services/scheduling.py`, `app/api/appointments.py` | TC-U-17 to 20, TC-I-20 to 28, TC-S-01 |
| FR-33 - FR-44 | Queue activity model; queue component | `app/services/queue.py`, `app/api/queue.py` | TC-U-21 to 26, TC-I-29 to 38, TC-S-02, TC-S-03 |
| FR-45 - FR-49 | Admin component; audit log entity | `app/api/admin.py`, `app/db.py` (`write_audit`) | TC-I-39 to 44, TC-S-04 |
| FR-50 - FR-52 | Reporting component | `app/services/reports.py`, `app/api/admin.py` | TC-U-27 to 29, TC-I-45 to 47 |
| FR-53 - FR-58 | Validation layer; error envelope | `app/validators.py`, `app/errors.py`, `app/db.py` | TC-U-30 to 36, TC-SEC-05 to 10 |
| NFR-PER-01 to 04 | Architecture; index design | `app/schema.sql` | TC-P-01 to 03 |
| NFR-SEC-01 to 06 | Security design | `app/security.py`, `app/__init__.py` | TC-SEC-01 to 12 |
| NFR-USA-01 to 05 | Wireframes; responsive CSS | `app/static/css/app.css` | TC-USA-01 to 05 |
| NFR-REL-01 to 04 | Error handling; health endpoint | `app/errors.py`, `app/api/health.py` | TC-I-48 to 50 |
| NFR-MNT-01 to 06 | Layered architecture | Whole package; `tests/` | TC-Q-01 to 03 |

---

## 10. Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| Author / Developer | [STUDENT NAME] | | 12 Aug 2026 |
| Reviewer (Course Examiner) | | | |

*End of SRS v1.0.*
