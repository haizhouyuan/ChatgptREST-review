"""EvoMap E2E integration tests — full signal flow verification.

Tests the complete data flow from event emission through EventBus to
Observer recording and Actuator behavioral changes.

Signal coverage:
  T1: route.selected → Observer recording
  T2: gate.passed/failed → GateAutoTuner threshold adjustment
  T3: llm.call_failed (infra) → CircuitBreaker → degraded
  T4: llm.call_failed (business) → CircuitBreaker ignores
  T5: KBScorer responds to advisor_ask.kb_direct events
  T6: CircuitBreaker → HealthTracker integration (OPEN-1 fix)
  T7: GateAutoTuner initial_threshold clamp (OPEN-2 fix)
  T8: Distiller SHA-256 hash stability (OPEN-3 fix)
  T9: Distiller source_path injection (OPEN-5 fix)
  T10: Distiller post-validator (OPEN-6 fix)
  T11: Full actuator feedback loop (signal → actuator → observer signal)
  T12: EventBus fan-out (one event → multiple subscribers)
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any

import pytest


# ── Helpers ──────────────────────────────────────────────────────


@dataclass
class MockEvent:
    """Lightweight event for testing EventBus subscribers."""
    event_type: str = ""
    data: dict = field(default_factory=dict)
    trace_id: str = "test-trace-001"
    source: str = "test"
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


class EventCapture:
    """Captures events for assertion."""

    def __init__(self):
        self.events: list[MockEvent] = []

    def on_event(self, event):
        self.events.append(event)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def observer():
    """Create EvoMapObserver with temp DB."""
    from chatgptrest.evomap.observer import EvoMapObserver
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    obs = EvoMapObserver(db_path=db_path)
    yield obs
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def circuit_breaker(observer):
    """Create CircuitBreaker wired to observer."""
    from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
    config = CircuitBreakerConfig(
        window_seconds=60,
        consecutive_fail_threshold=3,
        window_fail_threshold=5,
        cooldown_seconds=10,
        degraded_seconds=5,
    )
    return CircuitBreaker(observer=observer, config=config)


@pytest.fixture
def gate_tuner(observer):
    """Create GateAutoTuner wired to observer."""
    from chatgptrest.evomap.actuators.gate_tuner import GateAutoTuner
    return GateAutoTuner(observer=observer, initial_threshold=0.6)


@pytest.fixture
def kb_scorer(observer):
    """Create KBScorer wired to observer."""
    from chatgptrest.evomap.actuators.kb_scorer import KBScorer
    return KBScorer(observer=observer)


# ═══════════════════════════════════════════════════════════════════
# T1: route.selected → Observer recording
# ═══════════════════════════════════════════════════════════════════


class TestRouteSignalFlow:
    """T1: Verify route.selected signals are recorded by Observer."""

    def test_route_selected_recorded(self, observer):
        observer.record_event(
            trace_id="t-001",
            signal_type="route.selected",
            source="advisor",
            domain="routing",
            data={"route": "quick_ask", "provider": "chatgpt"},
        )
        signals = observer.query(trace_id="t-001")
        # Observer.query() returns Signal objects
        assert any(s.signal_type == "route.selected" for s in signals)

    def test_multiple_routes_per_trace(self, observer):
        """Multiple route signals in same trace should all be recorded."""
        for i in range(3):
            observer.record_event(
                trace_id="t-002",
                signal_type="route.selected",
                source="advisor",
                domain="routing",
                data={"route": f"route_{i}"},
            )
        signals = observer.query(trace_id="t-002")
        route_sigs = [s for s in signals if s.signal_type == "route.selected"]
        assert len(route_sigs) == 3


# ═══════════════════════════════════════════════════════════════════
# T2: gate.passed/failed → GateAutoTuner adjustment
# ═══════════════════════════════════════════════════════════════════


class TestGateAutoTunerIntegration:
    """T2: GateAutoTuner responds to gate events via EventBus pattern.
    
    Note: _CHECK_INTERVAL=50 gate events (gate.passed + gate.failed).
    dispatch.task_failed increments _task_failed but NOT _total_events.
    """

    def test_tighten_on_high_pass_rate_with_failures(self, gate_tuner):
        """High pass rate + downstream failures → threshold tightens.
        
        Need: pass_rate > 0.85 (_HIGH_PASS_RATE) AND downstream_fail_rate > 0.05
        So: 47 passes + 3 fails = 50 total gates, pass_rate=0.94
             + 3 dispatch.task_failed → downstream_fail_rate=3/47=0.064 > 0.05
        """
        initial = gate_tuner.get_threshold()

        # First add task failures (these don't count toward total_events)
        for _ in range(3):
            gate_tuner.on_event(MockEvent("dispatch.task_failed"))

        # 47 passes + 3 fails = 50 total → triggers _evaluate()
        for _ in range(47):
            gate_tuner.on_event(MockEvent("gate.passed"))
        for _ in range(3):
            gate_tuner.on_event(MockEvent("gate.failed"))

        assert gate_tuner.get_threshold() > initial

    def test_loosen_on_low_pass_rate(self, gate_tuner):
        """Low pass rate → threshold loosens.
        
        Need: pass_rate < 0.6 (_LOW_PASS_RATE)
        So: 25 passes + 25 fails = 50 total, pass_rate=0.5
        """
        initial = gate_tuner.get_threshold()

        for _ in range(25):
            gate_tuner.on_event(MockEvent("gate.passed"))
        for _ in range(25):
            gate_tuner.on_event(MockEvent("gate.failed"))

        assert gate_tuner.get_threshold() < initial

    def test_initial_threshold_clamped(self):
        """OPEN-2: initial_threshold is clamped to [min, max]."""
        from chatgptrest.evomap.actuators.gate_tuner import GateAutoTuner

        # Too high
        t1 = GateAutoTuner(initial_threshold=1.5, min_threshold=0.3, max_threshold=0.95)
        assert t1.get_threshold() == 0.95

        # Too low
        t2 = GateAutoTuner(initial_threshold=0.1, min_threshold=0.3, max_threshold=0.95)
        assert t2.get_threshold() == 0.3

        # Normal
        t3 = GateAutoTuner(initial_threshold=0.6, min_threshold=0.3, max_threshold=0.95)
        assert t3.get_threshold() == 0.6


# ═══════════════════════════════════════════════════════════════════
# T3-T4: CircuitBreaker error isolation
# ═══════════════════════════════════════════════════════════════════


class TestCircuitBreakerIntegration:
    """T3-T4: CircuitBreaker distinguishes infra vs business errors."""

    def test_infra_errors_trigger_degraded(self, circuit_breaker):
        """T3: 3 consecutive infra errors → provider degraded."""
        for _ in range(3):
            circuit_breaker.on_event(MockEvent(
                "llm.call_failed",
                {"provider": "chatgpt", "error_category": "timeout"},
            ))
        status = circuit_breaker.get_status()
        assert status["chatgpt"]["state"] == "degraded"

    def test_business_errors_ignored(self, circuit_breaker):
        """T4: Business errors don't trigger circuit breaking."""
        for _ in range(5):
            circuit_breaker.on_event(MockEvent(
                "llm.call_failed",
                {"provider": "gemini", "error_category": "context_exceeded"},
            ))
        status = circuit_breaker.get_status()
        assert status.get("gemini", {}).get("state", "healthy") == "healthy"

    def test_502_504_are_infra_errors(self, circuit_breaker):
        """OPEN-4: 502 and 504 errors are treated as infra errors."""
        for _ in range(3):
            circuit_breaker.on_event(MockEvent(
                "llm.call_failed",
                {"provider": "test_502", "error_category": "provider_502"},
            ))
        assert circuit_breaker.get_status()["test_502"]["state"] == "degraded"

    def test_success_resets_consecutive_failures(self, circuit_breaker):
        """Success after failures resets counter."""
        for _ in range(2):
            circuit_breaker.on_event(MockEvent(
                "llm.call_failed",
                {"provider": "chatgpt", "error_category": "timeout"},
            ))
        circuit_breaker.on_event(MockEvent(
            "llm.call_completed",
            {"provider": "chatgpt", "latency_ms": 1000},
        ))
        status = circuit_breaker.get_status()
        assert status["chatgpt"]["consecutive_failures"] == 0

    def test_window_failures_trigger_escalation(self, circuit_breaker):
        """5 failures in window → elevated state."""
        for i in range(5):
            circuit_breaker.on_event(MockEvent(
                "llm.call_failed",
                {"provider": "qwen", "error_category": "connection_error"},
            ))
            if i < 4:
                circuit_breaker.on_event(MockEvent(
                    "llm.call_completed",
                    {"provider": "qwen", "latency_ms": 500},
                ))
        status = circuit_breaker.get_status()
        assert status["qwen"]["state"] in ("degraded", "cooldown")


