from __future__ import annotations

import asyncio

from chatgptrest.executors.chatgpt_web_mcp import ChatGPTWebMcpExecutor


class _DummyMcpClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        self.calls.append(tool_name)
        if tool_name == "chatgpt_web_blocked_status":
            return {"blocked": False}
        if tool_name == "chatgpt_web_ask":
            return {"status": "in_progress", "answer": "", "conversation_url": "https://chatgpt.com/c/69896ee7-e764-83a3-81ea-7476193e4590"}
        if tool_name == "chatgpt_web_wait":
            return {"status": "completed", "answer": "done"}
        if tool_name == "chatgpt_web_wait_idempotency":
            raise AssertionError("should not call chatgpt_web_wait_idempotency when conversation_url is known")
        raise AssertionError(f"unexpected tool: {tool_name} args={tool_args}")


def test_wait_loop_skips_wait_idempotency_when_conversation_url_known() -> None:
    ex = ChatGPTWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    dummy = _DummyMcpClient()
    ex._client = dummy  # type: ignore[assignment]
    res = asyncio.run(
        ex.run(
            job_id="job-wait-idem-guard",
            kind="chatgpt_web.ask",
            input={"question": "hello"},
            params={"preset": "auto", "send_timeout_seconds": 30, "wait_timeout_seconds": 30, "max_wait_seconds": 60, "min_chars": 0},
        )
    )
    assert res.status == "completed"
    assert "chatgpt_web_wait_idempotency" not in dummy.calls
