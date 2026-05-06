"""Delivery publication scaffold for task runtime outcomes.

This bridge records a delivery projection but does not yet publish an
authoritative completion_contract / canonical_answer pair.
"""

from __future__ import annotations

import json
import time
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
    """Publishes task outcomes to a provisional delivery projection."""

    def __init__(self, task_id: str):
        self.task_id = task_id
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
        with task_db_conn() as conn:
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
        """Publish outcome to a provisional delivery projection."""
        # Get task record
        with task_db_conn() as conn:
            task = get_task(conn, task_id=self.task_id)

        # Parse intake spec
        intake_spec = json.loads(task.intake_json)

        # Note: This is a scaffold bridge. Full implementation would:
        # 1. Create or update a job record
        # 2. Build proper completion_contract
        # 3. Generate canonical_answer
        # 4. Handle all the existing contract fields

        delivery_projection = {
            "task_id": self.task_id,
            "outcome_id": outcome.outcome_id,
            "status": outcome.status,
            "summary": outcome.summary,
            "final_artifact_refs": json.loads(outcome.final_artifact_refs_json),
            "promoted_decisions": json.loads(outcome.promoted_decisions_json),
            "intake_spec": intake_spec,
            "published_at": time.time(),
        }

        # Update outcome with delivery reference
        with task_db_conn() as conn:
            now = time.time()
            conn.execute("""
                UPDATE task_final_outcomes
                SET delivery_projection_ref = ?
                WHERE outcome_id = ?
            """, (json.dumps(delivery_projection), outcome.outcome_id))
            conn.commit()

        # Transition task to PUBLISHED
        state_machine = TaskStateMachine(self.task_id)
        result = state_machine.transition(
            to_status=TaskStatus.PUBLISHED,
            trigger="delivery_publisher",
            metadata={"outcome_id": outcome.outcome_id}
        )

        if not result.success:
            raise RuntimeError(f"Failed to transition to PUBLISHED: {result.error}")

        # Log progress
        self.workspace.append_progress_ledger({
            "event": "published_to_delivery",
            "outcome_id": outcome.outcome_id,
            "ts": time.time(),
        })

        return delivery_projection

    def get_latest_outcome(self) -> FinalOutcome | None:
        """Get the latest final outcome for this task."""
        with task_db_conn() as conn:
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


def can_publish_outcome(task_id: str) -> tuple[bool, str]:
    """Check if a task outcome can be published.

    Returns:
        (can_publish, reason)
    """
    publisher = DeliveryPublisher(task_id)
    outcome = publisher.get_latest_outcome()

    if outcome is None:
        return False, "No final outcome exists"

    if not is_outcome_promoted(outcome):
        return False, "Outcome has not been promoted"

    if outcome.status != "success":
        return False, f"Outcome status is {outcome.status}, not success"

    return True, "OK"
