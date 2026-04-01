from __future__ import annotations

from chatgptrest.advisor.scenario_packs import apply_scenario_pack, resolve_scenario_pack
from chatgptrest.advisor.task_intake import TaskIntakeSpec


def _make_intake(*, objective: str, scenario: str = "general", output_shape: str = "text_answer") -> TaskIntakeSpec:
    return TaskIntakeSpec(
        trace_id="trace-pack-1",
        objective=objective,
        scenario=scenario,
        output_shape=output_shape,
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
