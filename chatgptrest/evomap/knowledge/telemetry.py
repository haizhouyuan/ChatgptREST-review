"""EvoMap Telemetry — observability layer for knowledge retrieval pipeline.

Three telemetry tables:
  1. query_events    — each retrieval request
  2. retrieval_events — per-candidate hit/rank at each pipeline stage
  3. answer_feedback  — user reactions (accepted/corrected/followup/abstained)

Plus high-level analytics:
  - Routing quality stats (for routing developer Phase 5)
  - Frustration Index (Gemini review suggestion)
  - Gap metrics (query coverage, confidence margin, stale-hit rate)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from chatgptrest.evomap.knowledge.db import KnowledgeDB

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DDL — These tables live in the same evomap_knowledge.db
# ---------------------------------------------------------------------------

TELEMETRY_DDL = """
-- query_events: each retrieval request
CREATE TABLE IF NOT EXISTS query_events (
    query_id TEXT PRIMARY KEY,
    normalized_query TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL DEFAULT '',
    intent TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    trace_id TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL DEFAULT '',
    job_id TEXT NOT NULL DEFAULT '',
    task_ref TEXT NOT NULL DEFAULT '',
    logical_task_id TEXT NOT NULL DEFAULT '',
    identity_confidence TEXT NOT NULL DEFAULT '',
    atom_count INTEGER NOT NULL DEFAULT 0,
    top_score REAL NOT NULL DEFAULT 0,
    elapsed_ms INTEGER NOT NULL DEFAULT 0,
    timestamp REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_qe_session ON query_events(session_id);
CREATE INDEX IF NOT EXISTS idx_qe_timestamp ON query_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_qe_domain ON query_events(domain);

-- retrieval_events: per-candidate hit/rank at each pipeline stage
CREATE TABLE IF NOT EXISTS retrieval_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id TEXT NOT NULL REFERENCES query_events(query_id),
    atom_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    rank INTEGER NOT NULL DEFAULT 0,
    stage_score REAL NOT NULL DEFAULT 0,
    selected BOOLEAN NOT NULL DEFAULT 0,
    used_in_answer BOOLEAN NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_re_query ON retrieval_events(query_id);
CREATE INDEX IF NOT EXISTS idx_re_atom ON retrieval_events(atom_id);
CREATE INDEX IF NOT EXISTS idx_re_stage ON retrieval_events(stage);

-- answer_feedback: user reactions
CREATE TABLE IF NOT EXISTS answer_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id TEXT NOT NULL REFERENCES query_events(query_id),
    feedback_type TEXT NOT NULL,
    correction_type TEXT NOT NULL DEFAULT '',
    atom_ids_json TEXT NOT NULL DEFAULT '[]',
    timestamp REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_af_query ON answer_feedback(query_id);
CREATE INDEX IF NOT EXISTS idx_af_type ON answer_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_af_timestamp ON answer_feedback(timestamp);
"""


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class QueryEvent:
    """A single retrieval query event."""
    query_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    normalized_query: str = ""
    domain: str = ""
    intent: str = ""
    session_id: str = ""
    trace_id: str = ""
    run_id: str = ""
    job_id: str = ""
    task_ref: str = ""
    logical_task_id: str = ""
    identity_confidence: str = ""
    atom_count: int = 0
    top_score: float = 0.0
    elapsed_ms: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class RetrievalEvent:
    """A single candidate atom's position at a pipeline stage."""
    query_id: str = ""
    atom_id: str = ""
    stage: str = ""        # "fts" | "quality_gate" | "scored" | "final"
    rank: int = 0
    stage_score: float = 0.0
    selected: bool = False
    used_in_answer: bool = False
    source: str = ""


@dataclass
class AnswerFeedback:
    """User feedback on a retrieval result."""
    query_id: str = ""
    feedback_type: str = ""    # "accepted" | "corrected" | "followup" | "abstained"
    correction_type: str = ""  # "factual" | "outdated" | "irrelevant" | ""
    atom_ids_json: str = "[]"
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Telemetry Recorder
# ---------------------------------------------------------------------------

class TelemetryRecorder:
    """Records and queries retrieval telemetry.

    Usage::

        recorder = TelemetryRecorder(db)
        recorder.init_schema()

        # Record a retrieval
        qe = recorder.record_query(query, results, elapsed_ms)

        # Record feedback
        recorder.record_feedback(qe.query_id, "accepted")

        # Aggregate stats
        stats = recorder.get_gap_metrics(window_days=7)
    """

    def __init__(self, db: KnowledgeDB):
        self.db = db

    def init_schema(self):
        """Create telemetry tables (idempotent)."""
        conn = self.db.connect()
        conn.executescript(TELEMETRY_DDL)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(retrieval_events)").fetchall()
        }
        if "source" not in columns:
            conn.execute("ALTER TABLE retrieval_events ADD COLUMN source TEXT NOT NULL DEFAULT ''")
        query_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(query_events)").fetchall()
        }
        for column_name, ddl in (
            ("run_id", "TEXT NOT NULL DEFAULT ''"),
            ("job_id", "TEXT NOT NULL DEFAULT ''"),
            ("task_ref", "TEXT NOT NULL DEFAULT ''"),
            ("logical_task_id", "TEXT NOT NULL DEFAULT ''"),
            ("identity_confidence", "TEXT NOT NULL DEFAULT ''"),
        ):
            if column_name not in query_columns:
                conn.execute(f"ALTER TABLE query_events ADD COLUMN {column_name} {ddl}")
        conn.commit()
        logger.info("Telemetry tables initialized")

    # -- Recording ----------------------------------------------------------

    def record_query(
        self,
        query: str,
        scored_atoms: list | None = None,
        elapsed_ms: int = 0,
        session_id: str = "",
        trace_id: str = "",
        run_id: str = "",
        job_id: str = "",
        task_ref: str = "",
        logical_task_id: str = "",
        identity_confidence: str = "",
        domain: str = "",
        intent: str = "",
    ) -> QueryEvent:
        """Record a retrieval query event and its results.

        Args:
            query: The user query
            scored_atoms: List of ScoredAtom from retrieval pipeline
            elapsed_ms: Pipeline latency
            session_id: Session context
            domain: Query domain (e.g., "redis", "docker")
            intent: Query intent (e.g., "troubleshooting", "howto")

        Returns:
            QueryEvent with generated query_id
        """
        conn = self.db.connect()
        atoms = scored_atoms or []

        qe = QueryEvent(
            normalized_query=query.strip().lower()[:500],
            domain=domain,
            intent=intent,
            session_id=session_id,
            trace_id=trace_id,
            run_id=run_id,
            job_id=job_id,
            task_ref=task_ref,
            logical_task_id=logical_task_id,
            identity_confidence=identity_confidence,
            atom_count=len(atoms),
            top_score=atoms[0].final_score if atoms else 0.0,
            elapsed_ms=elapsed_ms,
        )

        conn.execute(
            """INSERT OR REPLACE INTO query_events
               (query_id, normalized_query, domain, intent, session_id,
                trace_id, run_id, job_id, task_ref, logical_task_id, identity_confidence,
                atom_count, top_score, elapsed_ms, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (qe.query_id, qe.normalized_query, qe.domain, qe.intent,
             qe.session_id, qe.trace_id, qe.run_id, qe.job_id, qe.task_ref,
             qe.logical_task_id, qe.identity_confidence, qe.atom_count, qe.top_score,
             qe.elapsed_ms, qe.timestamp),
        )

        # Record per-atom retrieval events
        for rank, sa in enumerate(atoms, 1):
            conn.execute(
                """INSERT INTO retrieval_events
                   (query_id, atom_id, stage, rank, stage_score, selected, used_in_answer, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (qe.query_id, sa.atom.atom_id, "final", rank,
                 sa.final_score, rank <= 5, False, ""),  # top-5 considered "selected"
            )

        conn.commit()
        return qe

    def record_search_results(
        self,
        *,
        query: str,
        hits: list[dict[str, Any]] | None = None,
        elapsed_ms: int = 0,
        session_id: str = "",
        trace_id: str = "",
        run_id: str = "",
        job_id: str = "",
        task_ref: str = "",
        logical_task_id: str = "",
        identity_confidence: str = "",
        domain: str = "",
        intent: str = "",
    ) -> QueryEvent:
        """Record mixed search hits without requiring ScoredAtom objects."""
        conn = self.db.connect()
        items = list(hits or [])

        qe = QueryEvent(
            normalized_query=query.strip().lower()[:500],
            domain=domain,
            intent=intent,
            session_id=session_id,
            trace_id=trace_id,
            run_id=run_id,
            job_id=job_id,
            task_ref=task_ref,
            logical_task_id=logical_task_id,
            identity_confidence=identity_confidence,
            atom_count=len(items),
            top_score=max((float(item.get("score", 0) or 0) for item in items), default=0.0),
            elapsed_ms=elapsed_ms,
        )

        conn.execute(
            """INSERT OR REPLACE INTO query_events
               (query_id, normalized_query, domain, intent, session_id,
                trace_id, run_id, job_id, task_ref, logical_task_id, identity_confidence,
                atom_count, top_score, elapsed_ms, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (qe.query_id, qe.normalized_query, qe.domain, qe.intent,
             qe.session_id, qe.trace_id, qe.run_id, qe.job_id, qe.task_ref,
             qe.logical_task_id, qe.identity_confidence, qe.atom_count, qe.top_score,
             qe.elapsed_ms, qe.timestamp),
        )

        for rank, item in enumerate(items, 1):
            atom_id = str(item.get("artifact_id") or item.get("atom_id") or "").strip()
            if not atom_id:
                continue
            conn.execute(
                """INSERT INTO retrieval_events
                   (query_id, atom_id, stage, rank, stage_score, selected, used_in_answer, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    qe.query_id,
                    atom_id,
                    "final",
                    rank,
                    float(item.get("score", 0) or 0),
                    1 if rank <= 5 else 0,
                    0,
                    str(item.get("source") or ""),
                ),
            )

        conn.commit()
        return qe

    def record_feedback(
        self,
        query_id: str,
        feedback_type: str,
        correction_type: str = "",
        atom_ids: list[str] | None = None,
    ):
        """Record user feedback on retrieval quality.

        Args:
            query_id: From QueryEvent
            feedback_type: "accepted" | "corrected" | "followup" | "abstained"
            correction_type: "factual" | "outdated" | "irrelevant" | ""
            atom_ids: Atoms that were relevant to the feedback
        """
        conn = self.db.connect()
        conn.execute(
            """INSERT INTO answer_feedback
               (query_id, feedback_type, correction_type, atom_ids_json, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (query_id, feedback_type, correction_type,
             json.dumps(atom_ids or []), time.time()),
        )
        conn.commit()

    def mark_atoms_used(self, query_id: str, atom_ids: list[str]):
        """Mark specific atoms as actually used in the final answer."""
        conn = self.db.connect()
        for aid in atom_ids:
            conn.execute(
                """UPDATE retrieval_events
                   SET used_in_answer = 1
                   WHERE query_id = ? AND atom_id = ?""",
                (query_id, aid),
            )
        conn.commit()

    # -- Analytics: Gap Metrics (Pro L750-775) --------------------------------

    def get_gap_metrics(self, window_days: int = 7) -> dict:
        """Compute 6 retrieval quality gap metrics.

        Returns dict with:
          1. query_coverage — % of queries with top1 score > threshold
          2. confidence_margin — avg gap between top1 and top2
          3. acceptance_rate — % of queries with accepted feedback
          4. miss_rate — % of queries with 0 results
          5. stale_hit_rate — % of selected atoms that are superseded
          6. utilization — % of retrieved atoms actually used in answer
        """
        conn = self.db.connect()
        cutoff = time.time() - window_days * 86400

        # Total queries in window
        total = conn.execute(
            "SELECT COUNT(*) FROM query_events WHERE timestamp > ?",
            (cutoff,),
        ).fetchone()[0]

        if total == 0:
            return {
                "window_days": window_days,
                "total_queries": 0,
                "query_coverage": 0.0,
                "confidence_margin": 0.0,
                "acceptance_rate": 0.0,
                "miss_rate": 0.0,
                "stale_hit_rate": 0.0,
                "utilization": 0.0,
            }

        # 1. Query coverage (top_score > 0.3)
        covered = conn.execute(
            "SELECT COUNT(*) FROM query_events WHERE timestamp > ? AND top_score > 0.3",
            (cutoff,),
        ).fetchone()[0]

        # 2. Confidence margin (avg top1 - top2 score)
        margin_rows = conn.execute(
            """SELECT q.query_id,
                      MAX(r.stage_score) as top1,
                      (SELECT MAX(r2.stage_score) FROM retrieval_events r2
                       WHERE r2.query_id = q.query_id AND r2.rank = 2) as top2
               FROM query_events q
               JOIN retrieval_events r ON r.query_id = q.query_id AND r.rank = 1
               WHERE q.timestamp > ?
               GROUP BY q.query_id""",
            (cutoff,),
        ).fetchall()
        margins = [
            (row[1] - (row[2] or 0)) for row in margin_rows
            if row[1] is not None
        ]
        avg_margin = sum(margins) / len(margins) if margins else 0.0

        # 3. Acceptance rate
        accepted = conn.execute(
            """SELECT COUNT(DISTINCT af.query_id)
               FROM answer_feedback af
               JOIN query_events q ON q.query_id = af.query_id
               WHERE q.timestamp > ? AND af.feedback_type = 'accepted'""",
            (cutoff,),
        ).fetchone()[0]
        queries_with_feedback = conn.execute(
            """SELECT COUNT(DISTINCT af.query_id)
               FROM answer_feedback af
               JOIN query_events q ON q.query_id = af.query_id
               WHERE q.timestamp > ?""",
            (cutoff,),
        ).fetchone()[0]

        # 4. Miss rate (0 results)
        misses = conn.execute(
            "SELECT COUNT(*) FROM query_events WHERE timestamp > ? AND atom_count = 0",
            (cutoff,),
        ).fetchone()[0]

        # 5. Stale-hit rate (selected atoms with superseded stability)
        total_selected = conn.execute(
            """SELECT COUNT(*) FROM retrieval_events r
               JOIN query_events q ON q.query_id = r.query_id
               WHERE q.timestamp > ? AND r.selected = 1""",
            (cutoff,),
        ).fetchone()[0]
        stale_selected = conn.execute(
            """SELECT COUNT(*) FROM retrieval_events r
               JOIN query_events q ON q.query_id = r.query_id
               JOIN atoms a ON a.atom_id = r.atom_id
               WHERE q.timestamp > ? AND r.selected = 1
                 AND a.stability = 'superseded'""",
            (cutoff,),
        ).fetchone()[0]

        # 6. Utilization rate
        used = conn.execute(
            """SELECT COUNT(*) FROM retrieval_events r
               JOIN query_events q ON q.query_id = r.query_id
               WHERE q.timestamp > ? AND r.used_in_answer = 1""",
            (cutoff,),
        ).fetchone()[0]

        return {
            "window_days": window_days,
            "total_queries": total,
            "query_coverage": round(covered / total, 3) if total else 0,
            "confidence_margin": round(avg_margin, 3),
            "acceptance_rate": round(
                accepted / queries_with_feedback, 3
            ) if queries_with_feedback else 0,
            "miss_rate": round(misses / total, 3) if total else 0,
            "stale_hit_rate": round(
                stale_selected / total_selected, 3
            ) if total_selected else 0,
            "utilization": round(
                used / total_selected, 3
            ) if total_selected else 0,
        }

    # -- Analytics: Frustration Index (Gemini L102) -------------------------

    def get_frustration_index(
        self,
        atom_id: str,
        window_days: int = 30,
    ) -> dict:
        """Calculate frustration index for a specific atom.

        Frustration = (corrections + followups) / total_uses

        High frustration → atom quality should be degraded.
        """
        conn = self.db.connect()
        cutoff = time.time() - window_days * 86400

        # Total times this atom was selected
        total_uses = conn.execute(
            """SELECT COUNT(*) FROM retrieval_events r
               JOIN query_events q ON q.query_id = r.query_id
               WHERE r.atom_id = ? AND r.selected = 1
                 AND q.timestamp > ?""",
            (atom_id, cutoff),
        ).fetchone()[0]

        if total_uses == 0:
            return {"atom_id": atom_id, "total_uses": 0, "frustration": 0.0}

        # Count negative signals from queries that used this atom
        negatives = conn.execute(
            """SELECT COUNT(*) FROM answer_feedback af
               WHERE af.feedback_type IN ('corrected', 'followup')
                 AND af.timestamp > ?
                 AND af.query_id IN (
                     SELECT r.query_id FROM retrieval_events r
                     WHERE r.atom_id = ? AND r.selected = 1
                 )""",
            (cutoff, atom_id),
        ).fetchone()[0]

        frustration = negatives / total_uses

        return {
            "atom_id": atom_id,
            "total_uses": total_uses,
            "negative_signals": negatives,
            "frustration": round(frustration, 3),
            "should_degrade": frustration > 0.5,
        }

    # -- Analytics: Routing Quality (for routing developer Phase 5) ---------

    def get_routing_quality_stats(
        self,
        domain: str | None = None,
        intent: str | None = None,
        window_days: int = 7,
    ) -> dict:
        """Aggregate retrieval quality by domain/intent.

        The routing developer needs this to calibrate provider selection
        based on which knowledge domains have high/low coverage.
        """
        conn = self.db.connect()
        cutoff = time.time() - window_days * 86400

        conditions = ["q.timestamp > ?"]
        params: list[Any] = [cutoff]
        if domain:
            conditions.append("q.domain = ?")
            params.append(domain)
        if intent:
            conditions.append("q.intent = ?")
            params.append(intent)

        where = " AND ".join(conditions)

        row = conn.execute(
            f"""SELECT
                    COUNT(*) as total,
                    AVG(q.top_score) as avg_score,
                    AVG(q.atom_count) as avg_atoms,
                    AVG(q.elapsed_ms) as avg_latency_ms,
                    SUM(CASE WHEN q.atom_count = 0 THEN 1 ELSE 0 END) as misses
                FROM query_events q
                WHERE {where}""",
            params,
        ).fetchone()

        total = row[0] or 0
        return {
            "domain": domain or "all",
            "intent": intent or "all",
            "window_days": window_days,
            "total_queries": total,
            "avg_top_score": round(row[1] or 0, 3),
            "avg_atom_count": round(row[2] or 0, 1),
            "avg_latency_ms": round(row[3] or 0, 0),
            "miss_rate": round((row[4] or 0) / total, 3) if total else 0,
        }

    # -- Bulk stats ---------------------------------------------------------

    def stats(self) -> dict:
        """Return row counts for telemetry tables."""
        conn = self.db.connect()
        try:
            return {
                "query_events": conn.execute(
                    "SELECT COUNT(*) FROM query_events"
                ).fetchone()[0],
                "retrieval_events": conn.execute(
                    "SELECT COUNT(*) FROM retrieval_events"
                ).fetchone()[0],
                "answer_feedback": conn.execute(
                    "SELECT COUNT(*) FROM answer_feedback"
                ).fetchone()[0],
            }
        except Exception:
            return {"query_events": 0, "retrieval_events": 0, "answer_feedback": 0}
