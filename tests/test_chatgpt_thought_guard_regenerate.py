from __future__ import annotations

import asyncio
import threading
from typing import Any

from chatgptrest.executors.chatgpt_web_mcp import ChatGPTWebMcpExecutor


class _DummyToolCaller:
    def __init__(self, responses_by_tool: dict[str, list[dict[str, Any]]]) -> None:
        self._responses_by_tool = {k: list(v) for k, v in (responses_by_tool or {}).items()}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._lock = threading.Lock()

    def call_tool(
        self,
        *,
        tool_name: str,
        tool_args: dict[str, Any],
        timeout_sec: float = 600.0,
    ) -> dict[str, Any]:
        _ = timeout_sec
        with self._lock:
            self.calls.append((str(tool_name), dict(tool_args or {})))
            queue = self._responses_by_tool.get(str(tool_name))
            if queue:
                return queue.pop(0)
        raise AssertionError(f"unexpected tool call: {tool_name}")


def _long_review_answer(chars: int = 4600) -> str:
    paragraph = (
        "这是一个结构化外审结论：计划必须先收敛产品事实、VOC、设计决策矩阵，再进入高保真原型。"
        "如果没有可审计的 thinking 轨迹，不能把它当成 Pro 高推理证据。"
    )
    repeat = max(1, (chars // len(paragraph)) + 1)
    return (paragraph * repeat)[:chars]


def test_thinking_heavy_short_answer_without_trace_regenerates_same_conversation() -> None:
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-1234567890ab"
    caller = _DummyToolCaller(
        {
            "chatgpt_web_blocked_status": [{"blocked": False}],
            "chatgpt_web_ask": [
                {
                    "ok": True,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": thread_url,
                    "model_text": "thinking",
                    "thinking_time": "heavy",
                }
            ],
            "chatgpt_web_wait": [
                {
                    "ok": True,
                    "status": "completed",
                    "answer": "根据附件内容，以下是三条下一步计划：\n\n- 先确认恢复窗口。\n- 再安排资源。\n- 最后同步风险。",
                    "conversation_url": thread_url,
                }
            ],
            "chatgpt_web_regenerate": [
                {
                    "ok": True,
                    "status": "completed",
                    "answer": "# Findings\n\n1. 供应链恢复窗口尚未确认，当前材料不足以支持结论。\n2. 资源调整方案缺少负责人和时间表。\n3. 风险验证步骤没有落到可执行检查项。\n\n## Next Steps\n\n- 补齐恢复窗口证据\n- 明确责任人与时间线\n- 追加验证清单\n",
                    "conversation_url": thread_url,
                    "thinking_observation": {"thought_seconds": 420, "thought_for_present": True},
                }
            ],
        }
    )
    ex = ChatGPTWebMcpExecutor(tool_caller=caller)
    res = asyncio.run(
        ex.run(
            job_id="job-thinking-heavy-1",
            kind="chatgpt_web.ask",
            input={"question": "请完整评审这个 bundle"},
            params={
                "preset": "thinking_heavy",
                "timeout_seconds": 30,
                "max_wait_seconds": 30,
                "min_chars": 800,
                "answer_format": "markdown",
            },
        )
    )

    assert res.status == "completed"
    assert "Findings" in res.answer
    guard = (res.meta or {}).get("_thought_guard") or {}
    assert guard.get("action") == "regenerated"
    assert ((guard.get("prev") or {}).get("reason")) == "missing_thought_for_short_answer"
    tool_names = [name for name, _ in caller.calls]
    assert tool_names == ["chatgpt_web_blocked_status", "chatgpt_web_ask", "chatgpt_web_wait", "chatgpt_web_regenerate"]


def test_pro_short_answer_without_trace_adopts_regenerate_in_progress() -> None:
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-1234567890ab"
    caller = _DummyToolCaller(
        {
            "chatgpt_web_blocked_status": [{"blocked": False}],
            "chatgpt_web_ask_pro_extended": [
                {
                    "ok": True,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": thread_url,
                }
            ],
            "chatgpt_web_wait": [
                {
                    "ok": True,
                    "status": "completed",
                    "answer": "看来文件已加载。下面是简短建议：先做计划，再做执行。",
                    "conversation_url": thread_url,
                }
            ],
            "chatgpt_web_regenerate": [
                {
                    "ok": True,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": thread_url,
                }
            ],
        }
    )
    ex = ChatGPTWebMcpExecutor(tool_caller=caller)
    res = asyncio.run(
        ex.run(
            job_id="job-pro-short-regen-pending",
            kind="chatgpt_web.ask",
            input={"question": "请完整评审这个 review packet"},
            params={
                "preset": "pro_extended",
                "timeout_seconds": 30,
                "max_wait_seconds": 30,
                "min_chars": 800,
                "answer_format": "markdown",
            },
        )
    )

    assert res.status == "in_progress"
    guard = (res.meta or {}).get("_thought_guard") or {}
    assert guard.get("action") == "regenerate_pending"
    assert guard.get("regenerate_status") == "in_progress"
    assert ((guard.get("prev") or {}).get("reason")) == "missing_thought_for_short_answer"
    tool_names = [name for name, _ in caller.calls]
    assert tool_names == [
        "chatgpt_web_blocked_status",
        "chatgpt_web_ask_pro_extended",
        "chatgpt_web_wait",
        "chatgpt_web_regenerate",
    ]


def test_pro_research_answer_without_trace_regenerates_even_above_min_chars() -> None:
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-1234567890ab"
    caller = _DummyToolCaller(
        {
            "chatgpt_web_blocked_status": [{"blocked": False}],
            "chatgpt_web_ask_pro_extended": [
                {
                    "ok": True,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": thread_url,
                }
            ],
            "chatgpt_web_wait": [
                {
                    "ok": True,
                    "status": "completed",
                    "answer": _long_review_answer(4520),
                    "conversation_url": thread_url,
                }
            ],
            "chatgpt_web_regenerate": [
                {
                    "ok": True,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": thread_url,
                }
            ],
        }
    )
    ex = ChatGPTWebMcpExecutor(tool_caller=caller)
    res = asyncio.run(
        ex.run(
            job_id="job-pro-research-no-trace",
            kind="chatgpt_web.ask",
            input={"question": "请完整评审这个 review packet"},
            params={
                "preset": "pro_extended",
                "timeout_seconds": 30,
                "max_wait_seconds": 30,
                "min_chars": 4000,
                "answer_format": "markdown",
            },
        )
    )

    assert res.status == "in_progress"
    guard = (res.meta or {}).get("_thought_guard") or {}
    assert guard.get("action") == "regenerate_pending"
    assert guard.get("regenerate_status") == "in_progress"
    assert ((guard.get("prev") or {}).get("reason")) == "missing_thought_for_research_answer"
    assert ((guard.get("prev") or {}).get("answer_chars")) == 4520
    tool_names = [name for name, _ in caller.calls]
    assert tool_names == [
        "chatgpt_web_blocked_status",
        "chatgpt_web_ask_pro_extended",
        "chatgpt_web_wait",
        "chatgpt_web_regenerate",
    ]


def test_pro_research_answer_with_thought_trace_is_accepted_above_min_chars() -> None:
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-1234567890ab"
    answer = _long_review_answer(4520)
    caller = _DummyToolCaller(
        {
            "chatgpt_web_blocked_status": [{"blocked": False}],
            "chatgpt_web_ask_pro_extended": [
                {
                    "ok": True,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": thread_url,
                }
            ],
            "chatgpt_web_wait": [
                {
                    "ok": True,
                    "status": "completed",
                    "answer": answer,
                    "conversation_url": thread_url,
                    "thinking_observation": {"thought_seconds": 420, "thought_for_present": True},
                }
            ],
        }
    )
    ex = ChatGPTWebMcpExecutor(tool_caller=caller)
    res = asyncio.run(
        ex.run(
            job_id="job-pro-research-with-trace",
            kind="chatgpt_web.ask",
            input={"question": "请完整评审这个 review packet"},
            params={
                "preset": "pro_extended",
                "timeout_seconds": 30,
                "max_wait_seconds": 30,
                "min_chars": 4000,
                "answer_format": "markdown",
            },
        )
    )

    assert res.status == "completed"
    assert res.answer == answer
    assert not (res.meta or {}).get("_thought_guard")
    tool_names = [name for name, _ in caller.calls]
    assert tool_names == ["chatgpt_web_blocked_status", "chatgpt_web_ask_pro_extended", "chatgpt_web_wait"]


def test_pro_short_answer_without_trace_fail_closes_when_regenerate_not_started() -> None:
    thread_url = "https://chatgpt.com/c/12345678-1234-1234-1234-1234567890ab"
    short_answer = "看来文件已加载。下面是简短建议：先做计划，再做执行。"
    caller = _DummyToolCaller(
        {
            "chatgpt_web_blocked_status": [{"blocked": False}],
            "chatgpt_web_ask_pro_extended": [
                {
                    "ok": True,
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": thread_url,
                }
            ],
            "chatgpt_web_wait": [
                {
                    "ok": True,
                    "status": "completed",
                    "answer": short_answer,
                    "conversation_url": thread_url,
                }
            ],
            "chatgpt_web_regenerate": [
                {
                    "ok": False,
                    "status": "error",
                    "error": "regenerate button not available",
                    "conversation_url": thread_url,
                }
            ],
        }
    )
    ex = ChatGPTWebMcpExecutor(tool_caller=caller)
    res = asyncio.run(
        ex.run(
            job_id="job-pro-short-regen-failed",
            kind="chatgpt_web.ask",
            input={"question": "请完整评审这个 review packet"},
            params={
                "preset": "pro_extended",
                "timeout_seconds": 30,
                "max_wait_seconds": 30,
                "min_chars": 800,
                "answer_format": "markdown",
            },
        )
    )

    assert res.status == "needs_followup"
    assert res.answer == short_answer
    assert (res.meta or {}).get("error_type") == "ThoughtGuardMissingTrace"
    guard = (res.meta or {}).get("_thought_guard") or {}
    assert guard.get("action") == "regenerate_skipped"
    assert guard.get("fail_closed") is True
    assert guard.get("fail_closed_reason") == "missing_thought_for_short_answer"
