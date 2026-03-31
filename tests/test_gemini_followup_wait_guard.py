from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor


def test_gemini_existing_thread_followup_does_not_wait_without_new_response() -> None:
    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            if tool_name == "gemini_web_ask_pro":
                return {
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": "https://gemini.google.com/app/790681f697666eed",
                    "send_without_new_response_start": True,
                    "response_count_before_send": 5,
                    "response_count_after_error": 5,
                    "error_type": "TimeoutError",
                    "error": "Timed out waiting for a new response",
                }
            raise AssertionError(f"unexpected tool call: {tool_name}")

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job-followup-1",
            kind="gemini_web.ask",
            input={
                "question": "continue",
                "conversation_url": "https://gemini.google.com/app/790681f697666eed",
            },
            params={"preset": "pro", "timeout_seconds": 60, "max_wait_seconds": 60, "min_chars": 0},
        )
    )

    assert res.status == "needs_followup"
    assert calls and calls[0]["tool_name"] == "gemini_web_ask_pro"
    assert all(call["tool_name"] != "gemini_web_wait" for call in calls)
    assert isinstance(res.meta, dict)
    assert res.meta.get("error_type") == "GeminiFollowupSendUnconfirmed"
    guard = res.meta.get("followup_wait_guard")
    assert isinstance(guard, dict)
    assert guard.get("activated") is True
    assert guard.get("response_count_before_send") == 5
    assert guard.get("response_count_after_error") == 5


def test_gemini_bare_app_url_does_not_trigger_followup_guard() -> None:
    """Regression: bare /app URL is not a thread URL and must not trigger the
    GeminiFollowupSendUnconfirmed guard.  Without this fix the guard fires on
    any truthy initial_conversation_url, incorrectly blocking fresh asks that
    happen to carry the base /app page URL from a previous navigation."""
    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            if tool_name == "gemini_web_ask_pro":
                return {
                    "status": "in_progress",
                    "answer": "",
                    # Bare /app – NOT a thread URL
                    "conversation_url": "https://gemini.google.com/app",
                    "send_without_new_response_start": True,
                    "response_count_before_send": 0,
                    "response_count_after_error": 0,
                    "error_type": "TimeoutError",
                    "error": "Timed out waiting for a new response",
                }
            if tool_name == "gemini_web_wait":
                return {
                    "status": "completed",
                    "answer": "Here is the full answer." + ("x" * 200),
                    "conversation_url": "https://gemini.google.com/app/abcdef0123456789",
                }
            raise AssertionError(f"unexpected tool call: {tool_name}")

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job-bare-app-1",
            kind="gemini_web.ask",
            input={
                "question": "Analyze this document",
                # Bare /app URL from a prior navigation, not a real thread
                "conversation_url": "https://gemini.google.com/app",
            },
            params={"preset": "pro", "timeout_seconds": 60, "max_wait_seconds": 60, "min_chars": 0},
        )
    )

    # Must NOT get needs_followup / GeminiFollowupSendUnconfirmed  —
    # should proceed normally to wait, then complete.
    assert res.status == "completed"
    assert isinstance(res.meta, dict)
    assert res.meta.get("error_type") != "GeminiFollowupSendUnconfirmed"
    guard = res.meta.get("followup_wait_guard")
    # Guard should NOT have activated
    assert guard is None or guard.get("activated") is not True


def test_gemini_existing_thread_deep_research_followup_auto_confirms_and_waits() -> None:
    calls: list[dict[str, Any]] = []

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            if len(calls) == 1:
                assert tool_name == "gemini_web_deep_research"
                return {
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": "https://gemini.google.com/app/790681f697666eed",
                    "send_without_new_response_start": True,
                    "response_count_before_send": 5,
                    "response_count_after_error": 5,
                    "error_type": "TimeoutError",
                    "error": "Timed out waiting for a new response",
                }
            if len(calls) == 2:
                assert tool_name == "gemini_web_deep_research"
                assert str(tool_args.get("conversation_url") or "").endswith("/790681f697666eed")
                assert str(tool_args.get("question") or "").startswith("OK")
                return {
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": "https://gemini.google.com/app/790681f697666eed",
                }
            if len(calls) == 3:
                assert tool_name == "gemini_web_wait"
                return {
                    "status": "completed",
                    "answer": "这是完整研究报告。" + ("a" * 800),
                    "conversation_url": "https://gemini.google.com/app/790681f697666eed",
                }
            raise AssertionError(f"unexpected tool call: {tool_name}")

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job-followup-dr-1",
            kind="gemini_web.ask",
            input={
                "question": "继续并直接开始研究",
                "conversation_url": "https://gemini.google.com/app/790681f697666eed",
            },
            params={
                "preset": "deep_think",
                "timeout_seconds": 60,
                "max_wait_seconds": 60,
                "min_chars": 100,
                "deep_research": True,
            },
        )
    )

    assert res.status == "completed"
    assert len(calls) == 3
    assert isinstance(res.meta, dict)
    auto = res.meta.get("deep_research_auto_followup")
    assert isinstance(auto, dict)
    assert auto.get("enabled") is True
    assert auto.get("reason") == "send_without_new_response_start"
    assert auto.get("sent") is True
    assert auto.get("post_status") == "completed"


