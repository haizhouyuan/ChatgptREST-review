"""Memory distillation scaffold for task runtime outcomes.

This builds distillation payloads but does not yet write through the real
work-memory manager and review/operator lanes.
"""

from __future__ import annotations

import json
import time
from typing import Any

from chatgptrest.task_runtime.task_store import (
    FinalOutcome,
    TaskStatus,
    get_task,
    task_db_conn,
)
from chatgptrest.task_runtime.task_state_machine import TaskStateMachine
from chatgptrest.task_runtime.task_workspace import TaskWorkspace


class MemoryDistiller:
    """Distills task outcomes into a provisional memory projection."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.workspace = TaskWorkspace(task_id)

    def distill_outcome(
        self,
        outcome: FinalOutcome,
    ) -> dict[str, Any]:
        """Build a memory distillation payload for later integration.

        A full implementation would integrate with work_memory_manager to create:
        - DecisionLedger entries
        - ActiveProjectMap updates
        - PostCallTriage records
        - Handoff documents
        """
        # Get task record
        with task_db_conn() as conn:
            task = get_task(conn, task_id=self.task_id)

        # Parse intake and outcome
        intake_spec = json.loads(task.intake_json)
        final_artifacts = json.loads(outcome.final_artifact_refs_json)
        promoted_decisions = json.loads(outcome.promoted_decisions_json)

        # Build distillation payload
        distillation = {
            "task_id": self.task_id,
            "outcome_id": outcome.outcome_id,
            "scenario": intake_spec.get("scenario"),
            "objective": intake_spec.get("objective"),
            "summary": outcome.summary,
            "status": outcome.status,
            "artifacts": final_artifacts,
            "decisions": promoted_decisions,
            "distilled_at": time.time(),
            "memory_objects": [],
        }

        # Generate memory objects based on scenario
        scenario = intake_spec.get("scenario", "general")

        if scenario == "planning":
            distillation["memory_objects"].append({
                "type": "DecisionLedger",
                "content": self._extract_planning_decisions(outcome, intake_spec),
            })

        if scenario == "research":
            distillation["memory_objects"].append({
                "type": "PostCallTriage",
                "content": self._extract_research_findings(outcome, intake_spec),
            })

        if scenario == "code_review":
            distillation["memory_objects"].append({
                "type": "Handoff",
                "content": self._extract_review_handoff(outcome, intake_spec),
            })

        # Always create a project map update
        distillation["memory_objects"].append({
            "type": "ActiveProjectMap",
            "content": self._extract_project_update(outcome, intake_spec),
        })

        # Update outcome with distillation reference
        with task_db_conn() as conn:
            conn.execute("""
                UPDATE task_final_outcomes
                SET memory_distillation_ref = ?
                WHERE outcome_id = ?
            """, (json.dumps(distillation), outcome.outcome_id))
            conn.commit()

        # Transition task to DISTILLED
        state_machine = TaskStateMachine(self.task_id)
        result = state_machine.transition(
            to_status=TaskStatus.DISTILLED,
            trigger="memory_distiller",
            metadata={"outcome_id": outcome.outcome_id}
        )

        if not result.success:
            raise RuntimeError(f"Failed to transition to DISTILLED: {result.error}")

        # Log progress
        self.workspace.append_progress_ledger({
            "event": "distilled_to_memory",
            "outcome_id": outcome.outcome_id,
            "memory_objects": len(distillation["memory_objects"]),
            "ts": time.time(),
        })

        return distillation

    def _extract_planning_decisions(
        self,
        outcome: FinalOutcome,
        intake_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract planning decisions for DecisionLedger."""
        return {
            "decision_type": "planning",
            "objective": intake_spec.get("objective"),
            "summary": outcome.summary,
            "decisions": json.loads(outcome.promoted_decisions_json),
            "confidence": "high",  # Based on promotion
        }

    def _extract_research_findings(
        self,
        outcome: FinalOutcome,
        intake_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract research findings for PostCallTriage."""
        return {
            "research_type": "general",
            "query": intake_spec.get("objective"),
            "findings": outcome.summary,
            "artifacts": json.loads(outcome.final_artifact_refs_json),
            "quality": "promoted",  # Indicates it passed evaluation
        }

    def _extract_review_handoff(
        self,
        outcome: FinalOutcome,
        intake_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract code review handoff."""
        return {
            "handoff_type": "code_review",
            "review_summary": outcome.summary,
            "artifacts": json.loads(outcome.final_artifact_refs_json),
            "next_actions": [],  # Would be extracted from outcome
        }

    def _extract_project_update(
        self,
        outcome: FinalOutcome,
        intake_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract project map update."""
        return {
            "project_id": intake_spec.get("task_id", self.task_id),
            "status_update": outcome.summary,
            "completed_at": outcome.created_at,
            "outcome_status": outcome.status,
        }


def complete_task(task_id: str) -> bool:
    """Mark task as completed (final terminal state)."""
    state_machine = TaskStateMachine(task_id)

    result = state_machine.transition(
        to_status=TaskStatus.COMPLETED,
        trigger="task_completion",
        metadata={"completed_at": time.time()}
    )

    return result.success


def should_distill_outcome(outcome: FinalOutcome) -> tuple[bool, str]:
    """Check if an outcome should be distilled to memory.

    Returns:
        (should_distill, reason)
    """
    if outcome.status != "success":
        return False, f"Outcome status is {outcome.status}, not success"

    promoted_decisions = json.loads(outcome.promoted_decisions_json)
    if len(promoted_decisions) == 0:
        return False, "No promoted decisions to distill"

    if outcome.memory_distillation_ref:
        return False, "Already distilled"

    return True, "OK"
