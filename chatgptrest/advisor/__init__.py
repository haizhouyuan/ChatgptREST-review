"""
Advisor Routing Engine – Intelligent triage and route selection.

Implements the C/K/U/R/I scoring model from Advisor DR:
- IntentCertainty (I): confidence in understanding what user wants
- ComplexityScore (C): number of steps, constraints, open-endedness
- KBScore (K): how well KB can answer this (answerability)
- UrgencyScore (U): how quickly user needs a response
- RiskScore (R): potential for harm if answer is wrong

Route Decision Tree:
    I < 55 → Clarify (ask follow-up question)
    U > 80 & C < 40 & K > 50 → KBAnswer (fast, grounded)
    C > 70 OR (verification_need & K < 40) → DeepResearch
    multi_intent & C > 60 → Funnel
    action_required & R < 60 → Action
    else → Hybrid (KB + small lookups)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from ..contracts.schemas import (
    AdvisorContext,
    IntentSignals,
    KBProbeResult,
    Route,
    RouteScores,
    TraceEvent,
    EventType,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def compute_intent_certainty(intent: IntentSignals) -> float:
    """I = 100 × intent_confidence"""
    return min(100.0, 100.0 * intent.intent_confidence)


def compute_complexity(intent: IntentSignals) -> float:
    """
    C = weighted sum of:
    - step_count_est (0-10 mapped to 0-100)
    - constraint_count (each adds 10, max 30)
    - open_endedness (0-1 mapped to 0-20)
    - verification_need (adds 15)
    """
    step_score = min(100.0, intent.step_count_est * 10)
    constraint_score = min(30.0, intent.constraint_count * 10)
    openness_score = intent.open_endedness * 20
    verify_score = 15.0 if intent.verification_need else 0.0

    # Weighted blend
    raw = 0.4 * step_score + 0.25 * constraint_score + 0.2 * openness_score + 0.15 * verify_score
    return min(100.0, round(raw, 2))


def compute_kb_score(probe: KBProbeResult) -> float:
    """
    K = 100 × kb_answerability
    (answerability is already a blend of hit_rate + coverage + freshness)
    """
    return min(100.0, round(100.0 * probe.answerability, 2))


def compute_urgency(urgency_hint: str = "whenever") -> float:
    """
    U based on hints:
    - "immediate" → 100
    - "soon" → 60
    - "whenever" → 20
    """
    mapping = {
        "immediate": 100.0,
        "soon": 60.0,
        "whenever": 20.0,
    }
    return mapping.get(urgency_hint, 20.0)


def compute_risk(intent: IntentSignals, domain_risk: float = 0.0) -> float:
    """
    R = base domain risk + action risk + irreversibility
    """
    base = domain_risk * 50
    action_risk = 30.0 if intent.action_required else 0.0
    return min(100.0, round(base + action_risk, 2))


def compute_all_scores(
    intent: IntentSignals,
    kb_probe: KBProbeResult,
    urgency_hint: str = "whenever",
    domain_risk: float = 0.0,
) -> RouteScores:
    """Compute all 5 routing scores from signals."""
    return RouteScores(
        intent_certainty=compute_intent_certainty(intent),
        complexity=compute_complexity(intent),
        kb_score=compute_kb_score(kb_probe),
        urgency=compute_urgency(urgency_hint),
        risk=compute_risk(intent, domain_risk),
    )


# ---------------------------------------------------------------------------
# Route selection
# ---------------------------------------------------------------------------

@dataclass
class RouteDecision:
    """Result of the routing decision."""
    route: str = ""                # Route enum value
    rationale: str = ""            # Human-readable explanation
    scores: RouteScores = field(default_factory=RouteScores)
    needs_clarification: bool = False
    clarification_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def select_route(
    intent: IntentSignals,
    scores: RouteScores,
) -> RouteDecision:
    """
    Apply the deterministic routing decision tree.

    Stage A: Deterministic gates (safety, clarification, urgency)
    Stage B: Scoring/selection (flexible, tunable)
    """
    I = scores.intent_certainty
    C = scores.complexity
    K = scores.kb_score
    U = scores.urgency
    R = scores.risk

    # Stage A: Deterministic gates
    # Gate 1: Intent unclear → ask for clarification
    if I < 55:
        return RouteDecision(
            route=Route.CLARIFY.value,
            scores=scores,
            needs_clarification=True,
            clarification_reason=f"Intent confidence too low ({I:.0f}/100). "
                                  "Need more information to proceed.",
            rationale=f"I={I:.0f} < 55 → clarify",
        )

    # Stage B: Scoring-based route selection

    # Fast path: urgent + simple + KB has answer
    if U > 80 and C < 40 and K > 50:
        return RouteDecision(
            route=Route.KB_ANSWER.value,
            scores=scores,
            rationale=f"U={U:.0f}>80, C={C:.0f}<40, K={K:.0f}>50 → KB answer (fast path)",
        )

    # Complex or needs verification but KB doesn't have it
    if C > 70 or (intent.verification_need and K < 40):
        return RouteDecision(
            route=Route.DEEP_RESEARCH.value,
            scores=scores,
            rationale=f"C={C:.0f}>70 or (verify={intent.verification_need}, K={K:.0f}<40) "
                      "→ deep research",
        )

    # Multi-intent with moderate complexity → Funnel
    if intent.multi_intent and C > 60:
        return RouteDecision(
            route=Route.FUNNEL.value,
            scores=scores,
            rationale=f"multi_intent=True, C={C:.0f}>60 → funnel (projectization)",
        )

    # Action required with acceptable risk
    if intent.action_required and R < 60:
        return RouteDecision(
            route=Route.ACTION.value,
            scores=scores,
            rationale=f"action_required=True, R={R:.0f}<60 → action",
        )

    # KB can answer directly
    if K > 60:
        return RouteDecision(
            route=Route.KB_ANSWER.value,
            scores=scores,
            rationale=f"K={K:.0f}>60 → KB answer",
        )

    # Default: hybrid (KB + small lookups + answer)
    return RouteDecision(
        route=Route.HYBRID.value,
        scores=scores,
        rationale=f"Default → hybrid (I={I:.0f}, C={C:.0f}, K={K:.0f}, U={U:.0f}, R={R:.0f})",
    )


# ---------------------------------------------------------------------------
# Full routing pipeline
# ---------------------------------------------------------------------------

def route_request(
    user_message: str,
    *,
    intent: IntentSignals | None = None,
    kb_probe: KBProbeResult | None = None,
    urgency_hint: str = "whenever",
    domain_risk: float = 0.0,
    session_id: str = "",
    trace_id: str = "",
) -> AdvisorContext:
    """
    Full routing pipeline: classify → score → route → package context.

    In a real system, `intent` would be produced by an LLM classifier.
    For now, it can be provided directly.
    """
    if intent is None:
        intent = IntentSignals()
    if kb_probe is None:
        kb_probe = KBProbeResult()

    # Compute scores
    scores = compute_all_scores(
        intent=intent,
        kb_probe=kb_probe,
        urgency_hint=urgency_hint,
        domain_risk=domain_risk,
    )

    # Select route
    decision = select_route(intent, scores)

    # Package context
    ctx = AdvisorContext(
        user_message=user_message,
        session_id=session_id,
        trace_id=trace_id,
        intent=intent,
        kb_probe=kb_probe,
        scores=scores,
        selected_route=decision.route,
        route_rationale=decision.rationale,
    )

    return ctx
