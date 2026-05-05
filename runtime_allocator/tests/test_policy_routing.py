"""D1: Route/policy tests — table-driven for all task classes."""

from __future__ import annotations

import pytest

from runtime_allocator.allocator_mvp import (
    PrivacyTier,
    QualityTier,
    RouteRequest,
    allocate,
)
from runtime_allocator.policy_store import get_policy, load_routing_policy


class TestPolicyLoad:
    def test_all_policies_load(self):
        policies = load_routing_policy()
        assert len(policies) >= 30

    def test_policy_has_required_fields(self):
        policies = load_routing_policy()
        for task_class, p in policies.items():
            assert isinstance(p.primary, list)
            assert isinstance(p.fallback, list)
            assert p.terminal_if_unavailable in (
                "blocked", "human_review_required", "completed_no_trade"
            )


class TestPolicyRouting:
    """Table-driven routing tests per task class."""

    @pytest.mark.parametrize(
        "task_class,expected_primary",
        [
            ("finbot_trade_proposal", ["claudekimi"]),
            ("finbot_fundamental", ["claudekimi"]),
            ("finbot_market_analysis", ["minimax"]),
            ("hr_sensitive", ["ollama_gpu0"]),
            ("memory_indexing", ["ollama_gpu0"]),
            ("memory_comparison", ["claudekimi"]),
            ("strategic_plan", ["claudekimi"]),
            ("labebe_commerce_decision", ["claudekimi"]),
            ("dtc_copy", ["gemini_local"]),
            ("document_draft", ["gemini_local"]),
        ],
    )
    def test_primary_provider(self, task_class, expected_primary):
        policy = get_policy(task_class)
        assert policy is not None, f"No policy for {task_class}"
        assert policy.primary == expected_primary, (
            f"{task_class}: expected primary={expected_primary}, got {policy.primary}"
        )

    def test_unknown_task_class_blocked(self):
        req = RouteRequest(
            task_class="totally_unknown_task",
            privacy_tier_required=PrivacyTier.EXTERNAL_CLOUD,
            min_quality_tier=QualityTier.STANDARD,
            needs_tool_calling=False,
            needs_json=True,
            input_tokens_est=1000,
            output_tokens_est=500,
        )
        decision = allocate(req)
        assert decision.blocked
        assert decision.terminal_state == "blocked"
        assert "unknown_task_class" in decision.reason_codes

    def test_high_stakes_non_critical_triggers_review(self):
        req = RouteRequest(
            task_class="finbot_fundamental",
            privacy_tier_required=PrivacyTier.EXTERNAL_CLOUD,
            min_quality_tier=QualityTier.HIGH,
            needs_tool_calling=False,
            needs_json=True,
            input_tokens_est=2000,
            output_tokens_est=500,
            high_stakes=True,
        )
        decision = allocate(req)
        # fundamental allows claudekimi (critical) primary → no review needed
        # but if it fell back to minimax (high), review needed
        if decision.provider_id != "claudekimi":
            assert decision.requires_human_review


class TestPolicyPrivacyQualityGates:
    def test_hr_sensitive_blocks_external_providers(self):
        req = RouteRequest(
            task_class="hr_sensitive",
            privacy_tier_required=PrivacyTier.LOCAL,
            min_quality_tier=QualityTier.STANDARD,
            needs_tool_calling=False,
            needs_json=True,
            input_tokens_est=2000,
            output_tokens_est=500,
        )
        decision = allocate(req)
        # Should route to ollama_gpu0 or block, never minimax/openai
        assert decision.provider_id in ("ollama_gpu0", "blocked")

    def test_sensitive_task_no_external_override(self):
        policy = get_policy("hr_sensitive")
        assert policy.allowed_privacy == ["local", "private_cloud"]
