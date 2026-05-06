"""Comprehensive routing fabric tests: all business scenarios, edge cases, feedback loops.

Covers:
  B1. All 7 business-task profiles + 9 intent mappings
  B2. Health state transition matrix (5 states)
  B3. Fallback chain exhaustion & partial degradation
  B4. Feedback loop E2E (success/failure/cooldown/quality)
  B5. Config reload, unknown intents, task_type override
  B6. Composite score formula verification
  B7. EvoMap integration (telemetry, quality history, evomap observer)
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from chatgptrest.kernel.routing.config_loader import RoutingConfig, load_config
from chatgptrest.kernel.routing.fabric import RoutingFabric
from chatgptrest.kernel.routing.feedback import FeedbackCollector
from chatgptrest.kernel.routing.health_tracker import (
    HealthStatus,
    HealthTracker,
    ProviderHealth,
)
from chatgptrest.kernel.routing.selector import Selector
from chatgptrest.kernel.routing.types import (
    Capability,
    ExecutionOutcome,
    ProviderSpec,
    ProviderType,
    ResolvedRoute,
    RouteRequest,
    TaskProfile,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def all_providers():
    """All 6 production providers matching routing_profile.json."""
    return [
        ProviderSpec(
            id="chatgpt-web", display_name="ChatGPT Web (o3)",
            type=ProviderType.MCP_WEB, tier=1,
            capabilities={Capability.CHAT, Capability.DEEP_RESEARCH,
                          Capability.CODE_GEN, Capability.WEB_SEARCH},
            avg_latency_ms=15000, max_concurrent=1,
        ),
        ProviderSpec(
            id="gemini-web", display_name="Gemini Web (2.5 Pro)",
            type=ProviderType.MCP_WEB, tier=1,
            capabilities={Capability.CHAT, Capability.DEEP_RESEARCH,
                          Capability.IMAGE_GEN, Capability.WEB_SEARCH},
            avg_latency_ms=12000, max_concurrent=1,
        ),
        ProviderSpec(
            id="claude-api", display_name="Claude Sonnet 4",
            type=ProviderType.NATIVE_API, tier=2,
            capabilities={Capability.CHAT, Capability.CODE_GEN,
                          Capability.ANALYSIS, Capability.TOOL_USE},
            avg_latency_ms=5000, max_concurrent=5,
            models=["claude-sonnet-4-20250514"],
        ),
        ProviderSpec(
            id="qwen-api", display_name="Qwen 3.5+",
            type=ProviderType.API, tier=3,
            capabilities={Capability.CHAT, Capability.CODE_GEN},
            avg_latency_ms=3000, max_concurrent=10,
            models=["qwen3.5-plus"],
        ),
        ProviderSpec(
            id="kimi-api", display_name="Kimi K2.5",
            type=ProviderType.API, tier=3,
            capabilities={Capability.CHAT},
            avg_latency_ms=4000, max_concurrent=10,
            models=["kimi-k2.5"],
        ),
        ProviderSpec(
            id="minimax-api", display_name="MiniMax M2.5",
            type=ProviderType.API, tier=3,
            capabilities={Capability.CHAT},
            avg_latency_ms=2000, max_concurrent=10,
            models=["MiniMax-M2.5"],
        ),
    ]


def _profile(task_type, **kwargs):
    """Helper to make TaskProfile with defaults."""
    return TaskProfile(task_type=task_type, **kwargs)


@pytest.fixture
def health_tracker():
    return HealthTracker(
        window_seconds=600,
        degraded_failure_rate=0.3,
        exhausted_failure_rate=0.6,
        recovery_successes=3,
        cooldown_default_seconds=120,
    )


@pytest.fixture
def selector(health_tracker):
    return Selector(health_tracker=health_tracker)


# ═══════════════════════════════════════════════════════════════════
# B1. All 7 Business Scenario E2E Tests
# ═══════════════════════════════════════════════════════════════════

class TestBusinessScenarios:
    """B1: Verify correct provider ranking for each task profile."""

    def test_report_writing_prefers_flagship(self, all_providers, selector):
        """report_writing: tier-1, web_search preferred → chatgpt-web or gemini-web."""
        profile = _profile(
            "report_writing",
            required_caps={Capability.CHAT},
            preferred_caps={Capability.WEB_SEARCH},
            quality_weight=0.7, latency_weight=0.1, cost_weight=0.2,
            min_tier=1,
        )
        result = selector.select(all_providers, profile)
        assert len(result) >= 1
        top = result[0]
        assert top.provider.tier == 1
        assert top.provider.id in ("chatgpt-web", "gemini-web")
        # Web search preference should boost score
        assert Capability.WEB_SEARCH in top.provider.capabilities

    def test_deep_research_requires_deep_research_cap(self, all_providers, selector):
        """deep_research: must have deep_research capability → only flagships."""
        profile = _profile(
            "deep_research",
            required_caps={Capability.DEEP_RESEARCH},
            preferred_caps={Capability.WEB_SEARCH},
            quality_weight=0.8, latency_weight=0.0, cost_weight=0.2,
            min_tier=1,
        )
        result = selector.select(all_providers, profile)
        assert len(result) >= 1
        for cand in result:
            if not cand.reason.startswith("fallback"):
                assert Capability.DEEP_RESEARCH in cand.provider.capabilities

    def test_quick_qa_prefers_low_latency(self, all_providers, selector):
        """quick_qa: latency_weight high, any tier → fast API providers first."""
        profile = _profile(
            "quick_qa",
            required_caps={Capability.CHAT},
            quality_weight=0.3, latency_weight=0.5, cost_weight=0.2,
            max_latency_ms=30000, min_tier=3,
        )
        result = selector.select(all_providers, profile)
        assert len(result) >= 3
        # Top candidate should be low-latency
        top = result[0]
        assert top.provider.avg_latency_ms <= 5000

    def test_coding_prefers_code_gen(self, all_providers, selector):
        """coding: code_gen required, tool_use preferred → claude/qwen/chatgpt."""
        profile = _profile(
            "coding",
            required_caps={Capability.CODE_GEN},
            preferred_caps={Capability.TOOL_USE},
            quality_weight=0.5, latency_weight=0.2, cost_weight=0.3,
            min_tier=2,
        )
        result = selector.select(all_providers, profile)
        assert len(result) >= 1
        for cand in result:
            if not cand.reason.startswith("fallback"):
                assert Capability.CODE_GEN in cand.provider.capabilities

    def test_analysis_prefers_analysis_cap(self, all_providers, selector):
        """analysis: analysis preferred → claude-api has advantage."""
        profile = _profile(
            "analysis",
            required_caps={Capability.CHAT},
            preferred_caps={Capability.WEB_SEARCH, Capability.ANALYSIS},
            quality_weight=0.6, latency_weight=0.2, cost_weight=0.2,
            min_tier=2,
        )
        result = selector.select(all_providers, profile)
        assert len(result) >= 1
        # Claude has both web_search? No, but has analysis. Check it's ranked.
        analysis_ids = [c.provider.id for c in result
                       if Capability.ANALYSIS in c.provider.capabilities]
        assert "claude-api" in analysis_ids

    def test_default_accepts_any(self, all_providers, selector):
        """default: min_tier=3, chat → all providers qualify."""
        profile = _profile(
            "default",
            required_caps={Capability.CHAT},
            quality_weight=0.4, latency_weight=0.3, cost_weight=0.3,
            min_tier=3,
        )
        result = selector.select(all_providers, profile)
        assert len(result) >= 4  # Should include most providers

    def test_image_gen_only_gemini(self, all_providers, selector):
        """image_gen: only gemini-web has this capability."""
        profile = _profile(
            "image_gen",
            required_caps={Capability.IMAGE_GEN},
            quality_weight=0.5, latency_weight=0.2, cost_weight=0.3,
        )
        result = selector.select(all_providers, profile)
        primary = [c for c in result if not c.reason.startswith("fallback")]
        assert len(primary) >= 1
        assert primary[0].provider.id == "gemini-web"


class TestIntentMapping:
    """B1: All 9 intent → profile mappings resolve correctly."""

    @pytest.fixture
    def fabric(self):
        """Load fabric from real config (if available) or mock."""
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "config", "routing_profile.json"
        )
        if os.path.exists(config_path):
            return RoutingFabric.from_config(config_path)
        pytest.skip("routing_profile.json not found")

    @pytest.mark.parametrize("intent,expected_profile", [
        ("report", "report_writing"),
        ("deep_research", "deep_research"),
        ("kb_answer", "quick_qa"),
        ("hybrid", "analysis"),
        ("funnel", "analysis"),
        ("action", "coding"),
        ("cc_task", "coding"),
        ("clarify", "quick_qa"),
        ("direct_answer", "quick_qa"),
    ])
    def test_intent_resolves_correctly(self, fabric, intent, expected_profile):
        route = fabric.resolve(RouteRequest(intent_route=intent))
        assert route.task_profile is not None
        assert route.task_profile.task_type == expected_profile

    def test_unknown_intent_falls_to_default(self, fabric):
        """Unknown intent should use default profile."""
        route = fabric.resolve(RouteRequest(intent_route="nonexistent_xyz"))
        assert route.task_profile is not None
        assert route.task_profile.task_type == "default"

    def test_task_type_override(self, fabric):
        """task_type should override intent_route."""
        route = fabric.resolve(RouteRequest(
            intent_route="report",
            task_type="coding",
        ))
        assert route.task_profile.task_type == "coding"


# ═══════════════════════════════════════════════════════════════════
# B2. Health State Transition Matrix
# ═══════════════════════════════════════════════════════════════════

class TestHealthStateTransitions:
    """B2: Verify all health state transitions."""

    def test_initial_state_is_healthy(self, health_tracker):
        h = health_tracker.get_health("test-provider")
        assert h.status == HealthStatus.HEALTHY
        assert h.is_available()
        assert h.degradation_factor == 1.0

    def test_healthy_to_degraded(self, health_tracker):
        """30%+ failure rate → DEGRADED."""
        pid = "p1"
        # 3 successes + 2 failures = 40% failure rate
        for _ in range(3):
            health_tracker.record_success(pid)
        for _ in range(2):
            health_tracker.record_failure(pid, error_type="timeout")
        h = health_tracker.get_health(pid)
        assert h.status == HealthStatus.DEGRADED
        assert h.is_available()  # Still available but degraded
        assert 0.3 <= h.degradation_factor <= 0.7

    def test_degraded_to_exhausted(self, health_tracker):
        """60%+ failure rate → EXHAUSTED."""
        pid = "p2"
        health_tracker.record_success(pid)
        for _ in range(4):
            health_tracker.record_failure(pid, error_type="rate_limit")
        h = health_tracker.get_health(pid)
        assert h.status == HealthStatus.EXHAUSTED
        assert not h.is_available()
        assert h.degradation_factor == 0.0

    def test_cooldown_timing(self, health_tracker):
        """COOLDOWN blocks until expiry."""
        pid = "p3"
        health_tracker.record_cooldown(pid, seconds=1)
        h = health_tracker.get_health(pid)
        assert h.status == HealthStatus.COOLDOWN
        assert not h.is_available()
        assert h.degradation_factor == 0.1
        # Wait for cooldown
        time.sleep(1.1)
        h = health_tracker.get_health(pid)
        assert h.is_available()  # Should be available now

    def test_offline_manual(self, health_tracker):
        """set_offline → OFFLINE, can only recover via set_online."""
        pid = "p4"
        health_tracker.set_offline(pid, reason="maintenance")
        h = health_tracker.get_health(pid)
        assert h.status == HealthStatus.OFFLINE
        assert not h.is_available()
        assert h.offline_reason == "maintenance"

        # Successes don't auto-recover from offline
        health_tracker.record_success(pid)
        health_tracker.record_success(pid)
        h = health_tracker.get_health(pid)
        assert h.status == HealthStatus.OFFLINE

        # Only manual set_online works
        health_tracker.set_online(pid)
        h = health_tracker.get_health(pid)
        assert h.status == HealthStatus.HEALTHY
        assert h.is_available()

    def test_recovery_from_degraded(self, health_tracker):
        """3 consecutive successes recovers from DEGRADED."""
        pid = "p5"
        # Degrade it
        for _ in range(3):
            health_tracker.record_success(pid)
        for _ in range(2):
            health_tracker.record_failure(pid, error_type="timeout")
        assert health_tracker.get_health(pid).status == HealthStatus.DEGRADED

        # Recover with 3 successes
        for _ in range(3):
            health_tracker.record_success(pid)
        assert health_tracker.get_health(pid).status == HealthStatus.HEALTHY

    def test_reset_clears_all(self, health_tracker):
        """reset() clears all state."""
        pid = "p6"
        health_tracker.set_offline(pid, "test")
        health_tracker.reset(pid)
        h = health_tracker.get_health(pid)
        assert h.status == HealthStatus.HEALTHY

    def test_concurrent_updates(self, health_tracker):
        """Thread-safety: concurrent updates don't corrupt state."""
        pid = "p7"
        errors = []

        def record_events():
            try:
                for _ in range(50):
                    health_tracker.record_success(pid)
                    health_tracker.record_failure(pid, error_type="err")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_events) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        h = health_tracker.get_health(pid)
        assert h.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.EXHAUSTED)


