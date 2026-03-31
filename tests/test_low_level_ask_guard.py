from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import chatgptrest.core.ask_guard as ask_guard
from chatgptrest.api.app import create_app
from chatgptrest.core.client_request_auth import build_registered_client_hmac_headers
from chatgptrest.core.codex_runner import CodexExecResult


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobdb.sqlite3"
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "")
    monkeypatch.setenv("CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE", "0")
    monkeypatch.delenv("CHATGPTREST_ASK_CLIENT_REGISTRY_PATH", raising=False)
    monkeypatch.delenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", raising=False)
    ask_guard._NONCE_CACHE.clear()
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _row_payloads(db_path: Path, job_id: str) -> tuple[dict[str, object], dict[str, object]]:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT client_json, params_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    finally:
        conn.close()
    assert row is not None
    return json.loads(str(row[0] or "{}")), json.loads(str(row[1] or "{}"))


def _signed_headers(
    *,
    client_lookup: str,
    client_instance: str,
    method: str,
    path: str,
    body_payload: dict[str, object],
    environ: dict[str, str] | None = None,
    extra_headers: dict[str, str] | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    headers = {
        "User-Agent": "curl/8.7.1",
        "X-Client-Name": client_lookup,
        "X-Client-Instance": client_instance,
    }
    headers.update(
        build_registered_client_hmac_headers(
            client_lookup=client_lookup,
            client_instance=client_instance,
            method=method,
            path=path,
            body_payload=body_payload,
            environ=environ,
            now_ts=int(time.time()),
            nonce=str(nonce or f"{client_lookup}-nonce"),
        )
    )
    if extra_headers:
        headers.update(extra_headers)
    return headers


def test_low_level_ask_requires_registered_identity_for_non_testclient(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    res = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "请指出这段设计的三个主要风险。"},
            "params": {"preset": "auto"},
        },
        headers={"Idempotency-Key": "identity-required", "User-Agent": "curl/8.7.1"},
    )

    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "low_level_ask_client_identity_required"


def test_testclient_user_agent_spoof_is_not_identity_exempt() -> None:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/v1/jobs",
        "raw_path": b"/v1/jobs",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"user-agent", b"testclient")],
        "client": ("127.0.0.1", 54321),
        "server": ("127.0.0.1", 18711),
    }
    request = Request(scope)

    with pytest.raises(HTTPException) as excinfo:
        ask_guard.enforce_low_level_ask_identity_and_policy(
            request=request,
            body_payload={"kind": "gemini_web.ask", "input": {"question": "hi"}, "params": {"preset": "pro"}},
            kind="gemini_web.ask",
            input_obj={"question": "请指出三条风险。"},
            params_obj={"preset": "pro"},
            client_obj=None,
        )

    detail = excinfo.value.detail
    assert detail["error"] == "low_level_ask_client_identity_required"


def test_low_level_ask_rejects_unregistered_identity(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)

    res = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "请指出这段设计的三个主要风险。"},
            "params": {"preset": "auto"},
        },
        headers={
            "Idempotency-Key": "identity-unregistered",
            "User-Agent": "curl/8.7.1",
            "X-Client-Name": "unknown-pipeline",
        },
    )

    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "low_level_ask_client_not_registered"


def test_registered_automation_codex_guard_block_is_fail_closed(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "1")
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER", "planning-secret")

    def fake_codex_exec_with_schema(**kwargs):  # noqa: ANN003
        return CodexExecResult(
            ok=True,
            returncode=0,
            elapsed_ms=1,
            cmd=["codex", "exec"],
            output={
                "decision": "block",
                "reason_code": "unclear_intent_blocked",
                "intent_class": "unknown",
                "substantive": False,
                "allow_live_chatgpt": False,
                "allow_deep_research": False,
                "allow_pro": False,
                "short_answer_ok": False,
                "remediation": "Use a higher-level agent turn for this ambiguous automation request.",
                "notes": ["mock_codex_block"],
            },
        )

    monkeypatch.setattr(ask_guard, "codex_exec_with_schema", fake_codex_exec_with_schema)
    app = create_app()
    client = TestClient(app)

    res = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "Please review this proposal and summarize the important concerns."},
            "params": {"preset": "auto"},
        },
        headers={
            **_signed_headers(
                client_lookup="planning-chatgptrest-call",
                client_instance="planner-1",
                method="POST",
                path="/v1/jobs",
                body_payload={
                    "kind": "chatgpt_web.ask",
                    "input": {"question": "Please review this proposal and summarize the important concerns."},
                    "params": {"preset": "auto"},
                },
                environ={"CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER": "planning-secret"},
            ),
            "Idempotency-Key": "codex-guard-block",
        },
    )

    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "low_level_ask_intent_blocked"
    assert detail["reason"] == "unclear_intent_blocked"


