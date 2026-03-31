from __future__ import annotations

from chatgptrest.advisor.ask_contract import AskContract, RiskClass, TaskTemplate
from chatgptrest.advisor.ask_strategist import build_strategy_plan


def test_strategy_plan_requires_clarification_for_high_risk_incomplete_contract() -> None:
    contract = AskContract(
        objective="Help",
        output_shape="text_answer",
        risk_class=RiskClass.HIGH.value,
        task_template=TaskTemplate.DECISION_SUPPORT.value,
        contract_completeness=0.35,
    )

    plan = build_strategy_plan(
        message="Help",
        contract=contract,
        goal_hint="consult",
        context={},
    )

    assert plan.clarify_required is True
    assert plan.execution_mode == "clarify"
    assert plan.clarify_reason_code == "high_risk_incomplete_contract"
    assert plan.clarify_questions
    assert plan.route_hint == "hybrid"


def test_strategy_plan_builds_execution_contract_for_implementation_planning() -> None:
    contract = AskContract(
        objective="Plan the premium ingress strategist rollout",
        decision_to_support="Engineering implementation order",
        audience="Core platform team",
        output_shape="markdown_plan",
        task_template=TaskTemplate.IMPLEMENTATION_PLANNING.value,
        contract_completeness=0.9,
    )

    plan = build_strategy_plan(
        message=contract.objective,
        contract=contract,
        goal_hint="report",
        context={"files": ["spec.md"]},
    )

    assert plan.clarify_required is False
    assert plan.route_hint == "funnel"
    assert plan.output_contract["required_sections"] == ["goal", "plan", "dependencies", "risks", "validation"]
    assert plan.evidence_requirements["ground_in_attached_files"] is True
    assert "validation steps" in " ".join(plan.review_rubric)


def test_strategy_plan_uses_planning_scenario_pack_for_meeting_summary() -> None:
    contract = AskContract(
        objective="整理本周项目例会纪要",
        decision_to_support="对齐行动项",
        audience="项目组",
        output_shape="meeting_summary",
        task_template=TaskTemplate.IMPLEMENTATION_PLANNING.value,
        contract_completeness=0.9,
    )

    plan = build_strategy_plan(
        message=contract.objective,
        contract=contract,
        goal_hint="planning",
        context={
            "scenario_pack": {
                "profile": "meeting_summary",
                "route_hint": "report",
                "prompt_template_override": TaskTemplate.REPORT_GENERATION.value,
                "acceptance": {
                    "required_sections": [
                        "meeting_context",
                        "key_points",
                        "decisions",
                        "action_items",
                        "open_questions",
                    ]
                },
                "review_rubric": [
                    "captures meeting context and participants",
                    "lists owners and next actions when available",
                ],
                "evidence_required": {"require_traceable_claims": True},
            }
        },
    )

    assert plan.route_hint == "report"
    assert plan.output_contract["required_sections"] == [
        "meeting_context",
        "key_points",
        "decisions",
        "action_items",
        "open_questions",
    ]
    assert plan.provider_hints["prompt_template_override"] == TaskTemplate.REPORT_GENERATION.value
    assert plan.review_rubric[0] == "captures meeting context and participants"


def test_strategy_plan_requires_clarification_for_unscoped_interview_notes_without_grounding() -> None:
    contract = AskContract(
        objective="请总结面试纪要",
        output_shape="meeting_summary",
        risk_class=RiskClass.MEDIUM.value,
        task_template=TaskTemplate.IMPLEMENTATION_PLANNING.value,
        contract_completeness=0.6,
    )

    plan = build_strategy_plan(
        message=contract.objective,
        contract=contract,
        goal_hint="planning",
        context={
            "scenario_pack": {
                "profile": "interview_notes",
                "route_hint": "report",
                "watch_policy": {"checkpoint": "delivery_only"},
                "clarify_questions": [
                    "Which candidate, role, or interview round does this note set cover?",
                ],
            }
        },
    )

    assert plan.clarify_required is True
    assert plan.execution_mode == "clarify"


