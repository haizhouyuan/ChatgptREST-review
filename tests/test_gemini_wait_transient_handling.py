from __future__ import annotations

import asyncio
import time

import pytest

import chatgptrest.executors.gemini_web_mcp as gem_mod
from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor


class _TransientThenCompletedClient:
    def __init__(self, failures: int) -> None:
        self.failures = int(failures)
        self.calls = 0
        self.last_tool_args: dict | None = None

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        assert tool_name == "gemini_web_wait"
        self.last_tool_args = dict(tool_args)
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("Transport send error: [Errno 111] Connection refused")
        return {
            "ok": True,
            "status": "completed",
            "answer": "done",
            "conversation_url": str(tool_args.get("conversation_url") or ""),
        }


class _AlwaysTransientClient:
    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        assert tool_name == "gemini_web_wait"
        raise RuntimeError("Transport send error: [Errno 111] Connection refused")


def test_gemini_wait_transient_errors_retry_then_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setenv("CHATGPTREST_GEMINI_WAIT_TRANSIENT_FAILURE_LIMIT", "3")
    monkeypatch.setattr(gem_mod.asyncio, "sleep", _fast_sleep)
    ex = GeminiWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    ex._client = _TransientThenCompletedClient(failures=2)  # type: ignore[assignment]

    res = asyncio.run(
        ex.run(
            job_id="job-gemini-wait-transient-ok",
            kind="gemini_web.ask",
            input={"question": "hello", "conversation_url": "https://gemini.google.com/app/abc123xyz"},
            params={"preset": "pro", "phase": "wait", "wait_timeout_seconds": 30, "max_wait_seconds": 90, "min_chars": 1},
        )
    )
    assert res.status == "completed"
    assert str((res.meta or {}).get("conversation_url") or "").startswith("https://gemini.google.com/app/")


def test_gemini_wait_transient_errors_return_in_progress_after_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setenv("CHATGPTREST_GEMINI_WAIT_TRANSIENT_FAILURE_LIMIT", "2")
    monkeypatch.setenv("CHATGPTREST_GEMINI_WAIT_TRANSIENT_RETRY_AFTER_SECONDS", "9")
    monkeypatch.setattr(gem_mod.asyncio, "sleep", _fast_sleep)
    ex = GeminiWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    ex._client = _AlwaysTransientClient()  # type: ignore[assignment]

    res = asyncio.run(
        ex.run(
            job_id="job-gemini-wait-transient-limit",
            kind="gemini_web.ask",
            input={"question": "hello", "conversation_url": "https://gemini.google.com/app/abc123xyz"},
            params={"preset": "pro", "phase": "wait", "wait_timeout_seconds": 30, "max_wait_seconds": 90, "min_chars": 1},
        )
    )
    assert res.status == "in_progress"
    meta = dict(res.meta or {})
    assert meta.get("error_type") == "InfraError"
    assert int(meta.get("wait_transient_failures") or 0) == 2
    assert int(meta.get("retry_after_seconds") or 0) == 9


def test_gemini_wait_phase_without_conversation_url_is_retryable() -> None:
    ex = GeminiWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    ex._client = _AlwaysTransientClient()  # type: ignore[assignment]

    res = asyncio.run(
        ex.run(
            job_id="job-gemini-wait-missing-url",
            kind="gemini_web.ask",
            input={"question": "hello"},
            params={"preset": "pro", "phase": "wait", "wait_timeout_seconds": 30, "max_wait_seconds": 90},
        )
    )
    assert res.status == "in_progress"
    meta = dict(res.meta or {})
    assert meta.get("error_type") == "WaitingForConversationUrl"
    assert int(meta.get("retry_after_seconds") or 0) == 30
    assert str(meta.get("conversation_url") or "") == ""
    assert float(meta.get("not_before") or 0.0) > time.time() + 20


def test_gemini_wait_passes_deep_research_flag() -> None:
    ex = GeminiWebMcpExecutor(mcp_url="http://127.0.0.1:0/mcp")
    client = _TransientThenCompletedClient(failures=0)
    ex._client = client  # type: ignore[assignment]

    res = asyncio.run(
        ex.run(
            job_id="job-gemini-wait-deep-research",
            kind="gemini_web.ask",
            input={"question": "hello", "conversation_url": "https://gemini.google.com/app/abc123xyz"},
            params={
                "preset": "pro",
                "phase": "wait",
                "deep_research": True,
                "wait_timeout_seconds": 30,
                "max_wait_seconds": 90,
                "min_chars": 1,
            },
        )
    )
    assert res.status == "completed"
    assert isinstance(client.last_tool_args, dict)
    assert bool(client.last_tool_args.get("deep_research")) is True
