from __future__ import annotations

import inspect

from chatgpt_web_mcp import _tools_impl
from chatgpt_web_mcp.providers.gemini.wait import gemini_web_wait


def test_gemini_wait_signature_keeps_deep_research_compat_param() -> None:
    sig = inspect.signature(gemini_web_wait)
    assert "deep_research" in sig.parameters
    p = sig.parameters["deep_research"]
    assert p.default is None


def test_mcp_registry_exposes_deep_research_on_gemini_web_wait() -> None:
    for meta, fn in _tools_impl._iter_mcp_tools():
        name = str((meta.get("name") or fn.__name__) or "").strip()
        if name != "gemini_web_wait":
            continue
        sig = inspect.signature(fn)
        assert "deep_research" in sig.parameters
        return
    raise AssertionError("gemini_web_wait not found in MCP tool registry")
