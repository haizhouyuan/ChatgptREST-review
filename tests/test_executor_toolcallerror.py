from __future__ import annotations

import asyncio

from chatgptrest.driver.api import ToolCallError
from chatgptrest.executors.chatgpt_web_mcp import ChatGPTWebMcpExecutor


class _FailingToolCaller:
    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        raise ToolCallError("boom")


def test_executor_converts_tool_call_errors_to_cooldown() -> None:
    ex = ChatGPTWebMcpExecutor(tool_caller=_FailingToolCaller())
    res = asyncio.run(
        ex.run(
            job_id="job1",
            kind="chatgpt_web.ask",
            input={"question": "hello"},
            params={"preset": "auto", "timeout_seconds": 30, "max_wait_seconds": 30, "min_chars": 0, "answer_format": "markdown"},
        )
    )
    assert res.status == "cooldown"
    assert (res.meta or {}).get("error_type") == "ToolCallError"
