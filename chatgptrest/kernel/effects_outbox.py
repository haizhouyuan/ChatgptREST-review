"""Effects Outbox — idempotent side-effect management.

All external side-effects (feishu_notify, agent_dispatch, kb_writeback)
are first enqueued into this outbox.  A worker then executes pending
effects, marking them done on success or failed on error.

On retry / resume / replay, already-completed effects are automatically
skipped because ``(effect_type, effect_key)`` is UNIQUE.

Design reference:
    - v3 synthesis P0-1 (effects_outbox DDL)
    - Transactional Outbox pattern (microservices)

Storage: SQLite WAL, same pattern as EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import traceback as tb_module

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Data Models ───────────────────────────────────────────────────

@dataclass
class Effect:
    """An enqueued side-effect waiting for execution."""

    effect_id: str
    trace_id: str
    effect_type: str          # feishu_notify | agent_dispatch | kb_writeback
    effect_key: str           # dedup key: {trace_id}:{type}:{target}
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"   # pending → executing → done | failed
    created_at: float = 0.0
    executed_at: float | None = None
    error: str | None = None


@dataclass
class EffectResult:
    """Result of executing a single effect."""

    effect_id: str
    effect_type: str
    success: bool
    data: Any = None
    error: str | None = None


# ── DDL ───────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS effects_outbox (
    effect_id     TEXT PRIMARY KEY,
    trace_id      TEXT NOT NULL,
    effect_type   TEXT NOT NULL,
    effect_key    TEXT NOT NULL,
    payload_json  TEXT NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    REAL NOT NULL,
    executed_at   REAL,
    error         TEXT,
    UNIQUE(effect_type, effect_key)
);

CREATE INDEX IF NOT EXISTS idx_outbox_status
    ON effects_outbox(status);
CREATE INDEX IF NOT EXISTS idx_outbox_trace
    ON effects_outbox(trace_id);
"""


# ── EffectsOutbox ─────────────────────────────────────────────────

# Type alias for handler functions
EffectHandler = Callable[[dict[str, Any]], Any]


