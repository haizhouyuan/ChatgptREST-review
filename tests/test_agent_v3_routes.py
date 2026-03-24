from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import chatgptrest.api.routes_agent_v3 as routes_agent_v3


def _install_default_controller(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
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

    monkeypatch.setattr(routes_agent_v3, "ControllerEngine", _FakeController)
    return captured


def _make_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    openmind_api_key: str | None = "test-openmind-key",
    bearer_token: str | None = None,
    auth_mode: str = "strict",
) -> TestClient:
    if openmind_api_key is None:
        monkeypatch.delenv("OPENMIND_API_KEY", raising=False)
    else:
        monkeypatch.setenv("OPENMIND_API_KEY", openmind_api_key)
    if bearer_token is None:
        monkeypatch.delenv("CHATGPTREST_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("CHATGPTREST_API_TOKEN", bearer_token)
    monkeypatch.setenv("OPENMIND_AUTH_MODE", auth_mode)
    app = FastAPI()
    app.include_router(routes_agent_v3.make_v3_agent_router())
    return TestClient(app, raise_server_exceptions=False)


def test_agent_turn_returns_503_when_no_auth_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client(monkeypatch, openmind_api_key=None, bearer_token=None)
    r = client.post("/v3/agent/turn", json={"message": "hello"})
    assert r.status_code == 503
    assert "not configured" in r.text


def test_agent_turn_returns_401_for_invalid_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client(monkeypatch, openmind_api_key="expected-key", bearer_token="expected-token")

    r1 = client.post("/v3/agent/turn", json={"message": "hello"})
    assert r1.status_code == 401

    r2 = client.post("/v3/agent/turn", headers={"X-Api-Key": "wrong"}, json={"message": "hello"})
    assert r2.status_code == 401

    r3 = client.post("/v3/agent/turn", headers={"Authorization": "Bearer wrong"}, json={"message": "hello"})
    assert r3.status_code == 401


def test_agent_turn_accepts_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_default_controller(monkeypatch)
    client = _make_client(monkeypatch, openmind_api_key=None, bearer_token="token-1")
    r = client.post(
        "/v3/agent/turn",
        headers={"Authorization": "Bearer token-1"},
        json={"message": "review this repo for regression risk"},
    )
    assert r.status_code == 200
    assert r.json()["answer"] == "answer 1"


def test_agent_turn_blocks_synthetic_probe_after_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _make_client(monkeypatch)
    r = client.post(
        "/v3/agent/turn",
        headers={"X-Api-Key": "test-openmind-key"},
        json={"message": "test needs_followup state"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "agent_synthetic_prompt_blocked"


def test_agent_turn_controller_waits_for_final_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes_agent_v3, "_advisor_runtime", lambda: {})

    class _FakeController:
        def __init__(self, _state):
            pass

        def ask(self, **kwargs):
            return {
                "run_id": "run-123",
                "job_id": "job-123",
                "route": "quick_ask",
                "provider": "chatgpt",
                "controller_status": "WAITING_EXTERNAL",
                "answer": "",
            }

        def get_run_snapshot(self, *, run_id: str):
            return {
                "run": {
                    "run_id": run_id,
                    "route": "quick_ask",
                    "provider": "chatgpt",
                    "controller_status": "DELIVERED",
                    "final_job_id": "job-123",
                    "delivery": {
                        "status": "completed",
                        "answer": "final answer",
                        "conversation_url": "https://chatgpt.com/c/run-123",
                    },
                    "next_action": {"type": "followup"},
                },
                "artifacts": [{"kind": "conversation_url", "uri": "https://chatgpt.com/c/run-123"}],
            }

    monkeypatch.setattr(routes_agent_v3, "ControllerEngine", _FakeController)

    client = _make_client(monkeypatch)
    r = client.post(
        "/v3/agent/turn",
        headers={"X-Api-Key": "test-openmind-key"},
        json={"message": "review this repo", "goal_hint": "code_review", "timeout_seconds": 30},
    )
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "completed"
    assert body["answer"] == "final answer"
    assert body["provenance"]["job_id"] == "job-123"

    status_r = client.get(
        f"/v3/agent/session/{body['session_id']}",
        headers={"X-Api-Key": "test-openmind-key"},
    )
    status_body = status_r.json()
    assert status_r.status_code == 200
    assert status_body["status"] == "completed"
    assert status_body["last_answer"] == "final answer"
    assert status_body["job_id"] == "job-123"


def test_agent_turn_same_session_followup_preserves_continuity(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _install_default_controller(monkeypatch)
    client = _make_client(monkeypatch)

    first = client.post(
        "/v3/agent/turn",
        headers={"X-Api-Key": "test-openmind-key"},
        json={"message": "review this repo", "goal_hint": "code_review"},
    )
    assert first.status_code == 200
    first_body = first.json()
    session_id = first_body["session_id"]

    second = client.post(
        "/v3/agent/turn",
        headers={"X-Api-Key": "test-openmind-key"},
        json={"message": "continue with follow-up details", "session_id": session_id},
    )
    assert second.status_code == 200
    second_body = second.json()

    assert second_body["session_id"] == session_id
    assert [call["session_id"] for call in captured] == [session_id, session_id]
    assert [call["question"] for call in captured] == ["review this repo", "continue with follow-up details"]

    status_r = client.get(f"/v3/agent/session/{session_id}", headers={"X-Api-Key": "test-openmind-key"})
    assert status_r.status_code == 200
    status_body = status_r.json()
    assert status_body["status"] == "completed"
    assert status_body["last_answer"] == "answer 2"


def test_agent_turn_same_session_resume_after_clarify(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _install_default_controller(monkeypatch)
    client = _make_client(monkeypatch)

    first = client.post(
        "/v3/agent/turn",
        headers={"X-Api-Key": "test-openmind-key"},
        json={
            "message": "Help",
            "contract": {
                "risk_class": "high",
                "task_template": "decision_support",
                "output_shape": "text_answer",
            },
        },
    )
    assert first.status_code == 200
    first_body = first.json()
    session_id = first_body["session_id"]
    assert first_body["status"] == "needs_followup"
    assert first_body["next_action"]["type"] == "await_user_clarification"
    assert first_body["next_action"]["questions"]

    status_r = client.get(
        f"/v3/agent/session/{session_id}",
        headers={"X-Api-Key": "test-openmind-key"},
    )
    assert status_r.status_code == 200
    assert status_r.json()["status"] == "needs_followup"

    second = client.post(
        "/v3/agent/turn",
        headers={"X-Api-Key": "test-openmind-key"},
        json={
            "session_id": session_id,
            "message": "Assess whether we should ship the premium ingress strategist this week.",
            "contract": {
                "risk_class": "high",
                "task_template": "decision_support",
                "decision_to_support": "Whether to ship this week",
                "audience": "Platform lead",
                "output_shape": "decision memo",
            },
        },
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["session_id"] == session_id
    assert second_body["status"] == "completed"
    assert second_body["answer"] == "answer 1"

    assert len(captured) == 1
    assert captured[0]["session_id"] == session_id


def test_agent_turn_same_session_contract_patch_continues_after_clarify(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _install_default_controller(monkeypatch)
    client = _make_client(monkeypatch)

    first = client.post(
        "/v3/agent/turn",
        headers={"X-Api-Key": "test-openmind-key"},
        json={
            "message": "Help",
            "contract": {
                "risk_class": "high",
                "task_template": "decision_support",
                "output_shape": "text_answer",
            },
        },
    )
    assert first.status_code == 200
    first_body = first.json()
    session_id = first_body["session_id"]
    assert first_body["status"] == "needs_followup"
    assert first_body["task_intake"]["spec_version"] == "task-intake-v2"
    assert first_body["clarify_diagnostics"]["missing_fields"] == ["decision_to_support", "audience"]
    assert first_body["next_action"]["clarify_diagnostics"]["recommended_contract_patch"]["decision_to_support"]

    second = client.post(
        "/v3/agent/turn",
        headers={"X-Api-Key": "test-openmind-key"},
        json={
            "session_id": session_id,
            "message": "Assess whether we should ship the premium ingress strategist this week.",
            "contract_patch": {
                "decision_to_support": "Whether to ship this week",
                "audience": "Platform lead",
            },
        },
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["session_id"] == session_id
    assert second_body["status"] == "completed"
    assert second_body["control_plane"]["contract_source"] in {"client", "server_synthesized"}
    assert second_body["task_intake"]["decision_to_support"] == "Whether to ship this week"
    assert second_body["task_intake"]["audience"] == "Platform lead"
    assert second_body["task_intake"]["objective"] == "Assess whether we should ship the premium ingress strategist this week."

    status_r = client.get(
        f"/v3/agent/session/{session_id}",
        headers={"X-Api-Key": "test-openmind-key"},
    )
    assert status_r.status_code == 200
    status_body = status_r.json()
    assert status_body["status"] == "completed"
    assert status_body["task_intake"]["decision_to_support"] == "Whether to ship this week"
    assert status_body["control_plane"]["effective_execution_profile"] == "default"

    assert len(captured) == 1
    assert captured[0]["session_id"] == session_id
    assert captured[0]["stable_context"]["task_intake"]["decision_to_support"] == "Whether to ship this week"
    assert captured[0]["stable_context"]["task_intake"]["audience"] == "Platform lead"


def test_agent_session_survives_router_recreation_when_store_dir_is_persisted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _install_default_controller(monkeypatch)
    monkeypatch.setenv("CHATGPTREST_AGENT_SESSION_DIR", str(tmp_path / "agent-sessions"))

    client_a = _make_client(monkeypatch)
    first = client_a.post(
        "/v3/agent/turn",
        headers={"X-Api-Key": "test-openmind-key"},
        json={"message": "persist this session", "goal_hint": "code_review"},
    )
    assert first.status_code == 200
    session_id = first.json()["session_id"]
    client_a.close()

    client_b = _make_client(monkeypatch)
    status_r = client_b.get(
        f"/v3/agent/session/{session_id}",
        headers={"X-Api-Key": "test-openmind-key"},
    )
    assert status_r.status_code == 200
    assert status_r.json()["session_id"] == session_id
    assert status_r.json()["status"] == "completed"
    client_b.close()


def test_agent_turn_image_goal_uses_direct_job_substrate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes_agent_v3, "_advisor_runtime", lambda: {})
    captured: dict[str, object] = {}

    def _fake_submit_direct_job(**kwargs):
        captured.update(kwargs)
        return "job-img-1"

    def _fake_wait_for_job_completion(**kwargs):
        return {
            "job_id": "job-img-1",
            "job_status": "completed",
            "agent_status": "completed",
            "answer": "# Generated images\n\n![image 1](images/cat.png)",
            "conversation_url": "https://gemini.google.com/app/abc",
        }

    class _ShouldNotBeUsed:
        def __init__(self, _state):
            raise AssertionError("ControllerEngine should not be used for image goal")

    monkeypatch.setattr(routes_agent_v3, "_submit_direct_job", _fake_submit_direct_job)
    monkeypatch.setattr(routes_agent_v3, "_wait_for_job_completion", _fake_wait_for_job_completion)
    monkeypatch.setattr(routes_agent_v3, "ControllerEngine", _ShouldNotBeUsed)

    client = _make_client(monkeypatch)
    r = client.post(
        "/v3/agent/turn",
        headers={"X-Api-Key": "test-openmind-key"},
        json={
            "message": "draw a cat",
            "goal_hint": "image",
            "attachments": ["/tmp/ref.png"],
            "timeout_seconds": 30,
        },
    )
    body = r.json()
    assert r.status_code == 200
    assert captured["kind"] == "gemini_web.generate_image"
    assert captured["input_obj"]["file_paths"] == ["/tmp/ref.png"]
    assert "draw a cat" in captured["input_obj"]["prompt"]
    assert body["status"] == "completed"
    assert body["provenance"]["job_id"] == "job-img-1"


def test_agent_turn_consult_goal_and_cancel_track_underlying_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes_agent_v3, "_advisor_runtime", lambda: {})
    cancelled: list[str] = []

    def _fake_submit_consultation(**kwargs):
        return {
            "consultation_id": "cons-1",
            "jobs": [
                {"job_id": "job-a", "provider": "chatgpt_web", "model": "chatgpt_pro"},
                {"job_id": "job-b", "provider": "gemini_web", "model": "gemini_deepthink"},
            ],
        }

    def _fake_wait_for_consultation_completion(**kwargs):
        return {
            "consultation_id": "cons-1",
            "status": "completed",
            "agent_status": "completed",
            "jobs": [
                {"job_id": "job-a", "provider": "chatgpt_web", "model": "chatgpt_pro"},
                {"job_id": "job-b", "provider": "gemini_web", "model": "gemini_deepthink"},
            ],
            "answer": "## chatgpt_pro\n\nAnswer A\n\n---\n\n## gemini_deepthink\n\nAnswer B",
        }

    def _fake_cancel_job(*, cfg, job_id: str, reason: str = "agent_session_cancelled"):
        cancelled.append(job_id)

    monkeypatch.setattr(routes_agent_v3, "_submit_consultation", _fake_submit_consultation)
    monkeypatch.setattr(routes_agent_v3, "_wait_for_consultation_completion", _fake_wait_for_consultation_completion)
    monkeypatch.setattr(routes_agent_v3, "_cancel_job", _fake_cancel_job)

    client = _make_client(monkeypatch)
    turn_r = client.post(
        "/v3/agent/turn",
        headers={"X-Api-Key": "test-openmind-key"},
        json={"message": "double review this plan", "goal_hint": "dual_review", "timeout_seconds": 30},
    )
    turn_body = turn_r.json()
    assert turn_r.status_code == 200
    assert turn_body["status"] == "completed"
    assert turn_body["provenance"]["consultation_id"] == "cons-1"

    cancel_r = client.post(
        "/v3/agent/cancel",
        headers={"X-Api-Key": "test-openmind-key"},
        json={"session_id": turn_body["session_id"]},
    )
    cancel_body = cancel_r.json()
    assert cancel_r.status_code == 200
    assert cancel_body["status"] == "cancelled"
    assert set(cancelled) == {"job-a", "job-b"}
    assert set(cancel_body["cancelled_job_ids"]) == {"job-a", "job-b"}
