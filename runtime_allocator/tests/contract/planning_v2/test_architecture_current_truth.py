"""Contract: Architecture claims must match current system truth.

CloseoutGate should require human review if the agent's output
makes architecture claims without evidence from current code."""

import pytest

from runtime_allocator.closeout_gate import closeout
from runtime_allocator.contracts import GateStatus, WriteScope


class TestArchitectureCurrentTruth:
    def test_architecture_claim_with_evidence_allowed(self):
        result = closeout(
            task_type="strategic_plan",
            write_scope=WriteScope.READ_ONLY,
            files_changed=[],
            files_declared=["architecture_v2.md"],
            evidence_spans=["Current code shows 3 microservices in /services/"],
        )
        assert result.status == GateStatus.ALLOWED

    def test_architecture_claim_without_evidence_review(self):
        result = closeout(
            task_type="strategic_plan",
            write_scope=WriteScope.READ_ONLY,
            files_changed=[],
            files_declared=["architecture_v2.md"],
            evidence_spans=[],
        )
        assert result.status == GateStatus.HUMAN_REVIEW_REQUIRED
        assert "claim_without_evidence" in result.reason_codes
