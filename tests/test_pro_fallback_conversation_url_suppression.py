from __future__ import annotations

import asyncio

from chatgptrest.executors.chatgpt_web_mcp import ChatGPTWebMcpExecutor


class _DummyMcpClient:
    def __init__(self, *, ask_result: dict) -> None:
        self._ask_result = dict(ask_result)

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        if tool_name == "chatgpt_web_blocked_status":
            return {"blocked": False}
        if tool_name == "chatgpt_web_idempotency_get":
            return {"ok": True, "record": {"sent": False, "conversation_url": ""}}
        if tool_name in {"chatgpt_web_ask", "chatgpt_web_ask_pro_extended"}:
            return dict(self._ask_result)
        raise AssertionError(f"unexpected tool: {tool_name}")


def test_pro_fallback_does_not_switch_to_wait_on_homepage_url() -> None:
    ex = ChatGPTWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp", pro_fallback_presets=())
    ex._client = _DummyMcpClient(  # type: ignore[assignment]
        ask_result={
            "ok": False,
            "status": "cooldown",
            "conversation_url": "https://chatgpt.com/",
            "blocked_state": {"reason": "unusual_activity"},
            "error": "unusual activity detected",
            "debug_timeline": [],
        }
    )

    res = asyncio.run(
        ex.run(
            job_id="job-pro-fallback-home",
            kind="chatgpt_web.ask",
            input={"question": "hello"},
            params={"preset": "pro_extended", "send_timeout_seconds": 30, "max_wait_seconds": 60, "web_search": True},
        )
    )
    assert res.status == "cooldown"
    meta = res.meta or {}
    assert meta.get("_fallback_suppressed_reason") != "conversation_url_present"


def test_pro_fallback_does_not_switch_to_wait_on_same_thread_url() -> None:
    thread_url = "https://chatgpt.com/c/697626b7-0674-8322-bd4f-43f407cad353"
    ex = ChatGPTWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp", pro_fallback_presets=())
    ex._client = _DummyMcpClient(  # type: ignore[assignment]
        ask_result={
            "ok": False,
            "status": "cooldown",
            "conversation_url": thread_url,
            "blocked_state": {"reason": "unusual_activity"},
            "error": "unusual activity detected",
            "debug_timeline": [],
        }
    )

    res = asyncio.run(
        ex.run(
            job_id="job-pro-fallback-same-thread",
            kind="chatgpt_web.ask",
            input={"question": "hello", "conversation_url": thread_url},
            params={"preset": "pro_extended", "send_timeout_seconds": 30, "max_wait_seconds": 60, "web_search": True},
        )
    )
    assert res.status == "cooldown"
    meta = res.meta or {}
    assert meta.get("_fallback_suppressed_reason") != "conversation_url_present"

