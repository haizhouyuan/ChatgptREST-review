from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace

from chatgpt_web_mcp.providers.gemini import self_check as gemini_self_check


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

    async def is_visible(self) -> bool:
        return False

    async def get_attribute(self, _name: str):
        return None

    async def inner_text(self) -> str:
        return ""

    def first(self):
        return self

    def nth(self, _index: int):
        return self


class _FakePage:
    def __init__(self) -> None:
        self.url = "https://gemini.google.com/app"
        self.closed = False

    def locator(self, *_args, **_kwargs):
        return _FakeLocator()

    def is_closed(self) -> bool:
        return bool(self.closed)

    async def close(self) -> None:
        self.closed = True


def test_gemini_self_check_reopens_prompt_surface_after_target_closed(monkeypatch) -> None:
    pages = [_FakePage(), _FakePage()]
    open_calls: list[int] = []
    restart_calls: list[tuple[str, str | None]] = []

    async def _fake_open(*_args, **_kwargs):
        idx = len(open_calls)
        open_calls.append(idx)
        return None, None, pages[idx], False

    async def _fake_find_prompt_box(page, *_args, **_kwargs):
        if page is pages[0]:
            page.closed = True
            raise RuntimeError("Locator.count: Target page, context or browser has been closed")
        return object()

    async def _noop(*_args, **_kwargs):
        return None

    async def _fake_mode_text(*_args, **_kwargs):
        return "Pro"

    async def _fake_close_surface_handles(*, page=None, context=None, browser=None, close_context=False):
        if page is not None and hasattr(page, "close"):
            await page.close()

    async def _fake_restart_local_cdp_chrome(*, kind: str, cdp_url: str | None, ctx):
        restart_calls.append((kind, cdp_url))
        return True

    monkeypatch.setattr(gemini_self_check, "_load_gemini_web_config", lambda: SimpleNamespace(cdp_url="http://127.0.0.1:9226", storage_state_path=Path(__file__)))
    monkeypatch.setattr(gemini_self_check, "_page_slot", lambda *args, **kwargs: _fake_async_cm())
    monkeypatch.setattr(gemini_self_check, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(gemini_self_check, "_without_proxy_env", lambda: nullcontext())
    monkeypatch.setattr(gemini_self_check, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(gemini_self_check, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_self_check, "_gemini_initial_prompt_surface_needs_reopen", lambda exc, page=None: True)
    monkeypatch.setattr(gemini_self_check, "_gemini_close_surface_handles", _fake_close_surface_handles)
    monkeypatch.setattr(gemini_self_check, "_restart_local_cdp_chrome", _fake_restart_local_cdp_chrome)
    monkeypatch.setattr(gemini_self_check, "_human_pause", _noop)
    monkeypatch.setattr(gemini_self_check, "_gemini_current_mode_text", _fake_mode_text)
    monkeypatch.setattr(gemini_self_check, "_gemini_open_tools_drawer", _noop)
    monkeypatch.setattr(gemini_self_check, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_self_check, "_capture_debug_artifacts", lambda *_args, **_kwargs: {})

    result = asyncio.run(gemini_self_check.gemini_web_self_check(timeout_seconds=5))

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert len(open_calls) == 2
    assert restart_calls == [("gemini", "http://127.0.0.1:9226")]


def test_gemini_self_check_fails_after_reopen_budget_exhausted(monkeypatch) -> None:
    open_calls: list[int] = []
    restart_calls: list[tuple[str, str | None]] = []

    async def _fake_open(*_args, **_kwargs):
        page = _FakePage()
        open_calls.append(1)
        return None, None, page, False

    async def _fake_find_prompt_box(page, *_args, **_kwargs):
        page.closed = True
        raise RuntimeError("Locator.count: Target page, context or browser has been closed")

    async def _fake_close_surface_handles(*, page=None, context=None, browser=None, close_context=False):
        if page is not None and hasattr(page, "close"):
            await page.close()

    async def _fake_restart_local_cdp_chrome(*, kind: str, cdp_url: str | None, ctx):
        restart_calls.append((kind, cdp_url))
        return True

    monkeypatch.setattr(gemini_self_check, "_load_gemini_web_config", lambda: SimpleNamespace(cdp_url="http://127.0.0.1:9226", storage_state_path=Path(__file__)))
    monkeypatch.setattr(gemini_self_check, "_page_slot", lambda *args, **kwargs: _fake_async_cm())
    monkeypatch.setattr(gemini_self_check, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(gemini_self_check, "_without_proxy_env", lambda: nullcontext())
    monkeypatch.setattr(gemini_self_check, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(gemini_self_check, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_self_check, "_gemini_initial_prompt_surface_needs_reopen", lambda exc, page=None: True)
    monkeypatch.setattr(gemini_self_check, "_gemini_close_surface_handles", _fake_close_surface_handles)
    monkeypatch.setattr(gemini_self_check, "_restart_local_cdp_chrome", _fake_restart_local_cdp_chrome)
    monkeypatch.setattr(gemini_self_check, "_capture_debug_artifacts", lambda *_args, **_kwargs: {})

    result = asyncio.run(gemini_self_check.gemini_web_self_check(timeout_seconds=5))

    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["error_type"] == "RuntimeError"
    assert len(open_calls) == 3
    assert restart_calls == [("gemini", "http://127.0.0.1:9226"), ("gemini", "http://127.0.0.1:9226")]
