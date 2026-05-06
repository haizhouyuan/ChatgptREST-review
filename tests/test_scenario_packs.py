from __future__ import annotations

from chatgptrest.advisor.scenario_packs import apply_scenario_pack, resolve_scenario_pack
from chatgptrest.advisor.task_intake import TaskIntakeSpec


def _make_intake(
    *,
    objective: str,
    scenario: str = "general",
    output_shape: str = "text_answer",
    goal_hint: str = "",
    context: dict[str, object] | None = None,
) -> TaskIntakeSpec:
    return TaskIntakeSpec(
        trace_id="trace-pack-1",
        objective=objective,
        scenario=scenario,
        output_shape=output_shape,
        goal_hint=goal_hint,
        context=dict(context or {}),
    )


def test_resolve_scenario_pack_detects_workforce_planning_from_explicit_planning() -> None:
    intake = _make_intake(objective="请帮我做一份未来两个季度的人力规划方案", scenario="planning", output_shape="planning_memo")

    pack = resolve_scenario_pack(intake)

    assert pack is not None
    assert pack.profile == "workforce_planning"
    assert pack.route_hint == "funnel"
    assert pack.execution_preference == "job"


def test_resolve_scenario_pack_detects_meeting_summary_without_explicit_planning() -> None:
    intake = _make_intake(objective="请整理今天项目例会的会议纪要和行动项")

    pack = resolve_scenario_pack(intake)

    assert pack is not None
    assert pack.profile == "meeting_summary"
    assert pack.route_hint == "report"


def test_resolve_scenario_pack_detects_meeting_summary_from_common_shortform() -> None:
    intake = _make_intake(objective="请整理今天例会纪要", scenario="planning", output_shape="planning_memo")

    pack = resolve_scenario_pack(intake, goal_hint="planning")

    assert pack is not None
    assert pack.profile == "meeting_summary"
    assert pack.route_hint == "report"


def test_apply_scenario_pack_updates_canonical_task_intake() -> None:
    intake = _make_intake(objective="请整理候选人面试纪要")
    pack = resolve_scenario_pack(intake)

    assert pack is not None
    updated = apply_scenario_pack(intake, pack)

    assert updated.scenario == "planning"
    assert updated.output_shape == "meeting_summary"
    assert updated.acceptance.required_sections == [
        "candidate_context",
        "evidence",
        "strengths",
        "concerns",
        "recommendation",
        "next_steps",
    ]


def test_resolve_scenario_pack_uses_light_business_planning_lane_for_outline_request() -> None:
    intake = _make_intake(
        objective="请帮我做一个业务规划框架，先给简要版本，不要走复杂流程",
        scenario="planning",
        output_shape="planning_memo",
    )

    pack = resolve_scenario_pack(intake, goal_hint="planning")

    assert pack is not None
    assert pack.profile == "business_planning"
    assert pack.route_hint == "report"
    assert pack.execution_preference == "job"
    assert pack.prompt_template_override == "report_generation"
    assert pack.watch_policy["checkpoint"] == "delivery_only"


def test_resolve_scenario_pack_uses_compact_implementation_lane_for_next_steps_request() -> None:
    intake = _make_intake(
        objective="请严格依据附件整理三条下一步计划，直接输出三条无序列表，每条一句。",
        scenario="planning",
        output_shape="planning_memo",
    )

    pack = resolve_scenario_pack(intake, goal_hint="planning")

    assert pack is not None
    assert pack.profile == "implementation_plan"
    assert pack.route_hint == "quick_ask"
    assert pack.prompt_template_override == "general"
    assert pack.acceptance["required_sections"] == ["answer"]
    assert pack.watch_policy["checkpoint"] == "delivery_only"
    assert pack.provider_hints["planning_mode"] == "compact_next_steps"


def test_resolve_scenario_pack_honors_explicit_project_diagnosis_task_type() -> None:
    intake = _make_intake(
        objective="请判断 Robovance 项目当前阶段、下一里程碑和主要风险",
        scenario="planning",
        output_shape="planning_memo",
        goal_hint="planning",
        context={"planning_task_type": "project_diagnosis"},
    )

    pack = resolve_scenario_pack(intake, goal_hint="planning")

    assert pack is not None
    assert pack.profile == "project_diagnosis"
    assert pack.route_hint == "funnel"
    assert pack.acceptance["required_sections"] == [
        "current_stage",
        "key_findings",
        "next_milestone",
        "risks",
        "next_steps",
    ]
    assert pack.watch_policy["checkpoint"] == "quality_gate"


