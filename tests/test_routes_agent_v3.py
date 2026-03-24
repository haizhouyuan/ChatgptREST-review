from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import chatgptrest.api.routes_agent_v3 as routes_agent_v3
from chatgptrest.advisor.ask_contract import AskContract
from chatgptrest.advisor.post_review import generate_basic_review


def _install_fake_runtime(monkeypatch) -> list[dict[str, object]]:
    monkeypatch.setattr(routes_agent_v3, "_advisor_runtime", lambda: {})
    captured: list[dict[str, object]] = []

    class _FakeController:
        def __init__(self, _state):
            pass

        def ask(self, **kwargs):
            captured.append(kwargs)
            turn_idx = len(captured)
            return {
                "run_id": f"run-{turn_idx}",
                "job_id": f"job-{turn_idx}",
                "route": "quick_ask",
                "provider": "chatgpt",
                "controller_status": "DELIVERED",
                "answer": f"answer {turn_idx}",
                "artifacts": [],
            }

        def get_run_snapshot(self, *, run_id: str):
            suffix = run_id.split("-")[-1]
            return {
                "run": {
                    "run_id": run_id,
                    "route": "quick_ask",
                    "provider": "chatgpt",
                    "controller_status": "DELIVERED",
                    "delivery": {"status": "completed", "answer": f"answer {suffix}"},
                    "next_action": {"type": "followup"},
                },
                "artifacts": [],
            }

    def _fake_submit_direct_job(**kwargs):
        captured.append({"direct_job": kwargs})
        return "job-direct-1"

    def _fake_wait_for_job_completion(**kwargs):
        return {
            "job_id": str(kwargs.get("job_id") or "job-direct-1"),
            "job_status": "completed",
            "agent_status": "completed",
            "answer": "generated image",
            "conversation_url": "https://gemini.google.com/app/direct-1",
        }

    def _fake_submit_consultation(**kwargs):
        captured.append({"consult": kwargs})
        return {
            "consultation_id": "cons-1",
            "jobs": [
                {"job_id": "job-a", "provider": "chatgpt_web", "model": "chatgpt_pro"},
                {"job_id": "job-b", "provider": "gemini_web", "model": "gemini_deepthink"},
            ],
        }

    def _fake_wait_for_consultation_completion(**kwargs):
        return {
            "consultation_id": str(kwargs.get("consultation_id") or "cons-1"),
            "status": "completed",
            "agent_status": "completed",
            "jobs": [
                {"job_id": "job-a", "provider": "chatgpt_web", "model": "chatgpt_pro"},
                {"job_id": "job-b", "provider": "gemini_web", "model": "gemini_deepthink"},
            ],
            "answer": "dual review answer",
        }

    monkeypatch.setattr(routes_agent_v3, "ControllerEngine", _FakeController)
    monkeypatch.setattr(routes_agent_v3, "_submit_direct_job", _fake_submit_direct_job)
    monkeypatch.setattr(routes_agent_v3, "_wait_for_job_completion", _fake_wait_for_job_completion)
    monkeypatch.setattr(routes_agent_v3, "_submit_consultation", _fake_submit_consultation)
    monkeypatch.setattr(routes_agent_v3, "_wait_for_consultation_completion", _fake_wait_for_consultation_completion)
    monkeypatch.setattr(routes_agent_v3, "_cancel_job", lambda **kwargs: None)
    return captured


def _make_client(**kwargs) -> TestClient:
    app = FastAPI()
    app.include_router(routes_agent_v3.make_v3_agent_router())
    return TestClient(app, raise_server_exceptions=False, **kwargs)


def _collect_sse(response) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    current_event: str | None = None
    current_data: str | None = None
    for raw_line in response.iter_lines():
        line = raw_line.strip()
        if not line:
            if current_event is not None and current_data is not None:
                events.append((current_event, json.loads(current_data)))
            current_event = None
            current_data = None
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            current_data = line.split(":", 1)[1].strip()
    if current_event is not None and current_data is not None:
        events.append((current_event, json.loads(current_data)))
    return events


