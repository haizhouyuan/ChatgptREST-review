"""Shared contracts for PreflightGate, CloseoutGate, and runtime checkpoints.

All gate outputs inherit from BaseGateResult which carries a schema URI
for versioning and downstream validation.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class WriteScope(str, Enum):
    READ_ONLY = "read_only"
    APPEND_ONLY = "append_only"
    MUTATE = "mutate"


class GateStatus(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


# ── Base result with schema versioning ─────────────────────────────────────

class BaseGateResult(BaseModel):
    """All gate results carry a schema URI for downstream validation."""

    schema_uri: str = Field(default="urn:paperclip:gate:v1", frozen=True)
    status: GateStatus
    reason_codes: list[str] = Field(default_factory=list)
    detail: str = ""


# ── PreflightGate output ───────────────────────────────────────────────────

class PreflightResult(BaseGateResult):
    """Output of PreflightGate — checked BEFORE agent execution."""

    agent_slug: str = ""
    task_type: str = ""
    model_lane: str = ""
    write_scope: WriteScope = WriteScope.READ_ONLY
    requires_git_diff: bool = False
    git_diff_present: bool = False
    estimated_cost_usd: Optional[float] = None


# ── CloseoutGate output ────────────────────────────────────────────────────

class CloseoutResult(BaseGateResult):
    """Output of CloseoutGate — checked AFTER agent execution."""

    task_type: str = ""
    write_scope: WriteScope = WriteScope.READ_ONLY
    files_changed: list[str] = Field(default_factory=list)
    files_declared: list[str] = Field(default_factory=list)
    evidence_spans: list[str] = Field(default_factory=list)
    memory_deltas: list[dict] = Field(default_factory=list)
    review_state: str = "pending"