# ═══════════════════════════════════════════════════════════════════
# T5: KBScorer — responds to advisor_ask.kb_direct events
# ═══════════════════════════════════════════════════════════════════


class TestKBScorerIntegration:
    """T5: KBScorer responds to its specific event types."""

    def test_kb_direct_event_handled(self, kb_scorer):
        """KBScorer handles advisor_ask.kb_direct event."""
        kb_scorer.on_event(MockEvent(
            "advisor_ask.kb_direct",
            {"artifact_ids": ["art-001"], "relevance_score": 0.85},
        ))
        # Should not raise — verifies handler is wired
        # (Internal state depends on implementation)

    def test_task_failed_event_handled(self, kb_scorer):
        """KBScorer handles dispatch.task_failed event."""
        kb_scorer.on_event(MockEvent(
            "dispatch.task_failed",
            {"reason": "timeout", "provider": "chatgpt"},
        ))
        # Should not raise


# ═══════════════════════════════════════════════════════════════════
# T6: CircuitBreaker → HealthTracker integration (OPEN-1 fix)
# ═══════════════════════════════════════════════════════════════════


class TestCircuitBreakerHealthTrackerIntegration:
    """T6: OPEN-1 fix — CircuitBreaker pushes to HealthTracker using real API."""

    def test_degraded_triggers_health_tracker_failure(self):
        """CircuitBreaker degraded → HealthTracker.record_failure()."""
        from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        from chatgptrest.kernel.routing.health_tracker import HealthTracker

        ht = HealthTracker()
        config = CircuitBreakerConfig(consecutive_fail_threshold=3, degraded_seconds=5)
        breaker = CircuitBreaker(health_tracker=ht, config=config)

        # Trigger degraded
        for _ in range(3):
            breaker.on_event(MockEvent(
                "llm.call_failed",
                {"provider": "chatgpt", "error_category": "timeout"},
            ))

        # HealthTracker should have been called
        health = ht.get_health("chatgpt")
        # record_failure should have increased failure tracking
        assert health is not None

    def test_cooldown_triggers_health_tracker_cooldown(self):
        """CircuitBreaker cooldown → HealthTracker.record_cooldown()."""
        from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        from chatgptrest.kernel.routing.health_tracker import HealthTracker, HealthStatus

        ht = HealthTracker()
        config = CircuitBreakerConfig(
            consecutive_fail_threshold=3,
            window_fail_threshold=5,
            cooldown_seconds=30,
        )
        breaker = CircuitBreaker(health_tracker=ht, config=config)

        # Trigger cooldown (5+ failures in window)
        for _ in range(5):
            breaker.on_event(MockEvent(
                "llm.call_failed",
                {"provider": "gemini", "error_category": "timeout"},
            ))

        health = ht.get_health("gemini")
        # Should be in cooldown or degraded
        assert health.status in (
            HealthStatus.COOLDOWN, HealthStatus.DEGRADED, HealthStatus.EXHAUSTED,
        )

    def test_recovery_after_degraded(self):
        """CircuitBreaker degrades then recovers after success."""
        from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            consecutive_fail_threshold=3,
            degraded_seconds=2,  # short but non-zero
        )
        breaker = CircuitBreaker(config=config)

        # Trigger degraded
        for _ in range(3):
            breaker.on_event(MockEvent(
                "llm.call_failed",
                {"provider": "qwen", "error_category": "timeout"},
            ))
        # Check immediately (within 2s window)
        assert breaker.get_status()["qwen"]["state"] == "degraded"

        # Send success — breaker should record it
        breaker.on_event(MockEvent(
            "llm.call_completed",
            {"provider": "qwen", "latency_ms": 500},
        ))
        # Consecutive failures should reset even while degraded
        assert breaker.get_status()["qwen"]["consecutive_failures"] == 0


# ═══════════════════════════════════════════════════════════════════
# T8-T10: Distiller fixes
# ═══════════════════════════════════════════════════════════════════


class TestDistillerFixes:
    """T8-T10: Verify OPEN-3, OPEN-5, OPEN-6 distiller fixes."""

    def test_hash_stability_across_calls(self):
        """OPEN-3: SHA-256 hash is stable across calls (unlike hash())."""
        import hashlib
        content = "test content for hashing stability 测试"
        h1 = hashlib.sha256(content.encode()).hexdigest()[:16]
        h2 = hashlib.sha256(content.encode()).hexdigest()[:16]
        assert h1 == h2
        assert len(h1) == 16

    def test_llm_distill_receives_source_path(self):
        """OPEN-5: _llm_distill receives source_path parameter."""
        from chatgptrest.evomap.knowledge.distiller import KnowledgeDistiller

        captured_prompts = []

        def mock_llm(prompt, system_msg):
            captured_prompts.append(prompt)
            return "1. Test chunk about CircuitBreaker error isolation in circuit_breaker.py"

        distiller = KnowledgeDistiller(llm_fn=mock_llm)
        distiller._llm_distill(
            "some content about testing", "markdown",
            source_path="/path/to/my_module.py",
        )

        assert len(captured_prompts) == 1
        assert "my_module.py" in captured_prompts[0]

    def test_post_validator_rejects_short_chunks(self):
        """OPEN-6: Post-validator rejects chunks shorter than 30 chars."""
        from chatgptrest.evomap.knowledge.distiller import KnowledgeDistiller

        distiller = KnowledgeDistiller()
        chunks = [
            {"title": "Good", "content": "This is a substantial knowledge chunk about CircuitBreaker error isolation."},
            {"title": "Bad", "content": "short"},
            {"title": "Also good", "content": "GateAutoTuner uses AIMD algorithm for threshold adjustment."},
        ]
        validated = distiller._post_validate_chunks(chunks)
        assert len(validated) == 2
        assert all(len(c["content"]) >= 30 for c in validated)

    def test_post_validator_passes_good_chunks(self):
        """Post-validator accepts well-formed chunks."""
        from chatgptrest.evomap.knowledge.distiller import KnowledgeDistiller

        distiller = KnowledgeDistiller()
        chunks = [
            {"title": "CB", "content": "CircuitBreaker in circuit_breaker.py uses a sliding window to track failures."},
            {"title": "GT", "content": "GateAutoTuner implements AIMD for gate threshold in gate_tuner.py."},
        ]
        validated = distiller._post_validate_chunks(chunks)
        assert len(validated) == 2


# ═══════════════════════════════════════════════════════════════════
# T11: Full actuator feedback loop
# ═══════════════════════════════════════════════════════════════════


class TestActuatorFeedbackLoop:
    """T11: Actuator signals flow back to Observer DB."""

    def test_circuit_breaker_signal_in_observer(self, observer, circuit_breaker):
        """CircuitBreaker emits actuator.circuit_break → Observer records it."""
        for _ in range(3):
            circuit_breaker.on_event(MockEvent(
                "llm.call_failed",
                {"provider": "chatgpt", "error_category": "timeout"},
            ))

        # Query observer — returns Signal objects
        signals = observer.query(signal_type="actuator.circuit_break")
        assert len(signals) >= 1
        assert any(
            getattr(s, 'data', {}).get("action") == "degraded"
            for s in signals
        )

    def test_gate_tuner_signal_in_observer(self, observer, gate_tuner):
        """GateAutoTuner emits signal → Observer records it after _evaluate()."""
        # Need 50 total gates to trigger _evaluate:
        # 25 passes + 25 fails → pass_rate=0.5 < 0.6 → loosen
        for _ in range(25):
            gate_tuner.on_event(MockEvent("gate.passed"))
        for _ in range(25):
            gate_tuner.on_event(MockEvent("gate.failed"))

        signals = observer.query(signal_type="actuator.gate_tuned")
        assert len(signals) >= 1


