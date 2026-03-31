from __future__ import annotations

import pytest

from chatgptrest.integrations.openclaw_adapter import (
    OpenClawAdapter,
    OpenClawAdapterError,
    openclaw_mcp_url_from_params,
)


class _FakeClient:
    def __init__(self, *, fail_tool: str | None = None):
        self.calls: list[tuple[str, dict]] = []
        self.fail_tool = fail_tool

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):
        self.calls.append((tool_name, dict(tool_args)))
        if self.fail_tool and tool_name == self.fail_tool:
            raise RuntimeError(f"{tool_name} failed")
        if tool_name == "sessions_spawn":
            return {"ok": True, "sessionKey": tool_args.get("sessionKey")}
        if tool_name == "sessions_send":
            return {"ok": True, "ack": True}
        if tool_name == "session_status":
            return {"ok": True, "status": "running"}
        return {"ok": True}


def test_openclaw_mcp_url_from_params(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHATGPTREST_OPENCLOW_MCP_URL", raising=False)
    monkeypatch.delenv("CHATGPTREST_OPENCLAW_MCP_URL", raising=False)
    assert openclaw_mcp_url_from_params({}) is None
    monkeypatch.setenv("CHATGPTREST_OPENCLAW_MCP_URL", "http://127.0.0.1:18801/mcp")
    assert openclaw_mcp_url_from_params({}) == "http://127.0.0.1:18801/mcp"
    assert openclaw_mcp_url_from_params({"openclaw_mcp_url": "http://localhost:18803/mcp"}) == "http://localhost:18803/mcp"
    assert openclaw_mcp_url_from_params({"openclaw_mcp_url": "http://127.0.0.1:18802/mcp"}) == "http://127.0.0.1:18802/mcp"
    monkeypatch.delenv("CHATGPTREST_OPENCLAW_MCP_URL", raising=False)
    monkeypatch.setenv("CHATGPTREST_OPENCLOW_MCP_URL", "http://127.0.0.1:18804/mcp")
    assert openclaw_mcp_url_from_params({}) == "http://127.0.0.1:18804/mcp"


def test_openclaw_mcp_url_rejects_non_loopback_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHATGPTREST_OPENCLAW_ALLOW_REMOTE_MCP_URL", raising=False)
    monkeypatch.delenv("CHATGPTREST_OPENCLOW_ALLOW_REMOTE_MCP_URL", raising=False)
    with pytest.raises(ValueError, match="loopback"):
        openclaw_mcp_url_from_params({"openclaw_mcp_url": "http://10.0.0.8:18801/mcp"})


def test_openclaw_mcp_url_can_allow_remote_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_OPENCLAW_ALLOW_REMOTE_MCP_URL", "1")
    assert openclaw_mcp_url_from_params({"openclaw_mcp_url": "http://10.0.0.8:18801/mcp"}) == "http://10.0.0.8:18801/mcp"


def test_openclaw_adapter_run_protocol_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient()

    def _fake_init(self, *, url: str, client_name: str = "x", client_version: str = "x"):  # noqa: ANN001
        self._url = url
        self._client = fake

    monkeypatch.setattr(OpenClawAdapter, "__init__", _fake_init)
    adapter = OpenClawAdapter(url="http://127.0.0.1:18801/mcp")
    trace = adapter.run_protocol(run_id="r1", step_id="s1", question="hello", params={"openclaw_agent_id": "pm"})
    assert trace.session_key.startswith("advisor:r1:s1:")
    assert trace.spawn["ok"] is True
    assert trace.send is not None and trace.send["ok"] is True
    assert trace.status is not None and trace.status["status"] == "running"
    assert [name for name, _ in fake.calls] == ["sessions_spawn", "sessions_send", "session_status"]


def test_openclaw_adapter_run_protocol_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(fail_tool="sessions_send")

    def _fake_init(self, *, url: str, client_name: str = "x", client_version: str = "x"):  # noqa: ANN001
        self._url = url
        self._client = fake

    monkeypatch.setattr(OpenClawAdapter, "__init__", _fake_init)
    adapter = OpenClawAdapter(url="http://127.0.0.1:18801/mcp")
    with pytest.raises(OpenClawAdapterError):
        adapter.sessions_send(tool_args={"sessionKey": "k1", "message": "x"}, timeout_sec=5.0)
