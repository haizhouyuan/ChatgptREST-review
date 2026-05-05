"""CloseoutGate — fail-closed safety checks AFTER agent execution.

Rules (evaluated in order, first block wins):
1. read_only task with files_changed → blocked
2. final claim without evidence span → human_review_required
3. memory delta without review_state=pending → blocked
"""

from __future__ import annotations

from typing import Optional

from runtime_allocator.contracts import (
    CloseoutResult,
    GateStatus,
    WriteScope,
)


def closeout(
    task_type: str,
    write_scope: WriteScope = WriteScope.READ_ONLY,
    files_changed: Optional[list[str]] = None,
    files_declared: Optional[list[str]] = None,
    evidence_spans: Optional[list[str]] = None,
    memory_deltas: Optional[list[dict]] = None,
    review_state: str = "pending",
) -> CloseoutResult:
    """Run fail-closed closeout checks on agent output.

    Args:
        task_type: Task class key.
        write_scope: Scope that was in effect.
        files_changed: Files actually modified by the agent.
        files_declared: Files the agent claimed it would modify.
        evidence_spans: Text spans backing the agent's claims.
        memory_deltas: Memory write candidates produced.
        review_state: Current review state (pending/approved/rejected).
    """
    files_changed = files_changed or []
    files_declared = files_declared or []
    evidence_spans = evidence_spans or []
    memory_deltas = memory_deltas or []
    reason_codes: list[str] = []

    # 1. Rule: read_only task must not change files
    if write_scope == WriteScope.READ_ONLY and files_changed:
        return CloseoutResult(
            status=GateStatus.BLOCKED,
            reason_codes=[
                "read_only_violation",
                f"changed={len(files_changed)}",
            ],
            detail=f"Read-only task {task_type} modified {len(files_changed)} file(s): {files_changed[:3]}",
            task_type=task_type,
            write_scope=write_scope,
            files_changed=files_changed,
            files_declared=files_declared,
            evidence_spans=evidence_spans,
            memory_deltas=memory_deltas,
            review_state=review_state,
        )

    # 2. Rule: final claim must have evidence
    # A "final claim" is when the task produced deliverables (files_declared or evidence)
    if files_declared and not evidence_spans:
        return CloseoutResult(
            status=GateStatus.HUMAN_REVIEW_REQUIRED,
            reason_codes=[
                "claim_without_evidence",
                f"declared={len(files_declared)}",
            ],
            detail=f"Task {task_type} declared {len(files_declared)} deliverable(s) but provided no evidence spans",
            task_type=task_type,
            write_scope=write_scope,
            files_changed=files_changed,
            files_declared=files_declared,
            evidence_spans=evidence_spans,
            memory_deltas=memory_deltas,
            review_state=review_state,
        )

    # 3. Rule: memory delta must be in pending review state
    if memory_deltas and review_state != "pending":
        return CloseoutResult(
            status=GateStatus.BLOCKED,
            reason_codes=[
                "memory_delta_bad_review_state",
                f"state={review_state}",
            ],
            detail=f"Memory deltas require review_state=pending, got {review_state}",
            task_type=task_type,
            write_scope=write_scope,
            files_changed=files_changed,
            files_declared=files_declared,
            evidence_spans=evidence_spans,
            memory_deltas=memory_deltas,
            review_state=review_state,
        )

    # All checks passed
    return CloseoutResult(
        status=GateStatus.ALLOWED,
        reason_codes=["closeout_passed"],
        detail="All closeout checks passed",
        task_type=task_type,
        write_scope=write_scope,
        files_changed=files_changed,
        files_declared=files_declared,
        evidence_spans=evidence_spans,
        memory_deltas=memory_deltas,
        review_state=review_state,
    )