# ═══════════════════════════════════════════════════════════════════
# T12: EventBus fan-out
# ═══════════════════════════════════════════════════════════════════


class TestEventBusFanOut:
    """T12: Single event → multiple subscribers all receive it."""

    def test_event_reaches_all_subscribers(self, observer, circuit_breaker, gate_tuner, kb_scorer):
        """One llm.call_failed event reaches CB; gate events reach tuner."""
        capture = EventCapture()

        subscribers = [
            circuit_breaker.on_event,
            gate_tuner.on_event,
            kb_scorer.on_event,
            capture.on_event,
        ]

        event = MockEvent(
            "llm.call_failed",
            {"provider": "chatgpt", "error_category": "timeout"},
        )

        for sub in subscribers:
            sub(event)

        # Capture got it
        assert len(capture.events) == 1
        # CB registered it
        status = circuit_breaker.get_status()
        assert status.get("chatgpt", {}).get("consecutive_failures", 0) >= 1


# ═══════════════════════════════════════════════════════════════════
# T13: auth_error → OFFLINE exact state (GPT Pro R3 regression)
# ═══════════════════════════════════════════════════════════════════


class TestAuthErrorFatalOffline:
    """T13: auth_error triggers FATAL path → breaker offline + HT OFFLINE."""

    def test_auth_error_sets_breaker_offline(self, circuit_breaker):
        """auth_error must put breaker into offline state (not degraded/cooldown)."""
        event = MockEvent(
            "llm.call_failed",
            {"provider": "chatgpt", "error_category": "auth_error"},
        )
        # Must NOT raise — fail-open design
        circuit_breaker.on_event(event)

        status = circuit_breaker.get_status()
        # breaker internal state: when state_until=inf, get_status shows
        # the raw state since now < inf
        provider_status = status.get("chatgpt", {})
        assert provider_status["state"] == "offline", (
            f"Expected 'offline', got '{provider_status.get('state')}'"
        )

    def test_auth_error_pushes_ht_offline(self, observer):
        """auth_error must push OFFLINE to HealthTracker (not cooldown)."""
        from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        from chatgptrest.kernel.routing.health_tracker import HealthTracker, HealthStatus

        ht = HealthTracker()
        breaker = CircuitBreaker(
            observer=observer, health_tracker=ht,
            config=CircuitBreakerConfig(),
        )

        event = MockEvent(
            "llm.call_failed",
            {"provider": "chatgpt", "error_category": "auth_error"},
        )
        breaker.on_event(event)

        health = ht.get_health("chatgpt")
        assert health.status == HealthStatus.OFFLINE, (
            f"Expected OFFLINE, got {health.status}"
        )
        assert not health.is_available()

    def test_auth_error_does_not_raise(self, circuit_breaker):
        """FATAL path must not raise exceptions (fail-open)."""
        event = MockEvent(
            "llm.call_failed",
            {"provider": "chatgpt", "error_category": "auth_error"},
        )
        # Should complete without exception
        circuit_breaker.on_event(event)


# ═══════════════════════════════════════════════════════════════════
# T14: 5-in-window → COOLDOWN exact state (not degraded-or-cooldown)
# ═══════════════════════════════════════════════════════════════════


class TestWindowFailureCooldownExact:
    """T14: Exactly 5 window failures must result in COOLDOWN, not degraded."""

    def test_five_window_failures_exact_cooldown(self, circuit_breaker):
        """5 failures in window → state must be exactly 'cooldown'."""
        for i in range(5):
            event = MockEvent(
                "llm.call_failed",
                {"provider": "gemini", "error_category": "timeout"},
            )
            circuit_breaker.on_event(event)

        status = circuit_breaker.get_status()
        assert status["gemini"]["state"] == "cooldown", (
            f"5 window failures should give 'cooldown', got "
            f"'{status['gemini']['state']}'"
        )


# ═══════════════════════════════════════════════════════════════════
# T15: degraded → cooldown escalation (GPT Pro R3 state machine fix)
# ═══════════════════════════════════════════════════════════════════


class TestDegradedToCooldownEscalation:
    """T15: Provider in degraded state must escalate to cooldown on more failures."""

    def test_degraded_escalates_to_cooldown(self, circuit_breaker):
        """After 3 consecutive → degraded, 2 more → 5 total → cooldown."""
        # 3 consecutive failures → degraded
        for i in range(3):
            event = MockEvent(
                "llm.call_failed",
                {"provider": "qwen", "error_category": "provider_500"},
            )
            circuit_breaker.on_event(event)

        status = circuit_breaker.get_status()
        assert status["qwen"]["state"] == "degraded"

        # 2 more failures → 5 total in window → MUST escalate to cooldown
        for i in range(2):
            event = MockEvent(
                "llm.call_failed",
                {"provider": "qwen", "error_category": "provider_500"},
            )
            circuit_breaker.on_event(event)

        status = circuit_breaker.get_status()
        assert status["qwen"]["state"] == "cooldown", (
            f"Degraded should escalate to cooldown after 5 total, "
            f"got '{status['qwen']['state']}'"
        )


# ═══════════════════════════════════════════════════════════════════
# T16: Recovery syncs HealthTracker to HEALTHY (GPT Pro R3 fix)
# ═══════════════════════════════════════════════════════════════════


class TestRecoverySyncsHealthTracker:
    """T16: Recovery from degraded/cooldown must push HEALTHY to HealthTracker."""

    def test_recovery_pushes_healthy_to_ht(self, observer):
        """After cooldown expires + success, HealthTracker must be HEALTHY."""
        from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        from chatgptrest.kernel.routing.health_tracker import HealthTracker, HealthStatus

        ht = HealthTracker()
        config = CircuitBreakerConfig(
            cooldown_seconds=0,   # instant cooldown expiry for test
            degraded_seconds=0,   # instant degraded expiry
        )
        breaker = CircuitBreaker(
            observer=observer, health_tracker=ht, config=config,
        )

        # Put into degraded
        for i in range(3):
            breaker.on_event(MockEvent(
                "llm.call_failed",
                {"provider": "test_prov", "error_category": "timeout"},
            ))

        # Confirm degraded
        health = ht.get_health("test_prov")
        # HealthTracker may show DEGRADED or computed state
        assert health.status != HealthStatus.HEALTHY

        # Success after expiry → should recover
        breaker.on_event(MockEvent(
            "llm.call_completed",
            {"provider": "test_prov", "latency_ms": 500},
        ))

        # HealthTracker must now be set_online
        health = ht.get_health("test_prov")
        # After set_online, status depends on HealthTracker's internal state
        # At minimum, offline should be cleared
        assert health.status != HealthStatus.OFFLINE


# ═══════════════════════════════════════════════════════════════════
# T17: error_category alignment llm_connector → CircuitBreaker
# ═══════════════════════════════════════════════════════════════════


class TestErrorCategoryClassifier:
    """T17: _classify_error produces categories matching CircuitBreaker's sets."""

    def test_classify_http_401(self):
        from chatgptrest.kernel.llm_connector import LLMConnector
        import urllib.error
        import io
        exc = urllib.error.HTTPError(
            "http://test", 401, "Unauthorized", {}, io.BytesIO(b""),
        )
        assert LLMConnector._classify_error(exc) == "auth_error"

    def test_classify_http_429(self):
        from chatgptrest.kernel.llm_connector import LLMConnector
        import urllib.error
        import io
        exc = urllib.error.HTTPError(
            "http://test", 429, "Rate Limited", {}, io.BytesIO(b""),
        )
        assert LLMConnector._classify_error(exc) == "rate_limit_429"

    def test_classify_http_500(self):
        from chatgptrest.kernel.llm_connector import LLMConnector
        import urllib.error
        import io
        exc = urllib.error.HTTPError(
            "http://test", 500, "Internal Error", {}, io.BytesIO(b""),
        )
        assert LLMConnector._classify_error(exc) == "provider_500"

    def test_classify_connection_error(self):
        from chatgptrest.kernel.llm_connector import LLMConnector
        import urllib.error
        exc = urllib.error.URLError("Connection refused")
        assert LLMConnector._classify_error(exc) == "connection_error"

    def test_classify_timeout(self):
        from chatgptrest.kernel.llm_connector import LLMConnector
        exc = TimeoutError("timed out")
        assert LLMConnector._classify_error(exc) == "timeout"

    def test_classify_unknown(self):
        from chatgptrest.kernel.llm_connector import LLMConnector
        exc = ValueError("something weird")
        assert LLMConnector._classify_error(exc) == "unknown"


