from __future__ import annotations

import asyncio

from chatgptrest.executors.chatgpt_web_mcp import ChatGPTWebMcpExecutor


class _DummyMcpClient:
    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        if tool_name == "chatgpt_web_blocked_status":
            return {"blocked": False}
        if tool_name == "chatgpt_web_ask":
            return {
                "status": "in_progress",
                "answer": "",
                "conversation_url": "",
            }
        if tool_name == "chatgpt_web_idempotency_get":
            return {"ok": False, "status": "not_found", "conversation_url": ""}
        raise AssertionError(f"unexpected tool: {tool_name}")


def test_send_stage_missing_conversation_url_stays_in_progress() -> None:
    ex = ChatGPTWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    ex._client = _DummyMcpClient()  # type: ignore[assignment]
    res = asyncio.run(
        ex.run(
            job_id="job-send-stuck",
            kind="chatgpt_web.ask",
            input={"question": "hello"},
            params={"preset": "auto", "send_timeout_seconds": 30, "max_wait_seconds": 60},
        )
    )
    assert res.status == "in_progress"
    meta = res.meta or {}
    assert meta.get("error_type") == "SendStuckNoConversationUrl"
    assert meta.get("_send_stage_no_conversation_url") is True
