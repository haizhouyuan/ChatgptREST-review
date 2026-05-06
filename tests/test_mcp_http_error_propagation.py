from __future__ import annotations

import pytest

from chatgptrest.driver.api import ToolCallError
from chatgptrest.driver.backends.mcp_http import McpHttpToolCaller
from chatgptrest.integrations import mcp_http_client as client_mod
from chatgptrest.integrations.mcp_http_client import McpHttpError, McpHttpSession


def test_mcp_http_call_tool_wraps_empty_unexpected_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    session = McpHttpSession(url="http://127.0.0.1:18701/mcp", session_id=None, protocol_version="2025-06-18")

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError()

    monkeypatch.setattr(client_mod, "_jsonrpc_post_stream", _boom)

    with pytest.raises(McpHttpError, match=r"tools/call transport failure: RuntimeError: <empty error>"):
        client_mod.mcp_http_call_tool(session, tool_name="gemini_web_ask_pro", tool_args={"question": "x"})


def test_mcp_http_tool_caller_wraps_empty_unexpected_exception() -> None:
    caller = object.__new__(McpHttpToolCaller)

    class _FakeClient:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ANN001
            raise RuntimeError()

    caller._client = _FakeClient()

    with pytest.raises(
        ToolCallError,
        match=r"mcp_http tool gemini_web_ask_pro unexpected failure on attempt 1/15: RuntimeError: <empty error>",
    ):
        caller.call_tool(tool_name="gemini_web_ask_pro", tool_args={"question": "x"})



def test_mcp_http_client_does_not_retry_fresh_session_on_deadline_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str | None]] = []

    def _fake_initialize(url: str, *, client_name: str, client_version: str, protocol_version: str = "2025-06-18", timeout_sec: float = 30.0):  # noqa: ARG001
        calls.append(("initialize", None))
        return McpHttpSession(url=url, session_id=f"session-{len(calls)}", protocol_version=protocol_version)

    def _fake_call(session: McpHttpSession, *, tool_name: str, tool_args: dict, timeout_sec: float = 600.0):  # noqa: ARG001
        calls.append(("call", session.session_id))
        raise McpHttpError("SSE stream timeout (deadline exceeded).")

    monkeypatch.setattr(client_mod, 'mcp_http_initialize', _fake_initialize)
    monkeypatch.setattr(client_mod, 'mcp_http_call_tool', _fake_call)

    client = client_mod.McpHttpClient(url="http://127.0.0.1:18712/mcp", client_name="test", client_version="v1")

    with pytest.raises(McpHttpError, match=r"deadline exceeded"):
        client.call_tool(tool_name="gemini_web_ask_pro", tool_args={"question": "x"}, timeout_sec=45.0)

    assert calls == [
        ("initialize", None),
        ("call", "session-1"),
    ]


def test_mcp_http_client_retries_fresh_session_on_sse_jsonrpc_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    init_count = {'value': 0}
    call_count = {'value': 0}

    def _fake_initialize(url: str, *, client_name: str, client_version: str, protocol_version: str = "2025-06-18", timeout_sec: float = 30.0):  # noqa: ARG001
        init_count['value'] += 1
        return McpHttpSession(url=url, session_id=f"session-{init_count['value']}", protocol_version=protocol_version)

    def _fake_call(session: McpHttpSession, *, tool_name: str, tool_args: dict, timeout_sec: float = 600.0):  # noqa: ARG001
        call_count['value'] += 1
        if call_count['value'] == 1:
            raise McpHttpError("SSE stream ended without a JSON-RPC response.")
        return {"ok": True, "session_id": session.session_id}

    monkeypatch.setattr(client_mod, 'mcp_http_initialize', _fake_initialize)
    monkeypatch.setattr(client_mod, 'mcp_http_call_tool', _fake_call)

    client = client_mod.McpHttpClient(url="http://127.0.0.1:18712/mcp", client_name="test", client_version="v1")

    result = client.call_tool(tool_name="gemini_web_ask_pro", tool_args={"question": "x"}, timeout_sec=45.0)

    assert result == {"ok": True, "session_id": "session-2"}
    assert init_count['value'] == 2
    assert call_count['value'] == 2


def test_mcp_http_client_retries_fresh_session_on_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    init_count = {'value': 0}
    call_count = {'value': 0}

    def _fake_initialize(url: str, *, client_name: str, client_version: str, protocol_version: str = "2025-06-18", timeout_sec: float = 30.0):  # noqa: ARG001
        init_count['value'] += 1
        return McpHttpSession(url=url, session_id=f"session-{init_count['value']}", protocol_version=protocol_version)

    def _fake_call(session: McpHttpSession, *, tool_name: str, tool_args: dict, timeout_sec: float = 600.0):  # noqa: ARG001
        call_count['value'] += 1
        if call_count['value'] == 1:
            raise McpHttpError("transport error: Connection refused")
        return {"ok": True, "session_id": session.session_id}

    monkeypatch.setattr(client_mod, 'mcp_http_initialize', _fake_initialize)
    monkeypatch.setattr(client_mod, 'mcp_http_call_tool', _fake_call)

    client = client_mod.McpHttpClient(url="http://127.0.0.1:18712/mcp", client_name="test", client_version="v1")

    result = client.call_tool(tool_name="gemini_web_ask_pro", tool_args={"question": "x"}, timeout_sec=45.0)

    assert result == {"ok": True, "session_id": "session-2"}
    assert init_count['value'] == 2
    assert call_count['value'] == 2