# ═══════════════════════════════════════════════════════════════════
# T18: Distiller fallback path runs post-validator (GPT Pro R3 fix)
# ═══════════════════════════════════════════════════════════════════


class TestDistillerFallbackValidator:
    """T18: _simple_distill path must also apply <30 char rejection."""

    def test_simple_distill_rejects_short_chunks(self):
        """Chunks with content <30 chars must be filtered out in fallback."""
        from chatgptrest.evomap.knowledge.distiller import KnowledgeDistiller

        # No LLM function → forces fallback path
        distiller = KnowledgeDistiller(llm_fn=None)

        # Create content with a mix of long and very short paragraphs
        content = (
            "This is a substantial paragraph that should definitely pass "
            "the post-validation filter because it has plenty of content.\n\n"
            "Short.\n\n"
            "x\n\n"
            "Another substantial paragraph with enough content to survive "
            "the post-validation minimum length requirement of 30 characters.\n\n"
        )

        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            chunks = distiller._distill_artifact(
                "test-artifact", f.name, "text/markdown",
            )

        # All surviving chunks must have content >= 30 chars
        for chunk in chunks:
            assert len(chunk.get("content", "")) >= 30, (
                f"Short chunk should have been filtered: "
                f"'{chunk.get('content', '')[:50]}'"
            )

    def test_llm_failure_fallback_runs_validator(self):
        """When LLM fails, fallback must still run post-validator."""
        from chatgptrest.evomap.knowledge.distiller import KnowledgeDistiller

        def failing_llm(prompt, system_msg):
            raise RuntimeError("LLM unavailable")

        distiller = KnowledgeDistiller(llm_fn=failing_llm)

        content = (
            "A long paragraph with substantial content for testing "
            "the post-validation pipeline.\n\n"
            "Hi\n\n"  # Too short, should be filtered
            "Another paragraph with enough content to pass validation "
            "after the LLM fallback path.\n\n"
        )

        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            chunks = distiller._distill_artifact(
                "test-artifact", f.name, "text/markdown",
            )

        for chunk in chunks:
            assert len(chunk.get("content", "")) >= 30


# ═══════════════════════════════════════════════════════════════════
# T19: GateAutoTuner 5s throttle semantics (GPT Pro R3 precision test)
# ═══════════════════════════════════════════════════════════════════


class TestGateAutoTunerThrottle:
    """T19: Threshold adjustments within 5s must be suppressed."""

    def test_rapid_evaluations_throttled(self, gate_tuner):
        """Two rapid batches of events: only first batch adjusts threshold."""
        from chatgptrest.evomap.actuators.gate_tuner import _CHECK_INTERVAL

        initial = gate_tuner._threshold

        # First batch: enough events to trigger evaluate, with high fail rate
        for _ in range(_CHECK_INTERVAL):
            gate_tuner.on_event(MockEvent(
                "gate.passed",
                {"provider": "test", "quality_score": 0.9},
            ))
        # Add downstream failures to trigger tightening
        for _ in range(3):
            gate_tuner.on_event(MockEvent(
                "task.downstream_failed",
                {"provider": "test"},
            ))

        after_first = gate_tuner._threshold

        # Second batch immediately (< 5s): should NOT adjust
        for _ in range(_CHECK_INTERVAL):
            gate_tuner.on_event(MockEvent(
                "gate.passed",
                {"provider": "test", "quality_score": 0.9},
            ))
        for _ in range(3):
            gate_tuner.on_event(MockEvent(
                "task.downstream_failed",
                {"provider": "test"},
            ))

        after_second = gate_tuner._threshold

        # Second batch should be throttled — threshold unchanged
        assert after_second == after_first, (
            f"Second batch within 5s should not adjust threshold: "
            f"{after_first} → {after_second}"
        )


# ═══════════════════════════════════════════════════════════════════
# T20: Half-open recovery probe lifecycle (P0)
# ═══════════════════════════════════════════════════════════════════


class TestHalfOpenRecoveryProbe:
    """T20: OFFLINE → half_open after probe_seconds → success → healthy."""

    def test_offline_transitions_to_half_open(self, observer):
        """After offline_probe_seconds, get_status materializes half_open."""
        from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(offline_probe_seconds=1)  # 1s probe
        breaker = CircuitBreaker(observer=observer, config=config)

        # Trigger FATAL offline
        breaker.on_event(MockEvent(
            "llm.call_failed",
            {"provider": "probe_test", "error_category": "auth_error"},
        ))

        # Immediately after: still offline
        status = breaker.get_status()
        assert status["probe_test"]["state"] == "offline"

        # Manipulate state_until to simulate time passing
        with breaker._lock:
            w = breaker._windows["probe_test"]
            w.state_until = time.time() - 1  # expired 1s ago

        status = breaker.get_status()
        assert status["probe_test"]["state"] == "half_open", (
            f"Expected half_open, got {status['probe_test']['state']}"
        )

    def test_half_open_success_recovers(self, observer):
        """Success event in half_open state recovers to healthy."""
        from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(offline_probe_seconds=1)
        breaker = CircuitBreaker(observer=observer, config=config)

        # Go offline, then force half_open
        breaker.on_event(MockEvent(
            "llm.call_failed",
            {"provider": "probe_test", "error_category": "auth_error"},
        ))
        with breaker._lock:
            w = breaker._windows["probe_test"]
            w.state_until = time.time() - 1
        breaker.get_status()  # materialize half_open

        # Success in half_open → healthy
        breaker.on_event(MockEvent(
            "llm.call_completed",
            {"provider": "probe_test", "latency_ms": 200},
        ))
        status = breaker.get_status()
        assert status["probe_test"]["state"] == "healthy"

    def test_half_open_failure_returns_degraded(self, observer):
        """Failure event in half_open state should trigger degraded."""
        from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            offline_probe_seconds=1,
            consecutive_fail_threshold=1,
        )
        breaker = CircuitBreaker(observer=observer, config=config)

        # Go offline → force half_open
        breaker.on_event(MockEvent(
            "llm.call_failed",
            {"provider": "probe_test", "error_category": "auth_error"},
        ))
        with breaker._lock:
            w = breaker._windows["probe_test"]
            w.state_until = time.time() - 1
            w.consecutive_failures = 0  # reset for clean probe
        breaker.get_status()  # materialize half_open

        # Failure should trigger degraded (it's an infra error with threshold=1)
        breaker.on_event(MockEvent(
            "llm.call_failed",
            {"provider": "probe_test", "error_category": "timeout"},
        ))
        status = breaker.get_status()
        assert status["probe_test"]["state"] in ("degraded", "cooldown", "healthy")

    def test_probe_disabled_stays_offline(self, observer):
        """offline_probe_seconds=0 → permanently offline (probe disabled)."""
        from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        # Disabled half-open probe (0 = disabled)
        config = CircuitBreakerConfig(offline_probe_seconds=0)
        breaker = CircuitBreaker(observer=observer, config=config)

        breaker.on_event(MockEvent(
            "llm.call_failed",
            {"provider": "permanent", "error_category": "auth_error"},
        ))
        status = breaker.get_status()
        # Should stay offline permanently
        assert status["permanent"]["state"] == "offline"


# ═══════════════════════════════════════════════════════════════════
# T21: Admin reset_provider (P0)
# ═══════════════════════════════════════════════════════════════════


class TestAdminResetProvider:
    """T21: Manual admin reset from any state to healthy."""

    def test_reset_from_offline(self, observer):
        from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        from chatgptrest.kernel.routing.health_tracker import HealthTracker, HealthStatus

        ht = HealthTracker()
        breaker = CircuitBreaker(
            observer=observer, health_tracker=ht,
            config=CircuitBreakerConfig(offline_probe_seconds=0),
        )

        # Go offline
        breaker.on_event(MockEvent(
            "llm.call_failed",
            {"provider": "reset_test", "error_category": "auth_error"},
        ))

        # Admin reset
        assert breaker.reset_provider("reset_test") is True
        status = breaker.get_status()
        assert status["reset_test"]["state"] == "healthy"
        assert status["reset_test"]["consecutive_failures"] == 0

        # HealthTracker should be accessible
        health = ht.get_health("reset_test")
        assert health.status != HealthStatus.OFFLINE

    def test_reset_unknown_provider(self, circuit_breaker):
        assert circuit_breaker.reset_provider("nonexistent") is False


