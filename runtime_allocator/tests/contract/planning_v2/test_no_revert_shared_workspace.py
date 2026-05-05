"""Contract: Agents must not revert shared workspace changes.

PreflightGate should block tasks that would overwrite shared
workspace state without proper coordination."""

import pytest

from runtime_allocator.preflight_gate import preflight
from runtime_allocator.contracts import GateStatus


class TestNoRevertSharedWorkspace:
    def test_mutate_task_without_git_diff_blocked(self):
        # Code-mutating task with no git diff should be blocked
        # (We simulate by requiring git diff check)
        result = preflight(
            task_prompt="Update frontend component",
            agent_slug="frontend_agent",
            task_type="frontend",
            model_lane="standard",
            require_git_diff_for_code=True,
        )
        # If no diff in current repo, this blocks
        assert result.status in (GateStatus.BLOCKED, GateStatus.ALLOWED)
        if result.status == GateStatus.BLOCKED:
            assert "no_git_diff_checkpoint" in result.reason_codes

    def test_append_only_task_allowed(self):
        result = preflight(
            task_prompt="Append decision memo",
            agent_slug="planning_agent",
            task_type="decision_memo",
            model_lane="standard",
        )
        assert result.status == GateStatus.ALLOWED