def test_registered_automation_json_only_review_can_reach_codex_classify(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "1")
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER", "planning-secret")
    calls: list[dict[str, object]] = []

    def fake_codex_exec_with_schema(**kwargs):  # noqa: ANN003
        calls.append(dict(kwargs))
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
                "notes": ["mock_codex_allow_json_review"],
            },
        )

    monkeypatch.setattr(ask_guard, "codex_exec_with_schema", fake_codex_exec_with_schema)
    app = create_app()
    client = TestClient(app)
    body = {
        "kind": "chatgpt_web.ask",
        "input": {
            "question": (
                "Respond with JSON only using keys summary, risks, mitigations, readiness. "
                "Review this multi-team migration proposal and explain the operational, delivery, and rollback risks."
            )
        },
        "params": {"preset": "auto"},
    }

    res = client.post(
        "/v1/jobs",
        json=body,
        headers={
            **_signed_headers(
                client_lookup="planning-chatgptrest-call",
                client_instance="planner-json-review",
                method="POST",
                path="/v1/jobs",
                body_payload=body,
                environ={"CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER": "planning-secret"},
            ),
            "Idempotency-Key": "codex-guard-json-review",
        },
    )

    assert res.status_code == 200
    assert calls, "json-only substantive review should reach Codex classify"
    job_id = str(res.json()["job_id"])
    _client_json, params_json = _row_payloads(env["db_path"], job_id)
    assert params_json["ask_guard"]["decision"]["reason_code"] == "substantive_registered_automation"


def test_ask_guard_output_schema_requires_all_properties() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "ops" / "schemas" / "ask_guard_decision.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = set(schema.get("required") or [])
    properties = set((schema.get("properties") or {}).keys())
    assert required == properties


def test_registered_automation_json_only_microtask_still_blocks_deterministically(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "1")
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER", "planning-secret")
    app = create_app()
    client = TestClient(app)
    body = {
        "kind": "chatgpt_web.ask",
        "input": {
            "question": "Return only JSON array. Extract competitors from the supplied snippets."
        },
        "params": {"preset": "auto"},
    }

    res = client.post(
        "/v1/jobs",
        json=body,
        headers={
            **_signed_headers(
                client_lookup="planning-chatgptrest-call",
                client_instance="planner-json-microtask",
                method="POST",
                path="/v1/jobs",
                body_payload=body,
                environ={"CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER": "planning-secret"},
            ),
            "Idempotency-Key": "codex-guard-json-microtask",
        },
    )

    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "low_level_ask_intent_blocked"
    assert detail["reason"] == "structured_microtask"


