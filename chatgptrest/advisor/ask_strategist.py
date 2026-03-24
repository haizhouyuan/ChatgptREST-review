"""Strategist plan synthesis for premium ingress.

This module keeps the strategist layer additive: it accepts the existing
AskContract plus request context, then produces a structured execution plan
that downstream clarify/prompt/review layers can consume.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from chatgptrest.advisor.ask_contract import AskContract, RiskClass, TaskTemplate


_TASK_ROUTE_HINTS: dict[str, str] = {
    TaskTemplate.RESEARCH.value: "deep_research",
    TaskTemplate.DECISION_SUPPORT.value: "hybrid",
    TaskTemplate.CODE_REVIEW.value: "quick_ask",
    TaskTemplate.IMPLEMENTATION_PLANNING.value: "funnel",
    TaskTemplate.REPORT_GENERATION.value: "report",
    TaskTemplate.IMAGE_GENERATION.value: "image",
    TaskTemplate.DUAL_MODEL_CRITIQUE.value: "consult",
    TaskTemplate.REPAIR_DIAGNOSIS.value: "action",
    TaskTemplate.STAKEHOLDER_COMMUNICATION.value: "action",
    TaskTemplate.GENERAL.value: "quick_ask",
}


@dataclass
class AskStrategyPlan:
    """Structured strategist output for one ingress ask."""

    plan_id: str = field(default_factory=lambda: f"strategy_{uuid.uuid4().hex[:12]}")
    contract_id: str = ""
    task_template: str = TaskTemplate.GENERAL.value
    route_hint: str = "quick_ask"
    provider_family: str = "chatgpt"
    model_family: str = "standard"
    execution_mode: str = "execute"  # execute | clarify
    clarify_required: bool = False
    clarify_reason_code: str = ""
    clarify_reason: str = ""
    clarify_questions: list[str] = field(default_factory=list)
    recommended_reask_template: str = ""
    output_contract: dict[str, Any] = field(default_factory=dict)
    uncertainty_policy: dict[str, Any] = field(default_factory=dict)
    evidence_requirements: dict[str, Any] = field(default_factory=dict)
    review_rubric: list[str] = field(default_factory=list)
    provider_hints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AskStrategyPlan":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def build_strategy_plan(
    *,
    message: str,
    contract: AskContract,
    goal_hint: str = "",
    context: dict[str, Any] | None = None,
) -> AskStrategyPlan:
    """Build a deterministic strategist plan from the ingress contract."""
    context = dict(context or {})
    task_template = str(contract.task_template or TaskTemplate.GENERAL.value)
    scenario_pack = _scenario_pack(context)
    route_hint = _route_hint_for_pack(task_template=task_template, scenario_pack=scenario_pack, context=context)
    provider_family = "gemini" if task_template == TaskTemplate.IMAGE_GENERATION.value else "chatgpt"
    model_family = _select_model_family(contract=contract, route_hint=route_hint, goal_hint=goal_hint)

    clarify_questions = _build_clarify_questions(contract, scenario_pack=scenario_pack)
    clarify_required, clarify_reason_code, clarify_reason = _should_clarify(
        contract=contract,
        clarify_questions=clarify_questions,
        scenario_pack=scenario_pack,
        context=context,
        route_hint=route_hint,
    )

    execution_mode = "clarify" if clarify_required else "execute"
    review_rubric = _build_review_rubric(task_template, scenario_pack=scenario_pack)
    evidence_requirements = _build_evidence_requirements(contract=contract, context=context, scenario_pack=scenario_pack)
    output_contract = _build_output_contract(task_template, scenario_pack=scenario_pack)
    uncertainty_policy = _build_uncertainty_policy(contract=contract, route_hint=route_hint)
    provider_hints = {
        "goal_hint": str(goal_hint or ""),
        "preferred_route_hint": route_hint,
        "supports_files": bool(list(context.get("files") or [])),
        "contract_source": contract.contract_source,
    }
    if scenario_pack:
        provider_hints["scenario_pack"] = dict(scenario_pack)
        provider_hints["scenario_profile"] = str(scenario_pack.get("profile") or "")
        if str(scenario_pack.get("scenario") or "").strip() == "planning":
            provider_hints["planning_profile"] = str(scenario_pack.get("profile") or "")
        if str(scenario_pack.get("prompt_template_override") or "").strip():
            provider_hints["prompt_template_override"] = str(scenario_pack.get("prompt_template_override") or "").strip()

    return AskStrategyPlan(
        contract_id=str(contract.contract_id or ""),
        task_template=task_template,
        route_hint=route_hint,
        provider_family=provider_family,
        model_family=model_family,
        execution_mode=execution_mode,
        clarify_required=clarify_required,
        clarify_reason_code=clarify_reason_code,
        clarify_reason=clarify_reason,
        clarify_questions=clarify_questions,
        recommended_reask_template=_recommended_reask_template(
            contract=contract,
            clarify_questions=clarify_questions,
            message=message,
        ) if clarify_required else "",
        output_contract=output_contract,
        uncertainty_policy=uncertainty_policy,
        evidence_requirements=evidence_requirements,
        review_rubric=review_rubric,
        provider_hints=provider_hints,
    )


def _select_model_family(*, contract: AskContract, route_hint: str, goal_hint: str) -> str:
    goal = str(goal_hint or "").strip().lower()
    if contract.risk_class == RiskClass.HIGH.value or route_hint in {"deep_research", "analysis_heavy", "report", "consult", "funnel"}:
        return "premium_reasoning"
    if goal in {"code_review", "research"}:
        return "analysis"
    return "standard"


def _scenario_pack(context: dict[str, Any]) -> dict[str, Any]:
    pack = context.get("scenario_pack")
    return dict(pack) if isinstance(pack, dict) else {}


def _route_hint_for_pack(*, task_template: str, scenario_pack: dict[str, Any], context: dict[str, Any]) -> str:
    execution_profile = str(dict(scenario_pack.get("provider_hints") or {}).get("execution_profile") or "").strip().lower()
    if not execution_profile:
        task_intake = context.get("task_intake")
        if isinstance(task_intake, dict):
            execution_profile = str(task_intake.get("execution_profile") or "").strip().lower()
    preferred = str(scenario_pack.get("route_hint") or "").strip()
    if execution_profile == "thinking_heavy" and preferred in {"deep_research", "analysis_heavy"}:
        return "analysis_heavy"
    if execution_profile == "thinking_heavy" and task_template in {
        TaskTemplate.RESEARCH.value,
        TaskTemplate.DECISION_SUPPORT.value,
        TaskTemplate.GENERAL.value,
    }:
        return "analysis_heavy"
    if preferred:
        return preferred
    return _TASK_ROUTE_HINTS.get(task_template, "quick_ask")


def _build_clarify_questions(contract: AskContract, *, scenario_pack: dict[str, Any]) -> list[str]:
    questions: list[str] = []
    if not contract.objective or len(contract.objective.strip()) < 12:
        questions.append("What is the concrete objective or deliverable you want from this run?")
    if not contract.decision_to_support:
        questions.append("What decision, action, or next step should this answer support?")
    if not contract.audience:
        questions.append("Who is the target audience or owner of the output?")
    if not contract.output_shape:
        questions.append("What output format do you want: brief answer, report, plan, review, or another format?")
    if scenario_pack and (
        not contract.decision_to_support
        or not contract.audience
        or float(contract.contract_completeness or 0.0) < 0.85
    ):
        for question in list(scenario_pack.get("clarify_questions") or []):
            text = str(question or "").strip()
            if text and text not in questions:
                questions.append(text)
    return questions


def _should_clarify(
    *,
    contract: AskContract,
    clarify_questions: list[str],
    scenario_pack: dict[str, Any],
    context: dict[str, Any],
    route_hint: str,
) -> tuple[bool, str, str]:
    completeness = float(contract.contract_completeness or 0.0)
    risk = str(contract.risk_class or RiskClass.MEDIUM.value)
    synthesized = contract.contract_source == "server_synthesized"
    profile = str(scenario_pack.get("profile") or "").strip().lower()
    watch_checkpoint = str(dict(scenario_pack.get("watch_policy") or {}).get("checkpoint") or "").strip().lower()
    has_grounding_inputs = _has_grounding_inputs(contract=contract, context=context)
    execution_profile = _execution_profile(context=context, scenario_pack=scenario_pack)
    has_core_triage = all(
        str(value or "").strip()
        for value in (contract.objective, contract.decision_to_support, contract.audience)
    )

    if (
        execution_profile == "thinking_heavy"
        and route_hint == "analysis_heavy"
        and risk != RiskClass.HIGH.value
        and has_core_triage
    ):
        return False, "", ""

    if risk == RiskClass.HIGH.value and completeness < 0.75 and clarify_questions:
        return True, "high_risk_incomplete_contract", "High-stakes ask lacks enough decision context for premium execution."
    if (
        profile in {"meeting_summary", "interview_notes"}
        and watch_checkpoint == "delivery_only"
        and completeness < 0.75
        and clarify_questions
        and not has_grounding_inputs
    ):
        return True, "summary_missing_grounding", "Summary-style planning ask lacks enough source scope or grounding inputs to execute well."
    if (
        profile == "research_report"
        and watch_checkpoint == "evidence_gate"
        and completeness < 0.72
        and clarify_questions
        and not has_grounding_inputs
    ):
        return True, "research_report_missing_scope_or_grounding", "Research-report ask lacks enough scope, audience, or grounding inputs to produce a decision-ready report."
    if (
        profile in {"topic_research", "comparative_research"}
        and watch_checkpoint == "evidence_gate"
        and completeness < 0.55
        and clarify_questions
        and not has_grounding_inputs
    ):
        return True, "research_scope_needs_tightening", "Research ask would benefit from a tighter scope or decision question before deep execution."
    if risk == RiskClass.MEDIUM.value and completeness < 0.50 and clarify_questions:
        return True, "medium_risk_low_completeness", "Request would benefit from more structure before execution."
    if synthesized and completeness < 0.40 and clarify_questions:
        return True, "synthesized_contract_too_incomplete", "Server-synthesized contract is too incomplete to execute well."
    return False, "", ""


def _execution_profile(*, context: dict[str, Any], scenario_pack: dict[str, Any]) -> str:
    task_intake = context.get("task_intake")
    if isinstance(task_intake, dict):
        profile = str(task_intake.get("execution_profile") or "").strip().lower()
        if profile:
            return profile
    provider_hints = dict(scenario_pack.get("provider_hints") or {})
    return str(provider_hints.get("execution_profile") or "").strip().lower()


def _has_grounding_inputs(*, contract: AskContract, context: dict[str, Any]) -> bool:
    files = list(context.get("files") or [])
    if files:
        return True
    task_intake = context.get("task_intake")
    if isinstance(task_intake, dict) and list(task_intake.get("attachments") or []):
        return True
    return bool(str(contract.available_inputs or "").strip())


def _recommended_reask_template(
    *,
    contract: AskContract,
    clarify_questions: list[str],
    message: str,
) -> str:
    missing_lines = []
    if not contract.objective or len(contract.objective.strip()) < 12:
        missing_lines.append("Objective: <what needs to be produced or answered>")
    if not contract.decision_to_support:
        missing_lines.append("Decision to support: <why this output matters>")
    if not contract.audience:
        missing_lines.append("Audience: <who will use it>")
    if not contract.output_shape:
        missing_lines.append("Output format: <report / plan / summary / review / other>")
    if not missing_lines:
        missing_lines = [f"- {question}" for question in clarify_questions]
    return "Please resend in this shape:\n" + "\n".join(f"- {line}" for line in missing_lines) + f"\n- Original request: {message.strip()}"


def _build_output_contract(task_template: str, *, scenario_pack: dict[str, Any]) -> dict[str, Any]:
    base: dict[str, Any] = {"format": "markdown", "style": "decision_ready"}
    if task_template == TaskTemplate.RESEARCH.value:
        base["required_sections"] = ["summary", "evidence", "uncertainties", "recommendation"]
    elif task_template == TaskTemplate.IMPLEMENTATION_PLANNING.value:
        base["required_sections"] = ["goal", "plan", "dependencies", "risks", "validation"]
    elif task_template == TaskTemplate.CODE_REVIEW.value:
        base["required_sections"] = ["findings", "severity", "evidence", "recommended_fix"]
    elif task_template == TaskTemplate.REPORT_GENERATION.value:
        base["required_sections"] = ["summary", "analysis", "risks", "next_steps"]
    else:
        base["required_sections"] = ["answer"]
    if scenario_pack:
        required_sections = list(scenario_pack.get("acceptance", {}).get("required_sections") or [])
        if required_sections:
            base["required_sections"] = required_sections
        profile = str(scenario_pack.get("profile") or "").strip()
        if profile:
            base["scenario_profile"] = profile
    return base


def _build_uncertainty_policy(*, contract: AskContract, route_hint: str) -> dict[str, Any]:
    return {
        "acknowledge_unknowns": True,
        "flag_missing_inputs": True,
        "cite_uncertainty_explicitly": contract.risk_class == RiskClass.HIGH.value or route_hint == "deep_research",
        "avoid_overclaiming": True,
    }


def _build_evidence_requirements(
    *,
    contract: AskContract,
    context: dict[str, Any],
    scenario_pack: dict[str, Any],
) -> dict[str, Any]:
    task_template = str(contract.task_template or "")
    wants_sources = task_template in {
        TaskTemplate.RESEARCH.value,
        TaskTemplate.DECISION_SUPPORT.value,
        TaskTemplate.REPORT_GENERATION.value,
        TaskTemplate.DUAL_MODEL_CRITIQUE.value,
    }
    requirements = {
        "require_sources": wants_sources,
        "prefer_primary_sources": wants_sources or contract.risk_class == RiskClass.HIGH.value,
        "ground_in_attached_files": bool(list(context.get("files") or [])),
        "require_traceable_claims": contract.risk_class in {RiskClass.MEDIUM.value, RiskClass.HIGH.value},
    }
    if scenario_pack:
        requirements.update(dict(scenario_pack.get("evidence_required") or {}))
        requirements["ground_in_attached_files"] = bool(list(context.get("files") or []))
    return requirements


def _build_review_rubric(task_template: str, *, scenario_pack: dict[str, Any]) -> list[str]:
    if scenario_pack:
        rubric = [str(item).strip() for item in list(scenario_pack.get("review_rubric") or []) if str(item).strip()]
        if rubric:
            return rubric
    rubric = ["answers the stated objective", "stays within requested output format"]
    if task_template == TaskTemplate.RESEARCH.value:
        rubric.extend(["grounds claims in evidence", "states uncertainties clearly"])
    elif task_template == TaskTemplate.IMPLEMENTATION_PLANNING.value:
        rubric.extend(["covers dependencies and risks", "includes validation steps"])
    elif task_template == TaskTemplate.CODE_REVIEW.value:
        rubric.extend(["prioritizes findings by severity", "ties each finding to concrete evidence"])
    else:
        rubric.append("gives actionable next steps when appropriate")
    return rubric
