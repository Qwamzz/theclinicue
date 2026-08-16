"""Data access layer - the only module that knows SQLite exists.

Confining SQLite here is what converts TD-01 (the move to PostgreSQL) from a
rewrite into a bounded change, and it is where FR-56 (parameterised SQL only)
is guaranteed: no caller ever builds a statement from user input.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from flask import current_app, g

from .domain import utc_stamp

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


# --------------------------------------------------------------------------
# Connection lifecycle
# --------------------------------------------------------------------------

def is_memory(database_path: str) -> bool:
    return database_path == ":memory:" or "mode=memory" in database_path


def memory_uri(tag: str) -> str:
    """A named shared-cache in-memory database.

    A bare ':memory:' database is private to one connection, so it is useless
    here: every request opens its own connection and would find an empty
    schema. The shared-cache form gives all connections in the process the same
    database, provided at least one connection stays open - which is what the
    keep-alive connection in create_app() is for.
    """
    return f"file:tc_{tag}?mode=memory&cache=shared"


VALID_JOURNAL_MODES = {"WAL", "DELETE", "TRUNCATE", "PERSIST"}


def _connect(database_path: str, journal: str | None = None) -> sqlite3.Connection:
    uri = database_path.startswith("file:")
    if not is_memory(database_path) and not uri:
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        database_path,
        detect_types=0,
        # A short busy timeout is what makes the concurrent-booking path
        # (FR-26) wait for the write lock instead of failing immediately.
        timeout=10.0,
        isolation_level=None,          # explicit transaction control, see transaction()
        uri=uri,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not is_memory(database_path):
        # WAL needs a real file, and it is what lets readers proceed while a
        # booking holds the write lock. It is unsafe on an SMB share, however,
        # so deployments on network storage (Azure App Service's /home) select
        # DELETE instead. Whitelisted because a PRAGMA cannot be parameterised.
        mode = (journal or os.environ.get("TC_SQLITE_JOURNAL", "WAL")).strip().upper()
        if mode not in VALID_JOURNAL_MODES:
            mode = "WAL"
        conn.execute(f"PRAGMA journal_mode = {mode}")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def get_db() -> sqlite3.Connection:
    """Per-request connection, created lazily and closed by teardown."""
    if "db" not in g:
        settings = current_app.config["TC"]
        g.db = _connect(settings.database_path, settings.sqlite_journal_mode)
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_schema(conn: sqlite3.Connection) -> None:
    """Apply schema.sql. Idempotent - every statement is IF NOT EXISTS.

    This is emphatically not a migration system; altering an existing column
    requires manual work. That gap is TD-02.
    """
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Query helpers
# --------------------------------------------------------------------------

def query(conn: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, tuple(params)))


def query_one(conn: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
    cursor = conn.execute(sql, tuple(params))
    return cursor.fetchone()


def scalar(conn: sqlite3.Connection, sql: str, params: Sequence[Any] = (), default: Any = None) -> Any:
    row = query_one(conn, sql, params)
    if row is None:
        return default
    value = row[0]
    return default if value is None else value


def execute(conn: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
    return conn.execute(sql, tuple(params))


def insert(conn: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> int:
    cursor = conn.execute(sql, tuple(params))
    return int(cursor.lastrowid or 0)


@contextmanager
def transaction(conn: sqlite3.Connection, immediate: bool = False) -> Iterator[sqlite3.Connection]:
    """Explicit transaction with guaranteed rollback (NFR-REL-02).

    `immediate=True` takes the write lock up front. Booking and check-in use it
    so that the re-verification read and the insert cannot be interleaved with
    another writer - the mechanism behind FR-26.

    Nested use is tolerated: if a transaction is already open the block simply
    joins it, and only the outermost block commits.
    """
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()


# --------------------------------------------------------------------------
# Audit trail (FR-48)
# --------------------------------------------------------------------------

def write_audit(
    conn: sqlite3.Connection,
    *,
    actor_id: int | None,
    action: str,
    entity: str = "",
    entity_id: int | None = None,
    details: str = "",
    ip_address: str = "",
) -> None:
    """Append one audit record.

    Append-only by convention: nothing in the application ever updates or
    deletes from audit_log. Enforcing that in the database would need triggers,
    which is TD-10.
    """
    conn.execute(
        """
        INSERT INTO audit_log (actor_id, action, entity, entity_id, details,
                               ip_address, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (actor_id, action, entity, entity_id, details[:500], ip_address[:64], utc_stamp()),
    )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else {key: row[key] for key in row.keys()}