def test_registered_automation_allow_with_limits_is_enforced(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "1")
    registry_path = tmp_path / "ask_client_registry_limits.json"
    registry_path.write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": [
                    {
                        "client_id": "limits-bot",
                        "aliases": ["limits-bot"],
                        "display_name": "Limits bot",
                        "source_type": "pipeline",
                        "trust_class": "automation_registered",
                        "auth_mode": "hmac",
                        "shared_secret_env": "ASK_GUARD_LIMITS_BOT_SECRET",
                        "allowed_surfaces": ["low_level_jobs"],
                        "allowed_kinds": ["chatgpt_web.ask"],
                        "allow_live_chatgpt": True,
                        "allow_gemini_web": False,
                        "allow_qwen_web": False,
                        "allow_deep_research": True,
                        "allow_pro": True,
                        "codex_guard_mode": "classify",
                        "notes": "Temporary profile for allow_with_limits enforcement tests."
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CHATGPTREST_ASK_CLIENT_REGISTRY_PATH", str(registry_path))
    monkeypatch.setenv("ASK_GUARD_LIMITS_BOT_SECRET", "limits-secret")

    def fake_codex_exec_with_schema(**kwargs):  # noqa: ANN003
        return CodexExecResult(
            ok=True,
            returncode=0,
            elapsed_ms=1,
            cmd=["codex", "exec"],
            output={
                "decision": "allow_with_limits",
                "reason_code": "substantive_registered_automation",
                "intent_class": "substantive_human_like_task",
                "substantive": True,
                "allow_live_chatgpt": True,
                "allow_deep_research": False,
                "allow_pro": False,
                "short_answer_ok": True,
                "min_chars_override": 0,
                "notes": ["mock_codex_allow_with_limits"],
            },
        )

    monkeypatch.setattr(ask_guard, "codex_exec_with_schema", fake_codex_exec_with_schema)
    app = create_app()
    client = TestClient(app)

    body = {
        "kind": "chatgpt_web.ask",
        "input": {
            "question": (
                "Please review this proposal for a multi-team platform migration, explain the operational and delivery "
                "tradeoffs, and summarize the top risks with mitigation priorities for the next release window."
            )
        },
        "params": {"preset": "thinking_heavy", "deep_research": True, "min_chars": 800},
    }
    res = client.post(
        "/v1/jobs",
        json=body,
        headers={
            **_signed_headers(
                client_lookup="limits-bot",
                client_instance="limits-bot-1",
                method="POST",
                path="/v1/jobs",
                body_payload=body,
                environ={"ASK_GUARD_LIMITS_BOT_SECRET": "limits-secret"},
            ),
            "Idempotency-Key": "codex-guard-limits",
        },
    )

    assert res.status_code == 200
    job_id = str(res.json()["job_id"])
    _client_json, params_json = _row_payloads(env["db_path"], job_id)
    assert params_json["preset"] == "auto"
    assert params_json["deep_research"] is False
    assert params_json["min_chars"] == 0
    assert params_json["ask_guard"]["resolved_client_id"] == "limits-bot"
    assert params_json["ask_guard"]["enforced_limits"] == {"preset": "auto", "deep_research": False, "min_chars": 0}


def test_registered_automation_codex_guard_allow_persists_audit_metadata(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "1")
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER", "planning-secret")

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
            "question": "Please review this architecture proposal and produce three concrete engineering risks with mitigations."
        },
        "params": {"preset": "auto"},
    }
    res = client.post(
        "/v1/jobs",
        json=body,
        headers={
            **_signed_headers(
                client_lookup="planning-chatgptrest-call",
                client_instance="planner-2",
                method="POST",
                path="/v1/jobs",
                body_payload=body,
                environ={"CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER": "planning-secret"},
                extra_headers={
                    "X-Source-Repo": "haizhouyuan/planning",
                    "X-Source-Entrypoint": "scripts/planning_chatgptrest_call.py",
                    "X-Client-Run-Id": "run-123",
                },
            ),
            "Idempotency-Key": "codex-guard-allow",
        },
    )

    assert res.status_code == 200
    job_id = str(res.json()["job_id"])
    client_json, params_json = _row_payloads(env["db_path"], job_id)
    assert client_json["name"] == "planning-wrapper"
    assert client_json["client_id"] == "planning-wrapper"
    assert client_json["requested_name"] == "planning-chatgptrest-call"
    assert client_json["source_repo"] == "haizhouyuan/planning"
    guard_payload = params_json["ask_guard"]
    assert guard_payload["resolved_client_id"] == "planning-wrapper"
    assert guard_payload["decision"]["reason_code"] == "substantive_registered_automation"
    assert guard_payload["source_entrypoint"] == "scripts/planning_chatgptrest_call.py"