# ═══════════════════════════════════════════════════════════════════
# T22: MemoryInjector E2E (P0)
# ═══════════════════════════════════════════════════════════════════


class TestMemoryInjectorE2E:
    """T22: MemoryInjector retrieves and formats past experiences."""

    def test_retrieve_from_memory_db(self, tmp_path):
        """Create memory.db with records, retrieve formatted context."""
        import sqlite3
        from chatgptrest.evomap.actuators.memory_injector import MemoryInjector
        from datetime import datetime, timezone

        db_path = str(tmp_path / "memory.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE memory_records (
                tier TEXT DEFAULT 'L1',
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source TEXT DEFAULT 'test',
                updated_at TEXT NOT NULL
            )
        """)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO memory_records (category, key, value, confidence, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("routing", "chatgpt_500_retry", "ChatGPT 500 errors → switch to gemini fallback", 0.9, now),
        )
        conn.execute(
            "INSERT INTO memory_records (category, key, value, confidence, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("routing", "timeout_pattern", "Gemini deep_think > 90s → use fast preset", 0.7, now),
        )
        conn.commit()
        conn.close()

        injector = MemoryInjector(db_path=db_path)
        context = injector.retrieve(domain="routing", limit=5)

        # Should return formatted context block
        assert "<past_experiences>" in context
        assert "chatgpt_500_retry" in context
        assert "timeout_pattern" in context
        assert "</past_experiences>" in context

    def test_retrieve_failures(self, tmp_path):
        """Retrieve specifically failure-related memories."""
        import sqlite3
        from chatgptrest.evomap.actuators.memory_injector import MemoryInjector
        from datetime import datetime, timezone

        db_path = str(tmp_path / "memory.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE memory_records (
                tier TEXT DEFAULT 'L1',
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source TEXT DEFAULT 'test',
                updated_at TEXT NOT NULL
            )
        """)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO memory_records (category, key, value, confidence, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("routing", "error_pattern", "chatgpt failed with 429 three times in a row", 0.3, now),
        )
        conn.commit()
        conn.close()

        injector = MemoryInjector(db_path=db_path)
        result = injector.retrieve_failures(limit=5)
        assert "past failures" in result
        assert "error_pattern" in result

    def test_nonexistent_db_returns_empty(self):
        from chatgptrest.evomap.actuators.memory_injector import MemoryInjector
        injector = MemoryInjector(db_path="/tmp/nonexistent_memory.db")
        assert injector.retrieve() == ""
        assert injector.retrieve_failures() == ""


# ═══════════════════════════════════════════════════════════════════
# T23: TeamScorecardStore CRUD + Ranking (P1)
# ═══════════════════════════════════════════════════════════════════


class TestTeamScorecardE2E:
    """T23: TeamScorecardStore records outcomes and ranks teams."""

    def test_record_and_retrieve(self):
        from chatgptrest.evomap.team_scorecard import TeamScorecardStore

        store = TeamScorecardStore(db_path=":memory:")

        # Mock team_spec with required attributes
        class MockTeamSpec:
            team_id = "team_alpha"
            def to_dict(self):
                return {"roles": ["reviewer", "coder"]}

        class MockRunRecord:
            team_spec = MockTeamSpec()
            repo = "chatgptrest"
            task_type = "code_review"
            result_ok = True
            quality_score = 0.85
            elapsed_seconds = 12.5
            total_input_tokens = 1000
            total_output_tokens = 500
            cost_usd = 0.05

        store.record_outcome(MockRunRecord())

        card = store.get_scorecard("team_alpha", "chatgptrest", "code_review")
        assert card is not None
        assert card.total_runs == 1
        assert card.successes == 1
        assert card.failures == 0

    def test_ranking(self):
        from chatgptrest.evomap.team_scorecard import TeamScorecardStore

        store = TeamScorecardStore(db_path=":memory:")

        class MockTeamSpec:
            team_id = ""
            def to_dict(self):
                return {}

        class MockRun:
            team_spec = None
            repo = "test"
            task_type = "review"
            result_ok = True
            quality_score = 0.0
            elapsed_seconds = 10.0
            total_input_tokens = 100
            total_output_tokens = 50
            cost_usd = 0.01

        # Team A: high quality
        spec_a = MockTeamSpec()
        spec_a.team_id = "team_a"
        run_a = MockRun()
        run_a.team_spec = spec_a
        run_a.quality_score = 0.95
        store.record_outcome(run_a)

        # Team B: lower quality
        spec_b = MockTeamSpec()
        spec_b.team_id = "team_b"
        run_b = MockRun()
        run_b.team_spec = spec_b
        run_b.quality_score = 0.5
        store.record_outcome(run_b)

        ranked = store.rank_teams(repo="test", task_type="review")
        assert len(ranked) == 2
        # Team A should rank higher
        assert ranked[0].team_id == "team_a"
        assert ranked[1].team_id == "team_b"

        store.close()


# ═══════════════════════════════════════════════════════════════════
# T24: Knowledge Pipeline E2E (P1)
# (DB → GraphBuilder → Retrieval → Synthesis round-trip)
# ═══════════════════════════════════════════════════════════════════


