from pathlib import Path

from ops.check_public_mcp_client_configs import (
    PUBLIC_MCP_URL,
    extract_chatgptrest_block,
    inspect_antigravity_config,
    inspect_claude_config,
    inspect_config,
    inspect_json_http_mcp,
    inspect_skill_wrapper,
)


def test_extract_chatgptrest_block_stops_at_next_table() -> None:
    text = """
[mcp_servers.chatgptrest]
enabled = true
url = "http://127.0.0.1:18712/mcp"

[tui]
status_line = ["session-id"]
"""
    block = extract_chatgptrest_block(text)
    assert "[mcp_servers.chatgptrest]" in block
    assert "[tui]" not in block


def test_inspect_config_accepts_public_mcp_url(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        "\n".join(
            [
                "[mcp_servers.chatgptrest]",
                "enabled = true",
                f'url = "{PUBLIC_MCP_URL}"',
                "startup_timeout_sec = 30.0",
            ]
        )
    )
    result = inspect_config(config)
    assert result["ok"] is True
    assert result["reason"] == "ok"


def test_inspect_config_rejects_local_stdio_server(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        "\n".join(
            [
                "[mcp_servers.chatgptrest]",
                "enabled = true",
                'command = "/vol1/1000/projects/ChatgptREST/.venv/bin/python"',
                'args = ["/vol1/1000/projects/ChatgptREST/chatgptrest_agent_mcp_server.py", "--transport", "stdio"]',
            ]
        )
    )
    result = inspect_config(config)
    assert result["ok"] is False
    assert result["reason"] == "uses_local_stdio_server"


def test_inspect_claude_config_accepts_public_mcp_url(tmp_path: Path) -> None:
    config = tmp_path / ".claude.json"
    config.write_text(
        """
{
  "mcpServers": {
    "chatgptrest-mcp": {
      "type": "http",
      "url": "http://127.0.0.1:18712/mcp"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    result = inspect_claude_config(config)
    assert result["ok"] is True
    assert result["reason"] == "ok"
    assert result["server_name"] == "chatgptrest-mcp"


def test_inspect_antigravity_config_rejects_wrong_transport(tmp_path: Path) -> None:
    config = tmp_path / "mcp_config.json"
    config.write_text(
        """
{
  "mcpServers": {
    "chatgptrest": {
      "type": "stdio",
      "command": "/vol1/1000/projects/ChatgptREST/.venv/bin/python",
      "args": ["/vol1/1000/projects/ChatgptREST/chatgptrest_agent_mcp_server.py", "--transport", "stdio"]
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    result = inspect_antigravity_config(config)
    assert result["ok"] is False
    assert result["reason"] == "uses_local_stdio_server"


def test_inspect_json_http_mcp_rejects_missing_server(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text('{"mcpServers": {"other": {"type": "http", "url": "http://127.0.0.1:18712/mcp"}}}', encoding="utf-8")
    result = inspect_json_http_mcp(config, server_names=("chatgptrest",))
    assert result["ok"] is False
    assert result["reason"] == "missing_chatgptrest_server"


def test_inspect_skill_wrapper_accepts_public_mcp_agent_mode(tmp_path: Path) -> None:
    wrapper = tmp_path / "chatgptrest_call.py"
    wrapper.write_text(
        "\n".join(
            [
                'DEFAULT_PUBLIC_MCP_URL = "http://127.0.0.1:18712/mcp"',
                'PARSER_HELP = ["--workspace-request-json", "--workspace-request-file"]',
                "",
                "def _run_agent_turn():",
                '    result = _run_mcp_tool(mcp_url=DEFAULT_PUBLIC_MCP_URL, tool_name="advisor_agent_turn", arguments={}, timeout_seconds=30.0)',
                "    return result",
                "",
                "def _run_legacy_jobs():",
                "    pass",
            ]
        ),
        encoding="utf-8",
    )
    result = inspect_skill_wrapper(wrapper)
    assert result["ok"] is True
    assert result["reason"] == "ok"
    assert result["supports_workspace_request"] is True


def test_inspect_skill_wrapper_rejects_agent_rest_cli_path(tmp_path: Path) -> None:
    wrapper = tmp_path / "chatgptrest_call.py"
    wrapper.write_text(
        "\n".join(
            [
                'DEFAULT_PUBLIC_MCP_URL = "http://127.0.0.1:18712/mcp"',
                "",
                "def _run_agent_turn():",
                "    cmd.extend([\"agent\", \"turn\"])",
                "    return cmd",
                "",
                "def _run_legacy_jobs():",
                "    pass",
            ]
        ),
        encoding="utf-8",
    )
    result = inspect_skill_wrapper(wrapper)
    assert result["ok"] is False
    assert result["reason"] == "agent_mode_not_using_public_mcp"


def test_inspect_skill_wrapper_rejects_missing_workspace_support(tmp_path: Path) -> None:
    wrapper = tmp_path / "chatgptrest_call.py"
    wrapper.write_text(
        "\n".join(
            [
                'DEFAULT_PUBLIC_MCP_URL = "http://127.0.0.1:18712/mcp"',
                "",
                "def _run_agent_turn():",
                '    result = _run_mcp_tool(mcp_url=DEFAULT_PUBLIC_MCP_URL, tool_name="advisor_agent_turn", arguments={}, timeout_seconds=30.0)',
                "    return result",
                "",
                "def _run_legacy_jobs():",
                "    pass",
            ]
        ),
        encoding="utf-8",
    )
    result = inspect_skill_wrapper(wrapper)
    assert result["ok"] is False
    assert result["reason"] == "missing_workspace_request_support"
