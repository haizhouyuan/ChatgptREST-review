"""Tests for policy degradation logic in allocate().

Covers the three P3.5 fixes:
1. req.can_degrade=False blocks downgrade
2. policy.can_degrade=False blocks downgrade
3. Degrade does not mutate original request's min_quality_tier
"""

from __future__ import annotations

import pytest

from runtime_allocator.allocator_mvp import (
    RouteRequest,
    RouteDecision,
    allocate,
    Runtime,
    PrivacyTier,
    QualityTier,
)
from runtime_allocator.policy_store import PolicyEntry


@pytest.fixture
def cheap_runtime():
    return Runtime(
        provider_id="cheap_provider",
        model_name="cheap-model",
        endpoint="http://cheap",
        privacy_tier=PrivacyTier.EXTERNAL_CLOUD,
        quality_tier=QualityTier.CHEAP,
    )


@pytest.fixture
def standard_runtime():
    return Runtime(
        provider_id="standard_provider",
        model_name="std-model",
        endpoint="http://std",
        privacy_tier=PrivacyTier.EXTERNAL_CLOUD,
        quality_tier=QualityTier.STANDARD,
    )


@pytest.fixture
def policy_with_degrade():
    return PolicyEntry(
        task_class="test_task",
        primary=["standard_provider"],
        fallback=["cheap_provider"],
        can_degrade=True,
    )


@pytest.fixture
def policy_no_degrade():
    return PolicyEntry(
        task_class="test_task",
        primary=["standard_provider"],
        fallback=["cheap_provider"],
        can_degrade=False,
    )


class TestRequestCanDegrade:
    def test_can_degrade_false_blocks_downgrade(
        self, cheap_runtime, standard_runtime, policy_with_degrade
    ):
        """When req.can_degrade=False, downgrade should not happen even if policy allows."""
        req = RouteRequest(
            task_class="test_task",
            min_quality_tier=QualityTier.STANDARD,
            can_degrade=False,
        )
        # No standard runtime passes quota check (simulate by not providing any)
        # Wait - we need to simulate "no standard available". We can do this by
        # providing only the cheap runtime, or by using a ledger that blocks standard.
        # Simpler: provide both but set standard as disabled / not matching.
        # Actually, standard_runtime has quality=STANDARD which matches req.
        # Let's provide only cheap so standard is missing from candidates.
        decision = allocate(
            req,
            runtimes=[cheap_runtime],
            policy=policy_with_degrade,
        )
        assert decision.blocked is True
        assert "no_available_runtime" in decision.reason_codes[0]

    def test_can_degrade_true_allows_downgrade(
        self, cheap_runtime, standard_runtime, policy_with_degrade
    ):
        """When req.can_degrade=True, downgrade can happen."""
        req = RouteRequest(
            task_class="test_task",
            min_quality_tier=QualityTier.STANDARD,
            can_degrade=True,
        )
        decision = allocate(
            req,
            runtimes=[cheap_runtime],
            policy=policy_with_degrade,
        )
        assert decision.blocked is False
        assert decision.provider_id == "cheap_provider"


class TestPolicyCanDegrade:
    def test_policy_can_degrade_false_blocks_downgrade(
        self, cheap_runtime, standard_runtime, policy_no_degrade
    ):
        """When policy.can_degrade=False, downgrade should not happen."""
        req = RouteRequest(
            task_class="test_task",
            min_quality_tier=QualityTier.STANDARD,
            can_degrade=True,
        )
        decision = allocate(
            req,
            runtimes=[cheap_runtime],
            policy=policy_no_degrade,
        )
        assert decision.blocked is True


class TestDegradeDoesNotMutateRequest:
    def test_min_quality_tier_unchanged(
        self, cheap_runtime, standard_runtime, policy_with_degrade
    ):
        """allocate() should not mutate req.min_quality_tier."""
        req = RouteRequest(
            task_class="test_task",
            min_quality_tier=QualityTier.STANDARD,
            can_degrade=True,
        )
        original_tier = req.min_quality_tier
        allocate(
            req,
            runtimes=[cheap_runtime],
            policy=policy_with_degrade,
        )
        assert req.min_quality_tier == original_tier
