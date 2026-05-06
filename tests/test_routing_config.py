"""Tests for routing_config.py — config loading and validation."""

from __future__ import annotations

import json
import pytest

# v1.0 routing modules deprecated — tests replaced by test_routing_fabric.py
pytestmark = pytest.mark.skip(reason="v1.0 routing modules deprecated")

from chatgptrest.kernel.routing_config import (
    RoutingConfigError,
    RoutingProfile,
    load_routing_profile,
    validate_routing_profile,
    _parse_profile,
    DEFAULT_CONFIG_PATH,
)


# ── Loading ───────────────────────────────────────────────────────


def test_load_default_config() -> None:
    """Default config/routing_profile.json loads without errors."""
    profile = load_routing_profile()
    assert profile.schema_version == "1.0.0"
    assert profile.profile_name == "chatgptrest_scenario_routing"
    assert len(profile.routes) >= 7
    assert len(profile.providers) >= 7
    assert len(profile.models) >= 8


def test_load_respects_tiers() -> None:
    profile = load_routing_profile()
    assert profile.tier_order == ["membership", "buffer", "payg"]
    assert "membership" in profile.tiers
    assert "buffer" in profile.tiers
    assert "payg" in profile.tiers


def test_load_providers_have_tiers() -> None:
    profile = load_routing_profile()
    for pid, prov in profile.providers.items():
        assert prov.tier in profile.tier_order, (
            f"Provider {pid} has unknown tier: {prov.tier}"
        )


def test_load_routes_have_candidates() -> None:
    profile = load_routing_profile()
    for i, route in enumerate(profile.routes):
        assert route.candidates, f"Route[{i}] ({route.match.scenario}) has no candidates"


def test_load_switch_policy() -> None:
    profile = load_routing_profile()
    sp = profile.switch_policy
    assert sp.max_attempts_per_candidate >= 1
    assert sp.cooldown_seconds_on_429 > 0
    assert sp.cooldown_seconds_on_5xx > 0


def test_load_guards() -> None:
    profile = load_routing_profile()
    assert "global" in profile.guards
    assert "deep_research" in profile.guards
    assert profile.guards["deep_research"].ack_block_enabled is True
    assert profile.guards["deep_research"].min_chars_default >= 800


# ── Validation ────────────────────────────────────────────────────


def test_validation_passes_for_default_config() -> None:
    profile = load_routing_profile(validate=False)
    errors = validate_routing_profile(profile)
    assert errors == []


def test_validation_rejects_empty_candidates() -> None:
    raw = {
        "routes": [
            {"match": {"scenario": "test", "task_type": "test"}, "candidates": []},
        ],
        "providers": {},
    }
    profile = _parse_profile(raw)
    errors = validate_routing_profile(profile)
    assert any("empty candidates" in e for e in errors)


def test_validation_rejects_unknown_provider() -> None:
    raw = {
        "routes": [
            {
                "match": {"scenario": "test", "task_type": "test"},
                "candidates": [
                    {"provider": "nonexistent_provider", "mode": "api", "timeout_ms": 100},
                ],
            },
        ],
        "providers": {},
    }
    profile = _parse_profile(raw)
    errors = validate_routing_profile(profile)
    assert any("nonexistent_provider" in e for e in errors)


def test_validation_rejects_no_routes() -> None:
    raw = {"routes": [], "providers": {}}
    profile = _parse_profile(raw)
    errors = validate_routing_profile(profile)
    assert any("No routes" in e for e in errors)


def test_load_with_validation_raises_on_error(tmp_path) -> None:
    bad_config = tmp_path / "bad.json"
    bad_config.write_text(json.dumps({"routes": [], "providers": {}}))
    with pytest.raises(RoutingConfigError, match="No routes"):
        load_routing_profile(str(bad_config), validate=True)


def test_load_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_routing_profile("/nonexistent/path/config.json")


# ── Parsing Edge Cases ────────────────────────────────────────────


def test_parse_minimal_profile() -> None:
    """Parsing a minimal JSON should produce defaults for missing fields."""
    raw = {
        "routes": [
            {
                "match": {"scenario": "x"},
                "candidates": [
                    {"provider": "p1", "mode": "api", "timeout_ms": 100},
                ],
            },
        ],
        "providers": {"p1": {"tier": "payg"}},
    }
    profile = _parse_profile(raw)
    assert len(profile.routes) == 1
    assert profile.routes[0].match.task_type == ""
    assert profile.routes[0].candidates[0].timeout_ms == 100
    assert profile.providers["p1"].tier == "payg"


def test_parse_only_if_conditions() -> None:
    raw = {
        "routes": [
            {
                "match": {"scenario": "s1", "task_type": "t1"},
                "candidates": [
                    {
                        "provider": "p1",
                        "mode": "web",
                        "timeout_ms": 100,
                        "only_if": {
                            "evidence_level_in": ["strict"],
                            "latency_budget_ms_gte": 180000,
                        },
                    },
                ],
            },
        ],
        "providers": {"p1": {"tier": "membership"}},
    }
    profile = _parse_profile(raw)
    cand = profile.routes[0].candidates[0]
    assert cand.only_if is not None
    assert cand.only_if.evidence_level_in == ["strict"]
    assert cand.only_if.latency_budget_ms_gte == 180000
