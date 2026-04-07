"""Task Initializer - Converts intake to frozen task context.

This module implements Phase 1: Task Initializer and Frozen Context.
It takes a TaskIntakeSpec and produces:
- TASK_REQUEST.md
- TASK_CONTEXT.lock.json
- TASK_SPEC.yaml
- EXECUTION_PLAN.md
- ACCEPTANCE_CHECKS.json
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chatgptrest.advisor.task_intake import TaskIntakeSpec
from chatgptrest.task_runtime.task_store import (
    TaskRecord,
    TaskStatus,
    create_task,
    task_db_conn,
    update_task_status,
)
from chatgptrest.task_runtime.task_state_machine import TaskStateMachine
from chatgptrest.task_runtime.task_workspace import TaskWorkspace


@dataclass
class FrozenTaskContext:
    """Frozen context snapshot for task execution."""
    task_id: str
    intake_spec: dict[str, Any]
    context_snapshot: dict[str, Any]
    task_spec: dict[str, Any]
    execution_plan: str
    acceptance_checks: dict[str, Any]
    context_hash: str
    frozen_at: float


class TaskInitializer:
    """Initializes tasks from intake specs."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path

    def initialize_task(
        self,
        *,
        intake_spec: TaskIntakeSpec,
        context_snapshot: dict[str, Any] | None = None,
    ) -> FrozenTaskContext:
        """Initialize a task from intake spec.

        Steps:
        1. Create task record in database
        2. Generate frozen context snapshot
        3. Generate task spec
        4. Generate execution plan
        5. Generate acceptance checks
        6. Write all artifacts to workspace
        7. Transition to INITIALIZED status
        """
        # Create task record
        with task_db_conn(self.db_path) as conn:
            task_record = create_task(
                conn,
                task_kind=intake_spec.scenario,
                origin=intake_spec.source,
                logical_task_key=intake_spec.task_id,
                priority=0,
                owner_identity=intake_spec.user_id,
                task_mode="standard",
                freeze_level="full",
                intake_json=intake_spec.model_dump_json(),
            )

        task_id = task_record.task_id

        # Initialize workspace
        workspace = TaskWorkspace(task_id)
        workspace.initialize()

        # Generate frozen context
        if context_snapshot is None:
            context_snapshot = self._generate_context_snapshot(intake_spec)

        context_hash = self._hash_context(context_snapshot)

        # Generate task spec
        task_spec = self._generate_task_spec(intake_spec, context_snapshot)

        # Generate execution plan
        execution_plan = self._generate_execution_plan(intake_spec, task_spec)

        # Generate acceptance checks
        acceptance_checks = self._generate_acceptance_checks(intake_spec)

        # Write artifacts
        workspace.write_task_request(self._format_task_request(intake_spec))
        workspace.write_task_context_lock(context_snapshot)
        workspace.write_task_spec(task_spec)
        workspace.write_execution_plan(execution_plan)
        workspace.write_acceptance_checks(acceptance_checks)

        # Update task record with workspace and context
        with task_db_conn(self.db_path) as conn:
            now = time.time()
            conn.execute("""
                UPDATE tasks
                SET workspace_path = ?, context_lock_json = ?, updated_at = ?
                WHERE task_id = ?
            """, (str(workspace.root), json.dumps(context_snapshot), now, task_id))
            conn.commit()

        # Transition to INITIALIZED
        state_machine = TaskStateMachine(task_id, db_path=self.db_path)
        result = state_machine.transition(
            to_status=TaskStatus.INITIALIZED,
            trigger="task_initializer",
            metadata={"context_hash": context_hash}
        )

        if not result.success:
            raise RuntimeError(f"Failed to transition to INITIALIZED: {result.error}")

        return FrozenTaskContext(
            task_id=task_id,
            intake_spec=intake_spec.model_dump(),
            context_snapshot=context_snapshot,
            task_spec=task_spec,
            execution_plan=execution_plan,
            acceptance_checks=acceptance_checks,
            context_hash=context_hash,
            frozen_at=time.time(),
        )

    def _generate_context_snapshot(self, intake_spec: TaskIntakeSpec) -> dict[str, Any]:
        """Generate context snapshot from intake spec."""
        # This would integrate with planning_bootstrap, repo context, etc.
        # For now, return a minimal snapshot
        return {
            "spec_version": "context-snapshot-v1",
            "objective": intake_spec.objective,
            "scenario": intake_spec.scenario,
            "execution_profile": intake_spec.execution_profile,
            "constraints": intake_spec.constraints or {},
            "attachments": intake_spec.attachments or [],
            "repo_context": {},  # Would be populated by bootstrap
            "environment": {},  # Would be populated by env scanner
            "frozen_at": time.time(),
        }

    def _hash_context(self, context: dict[str, Any]) -> str:
        """Generate hash of frozen context."""
        canonical = json.dumps(context, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _generate_task_spec(
        self,
        intake_spec: TaskIntakeSpec,
        context_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate task specification."""
        return {
            "spec_version": "task-spec-v1",
            "objective": intake_spec.objective,
            "scenario": intake_spec.scenario,
            "output_shape": intake_spec.output_shape,
            "execution_profile": intake_spec.execution_profile,
            "acceptance_profile": intake_spec.acceptance.profile,
            "constraints": intake_spec.constraints or {},
            "evidence_requirements": intake_spec.evidence_required.to_dict(),
            "context_ref": context_snapshot.get("frozen_at"),
        }

    def _generate_execution_plan(
        self,
        intake_spec: TaskIntakeSpec,
        task_spec: dict[str, Any],
    ) -> str:
        """Generate execution plan markdown."""
        lines = [
            "# Execution Plan",
            "",
            f"**Objective:** {intake_spec.objective}",
            f"**Scenario:** {intake_spec.scenario}",
            f"**Output Shape:** {intake_spec.output_shape}",
            "",
            "## Approach",
            "",
            "1. Initialize execution context",
            "2. Execute primary objective",
            "3. Generate artifacts per contract",
            "4. Submit for evaluation",
            "",
            "## Constraints",
            "",
        ]

        for key, value in (intake_spec.constraints or {}).items():
            lines.append(f"- **{key}:** {value}")

        lines.extend([
            "",
            "## Success Criteria",
            "",
            f"- Pass score: {intake_spec.acceptance.pass_score}",
            f"- Required sections: {', '.join(intake_spec.acceptance.required_sections) or 'none'}",
            f"- Required artifacts: {', '.join(intake_spec.acceptance.required_artifacts) or 'none'}",
        ])

        return "\n".join(lines)

    def _generate_acceptance_checks(self, intake_spec: TaskIntakeSpec) -> dict[str, Any]:
        """Generate acceptance checks."""
        return {
            "spec_version": "acceptance-checks-v1",
            "profile": intake_spec.acceptance.profile,
            "pass_score": intake_spec.acceptance.pass_score,
            "required_sections": intake_spec.acceptance.required_sections,
            "required_artifacts": intake_spec.acceptance.required_artifacts,
            "min_evidence_items": intake_spec.acceptance.min_evidence_items,
            "require_traceability": intake_spec.acceptance.require_traceability,
            "checks": [
                {
                    "check_id": "output_shape",
                    "description": f"Output must match shape: {intake_spec.output_shape}",
                    "required": True,
                },
                {
                    "check_id": "required_sections",
                    "description": "All required sections must be present",
                    "required": len(intake_spec.acceptance.required_sections) > 0,
                },
                {
                    "check_id": "required_artifacts",
                    "description": "All required artifacts must be generated",
                    "required": len(intake_spec.acceptance.required_artifacts) > 0,
                },
            ],
        }

    def _format_task_request(self, intake_spec: TaskIntakeSpec) -> str:
        """Format task request as markdown."""
        lines = [
            "# Task Request",
            "",
            f"**Source:** {intake_spec.source}",
            f"**Ingress Lane:** {intake_spec.ingress_lane}",
            f"**Trace ID:** {intake_spec.trace_id}",
            "",
            "## Objective",
            "",
            intake_spec.objective,
            "",
            "## Scenario",
            "",
            f"**Type:** {intake_spec.scenario}",
            f"**Output Shape:** {intake_spec.output_shape}",
            f"**Execution Profile:** {intake_spec.execution_profile}",
            "",
        ]

        if intake_spec.constraints:
            lines.extend([
                "## Constraints",
                "",
            ])
            for key, value in intake_spec.constraints.items():
                lines.append(f"- **{key}:** {value}")
            lines.append("")

        if intake_spec.attachments:
            lines.extend([
                "## Attachments",
                "",
            ])
            for file_path in intake_spec.attachments:
                lines.append(f"- {file_path}")
            lines.append("")

        return "\n".join(lines)


def freeze_task_context(task_id: str) -> bool:
    """Freeze task context (transition to FROZEN status)."""
    state_machine = TaskStateMachine(task_id)

    result = state_machine.transition(
        to_status=TaskStatus.FROZEN,
        trigger="context_freeze",
        metadata={"frozen_by": "task_initializer"}
    )

    return result.success
