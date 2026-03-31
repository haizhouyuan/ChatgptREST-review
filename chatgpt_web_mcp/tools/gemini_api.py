from __future__ import annotations

from chatgpt_web_mcp.mcp_registry import mcp
from chatgpt_web_mcp.providers import gemini_api as _impl


gemini_ask_pro_thinking = mcp.tool(
    name="gemini_ask_pro_thinking",
    description=(
        "Ask Gemini with a Pro model and enable thinking (via generationConfig.thinkingConfig).\n"
        "Requires GEMINI_API_KEY (or GOOGLE_API_KEY)."
    ),
    structured_output=True,
)(_impl.gemini_ask_pro_thinking)


gemini_generate_image = mcp.tool(
    name="gemini_generate_image",
    description=(
        "Generate an image using Gemini image models (e.g. gemini-2.5-flash-image).\n"
        "Saves returned inline images to GEMINI_OUTPUT_DIR (default: artifacts).\n"
        "Requires GEMINI_API_KEY (or GOOGLE_API_KEY)."
    ),
    structured_output=True,
)(_impl.gemini_generate_image)


gemini_deep_research = mcp.tool(
    name="gemini_deep_research",
    description=(
        "Run Gemini Deep Research via the Interactions API.\n"
        "If question is provided, starts a new interaction; otherwise polls an existing interaction_id.\n"
        "Requires GEMINI_API_KEY (or GOOGLE_API_KEY)."
    ),
    structured_output=True,
)(_impl.gemini_deep_research)
