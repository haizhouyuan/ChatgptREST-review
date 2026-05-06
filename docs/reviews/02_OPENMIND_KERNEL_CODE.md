# OpenMind Kernel Code Bundle

Generated: 2026-02-28

Repository: `/vol1/1000/projects/openmind`

## File: artifact_store.py

```python
"""Content-addressable artifact storage with provenance tracking.

Adapted from planning/aios kernel for ChatgptREST conventions.

Design principles:
  - artifact_id = SHA256(content) — automatic deduplication
  - artifacts table = content metadata (INSERT OR IGNORE keeps first writer)
  - artifact_productions table = every production event (always INSERT)
  - Atomic writes via temp file + os.replace()
  - Thread-safe SQLite with WAL mode
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union


@dataclass
class Artifact:
    """Immutable artifact metadata snapshot."""

    artifact_id: str          # SHA256(content)
    content_type: str         # "text/markdown" | "application/json" | …
    content_path: str         # filesystem path (hash-named)
    task_id: str
    step_id: str
    producer: str             # module / capability name
    evidence_refs: list[str] = field(default_factory=list)
    security_label: str = "internal"
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Artifact:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ArtifactStore:
    """Content-addressable artifact storage with atomic writes."""

    def __init__(self, base_dir: str | Path, db_path: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    # ── Connection management ─────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                isolation_level=None,  # autocommit
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id   TEXT PRIMARY KEY,
                content_type  TEXT NOT NULL,
                content_path  TEXT NOT NULL,
                evidence_refs TEXT DEFAULT '[]',
                security_label TEXT DEFAULT 'internal',
                created_at    TEXT NOT NULL,
                metadata      TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artifact_productions (
                production_id TEXT PRIMARY KEY,
                artifact_id   TEXT NOT NULL,
                task_id       TEXT NOT NULL,
                step_id       TEXT NOT NULL,
                producer      TEXT NOT NULL,
                security_label TEXT DEFAULT 'internal',
                created_at    TEXT NOT NULL,
                metadata      TEXT DEFAULT '{}'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_task ON artifact_productions(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prod_artifact ON artifact_productions(artifact_id)")

    def close(self) -> None:
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn

    # ── Core operations ───────────────────────────────────────────

    @staticmethod
    def compute_id(content: Union[str, bytes]) -> str:
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def _content_path(self, artifact_id: str) -> Path:
        return self.base_dir / artifact_id[:2] / artifact_id

    def store(
        self,
        content: Union[str, bytes],
        *,
        task_id: str,
        step_id: str,
        producer: str,
        content_type: str = "text/markdown",
        evidence_refs: Optional[list[str]] = None,
        security_label: str = "internal",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Artifact:
        """Store content with atomic write; returns Artifact with provenance."""
        artifact_id = self.compute_id(content)
        content_path = self._content_path(artifact_id)
        content_path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        evidence_refs = evidence_refs or []
        metadata = metadata or {}

        # Atomic write: temp → rename
        raw = content.encode("utf-8") if isinstance(content, str) else content
        tmp = content_path.with_suffix(".tmp")
        try:
            tmp.write_bytes(raw)
            os.replace(tmp, content_path)
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise

        conn = self._get_conn()

        # INSERT OR IGNORE: first writer wins for metadata
        conn.execute(
            """INSERT OR IGNORE INTO artifacts
               (artifact_id, content_type, content_path, evidence_refs,
                security_label, created_at, metadata)
               VALUES (?,?,?,?,?,?,?)""",
            (
                artifact_id,
                content_type,
                str(content_path),
                json.dumps(evidence_refs),
                security_label,
                now,
                json.dumps(metadata),
            ),
        )

        # Always record production event
        conn.execute(
            """INSERT INTO artifact_productions
               (production_id, artifact_id, task_id, step_id, producer,
                security_label, created_at, metadata)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                uuid.uuid4().hex,
                artifact_id,
                task_id,
                step_id,
                producer,
                security_label,
                now,
                json.dumps(metadata),
            ),
        )

        return Artifact(
            artifact_id=artifact_id,
            content_type=content_type,
            content_path=str(content_path),
            task_id=task_id,
            step_id=step_id,
            producer=producer,
            evidence_refs=evidence_refs,
            security_label=security_label,
            created_at=now,
            metadata=metadata,
        )

    def get(self, artifact_id: str) -> Optional[Artifact]:
        conn = self._get_conn()
        row = conn.execute(
            """SELECT a.artifact_id, a.content_type, a.content_path,
                      p.task_id, p.step_id, p.producer,
                      a.evidence_refs, a.security_label, a.created_at, a.metadata
               FROM artifacts a
               LEFT JOIN artifact_productions p ON a.artifact_id = p.artifact_id
               WHERE a.artifact_id = ?
               ORDER BY p.created_at ASC
               LIMIT 1""",
            (artifact_id,),
        ).fetchone()
        if not row:
            return None
        return Artifact(
            artifact_id=row[0],
            content_type=row[1],
            content_path=row[2],
            task_id=row[3] or "",
            step_id=row[4] or "",
            producer=row[5] or "",
            evidence_refs=json.loads(row[6]),
            security_label=row[7],
            created_at=row[8],
            metadata=json.loads(row[9]),
        )

    def get_content(self, artifact_id: str) -> Optional[Union[str, bytes]]:
        """Read and integrity-verify content."""
        artifact = self.get(artifact_id)
        if not artifact:
            return None
        path = Path(artifact.content_path)
        if not path.exists():
            return None
        raw = path.read_bytes()
        if self.compute_id(raw) != artifact_id:
            raise ValueError(f"Artifact {artifact_id} content hash mismatch")
        if artifact.content_type.startswith("text/") or artifact.content_type == "application/json":
            return raw.decode("utf-8")
        return raw

    def list_by_task(self, task_id: str) -> list[Artifact]:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT a.artifact_id, a.content_type, a.content_path,
                      p.task_id, p.step_id, p.producer,
                      a.evidence_refs, a.security_label, a.created_at, a.metadata
               FROM artifacts a
               INNER JOIN artifact_productions p ON a.artifact_id = p.artifact_id
               WHERE p.task_id = ?
               ORDER BY p.created_at DESC""",
            (task_id,),
        ).fetchall()
        return [
            Artifact(
                artifact_id=r[0], content_type=r[1], content_path=r[2],
                task_id=r[3], step_id=r[4], producer=r[5],
                evidence_refs=json.loads(r[6]), security_label=r[7],
                created_at=r[8], metadata=json.loads(r[9]),
            )
            for r in rows
        ]
```