def test_resolve_scenario_pack_honors_explicit_research_decision_task_type() -> None:
    intake = _make_intake(
        objective="请把这份调研材料转成可拍板的判断稿",
        scenario="general",
        output_shape="planning_memo",
        goal_hint="research",
        context={"planning_task_type": "research_decision"},
    )

    pack = resolve_scenario_pack(intake, goal_hint="research")

    assert pack is not None
    assert pack.profile == "research_decision"
    assert pack.route_hint == "report"
    assert pack.acceptance["required_sections"] == [
        "core_judgment",
        "supporting_evidence",
        "suggested_action",
        "risks",
        "next_steps",
    ]
    assert pack.watch_policy["checkpoint"] == "quality_gate"


def test_resolve_scenario_pack_honors_explicit_leadership_report_task_type() -> None:
    intake = _make_intake(
        objective="请给我整理一版董事长汇报摘要",
        scenario="general",
        output_shape="text_answer",
        goal_hint="report",
        context={"planning_task_type": "leadership_report"},
    )

    pack = resolve_scenario_pack(intake, goal_hint="report")

    assert pack is not None
    assert pack.profile == "leadership_report"
    assert pack.route_hint == "report"
    assert pack.output_shape == "markdown_report"
    assert pack.acceptance["required_sections"] == [
        "chairman_summary",
        "key_updates",
        "key_risks",
        "decision_needed",
        "next_steps",
    ]


def test_resolve_scenario_pack_honors_explicit_planning_general_task_type() -> None:
    intake = _make_intake(
        objective="请整理一版业务推进方案和下一步计划",
        scenario="planning",
        output_shape="planning_memo",
        goal_hint="planning",
    )

    pack = resolve_scenario_pack(intake, goal_hint="planning")

    assert pack is not None
    assert pack.profile == "planning_general"
    assert pack.route_hint == "funnel"
    assert pack.acceptance["required_sections"] == [
        "objective",
        "current_state",
        "recommended_plan",
        "risks",
        "next_steps",
    ]


def test_resolve_scenario_pack_prefers_performance_summary_profile() -> None:
    intake = _make_intake(
        objective="我要做Q1绩效总结，先回看周报导出和之前的考核表，先按模块把工作总结梳理出来。",
        scenario="planning",
        output_shape="planning_memo",
        goal_hint="planning",
        context={
            "ingress_normalization": {
                "task_family": "performance_summary",
                "interaction_posture": "performance_summary_synthesis",
                "suggested_planning_profile": "performance_summary",
            }
        },
    )

    pack = resolve_scenario_pack(intake, goal_hint="planning")

    assert pack is not None
    assert pack.profile == "performance_summary"
    assert pack.route_hint == "report"
    assert pack.acceptance["required_sections"] == [
        "objective",
        "material_inventory",
        "work_modules",
        "work_items",
        "information_gaps",
        "next_steps",
    ]


def test_resolve_scenario_pack_detects_meeting_summary_from_attachment_transcript_signal() -> None:
    intake = _make_intake(
        objective="请先帮我整理一下今天材料",
        scenario="planning",
        output_shape="planning_memo",
        goal_hint="planning",
        context={
            "attachment_inventory": {
                "files": ["team_sync_transcript.md"],
                "notes": ["meeting transcript uploaded"],
                "preflight": {
                    "planning_roles": ["meeting_transcript"],
                    "material_families": ["document"],
                },
                "items": [
                    {
                        "planning_role": "meeting_transcript",
                        "family": "document",
                        "path": "team_sync_transcript.md",
                        "handling": "direct_review",
                    }
                ],
            }
        },
    )

    pack = resolve_scenario_pack(intake, goal_hint="planning")

    assert pack is not None
    assert pack.profile == "meeting_summary"
    assert pack.route_hint == "report"
    assert pack.acceptance["required_sections"] == [
        "meeting_context",
        "key_points",
        "decisions",
        "action_items",
        "open_questions",
    ]