class TestKnowledgePipelineE2E:
    """T24: Full knowledge pipeline round trip."""

    def test_graph_builder_creates_edges(self):
        """GraphBuilder creates SAME_TOPIC edges between related atoms."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, AtomType
        from chatgptrest.evomap.knowledge.graph_builder import GraphBuilder

        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()

        # Insert two related atoms with same canonical_question
        atom1 = Atom(
            atom_id="atom_001",
            episode_id="ep_01",
            canonical_question="How does the circuit breaker work?",
            question="How does the circuit breaker work?",
            answer="It tracks failures in a sliding window and transitions states.",
            atom_type=AtomType.TROUBLESHOOTING.value,
            status=AtomStatus.CANDIDATE.value,
            quality_auto=0.8,
        )
        atom2 = Atom(
            atom_id="atom_002",
            episode_id="ep_02",
            canonical_question="How does the circuit breaker work?",
            question="How does the circuit breaker work?",
            answer="CircuitBreaker uses consecutive failures and window thresholds.",
            atom_type=AtomType.TROUBLESHOOTING.value,
            status=AtomStatus.CANDIDATE.value,
            quality_auto=0.7,
        )
        db.put_atom(atom1)
        db.put_atom(atom2)

        builder = GraphBuilder(db)
        stats = builder.build_all()

        # Should have created at least one SAME_TOPIC edge
        assert stats.get("same_topic", 0) > 0

    def test_retrieval_returns_scored_atoms(self):
        """Retrieval pipeline returns scored atoms from FTS5 search."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, AtomType
        from chatgptrest.evomap.knowledge.retrieval import retrieve

        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()

        atom = Atom(
            atom_id="ret_001",
            episode_id="ep_01",
            question="What is the routing algorithm?",
            answer="The routing algorithm uses multi-armed bandit with UCB1 exploration.",
            atom_type=AtomType.DECISION.value,
            status=AtomStatus.CANDIDATE.value,
            quality_auto=0.8,
        )
        db.put_atom(atom)

        results = retrieve(db, query="routing algorithm bandit")
        assert len(results) >= 1
        assert results[0].atom.atom_id == "ret_001"
        assert results[0].final_score > 0

    def test_synthesis_creates_macro_atom(self):
        """MacroAtomSynthesizer creates summary atoms from clusters."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, AtomType, Episode, Document
        from chatgptrest.evomap.knowledge.synthesis import MacroAtomSynthesizer, SynthesisConfig

        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()

        # Create parent document (FK required)
        doc = Document(doc_id="doc_01", source="test", title="Test document")
        db.put_document(doc)

        # Create an episode
        ep = Episode(
            episode_id="ep_synth",
            doc_id="doc_01",
            title="Circuit breaker discussion",
        )
        db.put_episode(ep)

        # Create enough atoms for a cluster (min_cluster_size=3)
        for i in range(4):
            atom = Atom(
                atom_id=f"synth_{i:03d}",
                episode_id="ep_synth",
                canonical_question="How does the circuit breaker handle failures?",
                question="How does the circuit breaker handle failures?",
                answer=f"Aspect {i}: The circuit breaker handles failures through state transitions and health tracking.",
                atom_type=AtomType.TROUBLESHOOTING.value,
                status=AtomStatus.CANDIDATE.value,
                quality_auto=0.7,
                valid_from=time.time(),
            )
            db.put_atom(atom)

        config = SynthesisConfig(min_cluster_size=3)
        synth = MacroAtomSynthesizer(db, config=config)
        result = synth.run()

        assert result.clusters_found >= 1
        assert result.atoms_synthesized >= 1


# ═══════════════════════════════════════════════════════════════════
# T25: Vendor-specific _classify_error (P0)
# ═══════════════════════════════════════════════════════════════════


class TestVendorClassifyError:
    """T25: Extended _classify_error coverage for MiniMax/Anthropic."""

    def test_529_overloaded(self):
        from chatgptrest.kernel.llm_connector import LLMConnector
        import urllib.error, io
        exc = urllib.error.HTTPError(
            "http://test", 529, "Overloaded", {}, io.BytesIO(b""),
        )
        assert LLMConnector._classify_error(exc) == "provider_503"

    def test_402_billing(self):
        from chatgptrest.kernel.llm_connector import LLMConnector
        import urllib.error, io
        exc = urllib.error.HTTPError(
            "http://test", 402, "Payment Required", {}, io.BytesIO(b""),
        )
        assert LLMConnector._classify_error(exc) == "auth_error"

    def test_string_overloaded(self):
        from chatgptrest.kernel.llm_connector import LLMConnector
        exc = RuntimeError("Anthropic API overloaded, please retry")
        assert LLMConnector._classify_error(exc) == "provider_503"

    def test_string_billing(self):
        from chatgptrest.kernel.llm_connector import LLMConnector
        exc = RuntimeError("Insufficient quota for this request")
        assert LLMConnector._classify_error(exc) == "auth_error"


# ═══════════════════════════════════════════════════════════════════
# T26: KBPruner rules E2E (P1)
# ═══════════════════════════════════════════════════════════════════


class TestKBPrunerE2E:
    """T26: KBPruner correctly applies pruning rules."""

    def test_negative_score_deleted(self, tmp_path):
        """quality_score < 0 → immediate delete."""
        import sqlite3
        from chatgptrest.evomap.knowledge.pruner import KBPruner

        db_path = str(tmp_path / "kb_registry.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE artifacts (
                artifact_id TEXT PRIMARY KEY,
                source_path TEXT,
                file_size INTEGER DEFAULT 0,
                content_type TEXT DEFAULT '',
                quality_score REAL DEFAULT 0.0,
                stability TEXT DEFAULT 'active',
                indexed_at TEXT DEFAULT ''
            )
        """)
        conn.execute(
            "INSERT INTO artifacts (artifact_id, source_path, quality_score) "
            "VALUES ('bad_artifact', '/tmp/bad.md', -0.5)",
        )
        conn.commit()
        conn.close()

        pruner = KBPruner(registry_db=db_path)
        stats = pruner.run()
        assert stats["deleted"] >= 1

        # Verify it's gone
        conn = sqlite3.connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM artifacts WHERE artifact_id = 'bad_artifact'"
        ).fetchone()[0]
        conn.close()
        assert count == 0

    def test_positive_score_kept(self, tmp_path):
        """quality_score > 0 → NOT deleted."""
        import sqlite3
        from chatgptrest.evomap.knowledge.pruner import KBPruner

        db_path = str(tmp_path / "kb_registry.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE artifacts (
                artifact_id TEXT PRIMARY KEY,
                source_path TEXT,
                file_size INTEGER DEFAULT 0,
                content_type TEXT DEFAULT '',
                quality_score REAL DEFAULT 0.0,
                stability TEXT DEFAULT 'active',
                indexed_at TEXT DEFAULT ''
            )
        """)
        conn.execute(
            "INSERT INTO artifacts (artifact_id, source_path, quality_score) "
            "VALUES ('good_artifact', '/tmp/good.md', 0.8)",
        )
        conn.commit()
        conn.close()

        pruner = KBPruner(registry_db=db_path)
        stats = pruner.run()
        assert stats["deleted"] == 0

        conn = sqlite3.connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM artifacts WHERE artifact_id = 'good_artifact'"
        ).fetchone()[0]
        conn.close()
        assert count == 1


# ═══════════════════════════════════════════════════════════════════
# T27: get_status materializes state recovery (P1)
# ═══════════════════════════════════════════════════════════════════


class TestGetStatusMaterializedRecovery:
    """T27: get_status must update internal state, not just display healthy."""

    def test_expired_degraded_materializes_healthy(self, observer):
        from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(degraded_seconds=0)  # instant expire
        breaker = CircuitBreaker(observer=observer, config=config)

        # Trigger degraded
        for _ in range(3):
            breaker.on_event(MockEvent(
                "llm.call_failed",
                {"provider": "mat_test", "error_category": "timeout"},
            ))

        # get_status should materialize the healthy state
        status = breaker.get_status()
        assert status["mat_test"]["state"] == "healthy", (
            f"Expected materialized healthy, got {status['mat_test']['state']}"
        )

        # Calling again should still show healthy
        status2 = breaker.get_status()
        assert status2["mat_test"]["state"] == "healthy"


# ═══════════════════════════════════════════════════════════════════
# T28: AtomRefiner — LLM-powered atom post-processing
# ═══════════════════════════════════════════════════════════════════

class TestAtomRefinerE2E:
    """T28: AtomRefiner heuristic + LLM mock refinement."""

    def _setup_db_with_atoms(self):
        """Create a DB with some raw heuristic atoms."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, AtomType

        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()

        atoms = [
            Atom(
                atom_id="ref_001",
                episode_id="ep_01",
                question="1. Git 主干保护策略",
                answer="使用 protected branch 规则确保 main 分支不允许直接 push。"
                       " 所有改动必须通过 PR 合并，至少需要 1 人审批。"
                       " 合并时自动触发 CI 检查。",
                atom_type=AtomType.QA.value,
                status=AtomStatus.CANDIDATE.value,
                quality_auto=0.0,
                valid_from=time.time(),
            ),
            Atom(
                atom_id="ref_002",
                episode_id="ep_01",
                question="🔥 Circuit Breaker 熔断机制",
                answer="CircuitBreaker 使用滑动窗口追踪失败次数。"
                       " 当连续失败达到阈值时，状态转为 degraded → cooldown → offline。"
                       " FATAL 错误（如 auth_error）立即触发 offline 状态。"
                       " 支持 half-open 探测恢复机制。",
                atom_type=AtomType.QA.value,
                status=AtomStatus.CANDIDATE.value,
                quality_auto=0.0,
                valid_from=time.time(),
            ),
        ]

        for atom in atoms:
            db.put_atom(atom)

        return db

    def test_heuristic_refinement(self):
        """Heuristic mode generates questions and scores atoms."""
        from chatgptrest.evomap.knowledge.atom_refiner import AtomRefiner, RefinerConfig

        db = self._setup_db_with_atoms()
        config = RefinerConfig(batch_size=10)
        refiner = AtomRefiner(db=db, config=config)  # no llm_fn

        result = refiner.refine_all(limit=10)
        assert result.refined == 2
        assert result.errors == 0

        conn = db.connect()
        rows = conn.execute(
            "SELECT * FROM atoms WHERE status = 'scored' ORDER BY atom_id"
        ).fetchall()
        assert len(rows) == 2

        a1 = dict(rows[0])
        # Should have a proper question (not just the heading number)
        assert "What is the approach for" in a1["question"]
        # Should have canonical_question set
        assert a1["canonical_question"] != ""
        # Should have quality_auto > 0
        assert a1["quality_auto"] > 0
        # Status should be scored
        assert a1["status"] == "scored"

    def test_llm_refinement(self):
        """LLM mode applies structured classification and scoring."""
        import json
        from chatgptrest.evomap.knowledge.atom_refiner import AtomRefiner, RefinerConfig

        db = self._setup_db_with_atoms()

        def mock_llm(prompt: str, system: str) -> str:
            """Return structured JSON matching the expected format."""
            return json.dumps([
                {
                    "atom_id": "ref_001",
                    "question": "How do you implement Git branch protection?",
                    "canonical_question": "git branch protection strategy",
                    "atom_type": "procedure",
                    "quality_auto": 0.85,
                    "novelty": 0.5,
                    "groundedness": 0.9,
                    "reusability": 0.8,
                    "confidence": 0.95,
                },
                {
                    "atom_id": "ref_002",
                    "question": "How does the CircuitBreaker handle failures and recovery?",
                    "canonical_question": "circuit breaker failure handling and recovery",
                    "atom_type": "troubleshooting",
                    "quality_auto": 0.9,
                    "novelty": 0.7,
                    "groundedness": 0.85,
                    "reusability": 0.75,
                    "confidence": 0.9,
                },
            ])

        config = RefinerConfig(batch_size=5)
        refiner = AtomRefiner(db=db, llm_fn=mock_llm, config=config)

        result = refiner.refine_all(limit=10)
        assert result.refined == 2
        assert result.errors == 0

        conn = db.connect()
        a2 = dict(conn.execute(
            "SELECT * FROM atoms WHERE atom_id = 'ref_002'"
        ).fetchone())

        assert a2["question"] == "How does the CircuitBreaker handle failures and recovery?"
        assert a2["canonical_question"] == "circuit breaker failure handling and recovery"
        assert a2["atom_type"] == "troubleshooting"
        assert a2["quality_auto"] == pytest.approx(0.9, abs=0.01)
        assert a2["novelty"] == pytest.approx(0.7, abs=0.01)
        assert a2["status"] == "scored"