def test_agent_turn_requires_message(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post("/v3/agent/turn", json={}, headers=headers)
    assert r.status_code == 400
    assert "message is required" in r.json()["error"]


def test_agent_turn_accepts_valid_request(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={"message": "review this repo for regression risk"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["answer"] == "answer 1"


def test_agent_turn_bridges_session_events_and_completion_to_runtime_event_bus(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    emitted: list[object] = []

    class _FakeBus:
        def emit(self, event) -> bool:
            emitted.append(event)
            return True

    class _FakeRuntime:
        event_bus = _FakeBus()
        observer = None
        memory = None

    monkeypatch.setattr(routes_agent_v3, "get_advisor_runtime_if_ready", lambda: _FakeRuntime())

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={"message": "review this repo for regression risk", "trace_id": "trace-facade-1"},
        headers=headers,
    )

    assert r.status_code == 200
    event_types = [event.event_type for event in emitted]
    assert "session.created" in event_types
    assert "session.status" in event_types
    assert "agent_turn.completed" in event_types
    created = next(event for event in emitted if event.event_type == "session.created")
    completed = next(event for event in emitted if event.event_type == "session.status")
    turn_completed = next(event for event in emitted if event.event_type == "agent_turn.completed")
    assert created.trace_id == "trace-facade-1"
    assert created.data["status"] == "running"
    assert completed.data["status"] == "completed"
    assert completed.data["route"] == "quick_ask"
    assert turn_completed.data["status"] == "completed"
    assert turn_completed.data["route"] == "quick_ask"


def test_agent_turn_injects_task_intake_into_context_and_request_metadata(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    captured = _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "message": "请输出一份项目进展周报",
            "goal_hint": "report",
            "trace_id": "trace-intake-v3",
        },
        headers=headers,
    )

    assert r.status_code == 200
    controller_call = captured[0]
    task_intake = controller_call["stable_context"]["task_intake"]
    assert task_intake["spec_version"] == "task-intake-v2"
    assert task_intake["source"] == "rest"
    assert task_intake["scenario"] == "report"
    assert task_intake["output_shape"] == "markdown_report"
    ask_contract = controller_call["stable_context"]["ask_contract"]
    assert ask_contract["task_template"] == "report_generation"
    assert ask_contract["risk_class"] == "medium"
    request_metadata = controller_call["request_metadata"]
    assert request_metadata["task_intake"]["spec_version"] == "task-intake-v2"
    assert request_metadata["task_intake"]["scenario"] == "report"


def test_agent_turn_planning_injects_scenario_pack(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    captured = _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "message": "请给我做一份未来两个季度的人力规划方案",
            "goal_hint": "planning",
            "trace_id": "trace-intake-v3-planning",
        },
        headers=headers,
    )

    assert r.status_code == 200
    controller_call = captured[0]
    task_intake = controller_call["stable_context"]["task_intake"]
    assert task_intake["scenario"] == "planning"
    assert task_intake["output_shape"] == "planning_memo"
    scenario_pack = controller_call["stable_context"]["scenario_pack"]
    assert scenario_pack["profile"] == "workforce_planning"
    assert scenario_pack["route_hint"] == "funnel"
    assert controller_call["request_metadata"]["scenario_pack"]["profile"] == "workforce_planning"
    assert controller_call["stable_context"]["ask_strategy"]["route_hint"] == "funnel"


def test_agent_turn_light_business_planning_uses_report_lane(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    captured = _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "message": "请帮我做一个业务规划框架，先给简要版本，不要走复杂流程",
            "goal_hint": "planning",
            "trace_id": "trace-intake-v3-business-outline",
        },
        headers=headers,
    )

    assert r.status_code == 200
    controller_call = captured[0]
    scenario_pack = controller_call["stable_context"]["scenario_pack"]
    assert scenario_pack["profile"] == "business_planning"
    assert scenario_pack["route_hint"] == "report"
    assert controller_call["stable_context"]["ask_strategy"]["route_hint"] == "report"


def test_agent_turn_research_pack_uses_deep_research_lane(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    captured = _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "message": "调研行星滚柱丝杠产业链关键玩家和国产替代进展",
            "goal_hint": "research",
            "trace_id": "trace-intake-v3-research-pack",
        },
        headers=headers,
    )

    assert r.status_code == 200
    controller_call = captured[0]
    scenario_pack = controller_call["stable_context"]["scenario_pack"]
    assert scenario_pack["profile"] == "topic_research"
    assert scenario_pack["route_hint"] == "deep_research"
    assert controller_call["stable_context"]["task_intake"]["scenario"] == "research"
    assert controller_call["stable_context"]["ask_strategy"]["route_hint"] == "deep_research"


