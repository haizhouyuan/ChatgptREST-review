"""Batch event collector for reducing SQLite write-lock contention.

Non-critical job events (observability, diagnostics) can be collected during
a ``_run_once`` cycle and flushed in a single transaction at the end, instead
of opening individual ``BEGIN IMMEDIATE`` + ``COMMIT`` pairs for each event.

Critical coordination events (``claimed``, ``status_changed``, ``phase_changed``)
should still be written immediately — they serve as signals for other workers.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from chatgptrest.core import artifacts


@dataclass
class _PendingEvent:
    job_id: str
    ts: float
    type: str
    payload: dict[str, Any] | None


@dataclass
class EventBatch:
    """Collects job events and flushes them in a single transaction."""

    _events: list[_PendingEvent] = field(default_factory=list)

    def add(self, job_id: str, *, type: str, payload: dict[str, Any] | None = None) -> None:  # noqa: A002
        self._events.append(_PendingEvent(job_id=job_id, ts=time.time(), type=type, payload=payload))

    def flush(self, conn: Any, *, artifacts_dir: Any) -> None:
        """Write all collected events in a single transaction."""
        if not self._events:
            return
        events = list(self._events)
        self._events.clear()
        conn.execute("BEGIN IMMEDIATE")
        for ev in events:
            conn.execute(
                """
                INSERT INTO job_events(job_id, ts, type, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    ev.job_id,
                    ev.ts,
                    ev.type,
                    (json.dumps(ev.payload, ensure_ascii=False) if ev.payload is not None else None),
                ),
            )
        conn.commit()
        # Best-effort artifact writes (non-transactional).
        for ev in events:
            try:
                artifacts.append_event(artifacts_dir, ev.job_id, type=ev.type, payload=ev.payload)
            except Exception:
                pass

    @property
    def pending_count(self) -> int:
        return len(self._events)