def test_resolve_scenario_pack_detects_visit_cooperation_prep_from_raw_ingress() -> None:
    intake = _make_intake(
        objective=(
            "杭州资本刚才联系到哲源这边，下周一或周二准备带钛虎机器人董事长一行来拜访，"
            "核心洽谈机器人关节模组业务合作的可行性。我也要提前做一下准备，"
            "详细了解一下这家公司并准备建议回复。"
        ),
        scenario="general",
        output_shape="text_answer",
        context={
            "ingress_normalization": {
                "task_family": "visit_cooperation_prep",
                "interaction_posture": "external_visit_preparation",
                "suggested_planning_profile": "visit_cooperation_prep",
                "signals": ["visit", "prep", "cooperation", "reply", "schedule"],
            }
        },
    )

    pack = resolve_scenario_pack(intake)

    assert pack is not None
    assert pack.profile == "visit_cooperation_prep"
    assert pack.route_hint == "report"
    assert pack.output_shape == "planning_memo"
    assert pack.acceptance["required_sections"] == [
        "quick_judgment",
        "visit_purpose",
        "counterparty_focus",
        "prep_checklist",
        "confirmation_items",
        "suggested_reply",
        "next_steps",
    ]


def test_resolve_scenario_pack_prefers_visit_profile_over_generic_wrapper_default() -> None:
    intake = _make_intake(
        objective=(
            "杭州资本刚才联系到哲源这边，下周一或周二准备带钛虎机器人董事长一行来拜访，"
            "核心洽谈机器人关节模组业务合作的可行性。我也要提前做一下准备，"
            "详细了解一下这家公司并准备建议回复。"
        ),
        scenario="planning",
        output_shape="planning_memo",
        goal_hint="planning",
        context={
            "planning_task_type": "planning_general",
            "ingress_normalization": {
                "task_family": "visit_cooperation_prep",
                "interaction_posture": "external_visit_preparation",
                "suggested_planning_profile": "visit_cooperation_prep",
                "signals": ["visit", "prep", "cooperation", "reply", "schedule"],
            },
        },
    )

    pack = resolve_scenario_pack(intake, goal_hint="planning")

    assert pack is not None
    assert pack.profile == "visit_cooperation_prep"
    assert pack.route_hint == "report"


def test_resolve_scenario_pack_does_not_promote_negated_visit_prep_into_visit_profile() -> None:
    intake = _make_intake(
        objective="帮我看一下这个行业趋势，做一个普通行业研究，不是会前准备，也不是要接待谁。",
        scenario="research",
        output_shape="research_memo",
    )

    pack = resolve_scenario_pack(intake, goal_hint="research")

    assert pack is not None
    assert pack.profile == "topic_research"
    assert pack.route_hint == "deep_research"
    assert pack.scenario == "research"


def test_resolve_scenario_pack_detects_topic_research_from_research_markers() -> None:
    intake = _make_intake(objective="调研行星滚柱丝杠产业链关键玩家和国产替代进展")

    pack = resolve_scenario_pack(intake)

    assert pack is not None
    assert pack.profile == "topic_research"
    assert pack.route_hint == "deep_research"
    assert pack.scenario == "research"


def test_resolve_scenario_pack_detects_comparative_research() -> None:
    intake = _make_intake(objective="对比 PEEK 齿轮和金属齿轮在机器人减速器里的优劣与应用边界")

    pack = resolve_scenario_pack(intake)

    assert pack is not None
    assert pack.profile == "comparative_research"
    assert pack.route_hint == "deep_research"
    assert pack.acceptance["min_evidence_items"] == 4


def test_resolve_scenario_pack_detects_research_report_from_report_lane() -> None:
    intake = _make_intake(
        objective="请输出一份行星滚柱丝杠行业研究报告",
        scenario="report",
        output_shape="markdown_report",
    )

    pack = resolve_scenario_pack(intake, goal_hint="report")

    assert pack is not None
    assert pack.profile == "research_report"
    assert pack.route_hint == "report"
    assert pack.provider_hints["report_type"] == "analysis"