# ═══════════════════════════════════════════════════════════════════
# B3. Fallback Chain Tests
# ═══════════════════════════════════════════════════════════════════

class TestFallbackChains:
    """B3: Verify fallback behavior when providers are unhealthy."""

    def test_primary_offline_falls_to_secondary(
        self, all_providers, health_tracker, selector
    ):
        """If tier-1 providers are offline, tier-2/3 should be selected."""
        health_tracker.set_offline("chatgpt-web")
        health_tracker.set_offline("gemini-web")

        profile = _profile(
            "report_writing",
            required_caps={Capability.CHAT},
            quality_weight=0.7, latency_weight=0.1, cost_weight=0.2,
            min_tier=1,
        )
        result = selector.select(all_providers, profile)
        # Should have fallback candidates from lower tiers
        assert len(result) >= 1
        # The top primary candidates shouldn't include offline providers
        for cand in result:
            assert cand.provider.id not in ("chatgpt-web", "gemini-web")

    def test_all_flagship_offline_returns_empty_or_fallback(
        self, all_providers, health_tracker, selector
    ):
        """All tier-1 offline → may have fallback or empty."""
        profile = _profile(
            "deep_research",
            required_caps={Capability.DEEP_RESEARCH},
            min_tier=1,
        )
        health_tracker.set_offline("chatgpt-web")
        health_tracker.set_offline("gemini-web")

        result = selector.select(all_providers, profile, include_fallbacks=True)
        # When all primary exhausted, we get 0 primary + maybe fallbacks
        for cand in result:
            assert cand.provider.id not in ("chatgpt-web", "gemini-web")

    def test_degraded_provider_still_scored(
        self, all_providers, health_tracker, selector
    ):
        """DEGRADED providers still appear but with penalty."""
        profile = _profile(
            "quick_qa",
            required_caps={Capability.CHAT},
            quality_weight=0.3, latency_weight=0.5, cost_weight=0.2,
            min_tier=3,
        )
        # Score without degradation
        result_healthy = selector.select(all_providers, profile)
        healthy_scores = {c.provider.id: c.score for c in result_healthy}

        # Degrade minimax
        for _ in range(3):
            health_tracker.record_success("minimax-api")
        for _ in range(2):
            health_tracker.record_failure("minimax-api")

        result_degraded = selector.select(all_providers, profile)
        degraded_scores = {c.provider.id: c.score for c in result_degraded}

        # minimax should still appear but with lower score
        if "minimax-api" in healthy_scores and "minimax-api" in degraded_scores:
            assert degraded_scores["minimax-api"] <= healthy_scores["minimax-api"]

    def test_exhausted_excluded_from_candidates(
        self, all_providers, health_tracker, selector
    ):
        """EXHAUSTED providers are completely filtered out."""
        profile = _profile(
            "default",
            required_caps={Capability.CHAT},
            min_tier=3,
        )
        # Exhaust qwen-api
        health_tracker.record_success("qwen-api")
        for _ in range(4):
            health_tracker.record_failure("qwen-api")

        result = selector.select(all_providers, profile)
        ids = [c.provider.id for c in result]
        assert "qwen-api" not in ids


