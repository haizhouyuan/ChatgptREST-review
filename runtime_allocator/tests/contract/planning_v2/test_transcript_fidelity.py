"""Contract: Agent outputs must be traceable to source evidence.

CloseoutGate requires evidence_spans for any declared deliverables."""

import pytest

from runtime_allocator.closeout_gate import closeout
from runtime_allocator.contracts import GateStatus, WriteScope


class TestTranscriptFidelity:
    def test_deliverable_with_evidence_allowed(self):
        result = closeout(
            task_type="meeting_extraction",
            write_scope=WriteScope.READ_ONLY,
            files_changed=[],
            files_declared=["action_items.json"],
            evidence_spans=["At 05:23, Alice said: 'I will handle the API integration'"],
        )
        assert result.status == GateStatus.ALLOWED

    def test_deliverable_without_evidence_blocked(self):
        result = closeout(
            task_type="meeting_extraction",
            write_scope=WriteScope.READ_ONLY,
            files_changed=[],
            files_declared=["action_items.json"],
            evidence_spans=[],
        )
        assert result.status == GateStatus.HUMAN_REVIEW_REQUIRED
        assert "claim_without_evidence" in result.reason_codes

    def test_no_deliverables_no_evidence_ok(self):
        result = closeout(
            task_type="finbot_news_summary",
            write_scope=WriteScope.READ_ONLY,
            files_changed=[],
            files_declared=[],
            evidence_spans=[],
        )
        assert result.status == GateStatus.ALLOWED
