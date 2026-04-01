from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from chatgpt_web_mcp.config import ChatGPTWebConfig
from chatgpt_web_mcp.providers.gemini import core as gemini_core


class _FakePage:
    def __init__(self, url: str = "about:blank") -> None:
        self.url = url


class _FakeContext:
    def __init__(self, pages: list[_FakePage]) -> None:
        self.pages = list(pages)
        self.new_pages: list[_FakePage] = []

    async def new_page(self) -> _FakePage:
        page = _FakePage()
        self.pages.append(page)
        self.new_pages.append(page)
        return page


class _FakeBrowser:
    def __init__(self, context: _FakeContext) -> None:
        self.contexts = [context]


def _cfg() -> ChatGPTWebConfig:
    return ChatGPTWebConfig(
        url="https://gemini.google.com/app",
        storage_state_path=Path("/tmp/gemini-storage-state.json"),
        cdp_url="http://127.0.0.1:9226",
        headless=False,
        viewport_width=1280,
        viewport_height=720,
        proxy_server=None,
        proxy_username=None,
        proxy_password=None,
    )


async def _noop(*_args, **_kwargs) -> None:
    return None


def test_open_gemini_page_uses_fresh_cdp_tab_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = _FakePage("https://gemini.google.com/app/existing-tab")
    context = _FakeContext([existing])
    browser = _FakeBrowser(context)
    goto_calls: list[tuple[_FakePage, str]] = []

    async def _fake_connect(*_args, **_kwargs):
        return browser

    async def _fake_goto(page: _FakePage, url: str, **_kwargs) -> None:
        goto_calls.append((page, url))
        page.url = url

    monkeypatch.delenv("GEMINI_REUSE_EXISTING_CDP_PAGE", raising=False)
    monkeypatch.setattr(gemini_core, "_ensure_local_cdp_chrome_running", _noop)
    monkeypatch.setattr(gemini_core, "_connect_over_cdp_resilient", _fake_connect)
    monkeypatch.setattr(gemini_core, "_goto_with_retry", _fake_goto)
    monkeypatch.setattr(gemini_core, "_raise_if_gemini_blocked", _noop)

    _, _, page, close_context = asyncio.run(
        gemini_core._open_gemini_page(object(), _cfg(), conversation_url=None, ctx=None)
    )

    assert close_context is False
    assert page is not existing
    assert context.new_pages == [page]
    assert goto_calls == [(page, "https://gemini.google.com/app")]


def test_open_gemini_page_can_reuse_existing_cdp_tab_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = _FakePage("https://gemini.google.com/app")
    context = _FakeContext([existing])
    browser = _FakeBrowser(context)
    goto_calls: list[tuple[_FakePage, str]] = []

    async def _fake_connect(*_args, **_kwargs):
        return browser

    async def _fake_goto(page: _FakePage, url: str, **_kwargs) -> None:
        goto_calls.append((page, url))
        page.url = url

    monkeypatch.setenv("GEMINI_REUSE_EXISTING_CDP_PAGE", "1")
    monkeypatch.setattr(gemini_core, "_ensure_local_cdp_chrome_running", _noop)
    monkeypatch.setattr(gemini_core, "_connect_over_cdp_resilient", _fake_connect)
    monkeypatch.setattr(gemini_core, "_goto_with_retry", _fake_goto)
    monkeypatch.setattr(gemini_core, "_raise_if_gemini_blocked", _noop)

    _, _, page, close_context = asyncio.run(
        gemini_core._open_gemini_page(object(), _cfg(), conversation_url=None, ctx=None)
    )

    assert close_context is False
    assert page is existing
    assert context.new_pages == []
    assert goto_calls == []


def test_gemini_find_prompt_box_prefers_textbox_over_transient_textarea() -> None:
    async def _run() -> None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(
                """
                <main>
                  <textarea aria-label="prompt" style="display:block;width:240px;height:24px;"></textarea>
                  <div class="ql-editor" contenteditable="true" role="textbox"
                       aria-label="为 Gemini 输入提示"
                       style="display:block;width:280px;height:28px;">
                    <p><br></p>
                  </div>
                </main>
                """
            )
            locator = await gemini_core._gemini_find_prompt_box(page, timeout_ms=1_000)
            html = await locator.evaluate("(el) => el.outerHTML")
            await browser.close()
            assert "role=\"textbox\"" in html
            assert "contenteditable=\"true\"" in html

    asyncio.run(_run())


def test_gemini_find_prompt_box_waits_out_transient_textarea() -> None:
    async def _run() -> None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(
                """
                <main id="root">
                  <textarea aria-label="prompt" style="display:block;width:240px;height:24px;"></textarea>
                  <script>
                    setTimeout(() => {
                      const root = document.getElementById('root');
                      root.innerHTML = '<div class="ql-editor" contenteditable="true" role="textbox" ' +
                        'aria-label="为 Gemini 输入提示" style="display:block;width:280px;height:28px;"><p><br></p></div>';
                    }, 1200);
                  </script>
                </main>
                """
            )
            locator = await gemini_core._gemini_find_prompt_box(page, timeout_ms=4_000)
            html = await locator.evaluate("(el) => el.outerHTML")
            await browser.close()
            assert "role=\"textbox\"" in html
            assert "contenteditable=\"true\"" in html

    asyncio.run(_run())
