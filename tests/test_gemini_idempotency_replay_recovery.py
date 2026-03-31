from __future__ import annotations

import asyncio

import pytest

from chatgpt_web_mcp.providers.gemini import ask as gemini_ask


@pytest.mark.parametrize(
    ("tool_fn", "tool_name"),
    [
        (gemini_ask.gemini_web_ask_pro, "gemini_web_ask_pro"),
        (gemini_ask.gemini_web_ask_pro_deep_think, "gemini_web_ask_pro_deep_think"),
    ],
)
def test_gemini_replay_sent_without_thread_url_returns_wait_recovery(
    monkeypatch: pytest.MonkeyPatch,
    tool_fn,
    tool_name: str,
) -> None:
    async def _fake_begin(_idem):
        return False, {
            "tool": tool_name,
            "status": "in_progress",
            "sent": True,
            "conversation_url": "",
            "error": "TimeoutError: Timed out waiting for Gemini response.",
        }

    monkeypatch.setattr(gemini_ask, "_idempotency_begin", _fake_begin)

    result = asyncio.run(
        tool_fn(
            question="请继续完成评审。",
            idempotency_key="chatgptrest:test:gemini:pending-replay",
        )
    )

    assert result["status"] == "in_progress"
    assert result["replayed"] is True
    assert result["error_type"] == "GeminiSendPendingRecovery"
    assert result["wait_handoff_ready"] is True
    assert result["wait_handoff_reason"] == "idempotency_sent_without_thread"
    assert result["conversation_url"] == "https://gemini.google.com/app"
    assert int(result["retry_after_seconds"]) == 15
