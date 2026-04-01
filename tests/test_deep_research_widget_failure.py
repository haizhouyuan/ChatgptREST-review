from __future__ import annotations

import pytest

from chatgpt_web_mcp.server import _deep_research_widget_failure_reason


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Research failed", "Research failed"),
        ("研究失败，请重试", "研究失败，请重试"),
        ("Something went wrong. Try again.", "Something went wrong. Try again."),
        ("Please try again", "Please try again"),
    ],
)
def test_deep_research_widget_failure_reason_detects_banner(text: str, expected: str) -> None:
    assert _deep_research_widget_failure_reason(text) == expected


def test_deep_research_widget_failure_reason_ignores_long_reports() -> None:
    text = ("# Report\n\n" + ("a" * 1000) + "\nResearch failed\n" + ("b" * 1000))
    assert _deep_research_widget_failure_reason(text) is None


@pytest.mark.parametrize("text", ["", "OK", "All good", "## Sources\n- https://example.com"])
def test_deep_research_widget_failure_reason_ignores_normal_text(text: str) -> None:
    assert _deep_research_widget_failure_reason(text) is None
