"""Scenario pack policies for planning and research front-door asks.

Packs stay additive: they enrich the canonical task intake with route,
acceptance, evidence, and watch policies without replacing the base intake
schema. Phase 3 hardened planning; Phase 4 extends the same contract to
research asks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from chatgptrest.advisor.ask_contract import TaskTemplate
from chatgptrest.advisor.task_intake import (
    AcceptanceSpec,
    EvidenceRequirementSpec,
    TaskIntakeSpec,
)


@dataclass
class ScenarioPack:
    scenario: str
    profile: str
    intent_top: str
    route_hint: str
    output_shape: str
    execution_preference: str = "job"
    prompt_template_override: str = ""
    funnel_profile: str = ""
    acceptance: dict[str, Any] = field(default_factory=dict)
    evidence_required: dict[str, Any] = field(default_factory=dict)
    clarify_questions: list[str] = field(default_factory=list)
    review_rubric: list[str] = field(default_factory=list)
    watch_policy: dict[str, Any] = field(default_factory=dict)
    provider_hints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_PLANNING_PROFILE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "business_planning",
        (
            "业务规划",
            "业务方案",
            "业务计划",
            "增长规划",
            "经营规划",
            "business plan",
            "business planning",
            "go-to-market",
            "gtm plan",
        ),
    ),
    (
        "meeting_summary",
        (
            "例会纪要",
            "例会总结",
            "周会纪要",
            "周会总结",
            "同步纪要",
            "会议总结",
            "会议纪要",
            "会议记录",
            "复盘纪要",
            "meeting summary",
            "meeting notes",
            "meeting minutes",
        ),
    ),
    (
        "interview_notes",
        (
            "面试",
            "候选人",
            "访谈",
            "访谈纪要",
            "调查纪要",
            "访谈记录",
            "interview",
            "candidate",
            "debrief",
        ),
    ),
    (
        "workforce_planning",
        (
            "人力",
            "编制",
            "headcount",
            "staffing",
            "招聘",
            "组织规划",
            "岗位规划",
            "用工",
            "workforce",
            "hiring",
        ),
    ),
    (
        "implementation_plan",
        (
            "实施",
            "落地",
            "改造",
            "rollout",
            "migration",
            "上线",
            "技术规划",
            "implementation",
            "rollout plan",
            "系统设计",
            "开发计划",
        ),
    ),
)

_LIGHTWEIGHT_BUSINESS_PLANNING_KEYWORDS: tuple[str, ...] = (
    "简要",
    "简版",
    "概要",
    "概览",
    "框架",
    "大纲",
    "outline",
    "brief",
    "light",
    "不要走复杂流程",
    "先给简版",
    "先给框架",
    "先给一个版本",
)

_RESEARCH_REPORT_KEYWORDS: tuple[str, ...] = (
    "研究报告",
    "调研报告",
    "专题报告",
    "行业报告",
    "深度报告",
    "白皮书",
    "research report",
    "industry report",
    "analysis report",
    "white paper",
)

_COMPARATIVE_RESEARCH_KEYWORDS: tuple[str, ...] = (
    "对比",
    "比较",
    "横向",
    "竞品",
    "差异",
    "优劣",
    "vs",
    "versus",
    "benchmark",
    "compare",
    "comparison",
    "competitive analysis",
)

_RESEARCH_GENERAL_KEYWORDS: tuple[str, ...] = (
    "调研",
    "研究",
    "专题",
    "产业链",
    "行业",
    "趋势",
    "技术路线",
    "国产替代",
    "landscape",
    "literature",
    "prior art",
    "market map",
)

_RESEARCH_GOAL_HINTS: set[str] = {
    "research",
    "deep_research",
    "gemini_research",
    "gemini_deep_research",
}


def resolve_scenario_pack(
    task_intake: TaskIntakeSpec,
    *,
    goal_hint: str = "",
    context: Mapping[str, Any] | None = None,
) -> ScenarioPack | None:
    """Resolve a stable scenario pack for the canonical intake.

    Packs are resolved in priority order:
    1. Planning packs
    2. Research packs
    3. Fallback to base intake behavior
    """
    current_scenario = str(task_intake.scenario or "").strip().lower()
    explicit_planning = current_scenario == "planning"
    if current_scenario in {"code_review", "image", "repair"}:
        return None
    matched_profile = _matched_planning_profile(task_intake=task_intake, goal_hint=goal_hint, context=context)
    if explicit_planning or matched_profile:
        profile = matched_profile or "business_planning"
        return _planning_pack(profile, task_intake=task_intake)

    research_profile = _matched_research_profile(task_intake=task_intake, goal_hint=goal_hint, context=context)
    if research_profile:
        return _research_pack(research_profile, task_intake=task_intake)

    return None


def apply_scenario_pack(task_intake: TaskIntakeSpec, pack: ScenarioPack) -> TaskIntakeSpec:
    """Apply scenario-pack policy to the canonical intake object."""
    payload = task_intake.to_dict()

    acceptance_payload = dict(task_intake.acceptance.to_dict())
    acceptance_payload.update(dict(pack.acceptance or {}))
    evidence_payload = dict(task_intake.evidence_required.to_dict())
    evidence_payload.update(dict(pack.evidence_required or {}))

    # Attached files should always influence grounding policy, even if the pack
    # template itself is static.
    evidence_payload["ground_in_attached_files"] = bool(task_intake.attachments)
    payload["scenario"] = pack.scenario
    if pack.output_shape:
        payload["output_shape"] = pack.output_shape
    payload["acceptance"] = acceptance_payload
    payload["evidence_required"] = evidence_payload
    return TaskIntakeSpec(**payload)


def summarize_scenario_pack(pack: ScenarioPack | Mapping[str, Any] | None) -> dict[str, Any] | None:
    if pack is None:
        return None
    if isinstance(pack, ScenarioPack):
        source = pack.to_dict()
    else:
        source = dict(pack)
    return {
        "scenario": str(source.get("scenario") or ""),
        "profile": str(source.get("profile") or ""),
        "route_hint": str(source.get("route_hint") or ""),
        "output_shape": str(source.get("output_shape") or ""),
        "execution_preference": str(source.get("execution_preference") or ""),
    }


def _select_planning_profile(
    *,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    context: Mapping[str, Any] | None,
) -> str:
    return _matched_planning_profile(task_intake=task_intake, goal_hint=goal_hint, context=context) or "business_planning"


def _matched_planning_profile(
    *,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    context: Mapping[str, Any] | None,
) -> str:
    haystack = _planning_haystack(task_intake=task_intake, goal_hint=goal_hint, context=context)
    current_scenario = str(task_intake.scenario or "").strip().lower()

    if task_intake.output_shape == "meeting_summary":
        return "meeting_summary"
    for profile, keywords in _PLANNING_PROFILE_KEYWORDS:
        if any(keyword.lower() in haystack for keyword in keywords):
            return profile
    if task_intake.output_shape in {"planning_memo", "meeting_summary"} and current_scenario == "planning":
        if task_intake.output_shape == "meeting_summary":
            return "meeting_summary"
        goal = str(goal_hint or task_intake.goal_hint or "").strip().lower()
        if goal in {"planning", "implementation_planning"}:
            return "implementation_plan"
        return "business_planning"
    return ""


def _planning_haystack(
    *,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    context: Mapping[str, Any] | None,
) -> str:
    return _scenario_haystack(task_intake=task_intake, goal_hint=goal_hint, context=context)


def _scenario_haystack(
    *,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    context: Mapping[str, Any] | None,
) -> str:
    text_fragments = [
        str(task_intake.objective or ""),
        str(task_intake.goal_hint or ""),
        str(goal_hint or ""),
        str(task_intake.output_shape or ""),
        str(task_intake.decision_to_support or ""),
        str(task_intake.audience or ""),
    ]
    context_dict = dict(context or {})
    for key in ("notes", "summary_type", "planning_profile", "topic", "domain"):
        value = context_dict.get(key)
        if isinstance(value, str):
            text_fragments.append(value)
    return "\n".join(fragment for fragment in text_fragments if fragment).lower()


def _is_lightweight_business_planning(task_intake: TaskIntakeSpec) -> bool:
    haystack = _planning_haystack(
        task_intake=task_intake,
        goal_hint=str(task_intake.goal_hint or ""),
        context=task_intake.context,
    )
    return any(keyword.lower() in haystack for keyword in _LIGHTWEIGHT_BUSINESS_PLANNING_KEYWORDS)


def _matched_research_profile(
    *,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    context: Mapping[str, Any] | None,
) -> str:
    haystack = _scenario_haystack(task_intake=task_intake, goal_hint=goal_hint, context=context)
    current_scenario = str(task_intake.scenario or "").strip().lower()
    goal = str(goal_hint or task_intake.goal_hint or "").strip().lower()

    if _looks_like_research_report(haystack=haystack, current_scenario=current_scenario, goal=goal):
        return "research_report"
    if _looks_like_comparative_research(haystack=haystack, current_scenario=current_scenario, goal=goal):
        return "comparative_research"
    if _looks_like_topic_research(haystack=haystack, current_scenario=current_scenario, goal=goal):
        return "topic_research"
    return ""


def _looks_like_research_report(*, haystack: str, current_scenario: str, goal: str) -> bool:
    explicit_report = current_scenario == "report" or goal in {"report", "write_report"}
    has_report_keyword = any(keyword in haystack for keyword in _RESEARCH_REPORT_KEYWORDS)
    has_research_signal = (
        current_scenario == "research"
        or goal in _RESEARCH_GOAL_HINTS
        or any(keyword in haystack for keyword in _RESEARCH_GENERAL_KEYWORDS)
    )
    return has_report_keyword or (explicit_report and has_research_signal)


def _looks_like_comparative_research(*, haystack: str, current_scenario: str, goal: str) -> bool:
    has_compare_signal = any(keyword in haystack for keyword in _COMPARATIVE_RESEARCH_KEYWORDS)
    has_research_signal = (
        current_scenario == "research"
        or goal in _RESEARCH_GOAL_HINTS
        or any(keyword in haystack for keyword in _RESEARCH_GENERAL_KEYWORDS)
    )
    return has_compare_signal and (has_research_signal or current_scenario in {"general", "report"})


def _looks_like_topic_research(*, haystack: str, current_scenario: str, goal: str) -> bool:
    if current_scenario == "research" or goal in _RESEARCH_GOAL_HINTS:
        return True
    return any(keyword in haystack for keyword in _RESEARCH_GENERAL_KEYWORDS)


def _research_pack(profile: str, *, task_intake: TaskIntakeSpec) -> ScenarioPack:
    attachments_present = bool(task_intake.attachments)
    execution_profile = str(task_intake.execution_profile or "default").strip().lower()
    research_route_hint = "analysis_heavy" if execution_profile == "thinking_heavy" else "deep_research"
    consult_mode = "thinking_heavy" if execution_profile == "thinking_heavy" else "deep_research"
    if profile == "comparative_research":
        return ScenarioPack(
            scenario="research",
            profile="comparative_research",
            intent_top="DO_RESEARCH",
            route_hint=research_route_hint,
            output_shape="research_memo",
            execution_preference="job",
            prompt_template_override=TaskTemplate.RESEARCH.value,
            acceptance={
                "profile": "research",
                "required_sections": [
                    "comparison_scope",
                    "comparison_table",
                    "key_findings",
                    "evidence",
                    "recommendation",
                    "uncertainties",
                ],
                "required_artifacts": ["research_memo"],
                "min_evidence_items": 4,
                "require_traceability": True,
            },
            evidence_required={
                "level": "strict",
                "require_sources": True,
                "prefer_primary_sources": True,
                "ground_in_attached_files": attachments_present,
                "require_traceable_claims": True,
            },
            clarify_questions=[
                "Which two or more options, vendors, technologies, or companies should be compared explicitly?",
                "What decision should the comparison support, and what comparison dimensions matter most?",
            ],
            review_rubric=[
                "defines comparison scope and evaluation dimensions clearly",
                "grounds key differences in traceable evidence",
                "ends with a decision-ready recommendation and explicit uncertainties",
            ],
            watch_policy={"checkpoint": "evidence_gate", "notify_on_completion": True},
            provider_hints={
                "research_profile": "comparative_research",
                "consult_mode": consult_mode,
                "execution_profile": execution_profile,
            },
        )
    if profile == "research_report":
        return ScenarioPack(
            scenario="report",
            profile="research_report",
            intent_top="WRITE_REPORT",
            route_hint="report",
            output_shape="markdown_report",
            execution_preference="job",
            prompt_template_override=TaskTemplate.REPORT_GENERATION.value,
            acceptance={
                "profile": "research",
                "required_sections": [
                    "summary",
                    "research_question",
                    "analysis",
                    "evidence",
                    "risks",
                    "recommendation",
                ],
                "required_artifacts": ["markdown_report"],
                "min_evidence_items": 4,
                "require_traceability": True,
            },
            evidence_required={
                "level": "strict",
                "require_sources": True,
                "prefer_primary_sources": True,
                "ground_in_attached_files": attachments_present,
                "require_traceable_claims": True,
            },
            clarify_questions=[
                "What research question, scope boundary, and time horizon should this report answer?",
                "Who is the report for, and should it end as neutral analysis or a decision recommendation?",
            ],
            review_rubric=[
                "opens with a crisp research question and scope",
                "separates evidence from interpretation with traceable support",
                "ends with decision-ready implications, risks, and next steps",
            ],
            watch_policy={"checkpoint": "evidence_gate", "notify_on_completion": True},
            provider_hints={
                "research_profile": "research_report",
                "report_type": "analysis",
                "consult_mode": "deep_research",
            },
        )
    return ScenarioPack(
        scenario="research",
        profile="topic_research",
        intent_top="DO_RESEARCH",
        route_hint=research_route_hint,
        output_shape="research_memo",
        execution_preference="job",
        prompt_template_override=TaskTemplate.RESEARCH.value,
        acceptance={
            "profile": "research",
            "required_sections": [
                "research_question",
                "key_findings",
                "evidence",
                "uncertainties",
                "implications",
            ],
            "required_artifacts": ["research_memo"],
            "min_evidence_items": 3,
            "require_traceability": True,
        },
        evidence_required={
            "level": "strict",
            "require_sources": True,
            "prefer_primary_sources": True,
            "ground_in_attached_files": attachments_present,
            "require_traceable_claims": True,
        },
        clarify_questions=[
            "Which topic, segment, geography, or time window should this research focus on?",
            "Do you want a broad landscape scan, or an answer to a concrete decision question?",
        ],
        review_rubric=[
            "states the research question and scope clearly",
            "grounds major findings in traceable evidence",
            "surfaces uncertainties and what to verify next",
        ],
        watch_policy={"checkpoint": "evidence_gate", "notify_on_completion": True},
        provider_hints={
            "research_profile": "topic_research",
            "consult_mode": consult_mode,
            "execution_profile": execution_profile,
        },
    )


def _planning_pack(profile: str, *, task_intake: TaskIntakeSpec) -> ScenarioPack:
    attachments_present = bool(task_intake.attachments)
    if profile == "meeting_summary":
        return ScenarioPack(
            scenario="planning",
            profile="meeting_summary",
            intent_top="WRITE_REPORT",
            route_hint="report",
            output_shape="meeting_summary",
            execution_preference="job",
            prompt_template_override=TaskTemplate.REPORT_GENERATION.value,
            acceptance={
                "profile": "planning",
                "required_sections": [
                    "meeting_context",
                    "key_points",
                    "decisions",
                    "action_items",
                    "open_questions",
                ],
                "required_artifacts": ["meeting_summary"],
                "min_evidence_items": 0,
                "require_traceability": True,
            },
            evidence_required={
                "level": "standard",
                "require_sources": False,
                "prefer_primary_sources": False,
                "ground_in_attached_files": attachments_present,
                "require_traceable_claims": True,
            },
            clarify_questions=[
                "Which meeting, time window, or thread should this summary cover?",
                "What decisions or action items must be preserved verbatim?",
            ],
            review_rubric=[
                "captures meeting context and participants",
                "separates facts, decisions, and open questions",
                "lists owners and next actions when available",
            ],
            watch_policy={"checkpoint": "delivery_only", "notify_on_completion": True},
            provider_hints={"planning_profile": "meeting_summary"},
        )
    if profile == "interview_notes":
        return ScenarioPack(
            scenario="planning",
            profile="interview_notes",
            intent_top="WRITE_REPORT",
            route_hint="report",
            output_shape="meeting_summary",
            execution_preference="job",
            prompt_template_override=TaskTemplate.REPORT_GENERATION.value,
            acceptance={
                "profile": "planning",
                "required_sections": [
                    "candidate_context",
                    "evidence",
                    "strengths",
                    "concerns",
                    "recommendation",
                    "next_steps",
                ],
                "required_artifacts": ["interview_notes"],
                "min_evidence_items": 0,
                "require_traceability": True,
            },
            evidence_required={
                "level": "standard",
                "require_sources": False,
                "prefer_primary_sources": False,
                "ground_in_attached_files": attachments_present,
                "require_traceable_claims": True,
            },
            clarify_questions=[
                "Which candidate, role, or interview round does this note set cover?",
                "Should the output end as recommendation-only, or include a full evidence ledger?",
            ],
            review_rubric=[
                "keeps interview evidence separate from interpretation",
                "captures strengths and concerns with traceable examples",
                "ends with a clear hiring recommendation or next step",
            ],
            watch_policy={"checkpoint": "delivery_only", "notify_on_completion": True},
            provider_hints={"planning_profile": "interview_notes"},
        )
    if profile == "workforce_planning":
        return ScenarioPack(
            scenario="planning",
            profile="workforce_planning",
            intent_top="BUILD_FEATURE",
            route_hint="funnel",
            output_shape="planning_memo",
            execution_preference="job",
            prompt_template_override=TaskTemplate.IMPLEMENTATION_PLANNING.value,
            funnel_profile="workforce_planning",
            acceptance={
                "profile": "planning",
                "required_sections": [
                    "staffing_goal",
                    "current_state",
                    "demand_drivers",
                    "headcount_plan",
                    "hiring_sequence",
                    "risks",
                ],
                "required_artifacts": ["planning_memo"],
                "min_evidence_items": 0,
                "require_traceability": True,
            },
            evidence_required={
                "level": "standard",
                "require_sources": False,
                "prefer_primary_sources": False,
                "ground_in_attached_files": attachments_present,
                "require_traceable_claims": True,
            },
            clarify_questions=[
                "What planning horizon, org scope, and hiring constraints should the staffing plan cover?",
                "Do you want a target headcount plan, a role-by-role hiring sequence, or both?",
            ],
            review_rubric=[
                "states current state versus staffing target",
                "translates demand drivers into hiring sequence",
                "surfaces hiring risks and mitigation steps",
            ],
            watch_policy={"checkpoint": "quality_gate", "notify_on_completion": True},
            provider_hints={"planning_profile": "workforce_planning"},
        )
    if profile == "implementation_plan":
        return ScenarioPack(
            scenario="planning",
            profile="implementation_plan",
            intent_top="BUILD_FEATURE",
            route_hint="funnel",
            output_shape="planning_memo",
            execution_preference="job",
            prompt_template_override=TaskTemplate.IMPLEMENTATION_PLANNING.value,
            funnel_profile="implementation_plan",
            acceptance={
                "profile": "planning",
                "required_sections": [
                    "goal",
                    "plan",
                    "dependencies",
                    "risks",
                    "validation",
                ],
                "required_artifacts": ["planning_memo"],
                "min_evidence_items": 0,
                "require_traceability": True,
            },
            evidence_required={
                "level": "standard",
                "require_sources": False,
                "prefer_primary_sources": False,
                "ground_in_attached_files": attachments_present,
                "require_traceable_claims": True,
            },
            clarify_questions=[
                "What delivery boundary, milestones, and owners should the implementation plan cover?",
                "Are there hard dependencies, release windows, or validation gates that must be included?",
            ],
            review_rubric=[
                "breaks work into executable phases",
                "covers dependencies, risks, and validation",
                "names concrete milestones or owners when possible",
            ],
            watch_policy={"checkpoint": "quality_gate", "notify_on_completion": True},
            provider_hints={"planning_profile": "implementation_plan"},
        )
    if profile == "business_planning" and _is_lightweight_business_planning(task_intake):
        return ScenarioPack(
            scenario="planning",
            profile="business_planning",
            intent_top="WRITE_REPORT",
            route_hint="report",
            output_shape="planning_memo",
            execution_preference="job",
            prompt_template_override=TaskTemplate.REPORT_GENERATION.value,
            acceptance={
                "profile": "planning",
                "required_sections": [
                    "objective",
                    "current_state",
                    "options",
                    "outline",
                    "next_steps",
                ],
                "required_artifacts": ["planning_memo"],
                "min_evidence_items": 0,
                "require_traceability": True,
            },
            evidence_required={
                "level": "light",
                "require_sources": False,
                "prefer_primary_sources": False,
                "ground_in_attached_files": attachments_present,
                "require_traceable_claims": True,
            },
            clarify_questions=[
                "What business objective or decision owner should this outline support?",
                "Should this stay as a light framework, or do you still want milestones and executable next steps?",
            ],
            review_rubric=[
                "stays concise and framework-first",
                "keeps options and recommended direction easy to scan",
                "ends with concrete next steps without forcing heavy execution detail",
            ],
            watch_policy={"checkpoint": "delivery_only", "notify_on_completion": True},
            provider_hints={"planning_profile": "business_planning", "planning_mode": "outline"},
        )
    return ScenarioPack(
        scenario="planning",
        profile="business_planning",
        intent_top="BUILD_FEATURE",
        route_hint="funnel",
        output_shape="planning_memo",
        execution_preference="job",
        prompt_template_override=TaskTemplate.IMPLEMENTATION_PLANNING.value,
        funnel_profile="business_planning",
        acceptance={
            "profile": "planning",
            "required_sections": [
                "objective",
                "current_state",
                "options",
                "recommended_plan",
                "risks",
                "next_steps",
            ],
            "required_artifacts": ["planning_memo"],
            "min_evidence_items": 0,
            "require_traceability": True,
        },
        evidence_required={
            "level": "standard",
            "require_sources": False,
            "prefer_primary_sources": False,
            "ground_in_attached_files": attachments_present,
            "require_traceable_claims": True,
        },
        clarify_questions=[
            "What business objective, decision owner, and planning horizon should this plan support?",
            "Do you need options comparison only, or an executable recommended plan with milestones?",
        ],
        review_rubric=[
            "states objective and current state clearly",
            "compares options before recommending a plan",
            "ends with concrete next steps and risks",
        ],
        watch_policy={"checkpoint": "quality_gate", "notify_on_completion": True},
        provider_hints={"planning_profile": "business_planning"},
    )
