from __future__ import annotations

import pytest

from chatgpt_web_mcp.server import (
    _classify_deep_research_answer,
    _classify_non_deep_research_answer,
    _deep_research_auto_followup_prompt,
)


@pytest.mark.parametrize(
    "text",
    [
        "我将立即开展研究，报告准备好后稍后请查收。",
        "报告准备好后我会发给你，请稍等。",
        "请耐心等待，报告完成后我会发送给你。",
        "我将为你深入研究，研究完成后我会向你汇报。",
        "研究完成后将一次性输出所有内容，包括合规性检查、证据链表、催化日历、风险清单与最终判断框架。期间你可以随时继续和我交流。",
        "I'll start researching now and get back to you when the report is ready.",
    ],
)
def test_deep_research_ack_is_in_progress(text: str) -> None:
    assert _classify_deep_research_answer(text) == "in_progress"


@pytest.mark.parametrize(
    "text",
    [
        "如果没问题请回复 OK，我就开始研究。",
        "Reply with OK before I begin.",
        "请确认：回复 OK 后我将开始深度研究。",
    ],
)
def test_deep_research_confirm_is_needs_followup(text: str) -> None:
    assert _classify_deep_research_answer(text) == "needs_followup"


def test_gemini_deep_research_plan_stub_is_needs_followup() -> None:
    text = """我拟定了一个研究方案。如果你要进行任何更新，请告诉我。
儿童行为案例概念化与干预设计
更多
分析结果
生成报告
只需要几分钟就可以准备好
修改方案
开始研究
不使用 Deep Research，再试一次"""
    assert _classify_deep_research_answer(text) == "needs_followup"


def test_deep_research_long_report_is_completed() -> None:
    text = "这是研究报告正文。" + ("a" * 2000)
    assert _classify_deep_research_answer(text) == "completed"


def test_non_deep_research_answer_does_not_emit_needs_followup() -> None:
    text = "我已经整理完初稿，你是否希望我再补一版对比表？"
    assert _classify_deep_research_answer(text) == "needs_followup"
    assert _classify_non_deep_research_answer(text) == "completed"


def test_non_deep_research_empty_answer_is_in_progress() -> None:
    assert _classify_non_deep_research_answer("  ") == "in_progress"


def test_deep_research_auto_followup_prompt_is_safe_and_actionable() -> None:
    prompt = _deep_research_auto_followup_prompt("any")
    assert prompt.startswith("OK")
    assert "不要再反问" in prompt
