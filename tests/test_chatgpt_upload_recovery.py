from __future__ import annotations

from chatgpt_web_mcp import _tools_impl as driver


def test_transient_playwright_error_matches_page_closed_set_input_files() -> None:
    exc = RuntimeError("Locator.set_input_files: Target page, context or browser has been closed")
    assert driver._looks_like_transient_playwright_error(exc)


def test_upload_page_closed_error_is_recognized() -> None:
    exc = RuntimeError("Locator.set_input_files: Target page, context or browser has been closed")
    assert driver._looks_like_upload_page_closed_error(exc)


def test_upload_non_closed_error_is_not_page_closed_recovery_case() -> None:
    exc = RuntimeError("Upload menu button not found")
    assert not driver._looks_like_upload_page_closed_error(exc)
