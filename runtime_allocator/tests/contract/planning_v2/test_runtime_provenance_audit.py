"""Contract: Agent outputs must carry runtime provenance.

CloseoutGate should verify that outputs include evidence of
which runtime produced them."""

import pytest

from runtime_allocator.closeout_gate import closeout
from runtime_allocator.contracts import GateStatus, WriteScope


class TestRuntimeProvenanceAudit:
    def test_output_with_provenance_allowed(self):
        result = closeout(
            task_type="finbot_market_analysis",
            write_scope=WriteScope.READ_ONLY,
            files_changed=[],
            files_declared=["analysis.md"],
            evidence_spans=["Generated via minimax at 2026-05-05T10:00:00Z"],
        )
        assert result.status == GateStatus.ALLOWED

    def test_output_without_provenance_review(self):
        result = closeout(
            task_type="finbot_market_analysis",
            write_scope=WriteScope.READ_ONLY,
            files_changed=[],
            files_declared=["analysis.md"],
            evidence_spans=[],
        )
        assert result.status == GateStatus.HUMAN_REVIEW_REQUIRED
        assert "claim_without_evidence" in result.reason_codes
