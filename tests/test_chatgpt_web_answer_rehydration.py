from __future__ import annotations

import asyncio

from chatgptrest.executors.chatgpt_web_mcp import ChatGPTWebMcpExecutor


class _DummyMcpClient:
    def __init__(self) -> None:
        self.answer_get_calls: list[dict] = []

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        if tool_name == "chatgpt_web_blocked_status":
            return {"blocked": False}

        if tool_name == "chatgpt_web_ask_pro_extended":
            return {
                "status": "completed",
                "answer": "TRUNCATED",
                "conversation_url": "https://chatgpt.com/c/test",
                "answer_saved": True,
                "answer_truncated": True,
                "answer_id": "a" * 32,
                "answer_chars": 12,
            }

        if tool_name == "chatgpt_web_answer_get":
            self.answer_get_calls.append(dict(tool_args))
            offset = int(tool_args.get("offset") or 0)
            if offset == 0:
                return {
                    "ok": True,
                    "status": "completed",
                    "answer_id": "a" * 32,
                    "answer_chars": 12,
                    "offset": 0,
                    "returned_chars": 6,
                    "next_offset": 6,
                    "done": False,
                    "chunk": "FULL_A",
                }
            return {
                "ok": True,
                "status": "completed",
                "answer_id": "a" * 32,
                "answer_chars": 12,
                "offset": 6,
                "returned_chars": 6,
                "next_offset": None,
                "done": True,
                "chunk": "NSWER!",
            }

        raise AssertionError(f"unexpected tool: {tool_name}")


def test_executor_rehydrates_truncated_answer_via_answer_get() -> None:
    ex = ChatGPTWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    dummy = _DummyMcpClient()
    ex._client = dummy  # type: ignore[assignment]
    res = asyncio.run(
        ex.run(
            job_id="job1",
            kind="chatgpt_web.ask",
            input={"question": "hello"},
            params={"preset": "pro_extended", "timeout_seconds": 30, "max_wait_seconds": 30, "min_chars": 0, "answer_format": "markdown"},
        )
    )
    assert res.status == "completed"
    assert res.answer == "FULL_ANSWER!"
    assert len(dummy.answer_get_calls) >= 1

