"""MemoryInjector — retrieves relevant past experiences for task context.

Queries memory.db for relevant records (past task summaries, failures,
route decisions) and formats them for injection into the advisor graph's
system prompt, enabling the system to learn from past experiences.
"""

from __future__ import annotations

import logging
import sqlite3
import os
import pathlib
from datetime import datetime, timezone, timedelta
from typing import Any

from .registry import ActuatorMode, GovernedActuatorState

logger = logging.getLogger(__name__)

_DEFAULT_MEMORY_DB = str(
    pathlib.Path(os.path.expanduser("~/.openmind/memory.db"))
)


class MemoryInjector:
    """Retrieves relevant past experiences from memory.db for task context.

    Usage::

        injector = MemoryInjector()
        context = injector.retrieve(domain="routing", limit=3)
        if context:
            system_prompt += context

    Returns formatted context string for system prompt injection,
    or empty string if no relevant memories found.
    """

    def __init__(
        self,
        db_path: str = "",
        *,
        mode: ActuatorMode = ActuatorMode.ACTIVE,
        owner: str = "evomap.runtime",
        candidate_version: str = "memory-injector-live",
        rollback_trigger: str = "memory_grounding_regression",
    ) -> None:
        self._db_path = db_path or _DEFAULT_MEMORY_DB
        self._governance_state = GovernedActuatorState(
            "memory_injector",
            mode=mode,
            owner=owner,
            candidate_version=candidate_version,
            rollback_trigger=rollback_trigger,
        )
        logger.info("MemoryInjector initialized: db=%s", self._db_path)

    @property
    def governance(self) -> dict[str, Any]:
        return self._governance_state.describe()

    def describe_governance(self) -> dict[str, Any]:
        return self._governance_state.describe()

    def get_audit_trail(self) -> list[dict[str, Any]]:
        return self._governance_state.snapshot()

    def update_governance(self, **kwargs: Any) -> dict[str, Any]:
        return self._governance_state.update_governance(**kwargs)

    def retrieve(
        self,
        domain: str = "",
        category: str = "",
        limit: int = 3,
        max_age_hours: int = 168,  # 7 days
    ) -> str:
        """Retrieve relevant past experiences and format as context block.

        Args:
            domain: Filter by signal domain (routing, llm, kb, etc.)
            category: Filter by memory category
            limit: Max number of records to return
            max_age_hours: Only consider records from last N hours

        Returns:
            Formatted context string, or empty string if no memories found.
        """
        if not os.path.exists(self._db_path):
            return ""

        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row

            clauses = []
            params: list[Any] = []

            if category:
                clauses.append("category = ?")
                params.append(category)
            elif domain:
                # Search in key field for domain-related entries
                clauses.append("(key LIKE ? OR category LIKE ?)")
                params.extend([f"%{domain}%", f"%{domain}%"])

            # Time filter
            since = (
                datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            ).isoformat()
            clauses.append("updated_at >= ?")
            params.append(since)

            where = " AND ".join(clauses) if clauses else "1=1"
            sql = (
                f"SELECT tier, category, key, value, confidence, source "
                f"FROM memory_records "
                f"WHERE {where} "
                f"ORDER BY confidence DESC, updated_at DESC "
                f"LIMIT ?"
            )
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            conn.close()

            if not rows:
                return ""

            return self._format_memories(rows)

        except Exception as e:
            logger.warning("MemoryInjector.retrieve failed: %s", e)
            return ""

    def retrieve_failures(self, limit: int = 3) -> str:
        """Specifically retrieve past failure records for learning.

        Looks for route_stat entries with low confidence or failure keywords.
        """
        if not os.path.exists(self._db_path):
            return ""

        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row

            rows = conn.execute(
                "SELECT tier, category, key, value, confidence, source "
                "FROM memory_records "
                "WHERE value LIKE '%fail%' OR value LIKE '%error%' OR confidence < 0.5 "
                "ORDER BY updated_at DESC "
                "LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()

            if not rows:
                return ""

            return self._format_memories(rows, header="past failures")

        except Exception as e:
            logger.warning("MemoryInjector.retrieve_failures failed: %s", e)
            return ""

    def _format_memories(
        self,
        rows: list[Any],
        header: str = "past experiences",
    ) -> str:
        """Format memory rows into a system prompt injection block."""
        lines = []
        for row in rows:
            category = row["category"]
            key = row["key"]
            value = str(row["value"])[:200]  # truncate long values
            confidence = row["confidence"]
            lines.append(f"  - [{category}] {key}: {value} (conf={confidence:.1f})")

        if not lines:
            return ""

        body = "\n".join(lines)
        return (
            f"\n<past_experiences>\n"
            f"以下是系统过去的经验教训，请参考避免重复犯错 ({header}):\n"
            f"{body}\n"
            f"</past_experiences>\n"
        )
