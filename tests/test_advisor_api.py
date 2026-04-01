from __future__ import annotations

import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def test_advisor_advise_plan_mode_is_stateless(
    env: dict[str, Path],  # noqa: ARG001
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_root = tmp_path / "advisor_state"
    monkeypatch.setenv("CHATGPTREST_ADVISOR_STATE_ROOT", str(state_root))

    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "这个问题尽快处理",
            "context": {"project": "openclaw"},
            "force": False,
            "execute": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"planned", "needs_context"}
    assert body["route"]
    assert isinstance(body.get("route_decision"), dict)
    assert body["route_decision"]["route"] == body["route"]
    assert body["refined_question"]
    assert isinstance(body["answer_contract"], dict)
    if body["status"] == "planned":
        assert body.get("action_hint") == "execute_ready"
    else:
        assert body.get("action_hint") == "provide_followup_context"
    # plan-only should not instantiate v0 / create state directories.
    assert not state_root.exists()


def test_advisor_advise_execute_enforces_allowlist(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "allowed-client")

    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/advise",
        json={"raw_question": "执行", "execute": True},
        headers={"X-Client-Name": "not-allowed"},
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "client_not_allowed"


def test_advisor_advise_execute_trace_gate_missing_headers_returns_400(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "")

    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/advise",
        json={"raw_question": "执行", "execute": True},
        headers={"X-Client-Name": "openclaw-advisor"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "missing_trace_headers"


def test_advisor_advise_execute_trace_gate_with_headers_returns_200(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chatgptrest.api.routes_advisor as mod

    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "")
    monkeypatch.setattr(
        mod,
        "_load_wrapper_module",
        lambda: types.SimpleNamespace(
            prompt_refine=lambda raw_question, context: f"refined: {raw_question}",
            question_gap_check=lambda raw_question, context: [],
            channel_strategy=lambda raw_question: "chatgpt_pro",
        ),
    )

    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "执行",
            "execute": True,
            "agent_options": {"max_turns": 4},
        },
        headers={
            "X-Client-Name": "openclaw-advisor",
            "X-Client-Instance": "oc-1",
            "X-Request-ID": "rid-abc-1",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"job_created", "cooldown"}
    assert isinstance(body.get("job_id"), str) and body["job_id"]
    assert body.get("phase") in {"send", "wait"}
    assert body.get("route") == "chatgpt_pro"
    assert isinstance(body.get("route_decision"), dict)
    assert body["route_decision"]["route"] == "chatgpt_pro"
    assert body.get("action_hint") in {"wait_for_job_completion", "retry_after_cooldown"}


def test_advisor_advise_execute_crosscheck_route_marks_degraded_status(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import chatgptrest.api.routes_advisor as mod

    monkeypatch.setattr(
        mod,
        "_load_wrapper_module",
        lambda: types.SimpleNamespace(
            prompt_refine=lambda raw_question, context: f"refined: {raw_question}",
            question_gap_check=lambda raw_question, context: [],
            channel_strategy_trace=lambda raw_question: {
                "route": "pro_gemini_crosscheck",
                "reason": "matched_crosscheck_keywords",
                "flags": {"has_crosscheck": True},
                "matched_keywords": {"crosscheck": ["交叉验证"]},
                "normalized_question": str(raw_question),
            },
            channel_strategy=lambda raw_question: "pro_gemini_crosscheck",
        ),
    )

    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "请做多模型交叉验证并给出双重验证结论",
            "execute": True,
        },
        headers={
            "X-Client-Name": "chatgptrest-mcp",
            "X-Client-Instance": "test-crosscheck",
            "X-Request-ID": "rid-crosscheck-1",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("route") == "pro_gemini_crosscheck"
    assert body.get("fallback_action") == "crosscheck_degraded_to_single_job"
    assert body.get("degraded") is True
    if body.get("status") != "cooldown":
        assert body.get("ok") is True
        assert body.get("status") == "degraded_job_created"
        assert body.get("action_hint") == "wait_for_job_completion"
    else:
        assert body.get("ok") is False
        assert body.get("action_hint") == "retry_after_cooldown"


@pytest.mark.parametrize("forbidden_key", ["base_url", "api_token", "state_root"])
def test_advisor_advise_rejects_forbidden_agent_options(
    env: dict[str, Path],  # noqa: ARG001
    forbidden_key: str,
) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "计划",
            "execute": False,
            "agent_options": {forbidden_key: "x"},
        },
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "forbidden_agent_options"
    assert forbidden_key in detail["forbidden_keys"]


def test_advisor_advise_rejects_unknown_agent_options(env: dict[str, Path]) -> None:  # noqa: ARG001
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/advisor/advise",
        json={
            "raw_question": "计划",
            "execute": False,
            "agent_options": {"unknown_option": 1},
        },
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "unknown_agent_options"
