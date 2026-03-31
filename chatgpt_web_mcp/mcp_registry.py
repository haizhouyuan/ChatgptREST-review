"""FastMCP tool registry shim.

Tool implementations live in other modules and decorate functions with `@mcp.tool(...)`.
We capture the tool metadata here so the real FastMCP server (constructed in
`chatgpt_web_mcp.server`) can register tools after imports are complete.

This keeps `chatgpt_web_mcp.server` thin and makes large refactors safer.
"""

from __future__ import annotations

from typing import Any, Callable

_MCP_TOOL_REGISTRY: list[tuple[dict[str, Any], Callable[..., Any]]] = []


class ToolRegistry:
    def tool(self, *args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if args:
            raise TypeError("mcp.tool registry shim only supports keyword arguments")

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            meta = dict(kwargs)
            setattr(fn, "__mcp_tool_meta__", meta)
            _MCP_TOOL_REGISTRY.append((meta, fn))
            return fn

        return decorator


mcp = ToolRegistry()


def iter_mcp_tools() -> list[tuple[dict[str, Any], Callable[..., Any]]]:
    return list(_MCP_TOOL_REGISTRY)