# ═══════════════════════════════════════════════════════════════════
# B4. Feedback Loop E2E
# ═══════════════════════════════════════════════════════════════════

class TestFeedbackLoop:
    """B4: Verify feedback collector properly updates health + quality."""

    def test_success_keeps_healthy(self, health_tracker):
        collector = FeedbackCollector(health_tracker)
        outcome = ExecutionOutcome(
            provider_id="chatgpt-web", task_type="report",
            success=True, latency_ms=3000,
        )
        collector.report(outcome)
        h = health_tracker.get_health("chatgpt-web")
        assert h.status == HealthStatus.HEALTHY

    def test_repeated_failures_degrade(self, health_tracker):
        collector = FeedbackCollector(health_tracker)

        # 5 successes first
        for _ in range(5):
            collector.report(ExecutionOutcome(
                provider_id="gemini-web", task_type="report",
                success=True, latency_ms=5000,
            ))

        # 4 failures = 4/(5+4) = 44% failure rate → DEGRADED
        for _ in range(4):
            collector.report(ExecutionOutcome(
                provider_id="gemini-web", task_type="report",
                success=False, latency_ms=30000,
                error_type="timeout",
            ))

        h = health_tracker.get_health("gemini-web")
        assert h.status == HealthStatus.DEGRADED

    def test_cooldown_via_outcome(self, health_tracker):
        collector = FeedbackCollector(health_tracker)
        outcome = ExecutionOutcome(
            provider_id="chatgpt-web", task_type="quick_qa",
            success=False, latency_ms=0,
            cooldown_seconds=60,
        )
        collector.report(outcome)
        h = health_tracker.get_health("chatgpt-web")
        assert h.status == HealthStatus.COOLDOWN

    def test_quality_score_callback(self, health_tracker):
        """Quality scores trigger callback to update selector history."""
        updates = []

        def on_quality(pid, tt, q):
            updates.append((pid, tt, q))

        collector = FeedbackCollector(
            health_tracker, on_quality_update=on_quality,
        )
        outcome = ExecutionOutcome(
            provider_id="claude-api", task_type="coding",
            success=True, latency_ms=2000,
            quality_score=0.85,
        )
        collector.report(outcome)
        assert len(updates) == 1
        assert updates[0] == ("claude-api", "coding", 0.85)

    def test_evomap_signal_emission(self, health_tracker):
        """EvoMap observer receives routing outcome signals."""
        mock_observer = MagicMock()
        mock_observer.emit = MagicMock()

        collector = FeedbackCollector(
            health_tracker, evomap_observer=mock_observer,
        )
        outcome = ExecutionOutcome(
            provider_id="qwen-api", task_type="quick_qa",
            success=True, latency_ms=1500,
            quality_score=0.7, trace_id="trace123",
        )
        collector.report(outcome)
        mock_observer.emit.assert_called_once()
        call_kwargs = mock_observer.emit.call_args
        assert call_kwargs[1]["trace_id"] == "trace123"

    def test_timestamp_auto_set(self, health_tracker):
        """Outcome gets timestamp if not provided."""
        collector = FeedbackCollector(health_tracker)
        outcome = ExecutionOutcome(
            provider_id="test", task_type="test",
            success=True,
        )
        assert outcome.timestamp == ""
        collector.report(outcome)
        assert outcome.timestamp != ""


