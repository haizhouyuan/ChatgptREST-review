from __future__ import annotations

from chatgpt_web_mcp.mcp_registry import mcp
from chatgpt_web_mcp.providers import gemini_web as _impl


gemini_web_ask = mcp.tool(
    name="gemini_web_ask",
    description="Ask Gemini web without forcing any mode/tool (requires logged-in Chrome via CDP).",
    structured_output=True,
)(_impl.gemini_web_ask)


gemini_web_self_check = mcp.tool(
    name="gemini_web_self_check",
    description="Probe Gemini web UI state (mode + tools) WITHOUT sending any prompts (requires logged-in Chrome via CDP).",
    structured_output=True,
)(_impl.gemini_web_self_check)


gemini_web_capture_ui = mcp.tool(
    name="gemini_web_capture_ui",
    description="Open Gemini Web and capture screenshots of common UI surfaces (for debugging selector breakage).",
    structured_output=True,
)(_impl.gemini_web_capture_ui)


gemini_web_ask_pro = mcp.tool(
    name="gemini_web_ask_pro",
    description="Ask Gemini web with Pro mode enabled (requires logged-in Chrome via CDP).",
    structured_output=True,
)(_impl.gemini_web_ask_pro)


gemini_web_ask_pro_thinking = mcp.tool(
    name="gemini_web_ask_pro_thinking",
    description="Ask Gemini web with Thinking mode enabled (requires logged-in Chrome via CDP).",
    structured_output=True,
)(_impl.gemini_web_ask_pro_thinking)


gemini_web_ask_pro_deep_think = mcp.tool(
    name="gemini_web_ask_pro_deep_think",
    description="Ask Gemini web with Pro + Deep Think enabled (requires logged-in Chrome via CDP).",
    structured_output=True,
)(_impl.gemini_web_ask_pro_deep_think)


gemini_web_generate_image = mcp.tool(
    name="gemini_web_generate_image",
    description="Generate an image via Gemini web UI (Tools → 生成图片) and save it locally.",
    structured_output=True,
)(_impl.gemini_web_generate_image)


gemini_web_deep_research = mcp.tool(
    name="gemini_web_deep_research",
    description=(
        "Start Gemini Deep Research via web UI (Tools → Deep Research). "
        "May return follow-up questions or an in-progress status."
    ),
    structured_output=True,
)(_impl.gemini_web_deep_research)


gemini_web_deep_research_export_gdoc = mcp.tool(
    name="gemini_web_deep_research_export_gdoc",
    description=(
        "Deep Research fallback: open Share/Export in Gemini UI, export to Google Doc, "
        "and optionally fetch the document text."
    ),
    structured_output=True,
)(_impl.gemini_web_deep_research_export_gdoc)


gemini_web_wait = mcp.tool(
    name="gemini_web_wait",
    description="Wait for the latest Gemini web response WITHOUT sending a new prompt.",
    structured_output=True,
)(_impl.gemini_web_wait)


gemini_web_extract_answer = mcp.tool(
    name="gemini_web_extract_answer",
    description=(
        "Open an existing Gemini conversation URL (e.g. https://gemini.google.com/app/xxx) "
        "and extract the last model response as markdown. Read-only — no question is sent."
    ),
    structured_output=True,
)(_impl.gemini_web_extract_answer)


gemini_web_idempotency_get = mcp.tool(
    name="gemini_web_idempotency_get",
    description=(
        "Fetch the cached status/conversation_url for a previous Gemini ask/deep-research call by idempotency_key, "
        "without sending a prompt. Read-only."
    ),
    structured_output=True,
)(_impl.gemini_web_idempotency_get)
