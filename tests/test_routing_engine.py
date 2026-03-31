"""Tests for routing_engine.py — route resolution logic."""

from __future__ import annotations

import pytest

# v1.0 routing modules deprecated — tests replaced by test_routing_fabric.py
pytestmark = pytest.mark.skip(reason="v1.0 routing modules deprecated")

from chatgptrest.kernel.routing_config import load_routing_profile, _parse_profile
from chatgptrest.kernel.routing_engine import RoutingEngine, RouteRequest


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def engine():
    """Engine loaded from default config."""
    return RoutingEngine(load_routing_profile())


@pytest.fixture
def minimal_engine():
    """Engine with a small hand-crafted profile for deterministic tests."""
    raw = {
        "tiers": {
            "tier_order": ["membership", "buffer", "payg"],
            "membership": {"max_concurrency": 1},
            "buffer": {"max_concurrency": 4},
            "payg": {"max_concurrency": 4},
        },
        "providers": {
            "high_quality": {"tier": "membership", "type": "chatgptrest_job"},
            "mid_tier": {"tier": "buffer", "type": "openai_compat_api"},
            "fallback": {"tier": "payg", "type": "openai_api"},
        },
        "models": {
            "model-a": {"provider_type": "web_chatgpt", "quality_hint": 0.9},
            "model-b": {"provider_type": "api", "quality_hint": 0.7},
        },
        "static_routes": {
            "coding": ["model-a", "model-b"],
            "default": ["model-b"],
        },
        "routes": [
            {
                "match": {"scenario": "coding", "task_type": "code"},
                "candidates": [
                    {"provider": "high_quality", "mode": "web", "preset": "pro", "timeout_ms": 300000},
                    {"provider": "mid_tier", "mode": "api", "model": "model-b", "timeout_ms": 120000},
                    {"provider": "fallback", "mode": "api", "model": "model-b", "timeout_ms": 120000},
                ],
            },
            {
                "match": {"scenario": "research", "task_type": "research"},
                "candidates": [
                    {
                        "provider": "high_quality",
                        "mode": "web",
                        "preset": "deep_research",
                        "timeout_ms": 1800000,
                        "guard_profile": "deep_research",
                    },
                    {"provider": "fallback", "mode": "api", "model": "model-b", "timeout_ms": 240000},
                ],
            },
            {
                "match": {"scenario": "strict_only", "task_type": "strict_only"},
                "candidates": [
                    {
                        "provider": "high_quality",
                        "mode": "web",
                        "timeout_ms": 600000,
                        "only_if": {"evidence_level_in": ["strict"]},
                    },
                    {"provider": "fallback", "mode": "api", "timeout_ms": 120000},
                ],
            },
            {
                "match": {"scenario": "latency_gate", "task_type": "latency_gate"},
                "candidates": [
                    {
                        "provider": "high_quality",
                        "mode": "web",
                        "timeout_ms": 600000,
                        "only_if": {"latency_budget_ms_gte": 300000},
                    },
                    {"provider": "mid_tier", "mode": "api", "timeout_ms": 120000},
                ],
            },
            {
                "match": {"scenario": "default", "task_type": "default"},
                "candidates": [
                    {"provider": "mid_tier", "mode": "api", "timeout_ms": 120000},
                    {"provider": "fallback", "mode": "api", "timeout_ms": 120000},
                ],
            },
        ],
        "guards": {
            "global": {"no_duplicate_send": True, "wait_slice_seconds": 30},
            "deep_research": {"ack_block_enabled": True, "min_chars_default": 1800},
        },
    }
    return RoutingEngine(_parse_profile(raw))


# ── Exact Route Matching ──────────────────────────────────────────


def test_resolve_coding_exact(minimal_engine) -> None:
    r = minimal_engine.resolve(RouteRequest(scenario="coding", task_type="code"))
    assert len(r.candidates) == 3
    assert r.candidates[0].provider == "high_quality"
    assert r.candidates[0].mode == "web"
    assert r.source == "config"


def test_resolve_research_exact(minimal_engine) -> None:
    r = minimal_engine.resolve(RouteRequest(scenario="research", task_type="research"))
    assert len(r.candidates) == 2
    assert r.candidates[0].preset == "deep_research"
    assert r.guard_profile is not None
    assert r.guard_profile.ack_block_enabled is True


# ── Fallback Matching ─────────────────────────────────────────────


def test_resolve_unknown_falls_to_default(minimal_engine) -> None:
    r = minimal_engine.resolve(RouteRequest(scenario="unknown", task_type="unknown"))
    assert r.candidates[0].provider == "mid_tier"