def test_agent_turn_research_pack_can_use_thinking_heavy_execution_profile(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    captured = _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "message": "快速分析行星滚柱丝杠产业链关键风险与机会",
            "goal_hint": "research",
            "execution_profile": "thinking_heavy",
            "trace_id": "trace-intake-v3-research-heavy",
        },
        headers=headers,
    )

    assert r.status_code == 200
    controller_call = captured[0]
    scenario_pack = controller_call["stable_context"]["scenario_pack"]
    assert scenario_pack["profile"] == "topic_research"
    assert scenario_pack["route_hint"] == "analysis_heavy"
    assert controller_call["stable_context"]["task_intake"]["execution_profile"] == "thinking_heavy"
    assert controller_call["stable_context"]["ask_strategy"]["route_hint"] == "analysis_heavy"


def test_agent_turn_clarify_diagnostics_include_reason_code_and_resubmit_payload(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "message": "Help",
            "contract": {
                "risk_class": "high",
                "task_template": "decision_support",
                "output_shape": "text_answer",
            },
        },
        headers=headers,
    )

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "needs_followup"
    assert body["clarify_diagnostics"]["clarify_gate_reason"] == "high_risk_incomplete_contract"
    assert body["clarify_diagnostics"]["recommended_resubmit_payload"]["session_id"] == body["session_id"]
    assert body["next_action"]["clarify_diagnostics"]["recommended_contract_patch"]["decision_to_support"]
    assert body["lifecycle"]["phase"] == "clarify_required"
    assert body["lifecycle"]["same_session_patch_allowed"] is True
    assert body["delivery"]["mode"] == "sync"
    assert body["effects"]["artifact_delivery"]["count"] == 0


def test_agent_turn_deferred_accepts_lifecycle_and_delivery_surface(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "message": "请先做业务规划骨架",
            "goal_hint": "planning",
            "delivery_mode": "deferred",
            "trace_id": "trace-agent-deferred-surface",
        },
        headers=headers,
    )

    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] is True
    assert body["status"] == "running"
    assert body["lifecycle"]["phase"] == "accepted"
    assert body["lifecycle"]["resumable"] is True
    assert body["delivery"]["mode"] == "deferred"
    assert body["delivery"]["accepted"] is True
    assert body["delivery"]["watchable"] is True


def test_agent_turn_message_parser_fallback_reports_message_parser_contract_source(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "message": (
                "Task: 快速评估 PRS 产业链\n"
                "Decision to support: 是否推进供应链尽调\n"
                "Audience: 投研团队\n"
                "Constraints: 先给简版，不要 deep research\n"
            ),
            "goal_hint": "research",
            "execution_profile": "thinking_heavy",
        },
        headers=headers,
    )

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["control_plane"]["parser_fallback_used"] is True
    assert body["control_plane"]["contract_source"] == "message_parser"


def test_agent_turn_workspace_request_requires_patchable_fields(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "workspace_request": {
                "action": "deliver_report_to_docs",
                "payload": {"title": "Daily report"},
            }
        },
        headers=headers,
    )

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "needs_followup"
    assert body["workspace_diagnostics"]["missing_fields"] == ["body_markdown"]
    assert body["next_action"]["type"] == "await_workspace_patch"
    assert body["control_plane"]["workspace_request_summary"]["action"] == "deliver_report_to_docs"
    assert body["lifecycle"]["phase"] == "clarify_required"
    assert body["effects"]["workspace_action"]["status"] == "clarify_required"
    assert body["effects"]["workspace_action"]["action"] == "deliver_report_to_docs"


