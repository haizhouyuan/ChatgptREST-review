from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from chatgpt_web_mcp.providers.gemini import ask as gemini_ask


@asynccontextmanager
async def _fake_async_cm(*_args, **_kwargs):
    yield object()


class _FakePlaywright:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeLocator:
    async def count(self) -> int:
        return 0


class _FakePage:
    def __init__(self) -> None:
        self.url = "https://gemini.google.com/app"

    def locator(self, *_args, **_kwargs):
        return _FakeLocator()


def test_gemini_deep_think_error_path_returns_dict_before_send(monkeypatch) -> None:
    updates: list[dict] = []

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        return None, None, _FakePage(), False

    async def _noop(*_args, **_kwargs):
        return None

    async def _fake_find_prompt_box(*_args, **_kwargs):
        return object()

    async def _fake_mode_text(*_args, **_kwargs):
        return "Deep Think"

    async def _fake_best_effort_url(*_args, **_kwargs):
        return ""

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _raise_before_send(*_args, **_kwargs):
        raise RuntimeError("synthetic deep think pre-send failure")

    monkeypatch.setattr(gemini_ask, "_idempotency_begin", _fake_begin)
    monkeypatch.setattr(gemini_ask, "_idempotency_update", _fake_update)
    monkeypatch.setattr(
        gemini_ask,
        "_load_gemini_web_config",
        lambda: SimpleNamespace(cdp_url="http://127.0.0.1:9222", storage_state_path=Path(__file__)),
    )
    monkeypatch.setattr(gemini_ask, "_ask_lock", lambda: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "_page_slot", lambda *args, **kwargs: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(gemini_ask, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_clear_selected_tools", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_ensure_pro_mode", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_set_tool_checked", _raise_before_send)
    monkeypatch.setattr(gemini_ask, "_gemini_current_mode_text", _fake_mode_text)
    monkeypatch.setattr(gemini_ask, "_capture_debug_artifacts", _fake_debug)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask_pro_deep_think(
            question="test",
            idempotency_key="chatgptrest:test:gemini:deep-think-pre-send-error",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["error_type"] == "RuntimeError"
    assert "synthetic deep think pre-send failure" in str(result["error"])
    assert updates
    assert updates[-1]["status"] == "error"
    assert updates[-1]["sent"] is False