def test_resolve_scenario_only_match(minimal_engine) -> None:
    """Matching on scenario when task_type doesn't match exactly."""
    r = minimal_engine.resolve(RouteRequest(scenario="coding", task_type="unknown"))
    assert r.candidates[0].provider == "high_quality"


# ── only_if Condition Filtering ───────────────────────────────────


def test_only_if_evidence_filters_candidate(minimal_engine) -> None:
    """Candidate with evidence_level_in=[strict] is filtered when evidence is 'none'."""
    r = minimal_engine.resolve(
        RouteRequest(scenario="strict_only", task_type="strict_only", evidence_level="none")
    )
    # high_quality should be filtered, leaving only fallback
    assert r.candidates[0].provider == "fallback"
    assert len(r.candidates) == 1


def test_only_if_evidence_passes(minimal_engine) -> None:
    """Candidate with evidence_level_in=[strict] passes when evidence IS 'strict'."""
    r = minimal_engine.resolve(
        RouteRequest(scenario="strict_only", task_type="strict_only", evidence_level="strict")
    )
    # high_quality should be included
    assert r.candidates[0].provider == "high_quality"
    assert len(r.candidates) == 2


def test_only_if_latency_filters(minimal_engine) -> None:
    """Candidate with latency_budget_ms_gte=300000 is filtered at 100ms budget."""
    r = minimal_engine.resolve(
        RouteRequest(scenario="latency_gate", task_type="latency_gate", latency_budget_ms=100)
    )
    assert r.candidates[0].provider == "mid_tier"
    assert len(r.candidates) == 1


def test_only_if_latency_passes(minimal_engine) -> None:
    """Candidate passes when latency budget is sufficient."""
    r = minimal_engine.resolve(
        RouteRequest(scenario="latency_gate", task_type="latency_gate", latency_budget_ms=500000)
    )
    assert r.candidates[0].provider == "high_quality"
    assert len(r.candidates) == 2


def test_only_if_latency_zero_means_no_constraint(minimal_engine) -> None:
    """latency_budget_ms=0 means no constraint, should pass."""
    r = minimal_engine.resolve(
        RouteRequest(scenario="latency_gate", task_type="latency_gate", latency_budget_ms=0)
    )
    assert r.candidates[0].provider == "high_quality"


# ── Synthesize from Static Routes ─────────────────────────────────


def test_synthesize_from_static(minimal_engine) -> None:
    """When no route matches a completely unknown scenario, synthesize from static_routes."""
    # Remove all routes, leaving only static_routes
    minimal_engine._profile.routes.clear()
    r = minimal_engine.resolve(RouteRequest(scenario="coding"))
    assert r.source == "default_fallback"
    assert len(r.candidates) >= 1


# ── ResolvedRoute Properties ─────────────────────────────────────


def test_primary_and_fallbacks(minimal_engine) -> None:
    r = minimal_engine.resolve(RouteRequest(scenario="coding", task_type="code"))
    assert r.primary is not None
    assert r.primary.provider == "high_quality"
    assert len(r.fallbacks) == 2


def test_to_dict(minimal_engine) -> None:
    r = minimal_engine.resolve(RouteRequest(scenario="coding", task_type="code"))
    d = r.to_dict()
    assert d["scenario"] == "coding"
    assert d["task_type"] == "code"
    assert len(d["candidates"]) == 3


# ── Real Config Tests ─────────────────────────────────────────────


def test_real_config_coding_route(engine) -> None:
    r = engine.resolve(RouteRequest(scenario="coding", task_type="code"))
    assert len(r.candidates) >= 3
    providers = [c.provider for c in r.candidates]
    # Should have gemini_cli as first candidate
    assert "gemini_cli" in providers


def test_real_config_research_route(engine) -> None:
    r = engine.resolve(RouteRequest(scenario="research", task_type="research"))
    assert len(r.candidates) >= 2
    # Deep research should be first
    assert r.candidates[0].preset == "deep_research"


def test_real_config_all_routes_resolve(engine) -> None:
    """Every scenario from config resolves without errors."""
    scenarios = [
        ("coding", "code"),
        ("debug", "debug"),
        ("planning", "plan"),
        ("review", "review"),
        ("research", "research"),
        ("report", "report"),
        ("default", "default"),
    ]
    for scenario, task_type in scenarios:
        r = engine.resolve(RouteRequest(scenario=scenario, task_type=task_type))
        assert r.candidates, f"No candidates for {scenario}/{task_type}"
        assert r.rationale, f"No rationale for {scenario}/{task_type}"


# ── Reload ────────────────────────────────────────────────────────


def test_reload(engine) -> None:
    """reload() updates the profile without error."""
    old_name = engine.profile.profile_name
    engine.reload()
    assert engine.profile.profile_name == old_name
