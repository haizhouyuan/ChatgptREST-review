"""
Event Log Store – SQLite-based, append-only trace event persistence.

Design goals:
- Append-only writes (no updates/deletes in normal operation)
- Fast queries by trace_id, session_id, event_type, time range
- JSON payload storage with selective indexing
- Bulk insert support for high-throughput ingestion
- Simple backup (copy the file)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterator, Optional

from .schemas import TraceEvent, _now_iso, _uuid

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS trace_events (
    event_id       TEXT PRIMARY KEY,
    trace_id       TEXT NOT NULL,
    session_id     TEXT NOT NULL DEFAULT '',
    parent_event_id TEXT NOT NULL DEFAULT '',
    source         TEXT NOT NULL DEFAULT '',
    event_type     TEXT NOT NULL,
    timestamp      TEXT NOT NULL,
    data_json      TEXT NOT NULL DEFAULT '{}',
    content_hash   TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_trace_events_trace
    ON trace_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_trace_events_session
    ON trace_events(session_id);
CREATE INDEX IF NOT EXISTS idx_trace_events_type
    ON trace_events(event_type);
CREATE INDEX IF NOT EXISTS idx_trace_events_ts
    ON trace_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_trace_events_hash
    ON trace_events(content_hash);
"""


# ---------------------------------------------------------------------------
# EventLogStore
# ---------------------------------------------------------------------------

class EventLogStore:
    """
    Thread-safe, append-only SQLite event log.

    Usage::

        store = EventLogStore("/path/to/events.db")
        store.append(TraceEvent(
            source="advisor/triage",
            event_type="route_selected",
            trace_id="abc123",
            data={"route": "deep_research"},
        ))

        events = store.query(trace_id="abc123")
        for e in events:
            print(e.event_type, e.data)
    """

    def __init__(self, db_path: str | Path = ":memory:"):
        self._db_path = str(db_path)
        self._local = threading.local()
        # Ensure schema on first connection
        with self._conn() as conn:
            conn.executescript(_DDL)

    # -- connection management -----------------------------------------------

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        """Get a thread-local connection with WAL mode."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise

    # -- write ---------------------------------------------------------------

    def append(self, event: TraceEvent) -> str:
        """Append a single event.  Returns the event_id."""
        if not event.event_id:
            event.event_id = _uuid()
        if not event.timestamp:
            event.timestamp = _now_iso()

        content_hash = event.content_hash()
        data_json = json.dumps(event.data, default=str, ensure_ascii=False)

        with self._conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO trace_events
                   (event_id, trace_id, session_id, parent_event_id,
                    source, event_type, timestamp, data_json, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.event_id,
                    event.trace_id,
                    event.session_id,
                    event.parent_event_id,
                    event.source,
                    event.event_type,
                    event.timestamp,
                    data_json,
                    content_hash,
                ),
            )
            conn.commit()
        return event.event_id

    def append_many(self, events: list[TraceEvent]) -> int:
        """Bulk append.  Returns number inserted."""
        rows = []
        for ev in events:
            if not ev.event_id:
                ev.event_id = _uuid()
            if not ev.timestamp:
                ev.timestamp = _now_iso()
            rows.append((
                ev.event_id,
                ev.trace_id,
                ev.session_id,
                ev.parent_event_id,
                ev.source,
                ev.event_type,
                ev.timestamp,
                json.dumps(ev.data, default=str, ensure_ascii=False),
                ev.content_hash(),
            ))
        with self._conn() as conn:
            conn.executemany(
                """INSERT OR IGNORE INTO trace_events
                   (event_id, trace_id, session_id, parent_event_id,
                    source, event_type, timestamp, data_json, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            conn.commit()
        return len(rows)

    # -- read ----------------------------------------------------------------

    def _row_to_event(self, row: sqlite3.Row) -> TraceEvent:
        return TraceEvent(
            event_id=row["event_id"],
            trace_id=row["trace_id"],
            session_id=row["session_id"],
            parent_event_id=row["parent_event_id"],
            source=row["source"],
            event_type=row["event_type"],
            timestamp=row["timestamp"],
            data=json.loads(row["data_json"]),
        )

    def query(
        self,
        *,
        trace_id: str = "",
        session_id: str = "",
        event_type: str = "",
        since: str = "",
        until: str = "",
        limit: int = 500,
    ) -> list[TraceEvent]:
        """Query events with optional filters.  Returns newest first."""
        clauses: list[str] = []
        params: list[Any] = []

        if trace_id:
            clauses.append("trace_id = ?")
            params.append(trace_id)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until:
            clauses.append("timestamp <= ?")
            params.append(until)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"""SELECT * FROM trace_events
                  WHERE {where}
                  ORDER BY timestamp DESC
                  LIMIT ?"""
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_trace(self, trace_id: str) -> list[TraceEvent]:
        """Get all events for a trace, ordered chronologically."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM trace_events
                   WHERE trace_id = ?
                   ORDER BY timestamp ASC""",
                (trace_id,),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def count(self, **kwargs: str) -> int:
        """Count matching events."""
        clauses: list[str] = []
        params: list[Any] = []
        for k, v in kwargs.items():
            if v:
                clauses.append(f"{k} = ?")
                params.append(v)
        where = " AND ".join(clauses) if clauses else "1=1"
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT count(*) as cnt FROM trace_events WHERE {where}",
                params,
            ).fetchone()
        return row["cnt"] if row else 0

    # -- maintenance ---------------------------------------------------------

    def vacuum(self) -> None:
        """Reclaim space.  Safe for append-only stores."""
        with self._conn() as conn:
            conn.execute("VACUUM")


# ---------------------------------------------------------------------------
# Convenience: module-level singleton
# ---------------------------------------------------------------------------

_default_store: Optional[EventLogStore] = None
_store_lock = threading.Lock()


def get_event_log(db_path: str | Path | None = None) -> EventLogStore:
    """Get or create the default EventLogStore singleton."""
    global _default_store
    with _store_lock:
        if _default_store is None:
            if db_path is None:
                # Default to project data dir
                default_dir = Path.home() / ".chatgptrest" / "data"
                default_dir.mkdir(parents=True, exist_ok=True)
                db_path = default_dir / "event_log.db"
            _default_store = EventLogStore(db_path)
        return _default_store


def reset_event_log() -> None:
    """Reset the singleton (for testing)."""
    global _default_store
    with _store_lock:
        _default_store = None
