"""EvoMap Evolution — Approval Queue.

WP3: Approval queue for evolution plans.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from chatgptrest.evomap.evolution.models import (
    ApprovalRecord,
    EvolutionPlan,
    PlanStatus,
    _now_iso,
)

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "evolution_queue.db"
)

_DDL = """
-- Evolution plans
CREATE TABLE IF NOT EXISTS evolution_plans (
    plan_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    target_atoms TEXT NOT NULL DEFAULT '[]',
    operations TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft'
);

CREATE INDEX IF NOT EXISTS idx_plans_status ON evolution_plans(status);
CREATE INDEX IF NOT EXISTS idx_plans_created ON evolution_plans(created_at);

-- Approval records
CREATE TABLE IF NOT EXISTS approval_records (
    approval_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reviewer TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    conditions TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (plan_id) REFERENCES evolution_plans(plan_id)
);

CREATE INDEX IF NOT EXISTS idx_approvals_plan ON approval_records(plan_id);

-- Audit log for state transitions
CREATE TABLE IF NOT EXISTS plan_audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id TEXT NOT NULL,
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES evolution_plans(plan_id)
);

CREATE INDEX IF NOT EXISTS idx_audit_plan ON plan_audit_log(plan_id);
"""


class ApprovalQueue:
    """Approval queue for evolution plans."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get("EVOLUTION_QUEUE_DB", DEFAULT_DB_PATH)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_DDL)
        self._conn.commit()
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()

    def _log_audit(self, plan_id: str, old_status: str, new_status: str, actor: str = "", reason: str = ""):
        """Record a state transition in the audit log."""
        conn = self.connect()
        conn.execute(
            """INSERT INTO plan_audit_log (plan_id, old_status, new_status, actor, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (plan_id, old_status, new_status, actor, reason, _now_iso()),
        )
        conn.commit()

    def submit_plan(self, plan: EvolutionPlan) -> str:
        """Submit a plan for approval. Returns plan_id."""
        conn = self.connect()
        plan.status = PlanStatus.PENDING_APPROVAL.value
        conn.execute(
            """INSERT INTO evolution_plans (plan_id, title, description, created_by, created_at, target_atoms, operations, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                plan.plan_id,
                plan.title,
                plan.description,
                plan.created_by,
                plan.created_at,
                json.dumps(plan.target_atoms, ensure_ascii=False),
                json.dumps([op.to_dict() for op in plan.get_operations()], ensure_ascii=False),
                plan.status,
            ),
        )
        self._log_audit(plan.plan_id, "", PlanStatus.PENDING_APPROVAL.value, plan.created_by, "Plan submitted")
        conn.commit()
        logger.info("Plan %s submitted for approval", plan.plan_id)
        return plan.plan_id

    def list_pending(self) -> list[EvolutionPlan]:
        """List all plans pending approval."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM evolution_plans WHERE status = ? ORDER BY created_at",
            (PlanStatus.PENDING_APPROVAL.value,),
        ).fetchall()
        return [self._row_to_plan(dict(r)) for r in rows]

    def approve(self, plan_id: str, reviewer: str, reason: str, conditions: list[str] = None) -> ApprovalRecord:
        """Approve a plan. Only allowed if plan is pending_approval."""
        conn = self.connect()
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        if plan.status != PlanStatus.PENDING_APPROVAL.value:
            raise ValueError(f"Plan {plan_id} is not pending approval (status: {plan.status})")

        old_status = plan.status
        plan.status = PlanStatus.APPROVED.value
        conn.execute(
            "UPDATE evolution_plans SET status = ? WHERE plan_id = ?",
            (plan.status, plan_id),
        )

        approval = ApprovalRecord(
            plan_id=plan_id,
            decision="approved",
            reviewer=reviewer,
            reason=reason,
            conditions=conditions or [],
        )
        conn.execute(
            """INSERT INTO approval_records (approval_id, plan_id, decision, reviewer, reason, created_at, conditions)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                approval.approval_id,
                approval.plan_id,
                approval.decision,
                approval.reviewer,
                approval.reason,
                approval.created_at,
                json.dumps(approval.conditions, ensure_ascii=False),
            ),
        )
        self._log_audit(plan_id, old_status, PlanStatus.APPROVED.value, reviewer, reason)
        conn.commit()
        logger.info("Plan %s approved by %s", plan_id, reviewer)
        return approval

    def reject(self, plan_id: str, reviewer: str, reason: str) -> ApprovalRecord:
        """Reject a plan. Only allowed if plan is pending_approval."""
        conn = self.connect()
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        if plan.status != PlanStatus.PENDING_APPROVAL.value:
            raise ValueError(f"Plan {plan_id} is not pending approval (status: {plan.status})")

        old_status = plan.status
        plan.status = PlanStatus.REJECTED.value
        conn.execute(
            "UPDATE evolution_plans SET status = ? WHERE plan_id = ?",
            (plan.status, plan_id),
        )

        approval = ApprovalRecord(
            plan_id=plan_id,
            decision="rejected",
            reviewer=reviewer,
            reason=reason,
        )
        conn.execute(
            """INSERT INTO approval_records (approval_id, plan_id, decision, reviewer, reason, created_at, conditions)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                approval.approval_id,
                approval.plan_id,
                approval.decision,
                approval.reviewer,
                approval.reason,
                approval.created_at,
                "[]",
            ),
        )
        self._log_audit(plan_id, old_status, PlanStatus.REJECTED.value, reviewer, reason)
        conn.commit()
        logger.info("Plan %s rejected by %s", plan_id, reviewer)
        return approval

    def request_revision(self, plan_id: str, reviewer: str, reason: str) -> ApprovalRecord:
        """Request revision on a plan. Only allowed if plan is pending_approval."""
        conn = self.connect()
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        if plan.status != PlanStatus.PENDING_APPROVAL.value:
            raise ValueError(f"Plan {plan_id} is not pending approval (status: {plan.status})")

        old_status = plan.status
        plan.status = PlanStatus.REVISION_REQUESTED.value
        conn.execute(
            "UPDATE evolution_plans SET status = ? WHERE plan_id = ?",
            (plan.status, plan_id),
        )

        approval = ApprovalRecord(
            plan_id=plan_id,
            decision="revision_requested",
            reviewer=reviewer,
            reason=reason,
        )
        conn.execute(
            """INSERT INTO approval_records (approval_id, plan_id, decision, reviewer, reason, created_at, conditions)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                approval.approval_id,
                approval.plan_id,
                approval.decision,
                approval.reviewer,
                approval.reason,
                approval.created_at,
                "[]",
            ),
        )
        self._log_audit(plan_id, old_status, PlanStatus.REVISION_REQUESTED.value, reviewer, reason)
        conn.commit()
        logger.info("Revision requested on plan %s by %s", plan_id, reviewer)
        return approval

    def get_plan(self, plan_id: str) -> EvolutionPlan | None:
        """Get a plan by ID."""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM evolution_plans WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()
        return self._row_to_plan(dict(row)) if row else None

    def get_approvals(self, plan_id: str) -> list[ApprovalRecord]:
        """Get all approval records for a plan."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM approval_records WHERE plan_id = ? ORDER BY created_at",
            (plan_id,),
        ).fetchall()
        return [self._row_to_approval(dict(r)) for r in rows]

    def _row_to_plan(self, row: dict) -> EvolutionPlan:
        """Convert a database row to an EvolutionPlan."""
        target_atoms = json.loads(row["target_atoms"]) if row["target_atoms"] else []
        operations = json.loads(row["operations"]) if row["operations"] else []
        return EvolutionPlan(
            plan_id=row["plan_id"],
            title=row["title"],
            description=row["description"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            target_atoms=target_atoms,
            operations=operations,
            status=row["status"],
        )

    def _row_to_approval(self, row: dict) -> ApprovalRecord:
        """Convert a database row to an ApprovalRecord."""
        conditions = json.loads(row["conditions"]) if row["conditions"] else []
        return ApprovalRecord(
            approval_id=row["approval_id"],
            plan_id=row["plan_id"],
            decision=row["decision"],
            reviewer=row["reviewer"],
            reason=row["reason"],
            created_at=row["created_at"],
            conditions=conditions,
        )

    def update_plan_status(self, plan_id: str, new_status: str, actor: str = "", reason: str = ""):
        """Update plan status with audit logging."""
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        old_status = plan.status
        conn = self.connect()
        conn.execute(
            "UPDATE evolution_plans SET status = ? WHERE plan_id = ?",
            (new_status, plan_id),
        )
        self._log_audit(plan_id, old_status, new_status, actor, reason)
        conn.commit()
