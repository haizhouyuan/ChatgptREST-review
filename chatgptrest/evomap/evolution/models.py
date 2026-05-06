"""EvoMap Evolution — Data Models.

WP3: Plan and approval data structures.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


class PlanStatus(str, enum.Enum):
    """Evolution plan lifecycle status."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


def _new_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    uid = uuid.uuid4().hex
    return f"{prefix}{uid}" if prefix else uid


def _now_iso() -> str:
    """Return current ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PlanOperation:
    """Single operation within an evolution plan."""
    op_type: str  # "create_atom" | "update_atom" | "promote" | "quarantine" | "supersede"
    target_id: str
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PlanOperation:
        return cls(**data)


@dataclass
class EvolutionPlan:
    """Evolution plan for atomic knowledge changes."""
    plan_id: str = field(default_factory=lambda: _new_id("plan_"))
    title: str = ""
    description: str = ""
    created_by: str = ""  # agent or user
    created_at: str = field(default_factory=_now_iso)
    target_atoms: list[str] = field(default_factory=list)
    operations: list[dict] = field(default_factory=list)  # serialized PlanOperation
    status: str = PlanStatus.DRAFT.value

    def add_operation(self, op: PlanOperation):
        """Add an operation to the plan."""
        self.operations.append(op.to_dict())

    def get_operations(self) -> list[PlanOperation]:
        """Deserialize operations."""
        return [PlanOperation.from_dict(op) for op in self.operations]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> EvolutionPlan:
        return cls(**data)


@dataclass
class ApprovalRecord:
    """Record of an approval decision on a plan."""
    approval_id: str = field(default_factory=lambda: _new_id("apr_"))
    plan_id: str = ""
    decision: str = ""  # "approved" | "rejected" | "revision_requested"
    reviewer: str = ""
    reason: str = ""
    created_at: str = field(default_factory=_now_iso)
    conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ApprovalRecord:
        return cls(**data)
