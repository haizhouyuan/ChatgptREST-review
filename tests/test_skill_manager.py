from __future__ import annotations

from chatgptrest.kernel.skill_manager import get_bundle_resolver, get_canonical_registry


def test_canonical_registry_loads_authority() -> None:
    registry = get_canonical_registry()

    assert registry.authority.owner == "ChatgptREST/OpenMind"
    assert registry.authority.source_of_truth.endswith("skill_platform_registry_v1.json")
    assert "canonical" in registry.authority.classification_contract
    assert registry.capability_catalog()["market_research"].startswith("Conduct structured market research")


def test_platform_projection_contains_openclaw_agents_and_bundles() -> None:
    registry = get_canonical_registry()

    projection = registry.projection_for_platform("openclaw")
    bundle_ids = {item["bundle_id"] for item in projection["bundles"]}
    agent_ids = {item["agent_id"] for item in projection["agents"]}

    assert {"general_core", "maint_core", "research_core"}.issubset(bundle_ids)
    assert {"main", "maintagent", "finbot"} == agent_ids


def test_platform_projection_contains_shared_frontend_adapters() -> None:
    registry = get_canonical_registry()

    for platform in ("codex", "claude_code", "antigravity"):
        projection = registry.projection_for_platform(platform)
        assert projection["adapter"]["projection_mode"] == "shared_catalog_reference"
        assert "chatgptrest-call" in {item["skill_id"] for item in projection["skills"]}
        assert "market_scan_quarantine" in {item["bundle_id"] for item in projection["bundles"]}


def test_bundle_resolver_returns_unmet_capabilities_for_main_market_research() -> None:
    resolver = get_bundle_resolver()

    result = resolver.resolve_for_agent(
        agent_id="main",
        task_type="market_research",
        platform="openclaw",
    )

    assert result.passed is False
    assert result.status == "unmet_capabilities"
    assert result.suggested_agent == "finbot"
    assert any(item.capability_id == "market_research" for item in result.unmet_capabilities)
    assert "research_core" in result.recommended_bundles


def test_bundle_resolver_fails_closed_for_unknown_agent() -> None:
    resolver = get_bundle_resolver()

    result = resolver.resolve_for_agent(
        agent_id="unknown",
        task_type="general",
        platform="openclaw",
    )

    assert result.passed is False
    assert result.status == "unknown_agent"
    assert result.suggested_agent == "main"
