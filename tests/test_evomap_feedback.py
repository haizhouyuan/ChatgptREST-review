"""Tests for EvoMap feedback loop — signal emission + quota integration."""

from __future__ import annotations

import pytest

# v1.0 routing modules deprecated — tests replaced by test_routing_fabric.py
pytestmark = pytest.mark.skip(reason="v1.0 routing modules deprecated")

from chatgptrest.kernel.routing_config import load_routing_profile, _parse_profile
from chatgptrest.kernel.routing_engine import RoutingEngine, RouteRequest
from chatgptrest.kernel.quota_sensor import QuotaSensor, HealthStatus
from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.evomap.signals import SignalType


# ── Signal Emission ───────────────────────────────────────────────


def test_resolve_emits_route_selected_signal():
    observer = EvoMapObserver(db_path=":memory:")
    engine = RoutingEngine(load_routing_profile(), evomap_observer=observer)

    engine.resolve(RouteRequest(scenario="coding", task_type="code", trace_id="tr_001"))

    signals = observer.query(trace_id="tr_001")
    assert len(signals) >= 1

    route_sel = [s for s in signals if s.signal_type == "route_selected"]
    assert len(route_sel) == 1
    assert route_sel[0].domain == "routing"
    assert route_sel[0].source == "routing_engine"
    assert route_sel[0].data["scenario"] == "coding"
    assert route_sel[0].data["candidate_count"] >= 3


def test_report_outcome_emits_signal():
    observer = EvoMapObserver(db_path=":memory:")
    engine = RoutingEngine(load_routing_profile(), evomap_observer=observer)

    engine.report_outcome("chatgpt_web", success=True, latency_ms=5000, trace_id="tr_002")

    signals = observer.query(trace_id="tr_002")
    assert len(signals) == 1
    assert signals[0].signal_type == "route.candidate_outcome"
    assert signals[0].data["provider"] == "chatgpt_web"
    assert signals[0].data["success"] is True
    assert signals[0].data["latency_ms"] == 5000


def test_report_outcome_failure_emits_signal():
    observer = EvoMapObserver(db_path=":memory:")
    engine = RoutingEngine(load_routing_profile(), evomap_observer=observer)

    engine.report_outcome(
        "gemini_web", success=False, error_type="rate_limited", trace_id="tr_003",
    )

    signals = observer.query(trace_id="tr_003")
    assert len(signals) == 1
    assert signals[0].data["success"] is False
    assert signals[0].data["error_type"] == "rate_limited"


def test_no_observer_no_error():
    """resolve() works fine without an observer (fail-open)."""
    engine = RoutingEngine(load_routing_profile())
    r = engine.resolve(RouteRequest(scenario="coding", task_type="code"))
    assert len(r.candidates) >= 3


# ── Quota + Routing Integration ───────────────────────────────────


def _build_engine_with_quota():
    """Helper: build engine with quota sensor and observer."""
    raw = {
        "providers": {
            "good": {"tier": "membership"},
            "bad": {"tier": "buffer"},
            "fallback": {"tier": "payg"},
        },
        "models": {},
        "static_routes": {"default": []},
        "routes": [
            {
                "match": {"scenario": "test", "task_type": "test"},
                "candidates": [
                    {"provider": "good", "mode": "web", "timeout_ms": 100},
                    {"provider": "bad", "mode": "api", "timeout_ms": 100},
                    {"provider": "fallback", "mode": "api", "timeout_ms": 100},
                ],
            },
        ],
        "guards": {"global": {"no_duplicate_send": True}},
    }
    profile = _parse_profile(raw)
    sensor = QuotaSensor(degrade_threshold=2, exhaust_threshold=3)
    observer = EvoMapObserver(db_path=":memory:")
    engine = RoutingEngine(profile, quota_sensor=sensor, evomap_observer=observer)
    return engine, sensor, observer


def test_quota_exhausted_skips_provider():
    engine, sensor, observer = _build_engine_with_quota()

    # Exhaust "good" provider
    for _ in range(3):
        sensor.report_failure("good", "rate_limited")
    assert sensor.check("good").status == HealthStatus.EXHAUSTED

    r = engine.resolve(RouteRequest(scenario="test", task_type="test"))
    providers = [c.provider for c in r.candidates]
    assert "good" not in providers  # exhausted, should be skipped
    assert "bad" in providers
    assert "fallback" in providers


def test_quota_degraded_deprioritizes():
    engine, sensor, observer = _build_engine_with_quota()

    # Degrade "good" provider (2 failures)
    sensor.report_failure("good", "timeout")
    sensor.report_failure("good", "timeout")
    assert sensor.check("good").status == HealthStatus.DEGRADED

    r = engine.resolve(RouteRequest(scenario="test", task_type="test"))
    providers = [c.provider for c in r.candidates]
    # "good" should still be in list but after healthy providers
    assert "good" in providers
    assert providers[0] != "good"  # degraded pushed down


def test_report_outcome_updates_quota_and_emits():
    engine, sensor, observer = _build_engine_with_quota()

    # Report failure via engine
    engine.report_outcome("good", success=False, error_type="timeout", trace_id="tr_q1")

    # QuotaSensor updated
    assert sensor.check("good").consecutive_failures == 1

    # EvoMap signal emitted
    signals = observer.query(trace_id="tr_q1")
    assert len(signals) == 1
    assert signals[0].data["provider"] == "good"


def test_report_outcome_with_cooldown():
    engine, sensor, observer = _build_engine_with_quota()

    engine.report_outcome(
        "bad", success=False, error_type="rate_limited",
        cooldown_seconds=300, trace_id="tr_q2",
    )

    h = sensor.check("bad")
    assert h.status == HealthStatus.COOLDOWN


def test_config_version_in_resolved_route():
    engine, _, _ = _build_engine_with_quota()
    r = engine.resolve(RouteRequest(scenario="test", task_type="test"))
    assert r.config_version == 1

    # The to_dict includes config_version
    d = r.to_dict()
    assert d["config_version"] == 1
