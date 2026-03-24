from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import chatgptrest.advisor.graph as advisor_graph
from chatgptrest.advisor.runtime import reset_advisor_runtime
from chatgptrest.api.routes_advisor_v3 import make_v3_advisor_router
from chatgptrest.core.db import connect


def _make_client() -> TestClient:
    reset_advisor_runtime()
    # Keep v3 end-to-end expectations independent from other suites that
    # intentionally tighten the shared router rate limit.
    os.environ.pop("OPENMIND_RATE_LIMIT", None)
    app = FastAPI()
    app.include_router(make_v3_advisor_router())
    return TestClient(app, raise_server_exceptions=False)


def _patch_quick_ask_route(monkeypatch) -> None:
    monkeypatch.setattr(advisor_graph, "normalize", lambda state: {"normalized_message": state["user_message"]})
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
        lambda state: {"selected_route": "quick_ask", "route_rationale": "test quick ask", "executor_lane": "chatgpt"},
    )


def _patch_route(monkeypatch, *, route: str, rationale: str, executor_lane: str = "") -> None:
    monkeypatch.setattr(advisor_graph, "normalize", lambda state: {"normalized_message": state["user_message"]})
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
            "step_count_est": 2,
            "constraint_count": 0,
            "open_endedness": 0.4,
            "verification_need": False,
            "action_required": route == "action",
        },
    )
    monkeypatch.setattr(
        advisor_graph,
        "route_decision",
        lambda state: {
            "selected_route": route,
            "route_rationale": rationale,
            "executor_lane": executor_lane,
        },
    )


def test_v3_advise_round_trip_records_trace_and_evomap_signal(monkeypatch) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/advise",
        json={"message": "请快速梳理这个需求的关键问题和下一步建议"},
        headers=headers,
    )
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "completed"
    assert isinstance(body.get("trace_id"), str) and body["trace_id"]
    assert isinstance(body.get("selected_route"), str) and body["selected_route"]
    assert isinstance(body.get("answer"), str) and body["answer"]

    trace = client.get(f"/v2/advisor/trace/{body['trace_id']}", headers=headers)
    assert trace.status_code == 200
    trace_body = trace.json()
    assert trace_body["trace_id"] == body["trace_id"]
    assert trace_body["selected_route"] == body["selected_route"]

    stats = client.get("/v2/advisor/evomap/stats", headers=headers)
    assert stats.status_code == 200
    stats_body = stats.json()
    assert stats_body["total"] >= 1
    assert sum(stats_body["by_type"].values()) == stats_body["total"]
    assert "route.selected" in stats_body["by_type"]


