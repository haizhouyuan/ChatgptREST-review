from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app
from chatgptrest.core.client_request_auth import build_registered_client_hmac_headers


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _signed_headers(
    *,
    client_lookup: str,
    client_instance: str,
    body_payload: dict[str, object],
    environ: dict[str, str],
) -> dict[str, str]:
    headers = {
        "Authorization": "Bearer test-token",
        "User-Agent": "curl/8.7.1",
        "X-Client-Name": client_lookup,
        "X-Client-Instance": client_instance,
        "X-Request-ID": f"rid-{client_instance}",
    }
    headers.update(
        build_registered_client_hmac_headers(
            client_lookup=client_lookup,
            client_instance=client_instance,
            method="POST",
            path="/v1/jobs",
            body_payload=body_payload,
            environ=environ,
        )
    )
    return headers


def test_create_job_enforces_allowlist_and_trace_headers(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "allowed-client")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    app = create_app()
    client = TestClient(app)

    r1 = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "x"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "wg-create-1"},
    )
    assert r1.status_code == 403
    assert r1.json()["detail"]["error"] == "client_not_allowed"

    r2 = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "x"}, "params": {"repeat": 1}},
        headers={"Idempotency-Key": "wg-create-2", "X-Client-Name": "allowed-client"},
    )
    assert r2.status_code == 400
    assert r2.json()["detail"]["error"] == "missing_trace_headers"

    r3 = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "x"}, "params": {"repeat": 1}},
        headers={
            "Idempotency-Key": "wg-create-3",
            "X-Client-Name": "allowed-client",
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-1",
        },
    )
    assert r3.status_code == 200
    assert isinstance(r3.json().get("job_id"), str)


def test_registered_web_ask_client_bypasses_global_allowlist_and_hits_ask_guard(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT", "maint-secret")
    app = create_app()
    client = TestClient(app)

    denied = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "请给出三条不重复的工程建议。"},
            "params": {"preset": "auto"},
        },
        headers={
            "Authorization": "Bearer test-token",
            "Idempotency-Key": "wg-registered-bypass-1",
            "X-Client-Name": "chatgptrestctl-maint",
            "X-Client-Instance": "ci-registered-1",
            "X-Request-ID": "rid-registered-1",
        },
    )

    assert denied.status_code == 403
    detail = denied.json()["detail"]
    assert detail["error"] == "low_level_ask_client_auth_failed"
    assert detail["reason"] == "missing_hmac_headers"


def test_planning_wrapper_registered_web_ask_can_pass_allowlist_to_guard(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "1")
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER", "planning-secret")

    from chatgptrest.core import ask_guard
    from chatgptrest.core.codex_runner import CodexExecResult

    def fake_codex_exec_with_schema(**kwargs):  # noqa: ANN003
        return CodexExecResult(
            ok=True,
            returncode=0,
            elapsed_ms=1,
            cmd=["codex", "exec"],
            output={
                "decision": "allow",
                "reason_code": "substantive_registered_automation",
                "intent_class": "substantive_human_like_task",
                "substantive": True,
                "allow_live_chatgpt": True,
                "allow_deep_research": False,
                "allow_pro": True,
                "short_answer_ok": False,
                "notes": ["mock_codex_allow"],
            },
        )

    monkeypatch.setattr(ask_guard, "codex_exec_with_schema", fake_codex_exec_with_schema)

    app = create_app()
    client = TestClient(app)

    body = {
        "kind": "chatgpt_web.ask",
        "input": {
            "question": (
                "Review this architecture proposal and return only JSON object with top_3_risks, "
                "including risk, impact, mitigation, and missing_test."
            )
        },
        "params": {"preset": "auto"},
    }
    allowed = client.post(
        "/v1/jobs",
        json=body,
        headers={
            **_signed_headers(
                client_lookup="planning-chatgptrest-call",
                client_instance="planner-registered-1",
                body_payload=body,
                environ={"CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER": "planning-secret"},
            ),
            "Idempotency-Key": "wg-registered-bypass-2",
            "X-Source-Repo": "haizhouyuan/planning",
            "X-Source-Entrypoint": "scripts/planning_chatgptrest_call.py",
            "X-Client-Run-Id": "run-registered-2",
        },
    )

    assert allowed.status_code == 200
    assert isinstance(allowed.json().get("job_id"), str)


def test_planning_wrapper_registered_gemini_web_ask_allows_public_repo_hint_without_import_code(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "1")
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER", "planning-secret")

    from chatgptrest.core import ask_guard
    from chatgptrest.core.codex_runner import CodexExecResult

    def fake_codex_exec_with_schema(**kwargs):  # noqa: ANN003
        return CodexExecResult(
            ok=True,
            returncode=0,
            elapsed_ms=1,
            cmd=["codex", "exec"],
            output={
                "decision": "allow",
                "reason_code": "substantive_registered_automation",
                "intent_class": "substantive_human_like_task",
                "substantive": True,
                "allow_live_chatgpt": False,
                "allow_deep_research": True,
                "allow_pro": True,
                "short_answer_ok": False,
                "notes": ["mock_codex_allow"],
            },
        )

    monkeypatch.setattr(ask_guard, "codex_exec_with_schema", fake_codex_exec_with_schema)

    app = create_app()
    client = TestClient(app)

    body = {
        "kind": "gemini_web.ask",
        "input": {
            "question": "Read the attached review packet and produce a traceable architecture memo.",
            "github_repo": "https://github.com/haizhouyuan/ChatgptREST-review",
        },
        "params": {"preset": "pro"},
    }
    allowed = client.post(
        "/v1/jobs",
        json=body,
        headers={
            **_signed_headers(
                client_lookup="planning-chatgptrest-call",
                client_instance="planner-gemini-repo-1",
                body_payload=body,
                environ={"CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER": "planning-secret"},
            ),
            "Idempotency-Key": "wg-gemini-repo-hint-1",
            "X-Source-Repo": "haizhouyuan/planning",
            "X-Source-Entrypoint": "scripts/planning_chatgptrest_call.py",
            "X-Client-Run-Id": "run-gemini-repo-1",
        },
    )

    assert allowed.status_code == 200
    assert isinstance(allowed.json().get("job_id"), str)


def test_cancel_job_enforces_cancel_allowlist_and_reason(
    env: dict[str, Path],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "allowed-client,cancel-client")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CANCEL_CLIENT_NAME_ALLOWLIST", "cancel-client")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "1")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_CANCEL_REASON", "1")

    app = create_app()
    client = TestClient(app)

    create = client.post(
        "/v1/jobs",
        json={"kind": "dummy.echo", "input": {"text": "x"}, "params": {"repeat": 1}},
        headers={
            "Idempotency-Key": "wg-cancel-1",
            "X-Client-Name": "allowed-client",
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-1",
        },
    )
    assert create.status_code == 200
    job_id = create.json()["job_id"]

    denied = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={
            "X-Client-Name": "allowed-client",
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-2",
            "X-Cancel-Reason": "stop",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "cancel_client_not_allowed"

    missing_reason = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={
            "X-Client-Name": "cancel-client",
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-3",
        },
    )
    assert missing_reason.status_code == 400
    assert missing_reason.json()["detail"]["error"] == "missing_cancel_reason"

    ok = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={
            "X-Client-Name": "cancel-client",
            "X-Client-Instance": "ci-1",
            "X-Request-ID": "rid-4",
            "X-Cancel-Reason": "manual-stop",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "canceled"