def test_hmac_registered_client_must_present_valid_signature(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    registry_path = tmp_path / "ask_client_registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": [
                    {
                        "client_id": "signed-bot",
                        "aliases": ["signed-bot"],
                        "display_name": "Signed bot",
                        "source_type": "service",
                        "trust_class": "automation_registered",
                        "auth_mode": "hmac",
                        "shared_secret_env": "ASK_GUARD_SIGNED_BOT_SECRET",
                        "allowed_surfaces": ["low_level_jobs"],
                        "allowed_kinds": ["gemini_web.ask"],
                        "allow_live_chatgpt": False,
                        "allow_gemini_web": True,
                        "allow_qwen_web": False,
                        "allow_deep_research": False,
                        "allow_pro": True,
                        "codex_guard_mode": "deterministic_only",
                        "notes": "Signed automation client for ask guard tests."
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CHATGPTREST_ASK_CLIENT_REGISTRY_PATH", str(registry_path))
    monkeypatch.setenv("ASK_GUARD_SIGNED_BOT_SECRET", "super-secret")
    app = create_app()
    client = TestClient(app)
    body = {
        "kind": "gemini_web.ask",
        "input": {"question": "请给出三条不重复的工程建议。"},
        "params": {"preset": "auto"},
    }

    ok_headers = _signed_headers(
        client_lookup="signed-bot",
        client_instance="signed-bot-1",
        method="POST",
        path="/v1/jobs",
        body_payload=body,
        environ={"ASK_GUARD_SIGNED_BOT_SECRET": "super-secret"},
        extra_headers={"Idempotency-Key": "signed-bot-ok"},
    )

    ok = client.post(
        "/v1/jobs",
        json=body,
        headers=ok_headers,
    )
    assert ok.status_code == 200

    replay = client.post(
        "/v1/jobs",
        json=body,
        headers={**ok_headers, "Idempotency-Key": "signed-bot-replay"},
    )
    assert replay.status_code == 403
    detail = replay.json()["detail"]
    assert detail["error"] == "low_level_ask_client_auth_failed"
    assert detail["reason"] == "replayed_hmac_nonce"


def test_maintenance_internal_identity_requires_valid_hmac(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT", "maint-secret")
    app = create_app()
    client = TestClient(app)
    body = {
        "kind": "gemini_web.ask",
        "input": {"question": "请给出三条不重复的工程建议。"},
        "params": {"preset": "auto"},
    }

    unsigned = client.post(
        "/v1/jobs",
        json=body,
        headers={
            "Idempotency-Key": "maint-hmac-missing",
            "User-Agent": "curl/8.7.1",
            "X-Client-Name": "chatgptrestctl-maint",
            "X-Client-Instance": "maint-test-1",
        },
    )
    assert unsigned.status_code == 403
    unsigned_detail = unsigned.json()["detail"]
    assert unsigned_detail["error"] == "low_level_ask_client_auth_failed"
    assert unsigned_detail["reason"] == "missing_hmac_headers"

    signed = client.post(
        "/v1/jobs",
        json=body,
        headers=_signed_headers(
            client_lookup="chatgptrestctl-maint",
            client_instance="maint-test-1",
            method="POST",
            path="/v1/jobs",
            body_payload=body,
            environ={"CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT": "maint-secret"},
            extra_headers={"Idempotency-Key": "maint-hmac-ok"},
        ),
    )
    assert signed.status_code == 200


def test_default_planning_wrapper_requires_valid_hmac(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER", "planning-secret")
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "1")

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
        "input": {"question": "Please review this proposal and list the top risks."},
        "params": {"preset": "auto"},
    }

    unsigned = client.post(
        "/v1/jobs",
        json=body,
        headers={
            "Idempotency-Key": "planning-hmac-missing",
            "User-Agent": "curl/8.7.1",
            "X-Client-Name": "planning-chatgptrest-call",
            "X-Client-Instance": "planning-test-1",
        },
    )
    assert unsigned.status_code == 403
    unsigned_detail = unsigned.json()["detail"]
    assert unsigned_detail["error"] == "low_level_ask_client_auth_failed"
    assert unsigned_detail["reason"] == "missing_hmac_headers"

    signed = client.post(
        "/v1/jobs",
        json=body,
        headers={
            **_signed_headers(
                client_lookup="planning-chatgptrest-call",
                client_instance="planning-test-1",
                method="POST",
                path="/v1/jobs",
                body_payload=body,
                environ={"CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER": "planning-secret"},
            ),
            "Idempotency-Key": "planning-hmac-ok",
        },
    )
    assert signed.status_code == 200


def test_openclaw_wrapper_low_level_jobs_are_disabled(
    env: dict[str, Path],  # noqa: ARG001
) -> None:
    app = create_app()
    client = TestClient(app)

    res = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "Please review this proposal and summarize the main risks."},
            "params": {"preset": "auto"},
        },
        headers={
            "Idempotency-Key": "openclaw-low-level-disabled",
            "User-Agent": "curl/8.7.1",
            "X-Client-Name": "openclaw-chatgptrest-call",
            "X-Client-Instance": "openclaw-test-1",
        },
    )

    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "low_level_ask_surface_not_allowed"
    assert detail["reason"] == "client_surface_not_registered_for_low_level_jobs"


