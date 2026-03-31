"""Tests for ModelRouter config integration and backward compatibility."""

from __future__ import annotations

import pytest

from chatgptrest.kernel.model_router import ModelRouter, MODEL_REGISTRY, STATIC_ROUTES


def test_model_router_backward_compat() -> None:
    """ModelRouter() without args still works using hardcoded defaults."""
    router = ModelRouter()
    decision = router.select("coding")
    assert decision.models
    assert len(decision.models) >= 1
    assert decision.source in ("fusion", "static")


@pytest.mark.skip(reason="v1.0 routing_config.py deprecated — config is now v2.0, use RoutingFabric")
def test_model_router_from_config() -> None:
    """ModelRouter.from_config() produces a working router."""
    from chatgptrest.kernel.routing_config import load_routing_profile
    profile = load_routing_profile()
    router = ModelRouter.from_config(profile)
    decision = router.select("planning")
    assert decision.models
    assert len(decision.models) >= 1


@pytest.mark.skip(reason="v1.0 routing_config.py deprecated — config is now v2.0, use RoutingFabric")
def test_model_router_from_config_has_all_models() -> None:
    """Config-loaded router knows about all models from the config."""
    from chatgptrest.kernel.routing_config import load_routing_profile
    profile = load_routing_profile()
    router = ModelRouter.from_config(profile)
    for model_name in profile.models:
        assert model_name in router._registry


@pytest.mark.skip(reason="v1.0 routing_config.py deprecated — config is now v2.0, use RoutingFabric")
def test_model_router_from_config_static_routes_match() -> None:
    """Config-loaded router uses the config's static routes."""
    from chatgptrest.kernel.routing_config import load_routing_profile
    profile = load_routing_profile()
    router = ModelRouter.from_config(profile)
    for key in profile.static_routes:
        assert key in router._static


def test_model_router_default_registry_unchanged() -> None:
    """Module-level MODEL_REGISTRY still exists and is unchanged."""
    assert len(MODEL_REGISTRY) >= 8
    assert "chatgpt-web" in MODEL_REGISTRY
    assert "gemini-cli" in MODEL_REGISTRY
    assert "MiniMax-M2.5" in MODEL_REGISTRY


def test_model_router_default_static_routes_unchanged() -> None:
    """Module-level STATIC_ROUTES still exists and is unchanged."""
    assert len(STATIC_ROUTES) >= 6
    assert "default" in STATIC_ROUTES
    assert "coding" in STATIC_ROUTES
