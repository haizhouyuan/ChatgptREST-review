from __future__ import annotations

import chatgptrest.mcp.agent_mcp as agent_mcp
import chatgptrest.mcp.server as admin_mcp_server


def test_public_agent_mcp_does_not_expose_retired_agent_tools() -> None:
    names = {tool.name for tool in agent_mcp.mcp._tool_manager.list_tools()}
    assert 'advisor_agent_turn' not in names
    assert 'advisor_agent_status' not in names
    assert 'advisor_agent_cancel' not in names
    assert 'advisor_agent_wait' not in names
    assert 'advisor_agent_answer' not in names
    assert 'coding_agent_turn' not in names
    assert 'coding_agent_status' not in names
    assert 'coding_agent_cancel' not in names
    assert 'coding_agent_wait' not in names
    assert 'coding_agent_answer' not in names


def test_public_agent_mcp_exposes_manual_conversation_harvest_tools() -> None:
    names = {tool.name for tool in agent_mcp.mcp._tool_manager.list_tools()}
    assert "automation_conversation_fetch" in names
    assert "automation_conversation_get" in names
    assert "automation_conversation_find" in names


def test_admin_mcp_does_not_expose_retired_agent_tools() -> None:
    names = {tool.name for tool in admin_mcp_server.mcp._tool_manager.list_tools()}
    assert 'advisor_agent_turn' not in names
    assert 'advisor_agent_status' not in names
    assert 'advisor_agent_cancel' not in names
