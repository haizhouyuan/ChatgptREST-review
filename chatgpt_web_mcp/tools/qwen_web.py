from __future__ import annotations

from chatgpt_web_mcp.mcp_registry import mcp
from chatgpt_web_mcp.providers import qwen_web as _impl


qwen_web_self_check = mcp.tool(
    name="qwen_web_self_check",
    description="Open Qwen and verify the composer UI without sending a prompt (health check).",
    structured_output=True,
)(_impl.qwen_web_self_check)


qwen_web_capture_ui = mcp.tool(
    name="qwen_web_capture_ui",
    description=(
        "Open Qwen Web and capture screenshots of common UI surfaces (for debugging selector breakage).\n"
        "Does NOT send any prompt."
    ),
    structured_output=True,
)(_impl.qwen_web_capture_ui)


qwen_web_ask = mcp.tool(
    name="qwen_web_ask",
    description="Ask Qwen web UI (recommended: separate QWEN_CDP_URL profile, no proxy).",
    structured_output=True,
)(_impl.qwen_web_ask)


qwen_web_wait = mcp.tool(
    name="qwen_web_wait",
    description="Wait for the latest Qwen web response without sending a new prompt.",
    structured_output=True,
)(_impl.qwen_web_wait)
