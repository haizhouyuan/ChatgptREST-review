"""ChatgptREST embedded driver MCP server entrypoint.

`chatgpt_web_mcp._tools_impl` contains the Playwright automation and tool
implementations. This module:

- constructs the real `FastMCP` server instance
- registers tools captured by the implementation module
- provides the `mcp.run(...)` entrypoint

Keeping the entrypoint thin makes large refactors safer and keeps tool
registration reviewable.
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from chatgpt_web_mcp import _tools_impl as _impl


def _fastmcp_host_port() -> tuple[str, int]:
    host = os.environ.get("FASTMCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port_raw = os.environ.get("FASTMCP_PORT", "").strip()
    if port_raw:
        try:
            port = int(port_raw)
        except ValueError:
            port = 8000
    else:
        port = 8000
    return host, port


_FASTMCP_HOST, _FASTMCP_PORT = _fastmcp_host_port()


def _fastmcp_stateless_http_default() -> bool:
    raw = os.environ.get("FASTMCP_STATELESS_HTTP", "").strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    # Default to stateless StreamableHTTP so clients can survive server restarts without
    # re-initializing a session (many MCP clients cache session IDs).
    return True


mcp = FastMCP(
    name="chatgpt-web-mcp",
    instructions=(
        "Ask ChatGPT via the official web UI.\n"
        "- Option A: set CHATGPT_CDP_URL to connect to a running Google Chrome (recommended for Cloudflare).\n"
        "- Option B: set CHATGPT_STORAGE_STATE to use Playwright-managed Chromium with storage_state.json.\n"
        "\n"
        "Also exposes Gemini tools:\n"
        "- gemini_web.* uses the Gemini web UI (best with GEMINI_CDP_URL/CHATGPT_CDP_URL + logged-in Chrome).\n"
        "- gemini.* uses the official Gemini API (requires GEMINI_API_KEY or GOOGLE_API_KEY).\n"
        "\n"
        "Also exposes Qwen tools:\n"
        "- qwen_web.* uses the Qwen web UI (recommended: QWEN_CDP_URL=http://127.0.0.1:9335, no proxy)."
    ),
    host=_FASTMCP_HOST,
    port=_FASTMCP_PORT,
    stateless_http=_fastmcp_stateless_http_default(),
)


def _register_tools() -> None:
    tools = getattr(_impl, "_iter_mcp_tools", None)
    if not callable(tools):
        raise RuntimeError("chatgpt_web_mcp._tools_impl is missing _iter_mcp_tools()")

    seen_names: set[str] = set()
    for meta, fn in tools():
        if not isinstance(meta, dict):
            raise TypeError(f"Unexpected tool metadata type: {type(meta).__name__}")
        if not callable(fn):
            raise TypeError(f"Unexpected tool function type: {type(fn).__name__}")
        name = str(meta.get("name") or "").strip()
        if name:
            if name in seen_names:
                raise RuntimeError(f"Duplicate MCP tool name: {name}")
            seen_names.add(name)
        mcp.tool(**meta)(fn)


_register_tools()


# Explicit re-export for entrypoints.
_acquire_server_singleton_lock_or_die = _impl._acquire_server_singleton_lock_or_die


def __getattr__(name: str) -> Any:  # pragma: no cover - thin re-export shim
    return getattr(_impl, name)


def main() -> None:
    parser = argparse.ArgumentParser(description="ChatGPT Web MCP server (Playwright).")
    parser.add_argument(
        "--transport",
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        choices=["stdio", "sse", "streamable-http"],
        help="MCP transport to use.",
    )
    args = parser.parse_args()
    _acquire_server_singleton_lock_or_die(transport=str(args.transport))
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
