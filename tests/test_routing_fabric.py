"""Tests for the RoutingFabric (Phase 1+2).

Covers:
  - Config loading (v2.0 schema)
  - ProviderRegistry queries
  - HealthTracker state transitions
  - Selector composite scoring
  - RoutingFabric.resolve() end-to-end
  - FeedbackCollector flow
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from chatgptrest.kernel.routing.types import (
    Capability,
    ExecutionOutcome,
    ProviderSpec,
    ProviderType,
    ResolvedRoute,
    RouteRequest,
    TaskProfile,
)
from chatgptrest.kernel.routing.config_loader import load_config, RoutingConfig
from chatgptrest.kernel.routing.provider_registry import ProviderRegistry
from chatgptrest.kernel.routing.health_tracker import HealthTracker, HealthStatus
from chatgptrest.kernel.routing.selector import Selector
from chatgptrest.kernel.routing.feedback import FeedbackCollector
from chatgptrest.kernel.routing.fabric import RoutingFabric


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def sample_providers():
    return {
        "chatgpt-web": ProviderSpec(
            id="chatgpt-web", type=ProviderType.MCP_WEB, tier=1,
            capabilities={Capability.CHAT, Capability.DEEP_RESEARCH, Capability.WEB_SEARCH},
            avg_latency_ms=15000, max_concurrent=1,
        ),
        "gemini-web": ProviderSpec(
            id="gemini-web", type=ProviderType.MCP_WEB, tier=1,
            capabilities={Capability.CHAT, Capability.DEEP_RESEARCH, Capability.IMAGE_GEN},
            avg_latency_ms=12000, max_concurrent=1,
        ),
        "qwen-api": ProviderSpec(
            id="qwen-api", type=ProviderType.API, tier=3,
            capabilities={Capability.CHAT, Capability.CODE_GEN},
            avg_latency_ms=3000, max_concurrent=10,
            models=["qwen3.5-plus", "qwen3-coder-plus"],
        ),
        "claude-api": ProviderSpec(
            id="claude-api", type=ProviderType.NATIVE_API, tier=2,
            capabilities={Capability.CHAT, Capability.CODE_GEN, Capability.TOOL_USE},
            avg_latency_ms=5000, max_concurrent=5,
            models=["claude-sonnet-4-20250514"],
        ),
    }


@pytest.fixture
def report_profile():
    return TaskProfile(
        task_type="report_writing",
        required_caps={Capability.CHAT},
        preferred_caps={Capability.WEB_SEARCH},
        quality_weight=0.7, latency_weight=0.1, cost_weight=0.2,
        min_tier=1,
    )


@pytest.fixture
def coding_profile():
    return TaskProfile(
        task_type="coding",
        required_caps={Capability.CODE_GEN},
        preferred_caps={Capability.TOOL_USE},
        quality_weight=0.5, latency_weight=0.2, cost_weight=0.3,
        min_tier=2,
    )


@pytest.fixture
def quick_qa_profile():
    return TaskProfile(
        task_type="quick_qa",
        required_caps={Capability.CHAT},
        quality_weight=0.3, latency_weight=0.5, cost_weight=0.2,
        max_latency_ms=30000, min_tier=3,
    )


# ── Config Loading ───────────────────────────────────────────────

class TestConfigLoading:

    def test_load_real_config(self):
        cfg = load_config()
        assert cfg.is_valid, f"Config errors: {cfg._load_errors}"
        assert len(cfg.providers) >= 6
        assert len(cfg.task_profiles) >= 6
        assert "report" in cfg.intent_mapping
        assert "deep_research" in cfg.intent_mapping

    def test_load_from_dict(self):
        cfg = load_config()
        chatgpt = cfg.providers.get("chatgpt-web")
        assert chatgpt is not None
        assert chatgpt.type == ProviderType.MCP_WEB
        assert chatgpt.tier == 1
        assert Capability.CHAT in chatgpt.capabilities
        assert Capability.DEEP_RESEARCH in chatgpt.capabilities

    def test_task_profile_parsed(self):
        cfg = load_config()
        rp = cfg.task_profiles.get("report_writing")
        assert rp is not None
        assert rp.quality_weight == 0.7
        assert rp.min_tier == 1
        assert Capability.CHAT in rp.required_caps

    def test_intent_mapping(self):
        cfg = load_config()
        assert cfg.intent_mapping["report"] == "report_writing"
        assert cfg.intent_mapping["deep_research"] == "deep_research"
        assert cfg.intent_mapping["action"] == "coding"

    def test_missing_file(self):
        cfg = load_config("/nonexistent/path.json")
        assert not cfg.is_valid

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write("{invalid json")
            f.flush()
            cfg = load_config(f.name)
            assert not cfg.is_valid


# ── Provider Registry ────────────────────────────────────────────

class TestProviderRegistry:

    def test_basic_operations(self, sample_providers):
        reg = ProviderRegistry(sample_providers)
        assert len(reg) == 4
        assert "chatgpt-web" in reg
        assert reg.get("chatgpt-web").tier == 1

    def test_with_capability(self, sample_providers):
        reg = ProviderRegistry(sample_providers)
        deep = reg.with_capability(Capability.DEEP_RESEARCH)
        assert len(deep) == 2
        ids = {p.id for p in deep}
        assert ids == {"chatgpt-web", "gemini-web"}

    def test_by_tier(self, sample_providers):
        reg = ProviderRegistry(sample_providers)
        tier1 = reg.by_tier(1)
        assert len(tier1) == 2
        tier2 = reg.by_tier(2)
        assert len(tier2) == 3  # tier 1 + tier 2

    def test_by_type(self, sample_providers):
        reg = ProviderRegistry(sample_providers)
        mcp = reg.by_type(ProviderType.MCP_WEB)
        assert len(mcp) == 2

    def test_disabled_excluded(self, sample_providers):
        sample_providers["qwen-api"].enabled = False
        reg = ProviderRegistry(sample_providers)
        assert len(reg.enabled()) == 3


# ── Health Tracker ───────────────────────────────────────────────

class TestHealthTracker:

    def test_default_healthy(self):
        ht = HealthTracker()
        h = ht.get_health("chatgpt-web")
        assert h.status == HealthStatus.HEALTHY
        assert h.is_available()

    def test_degradation(self):
        ht = HealthTracker(degraded_failure_rate=0.3, exhausted_failure_rate=0.6)
        # 4 calls, 2 failures = 50% rate → degraded (not exhausted)
        ht.record_success("gpt", latency_ms=100)
        ht.record_success("gpt", latency_ms=100)
        ht.record_failure("gpt", error_type="timeout")
        ht.record_failure("gpt", error_type="timeout")
        h = ht.get_health("gpt")
        assert h.failure_rate == 0.5
        assert h.status == HealthStatus.DEGRADED
        assert h.is_available()  # Degraded but still available
        assert h.degradation_factor < 1.0

    def test_exhaustion(self):
        ht = HealthTracker(exhausted_failure_rate=0.5)
        ht.record_failure("gpt", error_type="infra")
        ht.record_failure("gpt", error_type="infra")
        ht.record_failure("gpt", error_type="infra")
        h = ht.get_health("gpt")
        assert h.status == HealthStatus.EXHAUSTED
        assert not h.is_available()

    def test_cooldown(self):
        ht = HealthTracker()
        ht.record_cooldown("gpt", seconds=60)
        h = ht.get_health("gpt")
        assert h.status == HealthStatus.COOLDOWN
        assert not h.is_available()

    def test_offline(self):
        ht = HealthTracker()
        ht.set_offline("gpt", reason="CDP port down")
        h = ht.get_health("gpt")
        assert h.status == HealthStatus.OFFLINE
        assert not h.is_available()
        assert h.offline_reason == "CDP port down"

    def test_recovery(self):
        ht = HealthTracker(
            degraded_failure_rate=0.3,
            exhausted_failure_rate=0.7,  # Higher threshold so we stay in DEGRADED
            recovery_successes=2,
        )
        # 3 successes + 2 failures = 2/5 = 40% → DEGRADED (above 0.3, below 0.7)
        ht.record_success("gpt")
        ht.record_success("gpt")
        ht.record_success("gpt")
        ht.record_failure("gpt")
        ht.record_failure("gpt")
        h = ht.get_health("gpt")
        assert h.status == HealthStatus.DEGRADED

        # 1 consecutive success — not enough
        ht.record_success("gpt")
        h = ht.get_health("gpt")
        assert h.status == HealthStatus.DEGRADED

        # 2nd consecutive success → recovery
        ht.record_success("gpt")
        h = ht.get_health("gpt")
        assert h.status == HealthStatus.HEALTHY

    def test_reset(self):
        ht = HealthTracker()
        ht.record_failure("gpt")
        ht.reset("gpt")
        h = ht.get_health("gpt")
        assert h.status == HealthStatus.HEALTHY


# ── Selector ─────────────────────────────────────────────────────

class TestSelector:

    def test_report_writing_prefers_tier1(self, sample_providers, report_profile):
        sel = Selector()
        candidates = list(sample_providers.values())
        ranked = sel.select(candidates, report_profile)
        assert len(ranked) >= 2
        # Top candidates should be tier 1 (chatgpt-web, gemini-web)
        top_ids = {c.provider.id for c in ranked[:2]}
        assert "chatgpt-web" in top_ids or "gemini-web" in top_ids

    def test_coding_prefers_code_gen(self, sample_providers, coding_profile):
        sel = Selector()
        candidates = list(sample_providers.values())
        ranked = sel.select(candidates, coding_profile)
        # Should include claude-api (tier 2 + code_gen + tool_use)
        assert any(c.provider.id == "claude-api" for c in ranked)

    def test_quick_qa_prefers_low_latency(self, sample_providers, quick_qa_profile):
        sel = Selector()
        candidates = list(sample_providers.values())
        ranked = sel.select(candidates, quick_qa_profile)
        # qwen-api (3000ms) should rank higher than chatgpt-web (15000ms)
        qwen_idx = next(
            (i for i, c in enumerate(ranked) if c.provider.id == "qwen-api"),
            99,
        )
        chatgpt_idx = next(
            (i for i, c in enumerate(ranked) if c.provider.id == "chatgpt-web"),
            99,
        )
        assert qwen_idx < chatgpt_idx

    def test_health_degrades_score(self, sample_providers, report_profile):
        ht = HealthTracker(degraded_failure_rate=0.3)
        sel = Selector(health_tracker=ht)

        # Degrade chatgpt-web
        ht.record_failure("chatgpt-web")
        ht.record_failure("chatgpt-web")
        ht.record_success("chatgpt-web")

        candidates = list(sample_providers.values())
        ranked = sel.select(candidates, report_profile)
        # chatgpt-web should be lower than gemini-web (same tier, but degraded)
        scores = {c.provider.id: c.score for c in ranked}
        if "chatgpt-web" in scores and "gemini-web" in scores:
            assert scores["gemini-web"] > scores["chatgpt-web"]

    def test_exhausted_excluded(self, sample_providers, report_profile):
        ht = HealthTracker(exhausted_failure_rate=0.5)
        sel = Selector(health_tracker=ht)
        # Exhaust chatgpt-web
        for _ in range(5):
            ht.record_failure("chatgpt-web")

        candidates = list(sample_providers.values())
        ranked = sel.select(candidates, report_profile)
        ids = {c.provider.id for c in ranked}
        assert "chatgpt-web" not in ids

    def test_quality_history(self, sample_providers, report_profile):
        sel = Selector()
        # gemini-web historically bad at reports
        sel.update_quality_history("gemini-web", "report_writing", 0.3)
        # chatgpt-web historically good
        sel.update_quality_history("chatgpt-web", "report_writing", 0.95)

        candidates = list(sample_providers.values())
        ranked = sel.select(candidates, report_profile)
        scores = {c.provider.id: c.score for c in ranked}
        assert scores.get("chatgpt-web", 0) > scores.get("gemini-web", 0)

    def test_fallbacks_added(self, sample_providers, report_profile):
        """When primary candidates are few, fallbacks are added."""
        # Only pass tier-1 providers + one disabled
        providers = {
            "chatgpt-web": sample_providers["chatgpt-web"],
            "qwen-api": sample_providers["qwen-api"],  # tier 3, won't match min_tier=1
        }
        sel = Selector()
        ranked = sel.select(list(providers.values()), report_profile)
        # Should have chatgpt-web as primary + qwen-api as fallback
        assert len(ranked) >= 2


# ── Feedback Collector ───────────────────────────────────────────

class TestFeedbackCollector:

    def test_success_updates_health(self):
        ht = HealthTracker()
        fc = FeedbackCollector(health_tracker=ht)
        fc.report(ExecutionOutcome(
            provider_id="chatgpt-web",
            task_type="report_writing",
            success=True,
            latency_ms=5000,
        ))
        h = ht.get_health("chatgpt-web")
        assert h.failure_rate == 0.0

    def test_failure_updates_health(self):
        ht = HealthTracker()
        fc = FeedbackCollector(health_tracker=ht)
        fc.report(ExecutionOutcome(
            provider_id="chatgpt-web",
            task_type="report_writing",
            success=False,
            error_type="timeout",
        ))
        h = ht.get_health("chatgpt-web")
        assert h.failure_rate == 1.0

    def test_cooldown_outcome(self):
        ht = HealthTracker()
        fc = FeedbackCollector(health_tracker=ht)
        fc.report(ExecutionOutcome(
            provider_id="gemini-web",
            task_type="quick_qa",
            success=False,
            cooldown_seconds=120,
        ))
        h = ht.get_health("gemini-web")
        assert h.status == HealthStatus.COOLDOWN

    def test_quality_callback(self):
        ht = HealthTracker()
        quality_updates = []
        fc = FeedbackCollector(
            health_tracker=ht,
            on_quality_update=lambda p, t, q: quality_updates.append((p, t, q)),
        )
        fc.report(ExecutionOutcome(
            provider_id="chatgpt-web",
            task_type="report_writing",
            success=True,
            quality_score=0.85,
        ))
        assert len(quality_updates) == 1
        assert quality_updates[0] == ("chatgpt-web", "report_writing", 0.85)

    def test_emit_fallback_signal(self):
        ht = HealthTracker()
        mock_observer = MagicMock()
        mock_observer.emit = MagicMock()
        fc = FeedbackCollector(health_tracker=ht, evomap_observer=mock_observer)

        fc.emit_fallback(
            trace_id="trace-fallback",
            task_type="report_writing",
            from_provider_id="chatgpt-web",
            to_provider_id="gemini-web",
            attempt_index=1,
            total_candidates=3,
            error_type="timeout",
            latency_ms=3210,
        )

        mock_observer.emit.assert_called_once()
        kwargs = mock_observer.emit.call_args.kwargs
        assert kwargs["signal_type"] == "route.fallback"
        assert kwargs["trace_id"] == "trace-fallback"
        assert kwargs["domain"] == "routing"
        assert kwargs["payload"]["from_provider_id"] == "chatgpt-web"
        assert kwargs["payload"]["to_provider_id"] == "gemini-web"
        assert kwargs["payload"]["attempt_index"] == 1
        assert kwargs["payload"]["total_candidates"] == 3
        assert kwargs["payload"]["error_type"] == "timeout"


# ── RoutingFabric (end-to-end) ───────────────────────────────────

class TestRoutingFabric:

    def test_from_real_config(self):
        fabric = RoutingFabric.from_config()
        assert fabric.status()["total_providers"] >= 6

    def test_resolve_report(self):
        fabric = RoutingFabric.from_config()
        route = fabric.resolve(RouteRequest(intent_route="report"))
        assert len(route.candidates) >= 2
        # Top should be tier 1
        assert route.candidates[0].provider.tier == 1

    def test_resolve_deep_research(self):
        fabric = RoutingFabric.from_config()
        route = fabric.resolve(RouteRequest(intent_route="deep_research"))
        assert len(route.candidates) >= 1
        # Must have deep_research capability
        top = route.candidates[0]
        assert Capability.DEEP_RESEARCH in top.provider.capabilities

    def test_resolve_coding(self):
        fabric = RoutingFabric.from_config()
        route = fabric.resolve(RouteRequest(intent_route="action"))
        # Should include claude-api or providers with code_gen
        has_code = any(
            Capability.CODE_GEN in c.provider.capabilities
            for c in route.candidates
        )
        assert has_code

    def test_resolve_quick_qa(self):
        fabric = RoutingFabric.from_config()
        route = fabric.resolve(RouteRequest(intent_route="kb_answer"))
        # Should have candidates — all providers have CHAT
        assert len(route.candidates) >= 2

    def test_api_only(self):
        fabric = RoutingFabric.from_config()
        route = fabric.resolve(RouteRequest(intent_route="kb_answer"))
        api_models = route.api_only()
        # Should return model names
        assert len(api_models) >= 1
        # Should be strings, not ProviderSpec
        assert all(isinstance(m, str) for m in api_models)

    def test_resolve_unknown_intent(self):
        fabric = RoutingFabric.from_config()
        route = fabric.resolve(RouteRequest(intent_route="nonexistent"))
        # Falls back to default profile
        assert len(route.candidates) >= 1

    def test_status(self):
        fabric = RoutingFabric.from_config()
        s = fabric.status()
        assert "config_version" in s
        assert "total_providers" in s
        assert "task_profiles" in s

    def test_get_llm_fn_returns_callable(self):
        fabric = RoutingFabric.from_config()
        fn = fabric.get_llm_fn("report", "report_writing")
        assert callable(fn)

    def test_report_outcome(self):
        fabric = RoutingFabric.from_config()
        fabric.report_outcome(ExecutionOutcome(
            provider_id="chatgpt-web",
            task_type="report_writing",
            success=True,
            latency_ms=5000,
        ))
        # Health should still be healthy
        s = fabric.status()
        health = s.get("provider_health", {}).get("chatgpt-web", {})
        assert health.get("status") == "healthy"

    def test_get_llm_fn_emits_fallback_signal(self):
        observer = MagicMock()
        observer.emit = MagicMock()
        fabric = RoutingFabric.from_config(evomap_observer=observer)

        calls = {"count": 0}

        def fake_invoke(provider, prompt, system_msg):
            calls["count"] += 1
            if calls["count"] == 1:
                raise TimeoutError("first provider timed out")
            return "second provider recovered with a valid answer"

        fabric._invoke_provider = fake_invoke  # type: ignore[method-assign]
        fn = fabric.get_llm_fn("report", "report_writing", trace_id="trace-chain")
        result = fn("hello", "")

        assert "valid answer" in result
        emitted_signal_types = [call.kwargs["signal_type"] for call in observer.emit.call_args_list]
        assert "route.fallback" in emitted_signal_types
        assert "route.candidate_outcome" in emitted_signal_types
