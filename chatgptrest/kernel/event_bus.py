"""TraceEvent publish-subscribe event bus.

The EventBus is the unified cross-layer event backbone.  Every layer
(Advisor, Workflows, KB, EvoMap) emits TraceEvents through this bus.
Subscribers (like the EvoMap observer) consume them.

Storage: SQLite WAL for durability.  In-process pub-sub for low-latency.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading

import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ── TraceEvent ────────────────────────────────────────────────────

@dataclass
class TraceEvent:
    """CloudEvents-style envelope for cross-layer communication.

    This is the SOLE event standard for the system.
    """

    event_id: str
    source: str           # "advisor" | "funnel" | "kb" | "evomap" | "pipeline"
    event_type: str       # "advisor.route_selected" | "funnel.stage_completed" | ...
    trace_id: str         # propagated across the request lifecycle
    timestamp: str        # ISO 8601 UTC
    data: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    parent_event_id: str = ""
    security_label: str = "internal"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        *,
        source: str,
        event_type: str,
        trace_id: str = "",
        data: dict[str, Any] | None = None,
        session_id: str = "",
        parent_event_id: str = "",
        security_label: str = "internal",
    ) -> TraceEvent:
        return cls(
            event_id=uuid.uuid4().hex,
            source=source,
            event_type=event_type,
            trace_id=trace_id or uuid.uuid4().hex,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data or {},
            session_id=session_id,
            parent_event_id=parent_event_id,
            security_label=security_label,
        )


# ── Subscriber type ──────────────────────────────────────────────

EventHandler = Callable[[TraceEvent], None]


# ── EventBus ─────────────────────────────────────────────────────

class EventBus:
    """TraceEvent publish-subscribe backbone with SQLite persistence."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._subscribers: list[EventHandler] = []
        self._lock = threading.Lock()
        self._db_path = Path(db_path) if db_path else None
        self._local = threading.local()
        self._closed = False
        # Phase-4: in-memory dedup for no-DB mode (bounded LRU)
        self._seen_ids: set[str] = set()
        self._MAX_SEEN = 10000
        if self._db_path:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    def _get_conn(self) -> sqlite3.Connection | None:
        if not self._db_path:
            return None
        if not hasattr(self._local, "conn"):
            # BUG-7 fix: use deferred transactions instead of autocommit (isolation_level=None)
            # to reduce WAL checkpoint pressure under high-concurrency emit()
            conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        if conn is None:
            return
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trace_events (
                event_id       TEXT PRIMARY KEY,
                source         TEXT NOT NULL,
                event_type     TEXT NOT NULL,
                trace_id       TEXT NOT NULL,
                timestamp      TEXT NOT NULL,
                data           TEXT NOT NULL DEFAULT '{}',
                session_id     TEXT DEFAULT '',
                parent_event_id TEXT DEFAULT '',
                security_label TEXT DEFAULT 'internal'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_te_trace ON trace_events(trace_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_te_type ON trace_events(event_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_te_source ON trace_events(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_te_ts ON trace_events(timestamp)")

    def close(self) -> None:
        """Close the EventBus. After close, emit() raises RuntimeError."""
        self._closed = True
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn

    # ── Pub/Sub ───────────────────────────────────────────────────

    def subscribe(self, handler: EventHandler) -> None:
        with self._lock:
            self._subscribers.append(handler)

    def unsubscribe(self, handler: EventHandler) -> None:
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s is not handler]

    def emit(self, event: TraceEvent) -> bool:
        """Persist event and notify all subscribers.

        Returns True if persisted, False if duplicate event_id (idempotent skip).
        Raises RuntimeError if the bus has been closed.
        """
        if self._closed:
            raise RuntimeError("EventBus is closed, cannot emit events")
        # 1. Persist
        persisted = self._persist(event)

        # Phase-1 fix: skip subscriber notification on duplicate events
        # to prevent duplicate side-effects (signal writes, memory updates)
        if not persisted:
            logger.debug("EventBus: duplicate event %s, skipping subscribers", event.event_id)
            return False

        # 2. Notify subscribers (errors logged, never propagated)
        with self._lock:
            subs = list(self._subscribers)
        for handler in subs:
            try:
                handler(event)
            except Exception:
                logger.exception("EventBus subscriber error for %s", event.event_type)
        return True

    def _persist(self, event: TraceEvent) -> bool:
        """Persist event. Returns True if inserted, False if duplicate."""
        conn = self._get_conn()
        if conn is None:
            # No-DB mode: in-memory dedup via _seen_ids set
            if event.event_id in self._seen_ids:
                return False
            self._seen_ids.add(event.event_id)
            # Trim to avoid unbounded memory growth
            if len(self._seen_ids) > self._MAX_SEEN:
                # Discard oldest ~20% (set is unordered, but prevents OOM)
                to_remove = len(self._seen_ids) - int(self._MAX_SEEN * 0.8)
                it = iter(self._seen_ids)
                for _ in range(to_remove):
                    self._seen_ids.discard(next(it))
            return True
        try:
            cur = conn.execute(
                """INSERT OR IGNORE INTO trace_events
                   (event_id, source, event_type, trace_id, timestamp,
                    data, session_id, parent_event_id, security_label)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    event.event_id,
                    event.source,
                    event.event_type,
                    event.trace_id,
                    event.timestamp,
                    json.dumps(event.data, ensure_ascii=False),
                    event.session_id,
                    event.parent_event_id,
                    event.security_label,
                ),
            )
            conn.commit()
            return cur.rowcount > 0  # 1 if inserted, 0 if ignored
        except sqlite3.IntegrityError:
            logger.debug("Duplicate event_id %s (idempotent skip)", event.event_id)
            return False

    # ── Query ─────────────────────────────────────────────────────

    def query(
        self,
        *,
        trace_id: str | None = None,
        source: str | None = None,
        event_type: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[TraceEvent]:
        conn = self._get_conn()
        if conn is None:
            return []
        conditions: list[str] = []
        params: list[Any] = []
        if trace_id:
            conditions.append("trace_id = ?")
            params.append(trace_id)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        where = " AND ".join(conditions) if conditions else "1=1"
        rows = conn.execute(
            f"""SELECT event_id, source, event_type, trace_id, timestamp,
                       data, session_id, parent_event_id, security_label
                FROM trace_events
                WHERE {where}
                ORDER BY timestamp ASC
                LIMIT ?""",
            params + [limit],
        ).fetchall()
        return [
            TraceEvent(
                event_id=r[0], source=r[1], event_type=r[2], trace_id=r[3],
                timestamp=r[4], data=json.loads(r[5]), session_id=r[6],
                parent_event_id=r[7], security_label=r[8],
            )
            for r in rows
        ]

    def replay(self, trace_id: str) -> list[TraceEvent]:
        """Replay all events for a trace in chronological order."""
        return self.query(trace_id=trace_id, limit=10_000)
