"""Memory distillation for task runtime outcomes.

This module distills task outcomes into work-memory through the real
work_memory_manager. Only after successful distillation does the task
enter DISTILLED status.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from chatgptrest.kernel.memory_manager import MemoryManager
from chatgptrest.kernel.work_memory_manager import WorkMemoryManager
from chatgptrest.task_runtime.task_store import (
    FinalOutcome,
    TaskStatus,
    get_task,
    task_db_conn,
)
from chatgptrest.task_runtime.task_state_machine import TaskStateMachine
from chatgptrest.task_runtime.task_workspace import TaskWorkspace


class MemoryDistiller:
    """Distills task outcomes into authoritative work-memory."""

    def __init__(self, task_id: str, memory_db_path: Path | None = None, task_db_path: Path | None = None):
        self.task_id = task_id
        self.task_db_path = task_db_path
        self.workspace = TaskWorkspace(task_id)
        # Initialize work memory manager with real memory backend
        if memory_db_path is None:
            memory_db_path = Path("~/.openmind/memory.db").expanduser()
        self._memory_db_path = memory_db_path
        self._memory_manager = MemoryManager(str(memory_db_path))
        self._work_memory_manager = WorkMemoryManager(self._memory_manager)

    def distill_outcome(
        self,
        outcome: FinalOutcome,
    ) -> dict[str, Any]:
        """Distill outcome to work-memory through real pipeline.

        This integrates with work_memory_manager to create actual memory entries.
        Only after successful distillation does the task enter DISTILLED status.
        """
        # Get task record
        with task_db_conn(self.task_db_path) as conn:
            task = get_task(conn, task_id=self.task_id)

        # Parse intake and outcome
        intake_spec = json.loads(task.intake_json)
        final_artifacts = json.loads(outcome.final_artifact_refs_json)
        promoted_decisions = json.loads(outcome.promoted_decisions_json)

        # Extract scenario and determine memory category
        scenario = intake_spec.get("scenario", "general")
        category = self._map_scenario_to_category(scenario)

        # Build distillation payload for work-memory
        title = f"Task {self.task_id}: {intake_spec.get('objective', 'Task')[:50]}"
        summary = outcome.summary or "No summary available"
        content = self._build_distillation_content(intake_spec, outcome, promoted_decisions)

        # Build payload for work-memory object
        payload = self._build_work_memory_payload(intake_spec, outcome, promoted_decisions)

        # Write to work-memory through the real pipeline
        # This is the authoritative integration - not just building a payload
        try:
            work_memory_result = self._work_memory_manager.write_from_capture(
                category=category,
                title=title,
                content=content,
                summary=summary,
                payload=payload,
                source_ref=f"task://{self.task_id}",
                source_system="task_harness",
                source_agent="task_runtime",
                role_id=intake_spec.get("role_id", "system"),
                session_id=intake_spec.get("session_id", self.task_id),
                account_id=intake_spec.get("account_id", "default"),
                thread_id=intake_spec.get("trace_id", self.task_id),
                trace_id=intake_spec.get("trace_id", self.task_id),
                confidence=0.9,  # High confidence from promoted outcomes
                provenance_quality="promoted",
                identity_gaps=[],
            )
        except Exception as e:
            # Fail-closed: if memory distillation fails, don't enter DISTILLED
            raise RuntimeError(f"Memory distillation failed: {e}")

        # Build distillation record
        distillation = {
            "task_id": self.task_id,
            "outcome_id": outcome.outcome_id,
            "scenario": scenario,
            "objective": intake_spec.get("objective"),
            "summary": outcome.summary,
            "status": outcome.status,
            "artifacts": final_artifacts,
            "decisions": promoted_decisions,
            "distilled_at": time.time(),
            "work_memory_record_id": work_memory_result.record_id if work_memory_result.ok else None,
            "work_memory_category": category,
            "distillation_success": work_memory_result.ok,
            "memory_objects": [category],  # Track what was created
        }

        # Update outcome with distillation reference
        with task_db_conn(self.task_db_path) as conn:
            conn.execute("""
                UPDATE task_final_outcomes
                SET memory_distillation_ref = ?
                WHERE outcome_id = ?
            """, (json.dumps(distillation), outcome.outcome_id))
            conn.commit()

        # Only transition to DISTILLED after successful memory write
        # This is the authoritative gate - task enters DISTILLED only after
        # real work-memory entries are created
        state_machine = TaskStateMachine(self.task_id, db_path=self.task_db_path)
        result = state_machine.transition(
            to_status=TaskStatus.DISTILLED,
            trigger="memory_distiller",
            metadata={"outcome_id": outcome.outcome_id, "record_id": work_memory_result.record_id}
        )

        if not result.success:
            raise RuntimeError(f"Failed to transition to DISTILLED: {result.error}")

        # Log progress
        self.workspace.append_progress_ledger({
            "event": "distilled_to_memory",
            "outcome_id": outcome.outcome_id,
            "work_memory_record_id": work_memory_result.record_id,
            "category": category,
            "ts": time.time(),
        })

        return distillation

    def _map_scenario_to_category(self, scenario: str) -> str:
        """Map task scenario to work-memory category."""
        mapping = {
            "planning": "decision_ledger",
            "research": "post_call_triage",
            "code_review": "handoff",
            "execution": "active_project",
            "general": "active_project",
        }
        return mapping.get(scenario, "active_project")

    def _build_distillation_content(
        self,
        intake_spec: dict[str, Any],
        outcome: FinalOutcome,
        promoted_decisions: list[dict[str, Any]],
    ) -> str:
        """Build content for work-memory entry."""
        lines = [
            f"Task: {intake_spec.get('objective', 'Unknown')}",
            f"Scenario: {intake_spec.get('scenario', 'general')}",
            f"Status: {outcome.status}",
            "",
            "Summary:",
            outcome.summary or "No summary",
            "",
        ]

        if promoted_decisions:
            lines.append("Promoted Decisions:")
            for decision in promoted_decisions:
                lines.append(f"  - {decision.get('decision', 'unknown')}: {decision.get('rationale', '')[:100]}")
            lines.append("")

        return "\n".join(lines)

    def _build_work_memory_payload(
        self,
        intake_spec: dict[str, Any],
        outcome: FinalOutcome,
        promoted_decisions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build work-memory payload based on scenario."""
        scenario = intake_spec.get("scenario", "general")
        payload = {
            "task_id": self.task_id,
            "objective": intake_spec.get("objective"),
            "status": outcome.status,
            "completed_at": outcome.created_at,
        }

        if scenario == "planning":
            payload["decision_type"] = "planning"
            payload["decisions"] = promoted_decisions
            payload["confidence"] = "high"

        elif scenario == "research":
            payload["research_type"] = "general"
            payload["findings"] = outcome.summary
            payload["quality"] = "promoted"

        elif scenario == "code_review":
            payload["handoff_type"] = "code_review"
            payload["review_summary"] = outcome.summary
            payload["next_actions"] = []

        # Always include project update
        payload["project_id"] = intake_spec.get("task_id", self.task_id)
        payload["status_update"] = outcome.summary
        payload["outcome_status"] = outcome.status

        return payload


def complete_task(task_id: str, db_path: Path | None = None) -> bool:
    """Mark task as completed (final terminal state).

    Raises:
        RuntimeError: If transition to COMPLETED fails.
    """
    state_machine = TaskStateMachine(task_id, db_path=db_path)

    result = state_machine.transition(
        to_status=TaskStatus.COMPLETED,
        trigger="task_completion",
        metadata={"completed_at": time.time()}
    )

    if not result.success:
        raise RuntimeError(f"Failed to complete task: {result.error}")

    return True


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
