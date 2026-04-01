"""
EvoMap Signal Engine (S7) – DEPRECATED.

⚠️  This module is superseded by the EventBus + EvoMapObserver + Knowledge
    Extractors architecture (chatgptrest.evomap.*).

    - Signals: chatgptrest.evomap.signals.Signal
    - Observer: chatgptrest.evomap.observer.EvoMapObserver
    - EventBus: chatgptrest.kernel.event_bus.EventBus
    - Extractors: chatgptrest.evomap.knowledge.extractors.*

The propose_evolution() heuristics may be migrated as an EventBus consumer
in a future release.

Original design (now legacy):
- Inner loop: per-session reflection (extract learnings)
- Middle loop: periodic signal aggregation + evolution plans
- Outer loop: model alignment (future, not implemented here)
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from ..contracts.schemas import TraceEvent, EventType, _uuid, _now_iso
from ..contracts.event_log import EventLogStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal types
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """A single observation extracted from trace events."""
    signal_id: str = ""
    signal_type: str = ""      # user_value | task_result | semantic | efficiency | safety | collaboration
    name: str = ""             # e.g., "route_accuracy", "latency_p95"
    value: float = 0.0
    unit: str = ""             # "rate", "ms", "count", "score"
    source_trace_id: str = ""
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SignalAggregation:
    """Aggregated signals over a time period."""
    period: str = ""           # "session", "daily", "weekly"
    computed_at: str = ""
    signal_count: int = 0
    signals: list[Signal] = field(default_factory=list)
    
    # Summary metrics
    route_distribution: dict[str, int] = field(default_factory=dict)
    workflow_success_rate: float = 0.0
    avg_workflow_duration_ms: float = 0.0
    kb_hit_rate: float = 0.0
    error_rate: float = 0.0
    
    # Anomalies detected
    anomalies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvolutionPlan:
    """A proposed change based on signal analysis."""
    plan_id: str = ""
    created_at: str = ""
    trigger_signals: list[str] = field(default_factory=list)
    
    # What to change
    change_type: str = ""      # "prompt" | "route_weight" | "threshold" | "strategy"
    target: str = ""           # Which component to change
    current_value: str = ""
    proposed_value: str = ""
    rationale: str = ""
    
    # Safety
    risk_level: str = "low"    # "low" | "medium" | "high"
    rollback_plan: str = ""
    canary_percentage: float = 10.0  # Start with 10% traffic
    
    # Approval
    status: str = "proposed"   # "proposed" | "approved" | "deployed" | "rolled_back"
    auto_approvable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Signal Extractors
# ---------------------------------------------------------------------------

def extract_route_signals(events: list[TraceEvent]) -> list[Signal]:
    """Extract routing signals from trace events."""
    signals = []
    route_events = [e for e in events if e.event_type == "route_selected"]
    
    if not route_events:
        return signals
    
    # Route distribution
    routes = Counter(e.data.get("route", "unknown") for e in route_events)
    total = sum(routes.values())
    
    for route, count in routes.items():
        signals.append(Signal(
            signal_id=_uuid(),
            signal_type="task_result",
            name=f"route_usage_{route}",
            value=count / total if total > 0 else 0,
            unit="rate",
            timestamp=_now_iso(),
            metadata={"route": route, "count": count, "total": total},
        ))
    
    # Clarification rate (how often we need to ask for more info)
    clarify_count = routes.get("clarify", 0)
    signals.append(Signal(
        signal_id=_uuid(),
        signal_type="user_value",
        name="clarification_rate",
        value=clarify_count / total if total > 0 else 0,
        unit="rate",
        timestamp=_now_iso(),
    ))
    
    return signals


def extract_workflow_signals(events: list[TraceEvent]) -> list[Signal]:
    """Extract workflow execution signals."""
    signals = []
    
    started = [e for e in events if e.event_type == "workflow_started"]
    finished = [e for e in events if e.event_type == "workflow_finished"]
    failed = [e for e in events if e.event_type == "workflow_step_failed"]
    
    total = len(started)
    if total > 0:
        success_rate = len(finished) / total
        error_rate = len(failed) / total
        
        signals.append(Signal(
            signal_id=_uuid(),
            signal_type="task_result",
            name="workflow_success_rate",
            value=success_rate,
            unit="rate",
            timestamp=_now_iso(),
            metadata={"started": total, "finished": len(finished), "failed": len(failed)},
        ))
        
        signals.append(Signal(
            signal_id=_uuid(),
            signal_type="efficiency",
            name="workflow_error_rate",
            value=error_rate,
            unit="rate",
            timestamp=_now_iso(),
        ))
    
    return signals


def extract_kb_signals(events: list[TraceEvent]) -> list[Signal]:
    """Extract KB usage signals."""
    signals = []
    
    kb_queries = [e for e in events if e.event_type == "kb_query_finished"]
    
    if kb_queries:
        hit_rates = [e.data.get("hit_rate", 0) for e in kb_queries]
        avg_hit_rate = sum(hit_rates) / len(hit_rates) if hit_rates else 0
        
        signals.append(Signal(
            signal_id=_uuid(),
            signal_type="efficiency",
            name="kb_avg_hit_rate",
            value=avg_hit_rate,
            unit="rate",
            timestamp=_now_iso(),
            metadata={"queries": len(kb_queries)},
        ))
    
    kb_writes = [e for e in events if e.event_type == "kb_write_committed"]
    if kb_writes:
        signals.append(Signal(
            signal_id=_uuid(),
            signal_type="collaboration",
            name="kb_write_count",
            value=len(kb_writes),
            unit="count",
            timestamp=_now_iso(),
        ))
    
    return signals


# ---------------------------------------------------------------------------
# EvoMap Engine
# ---------------------------------------------------------------------------

class EvoMapEngine:
    """
    Self-evolution engine that observes system behavior and proposes improvements.

    Usage::

        engine = EvoMapEngine(event_log=store)
        
        # Inner loop: after each session
        signals = engine.extract_session_signals(trace_id="abc123")
        
        # Middle loop: periodic aggregation
        agg = engine.aggregate_signals(since="2026-02-27T00:00:00")
        plans = engine.propose_evolution(agg)
    """

    def __init__(self, event_log: EventLogStore):
        self.event_log = event_log
        self._evolution_plans: list[EvolutionPlan] = []

    def extract_session_signals(self, trace_id: str) -> list[Signal]:
        """Inner loop: Extract signals from a single session trace."""
        events = self.event_log.get_trace(trace_id)
        if not events:
            return []
        
        signals = []
        signals.extend(extract_route_signals(events))
        signals.extend(extract_workflow_signals(events))
        signals.extend(extract_kb_signals(events))
        
        return signals

    def aggregate_signals(
        self,
        since: str = "",
        until: str = "",
        period: str = "daily",
    ) -> SignalAggregation:
        """Middle loop: Aggregate signals over a time period."""
        events = self.event_log.query(since=since, until=until, limit=10000)
        
        all_signals = []
        all_signals.extend(extract_route_signals(events))
        all_signals.extend(extract_workflow_signals(events))
        all_signals.extend(extract_kb_signals(events))
        
        # Compute summary metrics
        agg = SignalAggregation(
            period=period,
            computed_at=_now_iso(),
            signal_count=len(all_signals),
            signals=all_signals,
        )
        
        # Route distribution
        route_events = [e for e in events if e.event_type == "route_selected"]
        agg.route_distribution = dict(Counter(
            e.data.get("route", "unknown") for e in route_events
        ))
        
        # Workflow success rate
        for s in all_signals:
            if s.name == "workflow_success_rate":
                agg.workflow_success_rate = s.value
            if s.name == "workflow_error_rate":
                agg.error_rate = s.value
            if s.name == "kb_avg_hit_rate":
                agg.kb_hit_rate = s.value
        
        # Detect anomalies
        if agg.error_rate > 0.2:
            agg.anomalies.append(f"High error rate: {agg.error_rate:.1%}")
        if agg.kb_hit_rate < 0.3 and len(route_events) > 5:
            agg.anomalies.append(f"Low KB hit rate: {agg.kb_hit_rate:.1%}")
        clarify_rate = agg.route_distribution.get("clarify", 0) / max(len(route_events), 1)
        if clarify_rate > 0.3:
            agg.anomalies.append(f"High clarification rate: {clarify_rate:.1%}")
        
        return agg

    def propose_evolution(self, aggregation: SignalAggregation) -> list[EvolutionPlan]:
        """
        Propose evolution plans based on aggregated signals.
        
        Uses rule-based heuristics for now; future: LLM-as-Judge + optimization.
        """
        plans = []
        
        # Rule 1: Low KB hit rate → propose expanding KB coverage
        if aggregation.kb_hit_rate < 0.3:
            plans.append(EvolutionPlan(
                plan_id=_uuid(),
                created_at=_now_iso(),
                trigger_signals=["kb_avg_hit_rate"],
                change_type="strategy",
                target="kb/ingestion",
                current_value=f"hit_rate={aggregation.kb_hit_rate:.2f}",
                proposed_value="Expand KB coverage: scan more directories, index more file types",
                rationale=f"KB hit rate ({aggregation.kb_hit_rate:.1%}) is below 30% threshold. "
                          "Users are asking questions KB can't answer.",
                risk_level="low",
                rollback_plan="Revert to previous scan scope",
                auto_approvable=True,
            ))
        
        # Rule 2: High error rate → propose routing adjustment
        if aggregation.error_rate > 0.2:
            plans.append(EvolutionPlan(
                plan_id=_uuid(),
                created_at=_now_iso(),
                trigger_signals=["workflow_error_rate"],
                change_type="threshold",
                target="advisor/routing",
                current_value=f"error_rate={aggregation.error_rate:.2f}",
                proposed_value="Lower complexity threshold for deep_research route (C>70 → C>60)",
                rationale=f"Workflow error rate ({aggregation.error_rate:.1%}) exceeds 20%. "
                          "Complex tasks may be routed to simpler workflows.",
                risk_level="medium",
                rollback_plan="Restore original C>70 threshold",
                canary_percentage=10.0,
            ))
        
        # Rule 3: High clarification rate → improve intent detection
        total_routes = sum(aggregation.route_distribution.values())
        clarify_rate = aggregation.route_distribution.get("clarify", 0) / max(total_routes, 1)
        if clarify_rate > 0.3:
            plans.append(EvolutionPlan(
                plan_id=_uuid(),
                created_at=_now_iso(),
                trigger_signals=["clarification_rate"],
                change_type="prompt",
                target="advisor/intent_classifier",
                current_value=f"clarify_rate={clarify_rate:.2f}",
                proposed_value="Add few-shot examples to intent classification prompt",
                rationale=f"Clarification rate ({clarify_rate:.1%}) means users are often misunderstood. "
                          "Adding examples should improve first-pass classification.",
                risk_level="low",
                rollback_plan="Revert to zero-shot prompt",
                auto_approvable=True,
            ))
        
        self._evolution_plans.extend(plans)
        return plans

    def get_plans(self, status: str = "") -> list[EvolutionPlan]:
        """Get all evolution plans, optionally filtered by status."""
        if status:
            return [p for p in self._evolution_plans if p.status == status]
        return list(self._evolution_plans)

    def approve_plan(self, plan_id: str) -> bool:
        """Approve an evolution plan for deployment."""
        for plan in self._evolution_plans:
            if plan.plan_id == plan_id:
                plan.status = "approved"
                return True
        return False

    def rollback_plan(self, plan_id: str) -> bool:
        """Rollback a deployed evolution plan."""
        for plan in self._evolution_plans:
            if plan.plan_id == plan_id:
                plan.status = "rolled_back"
                return True
        return False
