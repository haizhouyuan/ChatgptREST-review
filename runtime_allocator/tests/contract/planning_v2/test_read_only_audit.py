"""Contract: Read-only tasks must not produce file changes.

CloseoutGate blocks any read-only task that reports files_changed."""

import pytest

from runtime_allocator.closeout_gate import closeout
from runtime_allocator.contracts import GateStatus, WriteScope


class TestReadOnlyAudit:
    def test_read_only_with_no_changes_allowed(self):
        result = closeout(
            task_type="finbot_fundamental",
            write_scope=WriteScope.READ_ONLY,
            files_changed=[],
            files_declared=[],
            evidence_spans=[],
        )
        assert result.status == GateStatus.ALLOWED

    def test_read_only_with_changes_blocked(self):
        result = closeout(
            task_type="finbot_fundamental",
            write_scope=WriteScope.READ_ONLY,
            files_changed=["report.md"],
            files_declared=[],
            evidence_spans=[],
        )
        assert result.status == GateStatus.BLOCKED
        assert "read_only_violation" in result.reason_codes

    def test_read_only_memory_query_allowed(self):
        result = closeout(
            task_type="memory_benchmark",
            write_scope=WriteScope.READ_ONLY,
            files_changed=[],
            files_declared=[],
            evidence_spans=["benchmark result: 0.92"],
        )
        assert result.status == GateStatus.ALLOWED