## File: event_bus.py

```python
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
import time
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
        if self._db_path:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    def _get_conn(self) -> sqlite3.Connection | None:
        if not self._db_path:
            return None
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                isolation_level=None,
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

    def emit(self, event: TraceEvent) -> None:
        """Persist event and notify all subscribers."""
        # 1. Persist
        self._persist(event)

        # 2. Notify subscribers (errors logged, never propagated)
        with self._lock:
            subs = list(self._subscribers)
        for handler in subs:
            try:
                handler(event)
            except Exception:
                logger.exception("EventBus subscriber error for %s", event.event_type)

    def _persist(self, event: TraceEvent) -> None:
        conn = self._get_conn()
        if conn is None:
            return
        try:
            conn.execute(
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
        except sqlite3.IntegrityError:
            logger.debug("Duplicate event_id %s (idempotent skip)", event.event_id)

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
```

## File: policy_engine.py

```python
"""Policy engine with pluggable quality-gate checker chain.

Adapted from planning/aios kernel for ChatgptREST.

Provides:
  - PII / sensitive-data detection (fail-closed for unknown labels)
  - Cost / token budget enforcement
  - Security label × audience delivery constraints
  - Execution / business dual-success semantics
  - Claim-evidence gating for external outputs
  - Composable quality gate that aggregates all checkers
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol, Union


# ── Data types ────────────────────────────────────────────────────

@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    conditions: list[str] = field(default_factory=list)


@dataclass
class QualityContext:
    """Input context passed through quality checkers."""
    audience: str
    security_label: str
    content: Union[str, bytes]
    estimated_tokens: int = 0
    channel: str = "default"
    risk_level: str = "low"
    execution_success: bool = True
    business_success: bool = True
    claims: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class QualityGateResult:
    allowed: bool
    reason: str
    decisions: dict[str, PolicyDecision] = field(default_factory=dict)
    blocked_by: list[str] = field(default_factory=list)
    requires_human_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "blocked_by": self.blocked_by,
            "requires_human_review": self.requires_human_review,
            "decisions": {
                name: {"allowed": d.allowed, "reason": d.reason, "conditions": list(d.conditions)}
                for name, d in self.decisions.items()
            },
        }


# ── Checker protocol ─────────────────────────────────────────────

class QualityChecker(Protocol):
    name: str

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision: ...


# ── Built-in checkers ─────────────────────────────────────────────

class StructureChecker:
    name = "structure"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        content = context.content
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")
        if not str(content).strip():
            return PolicyDecision(allowed=False, reason="Empty content", conditions=["requires_human_review"])
        return PolicyDecision(allowed=True, reason="Structure OK")


class ExecutionBusinessChecker:
    name = "execution_business"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        return engine.check_execution_business(
            execution_success=context.execution_success,
            business_success=context.business_success,
            audience=context.audience,
        )


class DeliveryChecker:
    name = "delivery"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        return engine.check_delivery_label(context.security_label, context.audience)


class CostChecker:
    name = "cost"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        return engine.check_cost(context.estimated_tokens, context.channel)


class SecurityChecker:
    name = "security"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        if context.security_label not in engine.ALLOWED_LABELS:
            return PolicyDecision(
                allowed=False,
                reason=f"Unknown security_label '{context.security_label}'",
                conditions=["requires_human_review"],
            )
        return engine.check_security(context.content, context.security_label)


class ClaimEvidenceChecker:
    name = "claim_evidence"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        return engine.check_claim_evidence(context.claims, context.audience, context.risk_level)


# ── Policy engine ─────────────────────────────────────────────────

class PolicyEngine:
    """Policy engine with fail-closed defaults."""

    ALLOWED_LABELS = {"public", "internal", "confidential"}

    SENSITIVE_PATTERNS = {
        "path": re.compile(
            r"(?:[A-Za-z]:\\(?:[^\\\/:*?\"<>|\r\n]+\\?)+|/(?:home|Users|tmp|var|etc|opt|vol\d+)(?:/[^\\\/:*?\"<>|\r\n]+)+)"
        ),
        "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "phone_cn": re.compile(r"\b1[3-9]\d{9}\b"),
        "phone_us": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        "id_card_cn": re.compile(
            r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"
        ),
        "credit_card": re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"),
        "api_key": re.compile(
            r'(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token)\s*[:=]\s*["\']?[\w-]{20,}["\']?',
            re.IGNORECASE,
        ),
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.max_tokens_per_task = self.config.get("max_tokens_per_task", 100_000)
        self.max_cost_per_task = self.config.get("max_cost_per_task", 10.0)
        self.confidential_allowed_audiences = self.config.get(
            "confidential_allowed_audiences", ["internal", "admin"]
        )
        self.sensitive_patterns_enabled = self.config.get("sensitive_patterns_enabled", True)

    # ── Individual checks ─────────────────────────────────────────

    def check_delivery_label(self, security_label: str, audience: str) -> PolicyDecision:
        if security_label == "confidential":
            if audience == "external":
                return PolicyDecision(allowed=True, reason="Confidential external communication allowed")
            if audience not in self.confidential_allowed_audiences:
                return PolicyDecision(allowed=False, reason=f"Confidential → {audience} blocked")
        if security_label == "internal" and audience == "external":
            return PolicyDecision(allowed=False, reason="Internal → external blocked")
        return PolicyDecision(allowed=True, reason="Delivery allowed")

    def check_cost(self, estimated_tokens: int, channel: str) -> PolicyDecision:
        if estimated_tokens > self.max_tokens_per_task:
            return PolicyDecision(
                allowed=False,
                reason=f"Tokens {estimated_tokens} > limit {self.max_tokens_per_task}",
                conditions=["reduce_scope"],
            )
        channel_limits = self.config.get("channel_limits", {})
        if channel in channel_limits and estimated_tokens > channel_limits[channel]:
            return PolicyDecision(allowed=False, reason=f"Channel {channel} limit exceeded")
        cost_per_1k = self.config.get("cost_per_1k_tokens", 0.01)
        estimated_cost = (estimated_tokens / 1000) * cost_per_1k
        if estimated_cost > self.max_cost_per_task:
            return PolicyDecision(allowed=False, reason=f"Cost ${estimated_cost:.2f} > ${self.max_cost_per_task}")
        return PolicyDecision(allowed=True, reason="Cost OK")

    def check_security(self, content: Union[str, bytes], security_label: str) -> PolicyDecision:
        if security_label not in self.ALLOWED_LABELS:
            return PolicyDecision(
                allowed=False,
                reason=f"Unknown label '{security_label}'",
                conditions=["requires_human_review"],
            )
        if not self.sensitive_patterns_enabled:
            return PolicyDecision(allowed=True, reason="Security disabled")
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")
        detected = []
        for name, pat in self.SENSITIVE_PATTERNS.items():
            matches = pat.findall(content)
            if matches:
                detected.append(f"{name}:{len(matches)}")
        if detected:
            return PolicyDecision(
                allowed=False,
                reason=f"Sensitive data: {', '.join(detected)}",
                conditions=["pii_redaction_required", "requires_human_review"],
            )
        return PolicyDecision(allowed=True, reason="Security OK")

    def check_execution_business(
        self, execution_success: bool, business_success: bool, audience: str
    ) -> PolicyDecision:
        if not execution_success:
            return PolicyDecision(allowed=False, reason="Execution failed", conditions=["requires_human_review"])
        if not business_success:
            if audience == "external":
                return PolicyDecision(
                    allowed=False,
                    reason="business_success=False blocked for external",
                    conditions=["requires_human_review"],
                )
            return PolicyDecision(allowed=True, reason="business_success=False (internal ok)", conditions=["requires_attention"])
        return PolicyDecision(allowed=True, reason="Exec/business OK")

    def check_claim_evidence(
        self, claims: list[dict[str, Any]], audience: str, risk_level: str
    ) -> PolicyDecision:
        strict = audience == "external" or risk_level == "high"
        if not strict:
            return PolicyDecision(allowed=True, reason="Claim check skipped (non-strict)")
        if not claims:
            return PolicyDecision(
                allowed=False,
                reason="Missing claims for external/high-risk output",
                conditions=["requires_human_review"],
            )
        for i, claim in enumerate(claims):
            refs = claim.get("evidence_refs")
            has_refs = isinstance(refs, list) and len(refs) > 0
            if not has_refs:
                reason = f"Claim[{i}] missing evidence_refs"
                if claim.get("quote"):
                    reason = f"Quote-only claim[{i}] without evidence"
                return PolicyDecision(allowed=False, reason=reason, conditions=["requires_human_review"])
        return PolicyDecision(allowed=True, reason="Claims OK")

    # ── Quality gate ──────────────────────────────────────────────

    def default_checkers(self) -> list[QualityChecker]:
        return [
            StructureChecker(),
            ExecutionBusinessChecker(),
            DeliveryChecker(),
            CostChecker(),
            SecurityChecker(),
            ClaimEvidenceChecker(),
        ]

    def run_quality_gate(
        self,
        context: QualityContext,
        checkers: list[QualityChecker] | None = None,
    ) -> QualityGateResult:
        decisions: dict[str, PolicyDecision] = {}
        blocked_by: list[str] = []
        requires_human = False

        for checker in (checkers or self.default_checkers()):
            d = checker.check(engine=self, context=context)
            decisions[checker.name] = d
            if not d.allowed:
                blocked_by.append(checker.name)
            if "requires_human_review" in d.conditions:
                requires_human = True

        allowed = all(d.allowed for d in decisions.values())
        if not allowed:
            requires_human = True
        return QualityGateResult(
            allowed=allowed,
            reason="Quality gate passed" if allowed else f"Blocked by: {', '.join(blocked_by)}",
            decisions=decisions,
            blocked_by=blocked_by,
            requires_human_review=requires_human,
        )
```
