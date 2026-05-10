from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


Status = Literal["pass", "fail", "blocked"]
MemoryDisposition = Literal["candidate_memory_delta", "no_write_reason"]
ConfigChangeState = Literal[
    "snapshot",
    "proposal",
    "risk_review",
    "bounded_change",
    "live_smoke",
    "rollback_proof",
    "paperclip_closeout",
    "blocked",
]

ApprovalDecision = Literal["approve", "reject", "request_changes", "defer"]
ConfigChangeKind = Literal["runtime", "mcp", "skill", "settings", "permissions", "hooks"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RuntimePreflight:
    runtime: str
    command: str
    status: Status
    checked_at: str = field(default_factory=utc_now)
    fallback_runtime: str | None = None
    blocker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime": self.runtime,
            "command": self.command,
            "status": self.status,
            "checked_at": self.checked_at,
            "fallback_runtime": self.fallback_runtime,
            "blocker": self.blocker,
        }


@dataclass(frozen=True)
class EvidenceManifest:
    evidence_path: str
    evidence_kind: str
    produced_by: str
    sha256: str | None = None
    source_paths: list[str] = field(default_factory=list)
    non_claims: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_path": self.evidence_path,
            "evidence_kind": self.evidence_kind,
            "produced_by": self.produced_by,
            "sha256": self.sha256,
            "source_paths": self.source_paths,
            "non_claims": self.non_claims,
        }


@dataclass(frozen=True)
class ValidatorResult:
    name: str
    status: Status
    command: str
    output_path: str | None = None
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "command": self.command,
            "output_path": self.output_path,
            "failures": self.failures,
        }


@dataclass(frozen=True)
class MemoryCloseout:
    disposition: MemoryDisposition
    path: str | None = None
    no_write_reason: str | None = None
    candidate_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition,
            "path": self.path,
            "no_write_reason": self.no_write_reason,
            "candidate_count": self.candidate_count,
        }


@dataclass(frozen=True)
class CompanyRunCloseout:
    company: str
    issue_identifier: str
    issue_id: str
    status: Status
    runtime_preflight: RuntimePreflight
    evidence: list[EvidenceManifest]
    validators: list[ValidatorResult]
    memory_closeout: MemoryCloseout
    paperclip_readback: dict[str, Any]
    blockers: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": self.company,
            "issue_identifier": self.issue_identifier,
            "issue_id": self.issue_id,
            "status": self.status,
            "created_at": self.created_at,
            "runtime_preflight": self.runtime_preflight.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "validators": [item.to_dict() for item in self.validators],
            "memory_closeout": self.memory_closeout.to_dict(),
            "paperclip_readback": self.paperclip_readback,
            "blockers": self.blockers,
        }


@dataclass(frozen=True)
class ConfigChangeRecord:
    """Gated change record for runtime/MCP/skill/config mutations.

    Every native runtime/MCP/skill config mutation must be represented as a
    ConfigChangeRecord, not hidden in ordinary execution code.  The record
    flows through the canonical states defined in ConfigChangeState and
    requires an explicit ApprovalDecision before the 'bounded_change' state.
    """

    change_id: str
    kind: ConfigChangeKind
    title: str
    description: str
    affected_runtimes: list[str]
    proposed_by: str
    current_state: ConfigChangeState
    approval_decision: ApprovalDecision | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    snapshot_paths: list[str] = field(default_factory=list)
    proposal_paths: list[str] = field(default_factory=list)
    rollback_commands: list[str] = field(default_factory=list)
    smoke_commands: list[str] = field(default_factory=list)
    risk_review_notes: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    issue_id: str | None = None
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_id": self.change_id,
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "affected_runtimes": self.affected_runtimes,
            "proposed_by": self.proposed_by,
            "current_state": self.current_state,
            "approval_decision": self.approval_decision,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "snapshot_paths": self.snapshot_paths,
            "proposal_paths": self.proposal_paths,
            "rollback_commands": self.rollback_commands,
            "smoke_commands": self.smoke_commands,
            "risk_review_notes": self.risk_review_notes,
            "blockers": self.blockers,
            "issue_id": self.issue_id,
            "created_at": self.created_at,
        }

    def can_apply(self) -> tuple[bool, str]:
        if self.current_state == "blocked":
            return False, "change is blocked"
        if self.current_state != "bounded_change":
            return False, f"current state is {self.current_state}; must reach bounded_change"
        if self.approval_decision != "approve":
            return False, f"approval decision is {self.approval_decision}; must be 'approve'"
        return True, ""


def path_exists(value: str | None, base: Path | None = None) -> bool:
    if not value:
        return False
    path = Path(value)
    if not path.is_absolute() and base is not None:
        path = base / path
    return path.exists()
