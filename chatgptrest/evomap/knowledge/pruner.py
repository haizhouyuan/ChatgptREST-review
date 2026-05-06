"""KBPruner — removes stale and useless KB artifacts.

Rules:
  - quality_score == 0.0 for >14 days → DELETE
  - quality_score < 0.0 → DELETE immediately
  - Never accessed (no kb.search_hit) for >30 days → stability=expired
"""

from __future__ import annotations

import logging
import os
import pathlib
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_KB_REGISTRY_DB = str(
    pathlib.Path(os.path.expanduser("~/.openmind/kb_registry.db"))
)
_ZERO_SCORE_MAX_AGE_DAYS = 14
_NEVER_ACCESSED_MAX_AGE_DAYS = 30


class KBPruner:
    """Periodically removes stale/useless KB artifacts.

    Usage::

        pruner = KBPruner(observer=evomap_observer)
        stats = pruner.run()
        # stats = {"deleted": 2, "expired": 1}
    """

    def __init__(
        self,
        registry_db: str = "",
        observer: Any = None,
    ) -> None:
        self._registry_db = registry_db or _KB_REGISTRY_DB
        self._observer = observer
        logger.info("KBPruner initialized")

    def run(self) -> dict[str, int]:
        """Execute pruning rules. Returns stats."""
        if not os.path.exists(self._registry_db):
            return {"deleted": 0, "expired": 0}

        conn = sqlite3.connect(self._registry_db)
        conn.row_factory = sqlite3.Row
        now = datetime.now(timezone.utc)
        stats = {"deleted": 0, "expired": 0}

        # Rule 1: quality_score < 0 → delete immediately
        neg_rows = conn.execute(
            "SELECT artifact_id, source_path FROM artifacts "
            "WHERE quality_score < 0"
        ).fetchall()
        for row in neg_rows:
            self._delete_artifact(conn, row["artifact_id"], row["source_path"])
            stats["deleted"] += 1
            self._emit_pruned(row["artifact_id"], "negative_score")

        # Rule 2: quality_score == 0 for >14 days → delete
        cutoff_14d = (now - timedelta(days=_ZERO_SCORE_MAX_AGE_DAYS)).isoformat()
        zero_rows = conn.execute(
            "SELECT artifact_id, source_path FROM artifacts "
            "WHERE quality_score = 0.0 AND indexed_at < ? "
            "AND stability != 'archived'",
            (cutoff_14d,),
        ).fetchall()
        for row in zero_rows:
            self._delete_artifact(conn, row["artifact_id"], row["source_path"])
            stats["deleted"] += 1
            self._emit_pruned(row["artifact_id"], "zero_score_14d")

        # Rule 3: never accessed for >30 days → mark expired
        cutoff_30d = (now - timedelta(days=_NEVER_ACCESSED_MAX_AGE_DAYS)).isoformat()
        stale_rows = conn.execute(
            "SELECT artifact_id FROM artifacts "
            "WHERE indexed_at < ? AND stability = 'active' "
            "AND quality_score = 0.0",
            (cutoff_30d,),
        ).fetchall()
        for row in stale_rows:
            conn.execute(
                "UPDATE artifacts SET stability = 'expired' WHERE artifact_id = ?",
                (row["artifact_id"],),
            )
            stats["expired"] += 1

        conn.commit()
        conn.close()

        logger.info(
            "KBPruner: deleted=%d expired=%d", stats["deleted"], stats["expired"],
        )
        return stats

    def _delete_artifact(
        self,
        conn: sqlite3.Connection,
        artifact_id: str,
        source_path: str,
    ) -> None:
        """Delete artifact from registry and optionally from disk."""
        conn.execute(
            "DELETE FROM artifacts WHERE artifact_id = ?", (artifact_id,),
        )
        # Also try to remove from FTS
        try:
            search_db = self._registry_db.replace("kb_registry.db", "kb_search.db")
            if os.path.exists(search_db):
                sc = sqlite3.connect(search_db)
                sc.execute(
                    "DELETE FROM kb_fts WHERE artifact_id = ?", (artifact_id,),
                )
                sc.commit()
                sc.close()
        except Exception:
            pass

        # Don't delete file — just remove from registry
        logger.info("KBPruner: deleted artifact %s", artifact_id)

    def _emit_pruned(self, artifact_id: str, reason: str) -> None:
        if not self._observer:
            return
        try:
            self._observer.record_event(
                trace_id="",
                signal_type="kb.artifact_pruned",
                source="kb_pruner",
                domain="kb",
                data={"artifact_id": artifact_id, "reason": reason},
            )
        except Exception:
            pass
