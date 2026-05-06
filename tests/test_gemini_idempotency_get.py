import asyncio

from chatgpt_web_mcp.providers.gemini import ask as gemini_ask


def test_gemini_web_idempotency_get_returns_filtered_record(monkeypatch) -> None:
    async def _fake_lookup(*, namespace: str, tool: str, idempotency_key: str):
        assert namespace == "unknown"
        assert tool == "gemini_web_ask_pro"
        assert idempotency_key == "chatgptrest:test:gemini:idem"
        return {
            "status": "completed",
            "conversation_url": "https://gemini.google.com/app/thread/abc",
            "result": {"answer": "hidden when include_result=false"},
        }

    monkeypatch.setattr(gemini_ask, "_idempotency_lookup", _fake_lookup)

    result = asyncio.run(
        gemini_ask.gemini_web_idempotency_get(
            idempotency_key="chatgptrest:test:gemini:idem",
            tool_name="gemini_web_ask_pro",
        )
    )

    assert result["ok"] is True
    assert result["found"] is True
    assert result["tool_name"] == "gemini_web_ask_pro"
    assert result["record"]["conversation_url"] == "https://gemini.google.com/app/thread/abc"
    assert "result" not in result["record"]
