from __future__ import annotations

from chatgptrest.controller.engine import ControllerEngine


def test_resolve_execution_kind_prefers_job_for_planning_pack() -> None:
    engine = ControllerEngine({"cc_native": object()})

    result = engine._resolve_execution_kind(
        route_plan={"route": "funnel", "executor_lane": ""},
        stable_context={"scenario_pack": {"execution_preference": "job"}},
    )

    assert result == "job"


def test_resolve_execution_kind_requires_explicit_team_request_for_funnel_route() -> None:
    engine = ControllerEngine({"cc_native": object()})

    result = engine._resolve_execution_kind(
        route_plan={"route": "funnel", "executor_lane": ""},
        stable_context={},
    )

    assert result == "job"


def test_resolve_execution_kind_keeps_explicit_topology_request_on_team_lane() -> None:
    engine = ControllerEngine({"cc_native": object()})

    result = engine._resolve_execution_kind(
        route_plan={"route": "funnel", "executor_lane": ""},
        stable_context={"topology_id": "team.topology.demo"},
    )

    assert result == "team"


def test_build_objective_plan_uses_answer_objective_for_implicit_funnel_job_lane() -> None:
    engine = ControllerEngine({"cc_native": object()})

    objective_plan = engine._build_objective_plan(
        question="帮我设计一个积分系统并拆分任务",
        route_plan={"route": "funnel", "executor_lane": ""},
        intent_hint="planning",
        stable_context={},
    )

    assert objective_plan["objective_kind"] == "answer"
    assert [step["kind"] for step in objective_plan["steps"]] == ["intake", "planning", "execution", "delivery"]