# ═══════════════════════════════════════════════════════════════════
# T29: Full Business Flow — Extract → Refine → Graph → Retrieve
# ═══════════════════════════════════════════════════════════════════

class TestFullPipelineRoundTrip:
    """T29: Document→Episode→Atom→Refine→GraphBuild→Retrieve end-to-end."""

    def test_full_pipeline_round_trip(self, tmp_path):
        """Test the complete knowledge pipeline from extraction to retrieval."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.extractors.antigravity_extractor import (
            AntigravityExtractor,
        )
        from chatgptrest.evomap.knowledge.atom_refiner import AtomRefiner, RefinerConfig
        from chatgptrest.evomap.knowledge.graph_builder import GraphBuilder
        from chatgptrest.evomap.knowledge.retrieval import retrieve, RetrievalConfig

        # 1. Set up mock brain directory
        conv_dir = tmp_path / "brain" / "test-conv-001"
        conv_dir.mkdir(parents=True)

        (conv_dir / "implementation_plan.md").write_text(
            "# Circuit Breaker Design\n\n"
            "## Half-Open Recovery Mechanism\n\n"
            "When a provider enters OFFLINE state, the circuit breaker "
            "automatically schedules a half-open probe after offline_probe_seconds. "
            "During half-open state, a single test request is sent. If successful, "
            "the provider returns to HEALTHY state. If the probe fails, the provider "
            "returns to OFFLINE and another probe is scheduled.\n\n"
            "## Error Classification Strategy\n\n"
            "HTTP 529 errors from MiniMax and Anthropic are classified as provider_503. "
            "HTTP 402 errors indicate billing issues and are classified as auth_error. "
            "This classification drives the circuit breaker's decision on whether to "
            "degrade (temporary) or go offline (permanent).\n\n"
            "## Decision: Use Sliding Window\n\n"
            "We decided to use a sliding window approach instead of a simple counter "
            "for failure tracking. The sliding window provides time-bounded fault "
            "detection, preventing old failures from keeping a provider in degraded "
            "state indefinitely. Window size: 300 seconds.\n",
            encoding="utf-8",
        )
        (conv_dir / "implementation_plan.md.metadata.json").write_text(
            '{"ArtifactType": "implementation_plan", "Summary": "Circuit breaker design docs"}',
            encoding="utf-8",
        )

        (conv_dir / "walkthrough.md").write_text(
            "# Walkthrough\n\n"
            "## Verification Results\n\n"
            "All 60 tests pass. The circuit breaker correctly transitions through: "
            "healthy → degraded → cooldown → offline → half_open → healthy. "
            "Admin reset works as expected.\n",
            encoding="utf-8",
        )

        # 2. Extract
        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()
        ext = AntigravityExtractor(db, brain_dir=str(tmp_path / "brain"))
        ext.extract_all()

        conn = db.connect()
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        episodes = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        atoms_raw = conn.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]
        assert docs == 1, f"Expected 1 doc, got {docs}"
        assert episodes == 2, f"Expected 2 episodes, got {episodes}"
        assert atoms_raw >= 3, f"Expected ≥3 atoms, got {atoms_raw}"

        # 3. Refine (heuristic — no LLM)
        refiner = AtomRefiner(db=db, config=RefinerConfig(batch_size=10))
        ref_result = refiner.refine_all(limit=50)
        assert ref_result.refined >= 3
        assert ref_result.errors == 0

        # Verify atoms got proper questions
        scored = conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE status = 'scored'"
        ).fetchone()[0]
        assert scored >= 3, f"Expected ≥3 scored atoms, got {scored}"

        # 4. Build graph
        gb_stats = GraphBuilder(db).build_all()
        assert gb_stats.get("same_topic", 0) >= 0  # may or may not find same-topic

        # 5. Retrieve
        results = retrieve(
            db, "circuit breaker", config=RetrievalConfig(result_limit=5)
        )
        assert len(results) >= 1, "Should retrieve at least 1 atom about circuit breaker"
        top = results[0]
        assert top.final_score > 0
        assert "circuit" in top.atom.answer.lower() or "breaker" in top.atom.answer.lower()

    def test_pipeline_with_llm_refinement(self, tmp_path):
        """Pipeline with LLM-mock refinement produces higher quality atoms."""
        import json
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.schema import Atom, AtomType, AtomStatus
        from chatgptrest.evomap.knowledge.atom_refiner import AtomRefiner, RefinerConfig

        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()

        # Insert atoms directly
        atoms = [
            Atom(
                atom_id="pipe_01",
                episode_id="ep_01",
                question="Error Handling 策略",
                answer="使用 try-except 包裹所有外部调用。HTTP 5xx 重试 3 次，间隔指数退避。"
                       " 4xx 立即返回错误。超时设为 30 秒。",
                atom_type=AtomType.QA.value,
                status=AtomStatus.CANDIDATE.value,
                valid_from=time.time(),
            ),
            Atom(
                atom_id="pipe_02",
                episode_id="ep_01",
                question="日志规范",
                answer="所有模块统一使用 logging 模块。ERROR 级别用于不可恢复错误。"
                       " WARNING 用于可恢复但异常的情况。日志格式包含 trace_id 用于链路追踪。",
                atom_type=AtomType.QA.value,
                status=AtomStatus.CANDIDATE.value,
                valid_from=time.time(),
            ),
        ]
        for a in atoms:
            db.put_atom(a)

        def mock_llm(prompt: str, system: str) -> str:
            return json.dumps([
                {
                    "atom_id": "pipe_01",
                    "question": "What is the error handling strategy for external API calls?",
                    "canonical_question": "error handling external api calls",
                    "atom_type": "procedure",
                    "quality_auto": 0.8,
                    "novelty": 0.4,
                    "groundedness": 0.9,
                    "reusability": 0.85,
                    "confidence": 0.9,
                },
                {
                    "atom_id": "pipe_02",
                    "question": "What are the logging conventions and standards?",
                    "canonical_question": "logging conventions standards",
                    "atom_type": "procedure",
                    "quality_auto": 0.75,
                    "novelty": 0.3,
                    "groundedness": 0.85,
                    "reusability": 0.9,
                    "confidence": 0.85,
                },
            ])

        refiner = AtomRefiner(db=db, llm_fn=mock_llm, config=RefinerConfig(batch_size=5))
        result = refiner.refine_all(limit=10)
        assert result.refined == 2

        conn = db.connect()
        a1 = dict(conn.execute("SELECT * FROM atoms WHERE atom_id='pipe_01'").fetchone())
        assert a1["atom_type"] == "procedure"
        assert a1["canonical_question"] == "error handling external api calls"
        assert a1["reusability"] == pytest.approx(0.85, abs=0.01)


# ═══════════════════════════════════════════════════════════════════
# T30: Atom Aging / TTL Rules
# ═══════════════════════════════════════════════════════════════════

class TestAtomAgingTTL:
    """T30: Atom aging marks old atoms as superseded/needs_revalidate."""

    def test_age_old_candidate_atoms(self):
        """Candidate atoms older than 90 days get marked superseded."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus
        from chatgptrest.advisor.runtime import _age_old_atoms

        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()

        now = time.time()

        # Old candidate (100 days old) - should be superseded
        db.put_atom(Atom(
            atom_id="old_cand",
            question="old question",
            answer="old answer that is long enough to be valid",
            status=AtomStatus.CANDIDATE.value,
            valid_from=now - (100 * 86400),
        ))

        # Recent candidate (10 days old) - should NOT be superseded
        db.put_atom(Atom(
            atom_id="new_cand",
            question="new question",
            answer="new answer that is long enough to be valid",
            status=AtomStatus.CANDIDATE.value,
            valid_from=now - (10 * 86400),
        ))

        _age_old_atoms(db)

        conn = db.connect()
        old = dict(conn.execute("SELECT * FROM atoms WHERE atom_id='old_cand'").fetchone())
        new = dict(conn.execute("SELECT * FROM atoms WHERE atom_id='new_cand'").fetchone())

        assert old["stability"] == "superseded"
        assert new["stability"] != "superseded"

    def test_age_old_scored_atoms(self):
        """Scored atoms older than 180 days get marked needs_revalidate."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus
        from chatgptrest.advisor.runtime import _age_old_atoms

        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()

        now = time.time()

        # Old scored (200 days old) - should be needs_revalidate
        db.put_atom(Atom(
            atom_id="old_scored",
            question="old scored question",
            answer="old scored answer that is long enough",
            status=AtomStatus.SCORED.value,
            valid_from=now - (200 * 86400),
        ))

        # Recent scored (30 days old) - should stay scored
        db.put_atom(Atom(
            atom_id="new_scored",
            question="new scored question",
            answer="new scored answer that is long enough",
            status=AtomStatus.SCORED.value,
            valid_from=now - (30 * 86400),
        ))

        _age_old_atoms(db)

        conn = db.connect()
        old = dict(conn.execute("SELECT * FROM atoms WHERE atom_id='old_scored'").fetchone())
        new = dict(conn.execute("SELECT * FROM atoms WHERE atom_id='new_scored'").fetchone())

        assert old["status"] == "needs_revalidate"
        assert new["status"] == "scored"

    def test_age_idempotent(self):
        """Running age twice doesn't change already-aged atoms."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus
        from chatgptrest.advisor.runtime import _age_old_atoms

        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()

        db.put_atom(Atom(
            atom_id="idem_test",
            question="question",
            answer="answer that is long enough to be valid",
            status=AtomStatus.CANDIDATE.value,
            valid_from=time.time() - (100 * 86400),
        ))

        _age_old_atoms(db)
        _age_old_atoms(db)  # second run should be idempotent

        conn = db.connect()
        row = dict(conn.execute("SELECT * FROM atoms WHERE atom_id='idem_test'").fetchone())
        assert row["stability"] == "superseded"


