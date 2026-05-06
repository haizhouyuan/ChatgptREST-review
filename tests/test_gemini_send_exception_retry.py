import asyncio

import pytest

from chatgptrest.driver.api import ToolCallError
from chatgptrest.executors import gemini_web_mcp
from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor


def test_gemini_send_deadline_exceeded_exception_does_not_outer_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    send_calls = 0

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            nonlocal send_calls
            if tool_name.startswith("gemini_web_ask_"):
                send_calls += 1
            raise ToolCallError(
                "mcp_http tool gemini_web_ask_pro failed on attempt 1/15: "
                "McpHttpError: SSE stream timeout (deadline exceeded)."
            )

    monkeypatch.setattr(gemini_web_mcp, "_gemini_send_max_retries", lambda: 3)
    monkeypatch.setattr(gemini_web_mcp, "_gemini_send_retry_delay", lambda: 0.0)
    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]

    with pytest.raises(ToolCallError, match="deadline exceeded"):
        asyncio.run(
            executor.run(
                job_id="job",
                kind="gemini_web.ask",
                input={"question": "read"},
                params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
            )
        )

    assert send_calls == 1


def test_gemini_send_transport_connection_refused_exception_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    send_calls = 0

    class _DummyToolCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
            nonlocal send_calls
            if tool_name.startswith("gemini_web_ask_"):
                send_calls += 1
            if tool_name.startswith("gemini_web_ask_") and send_calls < 3:
                raise ToolCallError(
                    "mcp_http tool gemini_web_ask_pro failed on attempt 1/15: "
                    "McpHttpError: transport error: Connection refused"
                )
            return {"status": "completed", "answer": "ok", "conversation_url": "https://gemini.google.com/app/abc123"}

    monkeypatch.setattr(gemini_web_mcp, "_gemini_send_max_retries", lambda: 2)
    monkeypatch.setattr(gemini_web_mcp, "_gemini_send_retry_delay", lambda: 0.0)
    executor = GeminiWebMcpExecutor(tool_caller=_DummyToolCaller())  # type: ignore[arg-type]

    res = asyncio.run(
        executor.run(
            job_id="job",
            kind="gemini_web.ask",
            input={"question": "read"},
            params={"preset": "pro", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0},
        )
    )

    assert res.status == "completed"
    assert send_calls == 3


def test_gemini_send_retry_delay_honors_human_retry_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_GEMINI_SEND_RETRY_DELAY", "5")
    monkeypatch.setenv("CHATGPTREST_WEB_HUMAN_RETRY_FLOOR_SECONDS", "90")
    monkeypatch.setenv("CHATGPTREST_WEB_HUMAN_RETRY_JITTER_MAX_SECONDS", "0")
    gemini_web_mcp._cfg.__dict__.pop("send_retry_delay", None)

    assert gemini_web_mcp._gemini_send_retry_delay() == 90.0


def test_gemini_wait_transient_retry_after_honors_human_retry_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPTREST_GEMINI_WAIT_TRANSIENT_RETRY_AFTER_SECONDS", "20")
    monkeypatch.setenv("CHATGPTREST_WEB_HUMAN_RETRY_FLOOR_SECONDS", "90")
    monkeypatch.setenv("CHATGPTREST_WEB_HUMAN_RETRY_JITTER_MAX_SECONDS", "0")

    assert gemini_web_mcp._gemini_wait_transient_retry_after_seconds() == 90
