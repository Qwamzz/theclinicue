-- TheClinicue schema. See docs/System_Design.md §3 and docs/diagrams/erd.svg.
-- Deletion is modelled as deactivation throughout so that historical
-- appointments never lose their referent.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    phone         TEXT    NOT NULL DEFAULT '',
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'PATIENT'
                          CHECK (role IN ('PATIENT', 'STAFF', 'ADMIN')),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS services (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL UNIQUE,
    description  TEXT    NOT NULL DEFAULT '',
    duration_min INTEGER NOT NULL CHECK (duration_min BETWEEN 5 AND 240),
    is_active    INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS practitioners (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name  TEXT    NOT NULL,
    specialty  TEXT    NOT NULL DEFAULT '',
    room       TEXT    NOT NULL DEFAULT '',
    is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS availability_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    practitioner_id INTEGER NOT NULL REFERENCES practitioners(id),
    weekday         INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time      TEXT    NOT NULL,
    end_time        TEXT    NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at      TEXT    NOT NULL,
    CHECK (start_time < end_time)                       -- FR-18
);

CREATE TABLE IF NOT EXISTS appointments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT    NOT NULL UNIQUE,
    patient_id      INTEGER NOT NULL REFERENCES users(id),
    practitioner_id INTEGER NOT NULL REFERENCES practitioners(id),
    service_id      INTEGER NOT NULL REFERENCES services(id),
    appt_date       TEXT    NOT NULL,
    start_time      TEXT    NOT NULL,
    end_time        TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'BOOKED'
                            CHECK (status IN ('BOOKED', 'CHECKED_IN', 'IN_PROGRESS',
                                              'COMPLETED', 'CANCELLED', 'NO_SHOW')),
    source          TEXT    NOT NULL DEFAULT 'SELF'
                            CHECK (source IN ('SELF', 'STAFF', 'WALK_IN')),
    notes           TEXT    NOT NULL DEFAULT '',
    created_by      INTEGER NOT NULL REFERENCES users(id),
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS queue_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id  INTEGER NOT NULL UNIQUE REFERENCES appointments(id),
    practitioner_id INTEGER NOT NULL REFERENCES practitioners(id),
    queue_date      TEXT    NOT NULL,
    ticket_no       INTEGER NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'WAITING'
                            CHECK (status IN ('WAITING', 'CALLED', 'DONE', 'SKIPPED')),
    checked_in_at   TEXT    NOT NULL,
    called_at       TEXT,
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id   INTEGER REFERENCES users(id),
    action     TEXT    NOT NULL,
    entity     TEXT    NOT NULL DEFAULT '',
    entity_id  INTEGER,
    details    TEXT    NOT NULL DEFAULT '',
    ip_address TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL
);

-- ---------------------------------------------------------------------------
-- Constraints that carry correctness.
-- These are partial indexes: cancelled rows are invisible to the constraint,
-- so a released slot can be rebooked (FR-29) while a live one cannot be
-- double-booked (FR-21, FR-26).
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS ux_appt_slot
    ON appointments (practitioner_id, appt_date, start_time)
    WHERE status <> 'CANCELLED';

CREATE UNIQUE INDEX IF NOT EXISTS ux_patient_day           -- FR-27
    ON appointments (patient_id, practitioner_id, appt_date)
    WHERE status <> 'CANCELLED';

CREATE UNIQUE INDEX IF NOT EXISTS ux_queue_ticket          -- FR-35
    ON queue_entries (practitioner_id, queue_date, ticket_no);

-- ---------------------------------------------------------------------------
-- Performance indexes (NFR-PER-01). Each serves a specific named query.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_appt_date       ON appointments (appt_date);
CREATE INDEX IF NOT EXISTS ix_appt_patient    ON appointments (patient_id, appt_date);
CREATE INDEX IF NOT EXISTS ix_appt_pract_date ON appointments (practitioner_id, appt_date);
CREATE INDEX IF NOT EXISTS ix_queue_lookup    ON queue_entries (practitioner_id, queue_date, status);
CREATE INDEX IF NOT EXISTS ix_avail_pract     ON availability_rules (practitioner_id, weekday);
CREATE INDEX IF NOT EXISTS ix_audit_created   ON audit_log (created_at DESC);