def test_strategy_plan_allows_summary_execution_when_grounding_inputs_exist() -> None:
    contract = AskContract(
        objective="请总结面试纪要",
        output_shape="meeting_summary",
        available_inputs="Files: interview_transcript.md",
        risk_class=RiskClass.MEDIUM.value,
        task_template=TaskTemplate.IMPLEMENTATION_PLANNING.value,
        contract_completeness=0.6,
    )

    plan = build_strategy_plan(
        message=contract.objective,
        contract=contract,
        goal_hint="planning",
        context={
            "files": ["interview_transcript.md"],
            "scenario_pack": {
                "profile": "interview_notes",
                "route_hint": "report",
                "watch_policy": {"checkpoint": "delivery_only"},
                "clarify_questions": [
                    "Which candidate, role, or interview round does this note set cover?",
                ],
            },
        },
    )

    assert plan.clarify_required is False
    assert plan.execution_mode == "execute"


def test_strategy_plan_requires_clarification_for_vague_research_report_without_grounding() -> None:
    contract = AskContract(
        objective="请写一份行业研究报告",
        output_shape="markdown_report",
        risk_class=RiskClass.MEDIUM.value,
        task_template=TaskTemplate.REPORT_GENERATION.value,
        contract_completeness=0.6,
    )

    plan = build_strategy_plan(
        message=contract.objective,
        contract=contract,
        goal_hint="report",
        context={
            "scenario_pack": {
                "profile": "research_report",
                "route_hint": "report",
                "watch_policy": {"checkpoint": "evidence_gate"},
                "clarify_questions": [
                    "What research question, scope boundary, and time horizon should this report answer?",
                ],
            }
        },
    )

    assert plan.clarify_required is True
    assert plan.execution_mode == "clarify"


def test_strategy_plan_allows_topic_research_execution_when_scope_is_explicit() -> None:
    contract = AskContract(
        objective="调研行星滚柱丝杠产业链关键玩家和国产替代进展",
        output_shape="research_memo",
        risk_class=RiskClass.MEDIUM.value,
        task_template=TaskTemplate.RESEARCH.value,
        contract_completeness=0.6,
    )

    plan = build_strategy_plan(
        message=contract.objective,
        contract=contract,
        goal_hint="research",
        context={
            "scenario_pack": {
                "profile": "topic_research",
                "route_hint": "deep_research",
                "watch_policy": {"checkpoint": "evidence_gate"},
                "clarify_questions": [
                    "Which topic, segment, geography, or time window should this research focus on?",
                ],
            }
        },
    )

    assert plan.clarify_required is False
    assert plan.route_hint == "deep_research"


def test_strategy_plan_allows_thinking_heavy_research_lane_when_requested() -> None:
    contract = AskContract(
        objective="快速分析 PRS 产业链风险和机会",
        output_shape="research_memo",
        risk_class=RiskClass.MEDIUM.value,
        task_template=TaskTemplate.RESEARCH.value,
        contract_completeness=0.7,
    )

    plan = build_strategy_plan(
        message=contract.objective,
        contract=contract,
        goal_hint="research",
        context={
            "task_intake": {
                "scenario": "research",
                "execution_profile": "thinking_heavy",
            },
            "scenario_pack": {
                "profile": "topic_research",
                "route_hint": "analysis_heavy",
                "watch_policy": {"checkpoint": "evidence_gate"},
                "provider_hints": {"execution_profile": "thinking_heavy"},
                "clarify_questions": [
                    "Which topic, segment, geography, or time window should this research focus on?",
                ],
            },
        },
    )

    assert plan.clarify_required is False
    assert plan.route_hint == "analysis_heavy"
    assert plan.model_family == "premium_reasoning"


def test_strategy_plan_allows_thinking_heavy_with_core_contract_even_when_completeness_is_mid() -> None:
    contract = AskContract(
        objective="快速评估 PRS 产业链的风险与机会",
        decision_to_support="是否安排下一轮尽调",
        audience="投研团队",
        output_shape="research_memo",
        risk_class=RiskClass.MEDIUM.value,
        task_template=TaskTemplate.RESEARCH.value,
        contract_completeness=0.48,
    )

    plan = build_strategy_plan(
        message=contract.objective,
        contract=contract,
        goal_hint="research",
        context={
            "task_intake": {
                "scenario": "research",
                "execution_profile": "thinking_heavy",
            },
            "scenario_pack": {
                "profile": "topic_research",
                "route_hint": "analysis_heavy",
                "watch_policy": {"checkpoint": "evidence_gate"},
                "provider_hints": {"execution_profile": "thinking_heavy"},
                "clarify_questions": [
                    "Which topic, segment, geography, or time window should this research focus on?",
                ],
            },
        },
    )

    assert plan.clarify_required is False
    assert plan.route_hint == "analysis_heavy"
