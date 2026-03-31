from __future__ import annotations

from typing import Any, Dict

from chatgptrest.driver.api import ToolCallError, ToolCaller
from chatgptrest.integrations.mcp_http_client import McpHttpClient, McpHttpError


class McpHttpToolCaller(ToolCaller):
    def __init__(self, *, url: str, client_name: str, client_version: str) -> None:
        self._client = McpHttpClient(url=url, client_name=client_name, client_version=client_version)

    def call_tool(
        self,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
        timeout_sec: float = 600.0,
    ) -> Dict[str, Any]:
        import time
        max_retries = 15
        last_exc = None
        for attempt in range(max_retries):
            try:
                return self._client.call_tool(tool_name=tool_name, tool_args=tool_args, timeout_sec=timeout_sec)
            except McpHttpError as exc:
                err_str = str(exc).lower()
                is_transient = "connection refused" in err_str or "econnrefused" in err_str or "transport error" in err_str
                if is_transient and attempt < max_retries - 1:
                    time.sleep(2.0)
                    continue
                raise ToolCallError(str(exc)) from exc
        raise ToolCallError(str(last_exc))
