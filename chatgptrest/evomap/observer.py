"""EvoMap Observer — collects and aggregates system signals.

Subscribes to EventBus events and transforms them into structured
Signal records for EvoMap analytics. Persists to SQLite for querying.

Signal collection serves multiple purposes:
  - Dashboard views (daily brief, gate effectiveness, KB leverage)
  - Pattern detection for EvoMap self-improvement
  - Audit trail for compliance
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from .paths import ensure_sqlite_parent_dir, resolve_evomap_db_path, resolve_kb_registry_db_path
from .signals import Signal, SignalType, SignalDomain, normalize_signal_type

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_DDL = """
CREATE TABLE IF NOT EXISTS signals (
    signal_id    TEXT PRIMARY KEY,
    trace_id     TEXT NOT NULL DEFAULT '',
    signal_type  TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT '',
    timestamp    TEXT NOT NULL DEFAULT '',
    domain       TEXT NOT NULL DEFAULT '',
    data         TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_signals_trace ON signals(trace_id);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_signals_domain ON signals(domain);
CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(timestamp);
"""


class EvoMapObserver:
    """Collects and stores system signals for EvoMap analytics.

    Usage::

        observer = EvoMapObserver(db_path=":memory:")
        observer.record(Signal(
            trace_id="tr_001",
            signal_type=SignalType.ROUTE_SELECTED,
            source="advisor",
            domain=SignalDomain.ROUTING,
            data={"route": "funnel", "scores": {...}},
        ))

        # Query
        signals = observer.query(trace_id="tr_001")
        stats = observer.aggregate_by_type()
    """

    def __init__(self, db_path: str = "") -> None:
        db_path = resolve_evomap_db_path(db_path)
        ensure_sqlite_parent_dir(db_path)
        self._db_path = db_path
        self._local = threading.local()
        self._conn_lock = threading.Lock()
        self._connections: list[sqlite3.Connection] = []
        self._memory_conn: sqlite3.Connection | None = None
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        if self._db_path == ":memory:":
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(self._db_path, check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
                self._memory_conn.execute("PRAGMA busy_timeout=3000")
                with self._conn_lock:
                    self._connections.append(self._memory_conn)
            return self._memory_conn

        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=3000")
            self._local.conn = conn
            with self._conn_lock:
                self._connections.append(conn)
        return conn

    @property
    def db_path(self) -> str:
        return self._db_path

    def _init_db(self) -> None:
        conn = self._conn()
        conn.executescript(_DDL)
        conn.commit()

    def record(self, signal: Signal) -> str:
        """Record a signal. Returns signal_id."""
        if not signal.signal_id:
            signal.signal_id = str(uuid.uuid4())
        if not signal.timestamp:
            signal.timestamp = _now_iso()
        # Normalize legacy signal names (e.g. route_selected → route.selected)
        signal.signal_type = normalize_signal_type(signal.signal_type)

        data_json = json.dumps(signal.data, default=str, ensure_ascii=False)
        conn = self._conn()
        conn.execute(
            """INSERT INTO signals
               (signal_id, trace_id, signal_type, source, timestamp, domain, data)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (signal.signal_id, signal.trace_id, signal.signal_type,
             signal.source, signal.timestamp, signal.domain, data_json),
        )
        conn.commit()
        logger.debug(
            "signal recorded: id=%s type=%s domain=%s trace=%s source=%s data_len=%d",
            signal.signal_id, signal.signal_type, signal.domain,
            signal.trace_id, signal.source, len(data_json),
        )
        return signal.signal_id

    def record_event(
        self,
        trace_id: str,
        signal_type: str,
        source: str,
        domain: str = "",
        data: dict[str, Any] | None = None,
    ) -> str:
        """Convenience method to record a signal from raw args."""
        signal_type = normalize_signal_type(signal_type)
        logger.debug(
            "record_event: type=%s source=%s domain=%s trace=%s",
            signal_type, source, domain, trace_id,
        )
        signal = Signal(
            trace_id=trace_id,
            signal_type=signal_type,
            source=source,
            domain=domain,
            data=data or {},
        )
        return self.record(signal)

    def emit(
        self,
        *,
        signal_type: str,
        payload: dict[str, Any] | None = None,
        trace_id: str = "",
        source: str = "feedback_collector",
        domain: str = "llm",
    ) -> str:
        """Emit a signal — compatibility bridge for FeedbackCollector.

        FeedbackCollector calls ``observer.emit(signal_type=..., payload=...,
        trace_id=...)`` which this method translates to ``record_event()``.
        """
        logger.debug(
            "emit: type=%s trace=%s source=%s payload_keys=%s",
            signal_type, trace_id, source,
            sorted((payload or {}).keys()),
        )
        return self.record_event(
            trace_id=trace_id,
            signal_type=signal_type,
            source=source,
            domain=domain,
            data=payload or {},
        )

    # -- Queries ──────────────────────────────────────────────────

    def query(
        self,
        *,
        trace_id: str = "",
        signal_type: str = "",
        domain: str = "",
        since: str = "",
        until: str = "",
        limit: int = 100,
    ) -> list[Signal]:
        """Query signals with filters."""
        clauses: list[str] = []
        params: list[Any] = []

        if trace_id:
            clauses.append("trace_id = ?")
            params.append(trace_id)
        if signal_type:
            clauses.append("signal_type = ?")
            params.append(signal_type)
        if domain:
            clauses.append("domain = ?")
            params.append(domain)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until:
            clauses.append("timestamp <= ?")
            params.append(until)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM signals WHERE {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        conn = self._conn()
        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_signal(r) for r in rows]

    def by_trace(self, trace_id: str) -> list[Signal]:
        """Get all signals for a trace, ordered by time."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM signals WHERE trace_id = ? ORDER BY timestamp",
            (trace_id,),
        ).fetchall()
        return [self._row_to_signal(r) for r in rows]

    def aggregate_by_type(self) -> dict[str, int]:
        """Count signals grouped by type."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT signal_type, count(*) as cnt FROM signals GROUP BY signal_type"
        ).fetchall()
        return {r["signal_type"]: r["cnt"] for r in rows}

    def aggregate_by_domain(self) -> dict[str, int]:
        """Count signals grouped by domain."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT domain, count(*) as cnt FROM signals GROUP BY domain"
        ).fetchall()
        return {r["domain"]: r["cnt"] for r in rows}

    def count(self, **kwargs: Any) -> int:
        """Count signals matching filters."""
        return len(self.query(**kwargs, limit=10000))

    # -- KB quality scoring (Phase 2) ──────────────────────────────

    def update_kb_score(self, artifact_id: str, delta: float) -> float:
        """Adjust KB artifact quality_score by *delta*. Returns new score.

        Updates the kb_registry.db artifact quality_score, clamping to [0.0, 1.0].
        Returns the new quality_score.
        """
        kb_reg = resolve_kb_registry_db_path()
        ensure_sqlite_parent_dir(kb_reg)
        if not os.path.exists(kb_reg):
            logger.warning("update_kb_score: kb_registry.db not found")
            return 0.0
        try:
            kb_conn = sqlite3.connect(kb_reg)
            kb_conn.execute(
                "UPDATE artifacts SET quality_score = "
                "MAX(0.0, MIN(1.0, quality_score + ?)) WHERE artifact_id = ?",
                (delta, artifact_id),
            )
            kb_conn.commit()
            row = kb_conn.execute(
                "SELECT quality_score FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
            new_score = row[0] if row else 0.0
            kb_conn.close()
            logger.info(
                "KB score updated: artifact=%s delta=%.2f new_score=%.2f",
                artifact_id, delta, new_score,
            )
            return new_score
        except Exception as e:
            logger.warning("update_kb_score failed: %s", e)
            return 0.0

    def query_recent(
        self,
        signal_type: str,
        since: str = "",
        limit: int = 50,
    ) -> list[Signal]:
        """Query recent signals of a specific type. Used by actuators."""
        signal_type = normalize_signal_type(signal_type)
        return self.query(signal_type=signal_type, since=since, limit=limit)

    def close(self) -> None:
        with self._conn_lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()
            self._memory_conn = None
        if hasattr(self._local, "conn"):
            del self._local.conn

    def _row_to_signal(self, row: sqlite3.Row) -> Signal:
        return Signal(
            signal_id=row["signal_id"],
            trace_id=row["trace_id"],
            signal_type=row["signal_type"],
            source=row["source"],
            timestamp=row["timestamp"],
            domain=row["domain"],
            data=json.loads(row["data"]),
        )
