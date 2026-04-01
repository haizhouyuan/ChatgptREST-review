"""Delivery publication for task runtime outcomes.

This module publishes authoritative completion_contract / canonical_answer pairs
to the delivery plane. Only after successful publication does the task enter
PUBLISHED status.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from chatgptrest.core.completion_contract import build_completion_contract
from chatgptrest.task_runtime.task_store import (
    FinalOutcome,
    TaskStatus,
    get_task,
    record_final_outcome,
    task_db_conn,
)
from chatgptrest.task_runtime.task_state_machine import TaskStateMachine
from chatgptrest.task_runtime.task_workspace import TaskWorkspace


class DeliveryPublisher:
    """Publishes task outcomes to authoritative delivery."""

    def __init__(self, task_id: str, db_path: Path | None = None):
        self.task_id = task_id
        self.db_path = db_path
        self.workspace = TaskWorkspace(task_id)

    def create_final_outcome(
        self,
        *,
        attempt_id: str,
        status: str,
        final_artifact_refs: list[str],
        summary: str,
        promoted_decisions: list[str],
    ) -> FinalOutcome:
        """Create a final outcome record."""
        with task_db_conn(self.db_path) as conn:
            outcome = record_final_outcome(
                conn,
                task_id=self.task_id,
                attempt_id=attempt_id,
                status=status,
                final_artifact_refs=final_artifact_refs,
                summary=summary,
                promoted_decisions=promoted_decisions,
            )

        # Write outcome to workspace
        outcome_data = {
            "outcome_id": outcome.outcome_id,
            "task_id": self.task_id,
            "attempt_id": attempt_id,
            "status": status,
            "final_artifact_refs": final_artifact_refs,
            "summary": summary,
            "promoted_decisions": promoted_decisions,
            "created_at": outcome.created_at,
        }

        self.workspace.write_final_outcome(outcome_data)

        # Log progress
        self.workspace.append_progress_ledger({
            "event": "final_outcome_created",
            "outcome_id": outcome.outcome_id,
            "status": status,
            "ts": time.time(),
        })

        return outcome

    def publish_to_delivery(
        self,
        outcome: FinalOutcome,
        *,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """Publish outcome to authoritative delivery.

        This builds an authoritative completion_contract and transitions the task
        to PUBLISHED. The task only enters PUBLISHED status after successful
        publication.
        """
        # Get task record
        with task_db_conn(self.db_path) as conn:
            task = get_task(conn, task_id=self.task_id)

        # Parse intake spec
        intake_spec = json.loads(task.intake_json)

        # Get final artifact refs
        final_artifacts = json.loads(outcome.final_artifact_refs_json)

        # Build authoritative completion_contract
        # Determine answer path from artifacts
        answer_path = None
        if final_artifacts:
            # Use the first artifact as the authoritative answer
            answer_path = final_artifacts[0] if isinstance(final_artifacts[0], str) else final_artifacts[0].get("path")

        # Build completion contract
        completion_contract = build_completion_contract(
            status="completed",
            kind=intake_spec.get("scenario", "task_execution"),
            answer_chars=len(outcome.summary) if outcome.summary else 0,
            answer_path=answer_path,
            authoritative_job_id=job_id,
            authoritative_answer_path=answer_path,
            min_chars_required=0,
            last_event_type="task_harness_completed",
            reason_type=None,
            completion_quality="final",
            conversation_export_path=None,
            widget_export_available=False,
            research_contract=False,
        )

        # Build canonical answer record
        canonical_answer = {
            "record_version": "v1",
            "ready": True,
            "answer_state": completion_contract.get("answer_state"),
            "finality_reason": completion_contract.get("finality_reason"),
            "authoritative_job_id": job_id,
            "authoritative_answer_path": answer_path,
            "answer_chars": completion_contract.get("answer_chars"),
            "answer_format": "text",
            "answer_provenance": completion_contract.get("answer_provenance", {}),
            "export_available": completion_contract.get("export_available", False),
            "widget_export_available": completion_contract.get("widget_export_available", False),
        }

        # Create delivery projection with authoritative contract
        delivery_projection = {
            "task_id": self.task_id,
            "outcome_id": outcome.outcome_id,
            "status": outcome.status,
            "summary": outcome.summary,
            "final_artifact_refs": final_artifacts,
            "promoted_decisions": json.loads(outcome.promoted_decisions_json),
            "intake_spec": intake_spec,
            "completion_contract": completion_contract,
            "canonical_answer": canonical_answer,
            "published_at": time.time(),
        }

        # Update outcome with delivery reference - MUST succeed before PUBLISHED
        with task_db_conn(self.db_path) as conn:
            now = time.time()
            conn.execute("""
                UPDATE task_final_outcomes
                SET delivery_projection_ref = ?
                WHERE outcome_id = ?
            """, (json.dumps(delivery_projection), outcome.outcome_id))
            conn.commit()

        # Only transition to PUBLISHED after successful publication
        # This is the authoritative gate - task enters PUBLISHED only after
        # a real completion_contract is built
        state_machine = TaskStateMachine(self.task_id, db_path=self.db_path)
        result = state_machine.transition(
            to_status=TaskStatus.PUBLISHED,
            trigger="delivery_publisher",
            metadata={"outcome_id": outcome.outcome_id, "completion_contract_version": completion_contract.get("answer_state")}
        )

        if not result.success:
            raise RuntimeError(f"Failed to transition to PUBLISHED: {result.error}")

        # Log progress
        self.workspace.append_progress_ledger({
            "event": "published_to_delivery",
            "outcome_id": outcome.outcome_id,
            "completion_contract_state": completion_contract.get("answer_state"),
            "ts": time.time(),
        })

        return delivery_projection

    def get_latest_outcome(self) -> FinalOutcome | None:
        """Get the latest final outcome for this task."""
        with task_db_conn(self.db_path) as conn:
            row = conn.execute("""
                SELECT * FROM task_final_outcomes
                WHERE task_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (self.task_id,)).fetchone()

            if row is None:
                return None

            return FinalOutcome(
                outcome_id=row["outcome_id"],
                task_id=row["task_id"],
                attempt_id=row["attempt_id"],
                status=row["status"],
                final_artifact_refs_json=row["final_artifact_refs_json"],
                summary=row["summary"],
                promoted_decisions_json=row["promoted_decisions_json"],
                delivery_projection_ref=row["delivery_projection_ref"],
                memory_distillation_ref=row["memory_distillation_ref"],
                created_at=row["created_at"],
            )


def is_outcome_promoted(outcome: FinalOutcome) -> bool:
    """Check if an outcome has been promoted."""
    promoted_decisions = json.loads(outcome.promoted_decisions_json)
    return len(promoted_decisions) > 0


def can_publish_outcome(task_id: str, db_path: Path | None = None) -> tuple[bool, str]:
    """Check if a task outcome can be published.

    Returns:
        (can_publish, reason)
    """
    publisher = DeliveryPublisher(task_id, db_path=db_path)
    outcome = publisher.get_latest_outcome()

    if outcome is None:
        return False, "No final outcome exists"

    if not is_outcome_promoted(outcome):
        return False, "Outcome has not been promoted"

    if outcome.status != "success":
        return False, f"Outcome status is {outcome.status}, not success"

    # Additional check: ensure we have a valid summary
    if not outcome.summary or len(outcome.summary.strip()) == 0:
        return False, "Outcome has no summary to publish"

    return True, "OK"
