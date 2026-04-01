"""MemoryManager — unified 4-tier memory with staging gate.

Implements the architecture from memory_module_design.md:

Tiers:
  - Working:  Current session context, hot data (<10ms)
  - Episodic: Task history, debate records, reports (30d TTL)
  - Semantic:  User profile, project knowledge, stable facts (90d+ TTL)
  - Meta:     Route stats, quality scores, audit trail (permanent)

Write pipeline:
  stage() → validate() → promote() — with conflict detection + audit

Design decisions:
  - SQLite single-table + audit table (shared DB with LangGraph checkpoint)
  - StagingGate enforces write control (min_confidence per tier)
  - All writes are audited (who, when, why, source)
  - Fingerprint-based deduplication
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────────

class MemoryTier(str, Enum):
    STAGING = "staging"
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    META = "meta"


class SourceType(str, Enum):
    USER_INPUT = "user_input"
    LLM_INFERENCE = "llm_inference"
    TOOL_RESULT = "tool_result"
    EVOMAP_SIGNAL = "evomap_signal"
    SYSTEM = "system"


# ── Data Models ───────────────────────────────────────────────────

@dataclass
class MemorySource:
    """Who/what produced this memory record."""
    type: str = "system"          # SourceType value
    agent: str = "aios"           # Component identity: "advisor" | "openclaw" etc.
    role: str = ""                # Business role: "devops" | "research" etc.
    session_id: str = ""
    account_id: str = ""
    thread_id: str = ""
    task_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MemoryRecord:
    """A single memory record in the unified store."""
    record_id: str = ""           # ULID or UUID
    tier: str = "staging"         # MemoryTier value
    category: str = ""            # "intent" | "route_stat" | "task_result" etc.
    key: str = ""                 # Namespaced: "intent:{task_id}" etc.
    value: dict = field(default_factory=dict)  # Structured content
    confidence: float = 0.0       # 0.0-1.0
    source: dict = field(default_factory=dict)  # MemorySource as dict
    evidence_span: str = ""       # Original evidence snippet
    fingerprint: str = ""         # Content hash for dedup
    ttl_seconds: int | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── DDL ───────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS memory_records (
    record_id     TEXT PRIMARY KEY,
    tier          TEXT NOT NULL,
    category      TEXT NOT NULL,
    key           TEXT NOT NULL,
    value         TEXT NOT NULL,
    confidence    REAL DEFAULT 0.0,
    source        TEXT NOT NULL,
    evidence      TEXT,
    fingerprint   TEXT,
    ttl_expires_at TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    session_id    TEXT DEFAULT '',
    agent_id      TEXT DEFAULT '',
    role_id       TEXT DEFAULT '',
    account_id    TEXT DEFAULT '',
    thread_id     TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_memory_tier ON memory_records(tier);
CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_records(tier, category);
CREATE INDEX IF NOT EXISTS idx_memory_key ON memory_records(key);
CREATE INDEX IF NOT EXISTS idx_memory_fingerprint ON memory_records(fingerprint);
CREATE INDEX IF NOT EXISTS idx_memory_expires ON memory_records(ttl_expires_at)
    WHERE ttl_expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_records(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_agent_role ON memory_records(agent_id, role_id);
CREATE INDEX IF NOT EXISTS idx_memory_account_thread ON memory_records(account_id, thread_id);
CREATE INDEX IF NOT EXISTS idx_memory_dedup_scope
    ON memory_records(fingerprint, category, agent_id, role_id, session_id, account_id, thread_id);

CREATE TABLE IF NOT EXISTS memory_audit (
    audit_id   TEXT PRIMARY KEY,
    record_id  TEXT NOT NULL,
    action     TEXT NOT NULL,
    old_tier   TEXT,
    new_tier   TEXT,
    reason     TEXT,
    agent      TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_record ON memory_audit(record_id);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(value: dict) -> str:
    """Content-hash for deduplication."""
    raw = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── StagingGate ───────────────────────────────────────────────────

class StagingGate:
    """Write control gate with tier-specific promotion rules."""

    PROMOTION_RULES = {
        MemoryTier.WORKING:  {"min_confidence": 0.0},
        MemoryTier.EPISODIC: {"min_confidence": 0.5},
        MemoryTier.SEMANTIC: {"min_confidence": 0.65, "min_occurrences": 2},
        MemoryTier.META:     {"min_confidence": 0.0},  # immediate for system metrics
    }

    def can_promote(self, record: MemoryRecord, target: MemoryTier,
                    occurrence_count: int = 1) -> tuple[bool, str]:
        """Check if a record can be promoted to the target tier.

        Returns (allowed, reason).
        """
        rules = self.PROMOTION_RULES.get(target, {})
        min_conf = rules.get("min_confidence", 0.0)
        min_occur = rules.get("min_occurrences", 1)

        if record.confidence < min_conf:
            return False, f"confidence {record.confidence:.2f} < {min_conf}"
        if occurrence_count < min_occur:
            return False, f"occurrences {occurrence_count} < {min_occur}"
        return True, "ok"


# ── MemoryManager ─────────────────────────────────────────────────

class MemoryManager:
    """Unified 4-tier memory manager with SQLite persistence.

    Usage::

        mm = MemoryManager("~/.openmind/memory.db")
        record_id = mm.stage(MemoryRecord(
            category="intent", key="intent:tr_001",
            value={"intent": "DO_RESEARCH", "confidence": 0.85},
            confidence=0.85,
            source=MemorySource(type="llm_inference", agent="advisor").to_dict(),
        ))
        mm.promote(record_id, MemoryTier.WORKING)

        # Read
        items = mm.get_working_context(session_id="sess_001")
        history = mm.get_episodic(query="PEEK", limit=5)
        profile = mm.get_semantic(domain="user_profile")
        stats = mm.get_meta(key="route_stats")
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._local = threading.local()
        self._gate = StagingGate()
        self._init_db()

    _IDENTITY_FIELDS = ("agent_id", "role_id", "session_id", "account_id", "thread_id")

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=3000")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _init_db(self) -> None:
        conn = self._conn()
        # First ensure the base table exists (without indexes) so we can inspect it safely
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_records (
                record_id TEXT PRIMARY KEY, tier TEXT NOT NULL, category TEXT NOT NULL,
                key TEXT NOT NULL, value TEXT NOT NULL, confidence REAL DEFAULT 0.0,
                source TEXT NOT NULL, evidence TEXT, fingerprint TEXT,
                ttl_expires_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        self._upgrade_schema(conn)
        conn.executescript(_DDL)
        conn.commit()

    def _upgrade_schema(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute("PRAGMA table_info(memory_records)")
        existing_cols = {row["name"] for row in cursor.fetchall()}

        new_cols = []
        for col in ["session_id", "agent_id", "role_id", "account_id", "thread_id"]:
            if col not in existing_cols:
                new_cols.append(col)

        if new_cols:
            for col in new_cols:
                conn.execute(f"ALTER TABLE memory_records ADD COLUMN {col} TEXT DEFAULT ''")
            logger.info("Migrated memory.db schema: added columns %s", new_cols)

        try:
            conn.execute(
                """
                UPDATE memory_records
                SET
                    session_id = COALESCE(
                        NULLIF(session_id, ''),
                        NULLIF(json_extract(source, '$.session_id'), ''),
                        ''
                    ),
                    agent_id = COALESCE(
                        NULLIF(agent_id, ''),
                        NULLIF(json_extract(source, '$.agent_id'), ''),
                        NULLIF(json_extract(source, '$.agent'), ''),
                        ''
                    ),
                    role_id = COALESCE(
                        NULLIF(role_id, ''),
                        NULLIF(json_extract(source, '$.role_id'), ''),
                        NULLIF(json_extract(source, '$.role'), ''),
                        ''
                    ),
                    account_id = COALESCE(
                        NULLIF(account_id, ''),
                        NULLIF(json_extract(source, '$.account_id'), ''),
                        ''
                    ),
                    thread_id = COALESCE(
                        NULLIF(thread_id, ''),
                        NULLIF(json_extract(source, '$.thread_id'), ''),
                        ''
                    )
                WHERE
                    session_id = ''
                    OR agent_id = ''
                    OR role_id = ''
                    OR account_id = ''
                    OR thread_id = ''
                """
            )
        except Exception as exc:
            logger.warning("Failed to back-fill memory_records identity data: %s", exc)

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None

    # ── Write API ─────────────────────────────────────────────────

    def stage(self, record: MemoryRecord) -> str:
        """Stage a memory record. Returns record_id."""
        now = _now_iso()
        record.source = self._normalize_source(record.source)
        if not record.record_id:
            record.record_id = str(uuid.uuid4())
        if not record.fingerprint:
            record.fingerprint = _fingerprint(record.value)
        record.tier = MemoryTier.STAGING.value
        record.created_at = now
        record.updated_at = now

        # Auto-inject current role from contextvars if not already set
        try:
            from chatgptrest.kernel.role_context import get_current_role_name
            role_name = get_current_role_name()
            if role_name:
                src = record.source if isinstance(record.source, dict) else {}
                if not src.get("role"):
                    src["role"] = role_name
                    record.source = src
        except ImportError:
            pass  # role_context not yet available — graceful degradation

        # TTL calculation
        ttl_expires = None
        if record.ttl_seconds:
            from datetime import timedelta
            expires = datetime.now(timezone.utc) + timedelta(seconds=record.ttl_seconds)
            ttl_expires = expires.isoformat()

        conn = self._conn()
        dedup_params = self._dedup_identity_params(record.source)

        # Dedup only within the same identity scope.
        existing = conn.execute(
            f"""SELECT record_id FROM memory_records
                WHERE fingerprint = ?
                  AND category = ?
                  AND {self._identity_where_clause()}""",
            (record.fingerprint, record.category, *dedup_params),
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE memory_records
                   SET value = ?, confidence = ?, source = ?, updated_at = ?,
                       agent_id = ?, role_id = ?, session_id = ?, account_id = ?, thread_id = ?
                   WHERE record_id = ?""",
                (json.dumps(record.value, ensure_ascii=False),
                 record.confidence,
                 json.dumps(record.source, ensure_ascii=False) if isinstance(record.source, dict) else record.source,
                 now,
                 dedup_params[0], dedup_params[1], dedup_params[2], dedup_params[3], dedup_params[4],
                 existing["record_id"]),
            )
            conn.commit()
            src = record.source if isinstance(record.source, dict) else {}
            self._audit(existing["record_id"], "update", record.tier, record.tier,
                        "dedup merge", src.get("agent", "system"))
            return existing["record_id"]

        # Insert new
        conn.execute(
            """INSERT INTO memory_records
               (record_id, tier, category, key, value, confidence,
                source, evidence, fingerprint, ttl_expires_at,
                created_at, updated_at, agent_id, role_id, session_id, account_id, thread_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.record_id, record.tier, record.category,
                record.key,
                json.dumps(record.value, ensure_ascii=False),
                record.confidence,
                json.dumps(record.source, ensure_ascii=False),
                record.evidence_span, record.fingerprint,
                ttl_expires, now, now,
                dedup_params[0], dedup_params[1], dedup_params[2], dedup_params[3], dedup_params[4],
            ),
        )
        conn.commit()
        self._audit(record.record_id, "stage", None, MemoryTier.STAGING.value,
                     "initial staging", record.source.get("agent", "system"))
        return record.record_id

    def promote(self, record_id: str, target: MemoryTier,
                reason: str = "") -> bool:
        """Promote a staged record to a target tier.

        Checks StagingGate rules before promotion.
        Returns True if promoted, False if rejected.
        """
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM memory_records WHERE record_id = ?",
            (record_id,),
        ).fetchone()

        if not row:
            return False

        record = self._row_to_record(row)

        occur_count = self._count_occurrences(conn, record)

        allowed, gate_reason = self._gate.can_promote(record, target, occur_count)
        if not allowed:
            logger.info("Promotion rejected: %s → %s: %s", record_id, target, gate_reason)
            self._audit(record_id, "reject", record.tier, target.value,
                        gate_reason, "system")
            return False

        # Promote
        now = _now_iso()
        conn.execute(
            """UPDATE memory_records
               SET tier = ?, updated_at = ?
               WHERE record_id = ?""",
            (target.value, now, record_id),
        )
        conn.commit()
        self._audit(record_id, "promote", record.tier, target.value,
                     reason or "gate passed", "system")
        return True

    def stage_and_promote(self, record: MemoryRecord, target: MemoryTier,
                          reason: str = "") -> str:
        """Convenience: stage + immediate promote for high-confidence records."""
        record_id = self.stage(record)
        self.promote(record_id, target, reason)
        return record_id

    # ── Read API ──────────────────────────────────────────────────

    def get_working_context(self, session_id: str = "",
                            limit: int = 20) -> list[MemoryRecord]:
        """Get current working memory (hot context)."""
        conn = self._conn()
        if session_id:
            rows = conn.execute(
                """SELECT * FROM memory_records
                   WHERE tier = 'working'
                   AND session_id = ?
                   ORDER BY updated_at DESC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM memory_records
                   WHERE tier = 'working'
                   ORDER BY updated_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_episodic(self, query: str = "", category: str = "",
                     limit: int = 10, agent_id: str = "",
                     session_id: str = "",
                     role_id: str = "",
                     account_id: str = "",
                     thread_id: str = "") -> list[MemoryRecord]:
        """Get episodic memory (task history, reports).

        Args:
            agent_id: If set, only return records created by this agent/component
                      (matches first-class agent_id column).
            role_id: If set, only return records from this business role
                     (matches first-class role_id column).
            session_id: If set, only return records from this session
                        (tenant isolation via first-class session_id column).
            account_id: If set, only return records from this account.
            thread_id: If set, only return records from this thread/conversation.
        """
        conn = self._conn()
        clauses = ["tier = 'episodic'"]
        params: list[Any] = []

        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if query:
            # Simple keyword match on value JSON
            clauses.append("value LIKE ?")
            params.append(f"%{query}%")
        if agent_id:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if role_id:
            clauses.append("role_id = ?")
            params.append(role_id)
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if thread_id:
            clauses.append("thread_id = ?")
            params.append(thread_id)

        where = " AND ".join(clauses)
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM memory_records WHERE {where} ORDER BY updated_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_semantic(self, domain: str = "", key: str = "",
                     agent_id: str = "",
                     session_id: str = "",
                     role_id: str = "",
                     account_id: str = "",
                     thread_id: str = "") -> list[MemoryRecord]:
        """Get semantic memory (stable knowledge, user profile).

        Args:
            agent_id: If set, only return records created by this agent/component
                      (matches first-class agent_id column).
            role_id: If set, only return records from this business role
                     (matches first-class role_id column).
            session_id: If set, only return records from this session
                        (tenant isolation via first-class session_id column).
            account_id: If set, only return records from this account.
            thread_id: If set, only return records from this thread/conversation.
        """
        conn = self._conn()
        clauses = ["tier = 'semantic'"]
        params: list[Any] = []

        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if domain:
            clauses.append("category = ?")
            params.append(domain)
        if key:
            clauses.append("key = ?")
            params.append(key)
        if agent_id:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if role_id:
            clauses.append("role_id = ?")
            params.append(role_id)
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if thread_id:
            clauses.append("thread_id = ?")
            params.append(thread_id)

        where = " AND ".join(clauses)
        rows = conn.execute(
            f"SELECT * FROM memory_records WHERE {where} ORDER BY updated_at DESC LIMIT 50",
            params,
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_meta(self, key: str = "", category: str = "",
                 limit: int = 50) -> list[MemoryRecord]:
        """Get meta memory (route stats, quality scores, audit)."""
        conn = self._conn()
        clauses = ["tier = 'meta'"]
        params: list[Any] = []

        if key:
            clauses.append("key = ?")
            params.append(key)
        if category:
            clauses.append("category = ?")
            params.append(category)

        where = " AND ".join(clauses)
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM memory_records WHERE {where} ORDER BY updated_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_by_key(self, key: str) -> MemoryRecord | None:
        """Get a single record by key (exact match)."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM memory_records WHERE key = ? ORDER BY updated_at DESC LIMIT 1",
            (key,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def get_by_record_id(self, record_id: str) -> MemoryRecord | None:
        """Get a single record by its record_id."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM memory_records WHERE record_id = ? LIMIT 1",
            (record_id,),
        ).fetchone()
        return self._row_to_record(row) if row else None

    def update_record_value(
        self,
        record_id: str,
        value: dict[str, Any],
        *,
        reason: str = "",
        agent: str = "system",
    ) -> bool:
        """Replace a record value in place and emit an audit entry."""
        record = self.get_by_record_id(record_id)
        if record is None:
            return False

        now = _now_iso()
        conn = self._conn()
        conn.execute(
            """UPDATE memory_records
               SET value = ?, fingerprint = ?, updated_at = ?
               WHERE record_id = ?""",
            (
                json.dumps(value, ensure_ascii=False),
                _fingerprint(value),
                now,
                record_id,
            ),
        )
        conn.commit()
        self._audit(
            record_id,
            "update",
            record.tier,
            record.tier,
            reason or "record updated",
            agent,
        )
        return True

    # ── Stats ─────────────────────────────────────────────────────

    def count_by_tier(self) -> dict[str, int]:
        """Count records by tier."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT tier, count(*) as cnt FROM memory_records GROUP BY tier"
        ).fetchall()
        return {r["tier"]: r["cnt"] for r in rows}

    def count_total(self) -> int:
        """Total records across all tiers."""
        conn = self._conn()
        return conn.execute("SELECT count(*) FROM memory_records").fetchone()[0]

    def audit_trail(self, record_id: str) -> list[dict]:
        """Get audit trail for a record."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM memory_audit WHERE record_id = ? ORDER BY created_at",
            (record_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Cleanup ───────────────────────────────────────────────────

    def expire_records(self) -> int:
        """Remove expired records. Returns count removed."""
        now = _now_iso()
        conn = self._conn()
        result = conn.execute(
            "DELETE FROM memory_records WHERE ttl_expires_at IS NOT NULL AND ttl_expires_at < ?",
            (now,),
        )
        conn.commit()
        return result.rowcount

    # ── Conversation History (M1) ─────────────────────────────────────

    # Working memory capacity limit
    WORKING_CAPACITY = 50

    def add_conversation_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        *,
        agent: str = "advisor",
    ) -> str:
        """Add a conversation turn to working memory.

        This is the core M1 feature: storing conversation history
        in working memory for multi-turn conversation context.

        Args:
            session_id: Session ID for isolation
            user_message: User's message
            assistant_response: Assistant's response
            agent: Agent name (default: advisor)

        Returns:
            Record ID of the added turn
        """
        conn = self._conn()

        # Check current working memory capacity for this session.
        # WORKING_CAPACITY is a record budget, but a conversation turn writes
        # a user/assistant pair. Evict whole turn pairs so history never drifts
        # into orphaned single-message records.
        count_row = conn.execute(
            """SELECT count(*) FROM memory_records
               WHERE tier = 'working'
               AND session_id = ?""",
            (session_id,),
        ).fetchone()
        current_count = count_row[0] if count_row else 0

        # If at capacity, remove oldest turn pair(s) until the incoming turn
        # fits inside the configured working-memory budget.
        while current_count + 2 > self.WORKING_CAPACITY:
            oldest = conn.execute(
                """SELECT record_id, json_extract(value, '$.turn_id') AS turn_id
                   FROM memory_records
                   WHERE tier = 'working'
                   AND session_id = ?
                   ORDER BY created_at ASC LIMIT 1""",
                (session_id,),
            ).fetchone()
            if oldest is None:
                break

            turn_id = oldest["turn_id"] if isinstance(oldest, sqlite3.Row) else oldest[1]
            if turn_id:
                result = conn.execute(
                    """DELETE FROM memory_records
                       WHERE tier = 'working'
                       AND session_id = ?
                       AND json_extract(value, '$.turn_id') = ?""",
                    (session_id, turn_id),
                )
            else:
                # Fallback for legacy rows without turn_id metadata.
                result = conn.execute(
                    """DELETE FROM memory_records
                       WHERE tier = 'working'
                       AND record_id IN (
                           SELECT record_id
                           FROM memory_records
                           WHERE tier = 'working'
                           AND session_id = ?
                           ORDER BY created_at ASC LIMIT 2
                       )""",
                    (session_id,),
                )

            deleted = max(int(result.rowcount or 0), 0)
            if deleted == 0:
                break
            current_count = max(current_count - deleted, 0)
            logger.debug(
                "Evicted %d working-memory record(s) for session %s to fit a new turn",
                deleted,
                session_id,
            )

        # BUG-4 fix: use unique key per turn to prevent fingerprint dedup
        # from overwriting previous turns with identical content.
        turn_id = str(uuid.uuid4())[:8]
        user_record = MemoryRecord(
            category="conversation",
            key=f"conv:{session_id}:user:{turn_id}",
            value={
                "role": "user",
                "message": user_message,
                "turn_id": turn_id,
            },
            confidence=1.0,
            source=MemorySource(
                type=SourceType.USER_INPUT.value,
                agent=agent,
                session_id=session_id,
            ).to_dict(),
            ttl_seconds=3600,  # 1 hour TTL for conversation
        )

        # Create assistant response record (same turn_id for pairing)
        assistant_record = MemoryRecord(
            category="conversation",
            key=f"conv:{session_id}:assistant:{turn_id}",
            value={
                "role": "assistant",
                "message": assistant_response,
                "turn_id": turn_id,
            },
            confidence=1.0,
            source=MemorySource(
                type=SourceType.LLM_INFERENCE.value,
                agent=agent,
                session_id=session_id,
            ).to_dict(),
            ttl_seconds=3600,  # 1 hour TTL for conversation
        )

        # Stage and promote both records
        user_id = self.stage_and_promote(
            user_record,
            MemoryTier.WORKING,
            reason="conversation turn",
        )
        assistant_id = self.stage_and_promote(
            assistant_record,
            MemoryTier.WORKING,
            reason="conversation turn",
        )

        return user_id

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """Get conversation history for a session.

        Args:
            session_id: Session ID
            limit: Maximum number of turns to return

        Returns:
            List of dicts with 'role' and 'message' keys
        """
        records = self.get_working_context(session_id=session_id, limit=limit * 2)

        # Extract conversation turns
        turns = []
        for rec in records:
            if rec.category == "conversation":
                turns.append({
                    "role": rec.value.get("role", "unknown"),
                    "message": rec.value.get("message", ""),
                })

        # Sort by recency (most recent first)
        turns.reverse()

        # Return as message pairs (user + assistant)
        return turns[:limit]

    def clear_session(self, session_id: str) -> int:
        """Clear all working memory for a session.

        Args:
            session_id: Session ID to clear

        Returns:
            Number of records deleted
        """
        conn = self._conn()
        result = conn.execute(
            """DELETE FROM memory_records
               WHERE tier = 'working'
               AND session_id = ?""",
            (session_id,),
        )
        conn.commit()
        return result.rowcount

    # ── Internal ──────────────────────────────────────────────────

    def _audit(self, record_id: str, action: str,
               old_tier: str | None, new_tier: str | None,
               reason: str, agent: str) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT INTO memory_audit
               (audit_id, record_id, action, old_tier, new_tier, reason, agent, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), record_id, action, old_tier, new_tier,
             reason, agent, _now_iso()),
        )
        conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            record_id=row["record_id"],
            tier=row["tier"],
            category=row["category"],
            key=row["key"],
            value=json.loads(row["value"]),
            confidence=row["confidence"],
            source=json.loads(row["source"]),
            evidence_span=row["evidence"] or "",
            fingerprint=row["fingerprint"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @classmethod
    def _identity_where_clause(cls) -> str:
        return " AND ".join(
            f"COALESCE({field}, '') = ?"
            for field in cls._IDENTITY_FIELDS
        )

    @classmethod
    def _dedup_identity_params(cls, source: dict[str, Any] | Any) -> tuple[str, ...]:
        src = cls._normalize_source(source)
        return tuple(str(src.get(field) or "").strip() for field in cls._IDENTITY_FIELDS)

    @classmethod
    def _normalize_source(cls, source: dict[str, Any] | Any) -> dict[str, Any]:
        if not isinstance(source, dict):
            source = {}
        normalized = dict(source)
        if "agent" in normalized and "agent_id" not in normalized:
            normalized["agent_id"] = normalized["agent"]
        if "role" in normalized and "role_id" not in normalized:
            normalized["role_id"] = normalized["role"]
        for field in cls._IDENTITY_FIELDS:
            normalized[field] = str(normalized.get(field) or "").strip()
        normalized["type"] = str(normalized.get("type") or "system").strip() or "system"
        normalized["task_id"] = str(normalized.get("task_id") or "").strip()
        return normalized

    def _count_occurrences(self, conn: sqlite3.Connection, record: MemoryRecord) -> int:
        params = self._dedup_identity_params(record.source)
        row = conn.execute(
            f"""SELECT count(*) FROM memory_records
                WHERE fingerprint = ?
                  AND {self._identity_where_clause()}""",
            (record.fingerprint, *params),
        ).fetchone()
        return int(row[0]) if row else 0
