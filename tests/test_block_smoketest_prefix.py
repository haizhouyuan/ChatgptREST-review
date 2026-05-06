from __future__ import annotations

import time
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
    monkeypatch.setenv("CHATGPTREST_PREVIEW_CHARS", "10")
    monkeypatch.setenv("CHATGPTREST_SAVE_CONVERSATION_EXPORT", "0")
    return {"db_path": db_path, "artifacts_dir": artifacts_dir}


def _signed_headers(
    *,
    client_lookup: str,
    client_instance: str,
    method: str,
    path: str,
    body_payload: dict[str, object],
    environ: dict[str, str] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    headers = {
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
            nonce=f"{client_lookup}-{time.time_ns()}",
        )
    )
    if extra_headers:
        headers.update(extra_headers)
    return headers


def test_blocks_smoketest_prefix_by_default(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "(smoketest) 只回复：ok"}, "params": {"preset": "auto"}},
        headers={"Idempotency-Key": "smoke-blocked"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "live_chatgpt_smoke_blocked"


def test_blocks_live_chatgpt_smoke_purpose_even_with_auto_preset(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请帮我确认链路是否通了"},
            "params": {"preset": "auto", "purpose": "smoke"},
        },
        headers={"Idempotency-Key": "live-chatgpt-smoke-auto-blocked"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "live_chatgpt_smoke_blocked"


def test_blocks_synthetic_fault_probe_prompt_by_default(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "test blocked state"}, "params": {"preset": "auto"}},
        headers={"Idempotency-Key": "live-chatgpt-state-probe-blocked"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "live_chatgpt_smoke_blocked"


def test_blocks_live_chatgpt_smoke_client_name_by_default(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "今天北京的天气大概多少度？"},
            "params": {"preset": "auto"},
            "client": {"name": "smoke_test_chatgpt_auto"},
        },
        headers={"Idempotency-Key": "live-chatgpt-client-name-blocked"},
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "low_level_ask_live_chatgpt_not_allowed"


def test_allows_smoketest_when_explicitly_overridden(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "(smoketest) 只回复：ok"},
            "params": {"preset": "auto", "allow_live_chatgpt_smoke": True},
        },
        headers={"Idempotency-Key": "smoke-allowed"},
    )
    assert r.status_code == 200


def test_env_can_disable_smoketest_block(env: dict[str, Path], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_ENFORCE_PROMPT_SUBMISSION_POLICY", "0")
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "(smoke test) 只回复：ok"}, "params": {"preset": "auto"}},
        headers={"Idempotency-Key": "smoke-env-off"},
    )
    assert r.status_code == 200


