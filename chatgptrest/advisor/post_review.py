"""Post-Ask Review — Lightweight Review for Premium Agent Ingress.

This module provides post-ask review capabilities:
- question_quality: How well was the question formed?
- contract_completeness: How complete was the ask contract?
- missing_info_detected: What information was missing?
- model_fit: How well did the model fit the task?
- route_fit: How appropriate was the routing?
- answer_quality: How good was the answer?
- actionability: How actionable is the answer?
- hallucination_risk: Risk of hallucination
- prompt_improvement_hint: Suggestions for improving the prompt
- template_improvement_hint: Suggestions for template improvement
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from chatgptrest.advisor.ask_contract import AskContract

logger = logging.getLogger(__name__)


@dataclass
class PostAskReview:
    """Post-ask review results."""
    # Question quality assessment
    question_quality: str = "unknown"  # excellent / good / fair / poor
    question_clarity: float = 0.0  # 0-1

    # Contract completeness
    contract_completeness: float = 0.0  # 0-1
    contract_source: str = "unknown"  # client / server_synthesized

    # Missing information
    missing_info_detected: list[str] = field(default_factory=list)

    # Model and route fit
    model_fit: str = "unknown"  # excellent / good / fair / poor
    route_fit: str = "unknown"  # excellent / good / fair / poor
    provider_used: str = ""

    # Answer quality (basic heuristics)
    answer_quality: str = "unknown"
    answer_length_adequate: bool = False
    answer_has_structure: bool = False

    # Actionability
    actionability: str = "unknown"  # high / medium / low
    has_actionable_steps: bool = False

    # Hallucination risk (basic)
    hallucination_risk: str = "low"  # low / medium / high

    # Improvement hints
    prompt_improvement_hint: str = ""
    template_improvement_hint: str = ""

    # Metadata
    review_id: str = field(default_factory=lambda: f"review_{uuid.uuid4().hex[:12]}")
    session_id: str = ""
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PostAskReview":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def generate_basic_review(
    contract: AskContract,
    answer: str,
    route: str,
    provider: str,
    session_id: str = "",
    trace_id: str = "",
) -> PostAskReview:
    """
    Generate a basic post-ask review based on heuristics.

    This is a lightweight review that doesn't require additional LLM calls.
    For full quality evaluation, use QAInspector.

    Args:
        contract: The ask contract used
        answer: The answer received
        route: The route used
        provider: The provider/model used
        session_id: Session ID
        trace_id: Trace ID

    Returns:
        PostAskReview with basic assessment
    """
    review = PostAskReview()
    review.session_id = session_id
    review.trace_id = trace_id
    review.provider_used = provider

    # Contract completeness
    review.contract_completeness = contract.contract_completeness
    review.contract_source = contract.contract_source

    # Missing info detection
    if contract.contract_completeness < 0.7:
        review.missing_info_detected = _identify_missing_info(contract)

    # Question quality assessment
    review.question_clarity = _assess_question_clarity(contract)
    review.question_quality = _rate_quality(review.question_clarity)

    # Route fit assessment
    review.route_fit = _assess_route_fit(contract, route)
    review.model_fit = _assess_model_fit(contract, provider)

    # Answer quality heuristics
    review.answer_length_adequate = len(answer) > 100
    answer_lower = answer.lower()
    review.answer_has_structure = any(
        marker in answer_lower
        for marker in ["##", "###", "1.", "2.", "3.", "- ", "* ", "**"]
    )
    if review.answer_length_adequate and review.answer_has_structure:
        review.answer_quality = "good"
    elif review.answer_length_adequate:
        review.answer_quality = "fair"
    else:
        review.answer_quality = "poor"

    # Actionability assessment
    action_indicators = [
        "step", "action", "recommend", "suggest", "should", "need to",
        "first", "then", "next", "finally", "1.", "2.", "3.",
    ]
    review.has_actionable_steps = any(
        indicator in answer_lower for indicator in action_indicators
    )
    if review.has_actionable_steps and review.answer_length_adequate:
        review.actionability = "high"
    elif review.answer_length_adequate:
        review.actionability = "medium"
    else:
        review.actionability = "low"

    # Hallucination risk (basic heuristics)
    review.hallucination_risk = _assess_hallucination_risk(answer, contract)

    # Generate improvement hints
    review.prompt_improvement_hint = _generate_prompt_hint(contract, review)
    review.template_improvement_hint = _generate_template_hint(contract, review)

    logger.info(
        f"Generated post-ask review: session={session_id}, "
        f"quality={review.question_quality}, "
        f"actionability={review.actionability}"
    )

    return review


def _identify_missing_info(contract: AskContract) -> list[str]:
    """Identify missing information from incomplete contract."""
    missing = []

    if not contract.objective or len(contract.objective) < 10:
        missing.append("objective_not_clear")
    if not contract.decision_to_support:
        missing.append("decision_to_support_not_specified")
    if not contract.audience:
        missing.append("audience_not_specified")
    if not contract.output_shape:
        missing.append("output_shape_not_specified")

    return missing


def _assess_question_clarity(contract: AskContract) -> float:
    """Assess how clear the question/objective is."""
    score = 0.5  # base score

    # Check objective clarity
    if contract.objective:
        if len(contract.objective) > 20:
            score += 0.2
        # Check for specific details
        if any(word in contract.objective.lower() for word in ["how", "what", "why", "when", "where"]):
            score += 0.1

    # Check constraints
    if contract.constraints:
        score += 0.1

    # Check available inputs
    if contract.available_inputs:
        score += 0.1

    return min(1.0, score)


def _rate_quality(score: float) -> str:
    """Rate quality from score."""
    if score >= 0.8:
        return "excellent"
    elif score >= 0.6:
        return "good"
    elif score >= 0.4:
        return "fair"
    else:
        return "poor"


def _assess_route_fit(contract: AskContract, route: str) -> str:
    """Assess how appropriate the route was."""
    template = contract.task_template
    route_lower = route.lower() if route else ""

    # Template to expected route mapping
    expected_routes = {
        "research": ["research", "deep_research", "gemini_research", "kb_answer"],
        "decision_support": ["consult", "hybrid"],
        "code_review": ["code_review"],
        "implementation_planning": ["funnel", "action"],
        "report_generation": ["report", "write_report"],
        "image_generation": ["image"],
        "dual_model_critique": ["dual_review", "consult"],
        "repair_diagnosis": ["repair"],
        "stakeholder_communication": ["action"],
        "general": ["quick_ask", "kb_answer"],
    }

    expected = expected_routes.get(template, [])
    if any(exp in route_lower for exp in expected):
        return "excellent"

    # Partial match
    if route:
        return "good"

    return "fair"


def _assess_model_fit(contract: AskContract, provider: str) -> str:
    """Assess how appropriate the model/provider was."""
    risk = contract.risk_class
    provider_lower = provider.lower() if provider else ""

    # High risk should use more capable models
    if risk == "high":
        if "pro" in provider_lower or "claude" in provider_lower or "gemini" in provider_lower:
            return "excellent"
        return "good"

    # Medium risk
    if risk == "medium":
        if provider_lower in {"chatgpt", "gemini", "claude"}:
            return "good"

    return "fair"


def _assess_hallucination_risk(answer: str, contract: AskContract) -> str:
    """Basic assessment of hallucination risk."""
    if not answer:
        return "high"

    # Check for uncertainty markers (good)
    uncertainty_markers = [
        "i'm not sure", "i don't know", "possibly", "perhaps",
        "might", "may be", "could be", "uncertain", "unclear",
    ]
    answer_lower = answer.lower()
    has_uncertainty = any(marker in answer_lower for marker in uncertainty_markers)

    # Check for factual claims without sources
    factual_markers = ["研究表明", "according to", "数据显示", "研究显示"]
    has_factual_claims = any(marker in answer_lower for marker in factual_markers)

    if has_uncertainty and not has_factual_claims:
        return "low"
    elif has_factual_claims:
        return "medium"  # May need verification

    return "low"


def _generate_prompt_hint(contract: AskContract, review: PostAskReview) -> str:
    """Generate prompt improvement hint."""
    hints = []

    if review.contract_completeness < 0.7:
        hints.append("Add more context to improve contract completeness")
    if not contract.constraints:
        hints.append("Specify constraints (time, scope, format)")
    if not contract.available_inputs:
        hints.append("List available inputs/materials")
    if review.question_quality in {"fair", "poor"}:
        hints.append("Make the objective more specific")

    return "; ".join(hints) if hints else "No specific improvements needed"


def _generate_template_hint(contract: AskContract, review: PostAskReview) -> str:
    """Generate template improvement hint."""
    hints = []

    if review.route_fit in {"fair", "poor"}:
        hints.append(f"Consider using a different template for {contract.task_template} tasks")
    if review.model_fit in {"fair", "poor"}:
        hints.append("Consider using a more capable model for high-stakes requests")

    return "; ".join(hints) if hints else "Current template appears appropriate"


# Import uuid for review_id generation
import uuid
