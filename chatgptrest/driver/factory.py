from __future__ import annotations

from chatgptrest.driver.api import ToolCaller
from chatgptrest.driver.backends.embedded import EmbeddedToolCaller
from chatgptrest.driver.backends.mcp_http import McpHttpToolCaller


def normalize_driver_mode(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"internal_mcp", "embedded", "external_mcp"}:
        return raw
    if raw in {"mcp", "external"}:
        return "external_mcp"
    if raw in {"internal"}:
        return "internal_mcp"
    return "external_mcp"


def build_tool_caller(
    *,
    mode: str,
    url: str | None,
    client_name: str,
    client_version: str,
) -> ToolCaller:
    normalized = normalize_driver_mode(mode)
    if normalized == "embedded":
        return EmbeddedToolCaller()
    if not url or not str(url).strip():
        raise ValueError("driver URL is required for MCP modes")
    return McpHttpToolCaller(url=str(url).strip(), client_name=client_name, client_version=client_version)
