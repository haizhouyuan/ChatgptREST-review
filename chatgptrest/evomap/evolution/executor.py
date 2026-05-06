"""EvoMap Evolution — Plan Executor.

WP3: Execute approved evolution plans.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from chatgptrest.evomap.evolution.models import PlanOperation, PlanStatus
from chatgptrest.evomap.evolution.queue import ApprovalQueue
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.promotion_engine import PromotionEngine
from chatgptrest.evomap.knowledge.schema import PromotionStatus

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing an evolution plan."""
    plan_id: str
    success: bool
    executed_operations: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PlanExecutor:
    """Execute approved evolution plans against the knowledge base."""

    def __init__(self, queue: ApprovalQueue, db: KnowledgeDB):
        self.queue = queue
        self.db = db
        self.promotion_engine = PromotionEngine(db)

    def can_execute(self, plan_id: str) -> tuple[bool, str]:
        """Check if a plan can be executed."""
        plan = self.queue.get_plan(plan_id)
        if not plan:
            return False, f"Plan {plan_id} not found"
        if plan.status != PlanStatus.APPROVED.value:
            return False, f"Plan {plan_id} is not approved (status: {plan.status})"
        return True, ""

    def execute(self, plan_id: str) -> ExecutionResult:
        """Execute an approved plan. Only runs if plan is approved."""
        can_exec, reason = self.can_execute(plan_id)
        if not can_exec:
            return ExecutionResult(plan_id=plan_id, success=False, errors=[reason])

        plan = self.queue.get_plan(plan_id)
        result = ExecutionResult(plan_id=plan_id, success=True)

        self.queue.update_plan_status(plan_id, PlanStatus.EXECUTING.value, "executor", "Starting execution")

        conn = self.db.connect()
        savepoint = f"plan_exec_{uuid.uuid4().hex[:8]}"
        try:
            conn.execute(f"SAVEPOINT {savepoint}")
            operations = plan.get_operations()
            for op in operations:
                self._execute_operation(op, result)

            if result.success:
                conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                self.queue.update_plan_status(plan_id, PlanStatus.COMPLETED.value, "executor", "Execution completed")
            else:
                self.queue.update_plan_status(plan_id, PlanStatus.FAILED.value, "executor", "Execution failed")

        except Exception as e:
            try:
                conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception:
                logger.exception("Failed to roll back plan %s savepoint", plan_id)
            if result.executed_operations:
                result.warnings.append("Execution rolled back after operation failure")
                result.executed_operations = []
            error_message = f"Execution failed: {str(e)}"
            if error_message not in result.errors:
                result.errors.append(error_message)
            result.success = False
            self.queue.update_plan_status(plan_id, PlanStatus.FAILED.value, "executor", error_message)

        logger.info("Plan %s execution %s", plan_id, "succeeded" if result.success else "failed")
        return result

    def dry_run(self, plan_id: str) -> ExecutionResult:
        """Preview execution without making changes."""
        plan = self.queue.get_plan(plan_id)
        if not plan:
            return ExecutionResult(plan_id=plan_id, success=False, errors=[f"Plan {plan_id} not found"])

        result = ExecutionResult(plan_id=plan_id, success=True)
        result.warnings.append("This is a dry run - no changes will be made")

        operations = plan.get_operations()
        for op in operations:
            validation_result = self._validate_operation(op)
            if validation_result:
                result.warnings.append(f"Operation {op.op_type} on {op.target_id}: {validation_result}")

        return result

    def _execute_operation(self, op: PlanOperation, result: ExecutionResult):
        """Execute a single operation."""
        if op.op_type == "create_atom":
            self._op_create_atom(op, result)
        elif op.op_type == "update_atom":
            self._op_update_atom(op, result)
        elif op.op_type == "promote":
            self._op_promote(op, result)
        elif op.op_type == "quarantine":
            self._op_quarantine(op, result)
        elif op.op_type == "supersede":
            self._op_supersede(op, result)
        else:
            raise ValueError(f"Unknown operation type: {op.op_type}")

    def _validate_operation(self, op: PlanOperation) -> str | None:
        """Validate an operation. Returns error message if invalid."""
        if op.op_type == "create_atom":
            return None
        elif op.op_type == "update_atom":
            atom = self.db.get_atom(op.target_id)
            if not atom:
                return f"Atom {op.target_id} not found"
        elif op.op_type == "promote":
            atom = self.db.get_atom(op.target_id)
            if not atom:
                return f"Atom {op.target_id} not found"
            try:
                self._promotion_target(op)
            except ValueError as e:
                return str(e)
        elif op.op_type == "quarantine":
            atom = self.db.get_atom(op.target_id)
            if not atom:
                return f"Atom {op.target_id} not found"
        elif op.op_type == "supersede":
            atom = self.db.get_atom(op.target_id)
            if not atom:
                return f"Atom {op.target_id} not found"
        return None

    def _op_create_atom(self, op: PlanOperation, result: ExecutionResult):
        """Create a new atom."""
        from chatgptrest.evomap.knowledge.schema import Atom
        params = op.params
        atom = Atom(
            atom_id=params.get("atom_id", ""),
            question=params.get("question", ""),
            answer=params.get("answer", ""),
            atom_type=params.get("atom_type", "qa"),
            canonical_question=params.get("canonical_question", ""),
            episode_id=params.get("episode_id", ""),
            promotion_status=params.get("promotion_status", PromotionStatus.STAGED.value),
        )
        self.db.put_atom(atom, commit=False)
        result.executed_operations.append({"op": op.op_type, "atom_id": atom.atom_id})
        logger.info("Created atom %s via plan %s", atom.atom_id, result.plan_id)

    def _op_update_atom(self, op: PlanOperation, result: ExecutionResult):
        """Update an existing atom."""
        atom = self.db.get_atom(op.target_id)
        if not atom:
            raise ValueError(f"Atom {op.target_id} not found")

        for key, value in op.params.items():
            if hasattr(atom, key):
                setattr(atom, key, value)

        self.db.put_atom(atom, commit=False)
        result.executed_operations.append({"op": op.op_type, "atom_id": op.target_id})
        logger.info("Updated atom %s via plan %s", op.target_id, result.plan_id)

    def _op_promote(self, op: PlanOperation, result: ExecutionResult):
        """Promote an atom to active status."""
        target = self._promotion_target(op)
        promotion_result = self.promotion_engine.promote(
            op.target_id,
            target,
            reason=op.params.get("reason", f"plan:{result.plan_id}"),
            actor=op.params.get("actor", "plan_executor"),
            commit=False,
        )
        if not promotion_result.success:
            raise ValueError(
                promotion_result.error
                or f"promotion_failed_{promotion_result.from_status}_to_{promotion_result.to_status}"
            )
        result.executed_operations.append({"op": op.op_type, "atom_id": op.target_id})
        logger.info("Promoted atom %s via plan %s", op.target_id, result.plan_id)

    def _op_quarantine(self, op: PlanOperation, result: ExecutionResult):
        """Quarantine an atom (mark as archived)."""
        promotion_result = self.promotion_engine.quarantine(
            op.target_id,
            reason=op.params.get("reason", f"plan:{result.plan_id}"),
            actor=op.params.get("actor", "plan_executor"),
            commit=False,
        )
        if not promotion_result.success:
            raise ValueError(
                promotion_result.error
                or f"quarantine_failed_{promotion_result.from_status}_to_{promotion_result.to_status}"
            )
        result.executed_operations.append({"op": op.op_type, "atom_id": op.target_id})
        logger.info("Quarantined atom %s via plan %s", op.target_id, result.plan_id)

    def _op_supersede(self, op: PlanOperation, result: ExecutionResult):
        """Mark an atom as superseded by another."""
        new_atom_id = op.params.get("superseded_by")
        if not new_atom_id:
            raise ValueError(f"superseded_by not provided for {op.target_id}")

        promotion_result = self.promotion_engine.supersede(
            op.target_id,
            new_atom_id,
            reason=op.params.get("reason", f"plan:{result.plan_id}"),
            actor=op.params.get("actor", "plan_executor"),
            commit=False,
        )
        if not promotion_result.success:
            raise ValueError(
                promotion_result.error
                or f"supersede_failed_{promotion_result.from_status}_to_{promotion_result.to_status}"
            )
        result.executed_operations.append({"op": op.op_type, "atom_id": op.target_id})
        logger.info("Superseded atom %s with %s via plan %s", op.target_id, new_atom_id, result.plan_id)

    def _promotion_target(self, op: PlanOperation) -> PromotionStatus:
        """Resolve the promotion target from operation params."""
        target_name = op.params.get("target_status", PromotionStatus.ACTIVE.value)
        try:
            return PromotionStatus(target_name)
        except ValueError as e:
            raise ValueError(f"Invalid promotion target: {target_name}") from e