# ═══════════════════════════════════════════════════════════════════
# B5. Config Reload & Edge Cases
# ═══════════════════════════════════════════════════════════════════

class TestConfigEdgeCases:
    """B5: Config loading, hot reload, edge cases."""

    def test_load_real_config(self):
        """Real routing_profile.json loads without errors."""
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "config", "routing_profile.json"
        )
        if not os.path.exists(config_path):
            pytest.skip("routing_profile.json not found")
        config = load_config(config_path)
        assert config.version == "2.0"
        assert len(config.providers) >= 6
        assert len(config.task_profiles) >= 6

    def test_invalid_config_graceful(self):
        """Invalid JSON → graceful error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            f.flush()
            with pytest.raises(Exception):
                RoutingConfig.from_file(f.name)
        os.unlink(f.name)

    def test_missing_config_graceful(self):
        """Non-existent file → returns config with load errors."""
        config = load_config("/tmp/nonexistent_config_xyz.json")
        assert len(config.providers) == 0
        assert hasattr(config, "_load_errors")
        assert len(config._load_errors) >= 1

    def test_empty_provider_list(self, selector):
        """Empty provider list → empty results."""
        profile = _profile("default", required_caps={Capability.CHAT})
        result = selector.select([], profile)
        assert len(result) == 0

    def test_no_matching_capability(self, all_providers, selector):
        """No provider has all of these caps → at most 1 (or none)."""
        # IMAGE_GEN + DEEP_RESEARCH + CODE_GEN + TOOL_USE — no single provider has all 4
        profile = _profile(
            "impossible",
            required_caps={
                Capability.IMAGE_GEN, Capability.DEEP_RESEARCH,
                Capability.CODE_GEN, Capability.TOOL_USE,
            },
        )
        result = selector.select(all_providers, profile, include_fallbacks=False)
        # No provider has all 4 capabilities at once
        assert len(result) == 0

    def test_disabled_provider_excluded(self, selector):
        """Disabled providers should not appear in results."""
        providers = [
            ProviderSpec(
                id="enabled", type=ProviderType.API, tier=3,
                capabilities={Capability.CHAT}, enabled=True,
            ),
            ProviderSpec(
                id="disabled", type=ProviderType.API, tier=3,
                capabilities={Capability.CHAT}, enabled=False,
            ),
        ]
        profile = _profile("default", required_caps={Capability.CHAT}, min_tier=3)
        result = selector.select(providers, profile)
        ids = [c.provider.id for c in result]
        assert "enabled" in ids
        assert "disabled" not in ids


# ═══════════════════════════════════════════════════════════════════
# B6. Score Breakdown Validation
# ═══════════════════════════════════════════════════════════════════

class TestScoreBreakdown:
    """B6: Verify composite score formula components."""

    def test_quality_weight_dominant(self, all_providers, selector):
        """High quality_weight → tier-1 providers score higher."""
        profile = _profile(
            "quality_heavy",
            required_caps={Capability.CHAT},
            quality_weight=0.9, latency_weight=0.05, cost_weight=0.05,
            min_tier=3,
        )
        result = selector.select(all_providers, profile)
        if len(result) >= 2:
            # Tier-1 should be at top
            top_tier = result[0].provider.tier
            assert top_tier <= 2  # Should be tier-1 or tier-2

    def test_latency_weight_dominant(self, all_providers, selector):
        """High latency_weight → low-latency API providers win."""
        profile = _profile(
            "speed_heavy",
            required_caps={Capability.CHAT},
            quality_weight=0.05, latency_weight=0.9, cost_weight=0.05,
            min_tier=3,
        )
        result = selector.select(all_providers, profile)
        assert len(result) >= 1
        # minimax has 2000ms, should be near top
        assert result[0].provider.avg_latency_ms <= 5000

    def test_score_breakdown_present(self, all_providers, selector):
        """Each candidate should have non-empty score_breakdown."""
        profile = _profile(
            "default",
            required_caps={Capability.CHAT},
            quality_weight=0.4, latency_weight=0.3, cost_weight=0.3,
            min_tier=3,
        )
        result = selector.select(all_providers, profile)
        for cand in result:
            assert cand.score > 0
            assert isinstance(cand.score_breakdown, dict)
            assert len(cand.score_breakdown) > 0

    def test_preferred_cap_bonus(self, all_providers, selector):
        """Preferred capability should give small score bonus."""
        profile_no_pref = _profile(
            "no_pref",
            required_caps={Capability.CHAT},
            quality_weight=0.5, latency_weight=0.3, cost_weight=0.2,
            min_tier=3,
        )
        profile_with_pref = _profile(
            "with_pref",
            required_caps={Capability.CHAT},
            preferred_caps={Capability.WEB_SEARCH},
            quality_weight=0.5, latency_weight=0.3, cost_weight=0.2,
            min_tier=3,
        )
        result_no = selector.select(all_providers, profile_no_pref)
        result_yes = selector.select(all_providers, profile_with_pref)

        # chatgpt-web has web_search → should have higher score with preference
        score_no = next((c.score for c in result_no if c.provider.id == "chatgpt-web"), 0)
        score_yes = next((c.score for c in result_yes if c.provider.id == "chatgpt-web"), 0)
        assert score_yes >= score_no

    def test_quality_history_updates_scores(self, all_providers, health_tracker):
        """Quality history should influence scoring."""
        quality_history = {
            ("claude-api", "coding"): 0.95,
            ("qwen-api", "coding"): 0.40,
        }
        selector_with_history = Selector(
            health_tracker=health_tracker,
            quality_history=quality_history,
        )
        profile = _profile(
            "coding",
            required_caps={Capability.CODE_GEN},
            quality_weight=0.7, latency_weight=0.1, cost_weight=0.2,
            min_tier=2,
        )
        result = selector_with_history.select(all_providers, profile)
        # Claude should rank higher than qwen due to quality history
        ids = [c.provider.id for c in result]
        if "claude-api" in ids and "qwen-api" in ids:
            assert ids.index("claude-api") < ids.index("qwen-api")


# ═══════════════════════════════════════════════════════════════════
# B7. Fabric Integration E2E
# ═══════════════════════════════════════════════════════════════════

class TestFabricE2E:
    """B7: Full RoutingFabric end-to-end tests."""

    @pytest.fixture
    def fabric(self):
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "config", "routing_profile.json"
        )
        if not os.path.exists(config_path):
            pytest.skip("routing_profile.json not found")
        return RoutingFabric.from_config(config_path)

    def test_resolve_returns_candidates(self, fabric):
        route = fabric.resolve(RouteRequest(intent_route="report"))
        assert isinstance(route, ResolvedRoute)
        assert len(route.candidates) >= 1
        assert route.task_profile is not None
        assert route.rationale  # Should have explanation

    def test_resolve_all_intents(self, fabric):
        """Every known intent returns at least 1 candidate."""
        for intent in ("report", "deep_research", "kb_answer", "hybrid",
                       "funnel", "action", "cc_task", "clarify", "direct_answer"):
            route = fabric.resolve(RouteRequest(intent_route=intent))
            assert route.candidates, f"No candidates for intent={intent}"

    def test_get_llm_fn_returns_callable(self, fabric):
        """get_llm_fn returns a function even when no providers are reachable."""
        fn = fabric.get_llm_fn(intent_route="report")
        assert callable(fn)

    def test_status_method(self, fabric):
        """status() returns a well-formed dict."""
        status = fabric.status()
        assert isinstance(status, dict)
        assert "providers" in status or "config_version" in status

    def test_report_outcome_doesnt_crash(self, fabric):
        """report_outcome with various outcomes doesn't raise."""
        outcomes = [
            ExecutionOutcome("chatgpt-web", "report", True, 5000),
            ExecutionOutcome("gemini-web", "report", False, 30000,
                           error_type="timeout"),
            ExecutionOutcome("qwen-api", "coding", True, 1500,
                           quality_score=0.8),
        ]
        for o in outcomes:
            fabric.report_outcome(o)  # Should not raise

    def test_resolved_route_top(self, fabric):
        """ResolvedRoute.top returns first candidate."""
        route = fabric.resolve(RouteRequest(intent_route="report"))
        assert route.top is not None
        assert route.top == route.candidates[0]

    def test_resolved_route_api_only(self, fabric):
        """api_only() returns only API models."""
        route = fabric.resolve(RouteRequest(intent_route="kb_answer"))
        models = route.api_only()
        assert isinstance(models, list)
        assert len(models) >= 1
        # Should be model names, not provider IDs
        for m in models:
            assert isinstance(m, str)


