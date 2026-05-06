from __future__ import annotations

import asyncio

import pytest

from chatgptrest.executors import gemini_web_mcp as gemini
from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor


def test_gemini_strip_ui_noise_prefix_removes_transcript_prefix() -> None:
    raw = (
        "调研报告\n"
        "設定和幫助\n"
        "與Gemini 對話\n"
        "你说\n"
        "显示思路\n"
        "Gemini 说\n"
        "\n"
        "作为 OpenClaw 的架构顾问，这是研究正文。"
    )
    cleaned, info = gemini._gemini_strip_ui_noise_prefix(raw)
    assert cleaned.startswith("作为 OpenClaw 的架构顾问")
    assert info.get("ui_noise_detected") is True
    assert info.get("ui_noise_sanitized") is True
    assert int(info.get("ui_noise_prefix_lines") or 0) >= 4


def test_gemini_strip_ui_noise_prefix_marks_anchor_only_as_empty() -> None:
    cleaned, info = gemini._gemini_strip_ui_noise_prefix("Gemini 说\n")
    assert cleaned == ""
    assert info.get("ui_noise_detected") is True
    assert info.get("ui_noise_empty_after_sanitize") is True


def test_gemini_semantic_risk_next_owner_mixed_detects_conflict() -> None:
    text = (
        "State 4: Handoff (owner: reqmgr -> next_owner: PM)\n"
        '{"acceptance_criteria":{"owner":"reqmgr","next_owner":"reqmgr"}}\n'
    )
    assert gemini._gemini_semantic_risk_next_owner_mixed(text) is True


def test_executor_sanitizes_gemini_ui_noise_answer() -> None:
    noisy_answer = (
        "调研报告\n設定和幫助\n與Gemini 對話\n你说\n显示思路\nGemini 说\n\n"
        "作为 OpenClaw 的架构顾问，我将给出可执行方案。"
    )

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            assert tool_name == "gemini_web_ask_pro_deep_think"
            return {
                "status": "completed",
                "answer": noisy_answer,
                "conversation_url": "https://gemini.google.com/app/abc",
            }

    ex = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-quality-sanitize",
            kind="gemini_web.ask",
            input={"question": "x"},
            params={"preset": "deep_think", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "completed"
    assert res.answer.startswith("作为 OpenClaw 的架构顾问")
    assert isinstance(res.meta, dict)
    guard = (res.meta or {}).get("answer_quality_guard")
    assert isinstance(guard, dict)
    assert guard.get("ui_noise_sanitized") is True


def test_executor_semantic_strict_mode_downgrades_to_needs_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_GEMINI_SEMANTIC_CONSISTENCY_GUARD", "1")
    conflict_answer = (
        "State 4: Handoff (owner: reqmgr -> next_owner: PM)\n"
        '{"acceptance_criteria":{"owner":"reqmgr","next_owner":"reqmgr"}}\n'
        "正文补充内容。"
    )

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            assert tool_name == "gemini_web_ask_pro_deep_think"
            return {
                "status": "completed",
                "answer": conflict_answer,
                "conversation_url": "https://gemini.google.com/app/xyz",
            }

    ex = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-semantic-strict",
            kind="gemini_web.ask",
            input={"question": "x"},
            params={"preset": "deep_think", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "needs_followup"
    assert isinstance(res.meta, dict)
    assert (res.meta or {}).get("error_type") == "GeminiAnswerSemanticConflict"
    guard = (res.meta or {}).get("answer_quality_guard")
    assert isinstance(guard, dict)
    assert guard.get("semantic_risk_next_owner_mixed") is True


def test_executor_downgrades_anchor_only_gemini_answer_to_needs_followup() -> None:
    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            assert tool_name == "gemini_web_ask_pro"
            return {
                "status": "completed",
                "answer": "Gemini 说\n",
                "conversation_url": "https://gemini.google.com/app/anchoronly",
            }

    ex = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-anchor-only",
            kind="gemini_web.ask",
            input={"question": "x"},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "needs_followup"
    assert res.answer == ""
    assert isinstance(res.meta, dict)
    assert (res.meta or {}).get("error_type") == "GeminiAnswerContaminated"
    guard = (res.meta or {}).get("answer_quality_guard")
    assert isinstance(guard, dict)
    assert guard.get("ui_noise_empty_after_sanitize") is True


def test_executor_recovers_contaminated_gemini_answer_via_extract_answer() -> None:
    class _DummyToolCaller:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            self.calls.append(tool_name)
            if tool_name == "gemini_web_ask_pro":
                return {
                    "status": "completed",
                    "answer": "Gemini 说\n",
                    "conversation_url": "https://gemini.google.com/app/recover123",
                }
            if tool_name == "gemini_web_extract_answer":
                assert tool_args["conversation_url"].endswith("/recover123")
                return {
                    "ok": True,
                    "status": "completed",
                    "answer": "这是提取后的正文答案。",
                    "conversation_url": "https://gemini.google.com/app/recover123",
                }
            raise AssertionError(f"unexpected tool: {tool_name}")

    dummy = _DummyToolCaller()
    ex = GeminiWebMcpExecutor(tool_caller=dummy)  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-quality-recover",
            kind="gemini_web.ask",
            input={"question": "x"},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "completed"
    assert res.answer == "这是提取后的正文答案。"
    assert dummy.calls == ["gemini_web_ask_pro", "gemini_web_extract_answer"]
    recovery = (res.meta or {}).get("answer_quality_recovery")
    assert isinstance(recovery, dict)
    assert recovery.get("recovered") is True


def test_executor_keeps_needs_followup_when_extract_answer_still_contaminated() -> None:
    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            if tool_name == "gemini_web_ask_pro":
                return {
                    "status": "completed",
                    "answer": "Gemini 说\n",
                    "conversation_url": "https://gemini.google.com/app/recover456",
                }
            if tool_name == "gemini_web_extract_answer":
                return {
                    "ok": True,
                    "status": "completed",
                    "answer": "Gemini 说\n",
                    "conversation_url": "https://gemini.google.com/app/recover456",
                }
            raise AssertionError(f"unexpected tool: {tool_name}")

    ex = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        ex.run(
            job_id="job-gemini-quality-recover-fail",
            kind="gemini_web.ask",
            input={"question": "x"},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )
    assert res.status == "needs_followup"
    recovery = (res.meta or {}).get("answer_quality_recovery")
    assert isinstance(recovery, dict)
    assert recovery.get("recovered") is False
    guard = (res.meta or {}).get("answer_quality_guard")
    assert isinstance(guard, dict)
    assert guard.get("status_override") == "needs_followup"