def test_advisor_alias_low_level_jobs_are_disabled(
    env: dict[str, Path],  # noqa: ARG001
) -> None:
    app = create_app()
    client = TestClient(app)

    res = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "Please review this proposal and summarize the main risks."},
            "params": {"preset": "auto"},
        },
        headers={
            "Idempotency-Key": "advisor-low-level-disabled",
            "User-Agent": "curl/8.7.1",
            "X-Client-Name": "advisor_ask",
            "X-Client-Instance": "advisor-test-1",
        },
    )

    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "low_level_ask_surface_not_allowed"
    assert detail["reason"] == "client_surface_not_registered_for_low_level_jobs"


def test_planning_wrapper_runtime_dedupe_blocks_recent_duplicate(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER", "planning-secret")
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "1")

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
            "question": "Respond with JSON only. Review this proposal and explain the top delivery risks with mitigations."
        },
        "params": {"preset": "auto"},
    }
    headers1 = _signed_headers(
        client_lookup="planning-chatgptrest-call",
        client_instance="planner-dedupe-1",
        method="POST",
        path="/v1/jobs",
        body_payload=body,
        environ={"CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER": "planning-secret"},
        nonce="planning-dedupe-nonce-1",
    )
    headers2 = _signed_headers(
        client_lookup="planning-chatgptrest-call",
        client_instance="planner-dedupe-1",
        method="POST",
        path="/v1/jobs",
        body_payload=body,
        environ={"CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER": "planning-secret"},
        nonce="planning-dedupe-nonce-2",
    )

    first = client.post("/v1/jobs", json=body, headers={**headers1, "Idempotency-Key": "planning-dedupe-1"})
    assert first.status_code == 200

    second = client.post("/v1/jobs", json=body, headers={**headers2, "Idempotency-Key": "planning-dedupe-2"})
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["error"] == "low_level_ask_duplicate_recently_submitted"
    assert detail["reason"] == "duplicate_recent_low_level_ask"


def test_planning_wrapper_runtime_dedupe_allows_immediate_retry_after_error(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER", "planning-secret")
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "1")

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
            "question": "Respond with JSON only. Review this proposal and explain the top delivery risks with mitigations."
        },
        "params": {"preset": "auto"},
    }
    headers1 = _signed_headers(
        client_lookup="planning-chatgptrest-call",
        client_instance="planner-dedupe-retry-1",
        method="POST",
        path="/v1/jobs",
        body_payload=body,
        environ={"CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER": "planning-secret"},
        nonce="planning-dedupe-retry-nonce-1",
    )
    headers2 = _signed_headers(
        client_lookup="planning-chatgptrest-call",
        client_instance="planner-dedupe-retry-1",
        method="POST",
        path="/v1/jobs",
        body_payload=body,
        environ={"CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER": "planning-secret"},
        nonce="planning-dedupe-retry-nonce-2",
    )

    first = client.post("/v1/jobs", json=body, headers={**headers1, "Idempotency-Key": "planning-dedupe-retry-1"})
    assert first.status_code == 200
    first_job_id = first.json()["job_id"]

    conn = sqlite3.connect(env["db_path"])
    try:
        conn.execute("UPDATE jobs SET status = 'error', updated_at = ? WHERE job_id = ?", (time.time(), first_job_id))
        conn.commit()
    finally:
        conn.close()

    second = client.post("/v1/jobs", json=body, headers={**headers2, "Idempotency-Key": "planning-dedupe-retry-2"})
    assert second.status_code == 200
    assert second.json()["job_id"] != first_job_id


