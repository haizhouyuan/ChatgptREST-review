from __future__ import annotations

import sys
from contextlib import AsyncExitStack

import pytest


def test_public_mcp_entrypoint_runs_agent_server(monkeypatch: pytest.MonkeyPatch) -> None:
    import chatgptrest_mcp_server as module

    seen: dict[str, str] = {}

    def fake_run(*, transport: str) -> None:
        seen["transport"] = transport

    monkeypatch.setattr(module.mcp, "run", fake_run)
    monkeypatch.setattr(module, "ensure_public_agent_mcp_auth_configured", lambda: {"ok": True, "source": "OPENMIND_API_KEY"})
    monkeypatch.setattr(sys, "argv", ["chatgptrest_mcp_server.py", "--transport", "streamable-http"])

    module.main()

    assert seen == {"transport": "streamable-http"}


def test_public_mcp_entrypoint_fails_fast_without_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    import chatgptrest_mcp_server as module

    monkeypatch.setattr(
        module,
        "ensure_public_agent_mcp_auth_configured",
        lambda: (_ for _ in ()).throw(RuntimeError("missing public mcp auth")),
    )
    monkeypatch.setattr(sys, "argv", ["chatgptrest_mcp_server.py", "--transport", "streamable-http"])

    with pytest.raises(SystemExit, match="missing public mcp auth"):
        module.main()


def test_admin_mcp_entrypoint_runs_legacy_server(monkeypatch: pytest.MonkeyPatch) -> None:
    import chatgptrest_admin_mcp_server as module

    seen: dict[str, str] = {}

    def fake_run(*, transport: str) -> None:
        seen["transport"] = transport

    monkeypatch.setattr(module.mcp, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["chatgptrest_admin_mcp_server.py", "--transport", "stdio"])

    module.main()

    assert seen == {"transport": "stdio"}


@pytest.mark.asyncio
async def test_cc_native_chatgptrest_http_override_uses_public_agent_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from chatgptrest.kernel import cc_native as module

    captured: dict[str, object] = {}

    class FakeReadStream:
        pass

    class FakeWriteStream:
        pass

    class FakeClientSession:
        def __init__(self, read_stream, write_stream):
            self.read_stream = read_stream
            self.write_stream = write_stream

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def initialize(self):
            return None

    class FakeStdioContext:
        async def __aenter__(self):
            return FakeReadStream(), FakeWriteStream()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_stdio_client(server_params):
        captured["command"] = server_params.command
        captured["args"] = list(server_params.args)
        return FakeStdioContext()

    monkeypatch.setattr(module, "stdio_client", fake_stdio_client)
    monkeypatch.setattr(module, "ClientSession", FakeClientSession)

    manager = module.McpManager()
    manager._exit_stack = AsyncExitStack()
    try:
        await manager._connect_server("chatgptrest-mcp", {"type": "http", "url": "http://127.0.0.1:18712/mcp"})
    finally:
        await manager.close()

    assert captured["args"][-2:] == ["--transport", "stdio"]
    assert str(captured["args"][0]).endswith("chatgptrest_agent_mcp_server.py")