def test_jsonrpc_post_stream_uses_extended_socket_timeout_for_long_loopback_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, float] = {}

    class _FakeResponse:
        status = 200

        def __init__(self) -> None:
            self.headers = {}

    def _fake_urlopen(req, *, timeout_sec: float, bypass_proxy: bool):  # noqa: ANN001
        seen["timeout_sec"] = timeout_sec
        seen["bypass_proxy"] = bypass_proxy
        return _FakeResponse()

    monkeypatch.setattr(client_mod, '_urlopen', _fake_urlopen)

    status, _headers, _resp = client_mod._jsonrpc_post_stream(
        'http://127.0.0.1:18712/mcp',
        message={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        headers={},
        timeout_sec=150.0,
    )

    assert status == 200
    assert seen["timeout_sec"] == 150.0
    assert seen["bypass_proxy"] is True


def test_mcp_http_initialize_handshake_returns_result_and_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeResponse:
        status = 200

        def __init__(self) -> None:
            self.headers = {
                "content-type": "application/json",
                "mcp-session-id": "mcp-sess-1",
            }

        def read(self) -> bytes:
            return b'{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26","serverInfo":{"name":"chatgptrest-agent-mcp"}}}'

        def close(self) -> None:
            return None

    class _FakeNotificationResponse:
        def close(self) -> None:
            return None

    monkeypatch.setattr(
        client_mod,
        "_jsonrpc_post_stream",
        lambda url, *, message, headers, timeout_sec: (200, {"content-type": "application/json", "mcp-session-id": "mcp-sess-1"}, _FakeResponse()),
    )
    monkeypatch.setattr(client_mod.urllib.request, "urlopen", lambda *args, **kwargs: _FakeNotificationResponse())

    handshake = client_mod.mcp_http_initialize_handshake(
        "http://127.0.0.1:18712/mcp",
        client_name="test-client",
        client_version="v1",
        protocol_version="2025-03-26",
    )

    assert handshake.session.session_id == "mcp-sess-1"
    assert handshake.session.protocol_version == "2025-03-26"
    assert handshake.result["serverInfo"]["name"] == "chatgptrest-agent-mcp"


def test_mcp_http_initialize_handshake_retries_once_on_sse_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    class _FakeResponse:
        status = 200

        def __init__(self) -> None:
            self.headers = {"content-type": "application/json", "mcp-session-id": "mcp-sess-2"}

        def read(self) -> bytes:
            return b'{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26","serverInfo":{"name":"chatgptrest-agent-mcp"}}}'

        def close(self) -> None:
            return None

    class _FakeNotificationResponse:
        def close(self) -> None:
            return None

    def _fake_jsonrpc_post_stream(url, *, message, headers, timeout_sec):  # noqa: ANN001, ARG001
        calls["count"] += 1
        if calls["count"] == 1:
            raise McpHttpError("SSE stream timeout (deadline exceeded).")
        return 200, {"content-type": "application/json", "mcp-session-id": "mcp-sess-2"}, _FakeResponse()

    monkeypatch.setattr(client_mod, "_jsonrpc_post_stream", _fake_jsonrpc_post_stream)
    monkeypatch.setattr(client_mod.urllib.request, "urlopen", lambda *args, **kwargs: _FakeNotificationResponse())
    monkeypatch.setattr(client_mod.time, "sleep", lambda _seconds: None)

    handshake = client_mod.mcp_http_initialize_handshake(
        "http://127.0.0.1:18712/mcp",
        client_name="test-client",
        client_version="v1",
        protocol_version="2025-03-26",
    )

    assert calls["count"] == 2
    assert handshake.session.session_id == "mcp-sess-2"


def test_mcp_http_list_tools_returns_tools_array(monkeypatch: pytest.MonkeyPatch) -> None:
    session = McpHttpSession(url="http://127.0.0.1:18712/mcp", session_id="mcp-sess-1", protocol_version="2025-03-26")

    class _FakeResponse:
        status = 200

        def __init__(self) -> None:
            self.headers = {"content-type": "application/json"}

        def read(self) -> bytes:
            return (
                b'{"jsonrpc":"2.0","id":123,"result":{"tools":[{"name":"automation_ask"},{"name":"automation_job_status"}]}}'
            )

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        client_mod,
        "_jsonrpc_post_stream",
        lambda url, *, message, headers, timeout_sec: (200, {"content-type": "application/json"}, _FakeResponse()),
    )
    monkeypatch.setattr(client_mod.time, "time", lambda: 0.123)

    tools = client_mod.mcp_http_list_tools(session, timeout_sec=30.0)

    assert [tool["name"] for tool in tools] == ["automation_ask", "automation_job_status"]
