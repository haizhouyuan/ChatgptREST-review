"""Contract: Tasks must run on the correct model quality lane.

PreflightGate blocks model lane mismatch between task requirement
and declared lane."""

import pytest

from runtime_allocator.preflight_gate import preflight
from runtime_allocator.contracts import GateStatus


class TestModelLaneSafety:
    def test_correct_lane_allowed(self):
        result = preflight(
            task_prompt="Analyze market fundamentals",
            agent_slug="finbot_agent",
            task_type="finbot_fundamental",
            model_lane="high",
        )
        assert result.status == GateStatus.ALLOWED

    def test_wrong_lane_blocked(self):
        result = preflight(
            task_prompt="Analyze market fundamentals",
            agent_slug="finbot_agent",
            task_type="finbot_fundamental",
            model_lane="cheap",
        )
        assert result.status == GateStatus.BLOCKED
        assert "model_lane_mismatch" in result.reason_codes
        assert "expected=high" in result.reason_codes
        assert "got=cheap" in result.reason_codes

    def test_no_lane_declared_allowed(self):
        result = preflight(
            task_prompt="Analyze market fundamentals",
            agent_slug="finbot_agent",
            task_type="finbot_fundamental",
            model_lane="",
        )
        assert result.status == GateStatus.ALLOWED
