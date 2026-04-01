"""Task Finalization Service - orchestrates the end-to-end finalization path.

This module provides the main orchestration path that connects:
1. PROMOTED -> PUBLISHED (via DeliveryPublisher.publish_to_delivery)
2. PUBLISHED -> DISTILLED (via MemoryDistiller.distill_outcome)
3. DISTILLED -> COMPLETED (via complete_task)

This is the real runtime path that was missing in previous implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chatgptrest.task_runtime.delivery_integration import (
    DeliveryPublisher,
)
from chatgptrest.task_runtime.memory_distillation import (
    MemoryDistiller,
    complete_task,
)
from chatgptrest.task_runtime.task_store import (
    FinalOutcome,
    TaskStatus,
    get_task,
    task_db_conn,
)
from chatgptrest.task_runtime.task_state_machine import TaskStateMachine


@dataclass
class FinalizationResult:
    """Result of task finalization."""
    success: bool
    task_id: str
    previous_status: str
    final_status: str
    error: str | None = None
    delivery_projection: dict[str, Any] | None = None
    memory_distillation: dict[str, Any] | None = None


class TaskFinalizationService:
    """Orchestrates the complete finalization path for a task.

    This service implements the real runtime path that connects:
    - PROMOTED -> PUBLISHED (via DeliveryPublisher)
    - PUBLISHED -> DISTILLED (via MemoryDistiller)
    - DISTILLED -> COMPLETED (via complete_task)

    Usage:
        finalization_service = TaskFinalizationService(task_id, db_path=db_path)
        result = finalization_service.finalize_task()

    The task must be in PROMOTED status with a valid final outcome before
    calling finalize_task().
    """

    def __init__(self, task_id: str, db_path: Path | None = None, memory_db_path: Path | None = None):
        self.task_id = task_id
        self.db_path = db_path
        self.memory_db_path = memory_db_path

    def can_finalize(self) -> tuple[bool, str]:
        """Check if task can be finalized.

        Returns:
            (can_finalize, reason)
        """
        with task_db_conn(self.db_path) as conn:
            task = get_task(conn, task_id=self.task_id)

        # Task must be in PROMOTED status
        if task.status != TaskStatus.PROMOTED:
            return False, f"Task must be in PROMOTED status, current status: {task.status.value}"

        # Check if final outcome exists
        publisher = DeliveryPublisher(self.task_id, db_path=self.db_path)
        outcome = publisher.get_latest_outcome()

        if outcome is None:
            return False, "No final outcome exists"

        # Basic validation: must have promoted decisions and success status
        if outcome.status != "success":
            return False, f"Outcome status is {outcome.status}, not success"

        import json
        promoted_decisions = json.loads(outcome.promoted_decisions_json)
        if len(promoted_decisions) == 0:
            return False, "No promoted decisions in outcome"

        # Validate summary exists and is non-empty
        if not outcome.summary or len(outcome.summary.strip()) == 0:
            return False, "Outcome has no summary to publish"

        return True, "OK"

    def finalize_task(self) -> FinalizationResult:
        """Execute the complete finalization path.

        This orchestrator:
        1. Validates prerequisites (task in PROMOTED, outcome exists)
        2. Calls DeliveryPublisher.publish_to_delivery -> task enters PUBLISHED
        3. Calls MemoryDistiller.distill_outcome -> task enters DISTILLED
        4. Calls complete_task -> task enters COMPLETED

        Returns:
            FinalizationResult with success status and details
        """
        # Get current status
        with task_db_conn(self.db_path) as conn:
            task = get_task(conn, task_id=self.task_id)
            previous_status = task.status.value

        # Step 1: Validate prerequisites
        can_finalize, reason = self.can_finalize()
        if not can_finalize:
            return FinalizationResult(
                success=False,
                task_id=self.task_id,
                previous_status=previous_status,
                final_status=previous_status,
                error=reason,
            )

        # Get the final outcome
        publisher = DeliveryPublisher(self.task_id, db_path=self.db_path)
        outcome = publisher.get_latest_outcome()

        if outcome is None:
            return FinalizationResult(
                success=False,
                task_id=self.task_id,
                previous_status=previous_status,
                final_status=previous_status,
                error="No final outcome found",
            )

        # Step 2: Publish to delivery -> PUBLISHED
        try:
            delivery_projection = publisher.publish_to_delivery(outcome)
        except Exception as e:
            return FinalizationResult(
                success=False,
                task_id=self.task_id,
                previous_status=previous_status,
                final_status=previous_status,
                error=f"Publication failed: {e}",
            )

        # Step 3: Distill to memory -> DISTILLED
        try:
            distiller = MemoryDistiller(
                self.task_id,
                memory_db_path=self.memory_db_path,
                task_db_path=self.db_path,
            )
            memory_distillation = distiller.distill_outcome(outcome)
        except Exception as e:
            return FinalizationResult(
                success=False,
                task_id=self.task_id,
                previous_status=previous_status,
                final_status=TaskStatus.PUBLISHED.value,  # Already published
                error=f"Memory distillation failed: {e}",
            )

        # Step 4: Complete task -> COMPLETED
        try:
            complete_task(self.task_id, db_path=self.db_path)
        except Exception as e:
            return FinalizationResult(
                success=False,
                task_id=self.task_id,
                previous_status=previous_status,
                final_status=TaskStatus.DISTILLED.value,  # Already distilled
                error=f"Task completion failed: {e}",
            )

        # Get final status
        with task_db_conn(self.db_path) as conn:
            task = get_task(conn, task_id=self.task_id)
            final_status = task.status.value

        return FinalizationResult(
            success=True,
            task_id=self.task_id,
            previous_status=previous_status,
            final_status=final_status,
            delivery_projection=delivery_projection,
            memory_distillation=memory_distillation,
        )


def finalize_task(task_id: str, db_path: Path | None = None, memory_db_path: Path | None = None) -> FinalizationResult:
    """Convenience function to finalize a task.

    Args:
        task_id: The task to finalize
        db_path: Path to task database
        memory_db_path: Path to memory database

    Returns:
        FinalizationResult
    """
    service = TaskFinalizationService(task_id, db_path=db_path, memory_db_path=memory_db_path)
    return service.finalize_task()