def test_blocks_trivial_prompt_on_chatgpt_pro_by_default(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={"kind": "chatgpt_web.ask", "input": {"question": "请回复OK"}, "params": {"preset": "pro_extended"}},
        headers={"Idempotency-Key": "trivial-pro-blocked"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "trivial_pro_prompt_blocked"


def test_still_blocks_trivial_prompt_on_chatgpt_pro_when_override_flag_present(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请回复OK"},
            "params": {"preset": "pro_extended", "allow_trivial_pro_prompt": True},
        },
        headers={"Idempotency-Key": "trivial-pro-override-still-blocked"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "trivial_pro_prompt_blocked"


def test_blocks_smoke_purpose_on_chatgpt_pro_by_default(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请帮我确认链路是否通了"},
            "params": {"preset": "pro_extended", "purpose": "smoke"},
        },
        headers={"Idempotency-Key": "smoke-pro-blocked"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "pro_smoke_test_blocked"


def test_still_blocks_smoke_purpose_on_chatgpt_pro_when_override_flag_present(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请帮我确认链路是否通了"},
            "params": {"preset": "pro_extended", "purpose": "smoke", "allow_pro_smoke_test": True},
        },
        headers={"Idempotency-Key": "smoke-pro-override-still-blocked"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "pro_smoke_test_blocked"


def test_blocks_smoke_purpose_on_gemini_pro_by_default(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "quick probe"},
            "params": {"preset": "pro", "purpose": "smoke"},
        },
        headers={"Idempotency-Key": "smoke-gemini-pro-blocked"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "pro_smoke_test_blocked"


def test_allows_live_chatgpt_smoke_with_explicit_override(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "test cooldown state"},
            "params": {"preset": "auto", "allow_live_chatgpt_smoke": True},
        },
        headers={"Idempotency-Key": "live-chatgpt-smoke-allowed"},
    )
    assert r.status_code == 200


def test_blocks_direct_live_chatgpt_ask_from_chatgptrestctl(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请对附带蓝图做严格战略评审。"},
            "params": {"preset": "auto"},
        },
        headers={
            "Idempotency-Key": "direct-live-chatgpt-blocked",
            "X-Client-Name": "chatgptrestctl",
            "User-Agent": "curl/7.88.1",
        },
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "direct_live_chatgpt_ask_blocked"


def test_allows_direct_live_chatgpt_ask_for_allowlisted_client(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_ADMIN_MCP", "admin-secret")
    app = create_app()
    client = TestClient(app)
    body = {
        "kind": "chatgpt_web.ask",
        "input": {"question": "请对附带蓝图做严格战略评审。"},
        "params": {"preset": "auto"},
    }
    r = client.post(
        "/v1/jobs",
        json=body,
        headers=_signed_headers(
            client_lookup="chatgptrest-admin-mcp",
            client_instance="admin-mcp-test-1",
            method="POST",
            path="/v1/jobs",
            body_payload=body,
            environ={"CHATGPTREST_ASK_HMAC_SECRET_ADMIN_MCP": "admin-secret"},
            extra_headers={"Idempotency-Key": "direct-live-chatgpt-allowed"},
        ),
    )
    assert r.status_code == 200


def test_still_blocks_direct_live_chatgpt_ask_for_interactive_client_even_with_override(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请对附带蓝图做严格战略评审。"},
            "params": {"preset": "auto", "allow_direct_live_chatgpt_ask": True},
        },
        headers={
            "Idempotency-Key": "direct-live-chatgpt-override",
            "X-Client-Name": "chatgptrestctl",
            "User-Agent": "curl/7.88.1",
        },
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "direct_live_chatgpt_ask_blocked"


def test_blocks_direct_low_level_gemini_ask_from_chatgptrestctl(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "请对这个候选方案做一次严格评审。"},
            "params": {"preset": "auto"},
        },
        headers={
            "Idempotency-Key": "direct-low-level-gemini-blocked",
            "X-Client-Name": "chatgptrestctl",
        },
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "coding_agent_low_level_ask_blocked"


def test_blocks_low_level_gemini_ask_from_legacy_mcp_body_client(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "请从工程角度指出这里的主要风险。"},
            "params": {"preset": "auto"},
            "client": {"name": "chatgptrest_ask"},
        },
        headers={
            "Idempotency-Key": "direct-low-level-gemini-mcp-blocked",
        },
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "coding_agent_low_level_ask_blocked"


def test_allows_low_level_gemini_ask_for_maintenance_client(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT", "maint-secret")
    app = create_app()
    client = TestClient(app)
    body = {
        "kind": "gemini_web.ask",
        "input": {"question": "请输出三条不重复的工程建议。"},
        "params": {"preset": "auto"},
    }
    r = client.post(
        "/v1/jobs",
        json=body,
        headers=_signed_headers(
            client_lookup="chatgptrestctl-maint",
            client_instance="maint-test-1",
            method="POST",
            path="/v1/jobs",
            body_payload=body,
            environ={"CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT": "maint-secret"},
            extra_headers={"Idempotency-Key": "direct-low-level-gemini-maint-allowed"},
        ),
    )
    assert r.status_code == 200


def test_blocks_explicit_brevity_prompt_on_chatgpt_pro_by_default(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请用四句话解释 issue ledger 的作用。"},
            "params": {"preset": "pro_extended"},
        },
        headers={"Idempotency-Key": "trivial-pro-brevity-blocked"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "trivial_pro_prompt_blocked"


def test_still_blocks_brevity_prompt_on_chatgpt_pro_when_override_flag_present(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请用四句话解释 issue ledger 的作用。"},
            "params": {"preset": "pro_extended", "allow_trivial_pro_prompt": True},
        },
        headers={"Idempotency-Key": "trivial-pro-brevity-override-still-blocked"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "trivial_pro_prompt_blocked"


def test_blocks_concise_explainer_prompt_on_chatgpt_pro_by_default(env: dict[str, Path]):
    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请简要说明 issue ledger 是什么。"},
            "params": {"preset": "pro_extended"},
        },
        headers={"Idempotency-Key": "trivial-pro-concise-explainer-blocked"},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "trivial_pro_prompt_blocked"
