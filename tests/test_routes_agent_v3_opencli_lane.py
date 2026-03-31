"""Integration tests for the explicit opencli narrow lane."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import chatgptrest.api.routes_agent_v3 as routes_agent_v3
from chatgptrest.advisor.ask_strategist import AskStrategyPlan
from chatgptrest.executors.opencli_contracts import OpenCLIExecutionResult


def _make_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("OPENMIND_API_KEY", "test-openmind-key")
    monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")
    app = FastAPI()
    app.include_router(routes_agent_v3.make_v3_agent_router())
    return TestClient(app, raise_server_exceptions=False)


def _install_fake_runtime(monkeypatch) -> list[dict[str, object]]:
    monkeypatch.setattr(routes_agent_v3, "_advisor_runtime", lambda: {})
    captured: list[dict[str, object]] = []

    class _FakeController:
        def __init__(self, _state):
            pass

        def ask(self, **kwargs):
            captured.append({"controller": kwargs})
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
            "answer": "generated content",
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


def _headers() -> dict[str, str]:
    return {"X-Api-Key": "test-openmind-key"}


def _force_strategy(monkeypatch: pytest.MonkeyPatch, *, route_hint: str) -> None:
    def _fake_build_strategy_plan(**kwargs):
        contract = kwargs.get("contract")
        return AskStrategyPlan(
            contract_id=str(getattr(contract, "contract_id", "") or ""),
            task_template=str(getattr(contract, "task_template", "general") or "general"),
            route_hint=route_hint,
            provider_family="gemini" if route_hint in {"image", "research", "deep_research", "analysis_heavy"} else "chatgpt",
            model_family="standard",
            execution_mode="execute",
            clarify_required=False,
        )

    monkeypatch.setattr(routes_agent_v3, "build_strategy_plan", _fake_build_strategy_plan)


def _write_opencli_artifacts(tmp_path: Path, *, ok: bool) -> list[str]:
    run_dir = tmp_path / ("opencli-ok" if ok else "opencli-fail")
    run_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "request.json": "{}",
        "stdout.txt": '{"status":"ok"}' if ok else "",
        "stderr.txt": "" if ok else "command failed",
        "diagnostics.json": '{"attempt": 1}',
        "result.json": '{"ok": true}' if ok else '{"ok": false}',
        "answer.md": "opencli success answer" if ok else "opencli failure answer",
    }
    if not ok:
        files["doctor.txt"] = "doctor output"
    paths: list[str] = []
    for name, content in files.items():
        artifact = run_dir / name
        artifact.write_text(content, encoding="utf-8")
        paths.append(str(artifact))
    return paths


def _patch_opencli_execute(monkeypatch, tmp_path: Path, *, ok: bool, capture: list[dict[str, object]]):
    def _fake_execute(self, request):  # noqa: ANN001
        capture.append({"opencli_request": request.to_dict()})
        return OpenCLIExecutionResult(
            ok=ok,
            executor_kind="opencli",
            command_id=request.command_id,
            exit_code=0 if ok else 1,
            retryable=False,
            error_type="" if ok else "execution_error",
            error_message="" if ok else "command failed",
            structured_result={"status": "ok"} if ok else {},
            artifacts=_write_opencli_artifacts(tmp_path, ok=ok),
            diagnostics={"attempt": 1},
            timing={"elapsed_seconds": 0.2},
        )

    monkeypatch.setattr("chatgptrest.executors.opencli_executor.OpenCLIExecutor.execute", _fake_execute)


def test_opencli_lane_not_triggered_without_execution_request(monkeypatch):
    headers = _headers()
    captured = _install_fake_runtime(monkeypatch)
    _force_strategy(monkeypatch, route_hint="quick_ask")
    client = _make_client(monkeypatch)

    response = client.post("/v3/agent/turn", json={"message": "plain request"}, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["provenance"]["route"] == "quick_ask"
    assert payload["provenance"]["final_provider"] == "chatgpt"
    assert any("controller" in item for item in captured)


def test_opencli_lane_not_triggered_with_wrong_executor_kind(monkeypatch):
    headers = _headers()
    captured = _install_fake_runtime(monkeypatch)
    _force_strategy(monkeypatch, route_hint="quick_ask")
    client = _make_client(monkeypatch)

    response = client.post(
        "/v3/agent/turn",
        json={
            "message": "not opencli",
            "task_intake": {"context": {"execution_request": {"executor_kind": "shell", "command_id": "noop"}}},
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provenance"]["route"] == "quick_ask"
    assert any("controller" in item for item in captured)
    assert not any("opencli_request" in item for item in captured)


def test_opencli_lane_triggered_with_valid_request(monkeypatch, tmp_path):
    headers = _headers()
    captured = _install_fake_runtime(monkeypatch)
    _force_strategy(monkeypatch, route_hint="quick_ask")
    _patch_opencli_execute(monkeypatch, tmp_path, ok=True, capture=captured)
    client = _make_client(monkeypatch)

    response = client.post(
        "/v3/agent/turn",
        json={
            "message": "run opencli",
            "task_intake": {
                "context": {
                    "execution_request": {
                        "executor_kind": "opencli",
                        "capability_id": "public_web_read",
                        "command_id": "hackernews.top",
                        "args": {"limit": 5},
                    }
                }
            },
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provenance"]["route"] == "opencli"
    assert payload["status"] == "completed"
    assert payload["answer"] == "opencli success answer"
    assert payload["provenance"]["final_provider"] == "opencli"
    assert payload["provenance"]["provider_path"] == ["opencli"]
    assert "provider_selection" not in payload["provenance"]
    artifact_kinds = {item["kind"] for item in payload["artifacts"]}
    assert "opencli_answer" in artifact_kinds
    assert "opencli_diagnostics" in artifact_kinds
    assert any("opencli_request" in item for item in captured)
    assert not any("controller" in item for item in captured)


def test_opencli_lane_no_fallback_to_provider_web_on_failure(monkeypatch, tmp_path):
    headers = _headers()
    captured = _install_fake_runtime(monkeypatch)
    _force_strategy(monkeypatch, route_hint="quick_ask")
    _patch_opencli_execute(monkeypatch, tmp_path, ok=False, capture=captured)
    client = _make_client(monkeypatch)

    response = client.post(
        "/v3/agent/turn",
        json={
            "message": "run opencli and fail",
            "task_intake": {
                "context": {
                    "execution_request": {
                        "executor_kind": "opencli",
                        "capability_id": "public_web_read",
                        "command_id": "hackernews.top",
                        "args": {"limit": 5},
                    },
                }
            },
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provenance"]["route"] == "opencli"
    assert payload["status"] == "failed"
    assert payload["answer"] == "opencli failure answer"
    assert "provider_selection" not in payload["provenance"]
    assert not any("controller" in item for item in captured)
    assert not any("direct_job" in item for item in captured)
    assert not any("consult" in item for item in captured)


def test_image_branch_unchanged(monkeypatch):
    headers = _headers()
    captured = _install_fake_runtime(monkeypatch)
    _force_strategy(monkeypatch, route_hint="image")
    client = _make_client(monkeypatch)

    response = client.post("/v3/agent/turn", json={"message": "draw a cat", "goal_hint": "image"}, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["provenance"]["route"] == "image"
    assert payload["provenance"]["final_provider"] == "gemini_web"
    assert any("direct_job" in item for item in captured)


def test_consult_branch_unchanged(monkeypatch):
    headers = _headers()
    captured = _install_fake_runtime(monkeypatch)
    _force_strategy(monkeypatch, route_hint="consult")
    client = _make_client(monkeypatch)

    response = client.post("/v3/agent/turn", json={"message": "compare options", "goal_hint": "consult"}, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["provenance"]["route"] == "consult"
    assert payload["provenance"]["final_provider"] == "consult"
    assert any("consult" in item for item in captured)


def test_direct_gemini_branch_unchanged(monkeypatch):
    headers = _headers()
    captured = _install_fake_runtime(monkeypatch)
    _force_strategy(monkeypatch, route_hint="research")
    monkeypatch.setattr(routes_agent_v3, "_should_use_direct_gemini_lane", lambda **kwargs: True)
    client = _make_client(monkeypatch)

    response = client.post(
        "/v3/agent/turn",
        json={"message": "deep think", "task_intake": {"context": {"requested_provider": "gemini"}}},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provenance"]["route"] in {"research", "deep_research", "analysis_heavy"}
    assert payload["provenance"]["final_provider"] == "gemini_web"
    assert any("direct_job" in item for item in captured)


def test_provider_registry_unchanged():
    from chatgptrest.providers.registry import provider_specs, web_ask_kinds

    specs = provider_specs()
    assert len(specs) == 2
    assert specs[0].provider_id == "chatgpt"
    assert specs[1].provider_id == "gemini"
    assert web_ask_kinds() == {"chatgpt_web.ask", "gemini_web.ask"}
