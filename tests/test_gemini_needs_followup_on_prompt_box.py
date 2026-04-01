from __future__ import annotations

import asyncio

from chatgptrest.executors.gemini_web_mcp import GeminiWebMcpExecutor


class _FakeToolCaller:
    def __init__(self, result: dict):
        self._result = dict(result)

    def call_tool(self, *, tool_name: str, tool_args: dict, timeout_sec: float):  # noqa: ARG002
        return dict(self._result)


def test_gemini_prompt_box_not_found_is_needs_followup(monkeypatch):
    monkeypatch.delenv("CHATGPTREST_GEMINI_NEEDS_FOLLOWUP_RETRY_AFTER_SECONDS", raising=False)
    fake = _FakeToolCaller(
        {
            "ok": False,
            "status": "error",
            "answer": "",
            "conversation_url": "https://gemini.google.com/app",
            "error_type": "GeminiPromptBoxNotFound",
            "error": "Cannot find Gemini prompt box. Are you logged in?",
        }
    )
    ex = GeminiWebMcpExecutor(tool_caller=fake)
    res = asyncio.run(
        ex.run(
            job_id="j1",
            kind="gemini_web.ask",
            input={"question": "hi"},
            params={"preset": "pro", "phase": "send", "timeout_seconds": 30},
        )
    )
    assert res.status == "needs_followup"
    assert res.meta is not None
    assert "Follow-up:" in (res.meta.get("error") or "")
    assert int(res.meta.get("retry_after_seconds") or 0) >= 30


def test_gemini_other_error_remains_error():
    fake = _FakeToolCaller(
        {
            "ok": False,
            "status": "error",
            "answer": "",
            "conversation_url": "https://gemini.google.com/app",
            "error_type": "RuntimeError",
            "error": "some other failure",
        }
    )
    ex = GeminiWebMcpExecutor(tool_caller=fake)
    res = asyncio.run(
        ex.run(
            job_id="j1",
            kind="gemini_web.ask",
            input={"question": "hi"},
            params={"preset": "pro", "phase": "send", "timeout_seconds": 30},
        )
    )
    assert res.status == "error"


def test_gemini_blocked_region_is_needs_followup(monkeypatch):
    monkeypatch.delenv("CHATGPTREST_GEMINI_NEEDS_FOLLOWUP_RETRY_AFTER_SECONDS", raising=False)
    fake = _FakeToolCaller(
        {
            "ok": False,
            "status": "blocked",
            "answer": "",
            "conversation_url": "https://gemini.google.com/",
            "error_type": "GeminiUnsupportedRegion",
            "error": "Gemini is not available in this region.",
        }
    )
    ex = GeminiWebMcpExecutor(tool_caller=fake)
    res = asyncio.run(
        ex.run(
            job_id="j1",
            kind="gemini_web.ask",
            input={"question": "hi"},
            params={"preset": "pro", "phase": "send", "timeout_seconds": 30},
        )
    )
    assert res.status == "needs_followup"