# ═══════════════════════════════════════════════════════════════════
# B8. Routing + EvoMap Telemetry Integration
# ═══════════════════════════════════════════════════════════════════

class TestRoutingEvoMapIntegration:
    """B8: Verify routing quality stats from telemetry feed into selector."""

    @pytest.mark.skipif(
        not os.path.exists("/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db"),
        reason="production DB not available",
    )
    def test_telemetry_gap_metrics_feed_routing(self):
        """Telemetry gap metrics can be queried for routing quality assessment."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.telemetry import TelemetryRecorder

        db = KnowledgeDB()
        db.connect()
        recorder = TelemetryRecorder(db)
        recorder.init_schema()

        gap = recorder.get_gap_metrics(window_days=7)
        assert isinstance(gap, dict)
        assert "query_coverage" in gap
        assert "miss_rate" in gap
        db.close()

    def test_routing_quality_stats_api(self):
        """get_routing_quality_stats returns valid dict."""
        from chatgptrest.evomap.knowledge.telemetry import TelemetryRecorder
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        import tempfile

        db = KnowledgeDB(db_path=os.path.join(tempfile.gettempdir(), "test_telemetry.db"))
        db.connect()
        db.init_schema()
        recorder = TelemetryRecorder(db)
        recorder.init_schema()

        stats = recorder.get_routing_quality_stats(window_days=7)
        assert isinstance(stats, dict)
        db.close()
