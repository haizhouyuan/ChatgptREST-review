from __future__ import annotations

import chatgptrest.advisor.graph as advisor_graph
from chatgptrest.controller.engine import ControllerEngine


class _EventBus:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> bool:
        self.events.append(event)
        return True


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


def test_resolve_execution_kind_uses_coding_agent_for_explicit_execution_lane() -> None:
    engine = ControllerEngine({"cc_native": object()})

    result = engine._resolve_execution_kind(
        route_plan={"route": "quick_ask", "executor_lane": ""},
        stable_context={
            "lane_policy": {"execution_lane": "coding_agent", "selected_executor": "claudeminmax"},
            "execution_request": {"requested_execution_lane": "coding_agent", "selected_executor": "claudeminmax"},
        },
    )

    assert result == "coding_agent"


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


def test_build_objective_plan_uses_coding_agent_delivery_for_explicit_coding_lane() -> None:
    engine = ControllerEngine({"cc_native": object()})

    objective_plan = engine._build_objective_plan(
        question="给我一份执行计划",
        route_plan={"route": "quick_ask", "executor_lane": ""},
        intent_hint="planning",
        stable_context={
            "lane_policy": {"execution_lane": "coding_agent", "selected_executor": "claudeminmax"},
            "execution_request": {"requested_execution_lane": "coding_agent", "selected_executor": "claudeminmax"},
        },
    )

    assert objective_plan["objective_kind"] == "coding_agent_delivery"
    assert {"type": "coding_agent_execution_tracked", "value": True} in objective_plan["success_criteria"]


def test_dispatch_route_to_coding_agent_resolves_executor(monkeypatch) -> None:
    import chatgptrest.controller.engine as engine_mod

    class _Resolved:
        executor_id = "claudeminmax"
        family = "claude"
        ready = True

        @staticmethod
        def to_public_dict() -> dict[str, str]:
            return {"executor_id": "claudeminmax", "family": "claude"}

    monkeypatch.setattr(engine_mod, "resolve_coding_agent_executor", lambda **kwargs: _Resolved())
    engine = ControllerEngine({"cc_native": object()})

    step_result, dispatch_request = engine._dispatch_route_to_coding_agent(
        run_id="run-1",
        question="整理下一步",
        route_plan={"route": "quick_ask"},
        stable_context={
            "execution_request": {
                "requested_execution_lane": "coding_agent",
                "requested_executor": "claudeminmax",
            }
        },
        timeout_seconds=60,
    )

    assert step_result.controller_status == "WAITING_EXTERNAL"
    assert step_result.next_action["type"] == "await_coding_agent_completion"
    assert dispatch_request is not None
    assert dispatch_request["resolved_executor"]["executor_id"] == "claudeminmax"


def test_default_job_min_chars_uses_compact_threshold_for_compact_next_steps() -> None:
    engine = ControllerEngine({"cc_native": object()})

    result = engine._default_job_min_chars(
        route="quick_ask",
        stable_context={
            "scenario_pack": {
                "scenario": "planning",
                "output_shape": "planning_memo",
                "provider_hints": {"planning_mode": "compact_next_steps"},
            }
        },
    )

    assert result == 60


def test_default_job_min_chars_keeps_quick_ask_default_without_compact_planning() -> None:
    engine = ControllerEngine({"cc_native": object()})

    result = engine._default_job_min_chars(
        route="quick_ask",
        stable_context={"scenario_pack": {"scenario": "planning", "output_shape": "planning_memo"}},
    )

    assert result == 200


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


def test_emit_runtime_event_publishes_trace_event() -> None:
    bus = _EventBus()
    engine = ControllerEngine({"event_bus": bus})

    engine._emit_runtime_event(
        event_type="advisor_ask.kb_direct",
        trace_id="trace-kb-1",
        session_id="sess-kb-1",
        data={"artifact_ids": ["kb-doc-1"]},
    )

    assert [event.event_type for event in bus.events] == ["advisor_ask.kb_direct"]
    event = bus.events[0]
    assert event.trace_id == "trace-kb-1"
    assert event.session_id == "sess-kb-1"
    assert event.data["artifact_ids"] == ["kb-doc-1"]
