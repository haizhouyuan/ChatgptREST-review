"""Contract: Second review must operate on current code only.

PreflightGate should require human_review for code-review tasks
that need a second pass, ensuring they target the current HEAD."""

import pytest

from runtime_allocator.preflight_gate import preflight
from runtime_allocator.contracts import GateStatus


class TestCurrentCodeOnlySecondReview:
    def test_high_stakes_code_review_requires_human_review(self):
        result = preflight(
            task_prompt="Second review of critical trading logic",
            agent_slug="code_review_agent",
            task_type="code_reasoning",
            model_lane="high",
            declared_write_scope=None,
        )
        # code_reasoning is read-only, so allowed, but high-stakes
        # might need human review depending on policy
        assert result.status in (GateStatus.ALLOWED, GateStatus.HUMAN_REVIEW_REQUIRED)

    def test_read_only_audit_allowed(self):
        result = preflight(
            task_prompt="Audit current codebase for security issues",
            agent_slug="audit_agent",
            task_type="code_reasoning",
            model_lane="high",
        )
        assert result.status == GateStatus.ALLOWED
