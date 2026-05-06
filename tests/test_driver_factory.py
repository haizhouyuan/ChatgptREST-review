from __future__ import annotations

from chatgptrest.driver.factory import build_tool_caller, normalize_driver_mode
from chatgptrest.driver.backends.mcp_http import McpHttpToolCaller


def test_normalize_driver_mode_defaults() -> None:
    assert normalize_driver_mode(None) == "external_mcp"
    assert normalize_driver_mode("") == "external_mcp"
    assert normalize_driver_mode("internal") == "internal_mcp"
    assert normalize_driver_mode("mcp") == "external_mcp"


def test_build_tool_caller_mcp() -> None:
    caller = build_tool_caller(
        mode="external_mcp",
        url="http://127.0.0.1:18701/mcp",
        client_name="test",
        client_version="0.1.0",
    )
    assert isinstance(caller, McpHttpToolCaller)
