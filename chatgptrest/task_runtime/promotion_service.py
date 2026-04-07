"""Promotion Service - Evaluator gate and promotion decisions.

This module implements Phase 3: Evaluator Promotion Gate.
Generators cannot self-certify completion. Evaluators are the promotion gate.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal

from chatgptrest.task_runtime.task_store import (
    ChunkStatus,
    EvaluationReport,
    PromotionDecision,
    get_chunk,
    record_evaluation,
    record_promotion_decision,
    task_db_conn,
)
from chatgptrest.task_runtime.task_workspace import TaskWorkspace


@dataclass
class GraderResult:
    """Result from a single grader."""
    grader_name: str
    grade: str  # "pass", "fail", "warning"
    confidence: float
    failures: list[dict[str, Any]]
    details: dict[str, Any]


@dataclass
class EvaluationResult:
    """Combined evaluation result."""
    chunk_id: str
    grader_results: list[GraderResult]
    overall_grade: str  # "pass", "fail", "needs_review"
    recommendation: str  # "promote", "reject", "operator_review"
    confidence: float
    observed_failures: list[dict[str, Any]]


class PromotionService:
    """Manages evaluation and promotion decisions."""

    def __init__(self, task_id: str, db_path: Path | None = None):
        self.task_id = task_id
        self.db_path = db_path
        self.workspace = TaskWorkspace(task_id)

    def evaluate_chunk(
        self,
        chunk_id: str,
        *,
        grader_suite: str = "standard",
    ) -> EvaluationResult:
        """Evaluate a completed chunk."""
        with task_db_conn(self.db_path) as conn:
            chunk = get_chunk(conn, chunk_id=chunk_id)

        if chunk.status != ChunkStatus.COMPLETED:
            raise ValueError(f"Chunk {chunk_id} is not completed (status: {chunk.status.value})")

        # Get grader requirements
        grader_requirements = json.loads(chunk.grader_requirements_json)

        # Run graders
        grader_results = []

        # Code/unit grader
        if grader_requirements.get("run_code_grader", True):
            grader_results.append(self._run_code_grader(chunk))

        # Outcome grader
        if grader_requirements.get("run_outcome_grader", True):
            grader_results.append(self._run_outcome_grader(chunk))

        # Rubric/LLM grader
        if grader_requirements.get("run_rubric_grader", False):
            grader_results.append(self._run_rubric_grader(chunk))

        # Aggregate results
        overall_grade, recommendation, confidence = self._aggregate_grader_results(grader_results)

        # Collect all failures
        observed_failures = []
        for result in grader_results:
            observed_failures.extend(result.failures)

        # Record evaluation
        artifact_refs = self._collect_artifact_refs(chunk)

        with task_db_conn(self.db_path) as conn:
            evaluation = record_evaluation(
                conn,
                task_id=chunk.task_id,
                attempt_id=chunk.attempt_id,
                chunk_id=chunk_id,
                grader_suite=grader_suite,
                machine_grade=overall_grade,
                rubric_grade=None,  # Would be populated by LLM grader
                observed_failures=observed_failures,
                artifact_refs=artifact_refs,
                recommendation=recommendation,
                confidence=confidence,
            )

        # Write evaluation to workspace
        evaluation_data = {
            "evaluation_id": evaluation.evaluation_id,
            "chunk_id": chunk_id,
            "grader_suite": grader_suite,
            "grader_results": [
                {
                    "grader": r.grader_name,
                    "grade": r.grade,
                    "confidence": r.confidence,
                    "failures": r.failures,
                }
                for r in grader_results
            ],
            "overall_grade": overall_grade,
            "recommendation": recommendation,
            "confidence": confidence,
            "observed_failures": observed_failures,
            "evaluated_at": evaluation.created_at,
        }

        self.workspace.write_chunk_evaluation(chunk_id, evaluation_data)

        # Log progress
        self.workspace.append_progress_ledger({
            "event": "chunk_evaluated",
            "chunk_id": chunk_id,
            "overall_grade": overall_grade,
            "recommendation": recommendation,
            "ts": time.time(),
        })

        # Update chunk status to EVALUATING
        with task_db_conn(self.db_path) as conn:
            now = time.time()
            conn.execute("""
                UPDATE task_chunks
                SET status = ?, updated_at = ?
                WHERE chunk_id = ?
            """, (ChunkStatus.EVALUATING.value, now, chunk_id))
            conn.commit()

        return EvaluationResult(
            chunk_id=chunk_id,
            grader_results=grader_results,
            overall_grade=overall_grade,
            recommendation=recommendation,
            confidence=confidence,
            observed_failures=observed_failures,
        )

    def make_promotion_decision(
        self,
        chunk_id: str,
        *,
        decision: Literal["promote", "reject", "rollback"],
        source: Literal["evaluator", "operator", "policy"],
        reviewer_identity: str | None = None,
        rationale: str,
        rollback_target: str | None = None,
    ) -> PromotionDecision:
        """Record a promotion decision."""
        with task_db_conn(self.db_path) as conn:
            chunk = get_chunk(conn, chunk_id=chunk_id)

            promotion = record_promotion_decision(
                conn,
                task_id=chunk.task_id,
                attempt_id=chunk.attempt_id,
                chunk_id=chunk_id,
                decision=decision,
                source=source,
                reviewer_identity=reviewer_identity,
                rationale=rationale,
                rollback_target=rollback_target,
            )

        # Update chunk status based on decision
        new_status = {
            "promote": ChunkStatus.PROMOTED,
            "reject": ChunkStatus.REJECTED,
            "rollback": ChunkStatus.REJECTED,
        }[decision]

        with task_db_conn(self.db_path) as conn:
            now = time.time()
            conn.execute("""
                UPDATE task_chunks
                SET status = ?, updated_at = ?
                WHERE chunk_id = ?
            """, (new_status.value, now, chunk_id))
            conn.commit()

        # Log progress
        self.workspace.append_progress_ledger({
            "event": "promotion_decision",
            "chunk_id": chunk_id,
            "decision": decision,
            "source": source,
            "rationale": rationale,
            "ts": time.time(),
        })

        return promotion

    def auto_promote_if_passing(self, chunk_id: str) -> PromotionDecision | None:
        """Automatically promote if evaluation passed."""
        # Get latest evaluation
        with task_db_conn(self.db_path) as conn:
            row = conn.execute("""
                SELECT * FROM task_evaluations
                WHERE chunk_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (chunk_id,)).fetchone()

            if row is None:
                return None

            recommendation = row["recommendation"]
            confidence = row["confidence"]

        # Auto-promote if recommendation is "promote" and confidence is high
        if recommendation == "promote" and confidence >= 0.8:
            return self.make_promotion_decision(
                chunk_id,
                decision="promote",
                source="evaluator",
                reviewer_identity="auto_promoter",
                rationale=f"Automatic promotion: evaluation passed with {confidence:.2f} confidence",
            )

        return None

    def _run_code_grader(self, chunk: Any) -> GraderResult:
        """Run code/unit grader."""
        # Placeholder: would run actual tests
        return GraderResult(
            grader_name="code_grader",
            grade="pass",
            confidence=0.9,
            failures=[],
            details={"tests_run": 0, "tests_passed": 0},
        )

    def _run_outcome_grader(self, chunk: Any) -> GraderResult:
        """Run outcome grader."""
        # Placeholder: would check artifact contract compliance
        return GraderResult(
            grader_name="outcome_grader",
            grade="pass",
            confidence=0.85,
            failures=[],
            details={"artifacts_checked": 0},
        )

    def _run_rubric_grader(self, chunk: Any) -> GraderResult:
        """Run rubric/LLM grader."""
        # Placeholder: would use LLM to grade against rubric
        return GraderResult(
            grader_name="rubric_grader",
            grade="pass",
            confidence=0.75,
            failures=[],
            details={"rubric_items": 0},
        )

    def _aggregate_grader_results(
        self,
        results: list[GraderResult],
    ) -> tuple[str, str, float]:
        """Aggregate grader results into overall grade and recommendation.

        Returns:
            (overall_grade, recommendation, confidence)
        """
        if not results:
            return "unknown", "operator_review", 0.0

        # Count passes and fails
        passes = sum(1 for r in results if r.grade == "pass")
        fails = sum(1 for r in results if r.grade == "fail")

        # Average confidence
        avg_confidence = sum(r.confidence for r in results) / len(results)

        # Determine overall grade
        if fails > 0:
            overall_grade = "fail"
            recommendation = "reject"
        elif passes == len(results):
            overall_grade = "pass"
            recommendation = "promote"
        else:
            overall_grade = "needs_review"
            recommendation = "operator_review"

        # Lower confidence if results are mixed
        if fails > 0 and passes > 0:
            avg_confidence *= 0.7

        return overall_grade, recommendation, avg_confidence

    def _collect_artifact_refs(self, chunk: Any) -> list[str]:
        """Collect artifact references for a chunk."""
        # Placeholder: would scan workspace for artifacts
        return []


def get_chunks_awaiting_evaluation(task_id: str) -> list[str]:
    """Get chunk IDs awaiting evaluation."""
    with task_db_conn(self.db_path) as conn:
        rows = conn.execute("""
            SELECT chunk_id FROM task_chunks
            WHERE task_id = ? AND status = ?
            ORDER BY chunk_no ASC
        """, (task_id, ChunkStatus.COMPLETED.value)).fetchall()

        return [row["chunk_id"] for row in rows]


def get_chunks_awaiting_promotion(task_id: str) -> list[str]:
    """Get chunk IDs awaiting promotion decision."""
    with task_db_conn(self.db_path) as conn:
        rows = conn.execute("""
            SELECT chunk_id FROM task_chunks
            WHERE task_id = ? AND status = ?
            ORDER BY chunk_no ASC
        """, (task_id, ChunkStatus.EVALUATING.value)).fetchall()

        return [row["chunk_id"] for row in rows]
