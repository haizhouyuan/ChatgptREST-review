"""EvoMap Promotion Engine — Scratch/Live Knowledge Governance.

Manages atom promotion lifecycle:
- staged → candidate → active → superseded → archived

Key features:
- Groundedness gate enforcement before promotion to active
- Immutable audit trail for all transitions
- Quarantine and rollback capabilities

Reference: Issue #99 WP2
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from chatgptrest.evomap.knowledge.groundedness_checker import enforce_promotion_gate
from chatgptrest.evomap.knowledge.schema import Atom, PromotionStatus

if TYPE_CHECKING:
    from chatgptrest.evomap.knowledge.db import KnowledgeDB

logger = logging.getLogger(__name__)


ALLOWED_TRANSITIONS = {
    PromotionStatus.STAGED.value: {PromotionStatus.CANDIDATE.value},
    PromotionStatus.CANDIDATE.value: {PromotionStatus.ACTIVE.value, PromotionStatus.STAGED.value},
    PromotionStatus.ACTIVE.value: {PromotionStatus.SUPERSEDED.value, PromotionStatus.ARCHIVED.value},
    PromotionStatus.SUPERSEDED.value: {PromotionStatus.ARCHIVED.value},
    PromotionStatus.ARCHIVED.value: set(),
}


@dataclass
class PromotionResult:
    """Result of a promotion operation."""
    success: bool
    atom_id: str
    from_status: str
    to_status: str
    reason: str
    actor: str
    groundedness_passed: bool | None = None
    groundedness_score: float | None = None
    error: str | None = None


@dataclass
class PromotionAuditRecord:
    """Immutable audit record for a promotion transition."""
    audit_id: str = field(default_factory=lambda: f"pa_{uuid.uuid4().hex[:12]}")
    atom_id: str = ""
    from_status: str = ""
    to_status: str = ""
    reason: str = ""
    actor: str = "system"
    groundedness_result: str | None = None
    created_at: float = field(default_factory=time.time)


class PromotionEngine:
    """Manages atom promotion lifecycle with governance gates."""

    GROUNDEDNESS_THRESHOLD = 0.7

    def __init__(self, db: KnowledgeDB):
        self.db = db

    def promote(
        self,
        atom_id: str,
        target: PromotionStatus,
        *,
        reason: str,
        actor: str = "system",
        commit: bool = True,
    ) -> PromotionResult:
        """Promote atom to target status.

        Special behavior:
        - promotion to 'active' requires groundedness gate check
        - all transitions are recorded in audit trail

        Returns PromotionResult with success status and details.
        """
        conn = self.db.connect()

        row = conn.execute(
            "SELECT promotion_status FROM atoms WHERE atom_id = ?",
            (atom_id,),
        ).fetchone()

        if not row:
            return PromotionResult(
                success=False,
                atom_id=atom_id,
                from_status="",
                to_status=target.value,
                reason=reason,
                actor=actor,
                error="atom_not_found",
            )

        current_status = row[0]

        if target.value not in ALLOWED_TRANSITIONS.get(current_status, set()):
            return PromotionResult(
                success=False,
                atom_id=atom_id,
                from_status=current_status,
                to_status=target.value,
                reason=reason,
                actor=actor,
                error=f"invalid_transition_from_{current_status}",
            )

        groundedness_passed: bool | None = None
        groundedness_score: float | None = None
        groundedness_json: str | None = None

        if target == PromotionStatus.ACTIVE:
            passed, record = enforce_promotion_gate(
                self.db,
                atom_id,
                threshold=self.GROUNDEDNESS_THRESHOLD,
                commit=False,
            )
            groundedness_passed = passed
            groundedness_score = record.overall_score
            groundedness_json = json.dumps({
                "passed": passed,
                "score": record.overall_score,
                "audit_id": record.audit_id,
            })

            if not passed:
                conn.execute(
                    "UPDATE atoms SET promotion_status = ?, promotion_reason = ? WHERE atom_id = ?",
                    (PromotionStatus.STAGED.value, f"groundedness_failed_{record.audit_id}", atom_id),
                )

                self.db.add_promotion_audit(
                    audit_id=str(uuid.uuid4()),
                    atom_id=atom_id,
                    from_status=current_status,
                    to_status=PromotionStatus.STAGED.value,
                    reason=f"groundedness_gate_failed: {reason}",
                    actor=actor,
                    groundedness_result=groundedness_json,
                    commit=False,
                )
                if commit:
                    conn.commit()

                return PromotionResult(
                    success=False,
                    atom_id=atom_id,
                    from_status=current_status,
                    to_status=PromotionStatus.STAGED.value,
                    reason=f"groundedness_gate_failed: {reason}",
                    actor=actor,
                    groundedness_passed=False,
                    groundedness_score=groundedness_score,
                )

        conn.execute(
            "UPDATE atoms SET promotion_status = ?, promotion_reason = ? WHERE atom_id = ?",
            (target.value, reason, atom_id),
        )

        self.db.add_promotion_audit(
            audit_id=str(uuid.uuid4()),
            atom_id=atom_id,
            from_status=current_status,
            to_status=target.value,
            reason=reason,
            actor=actor,
            groundedness_result=groundedness_json,
            commit=False,
        )
        if commit:
            conn.commit()

        return PromotionResult(
            success=True,
            atom_id=atom_id,
            from_status=current_status,
            to_status=target.value,
            reason=reason,
            actor=actor,
            groundedness_passed=groundedness_passed,
            groundedness_score=groundedness_score,
        )

    def quarantine(
        self,
        atom_id: str,
        *,
        reason: str,
        actor: str = "system",
        commit: bool = True,
    ) -> PromotionResult:
        """Move atom to archived status with quarantine flag.

        Quarantine is used for atoms that need review but shouldn't be
        immediately deleted.
        """
        return self.promote(
            atom_id,
            PromotionStatus.ARCHIVED,
            reason=f"quarantine: {reason}",
            actor=actor,
            commit=commit,
        )

    def supersede(
        self,
        atom_id: str,
        superseded_by: str,
        *,
        reason: str,
        actor: str = "system",
        commit: bool = True,
    ) -> PromotionResult:
        """Move atom to superseded status and persist the replacement pointer."""
        result = self.promote(
            atom_id,
            PromotionStatus.SUPERSEDED,
            reason=reason,
            actor=actor,
            commit=False,
        )
        if not result.success:
            return result

        conn = self.db.connect()
        conn.execute(
            "UPDATE atoms SET superseded_by = ? WHERE atom_id = ?",
            (superseded_by, atom_id),
        )
        if commit:
            conn.commit()
        return result

    def rollback(
        self,
        atom_id: str,
        *,
        reason: str,
        actor: str = "system",
        commit: bool = True,
    ) -> PromotionResult:
        """Rollback atom to staged status.

        Used when an atom needs to go through the promotion process again.
        """
        return self.promote(
            atom_id,
            PromotionStatus.STAGED,
            reason=f"rollback: {reason}",
            actor=actor,
            commit=commit,
        )

    def get_audit_trail(self, atom_id: str) -> list[PromotionAuditRecord]:
        """Get the audit trail for an atom."""
        records = self.db.list_promotion_audits(atom_id)
        return [
            PromotionAuditRecord(
                audit_id=r["audit_id"],
                atom_id=r["atom_id"],
                from_status=r["from_status"],
                to_status=r["to_status"],
                reason=r["reason"],
                actor=r["actor"],
                groundedness_result=r.get("groundedness_result"),
                created_at=r["created_at"],
            )
            for r in records
        ]

    def can_promote(self, atom_id: str, target: PromotionStatus) -> bool:
        """Check if a promotion is allowed without performing it."""
        conn = self.db.connect()
        row = conn.execute(
            "SELECT promotion_status FROM atoms WHERE atom_id = ?",
            (atom_id,),
        ).fetchone()

        if not row:
            return False

        current = row[0]
        return target.value in ALLOWED_TRANSITIONS.get(current, set())
