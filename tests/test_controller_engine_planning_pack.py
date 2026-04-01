from __future__ import annotations

import chatgptrest.advisor.graph as advisor_graph
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


def test_plan_async_route_injects_role_id_into_graph_state(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _capture_normalize(state: dict[str, object]) -> dict[str, object]:
        captured.update(state)
        return {"normalized_message": str(state["user_message"])}

    monkeypatch.setattr(advisor_graph, "normalize", _capture_normalize)
    monkeypatch.setattr(
        advisor_graph,
        "kb_probe",
        lambda state: {
            "kb_has_answer": False,
            "kb_answerability": 0.0,
            "kb_top_chunks": [],
        },
    )
    monkeypatch.setattr(
        advisor_graph,
        "analyze_intent",
        lambda state: {
            "intent_top": "QUICK_QUESTION",
            "intent_confidence": 0.9,
            "multi_intent": False,
            "step_count_est": 1,
            "constraint_count": 0,
            "open_endedness": 0.1,
            "verification_need": False,
            "action_required": False,
        },
    )
    monkeypatch.setattr(
        advisor_graph,
        "route_decision",
        lambda state: {"selected_route": "quick_ask", "route_rationale": "captured-role"},
    )

    engine = ControllerEngine({"cc_native": object()})
    result = engine._plan_async_route(
        question="当前项目状态是什么",
        trace_id="trace-1",
        intent_hint="quick",
        session_id="sess-1",
        account_id="acct-1",
        thread_id="thread-1",
        agent_id="agent-1",
        role_id="planning",
        stable_context={},
    )

    assert captured["role_id"] == "planning"
    assert result["graph_state"]["role_id"] == "planning"
