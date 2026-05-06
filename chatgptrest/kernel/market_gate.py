from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.evomap.paths import resolve_evomap_db_path
from chatgptrest.evomap.signals import SignalDomain, SignalType
from chatgptrest.kernel.skill_manager import CanonicalRegistry

logger = logging.getLogger(__name__)

DEFAULT_SKILL_PLATFORM_DB = "~/.openmind/skill_platform.db"

_DDL = """
CREATE TABLE IF NOT EXISTS capability_gaps (
    gap_id TEXT PRIMARY KEY,
    gap_key TEXT NOT NULL UNIQUE,
    capability_id TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL DEFAULT '',
    repo TEXT NOT NULL DEFAULT '',
    role_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    owner TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'P2',
    suggested_agent TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL DEFAULT '',
    last_seen_at TEXT NOT NULL DEFAULT '',
    hit_count INTEGER NOT NULL DEFAULT 1,
    latest_trace_id TEXT NOT NULL DEFAULT '',
    latest_session_id TEXT NOT NULL DEFAULT '',
    latest_agent_id TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'resolver',
    context_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_capability_gaps_status
    ON capability_gaps(status);
CREATE INDEX IF NOT EXISTS idx_capability_gaps_platform
    ON capability_gaps(platform);
CREATE INDEX IF NOT EXISTS idx_capability_gaps_capability
    ON capability_gaps(capability_id);

CREATE TABLE IF NOT EXISTS capability_gap_events (
    event_id TEXT PRIMARY KEY,
    gap_id TEXT NOT NULL,
    trace_id TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    agent_id TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL DEFAULT '',
    task_type TEXT NOT NULL DEFAULT '',
    suggested_agent TEXT NOT NULL DEFAULT '',
    unmet_json TEXT NOT NULL DEFAULT '[]',
    context_json TEXT NOT NULL DEFAULT '{}',
    observed_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_capability_gap_events_gap
    ON capability_gap_events(gap_id);
CREATE INDEX IF NOT EXISTS idx_capability_gap_events_trace
    ON capability_gap_events(trace_id);

CREATE TABLE IF NOT EXISTS market_skill_candidates (
    candidate_id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    source_market TEXT NOT NULL DEFAULT '',
    source_uri TEXT NOT NULL DEFAULT '',
    capability_ids_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'quarantine',
    trust_level TEXT NOT NULL DEFAULT 'unreviewed',
    quarantine_state TEXT NOT NULL DEFAULT 'pending',
    linked_gap_id TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_market_skill_candidates_status
    ON market_skill_candidates(status);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_skill_platform_db_path(raw: str | os.PathLike[str] = "") -> str:
    candidate = str(raw or "").strip() or os.environ.get("OPENMIND_SKILL_PLATFORM_DB", "").strip() or DEFAULT_SKILL_PLATFORM_DB
    path = Path(candidate).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


@dataclass
class CapabilityGap:
    gap_id: str
    gap_key: str
    capability_id: str
    task_type: str
    platform: str
    repo: str = ""
    role_id: str = ""
    status: str = "open"
    owner: str = ""
    priority: str = "P2"
    suggested_agent: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    hit_count: int = 1
    latest_trace_id: str = ""
    latest_session_id: str = ""
    latest_agent_id: str = ""
    source: str = "resolver"
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MarketSkillCandidate:
    candidate_id: str
    skill_id: str
    source_market: str
    source_uri: str
    capability_ids: list[str] = field(default_factory=list)
    status: str = "quarantine"
    trust_level: str = "unreviewed"
    quarantine_state: str = "pending"
    linked_gap_id: str = ""
    summary: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QuarantineDecision:
    allowed: bool
    skill_id: str
    platform: str
    maturity: str
    quarantine_required: bool
    trust_level: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CapabilityGapRecorder:
    """Persistent capability-gap recorder and quarantine candidate store."""

    def __init__(self, db_path: str = "") -> None:
        self._db_path = resolve_skill_platform_db_path(db_path)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._connections: list[sqlite3.Connection] = []
        self._init_db()

    @property
    def db_path(self) -> str:
        return self._db_path

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=3000")
            self._local.conn = conn
            with self._lock:
                self._connections.append(conn)
        return conn

    def _init_db(self) -> None:
        conn = self._conn()
        conn.executescript(_DDL)
        conn.commit()

    def close(self) -> None:
        with self._lock:
            conns = list(self._connections)
            self._connections.clear()
        for conn in conns:
            try:
                conn.close()
            except Exception:
                logger.debug("closing skill platform db failed", exc_info=True)

    def _gap_key(
        self,
        *,
        capability_id: str,
        task_type: str,
        platform: str,
        repo: str,
        role_id: str,
    ) -> str:
        return "|".join(
            [
                platform.strip() or "unknown-platform",
                task_type.strip() or "unknown-task",
                repo.strip(),
                role_id.strip(),
                capability_id.strip(),
            ]
        )

    def _priority_for(self, capability_id: str, task_type: str) -> str:
        if capability_id in {"investment_analysis", "market_research"}:
            return "P1"
        if task_type in {"investment_research", "market_research", "deep_research"}:
            return "P1"
        return "P2"

    def _row_to_gap(self, row: sqlite3.Row) -> CapabilityGap:
        return CapabilityGap(
            gap_id=str(row["gap_id"]),
            gap_key=str(row["gap_key"]),
            capability_id=str(row["capability_id"]),
            task_type=str(row["task_type"]),
            platform=str(row["platform"]),
            repo=str(row["repo"]),
            role_id=str(row["role_id"]),
            status=str(row["status"]),
            owner=str(row["owner"]),
            priority=str(row["priority"]),
            suggested_agent=str(row["suggested_agent"]),
            first_seen_at=str(row["first_seen_at"]),
            last_seen_at=str(row["last_seen_at"]),
            hit_count=int(row["hit_count"] or 0),
            latest_trace_id=str(row["latest_trace_id"]),
            latest_session_id=str(row["latest_session_id"]),
            latest_agent_id=str(row["latest_agent_id"]),
            source=str(row["source"]),
            context=json.loads(row["context_json"] or "{}"),
        )

    def _normalize_unmet(self, unmet_capabilities: Iterable[dict[str, Any] | Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in unmet_capabilities or []:
            if hasattr(item, "to_dict"):
                payload = item.to_dict()
            else:
                payload = dict(item or {})
            capability_id = str(payload.get("capability_id") or "").strip()
            if not capability_id:
                continue
            normalized.append(
                {
                    "capability_id": capability_id,
                    "reason": str(payload.get("reason") or "bundle_missing"),
                    "required_by_task": str(payload.get("required_by_task") or ""),
                    "candidate_bundles": [str(v) for v in payload.get("candidate_bundles") or [] if str(v).strip()],
                    "candidate_skills": [str(v) for v in payload.get("candidate_skills") or [] if str(v).strip()],
                }
            )
        return normalized

    def promote_unmet(
        self,
        *,
        trace_id: str,
        agent_id: str,
        task_type: str,
        platform: str,
        unmet_capabilities: Iterable[dict[str, Any] | Any],
        suggested_agent: str = "",
        session_id: str = "",
        repo: str = "",
        role_id: str = "",
        source: str = "resolver",
        context: dict[str, Any] | None = None,
    ) -> list[CapabilityGap]:
        normalized = self._normalize_unmet(unmet_capabilities)
        if not normalized:
            return []
        now = _now_iso()
        rows: list[CapabilityGap] = []
        conn = self._conn()
        with conn:
            for unmet in normalized:
                gap_key = self._gap_key(
                    capability_id=unmet["capability_id"],
                    task_type=task_type,
                    platform=platform,
                    repo=repo,
                    role_id=role_id,
                )
                existing = conn.execute(
                    "SELECT * FROM capability_gaps WHERE gap_key = ?",
                    (gap_key,),
                ).fetchone()
                merged_context = dict(context or {})
                merged_context["latest_unmet"] = unmet
                if existing is None:
                    gap_id = uuid.uuid4().hex
                    conn.execute(
                        """
                        INSERT INTO capability_gaps (
                            gap_id, gap_key, capability_id, task_type, platform, repo, role_id,
                            status, owner, priority, suggested_agent, first_seen_at, last_seen_at,
                            hit_count, latest_trace_id, latest_session_id, latest_agent_id, source, context_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', '', ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                        """,
                        (
                            gap_id,
                            gap_key,
                            unmet["capability_id"],
                            task_type,
                            platform,
                            repo,
                            role_id,
                            self._priority_for(unmet["capability_id"], task_type),
                            suggested_agent,
                            now,
                            now,
                            trace_id,
                            session_id,
                            agent_id,
                            source,
                            json.dumps(merged_context, ensure_ascii=False, default=str),
                        ),
                    )
                    record_skill_signal(
                        signal_type=SignalType.CAPABILITY_GAP_OPENED,
                        trace_id=trace_id or f"capability-gap:{gap_id}",
                        source="skill_platform.capability_gap_recorder",
                        agent_id=agent_id,
                        task_type=task_type,
                        platform=platform,
                        unmet_capabilities=[unmet],
                        extra={"gap_id": gap_id, "status": "open", "suggested_agent": suggested_agent},
                    )
                else:
                    gap_id = str(existing["gap_id"])
                    conn.execute(
                        """
                        UPDATE capability_gaps
                        SET last_seen_at = ?,
                            hit_count = hit_count + 1,
                            latest_trace_id = ?,
                            latest_session_id = ?,
                            latest_agent_id = ?,
                            suggested_agent = ?,
                            source = ?,
                            context_json = ?
                        WHERE gap_id = ?
                        """,
                        (
                            now,
                            trace_id,
                            session_id,
                            agent_id,
                            suggested_agent,
                            source,
                            json.dumps(merged_context, ensure_ascii=False, default=str),
                            gap_id,
                        ),
                    )
                conn.execute(
                    """
                    INSERT INTO capability_gap_events (
                        event_id, gap_id, trace_id, session_id, agent_id, platform, task_type,
                        suggested_agent, unmet_json, context_json, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        gap_id,
                        trace_id,
                        session_id,
                        agent_id,
                        platform,
                        task_type,
                        suggested_agent,
                        json.dumps(unmet, ensure_ascii=False, default=str),
                        json.dumps(context or {}, ensure_ascii=False, default=str),
                        now,
                    ),
                )
                gap_row = conn.execute(
                    "SELECT * FROM capability_gaps WHERE gap_id = ?",
                    (gap_id,),
                ).fetchone()
                if gap_row is not None:
                    rows.append(self._row_to_gap(gap_row))
        return rows

    def close_gap(
        self,
        gap_id: str,
        *,
        owner: str = "",
        status: str = "closed",
        context_patch: dict[str, Any] | None = None,
    ) -> CapabilityGap:
        conn = self._conn()
        row = conn.execute("SELECT * FROM capability_gaps WHERE gap_id = ?", (gap_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown capability gap: {gap_id}")
        context = json.loads(row["context_json"] or "{}")
        if context_patch:
            context.update(context_patch)
        now = _now_iso()
        with conn:
            conn.execute(
                """
                UPDATE capability_gaps
                SET status = ?, owner = ?, last_seen_at = ?, context_json = ?
                WHERE gap_id = ?
                """,
                (
                    status,
                    owner or row["owner"],
                    now,
                    json.dumps(context, ensure_ascii=False, default=str),
                    gap_id,
                ),
            )
        refreshed = conn.execute("SELECT * FROM capability_gaps WHERE gap_id = ?", (gap_id,)).fetchone()
        assert refreshed is not None
        gap = self._row_to_gap(refreshed)
        record_skill_signal(
            signal_type=SignalType.CAPABILITY_GAP_CLOSED,
            trace_id=gap.latest_trace_id or f"capability-gap:{gap.gap_id}",
            source="skill_platform.capability_gap_recorder",
            agent_id=gap.latest_agent_id or owner or "skill-platform",
            task_type=gap.task_type,
            platform=gap.platform,
            unmet_capabilities=[{"capability_id": gap.capability_id}],
            extra={"gap_id": gap.gap_id, "status": gap.status, "owner": gap.owner},
        )
        return gap

    def record_gap(
        self,
        capability_name: str,
        requesting_agent: str,
        session_id: str,
        context: dict[str, Any] | None = None,
    ) -> CapabilityGap:
        """Backward-compatible single-gap recorder."""
        gaps = self.promote_unmet(
            trace_id=str((context or {}).get("trace_id") or ""),
            agent_id=requesting_agent,
            task_type=str((context or {}).get("task_type") or "unknown"),
            platform=str((context or {}).get("platform") or "openclaw"),
            unmet_capabilities=[
                {
                    "capability_id": capability_name,
                    "reason": str((context or {}).get("reason") or "missing"),
                    "required_by_task": str((context or {}).get("task_type") or "unknown"),
                    "candidate_bundles": list((context or {}).get("candidate_bundles") or []),
                    "candidate_skills": list((context or {}).get("candidate_skills") or []),
                }
            ],
            suggested_agent=str((context or {}).get("suggested_agent") or ""),
            session_id=session_id,
            repo=str((context or {}).get("repo") or ""),
            role_id=str((context or {}).get("role_id") or ""),
            source=str((context or {}).get("source") or "legacy_record_gap"),
            context=context or {},
        )
        return gaps[0]

    def fetch_gaps(self, *, status: str = "", limit: int = 100) -> list[CapabilityGap]:
        conn = self._conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM capability_gaps WHERE status = ? ORDER BY last_seen_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM capability_gaps ORDER BY last_seen_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_gap(row) for row in rows]

    def register_market_candidate(
        self,
        *,
        skill_id: str,
        source_market: str,
        source_uri: str,
        capability_ids: Iterable[str],
        linked_gap_id: str = "",
        summary: str = "",
        evidence: dict[str, Any] | None = None,
        trust_level: str = "unreviewed",
        quarantine_state: str = "pending",
    ) -> MarketSkillCandidate:
        now = _now_iso()
        candidate = MarketSkillCandidate(
            candidate_id=uuid.uuid4().hex,
            skill_id=skill_id,
            source_market=source_market,
            source_uri=source_uri,
            capability_ids=[str(item) for item in capability_ids if str(item).strip()],
            linked_gap_id=linked_gap_id,
            summary=summary,
            evidence=dict(evidence or {}),
            trust_level=trust_level,
            quarantine_state=quarantine_state,
            created_at=now,
            updated_at=now,
        )
        conn = self._conn()
        with conn:
            conn.execute(
                """
                INSERT INTO market_skill_candidates (
                    candidate_id, skill_id, source_market, source_uri, capability_ids_json,
                    status, trust_level, quarantine_state, linked_gap_id, summary,
                    evidence_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    candidate.skill_id,
                    candidate.source_market,
                    candidate.source_uri,
                    json.dumps(candidate.capability_ids, ensure_ascii=False),
                    candidate.status,
                    candidate.trust_level,
                    candidate.quarantine_state,
                    candidate.linked_gap_id,
                    candidate.summary,
                    json.dumps(candidate.evidence, ensure_ascii=False, default=str),
                    candidate.created_at,
                    candidate.updated_at,
                ),
            )
        return candidate

    def _row_to_market_candidate(self, row: sqlite3.Row) -> MarketSkillCandidate:
        return MarketSkillCandidate(
            candidate_id=str(row["candidate_id"]),
            skill_id=str(row["skill_id"]),
            source_market=str(row["source_market"]),
            source_uri=str(row["source_uri"]),
            capability_ids=json.loads(row["capability_ids_json"] or "[]"),
            status=str(row["status"]),
            trust_level=str(row["trust_level"]),
            quarantine_state=str(row["quarantine_state"]),
            linked_gap_id=str(row["linked_gap_id"]),
            summary=str(row["summary"]),
            evidence=json.loads(row["evidence_json"] or "{}"),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def list_market_candidates(self, *, status: str = "", limit: int = 100) -> list[MarketSkillCandidate]:
        conn = self._conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM market_skill_candidates WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM market_skill_candidates ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_market_candidate(row) for row in rows]

    def search_market_candidates(
        self,
        *,
        capability_id: str = "",
        linked_gap_id: str = "",
        status: str = "",
        trust_level: str = "",
        limit: int = 100,
    ) -> list[MarketSkillCandidate]:
        candidates = self.list_market_candidates(status=status, limit=max(limit, 1) * 4)
        filtered: list[MarketSkillCandidate] = []
        for candidate in candidates:
            if capability_id and capability_id not in candidate.capability_ids:
                continue
            if linked_gap_id and linked_gap_id != candidate.linked_gap_id:
                continue
            if trust_level and trust_level != candidate.trust_level:
                continue
            filtered.append(candidate)
            if len(filtered) >= limit:
                break
        return filtered

    def update_market_candidate(
        self,
        candidate_id: str,
        *,
        status: str | None = None,
        trust_level: str | None = None,
        quarantine_state: str | None = None,
        summary: str | None = None,
        evidence_patch: dict[str, Any] | None = None,
    ) -> MarketSkillCandidate:
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM market_skill_candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown market candidate: {candidate_id}")
        evidence = json.loads(row["evidence_json"] or "{}")
        if evidence_patch:
            evidence.update(evidence_patch)
        updated_at = _now_iso()
        with conn:
            conn.execute(
                """
                UPDATE market_skill_candidates
                SET status = ?, trust_level = ?, quarantine_state = ?, summary = ?,
                    evidence_json = ?, updated_at = ?
                WHERE candidate_id = ?
                """,
                (
                    status if status is not None else row["status"],
                    trust_level if trust_level is not None else row["trust_level"],
                    quarantine_state if quarantine_state is not None else row["quarantine_state"],
                    summary if summary is not None else row["summary"],
                    json.dumps(evidence, ensure_ascii=False, default=str),
                    updated_at,
                    candidate_id,
                ),
            )
        refreshed = conn.execute(
            "SELECT * FROM market_skill_candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        assert refreshed is not None
        return self._row_to_market_candidate(refreshed)

    def evaluate_market_candidate(
        self,
        candidate_id: str,
        *,
        platform: str,
        smoke_passed: bool,
        compatibility_passed: bool,
        summary: str | None = None,
        evidence_patch: dict[str, Any] | None = None,
    ) -> MarketSkillCandidate:
        base_patch = {
            "platform": platform,
            "smoke": "passed" if smoke_passed else "failed",
            "compatibility_gate": "passed" if compatibility_passed else "failed",
            "evaluated_at": _now_iso(),
        }
        if evidence_patch:
            base_patch.update(evidence_patch)
        approved = smoke_passed and compatibility_passed
        return self.update_market_candidate(
            candidate_id,
            status="evaluated" if approved else "rejected",
            trust_level="compatibility_passed" if approved else "blocked",
            quarantine_state="approved" if approved else "blocked",
            summary=summary,
            evidence_patch=base_patch,
        )

    def promote_market_candidate(
        self,
        candidate_id: str,
        *,
        promoted_by: str,
        real_use_trace_id: str,
        real_use_notes: str = "",
        close_linked_gap: bool = True,
    ) -> MarketSkillCandidate:
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM market_skill_candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown market candidate: {candidate_id}")
        candidate = self._row_to_market_candidate(row)
        smoke_ok = str(candidate.evidence.get("smoke") or "") == "passed"
        compatibility_ok = str(candidate.evidence.get("compatibility_gate") or "") == "passed"
        if candidate.quarantine_state != "approved" or not smoke_ok or not compatibility_ok:
            raise ValueError("candidate_not_quarantine_approved")
        if not str(real_use_trace_id).strip():
            raise ValueError("real_use_trace_id_required")
        promoted = self.update_market_candidate(
            candidate_id,
            status="promoted",
            trust_level="promoted",
            quarantine_state="released",
            evidence_patch={
                "promoted_at": _now_iso(),
                "promoted_by": promoted_by,
                "real_use_trace_id": real_use_trace_id,
                "real_use_notes": real_use_notes,
            },
        )
        if close_linked_gap and promoted.linked_gap_id:
            self.close_gap(
                promoted.linked_gap_id,
                owner=promoted_by,
                status="closed",
                context_patch={
                    "resolution": "market_candidate_promoted",
                    "candidate_id": promoted.candidate_id,
                    "skill_id": promoted.skill_id,
                },
            )
        record_skill_signal(
            signal_type=SignalType.SKILL_PROMOTED,
            trace_id=real_use_trace_id,
            source="skill_platform.market_gate",
            agent_id=promoted_by,
            task_type="market_acquisition",
            platform=str(promoted.evidence.get("platform") or "unknown"),
            skill_ids=[promoted.skill_id],
            extra={
                "candidate_id": promoted.candidate_id,
                "source_market": promoted.source_market,
                "linked_gap_id": promoted.linked_gap_id,
            },
        )
        return promoted

    def deprecate_market_candidate(
        self,
        candidate_id: str,
        *,
        deprecated_by: str,
        reason: str,
        reopen_linked_gap: bool = False,
    ) -> MarketSkillCandidate:
        deprecated = self.update_market_candidate(
            candidate_id,
            status="deprecated",
            trust_level="deprecated",
            quarantine_state="archived",
            evidence_patch={
                "deprecated_at": _now_iso(),
                "deprecated_by": deprecated_by,
                "deprecation_reason": reason,
            },
        )
        if reopen_linked_gap and deprecated.linked_gap_id:
            conn = self._conn()
            now = _now_iso()
            with conn:
                conn.execute(
                    """
                    UPDATE capability_gaps
                    SET status = 'open',
                        owner = '',
                        last_seen_at = ?,
                        context_json = ?
                    WHERE gap_id = ?
                    """,
                    (
                        now,
                        json.dumps(
                            {
                                "resolution": "market_candidate_deprecated",
                                "candidate_id": deprecated.candidate_id,
                                "skill_id": deprecated.skill_id,
                            },
                            ensure_ascii=False,
                            default=str,
                        ),
                        deprecated.linked_gap_id,
                    ),
                )
        record_skill_signal(
            signal_type=SignalType.SKILL_DEPRECATED,
            trace_id=str(deprecated.evidence.get("real_use_trace_id") or f"market-candidate:{deprecated.candidate_id}"),
            source="skill_platform.market_gate",
            agent_id=deprecated_by,
            task_type="market_acquisition",
            platform=str(deprecated.evidence.get("platform") or "unknown"),
            skill_ids=[deprecated.skill_id],
            extra={
                "candidate_id": deprecated.candidate_id,
                "source_market": deprecated.source_market,
                "reason": reason,
            },
        )
        return deprecated


class QuarantineGate:
    """Trust gate for externally sourced or low-maturity skills."""

    def __init__(self, registry: CanonicalRegistry):
        self._registry = registry

    def assess_skill(
        self,
        skill_name: str,
        *,
        platform: str = "",
        execution_scope: str = "production",
    ) -> QuarantineDecision:
        manifest = self._registry.lookup(skill_name)
        if manifest is None:
            return QuarantineDecision(
                allowed=False,
                skill_id=skill_name,
                platform=platform,
                maturity="missing",
                quarantine_required=True,
                trust_level="blocked",
                reason="skill_not_found",
            )
        if platform and not manifest.supports_platform(platform):
            return QuarantineDecision(
                allowed=False,
                skill_id=skill_name,
                platform=platform,
                maturity=manifest.maturity,
                quarantine_required=True,
                trust_level="blocked",
                reason="platform_unsupported",
            )
        if manifest.maturity == "experimental":
            allowed = execution_scope in {"quarantine", "evaluation"}
            return QuarantineDecision(
                allowed=allowed,
                skill_id=skill_name,
                platform=platform,
                maturity=manifest.maturity,
                quarantine_required=True,
                trust_level="experimental",
                reason="experimental_skills_require_quarantine",
            )
        return QuarantineDecision(
            allowed=True,
            skill_id=skill_name,
            platform=platform,
            maturity=manifest.maturity,
            quarantine_required=False,
            trust_level="trusted",
            reason="maturity_and_platform_checks_passed",
        )

    def check_trust(self, capability_name: str) -> bool:
        decision = self.assess_skill(capability_name)
        if not decision.allowed:
            logger.warning("QuarantineGate rejected %s: %s", capability_name, decision.reason)
        return decision.allowed


def _resolve_skill_observer(explicit: EvoMapObserver | None = None) -> EvoMapObserver:
    if explicit is not None:
        return explicit
    try:
        from chatgptrest.advisor.runtime import get_advisor_runtime_if_ready

        runtime = get_advisor_runtime_if_ready()
        if runtime is not None and getattr(runtime, "evomap_observer", None) is not None:
            return runtime.evomap_observer
    except Exception:
        logger.debug("skill observer runtime lookup failed", exc_info=True)
    return get_skill_platform_observer()


def record_skill_signal(
    *,
    signal_type: str,
    trace_id: str,
    source: str,
    agent_id: str,
    task_type: str,
    platform: str,
    skill_ids: Iterable[str] | None = None,
    bundle_ids: Iterable[str] | None = None,
    unmet_capabilities: Iterable[dict[str, Any] | Any] | None = None,
    observer: EvoMapObserver | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    payload = {
        "agent_id": agent_id,
        "task_type": task_type,
        "platform": platform,
        "skill_ids": [str(item) for item in skill_ids or [] if str(item).strip()],
        "bundle_ids": [str(item) for item in bundle_ids or [] if str(item).strip()],
        "unmet_capabilities": [
            str((item.to_dict() if hasattr(item, "to_dict") else item).get("capability_id") or "")
            for item in unmet_capabilities or []
            if str((item.to_dict() if hasattr(item, "to_dict") else item).get("capability_id") or "").strip()
        ],
    }
    if extra:
        payload.update(extra)
    return _resolve_skill_observer(observer).record_event(
        trace_id=trace_id,
        signal_type=signal_type,
        source=source,
        domain=SignalDomain.SKILL,
        data=payload,
    )


def emit_skill_resolution_signals(
    *,
    trace_id: str,
    source: str,
    agent_id: str,
    task_type: str,
    platform: str,
    recommended_skills: Iterable[str] | None = None,
    recommended_bundles: Iterable[str] | None = None,
    selected_skills: Iterable[str] | None = None,
    selected_bundles: Iterable[str] | None = None,
    unmet_capabilities: Iterable[dict[str, Any] | Any] | None = None,
    observer: EvoMapObserver | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    recommended_skill_ids = [str(item) for item in recommended_skills or [] if str(item).strip()]
    recommended_bundle_ids = [str(item) for item in recommended_bundles or [] if str(item).strip()]
    selected_skill_ids = [str(item) for item in selected_skills or [] if str(item).strip()]
    selected_bundle_ids = [str(item) for item in selected_bundles or [] if str(item).strip()]
    if recommended_skill_ids or recommended_bundle_ids or list(unmet_capabilities or []):
        record_skill_signal(
            signal_type=SignalType.SKILL_SUGGESTED,
            trace_id=trace_id,
            source=source,
            agent_id=agent_id,
            task_type=task_type,
            platform=platform,
            skill_ids=recommended_skill_ids,
            bundle_ids=recommended_bundle_ids,
            unmet_capabilities=unmet_capabilities,
            observer=observer,
            extra=extra,
        )
    if selected_skill_ids or selected_bundle_ids:
        record_skill_signal(
            signal_type=SignalType.SKILL_SELECTED,
            trace_id=trace_id,
            source=source,
            agent_id=agent_id,
            task_type=task_type,
            platform=platform,
            skill_ids=selected_skill_ids,
            bundle_ids=selected_bundle_ids,
            observer=observer,
            extra=extra,
        )


def emit_skill_execution_signals(
    *,
    trace_id: str,
    source: str,
    agent_id: str,
    task_type: str,
    platform: str,
    selected_skills: Iterable[str] | None = None,
    selected_bundles: Iterable[str] | None = None,
    success: bool,
    observer: EvoMapObserver | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = dict(extra or {})
    selected_skill_ids = [str(item) for item in selected_skills or [] if str(item).strip()]
    selected_bundle_ids = [str(item) for item in selected_bundles or [] if str(item).strip()]
    record_skill_signal(
        signal_type=SignalType.SKILL_EXECUTED,
        trace_id=trace_id,
        source=source,
        agent_id=agent_id,
        task_type=task_type,
        platform=platform,
        skill_ids=selected_skill_ids,
        bundle_ids=selected_bundle_ids,
        observer=observer,
        extra=payload,
    )
    record_skill_signal(
        signal_type=SignalType.SKILL_SUCCEEDED if success else SignalType.SKILL_FAILED,
        trace_id=trace_id,
        source=source,
        agent_id=agent_id,
        task_type=task_type,
        platform=platform,
        skill_ids=selected_skill_ids,
        bundle_ids=selected_bundle_ids,
        observer=observer,
        extra=payload,
    )
    record_skill_signal(
        signal_type=SignalType.SKILL_HELPFUL if success else SignalType.SKILL_UNHELPFUL,
        trace_id=trace_id,
        source=source,
        agent_id=agent_id,
        task_type=task_type,
        platform=platform,
        skill_ids=selected_skill_ids,
        bundle_ids=selected_bundle_ids,
        observer=observer,
        extra=payload,
    )


def find_market_candidates_for_unmet(
    unmet_capabilities: Iterable[dict[str, Any] | Any] | None,
    *,
    statuses: Iterable[str] = ("quarantine", "evaluated", "promoted"),
    limit_per_capability: int = 3,
) -> list[dict[str, Any]]:
    recorder = get_capability_gap_recorder()
    normalized = recorder._normalize_unmet(unmet_capabilities or [])
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for unmet in normalized:
        capability_id = unmet["capability_id"]
        for status in statuses:
            for candidate in recorder.search_market_candidates(
                capability_id=capability_id,
                status=status,
                limit=limit_per_capability,
            ):
                if candidate.candidate_id in seen:
                    continue
                seen.add(candidate.candidate_id)
                payload = candidate.to_dict()
                payload["matched_capability_id"] = capability_id
                results.append(payload)
    return results


@lru_cache(maxsize=1)
def get_capability_gap_recorder(db_path: str = "") -> CapabilityGapRecorder:
    return CapabilityGapRecorder(db_path=db_path)


@lru_cache(maxsize=1)
def get_skill_platform_observer(db_path: str = "") -> EvoMapObserver:
    return EvoMapObserver(db_path=db_path or resolve_evomap_db_path())
