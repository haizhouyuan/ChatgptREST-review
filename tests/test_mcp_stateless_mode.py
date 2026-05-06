from __future__ import annotations

import asyncio
import importlib

import pytest


def _load_mcp_server_module():
    import chatgptrest.mcp.server as mod

    return importlib.reload(mod)


def test_fastmcp_stateless_http_defaults_to_true(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FASTMCP_STATELESS_HTTP", raising=False)
    monkeypatch.delenv("CHATGPTREST_CLIENT_NAME", raising=False)
    monkeypatch.delenv("CHATGPTREST_AGENT_MCP_CLIENT_NAME", raising=False)
    monkeypatch.delenv("CHATGPTREST_AGENT_MCP_STATELESS_HTTP", raising=False)
    mod = _load_mcp_server_module()
    assert mod._fastmcp_stateless_http_default() is True
    assert mod._background_wait_stateless_http_default() is True


def test_fastmcp_stateless_http_env_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FASTMCP_STATELESS_HTTP", "1")
    mod = _load_mcp_server_module()
    assert mod._fastmcp_stateless_http_default() is True
    assert mod._background_wait_stateless_http_default() is True

    monkeypatch.setenv("FASTMCP_STATELESS_HTTP", "0")
    mod = _load_mcp_server_module()
    assert mod._fastmcp_stateless_http_default() is False
    assert mod._background_wait_stateless_http_default() is False


def test_background_wait_defaults_to_stateful_for_public_agent_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FASTMCP_STATELESS_HTTP", raising=False)
    monkeypatch.delenv("CHATGPTREST_AGENT_MCP_STATELESS_HTTP", raising=False)
    monkeypatch.setenv("CHATGPTREST_CLIENT_NAME", "chatgptrest-agent-mcp")
    mod = _load_mcp_server_module()

    assert mod._fastmcp_stateless_http_default() is True
    assert mod._background_wait_stateless_http_default() is False


def test_background_wait_honors_public_agent_stateless_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FASTMCP_STATELESS_HTTP", raising=False)
    monkeypatch.setenv("CHATGPTREST_CLIENT_NAME", "chatgptrest-agent-mcp")
    monkeypatch.setenv("CHATGPTREST_AGENT_MCP_STATELESS_HTTP", "1")
    mod = _load_mcp_server_module()

    assert mod._background_wait_stateless_http_default() is True


def test_background_wait_start_rejects_stateless_runtime(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FASTMCP_STATELESS_HTTP", raising=False)
    monkeypatch.delenv("CHATGPTREST_CLIENT_NAME", raising=False)
    monkeypatch.delenv("CHATGPTREST_AGENT_MCP_CLIENT_NAME", raising=False)
    monkeypatch.delenv("CHATGPTREST_AGENT_MCP_STATELESS_HTTP", raising=False)
    mod = _load_mcp_server_module()

    async def scenario() -> dict[str, object]:
        return await mod.chatgptrest_job_wait_background_start(
            "j1",
            timeout_seconds=60,
            poll_seconds=1.0,
            notify_controller=False,
            notify_done=False,
        )

    out = asyncio.run(scenario())
    assert out["ok"] is False
    assert out["error_type"] == "BackgroundWaitUnsupported"
    assert out["job_id"] == "j1"


def test_background_wait_start_allows_stateful_runtime(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FASTMCP_STATELESS_HTTP", raising=False)
    monkeypatch.setenv("CHATGPTREST_CLIENT_NAME", "chatgptrest-agent-mcp")
    monkeypatch.delenv("CHATGPTREST_AGENT_MCP_STATELESS_HTTP", raising=False)
    mod = _load_mcp_server_module()

    async def fake_wait(**_kwargs):  # noqa: ANN003
        return {"ok": True, "job_id": "j1", "status": "completed"}

    monkeypatch.setattr(mod, "_chatgptrest_job_wait_impl", fake_wait)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    async def scenario() -> dict[str, object]:
        started = await mod.chatgptrest_job_wait_background_start(
            "j1",
            timeout_seconds=30,
            poll_seconds=0.2,
            notify_controller=False,
            notify_done=False,
        )
        return started

    out = asyncio.run(scenario())
    assert out["ok"] is True
    assert out["watch_status"] == "running"
