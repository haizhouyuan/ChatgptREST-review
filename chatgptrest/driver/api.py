from __future__ import annotations

from typing import Any, Dict, Protocol


class ToolCallError(RuntimeError):
    """Raised when a driver backend cannot complete a tool call."""


class ToolCaller(Protocol):
    def call_tool(
        self,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
        timeout_sec: float = 600.0,
    ) -> Dict[str, Any]:
        """Invoke a ChatGPT web tool and return structured content."""
        raise NotImplementedError
