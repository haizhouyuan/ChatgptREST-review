from __future__ import annotations

import asyncio

import pytest

import chatgptrest.mcp.server as mcp_server


def test_mcp_auth_headers_include_trace_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_CLIENT_NAME", "mcp-tests")
    monkeypatch.setenv("CHATGPTREST_CLIENT_INSTANCE", "mcp-instance-1")
    monkeypatch.setenv("CHATGPTREST_REQUEST_ID_PREFIX", "mcp-rid")

    h1 = mcp_server._auth_headers()
    h2 = mcp_server._auth_headers()

    assert h1["X-Client-Name"] == "mcp-tests"
    assert h1["X-Client-Instance"] == "mcp-instance-1"
    assert h1["X-Request-ID"].startswith("mcp-rid-")
    assert h2["X-Request-ID"] != h1["X-Request-ID"]


def test_mcp_auth_headers_fallback_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_CLIENT_NAME", "mcp-tests")
    monkeypatch.delenv("CHATGPTREST_CLIENT_INSTANCE", raising=False)
    monkeypatch.delenv("CHATGPTREST_REQUEST_ID_PREFIX", raising=False)

    headers = mcp_server._auth_headers()
    assert headers["X-Client-Name"] == "mcp-tests"
    assert headers["X-Client-Instance"]
    assert headers["X-Request-ID"].startswith("mcp-tests-")


def test_mcp_job_create_signs_hmac_for_registered_maintenance_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_CLIENT_NAME", "chatgptrest-admin-mcp")
    monkeypatch.setenv("CHATGPTREST_CLIENT_INSTANCE", "admin-mcp-1")
    monkeypatch.setenv("CHATGPTREST_ASK_HMAC_SECRET_ADMIN_MCP", "admin-secret")
    captured: dict[str, object] = {}

    def fake_http_json(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return {"ok": True, "job_id": "job-1", "status": "queued"}

    monkeypatch.setattr(mcp_server, "_http_json", fake_http_json)

    result = asyncio.run(
        mcp_server.chatgptrest_job_create(
            idempotency_key="idem-hmac-1",
            kind="gemini_web.ask",
            input={"question": "请给出三条不重复的工程建议。"},
            params={"preset": "auto"},
            client={"name": "chatgptrest_gemini_ask_submit"},
        )
    )

    assert result["job_id"] == "job-1"
    headers = dict(captured["headers"])
    assert headers["X-Client-Name"] == "chatgptrest-admin-mcp"
    assert headers["X-Client-Id"] == "chatgptrest-admin-mcp"
    assert headers["X-Client-Timestamp"]
    assert headers["X-Client-Nonce"]
    assert headers["X-Client-Signature"]


def test_mcp_default_cancel_reason_uses_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHATGPTREST_CANCEL_REASON_DEFAULT", raising=False)
    reason = mcp_server._default_cancel_reason(job_id="job-abc")
    assert reason.startswith("mcp_cancel:job-abc")


def test_mcp_default_cancel_reason_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_CANCEL_REASON_DEFAULT", "manual close by guardian")
    reason = mcp_server._default_cancel_reason(job_id="job-abc")
    assert reason == "manual close by guardian"
