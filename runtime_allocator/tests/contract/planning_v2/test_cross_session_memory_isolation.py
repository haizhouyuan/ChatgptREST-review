"""Contract: Memory writes must be isolated per session.

Memory deltas must carry session_id and start in review_state=pending.
CloseoutGate blocks memory deltas with bad review state."""

import pytest

from runtime_allocator.closeout_gate import closeout
from runtime_allocator.contracts import GateStatus, WriteScope


class TestCrossSessionMemoryIsolation:
    def test_memory_delta_pending_allowed(self):
        result = closeout(
            task_type="memory_indexing",
            write_scope=WriteScope.MUTATE,
            files_changed=[],
            files_declared=[],
            evidence_spans=[],
            memory_deltas=[
                {"session_id": "sess_abc", "layer": "working", "content": "test"}
            ],
            review_state="pending",
        )
        assert result.status == GateStatus.ALLOWED

    def test_memory_delta_approved_blocked(self):
        result = closeout(
            task_type="memory_indexing",
            write_scope=WriteScope.MUTATE,
            files_changed=[],
            files_declared=[],
            evidence_spans=[],
            memory_deltas=[
                {"session_id": "sess_abc", "layer": "working", "content": "test"}
            ],
            review_state="approved",
        )
        assert result.status == GateStatus.BLOCKED
        assert "memory_delta_bad_review_state" in result.reason_codes

    def test_no_memory_delta_no_review_state_check(self):
        result = closeout(
            task_type="memory_benchmark",
            write_scope=WriteScope.READ_ONLY,
            files_changed=[],
            files_declared=[],
            evidence_spans=["result: 0.95"],
            memory_deltas=[],
            review_state="approved",
        )
        assert result.status == GateStatus.ALLOWED
