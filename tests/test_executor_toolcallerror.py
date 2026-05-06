from __future__ import annotations

import asyncio
import importlib
import time
from pathlib import Path

import pytest

from chatgptrest.driver.api import ToolCallError
from chatgptrest.core.chatgpt_web_hold import set_chatgpt_web_hold
from chatgptrest.core.db import connect
from chatgptrest.executors.chatgpt_web_mcp import ChatGPTWebMcpExecutor
import chatgptrest.executors.chatgpt_web_mcp as mod


@pytest.fixture(autouse=True)
def isolated_chatgpt_web_hold_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(tmp_path / "jobdb.sqlite3"))


class _FailingToolCaller:
    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        raise ToolCallError("boom")


class _FrontendRateLimitBlockedCaller:
    def __init__(self, *, reason: str = "frontend_rate_limit") -> None:
        self.calls: list[str] = []
        self.reason = reason

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
        self.calls.append(tool_name)
        if tool_name == "chatgpt_web_blocked_status":
            return {
                "blocked": True,
                "reason": self.reason,
                "seconds_until_unblocked": 3600,
                "blocked_until": 9999999999.0,
            }
        raise AssertionError(f"unexpected tool call: {tool_name}")


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


def test_executor_preflight_frontend_rate_limit_stays_blocked() -> None:
    caller = _FrontendRateLimitBlockedCaller()
    ex = ChatGPTWebMcpExecutor(tool_caller=caller)
    res = asyncio.run(
        ex.run(
            job_id="job-frontend-rate-limit",
            kind="chatgpt_web.ask",
            input={"question": "hello"},
            params={"preset": "auto", "timeout_seconds": 30, "max_wait_seconds": 30, "min_chars": 0, "answer_format": "markdown"},
        )
    )
    assert res.status == "blocked"
    assert (res.meta or {}).get("error_type") == "Blocked"
    assert caller.calls == ["chatgpt_web_blocked_status"]


def test_executor_preflight_manual_pro_session_stays_blocked() -> None:
    caller = _FrontendRateLimitBlockedCaller(reason="manual_pro_session")
    ex = ChatGPTWebMcpExecutor(tool_caller=caller)
    res = asyncio.run(
        ex.run(
            job_id="job-manual-pro-session",
            kind="chatgpt_web.ask",
            input={"question": "hello"},
            params={"preset": "auto", "timeout_seconds": 30, "max_wait_seconds": 30, "min_chars": 0, "answer_format": "markdown"},
        )
    )
    assert res.status == "blocked"
    assert (res.meta or {}).get("error_type") == "Blocked"
    assert "manual_pro_session" in str(res.answer)
    assert caller.calls == ["chatgpt_web_blocked_status"]


def test_executor_db_manual_pro_hold_blocks_before_driver_call(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "jobdb.sqlite3"
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        set_chatgpt_web_hold(
            conn,
            reason="manual_pro_session",
            until_ts=time.time() + 600,
            source="unit_test_db_hold",
        )
        conn.commit()

    caller = _FrontendRateLimitBlockedCaller()
    ex = ChatGPTWebMcpExecutor(tool_caller=caller)
    res = asyncio.run(
        ex.run(
            job_id="job-db-manual-pro-session",
            kind="chatgpt_web.conversation_export",
            input={"conversation_url": "https://chatgpt.com/c/69ecdadf-e784-83e8-a1dc-02b36a2f36f5"},
            params={"timeout_seconds": 30},
        )
    )
    assert res.status == "blocked"
    assert (res.meta or {}).get("error_type") == "Blocked"
    assert ((res.meta or {}).get("chatgpt_web_hold") or {}).get("reason") == "manual_pro_session"
    assert caller.calls == []


def test_chatgpt_send_timeout_with_base_url_recovery_stays_retryable() -> None:
    mod_reloaded = importlib.reload(mod)

    class _TimeoutCaller:
        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:  # noqa: ARG002
            if tool_name == "chatgpt_web_blocked_status":
                raise ToolCallError("McpHttpError: SSE stream timeout (deadline exceeded).")
            if tool_name == "chatgpt_web_idempotency_get":
                return {
                    "ok": True,
                    "record": {
                        "sent": False,
                        "conversation_url": "https://chatgpt.com/",
                    },
                }
            raise ToolCallError("mcp_http tool chatgpt_web_ask_pro_extended failed on attempt 1/15: McpHttpError: SSE stream timeout (deadline exceeded).")

    ex = mod_reloaded.ChatGPTWebMcpExecutor(tool_caller=_TimeoutCaller())
    res = asyncio.run(
        ex.run(
            job_id="job-timeout-1",
            kind="chatgpt_web.ask",
            input={"question": "hello"},
            params={"preset": "pro_extended", "timeout_seconds": 120, "max_wait_seconds": 120, "min_chars": 0, "answer_format": "markdown"},
        )
    )
    assert res.status == "cooldown"
    meta = dict(res.meta or {})
    evidence = dict(meta.get("send_phase_evidence") or {})
    assert evidence.get("idempotency_sent") is False
    assert evidence.get("recovered_conversation_url") is None
    assert evidence.get("safe_to_retry_send") is True


def test_deep_research_send_timeout_uses_dedicated_floor(monkeypatch) -> None:
    monkeypatch.setenv("CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("CHATGPTREST_CHATGPT_DEEP_RESEARCH_SEND_TIMEOUT_SECONDS", "240")
    mod_reloaded = importlib.reload(mod)

    class _CaptureCaller:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float) -> dict:
            self.calls.append({"tool_name": tool_name, "tool_args": dict(tool_args), "timeout_sec": timeout_sec})
            if tool_name == "chatgpt_web_blocked_status":
                return {"blocked": False}
            if tool_name == "chatgpt_web_ask_deep_research":
                return {
                    "status": "in_progress",
                    "answer": "",
                    "conversation_url": "https://chatgpt.com/c/69f05784-b010-83e8-92ca-bc4e45a20666",
                    "debug_timeline": [{"event": "submitted"}],
                }
            raise AssertionError(f"unexpected tool call: {tool_name}")

    caller = _CaptureCaller()
    ex = mod_reloaded.ChatGPTWebMcpExecutor(tool_caller=caller)
    res = asyncio.run(
        ex.run(
            job_id="job-deep-research-timeout-floor",
            kind="chatgpt_web.ask",
            input={"question": "请做深度调研。"},
            params={
                "preset": "pro_extended",
                "deep_research": True,
                "timeout_seconds": 7200,
                "max_wait_seconds": 7200,
                "min_chars": 0,
                "answer_format": "markdown",
                "phase": "send",
            },
        )
    )

    deep_call = next(item for item in caller.calls if item["tool_name"] == "chatgpt_web_ask_deep_research")
    assert deep_call["tool_args"]["timeout_seconds"] == 240
    assert deep_call["timeout_sec"] == 270.0
    assert res.status == "in_progress"
