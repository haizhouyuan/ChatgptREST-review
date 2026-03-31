from pathlib import Path

from ops.check_public_mcp_client_configs import (
    CHROME_WATCHDOG_PATH,
    PUBLIC_MCP_URL,
    extract_chatgptrest_block,
    inspect_chrome_watchdog_contract,
    inspect_antigravity_config,
    inspect_claude_config,
    inspect_config,
    inspect_json_http_mcp,
    inspect_skill_wrapper,
    repair_antigravity_config,
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


def test_inspect_antigravity_config_flags_legacy_server_url_field(tmp_path: Path) -> None:
    config = tmp_path / "mcp_config.json"
    config.write_text(
        """
{
  "mcpServers": {
    "chatgptrest": {
      "serverURL": "http://127.0.0.1:18712/mcp"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    result = inspect_antigravity_config(config)
    assert result["ok"] is False
    assert result["reason"] == "legacy_serverURL_field"
    assert result["uses_legacy_public_url"] is True


def test_repair_antigravity_config_normalizes_legacy_server_url(tmp_path: Path) -> None:
    config = tmp_path / "mcp_config.json"
    config.write_text(
        """
{
  "mcpServers": {
    "chatgptrest": {
      "serverURL": "http://127.0.0.1:18712/mcp"
    },
    "other": {
      "type": "stdio",
      "command": "echo"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    repair = repair_antigravity_config(config)
    assert repair["ok"] is True
    assert repair["changed"] is True
    assert repair["backup_path"]

    result = inspect_antigravity_config(config)
    assert result["ok"] is True
    assert result["reason"] == "ok"


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
                'DEFAULT_MAINT_LEGACY_CLIENT_NAME = "chatgptrestctl-maint"',
                'PARSER_HELP = ["--workspace-request-json", "--workspace-request-file", "--maintenance-legacy-jobs"]',
                "",
                "def _run_agent_turn():",
                '    result = _run_mcp_tool(mcp_url=DEFAULT_PUBLIC_MCP_URL, tool_name="advisor_agent_turn", arguments={}, timeout_seconds=30.0)',
                "    return result",
                "",
                "def _run_legacy_jobs():",
                "    if not args.maintenance_legacy_jobs:",
                '        raise RuntimeError("legacy mode is maintenance-only")',
                '    env = {"CHATGPTREST_CLIENT_NAME": DEFAULT_MAINT_LEGACY_CLIENT_NAME}',
                "    return env",
            ]
        ),
        encoding="utf-8",
    )
    result = inspect_skill_wrapper(wrapper)
    assert result["ok"] is True
    assert result["reason"] == "ok"
    assert result["supports_workspace_request"] is True
    assert result["requires_maintenance_legacy_gate"] is True
    assert result["uses_maintenance_client_name"] is True


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


def test_inspect_skill_wrapper_rejects_legacy_jobs_without_maintenance_gate(tmp_path: Path) -> None:
    wrapper = tmp_path / "chatgptrest_call.py"
    wrapper.write_text(
        "\n".join(
            [
                'DEFAULT_PUBLIC_MCP_URL = "http://127.0.0.1:18712/mcp"',
                'DEFAULT_MAINT_LEGACY_CLIENT_NAME = "chatgptrestctl-maint"',
                'PARSER_HELP = ["--workspace-request-json", "--workspace-request-file"]',
                "",
                "def _run_agent_turn():",
                '    result = _run_mcp_tool(mcp_url=DEFAULT_PUBLIC_MCP_URL, tool_name="advisor_agent_turn", arguments={}, timeout_seconds=30.0)',
                "    return result",
                "",
                "def _run_legacy_jobs():",
                '    env = {"CHATGPTREST_CLIENT_NAME": DEFAULT_MAINT_LEGACY_CLIENT_NAME}',
                "    return env",
            ]
        ),
        encoding="utf-8",
    )
    result = inspect_skill_wrapper(wrapper)
    assert result["ok"] is False
    assert result["reason"] == "legacy_jobs_not_maintenance_gated"


def test_inspect_skill_wrapper_rejects_missing_maintenance_client(tmp_path: Path) -> None:
    wrapper = tmp_path / "chatgptrest_call.py"
    wrapper.write_text(
        "\n".join(
            [
                'DEFAULT_PUBLIC_MCP_URL = "http://127.0.0.1:18712/mcp"',
                'PARSER_HELP = ["--workspace-request-json", "--workspace-request-file", "--maintenance-legacy-jobs"]',
                "",
                "def _run_agent_turn():",
                '    result = _run_mcp_tool(mcp_url=DEFAULT_PUBLIC_MCP_URL, tool_name="advisor_agent_turn", arguments={}, timeout_seconds=30.0)',
                "    return result",
                "",
                "def _run_legacy_jobs():",
                "    if not args.maintenance_legacy_jobs:",
                '        raise RuntimeError("legacy mode is maintenance-only")',
                "    return {}",
            ]
        ),
        encoding="utf-8",
    )
    result = inspect_skill_wrapper(wrapper)
    assert result["ok"] is False
    assert result["reason"] == "legacy_jobs_missing_maintenance_client"


def test_inspect_chrome_watchdog_contract_accepts_rest_api_port(tmp_path: Path) -> None:
    script = tmp_path / CHROME_WATCHDOG_PATH.name
    script.write_text(
        "\n".join(
            [
                'API_PORT="${CHATGPTREST_API_PORT:-18711}"',
                'timeout 3 curl -sS -X POST "http://127.0.0.1:${API_PORT}/v1/issues/report" \\',
            ]
        ),
        encoding="utf-8",
    )
    result = inspect_chrome_watchdog_contract(script)
    assert result["ok"] is True
    assert result["reason"] == "ok"


def test_inspect_chrome_watchdog_contract_rejects_mcp_port_default(tmp_path: Path) -> None:
    script = tmp_path / CHROME_WATCHDOG_PATH.name
    script.write_text(
        "\n".join(
            [
                'API_PORT="${CHATGPTREST_API_PORT:-18712}"',
                'timeout 3 curl -sS -X POST "http://127.0.0.1:${API_PORT}/v1/issues/report" \\',
            ]
        ),
        encoding="utf-8",
    )
    result = inspect_chrome_watchdog_contract(script)
    assert result["ok"] is False
    assert result["reason"] == "wrong_default_api_port"
