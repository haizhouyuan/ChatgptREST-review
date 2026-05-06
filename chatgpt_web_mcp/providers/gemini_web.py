from __future__ import annotations

# Backward-compatible facade for the Gemini Web driver implementation.
#
# The implementation is split into focused modules under `chatgpt_web_mcp.providers.gemini`.
# This module re-exports internal helpers used by tests/ops and the public entrypoints used
# by MCP tools.

from chatgpt_web_mcp.providers.gemini.core import *  # noqa: F403
from chatgpt_web_mcp.providers.gemini.ask import (
    gemini_web_ask,
    gemini_web_ask_pro,
    gemini_web_ask_pro_deep_think,
    gemini_web_ask_pro_thinking,
    gemini_web_idempotency_get,
    gemini_web_extract_answer,
)
from chatgpt_web_mcp.providers.gemini.capture_ui import gemini_web_capture_ui
from chatgpt_web_mcp.providers.gemini.deep_research import gemini_web_deep_research
from chatgpt_web_mcp.providers.gemini.deep_research_export import gemini_web_deep_research_export_gdoc
from chatgpt_web_mcp.providers.gemini.generate_image import gemini_web_generate_image
from chatgpt_web_mcp.providers.gemini.self_check import gemini_web_self_check
from chatgpt_web_mcp.providers.gemini.wait import gemini_web_wait