def test_v3_advise_forwards_identity_to_advisor_api(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    calls: dict[str, object] = {}

    class _FakeApi:
        def advise(self, message: str, **kwargs: object) -> dict[str, object]:
            calls["message"] = message
            calls["kwargs"] = dict(kwargs)
            return {
                "status": "completed",
                "trace_id": "trace-identity",
                "selected_route": "quick_ask",
                "answer": "ok",
            }

    fake_state = {
        "api": _FakeApi(),
        "observer": None,
        "event_bus": None,
        "evomap_knowledge_db": None,
        "circuit_breaker": None,
        "kb_scorer": None,
        "gate_tuner": None,
    }
    monkeypatch.setattr("chatgptrest.advisor.runtime.get_advisor_runtime", lambda: fake_state)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/advise",
        json={
            "message": "请继续执行",
            "role_id": "devops",
            "session_id": "sess-openclaw",
            "account_id": "acct-openclaw",
            "thread_id": "thread-openclaw",
            "agent_id": "agent-openclaw",
            "trace_id": "12345678123456781234567812345678",
            "context": {"channel": "openclaw", "incident": "INC-001"},
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"] == "trace-identity"
    assert body["request_metadata"] == {
        "trace_id": "12345678123456781234567812345678",
        "session_id": "sess-openclaw",
        "account_id": "acct-openclaw",
        "thread_id": "thread-openclaw",
        "agent_id": "agent-openclaw",
        "role_id": "devops",
        "user_id": "acct-openclaw",
        "intent_hint": "",
        "task_intake": {
            "spec_version": "task-intake-v2",
            "source": "rest",
            "ingress_lane": "advisor_advise_v2",
            "scenario": "general",
            "output_shape": "text_answer",
        },
    }
    assert calls["message"] == "请继续执行"
    assert calls["kwargs"] == {
        "session_id": "sess-openclaw",
        "account_id": "acct-openclaw",
        "thread_id": "thread-openclaw",
        "agent_id": "agent-openclaw",
        "task_intake": {
            "spec_version": "task-intake-v2",
            "source": "rest",
            "ingress_lane": "advisor_advise_v2",
            "trace_id": "12345678123456781234567812345678",
            "objective": "请继续执行",
            "scenario": "general",
            "output_shape": "text_answer",
            "acceptance": {
                "profile": "light",
                "required_sections": ["answer"],
                "required_artifacts": [],
                "min_evidence_items": 0,
                "require_traceability": False,
                "pass_score": 0.8,
            },
            "session_id": "sess-openclaw",
            "user_id": "acct-openclaw",
            "account_id": "acct-openclaw",
            "thread_id": "thread-openclaw",
            "agent_id": "agent-openclaw",
            "role_id": "devops",
            "attachments": [],
            "context": {"channel": "openclaw", "incident": "INC-001"},
            "evidence_required": {
                "level": "light",
                "require_sources": False,
                "prefer_primary_sources": False,
                "ground_in_attached_files": False,
                "require_traceable_claims": False,
            },
        },
        "context": {
            "channel": "openclaw",
            "incident": "INC-001",
            "task_intake": {
                "spec_version": "task-intake-v2",
                "source": "rest",
                "ingress_lane": "advisor_advise_v2",
                "trace_id": "12345678123456781234567812345678",
                "objective": "请继续执行",
                "scenario": "general",
                "output_shape": "text_answer",
                "acceptance": {
                    "profile": "light",
                    "required_sections": ["answer"],
                    "required_artifacts": [],
                    "min_evidence_items": 0,
                    "require_traceability": False,
                    "pass_score": 0.8,
                },
                "session_id": "sess-openclaw",
                "user_id": "acct-openclaw",
                "account_id": "acct-openclaw",
                "thread_id": "thread-openclaw",
                "agent_id": "agent-openclaw",
                "role_id": "devops",
                "attachments": [],
                "context": {"channel": "openclaw", "incident": "INC-001"},
                "evidence_required": {
                    "level": "light",
                    "require_sources": False,
                    "prefer_primary_sources": False,
                    "ground_in_attached_files": False,
                    "require_traceable_claims": False,
                },
            },
        },
        "trace_id": "12345678123456781234567812345678",
        "role_id": "devops",
        "user_id": "acct-openclaw",
    }


def test_v3_advise_backfills_request_metadata_trace_id_from_runtime_result(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    class _FakeApi:
        def advise(self, message: str, **kwargs: object) -> dict[str, object]:
            return {
                "status": "completed",
                "trace_id": "trace-generated-by-api",
                "selected_route": "quick_ask",
                "answer": f"echo:{message}",
            }

    fake_state = {
        "api": _FakeApi(),
        "observer": None,
        "event_bus": None,
        "evomap_knowledge_db": None,
        "circuit_breaker": None,
        "kb_scorer": None,
        "gate_tuner": None,
    }
    monkeypatch.setattr("chatgptrest.advisor.runtime.get_advisor_runtime", lambda: fake_state)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/advise",
        json={
            "message": "请继续执行",
            "session_id": "sess-openclaw",
            "account_id": "acct-openclaw",
            "thread_id": "thread-openclaw",
            "agent_id": "agent-openclaw",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"] == "trace-generated-by-api"
    assert body["request_metadata"]["trace_id"] == "trace-generated-by-api"
    assert body["request_metadata"]["session_id"] == "sess-openclaw"
    assert body["request_metadata"]["account_id"] == "acct-openclaw"
    assert body["request_metadata"]["thread_id"] == "thread-openclaw"
    assert body["request_metadata"]["agent_id"] == "agent-openclaw"
    assert isinstance(body.get("run_id"), str) and body["run_id"]
    assert body["controller_status"] == "DELIVERED"


def test_v3_advise_kb_direct_defaults_to_raw_answer_without_llm_synthesis(monkeypatch) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENMIND_KB_DIRECT_SYNTHESIS", raising=False)
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    monkeypatch.setattr(advisor_graph, "normalize", lambda state: {"normalized_message": state["user_message"]})
    monkeypatch.setattr(
        advisor_graph,
        "kb_probe",
        lambda state: {
            "kb_has_answer": True,
            "kb_answerability": 0.95,
            "kb_top_chunks": [
                {
                    "title": "Runbook",
                    "snippet": "先检查 API health，再检查 worker backlog。",
                    "artifact_id": "art-runbook",
                }
            ],
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
        lambda state: {"selected_route": "kb_answer", "route_rationale": "test kb direct"},
    )

    def _should_not_run(*args, **kwargs):
        raise AssertionError("KB direct synthesis should be skipped by default")

    monkeypatch.setattr(advisor_graph, "_get_llm_fn", _should_not_run)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/advise",
        json={"message": "请直接告诉我排障第一步"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["selected_route"] == "kb_answer"
    assert "Runbook" in body["answer"]
    assert "先检查 API health，再检查 worker backlog。" in body["answer"]


def test_v3_advise_kb_direct_can_opt_in_to_llm_synthesis(monkeypatch) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("OPENMIND_KB_DIRECT_SYNTHESIS", "1")
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    monkeypatch.setattr(advisor_graph, "normalize", lambda state: {"normalized_message": state["user_message"]})
    monkeypatch.setattr(
        advisor_graph,
        "kb_probe",
        lambda state: {
            "kb_has_answer": True,
            "kb_answerability": 0.95,
            "kb_top_chunks": [
                {
                    "title": "Runbook",
                    "snippet": "先检查 API health，再检查 worker backlog。",
                    "artifact_id": "art-runbook",
                }
            ],
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
        lambda state: {"selected_route": "kb_answer", "route_rationale": "test kb direct"},
    )
    monkeypatch.setattr(
        advisor_graph,
        "_get_llm_fn",
        lambda *args, **kwargs: lambda prompt, system_msg="": "这是综合后的自然语言答案，并补充了关键细节。",
    )

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={"question": "请直接告诉我排障第一步"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["provider"] == "kb"
    assert body["answer"] == "这是综合后的自然语言答案，并补充了关键细节。"


def test_v3_ask_injects_identity_into_graph_state(monkeypatch) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENMIND_KB_DIRECT_SYNTHESIS", raising=False)
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    captured: dict[str, object] = {}

    def _capture_normalize(state: dict[str, object]) -> dict[str, object]:
        captured.update(state)
        return {"normalized_message": state["user_message"]}

    monkeypatch.setattr(advisor_graph, "normalize", _capture_normalize)
    monkeypatch.setattr(
        advisor_graph,
        "kb_probe",
        lambda state: {
            "kb_has_answer": True,
            "kb_answerability": 0.95,
            "kb_top_chunks": [
                {
                    "title": "Runbook",
                    "snippet": "先检查 API health，再检查 worker backlog。",
                    "artifact_id": "art-runbook",
                }
            ],
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
        lambda state: {"selected_route": "kb_answer", "route_rationale": "identity capture"},
    )

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={
            "question": "请直接告诉我排障第一步",
            "session_id": "sess-openclaw",
            "account_id": "acct-openclaw",
            "thread_id": "thread-openclaw",
            "agent_id": "agent-openclaw",
            "trace_id": "trace-openclaw-ask",
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["trace_id"] == "trace-openclaw-ask"
    assert body["request_metadata"]["trace_id"] == "trace-openclaw-ask"
    assert body["request_metadata"]["session_id"] == "sess-openclaw"
    assert body["request_metadata"]["account_id"] == "acct-openclaw"
    assert body["request_metadata"]["thread_id"] == "thread-openclaw"
    assert body["request_metadata"]["agent_id"] == "agent-openclaw"
    assert captured["session_id"] == "sess-openclaw"
    assert captured["account_id"] == "acct-openclaw"
    assert captured["thread_id"] == "thread-openclaw"
    assert captured["agent_id"] == "agent-openclaw"


def test_v3_ask_applies_explicit_role_binding(monkeypatch) -> None:
    from chatgptrest.kernel.role_context import get_current_role_name

    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENMIND_KB_DIRECT_SYNTHESIS", raising=False)
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    monkeypatch.setattr(advisor_graph, "normalize", lambda state: {"normalized_message": state["user_message"]})
    monkeypatch.setattr(
        advisor_graph,
        "kb_probe",
        lambda state: {
            "kb_has_answer": True,
            "kb_answerability": 0.95,
            "kb_top_chunks": [
                {
                    "title": "Devops Runbook",
                    "snippet": "先检查 API health，再检查 worker backlog。",
                    "artifact_id": "art-runbook",
                }
            ],
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
        lambda state: {
            "selected_route": "kb_answer",
            "route_rationale": f"role={get_current_role_name()}",
        },
    )

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={"question": "请直接告诉我排障第一步", "role_id": "devops"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["role_id"] == "devops"
    assert "role=devops" in body["route_rationale"]


def test_v3_ask_rejects_unknown_role_id(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={"question": "请帮我看看", "role_id": "unknown-role"},
        headers=headers,
    )
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"] == "invalid_role_id"
    assert body["detail"]["role_id"] == "unknown-role"


def test_v3_ask_does_not_short_circuit_complex_kb_hits(monkeypatch) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENMIND_KB_DIRECT_SYNTHESIS", raising=False)
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    monkeypatch.setattr(advisor_graph, "normalize", lambda state: {"normalized_message": state["user_message"]})
    monkeypatch.setattr(
        advisor_graph,
        "kb_probe",
        lambda state: {
            "kb_has_answer": True,
            "kb_answerability": 0.95,
            "kb_top_chunks": [
                {
                    "title": "Legacy Plan",
                    "snippet": "这里有一些历史资料，但还不足以直接完成当前复杂需求。",
                    "artifact_id": "art-legacy",
                }
            ],
        },
    )
    monkeypatch.setattr(
        advisor_graph,
        "analyze_intent",
        lambda state: {
            "intent_top": "QUICK_QUESTION",
            "intent_confidence": 0.9,
            "multi_intent": True,
            "step_count_est": 3,
            "constraint_count": 1,
            "open_endedness": 0.5,
            "verification_need": False,
            "action_required": False,
        },
    )
    monkeypatch.setattr(
        advisor_graph,
        "route_decision",
        lambda state: {"selected_route": "kb_answer", "route_rationale": "test complex kb hit"},
    )

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={"question": "请输出关键业务流程、核心实体和最小可行版本方案"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submitted"
    assert body["provider"] == "chatgpt"
    assert body["job_id"]


def test_v3_ask_auto_idempotency_reuses_same_identity_request(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _patch_quick_ask_route(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    body = {
        "question": "请帮我整理当前故障排查思路",
        "session_id": "session-a",
        "user_id": "user-a",
        "role_id": "devops",
        "context": {"incident": "INC-001"},
    }

    first = client.post("/v2/advisor/ask", json=body, headers=headers)
    second = client.post("/v2/advisor/ask", json=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]
    assert first.json()["run_id"] == second.json()["run_id"]


def test_v3_ask_auto_idempotency_splits_different_sessions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _patch_quick_ask_route(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    first = client.post(
        "/v2/advisor/ask",
        json={"question": "同一句问题", "session_id": "session-a", "user_id": "user-a"},
        headers=headers,
    )
    second = client.post(
        "/v2/advisor/ask",
        json={"question": "同一句问题", "session_id": "session-b", "user_id": "user-a"},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job_id"] != second.json()["job_id"]


def test_v3_ask_auto_idempotency_ignores_volatile_context_fields(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _patch_quick_ask_route(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    first = client.post(
        "/v2/advisor/ask",
        json={
            "question": "同一句问题",
            "session_id": "session-a",
            "user_id": "user-a",
            "context": {"incident": "INC-001", "trace_id": "trace-a", "session_key": "session:a"},
        },
        headers=headers,
    )
    second = client.post(
        "/v2/advisor/ask",
        json={
            "question": "同一句问题",
            "session_id": "session-a",
            "user_id": "user-a",
            "context": {"incident": "INC-001", "trace_id": "trace-b", "session_key": "session:b"},
        },
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]


def test_v3_ask_auto_idempotency_keeps_stable_business_context(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _patch_quick_ask_route(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    first = client.post(
        "/v2/advisor/ask",
        json={
            "question": "同一句问题",
            "session_id": "session-a",
            "user_id": "user-a",
            "context": {"incident": "INC-001"},
        },
        headers=headers,
    )
    second = client.post(
        "/v2/advisor/ask",
        json={
            "question": "同一句问题",
            "session_id": "session-a",
            "user_id": "user-a",
            "context": {"incident": "INC-002"},
        },
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job_id"] != second.json()["job_id"]


def test_v3_ask_passes_file_paths_and_can_disable_auto_context(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setattr(advisor_graph, "normalize", lambda state: {"normalized_message": state["user_message"]})
    monkeypatch.setattr(
        advisor_graph,
        "kb_probe",
        lambda state: {
            "kb_has_answer": False,
            "kb_answerability": 0.2,
            "kb_top_chunks": [
                {"title": "Runbook A", "snippet": "Chunk A"},
                {"title": "Runbook B", "snippet": "Chunk B"},
            ],
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
        lambda state: {"selected_route": "quick_ask", "route_rationale": "files only"},
    )

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={
            "question": "请评审 dashboard UX",
            "file_paths": ["/tmp/dashboard.zip", "/tmp/notes.md"],
            "auto_context": False,
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    with connect(tmp_path / "jobdb.sqlite3") as conn:
        row = conn.execute("SELECT input_json FROM jobs WHERE job_id = ?", (body["job_id"],)).fetchone()
    assert row is not None
    input_obj = json.loads(str(row["input_json"]))
    assert input_obj["file_paths"] == ["/tmp/dashboard.zip", "/tmp/notes.md"]
    assert "相关知识库参考" not in input_obj["question"]
    assert "Chunk A" not in input_obj["question"]


def test_v3_ask_limits_auto_context_chunks(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    monkeypatch.setattr(advisor_graph, "normalize", lambda state: {"normalized_message": state["user_message"]})
    monkeypatch.setattr(
        advisor_graph,
        "kb_probe",
        lambda state: {
            "kb_has_answer": False,
            "kb_answerability": 0.2,
            "kb_top_chunks": [
                {"title": "Runbook A", "snippet": "Chunk A"},
                {"title": "Runbook B", "snippet": "Chunk B"},
            ],
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
        lambda state: {"selected_route": "quick_ask", "route_rationale": "top-k gate"},
    )

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={
            "question": "请评审 dashboard UX",
            "auto_context": True,
            "auto_context_top_k": 1,
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    with connect(tmp_path / "jobdb.sqlite3") as conn:
        row = conn.execute("SELECT input_json FROM jobs WHERE job_id = ?", (body["job_id"],)).fetchone()
    assert row is not None
    input_obj = json.loads(str(row["input_json"]))
    assert "相关知识库参考" not in input_obj["question"]
    assert "Runbook A" not in input_obj["question"]
    assert "Chunk A" not in input_obj["question"]
    assert "Runbook B" not in input_obj["question"]
    assert "Chunk B" not in input_obj["question"]


def test_v3_ask_explicit_idempotency_key_conflicts_across_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _patch_quick_ask_route(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    first = client.post(
        "/v2/advisor/ask",
        json={
            "question": "请继续处理这个问题",
            "session_id": "session-a",
            "user_id": "user-a",
            "idempotency_key": "fixed-idem-key",
        },
        headers=headers,
    )
    second = client.post(
        "/v2/advisor/ask",
        json={
            "question": "请继续处理这个问题",
            "session_id": "session-b",
            "user_id": "user-a",
            "idempotency_key": "fixed-idem-key",
        },
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"] == "idempotency_collision"


def test_v3_ask_job_creation_failure_hides_traceback_and_returns_degradation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _patch_quick_ask_route(monkeypatch)

    def _boom(*args, **kwargs):
        raise RuntimeError("db write exploded")

    monkeypatch.setattr("chatgptrest.core.job_store.create_job", _boom)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={
            "question": "请继续处理这个问题",
            "session_id": "session-a",
            "user_id": "user-a",
            "trace_id": "trace-job-failure",
        },
        headers=headers,
    )

    assert response.status_code == 502
    body = response.json()
    assert body["ok"] is False
    assert body["error_type"] == "RuntimeError"
    assert body["trace_id"] == "trace-job-failure"
    assert "traceback" not in body
    assert body["request_metadata"]["trace_id"] == "trace-job-failure"
    assert any(item["component"] == "advisor_ask" for item in body["degradation"])


def test_v3_advise_trace_falls_back_to_controller_snapshot(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    class _FakeApi:
        def advise(self, message: str, **kwargs: object) -> dict[str, object]:
            return {
                "status": "completed",
                "trace_id": "trace-controller-fallback",
                "selected_route": "quick_ask",
                "route_rationale": "controller fallback",
                "answer": f"echo:{message}",
                "route_result": {"final_text": f"echo:{message}"},
            }

    fake_state = {
        "api": _FakeApi(),
        "observer": None,
        "event_bus": None,
        "evomap_knowledge_db": None,
        "circuit_breaker": None,
        "kb_scorer": None,
        "gate_tuner": None,
    }
    monkeypatch.setattr("chatgptrest.advisor.runtime.get_advisor_runtime", lambda: fake_state)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}

    response = client.post(
        "/v2/advisor/advise",
        json={"message": "请继续执行", "trace_id": "trace-controller-fallback"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["controller_status"] == "DELIVERED"
    assert isinstance(body.get("run_id"), str) and body["run_id"]

    trace = client.get("/v2/advisor/trace/trace-controller-fallback", headers=headers)
    assert trace.status_code == 200
    trace_body = trace.json()
    assert trace_body["trace_id"] == "trace-controller-fallback"
    assert trace_body["selected_route"] == "quick_ask"
    assert trace_body["answer"] == "echo:请继续执行"

    run = client.get(f"/v2/advisor/run/{body['run_id']}", headers=headers)
    assert run.status_code == 200
    run_body = run.json()
    assert run_body["run"]["trace_id"] == "trace-controller-fallback"
    assert run_body["run"]["controller_status"] == "DELIVERED"
    assert any(item["work_id"] == "deliver" for item in run_body["work_items"])


def test_v3_ask_returns_controller_snapshot(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _patch_quick_ask_route(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}

    response = client.post(
        "/v2/advisor/ask",
        json={
            "question": "请帮我整理当前故障排查思路",
            "session_id": "session-a",
            "user_id": "user-a",
            "role_id": "devops",
            "context": {"incident": "INC-001"},
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["controller_status"] == "WAITING_EXTERNAL"
    assert isinstance(body.get("run_id"), str) and body["run_id"]
    assert body["delivery"]["status"] == "submitted"
    assert body["next_action"]["type"] == "await_job_completion"
    assert any(item["work_id"] == "execute" for item in body["work_items"])

    run = client.get(f"/v2/advisor/run/{body['run_id']}", headers=headers)
    assert run.status_code == 200
    run_body = run.json()
    assert run_body["run"]["request_id"] == body["request_metadata"]["idempotency_key"]
    assert run_body["run"]["controller_status"] == "WAITING_EXTERNAL"
    assert any(item["work_id"] == "plan" for item in run_body["work_items"])


def test_v3_ask_objective_first_planned_then_executed_by_step_executor(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _patch_quick_ask_route(monkeypatch)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={
            "question": "请整理这个故障的下一步执行计划",
            "session_id": "session-objective",
            "user_id": "user-objective",
            "context": {"incident": "INC-009", "repo": "ChatgptREST"},
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["controller_status"] == "WAITING_EXTERNAL"
    assert any(item["work_id"] == "execute" and item["kind"] == "execution" for item in body["work_items"])

    run = client.get(f"/v2/advisor/run/{body['run_id']}", headers=headers)
    assert run.status_code == 200
    snapshot = run.json()
    assert snapshot["run"]["objective_text"] == "请整理这个故障的下一步执行计划"
    assert snapshot["run"]["objective_kind"] == "answer"
    assert snapshot["run"]["plan_version"] >= 2
    assert snapshot["run"]["delivery_target"]["mode"] == "decision_ready"
    assert any(item["type"] == "external_execution_tracked" for item in snapshot["run"]["success_criteria"])
    assert any(step["work_id"] == "execute" for step in snapshot["run"]["plan"]["steps"])


def test_v3_ask_action_route_returns_effect_intent_waiting_human(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _patch_route(monkeypatch, route="action", rationale="needs external effect")
    from chatgptrest.controller.engine import ControllerEngine

    monkeypatch.setattr(
        ControllerEngine,
        "_evaluate_action_effect",
        lambda self, **kwargs: {
            "route_result": {
                "status": "action_planned",
                "answer": "会生成一个发送通知的执行意图，等待确认。",
                "required_capabilities": ["notify"],
                "available_capabilities": ["notify"],
                "needs_confirmation": True,
                "executor": "action",
            },
            "route_status": "action_planned",
        },
    )

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={
            "question": "给团队发一条通知，说今晚 9 点开始切换",
            "session_id": "session-effect",
            "user_id": "user-effect",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] is None
    assert body["controller_status"] == "WAITING_HUMAN"
    assert body["next_action"]["type"] == "await_user_confirmation"
    assert any(item["work_id"] == "effect_intent" and item["kind"] == "effect" for item in body["work_items"])
    assert any(item["kind"] == "effect_intent" for item in body["artifacts"])
    assert any(item["status"] == "NEEDS_HUMAN" for item in body["checkpoints"])


def test_v3_ask_upload_to_google_drive_routes_to_action_effect_intent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

    from chatgptrest.controller.engine import ControllerEngine

    class _Runtime(dict):
        __getattr__ = dict.get

    minimal_runtime = _Runtime(
        api=None,
        llm=None,
        event_bus=None,
        observer=None,
        routing_fabric=None,
        cc_native=None,
        kb_hub=None,
        memory=None,
        outbox=None,
    )
    monkeypatch.setattr("chatgptrest.advisor.runtime.get_advisor_runtime", lambda: minimal_runtime)
    monkeypatch.setattr(
        ControllerEngine,
        "_evaluate_action_effect",
        lambda self, **kwargs: {
            "route_result": {
                "status": "action_planned",
                "answer": "会生成一个上传到 Google Drive 的执行意图，等待确认。",
                "required_capabilities": ["google_drive"],
                "available_capabilities": ["google_drive"],
                "needs_confirmation": True,
                "executor": "action",
            },
            "route_status": "action_planned",
        },
    )

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={
            "question": "把这个文件上传到Google Drive",
            "session_id": "session-drive",
            "user_id": "user-drive",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "action"
    assert body["job_id"] is None
    assert body["controller_status"] == "WAITING_HUMAN"
    assert body["next_action"]["type"] == "await_user_confirmation"
    assert any(item["work_id"] == "effect_intent" and item["kind"] == "effect" for item in body["work_items"])
    assert any(item["kind"] == "effect_intent" for item in body["artifacts"])


def test_v3_ask_team_route_invokes_child_team_executor_and_stores_team_run_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("OPENMIND_API_KEY", "secret-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    _patch_route(monkeypatch, route="funnel", rationale="needs multi-role review", executor_lane="team")

    from types import SimpleNamespace
    from chatgptrest.kernel.team_control_plane import TeamControlPlane
    from chatgptrest.kernel.cc_executor import CcResult

    plane = TeamControlPlane(db_path=":memory:")

    async def _fake_dispatch_team(task, team=None):
        return CcResult(
            ok=True,
            agent="native-team",
            task_type=task.task_type,
            output="team output",
            elapsed_seconds=1.2,
            quality_score=0.88,
            team_run_id="trun_objective",
            team_digest="team digest ready for approval",
            team_checkpoints=[{"checkpoint_id": "tcp_objective", "status": "pending", "summary": "approve funnel output"}],
            role_results={"scout": {"ok": True}},
        )

    fake_cc = SimpleNamespace(
        _team_control_plane=plane,
        dispatch_team=_fake_dispatch_team,
    )

    class _ImmediateThread:
        def __init__(self, *, target=None, kwargs=None, daemon=None, name=None):
            self._target = target
            self._kwargs = kwargs or {}

        def start(self):
            if self._target:
                self._target(**self._kwargs)

    monkeypatch.setattr("chatgptrest.advisor.runtime.get_advisor_runtime", lambda: {"cc_native": fake_cc})
    monkeypatch.setattr("chatgptrest.controller.engine.threading.Thread", _ImmediateThread)

    client = _make_client()
    headers = {"X-Api-Key": "secret-key"}
    response = client.post(
        "/v2/advisor/ask",
        json={
            "question": "帮我做一个三角色漏斗评审",
            "session_id": "session-team",
            "user_id": "user-team",
            "context": {"topology_id": "review_triad", "repo": "ChatgptREST"},
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["controller_status"] == "WAITING_HUMAN"
    assert body["provider"] == "team_control_plane"
    assert any(item["work_id"] == "team_execute" and item["kind"] == "team_execution" for item in body["work_items"])
    assert any(item["details"].get("team_gate") for item in body["checkpoints"])
    run = client.get(f"/v2/advisor/run/{body['run_id']}", headers=headers)
    assert run.status_code == 200
    snapshot = run.json()
    team_item = next(item for item in snapshot["work_items"] if item["work_id"] == "team_execute")
    assert team_item["output"]["output"]["team_run_id"] == "trun_objective"
    assert any(item["artifact_id"] == "team_run:trun_objective" for item in snapshot["artifacts"])