def test_gemini_wait_plan_stub_auto_confirms_once() -> None:
    calls: list[dict[str, Any]] = []
    stub = """这是我针对该主题拟定的方案。如果你需要进行修改，请告诉我。
研究网站
更多
分析结果
生成报告
只需要几分钟就可以准备好
修改方案
开始研究
不使用 Deep Research，再试一次"""

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            if len(calls) == 1:
                assert tool_name == "gemini_web_wait"
                return {
                    "status": "needs_followup",
                    "answer": stub,
                    "conversation_url": "https://gemini.google.com/app/790681f697666eed",
                }
            if len(calls) == 2:
                assert tool_name == "gemini_web_deep_research"
                assert str(tool_args.get("question") or "").startswith("OK")
                return {
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": "https://gemini.google.com/app/790681f697666eed",
                }
            if len(calls) == 3:
                assert tool_name == "gemini_web_wait"
                return {
                    "status": "completed",
                    "answer": "这是完整研究报告。" + ("b" * 900),
                    "conversation_url": "https://gemini.google.com/app/790681f697666eed",
                }
            raise AssertionError(f"unexpected tool call: {tool_name}")

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job-followup-dr-wait",
            kind="gemini_web.ask",
            input={
                "question": "继续",
                "conversation_url": "https://gemini.google.com/app/790681f697666eed",
            },
            params={
                "preset": "deep_think",
                "phase": "wait",
                "timeout_seconds": 60,
                "wait_timeout_seconds": 60,
                "max_wait_seconds": 60,
                "min_chars": 100,
                "deep_research": True,
            },
        )
    )

    assert res.status == "completed"
    assert len(calls) == 3
    assert isinstance(res.meta, dict)
    auto = res.meta.get("deep_research_auto_followup")
    assert isinstance(auto, dict)
    assert auto.get("reason") == "wait_needs_followup"
    assert auto.get("sent") is True


def test_gemini_send_plan_stub_auto_confirms_once() -> None:
    calls: list[dict[str, Any]] = []
    stub = """这是该主题的研究方案。如果你需要进行更新，请告诉我。
研究网站
更多
分析结果
生成报告
只需要几分钟就可以准备好
修改方案
开始研究
不使用 Deep Research，再试一次"""

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            calls.append({"tool_name": tool_name, "tool_args": dict(tool_args)})
            if len(calls) == 1:
                assert tool_name == "gemini_web_deep_research"
                return {
                    "status": "needs_followup",
                    "answer": stub,
                    "conversation_url": "https://gemini.google.com/app/89abcdef01234567",
                }
            if len(calls) == 2:
                assert tool_name == "gemini_web_deep_research"
                assert str(tool_args.get("conversation_url") or "").endswith("/89abcdef01234567")
                assert str(tool_args.get("question") or "").startswith("OK")
                return {
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": "https://gemini.google.com/app/89abcdef01234567",
                }
            if len(calls) == 3:
                assert tool_name == "gemini_web_wait"
                return {
                    "status": "completed",
                    "answer": "这是完整研究报告。" + ("c" * 900),
                    "conversation_url": "https://gemini.google.com/app/89abcdef01234567",
                }
            raise AssertionError(f"unexpected tool call: {tool_name}")

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job-followup-dr-send-plan",
            kind="gemini_web.ask",
            input={
                "question": "继续",
                "conversation_url": "https://gemini.google.com/app/790681f697666eed",
            },
            params={
                "preset": "deep_think",
                "timeout_seconds": 60,
                "wait_timeout_seconds": 60,
                "max_wait_seconds": 60,
                "min_chars": 100,
                "deep_research": True,
            },
        )
    )

    assert res.status == "completed"
    assert len(calls) == 3
    assert isinstance(res.meta, dict)
    auto = res.meta.get("deep_research_auto_followup")
    assert isinstance(auto, dict)
    assert auto.get("reason") == "send_needs_followup"
    assert auto.get("sent") is True


def test_gemini_wait_in_progress_sets_stable_thread_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    stable_url = "https://gemini.google.com/app/790681f697666eed"

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            raise AssertionError(f"unexpected tool call: {tool_name}")

    async def _fake_wait_loop_core(self, **kwargs):  # noqa: ARG001
        return (
            {
                "status": "in_progress",
                "answer": "",
                "conversation_url": stable_url,
            },
            stable_url,
        )

    monkeypatch.setattr(GeminiWebMcpExecutor, "_wait_loop_core", _fake_wait_loop_core)

    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]
    res = asyncio.run(
        executor.run(
            job_id="job-followup-dr-stable-wait",
            kind="gemini_web.ask",
            input={
                "question": "继续",
                "conversation_url": stable_url,
            },
            params={
                "preset": "deep_think",
                "phase": "wait",
                "timeout_seconds": 60,
                "wait_timeout_seconds": 60,
                "max_wait_seconds": 60,
                "min_chars": 100,
                "deep_research": True,
            },
        )
    )

    assert res.status == "in_progress"
    assert isinstance(res.meta, dict)
    assert res.meta.get("wait_state") == "stable_thread_wait"
    assert int(res.meta.get("retry_after_seconds") or 0) >= 180
    assert float(res.meta.get("not_before") or 0.0) > time.time()
