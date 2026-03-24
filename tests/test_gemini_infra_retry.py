from __future__ import annotations

import pytest

from chatgpt_web_mcp import _tools_impl as mcp_server


def test_looks_like_gemini_infra_error_detects_common_failures() -> None:
    assert mcp_server._looks_like_gemini_infra_error("'NoneType' object has no attribute 'contexts'")
    assert mcp_server._looks_like_gemini_infra_error("CDP connect failed")
    assert mcp_server._looks_like_gemini_infra_error("Page.goto: net::ERR_CONNECTION_CLOSED")

    assert not mcp_server._looks_like_gemini_infra_error("Gemini mode selector not found")


def test_gemini_infra_retry_after_seconds_clamps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_INFRA_RETRY_AFTER_SECONDS", "42")
    assert mcp_server._gemini_infra_retry_after_seconds() == 42

    monkeypatch.setenv("CHATGPTREST_INFRA_RETRY_AFTER_SECONDS", "1")
    assert mcp_server._gemini_infra_retry_after_seconds() == 15

    monkeypatch.setenv("CHATGPTREST_INFRA_RETRY_AFTER_SECONDS", "999999")
    assert mcp_server._gemini_infra_retry_after_seconds() == 3600