def test_agent_turn_workspace_request_same_session_patch_executes(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    class _FakeWorkspaceService:
        def execute(self, request):
            from chatgptrest.workspace.contracts import WorkspaceActionResult

            return WorkspaceActionResult(
                ok=True,
                action=request.action,
                status="completed",
                message="done",
                data={"url": "https://docs.test/doc-1"},
                artifacts=[{"kind": "google_doc", "uri": "https://docs.test/doc-1"}],
            )

    monkeypatch.setattr(routes_agent_v3, "WorkspaceService", _FakeWorkspaceService)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    first = client.post(
        "/v3/agent/turn",
        json={
            "workspace_request": {
                "action": "deliver_report_to_docs",
                "payload": {"title": "Daily report"},
            }
        },
        headers=headers,
    )
    assert first.status_code == 200
    session_id = first.json()["session_id"]

    second = client.post(
        "/v3/agent/turn",
        json={
            "session_id": session_id,
            "contract_patch": {
                "workspace_request": {
                    "payload": {"body_markdown": "# Daily report"}
                }
            },
        },
        headers=headers,
    )

    assert second.status_code == 200
    body = second.json()
    assert body["status"] == "completed"
    assert body["workspace_result"]["data"]["url"] == "https://docs.test/doc-1"
    assert body["control_plane"]["workspace_result"]["action"] == "deliver_report_to_docs"
    assert body["lifecycle"]["phase"] == "completed"
    assert body["effects"]["workspace_action"]["status"] == "completed"


def test_agent_cancel_returns_cancelled_lifecycle_surface(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    first = client.post(
        "/v3/agent/turn",
        json={
            "message": "Help",
            "contract": {
                "risk_class": "high",
                "task_template": "decision_support",
                "output_shape": "text_answer",
            },
        },
        headers=headers,
    )
    assert first.status_code == 200
    session_id = first.json()["session_id"]

    cancel = client.post("/v3/agent/cancel", json={"session_id": session_id}, headers=headers)
    assert cancel.status_code == 200
    body = cancel.json()
    assert body["status"] == "cancelled"
    assert body["lifecycle"]["phase"] == "cancelled"
    assert body["lifecycle"]["session_terminal"] is True
    assert body["delivery"]["terminal"] is True


def test_agent_cancel_blocks_coding_agent_direct_rest_client(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrestctl,chatgptrest-mcp,chatgptrestctl-maint")
    _install_fake_runtime(monkeypatch)

    client = _make_client()
    create_headers = {
        "X-Api-Key": "test-key",
        "X-Client-Name": "chatgptrestctl-maint",
    }
    turn = client.post("/v3/agent/turn", json={"message": "review this repo"}, headers=create_headers)
    assert turn.status_code == 200
    session_id = turn.json()["session_id"]

    headers = {
        "X-Api-Key": "test-key",
        "X-Client-Name": "chatgptrestctl",
    }
    cancel = client.post("/v3/agent/cancel", json={"session_id": session_id}, headers=headers)
    assert cancel.status_code == 403
    body = cancel.json()
    assert body["detail"]["error"] == "coding_agent_direct_rest_blocked"


def test_agent_turn_research_report_pack_uses_report_lane(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    captured = _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "message": "请输出一份行星滚柱丝杠行业研究报告",
            "goal_hint": "report",
            "trace_id": "trace-intake-v3-research-report",
            "decision_to_support": "投资与技术路线判断",
            "audience": "研究团队",
            "attachments": ["research_notes.md"],
        },
        headers=headers,
    )

    assert r.status_code == 200
    controller_call = captured[0]
    scenario_pack = controller_call["stable_context"]["scenario_pack"]
    assert scenario_pack["profile"] == "research_report"
    assert scenario_pack["route_hint"] == "report"
    assert controller_call["stable_context"]["task_intake"]["scenario"] == "report"
    assert controller_call["stable_context"]["ask_strategy"]["route_hint"] == "report"


def test_agent_turn_rejects_unsupported_task_intake_spec_version(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "message": "请输出一份业务规划备忘录",
            "task_intake": {"spec_version": "task-intake-v1"},
        },
        headers=headers,
    )

    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "unsupported_task_intake_spec_version"
    assert body["expected"] == "task-intake-v2"


def test_agent_turn_enforces_client_name_allowlist_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post("/v3/agent/turn", json={"message": "review this repo"}, headers=headers)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "client_not_allowed"


def test_agent_turn_blocks_coding_agent_direct_rest_client(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrestctl,chatgptrest-mcp,chatgptrestctl-maint")

    client = _make_client()
    headers = {
        "X-Api-Key": "test-key",
        "X-Client-Name": "chatgptrestctl",
    }

    r = client.post("/v3/agent/turn", json={"message": "review this repo"}, headers=headers)
    assert r.status_code == 403
    body = r.json()
    assert body["detail"]["error"] == "coding_agent_direct_rest_blocked"
    assert body["detail"]["reason"] == "public_mcp_is_required_for_coding_agents"


def test_agent_turn_allows_explicit_maintenance_client_on_direct_rest(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrestctl,chatgptrest-mcp,chatgptrestctl-maint")
    _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {
        "X-Api-Key": "test-key",
        "X-Client-Name": "chatgptrestctl-maint",
    }

    r = client.post("/v3/agent/turn", json={"message": "review this repo"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["answer"] == "answer 1"


def test_agent_turn_enforces_trace_headers_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")

    client = _make_client()
    headers = {
        "X-Api-Key": "test-key",
        "X-Client-Name": "chatgptrest-mcp",
    }

    r = client.post("/v3/agent/turn", json={"message": "review this repo"}, headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "missing_trace_headers"


def test_agent_turn_blocks_synthetic_or_trivial_prompt(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post("/v3/agent/turn", json={"message": "hello"}, headers=headers)
    assert r.status_code == 400
    assert r.json()["error"] == "agent_trivial_prompt_blocked"


def test_agent_session_not_found(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.get("/v3/agent/session/nonexistent", headers=headers)
    assert r.status_code == 404
    assert "session_not_found" in r.json()["error"]


def test_agent_cancel_not_found(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post("/v3/agent/cancel", json={"session_id": "nonexistent"}, headers=headers)
    assert r.status_code == 404
    assert "session_not_found" in r.json()["error"]


def test_agent_cancel_requires_session_id(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post("/v3/agent/cancel", json={}, headers=headers)
    assert r.status_code == 400
    assert "session_id is required" in r.json()["error"]


def test_agent_health_exempt_from_auth(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()

    r = client.get("/v3/agent/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "not_initialized")


def test_agent_auth_rejects_invalid_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()

    r = client.post("/v3/agent/turn", json={"message": "hello"}, headers={"X-Api-Key": "wrong-key"})
    assert r.status_code == 401


def test_agent_auth_rejects_no_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()

    r = client.post("/v3/agent/turn", json={"message": "hello"})
    assert r.status_code == 401


def test_agent_auth_503_when_no_config(monkeypatch) -> None:
    monkeypatch.delenv("OPENMIND_API_KEY", raising=False)
    monkeypatch.delenv("CHATGPTREST_API_TOKEN", raising=False)
    monkeypatch.delenv("OPENMIND_AUTH_MODE", raising=False)

    client = _make_client()

    r = client.post("/v3/agent/turn", json={"message": "hello"})
    assert r.status_code == 503
    assert "API key not configured" in r.json()["detail"]


def test_agent_auth_accepts_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "bearer-token")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    client = _make_client()

    r = client.post(
        "/v3/agent/turn",
        json={"message": "review this repo for regression risk"},
        headers={"Authorization": "Bearer bearer-token"},
    )
    assert r.status_code == 200
    assert r.json()["answer"] == "answer 1"


def test_write_review_to_evomap_uses_runtime_event_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[object] = []

    class _FakeBus:
        def emit(self, event) -> bool:
            emitted.append(event)
            return True

    class _FakeRuntime:
        event_bus = _FakeBus()

    monkeypatch.setattr(routes_agent_v3, "get_advisor_runtime_if_ready", lambda: _FakeRuntime())

    contract = AskContract(
        contract_id="contract_test_1",
        objective="Review the dashboard changes and explain the regression risk.",
        decision_to_support="merge_or_revise",
        audience="engineering",
        output_shape="bulleted review",
        task_template="code_review",
        contract_source="client",
        contract_completeness=0.9,
    )
    review = generate_basic_review(
        contract=contract,
        answer="## Findings\n\n1. Keep the current patch.\n2. Add one regression test.",
        route="quick_ask",
        provider="chatgpt",
        session_id="agent_sess_test",
        trace_id="trace-premium-1",
    )

    routes_agent_v3._write_review_to_evomap(
        review=review,
        contract=contract,
        answer="## Findings\n\n1. Keep the current patch.\n2. Add one regression test.",
        route="quick_ask",
        provider="chatgpt",
        session_id="agent_sess_test",
        trace_id="trace-premium-1",
    )

    assert [event.event_type for event in emitted] == [
        "premium_ask.review.contract_completeness",
        "premium_ask.review.question_quality",
        "premium_ask.review.answer_quality",
        "premium_ask.review.model_route_fit",
        "premium_ask.review.hallucination_risk",
    ]
    assert {event.trace_id for event in emitted} == {"trace-premium-1"}
    assert {event.session_id for event in emitted} == {"agent_sess_test"}


def test_build_agent_response_emits_review_signals_with_trace_id(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[object] = []

    class _FakeBus:
        def emit(self, event) -> bool:
            emitted.append(event)
            return True

    class _FakeRuntime:
        event_bus = _FakeBus()

    monkeypatch.setattr(routes_agent_v3, "get_advisor_runtime_if_ready", lambda: _FakeRuntime())

    contract = AskContract(
        contract_id="contract_test_2",
        objective="Review the routing patch and identify merge blockers.",
        decision_to_support="merge_or_revise",
        audience="engineering",
        output_shape="findings first review",
        task_template="code_review",
        contract_source="client",
        contract_completeness=0.95,
    )

    payload = routes_agent_v3._build_agent_response(
        session_id="agent_sess_test_2",
        run_id="run-123",
        status="completed",
        answer="## Findings\n\n- No blockers found.",
        route="quick_ask",
        provider_path=["chatgpt"],
        final_provider="chatgpt",
        contract=contract.to_dict(),
        trace_id="trace-premium-2",
    )

    assert payload["review"]["trace_id"] == "trace-premium-2"
    assert len(emitted) == 5
    assert {event.trace_id for event in emitted} == {"trace-premium-2"}


def test_agent_turn_accepts_goal_hints(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    for hint in ["research", "code_review", "report", "image", "consult", "gemini_research"]:
        r = client.post(
            "/v3/agent/turn",
            json={"message": "review this repo for regression risk", "goal_hint": hint},
            headers=headers,
        )
        assert r.status_code == 200, f"goal_hint {hint} should be accepted"


def test_agent_turn_accepts_role_id_user_id_trace_id(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    captured = _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    r = client.post(
        "/v3/agent/turn",
        json={
            "message": "review this repo for regression risk",
            "role_id": "devops",
            "user_id": "test-user",
            "trace_id": "trace-123",
        },
        headers=headers,
    )
    assert r.status_code == 200
    controller_call = next(item for item in captured if "question" in item)
    assert controller_call["role_id"] == "devops"
    assert controller_call["user_id"] == "test-user"
    assert controller_call["trace_id"] == "trace-123"


def test_agent_turn_translates_attachment_contract_block_to_needs_input(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setattr(routes_agent_v3, "_advisor_runtime", lambda: {})
    monkeypatch.setattr(
        routes_agent_v3,
        "_attachment_confirmation_for_job",
        lambda **kwargs: {
            "error_type": "attachment_confirmation_required",
            "status": "needs_input",
            "confidence": "high",
            "attachment_candidates": [
                {"text": "./review_bundle_v1.zip", "reason": "explicit_local_file_reference", "confidence": "high"}
            ],
            "client_actions": [
                "provide_input_file_paths",
                "mark_candidates_as_not_attachments",
                "rewrite_prompt_without_path_like_tokens",
            ],
            "message": "Detected possible local attachment references.",
            "next_action": {
                "type": "attachment_confirmation_required",
                "status": "needs_input",
                "attachment_candidates": [
                    {"text": "./review_bundle_v1.zip", "reason": "explicit_local_file_reference", "confidence": "high"}
                ],
            },
        },
    )

    class _FakeController:
        def __init__(self, _state):
            pass

        def ask(self, **kwargs):
            return {
                "run_id": "run-attach-1",
                "job_id": "job-attach-1",
                "route": "deep_research",
                "provider": "chatgpt",
                "controller_status": "WAITING_EXTERNAL",
                "answer": "",
            }

        def get_run_snapshot(self, *, run_id: str):
            return {
                "run": {
                    "run_id": run_id,
                    "route": "deep_research",
                    "provider": "chatgpt",
                    "controller_status": "FAILED",
                    "final_job_id": "job-attach-1",
                    "delivery": {
                        "status": "failed",
                        "blockers": ["Attachment contract missing"],
                    },
                    "next_action": {"type": "investigate_or_retry", "status": "blocking", "job_id": "job-attach-1"},
                },
                "artifacts": [],
            }

    monkeypatch.setattr(routes_agent_v3, "ControllerEngine", _FakeController)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}
    turn = client.post(
        "/v3/agent/turn",
        json={"message": "Read ./review_bundle_v1.zip and summarize it.", "goal_hint": "research"},
        headers=headers,
    )
    assert turn.status_code == 200
    body = turn.json()
    assert body["status"] == "needs_input"
    assert body["next_action"]["type"] == "attachment_confirmation_required"
    assert body["attachment_confirmation"]["attachment_candidates"][0]["text"] == "./review_bundle_v1.zip"

    status = client.get(f"/v3/agent/session/{body['session_id']}", headers=headers)
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["status"] == "needs_input"
    assert status_body["attachment_confirmation"]["error_type"] == "attachment_confirmation_required"


def test_agent_turn_deferred_returns_stream_url_and_sse(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    turn = client.post(
        "/v3/agent/turn",
        json={"message": "review this repo for regression risk", "delivery_mode": "deferred"},
        headers=headers,
    )
    assert turn.status_code == 202
    body = turn.json()
    assert body["accepted"] is True
    assert body["delivery"]["mode"] == "deferred"
    assert body["stream_url"].endswith(f"/v3/agent/session/{body['session_id']}/stream")

    with client.stream(
        "GET",
        f"/v3/agent/session/{body['session_id']}/stream",
        headers=headers,
    ) as response:
        assert response.status_code == 200
        events = _collect_sse(response)

    assert events
    assert any(event_name in {"snapshot", "session.created", "session.status"} for event_name, _ in events)
    done_event = next(payload for event_name, payload in events if event_name == "done")
    assert done_event["session"]["status"] == "completed"
    assert done_event["session"]["stream_url"].endswith(f"/v3/agent/session/{body['session_id']}/stream")


def test_agent_cancel_bridges_session_cancelled_to_runtime_event_bus(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _install_fake_runtime(monkeypatch)

    emitted: list[object] = []

    class _FakeBus:
        def emit(self, event) -> bool:
            emitted.append(event)
            return True

    class _FakeRuntime:
        event_bus = _FakeBus()
        observer = None
        memory = None

    monkeypatch.setattr(routes_agent_v3, "get_advisor_runtime_if_ready", lambda: _FakeRuntime())

    client = _make_client()
    headers = {"X-Api-Key": "test-key"}

    turn = client.post(
        "/v3/agent/turn",
        json={"message": "review this repo for regression risk", "trace_id": "trace-facade-cancel"},
        headers=headers,
    )
    assert turn.status_code == 200
    session_id = turn.json()["session_id"]

    cancel = client.post("/v3/agent/cancel", json={"session_id": session_id}, headers=headers)
    assert cancel.status_code == 200

    cancelled = [event for event in emitted if event.event_type == "session.cancelled"]
    assert cancelled
    assert cancelled[-1].trace_id == "trace-facade-cancel"
    assert cancelled[-1].data["cancelled_job_ids"] == ["job-1"]


def test_enrich_message_keeps_prompt_clean() -> None:
    contract, _ = routes_agent_v3.normalize_ask_contract(
        message="请帮我做投资研究",
        goal_hint="research",
        context={"depth": "standard"},
    )

    built = routes_agent_v3._enrich_message(
        "请帮我做投资研究",
        {
            "ask_contract": contract.to_dict(),
            "depth": "standard",
            "provider": "chatgpt",
            "custom_hint": "should-not-inline",
        },
    )

    assert "附加上下文" not in built
    assert "should-not-inline" not in built


def test_enrich_message_prefers_compiled_prompt() -> None:
    built = routes_agent_v3._enrich_message(
        "raw message",
        {
            "compiled_prompt": {
                "system_prompt": "system",
                "user_prompt": "compiled user prompt",
                "template_used": "general",
                "model_hints": {},
            }
        },
    )

    assert built == "compiled user prompt"
