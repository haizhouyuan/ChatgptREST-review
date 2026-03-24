from __future__ import annotations

from dataclasses import dataclass, field
import time

from chatgptrest.evomap.actuators import ActuatorMode
from chatgptrest.evomap.actuators.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from chatgptrest.evomap.actuators.gate_tuner import GateAutoTuner
from chatgptrest.evomap.actuators.kb_scorer import KBScorer
from chatgptrest.evomap.actuators.memory_injector import MemoryInjector


@dataclass
class MockEvent:
    event_type: str
    data: dict = field(default_factory=dict)
    trace_id: str = "trace-001"
    timestamp: float = field(default_factory=time.time)


class DummyObserver:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.scores: dict[str, float] = {}

    def record_event(
        self,
        trace_id: str,
        signal_type: str,
        source: str,
        domain: str = "",
        data: dict | None = None,
    ) -> str:
        self.events.append(
            {
                "trace_id": trace_id,
                "signal_type": signal_type,
                "source": source,
                "domain": domain,
                "data": data or {},
            }
        )
        return f"sig-{len(self.events)}"

    def update_kb_score(self, artifact_id: str, delta: float) -> float:
        self.scores[artifact_id] = self.scores.get(artifact_id, 0.5) + delta
        return self.scores[artifact_id]


def test_gate_tuner_exposes_governance_and_audits_threshold_changes():
    observer = DummyObserver()
    tuner = GateAutoTuner(observer=observer, initial_threshold=0.6)

    assert tuner.describe_governance() == {
        "name": "gate_tuner",
        "mode": "active",
        "owner": "evomap.runtime",
        "candidate_version": "gate-tuner-live",
        "rollback_trigger": "threshold_regression_or_false_gate_decisions",
    }

    for _ in range(3):
        tuner.on_event(MockEvent("dispatch.task_failed"))
    for _ in range(47):
        tuner.on_event(MockEvent("gate.passed"))
    for _ in range(3):
        tuner.on_event(MockEvent("gate.failed"))

    trail = tuner.get_audit_trail()
    assert trail
    last = trail[-1]
    assert last["category"] == "state_change"
    assert last["action"] == "threshold_adjusted"
    assert last["previous_state"] == "0.60"
    assert last["new_state"] == "0.65"
    assert observer.events[-1]["data"]["governance"]["mode"] == "active"
    assert observer.events[-1]["data"]["audit_event"]["action"] == "threshold_adjusted"


def test_circuit_breaker_records_governance_and_state_transition_audits():
    observer = DummyObserver()
    breaker = CircuitBreaker(
        observer=observer,
        config=CircuitBreakerConfig(
            consecutive_fail_threshold=2,
            window_fail_threshold=5,
            degraded_seconds=30,
        ),
    )

    assert breaker.describe_governance()["candidate_version"] == "circuit-breaker-live"

    breaker.on_event(MockEvent("llm.call_failed", {"provider": "gemini", "error_category": "timeout"}))
    breaker.on_event(MockEvent("llm.call_failed", {"provider": "gemini", "error_category": "timeout"}))

    state_events = [event for event in breaker.get_audit_trail() if event["category"] == "state_change"]
    assert state_events
    degraded = state_events[-1]
    assert degraded["action"] == "degraded"
    assert degraded["metadata"]["provider"] == "gemini"
    assert degraded["metadata"]["mode"] == "active"

    governance_event = breaker.update_governance(
        mode=ActuatorMode.CANARY,
        candidate_version="cb-canary-v2",
        reason="lane_c_review",
    )
    assert governance_event["category"] == "governance"
    assert breaker.describe_governance()["mode"] == "canary"
    assert breaker.describe_governance()["candidate_version"] == "cb-canary-v2"


def test_kb_scorer_records_audit_trail_for_score_updates():
    observer = DummyObserver()
    scorer = KBScorer(observer=observer)

    scorer._update_score("art-001", 0.1, "kb_direct_success")

    trail = scorer.get_audit_trail()
    assert trail
    score_event = trail[-1]
    assert score_event["action"] == "score_updated"
    assert score_event["metadata"]["artifact_id"] == "art-001"
    assert observer.scores["art-001"] == 0.6
    assert observer.events[-1]["data"]["governance"]["name"] == "kb_scorer"
    assert observer.events[-1]["data"]["audit_event"]["reason"] == "kb_direct_success"


def test_memory_injector_exposes_governance_without_behavior_change(tmp_path):
    injector = MemoryInjector(db_path=str(tmp_path / "missing.db"))

    assert injector.retrieve(domain="routing") == ""
    assert injector.describe_governance() == {
        "name": "memory_injector",
        "mode": "active",
        "owner": "evomap.runtime",
        "candidate_version": "memory-injector-live",
        "rollback_trigger": "memory_grounding_regression",
    }
    governance_event = injector.update_governance(owner="runtime-evals", reason="lane_c_alignment")
    assert governance_event["category"] == "governance"
    assert injector.describe_governance()["owner"] == "runtime-evals"
