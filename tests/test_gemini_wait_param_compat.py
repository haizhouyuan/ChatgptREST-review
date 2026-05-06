from __future__ import annotations

import inspect

from chatgpt_web_mcp import _tools_impl
from chatgpt_web_mcp.providers.gemini.wait import (
    _gemini_expected_wait_thread_url,
    _gemini_wait_thread_guard_result,
    gemini_web_wait,
)


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


def test_gemini_wait_thread_guard_allows_base_to_thread_upgrade() -> None:
    assert (
        _gemini_wait_thread_guard_result(
            requested_conversation_url="https://gemini.google.com/app",
            observed_conversation_url="https://gemini.google.com/app/thread-12345678",
            started_at=100.0,
            run_id="r1",
        )
        is None
    )


def test_gemini_wait_thread_guard_fail_closes_on_different_thread() -> None:
    result = _gemini_wait_thread_guard_result(
        requested_conversation_url="https://gemini.google.com/app/thread-aaaaaaaa",
        observed_conversation_url="https://gemini.google.com/app/thread-bbbbbbbb",
        started_at=100.0,
        run_id="r2",
    )
    assert isinstance(result, dict)
    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["conversation_url"] == "https://gemini.google.com/app/thread-aaaaaaaa"
    assert result["observed_conversation_url"] == "https://gemini.google.com/app/thread-bbbbbbbb"
    assert result["error_type"] == "GeminiConversationThreadMismatch"


def test_gemini_expected_wait_thread_url_prefers_selected_cid_over_observed_thread() -> None:
    expected = _gemini_expected_wait_thread_url(
        requested_conversation_url="https://gemini.google.com/app",
        observed_conversation_url="https://gemini.google.com/app/thread-bbbbbbbb",
        selected_conversation_id="thread-aaaaaaaa",
    )
    assert expected == "https://gemini.google.com/app/thread-aaaaaaaa"


def test_gemini_expected_wait_thread_url_uses_observed_thread_when_no_selected_cid() -> None:
    expected = _gemini_expected_wait_thread_url(
        requested_conversation_url="https://gemini.google.com/app",
        observed_conversation_url="https://gemini.google.com/app/thread-bbbbbbbb",
        selected_conversation_id="",
    )
    assert expected == "https://gemini.google.com/app/thread-bbbbbbbb"
