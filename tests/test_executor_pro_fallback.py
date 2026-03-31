from __future__ import annotations

import asyncio
import threading
import time
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


def test_pro_fallback_when_not_sent() -> None:
    blocked_until = time.time() + 600.0
    caller = _DummyToolCaller(
        {
            "chatgpt_web_blocked_status": [{"blocked": False}],
            "chatgpt_web_idempotency_get": [
                {"ok": True, "record": {"sent": False}},
                {"ok": True, "record": {"conversation_url": ""}},
            ],
            "chatgpt_web_ask_pro_extended": [
                {
                    "ok": False,
                    "status": "cooldown",
                    "answer": "",
                    "conversation_url": "",
                    "error": "unusual activity",
                    "blocked_state": {"reason": "unusual_activity", "blocked_until": blocked_until},
                    "debug_timeline": [],
                    "retry_after_seconds": 120,
                }
            ],
            "chatgpt_web_ask": [
                {
                    "ok": True,
                    "status": "completed",
                    "answer": "fallback ok",
                    "conversation_url": "https://chatgpt.com/c/test",
                }
            ],
        }
    )
    exe = ChatGPTWebMcpExecutor(tool_caller=caller, pro_fallback_presets=("thinking_heavy",))
    result = asyncio.run(
        exe.run(
            job_id="job-1",
            kind="chatgpt_web.ask",
            input={"question": "hi"},
            params={"preset": "pro_extended"},
        )
    )
    assert result.status == "completed"
    assert result.meta.get("_fallback_from") == "pro_extended"
    assert result.meta.get("_fallback_preset") == "thinking_heavy"

    tool_names = [name for name, _ in caller.calls]
    assert tool_names[:2] == ["chatgpt_web_blocked_status", "chatgpt_web_ask_pro_extended"]
    assert tool_names.count("chatgpt_web_idempotency_get") >= 1
    assert tool_names[-1] == "chatgpt_web_ask"

    assert caller.calls[1][1]["idempotency_key"] == "chatgptrest:job-1:pro_extended"
    fallback_call = caller.calls[-1]
    assert fallback_call[1]["idempotency_key"] == "chatgptrest:job-1:thinking_heavy"
    assert fallback_call[1].get("model") == "thinking"
    assert fallback_call[1].get("thinking_time") == "heavy"


def test_pro_fallback_skipped_when_sent() -> None:
    blocked_until = time.time() + 600.0
    caller = _DummyToolCaller(
        {
            "chatgpt_web_blocked_status": [{"blocked": False}],
            "chatgpt_web_ask_pro_extended": [
                {
                    "ok": False,
                    "status": "cooldown",
                    "answer": "",
                    "conversation_url": "https://chatgpt.com/c/test",
                    "error": "unusual activity",
                    "blocked_state": {"reason": "unusual_activity", "blocked_until": blocked_until},
                    "debug_timeline": [{"phase": "sent", "t": 0.1}],
                    "retry_after_seconds": 120,
                }
            ],
        }
    )
    exe = ChatGPTWebMcpExecutor(tool_caller=caller, pro_fallback_presets=("thinking_heavy",))
    result = asyncio.run(
        exe.run(
            job_id="job-2",
            kind="chatgpt_web.ask",
            input={"question": "hi"},
            params={"preset": "pro_extended"},
        )
    )
    assert result.status == "cooldown"
    tool_names = [name for name, _ in caller.calls]
    assert tool_names == ["chatgpt_web_blocked_status", "chatgpt_web_ask_pro_extended"]


def test_wait_phase_does_not_send() -> None:
    conv_url = "https://chatgpt.com/c/12345678-1234-1234-1234-1234567890ab"
    caller = _DummyToolCaller(
        {
            "chatgpt_web_blocked_status": [{"blocked": False}],
            "chatgpt_web_idempotency_get": [{"ok": True, "record": {"conversation_url": conv_url}}],
            "chatgpt_web_wait": [{"ok": True, "status": "completed", "answer": "done", "conversation_url": conv_url}],
        }
    )
    exe = ChatGPTWebMcpExecutor(tool_caller=caller)
    result = asyncio.run(
        exe.run(
            job_id="job-3",
            kind="chatgpt_web.ask",
            input={"question": "hi"},
            params={"phase": "wait", "preset": "auto"},
        )
    )
    assert result.status == "completed"
    tool_names = [name for name, _ in caller.calls]
    assert "chatgpt_web_ask" not in tool_names
    assert "chatgpt_web_ask_pro_extended" not in tool_names
