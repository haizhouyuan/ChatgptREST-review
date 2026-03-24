from __future__ import annotations

import asyncio

from chatgptrest.executors.qwen_web_mcp import QwenWebMcpExecutor


class _DummyMcpClient:
    def __init__(self, *, status: str = "completed") -> None:
        self.calls: list[tuple[str, dict]] = []
        self._status = status

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        self.calls.append((tool_name, dict(tool_args)))
        if tool_name == "qwen_web_ask":
            return {
                "ok": True,
                "status": self._status,
                "answer": "ok" if self._status == "completed" else "",
                "conversation_url": "https://www.qianwen.com/chat/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            }
        if tool_name == "qwen_web_wait":
            return {
                "ok": True,
                "status": "completed",
                "answer": "ok",
                "conversation_url": "https://www.qianwen.com/chat/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            }
        raise AssertionError(f"unexpected tool: {tool_name}")


def test_qwen_auto_defaults_to_deep_thinking() -> None:
    ex = QwenWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    dummy = _DummyMcpClient(status="completed")
    ex._client = dummy  # type: ignore[assignment]

    res = asyncio.run(
        ex.run(
            job_id="job-qwen-auto",
            kind="qwen_web.ask",
            input={"question": "hello"},
            params={"preset": "auto", "timeout_seconds": 30, "max_wait_seconds": 60},
        )
    )
    assert res.status == "completed"
    assert dummy.calls
    assert dummy.calls[0][0] == "qwen_web_ask"
    assert dummy.calls[0][1].get("preset") == "deep_thinking"


def test_qwen_auto_uses_deep_research_when_requested() -> None:
    ex = QwenWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    dummy = _DummyMcpClient(status="completed")
    ex._client = dummy  # type: ignore[assignment]

    res = asyncio.run(
        ex.run(
            job_id="job-qwen-research",
            kind="qwen_web.ask",
            input={"question": "hello"},
            params={"preset": "auto", "deep_research": True, "timeout_seconds": 30, "max_wait_seconds": 60},
        )
    )
    assert res.status == "completed"
    assert dummy.calls
    assert dummy.calls[0][1].get("preset") == "deep_research"
    assert bool((res.meta or {}).get("deep_research_requested")) is True


def test_qwen_wait_phase_requires_conversation_url() -> None:
    ex = QwenWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    ex._client = _DummyMcpClient()  # type: ignore[assignment]
    res = asyncio.run(
        ex.run(
            job_id="job-qwen-wait",
            kind="qwen_web.ask",
            input={"question": "hello"},
            params={"preset": "deep_thinking", "phase": "wait"},
        )
    )
    assert res.status == "error"
    assert "conversation_url" in (res.answer or "")


def test_qwen_wait_passes_deep_research_flag() -> None:
    ex = QwenWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    dummy = _DummyMcpClient(status="in_progress")
    ex._client = dummy  # type: ignore[assignment]

    res = asyncio.run(
        ex.run(
            job_id="job-qwen-wait-research",
            kind="qwen_web.ask",
            input={
                "question": "hello",
                "conversation_url": "https://www.qianwen.com/chat/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
            params={
                "preset": "deep_research",
                "phase": "wait",
                "deep_research": True,
                "max_wait_seconds": 30,
                "wait_timeout_seconds": 30,
                "min_chars": 1,
            },
        )
    )
    assert res.status == "completed"
    assert len(dummy.calls) >= 1
    tool_name, tool_args = dummy.calls[-1]
    assert tool_name == "qwen_web_wait"
    assert bool(tool_args.get("deep_research")) is True