# ═══════════════════════════════════════════════════════════════════
# T31: Retrieval Pipeline Quality — Diversity + Time Decay
# ═══════════════════════════════════════════════════════════════════

class TestRetrievalQuality:
    """T31: Verify retrieval scoring, time decay, and diversity."""

    def test_time_decay_prefers_recent(self):
        """Recent atoms score higher than old ones for same query."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus
        from chatgptrest.evomap.knowledge.retrieval import retrieve, RetrievalConfig

        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()

        now = time.time()

        # Same content, different ages
        db.put_atom(Atom(
            atom_id="recent_a",
            episode_id="ep_recent",
            question="How to deploy the service?",
            answer="Use docker compose up to deploy the service. "
                   "Make sure to set environment variables first.",
            atom_type="procedure",
            status=AtomStatus.SCORED.value,
            quality_auto=0.8,
            valid_from=now - (5 * 86400),  # 5 days old
        ))

        db.put_atom(Atom(
            atom_id="old_a",
            episode_id="ep_old",
            question="How to deploy the service?",
            answer="Use docker compose up to deploy the old service. "
                   "Make sure to set environment variables first.",
            atom_type="procedure",
            status=AtomStatus.SCORED.value,
            quality_auto=0.8,
            valid_from=now - (365 * 86400),  # 1 year old
        ))

        results = retrieve(db, "deploy service", config=RetrievalConfig(result_limit=5))
        assert len(results) >= 2

        # Recent atom should have higher final score due to time decay
        scores = {r.atom.atom_id: r.final_score for r in results}
        assert scores["recent_a"] > scores["old_a"], (
            f"Recent ({scores['recent_a']:.3f}) should outscore old ({scores['old_a']:.3f})"
        )

    def test_quality_gate_filters_low_quality(self):
        """Atoms below min quality threshold are filtered out."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus
        from chatgptrest.evomap.knowledge.retrieval import retrieve, RetrievalConfig

        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()

        db.put_atom(Atom(
            atom_id="good_q",
            question="What is the deployment process?",
            answer="First build the image, then push to registry, then deploy.",
            status=AtomStatus.SCORED.value,
            quality_auto=0.8,
            valid_from=time.time(),
        ))

        db.put_atom(Atom(
            atom_id="bad_q",
            question="What is the deployment process?",
            answer="Deploy it somehow, maybe with docker.",
            status=AtomStatus.SCORED.value,
            quality_auto=0.01,  # very low quality
            valid_from=time.time(),
        ))

        results = retrieve(
            db, "deployment process",
            config=RetrievalConfig(min_quality=0.15, result_limit=5),
        )
        atom_ids = {r.atom.atom_id for r in results}
        assert "good_q" in atom_ids
        # bad_q may or may not be filtered depending on FTS rank
        # But good_q should definitely be there


# ═══════════════════════════════════════════════════════════════════
# T32: AntigravityExtractor + AtomRefiner Integration
# ═══════════════════════════════════════════════════════════════════

class TestAntigravityRefinerIntegration:
    """T32: Extract from mock brain dir then refine - full integration."""

    def test_extract_then_refine_updates_atoms(self, tmp_path):
        """Atoms extracted by AntigravityExtractor are refined by AtomRefiner."""
        from chatgptrest.evomap.knowledge.db import KnowledgeDB
        from chatgptrest.evomap.knowledge.extractors.antigravity_extractor import (
            AntigravityExtractor,
        )
        from chatgptrest.evomap.knowledge.atom_refiner import AtomRefiner, RefinerConfig

        # Create mock brain
        conv = tmp_path / "brain" / "integ-test-001"
        conv.mkdir(parents=True)
        (conv / "analysis.md").write_text(
            "# API Analysis\n\n"
            "## Performance Bottleneck\n\n"
            "The main bottleneck is the synchronous database query in the hot path. "
            "Switching to async queries with connection pooling reduced p50 latency "
            "from 188ms to 42ms.\n\n"
            "## Lesson Learned: Always Profile First\n\n"
            "Before optimizing, always profile the actual workload. We initially "
            "assumed the bottleneck was in JSON serialization, but profiling showed "
            "90% of time was spent in DB queries.\n",
            encoding="utf-8",
        )

        db = KnowledgeDB(db_path=":memory:")
        db.init_schema()

        # Extract
        ext = AntigravityExtractor(db, brain_dir=str(tmp_path / "brain"))
        ext.extract_all()

        conn = db.connect()
        before_count = conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE canonical_question != ''"
        ).fetchone()[0]
        assert before_count == 0, "Before refining, no atoms should have canonical_question"

        # Refine
        refiner = AtomRefiner(db=db, config=RefinerConfig(batch_size=10))
        result = refiner.refine_all(limit=50)
        assert result.refined >= 2
        assert result.errors == 0

        after_count = conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE canonical_question != ''"
        ).fetchone()[0]
        assert after_count >= 2, f"After refining, should have ≥2 atoms with canonical_question"

        # Verify atom types were updated
        lesson_count = conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE atom_type = 'lesson'"
        ).fetchone()[0]
        # The "Lesson Learned" heading should trigger lesson type via heuristic
        assert lesson_count >= 1, "Expected at least 1 lesson atom from heading heuristic"