class EffectsOutbox:
    """Transactional outbox for idempotent side-effect execution.

    Usage::

        outbox = EffectsOutbox(":memory:")

        # Enqueue (returns effect_id, or None if duplicate)
        eid = outbox.enqueue("trace_123", "feishu_notify", "trace_123:feishu:ou_abc",
                             {"message": "hello"})

        # Execute all pending effects
        handlers = {
            "feishu_notify": lambda payload: send_feishu(payload["message"]),
            "agent_dispatch": lambda payload: dispatch_agent(payload),
        }
        results = outbox.execute_pending(handlers)

        # Check if already done
        assert outbox.is_done("feishu_notify", "trace_123:feishu:ou_abc")
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)  # S3-4.5: FastAPI thread safety
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_DDL)
        self._conn.commit()
        self._closed = False

    # ── Public API ────────────────────────────────────────────────

    def enqueue(
        self,
        trace_id: str,
        effect_type: str,
        effect_key: str,
        payload: dict[str, Any] | None = None,
        effect_id: str | None = None,
    ) -> str | None:
        """Enqueue a side-effect for later execution.

        Returns the effect_id on success, or None if the
        ``(effect_type, effect_key)`` was already enqueued (dedup).

        Raises RuntimeError if the outbox is closed.
        """
        if self._closed:
            raise RuntimeError("EffectsOutbox is closed")

        import uuid
        eid = effect_id or str(uuid.uuid4())
        now = time.time()
        payload_json = json.dumps(payload or {}, ensure_ascii=False, default=str)

        cursor = self._conn.execute(
            """INSERT OR IGNORE INTO effects_outbox
               (effect_id, trace_id, effect_type, effect_key,
                payload_json, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (eid, trace_id, effect_type, effect_key, payload_json, now),
        )
        self._conn.commit()

        if cursor.rowcount == 0:
            logger.debug(
                "Effect deduped: type=%s key=%s", effect_type, effect_key
            )
            return None

        logger.info(
            "Effect enqueued: id=%s type=%s key=%s",
            eid, effect_type, effect_key,
        )
        return eid

    def execute_pending(
        self,
        handler_map: dict[str, EffectHandler],
        *,
        limit: int = 100,
    ) -> list[EffectResult]:
        """Execute all pending effects using the provided handlers.

        Args:
            handler_map: ``{effect_type: handler_fn(payload) -> result}``
            limit: max effects to process in one batch.

        Returns:
            List of :class:`EffectResult` for each processed effect.
        """
        if self._closed:
            raise RuntimeError("EffectsOutbox is closed")

        rows = self._conn.execute(
            """SELECT effect_id, trace_id, effect_type, effect_key, payload_json
               FROM effects_outbox
               WHERE status = 'pending'
               ORDER BY created_at ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        results: list[EffectResult] = []

        for effect_id, trace_id, effect_type, effect_key, payload_json in rows:
            handler = handler_map.get(effect_type)
            if handler is None:
                logger.warning(
                    "No handler for effect_type=%s (id=%s), skipping",
                    effect_type, effect_id,
                )
                continue

            # Mark as executing
            self._conn.execute(
                "UPDATE effects_outbox SET status = 'executing' WHERE effect_id = ?",
                (effect_id,),
            )
            self._conn.commit()

            payload = json.loads(payload_json)
            try:
                data = handler(payload)
                self._conn.execute(
                    """UPDATE effects_outbox
                       SET status = 'done', executed_at = ?
                       WHERE effect_id = ?""",
                    (time.time(), effect_id),
                )
                self._conn.commit()
                results.append(EffectResult(
                    effect_id=effect_id,
                    effect_type=effect_type,
                    success=True,
                    data=data,
                ))
                logger.info("Effect done: id=%s type=%s", effect_id, effect_type)

            except Exception as exc:
                error_str = json.dumps({
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": tb_module.format_exc(),
                }, ensure_ascii=False)
                self._conn.execute(
                    """UPDATE effects_outbox
                       SET status = 'failed', executed_at = ?, error = ?
                       WHERE effect_id = ?""",
                    (time.time(), error_str, effect_id),
                )
                self._conn.commit()
                results.append(EffectResult(
                    effect_id=effect_id,
                    effect_type=effect_type,
                    success=False,
                    error=str(exc),
                ))
                logger.error(
                    "Effect failed: id=%s type=%s error=%s",
                    effect_id, effect_type, exc,
                )

        return results

    def is_done(self, effect_type: str, effect_key: str) -> bool:
        """Check whether a specific effect has already been executed."""
        row = self._conn.execute(
            """SELECT status FROM effects_outbox
               WHERE effect_type = ? AND effect_key = ?""",
            (effect_type, effect_key),
        ).fetchone()
        return row is not None and row[0] == "done"

    def mark_done(self, effect_id: str) -> None:
        """Mark an effect as done (called by dispatch.py after successful execution)."""
        self._conn.execute(
            """UPDATE effects_outbox
               SET status = 'done', executed_at = ?
               WHERE effect_id = ?""",
            (time.time(), effect_id),
        )
        self._conn.commit()
        logger.info("Effect marked done: id=%s", effect_id)

    def mark_failed(self, effect_id: str, error: str) -> None:
        """Mark an effect as failed (called by dispatch.py on execution error)."""
        self._conn.execute(
            """UPDATE effects_outbox
               SET status = 'failed', executed_at = ?, error = ?
               WHERE effect_id = ?""",
            (time.time(), error, effect_id),
        )
        self._conn.commit()
        logger.info("Effect marked failed: id=%s error=%s", effect_id, error[:200])

    def get_by_trace(self, trace_id: str) -> list[Effect]:
        """Get all effects for a given trace_id."""
        rows = self._conn.execute(
            """SELECT effect_id, trace_id, effect_type, effect_key,
                      payload_json, status, created_at, executed_at, error
               FROM effects_outbox
               WHERE trace_id = ?
               ORDER BY created_at ASC""",
            (trace_id,),
        ).fetchall()
        return [
            Effect(
                effect_id=r[0],
                trace_id=r[1],
                effect_type=r[2],
                effect_key=r[3],
                payload=json.loads(r[4]),
                status=r[5],
                created_at=r[6],
                executed_at=r[7],
                error=r[8],
            )
            for r in rows
        ]

    def retry_failed(
        self,
        handler_map: dict[str, EffectHandler],
        *,
        limit: int = 50,
    ) -> list[EffectResult]:
        """Retry failed effects by resetting them to pending, then executing."""
        if self._closed:
            raise RuntimeError("EffectsOutbox is closed")

        self._conn.execute(
            """UPDATE effects_outbox
               SET status = 'pending', error = NULL
               WHERE effect_id IN (
                   SELECT effect_id FROM effects_outbox
                   WHERE status = 'failed'
                   ORDER BY created_at ASC
                   LIMIT ?
               )""",
            (limit,),
        )
        self._conn.commit()
        return self.execute_pending(handler_map, limit=limit)

    def count(
        self,
        *,
        status: str | None = None,
        trace_id: str | None = None,
    ) -> int:
        """Count effects, optionally filtered by status and/or trace_id."""
        query = "SELECT COUNT(*) FROM effects_outbox WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if trace_id:
            query += " AND trace_id = ?"
            params.append(trace_id)
        return self._conn.execute(query, params).fetchone()[0]

    def close(self) -> None:
        """Close the outbox (idempotent)."""
        if not self._closed:
            self._closed = True
            self._conn.close()
            logger.debug("EffectsOutbox closed: %s", self._db_path)