def test_automation_registered_low_level_jobs_must_use_hmac(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "ask_client_registry_registry_mode.json"
    registry_path.write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": [
                    {
                        "client_id": "registry-bot",
                        "aliases": ["registry-bot"],
                        "display_name": "Registry bot",
                        "source_type": "pipeline",
                        "trust_class": "automation_registered",
                        "auth_mode": "registry",
                        "allowed_surfaces": ["low_level_jobs"],
                        "allowed_kinds": ["chatgpt_web.ask"],
                        "allow_live_chatgpt": True,
                        "allow_gemini_web": False,
                        "allow_qwen_web": False,
                        "allow_deep_research": False,
                        "allow_pro": False,
                        "codex_guard_mode": "deterministic_only",
                        "notes": "Invalid low-level profile used to verify hard-auth enforcement."
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CHATGPTREST_ASK_CLIENT_REGISTRY_PATH", str(registry_path))
    app = create_app()
    client = TestClient(app)

    res = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "Please review this proposal and list the top risks."},
            "params": {"preset": "auto"},
        },
        headers={
            "Idempotency-Key": "registry-bot-misconfigured",
            "User-Agent": "curl/8.7.1",
            "X-Client-Name": "registry-bot",
            "X-Client-Instance": "registry-bot-1",
        },
    )

    assert res.status_code == 500
    detail = res.json()["detail"]
    assert detail["error"] == "low_level_ask_registry_misconfigured"
    assert detail["reason"] == "automation_low_level_jobs_requires_hmac"


def test_runtime_max_in_flight_jobs_blocks_third_request(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CHATGPTREST_ASK_GUARD_CODEX_ENABLED", "1")
    registry_path = tmp_path / "ask_client_registry_concurrency.json"
    registry_path.write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": [
                    {
                        "client_id": "limited-bot",
                        "aliases": ["limited-bot"],
                        "display_name": "Limited bot",
                        "source_type": "pipeline",
                        "trust_class": "automation_registered",
                        "auth_mode": "hmac",
                        "shared_secret_env": "ASK_GUARD_LIMITED_BOT_SECRET",
                        "allowed_surfaces": ["low_level_jobs"],
                        "allowed_kinds": ["chatgpt_web.ask"],
                        "allow_live_chatgpt": True,
                        "allow_gemini_web": False,
                        "allow_qwen_web": False,
                        "allow_deep_research": False,
                        "allow_pro": False,
                        "max_in_flight_jobs": 2,
                        "dedupe_window_seconds": 0,
                        "codex_guard_mode": "classify",
                        "notes": "Temporary profile used to verify max_in_flight enforcement."
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CHATGPTREST_ASK_CLIENT_REGISTRY_PATH", str(registry_path))
    monkeypatch.setenv("ASK_GUARD_LIMITED_BOT_SECRET", "limited-secret")

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
                "allow_pro": False,
                "short_answer_ok": False,
                "notes": ["mock_codex_allow"],
            },
        )

    monkeypatch.setattr(ask_guard, "codex_exec_with_schema", fake_codex_exec_with_schema)
    app = create_app()
    client = TestClient(app)

    def _post(idx: int, question: str) -> Any:
        body = {
            "kind": "chatgpt_web.ask",
            "input": {"question": question},
            "params": {"preset": "auto"},
        }
        headers = _signed_headers(
            client_lookup="limited-bot",
            client_instance="limited-bot-1",
            method="POST",
            path="/v1/jobs",
            body_payload=body,
            environ={"ASK_GUARD_LIMITED_BOT_SECRET": "limited-secret"},
            nonce=f"limited-bot-nonce-{idx}",
        )
        return client.post("/v1/jobs", json=body, headers={**headers, "Idempotency-Key": f"limited-bot-{idx}"})

    first = _post(1, "Review proposal A and list the top risks.")
    second = _post(2, "Review proposal B and list the top risks.")
    third = _post(3, "Review proposal C and list the top risks.")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    detail = third.json()["detail"]
    assert detail["error"] == "low_level_ask_client_concurrency_exceeded"
    assert detail["reason"] == "registered_client_max_in_flight_exceeded"
