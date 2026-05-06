from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, nullcontext
from types import SimpleNamespace

import pytest

from chatgpt_web_mcp.providers.gemini import wait as wait_mod


class _FakeRow:
    def __init__(self, page: "_FakePage", *, title: str, jslog: str, click_url: str) -> None:
        self._page = page
        self._title = title
        self._jslog = jslog
        self._click_url = click_url

    async def get_attribute(self, name: str) -> str | None:
        if name == "jslog":
            return self._jslog
        return None

    async def scroll_into_view_if_needed(self, timeout: int = 0) -> None:  # noqa: ARG002
        return None

    async def is_visible(self) -> bool:
        return True

    async def click(self, timeout: int = 0, trial: bool = False, force: bool = False) -> None:  # noqa: ARG002
        if not trial:
            self._page.url = self._click_url
            self._page.responses_visible = 1

    async def inner_text(self, timeout: int = 0) -> str:  # noqa: ARG002
        return self._title


class _FakeTextNode:
    def __init__(self, text: str) -> None:
        self._text = text

    async def inner_text(self, timeout: int = 0) -> str:  # noqa: ARG002
        return self._text


class _FakeLocator:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    @property
    def first(self) -> "_FakeLocator":
        if not self._items:
            return _FakeLocator([])
        return _FakeLocator([self._items[0]])

    def nth(self, idx: int) -> "_FakeLocator":
        return _FakeLocator([self._items[idx]])

    async def count(self) -> int:
        return len(self._items)

    async def click(self, **kwargs) -> None:
        if not self._items:
            raise AssertionError("empty locator")
        await self._items[0].click(**kwargs)

    async def is_visible(self) -> bool:
        if not self._items:
            return False
        item = self._items[0]
        if hasattr(item, "is_visible"):
            return await item.is_visible()
        return True

    async def inner_text(self, timeout: int = 0) -> str:
        if not self._items:
            return ""
        item = self._items[0]
        if hasattr(item, "inner_text"):
            return await item.inner_text(timeout=timeout)
        raise AssertionError("item has no inner_text")

    async def get_attribute(self, name: str) -> str | None:
        if not self._items:
            return None
        item = self._items[0]
        if hasattr(item, "get_attribute"):
            return await item.get_attribute(name)
        return None


class _FakePage:
    def __init__(self) -> None:
        self.url = "https://gemini.google.com/app"
        self.responses_visible = 0
        self.row = _FakeRow(
            self,
            title="hello outline-part1.md planning thread",
            jslog='186014;track:generic_click;BardVeMetadataKey:[null,null,null,null,null,null,null,["c_thread-aaaaaaaa",null,0,5]];mutable:true',
            click_url="https://gemini.google.com/app/thread-bbbbbbbb",
        )

    def locator(self, selector: str) -> _FakeLocator:
        if "conversation-row" in selector or "data-test-id='conversation'" in selector:
            return _FakeLocator([self.row])
        if selector == "model-response":
            return _FakeLocator([_FakeTextNode("done")]) if self.responses_visible else _FakeLocator([])
        if selector == "body":
            return _FakeLocator([_FakeTextNode("")])
        return _FakeLocator([])

    async def wait_for_timeout(self, timeout_ms: int) -> None:  # noqa: ARG002
        return None

    async def close(self) -> None:
        return None


class _FakeBrowser:
    async def close(self) -> None:
        return None


class _FakePlaywright:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ARG002
        return False


@pytest.mark.asyncio
async def test_gemini_wait_fail_closes_when_sidebar_row_cid_and_observed_thread_diverge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _FakePage()

    @asynccontextmanager
    async def _fake_page_slot(*_args, **_kwargs):
        yield None

    async def _fake_open(*_args, **_kwargs):
        return _FakeBrowser(), object(), page, False

    async def _fake_wait_for_url(_page, timeout_seconds: float = 0.0):  # noqa: ARG001
        return page.url

    async def _fake_last_response(_page):
        return "done", False

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(wait_mod, "_load_gemini_web_config", lambda: SimpleNamespace(cdp_url=None))
    monkeypatch.setattr(wait_mod, "_page_slot", _fake_page_slot)
    monkeypatch.setattr(wait_mod, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(wait_mod, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(wait_mod, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(wait_mod, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(wait_mod, "_gemini_last_model_response_text_and_busy", _fake_last_response)
    monkeypatch.setattr(wait_mod, "_maybe_append_call_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wait_mod, "_run_id", lambda **_kwargs: "run-sidebar-thread-guard")
    monkeypatch.setattr(wait_mod, "_without_proxy_env", lambda: nullcontext())
    monkeypatch.setattr(wait_mod, "_ask_lock", lambda: asyncio.Lock())

    result = await wait_mod.gemini_web_wait(
        conversation_url="https://gemini.google.com/app",
        conversation_hint="hello outline-part1.md",
        timeout_seconds=2,
    )

    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["error_type"] == "GeminiConversationThreadMismatch"
    assert result["conversation_url"] == "https://gemini.google.com/app/thread-aaaaaaaa"
    assert result["observed_conversation_url"] == "https://gemini.google.com/app/thread-bbbbbbbb"
    assert result["sidebar_debug"]["selected"]["cid"] == "thread-aaaaaaaa"
    assert result["sidebar_debug"]["selected"]["observed_thread_after_click"] == "https://gemini.google.com/app/thread-bbbbbbbb"



class _MultiRowFakePage:
    def __init__(self, rows: list[_FakeRow]) -> None:
        self.url = "https://gemini.google.com/app"
        self.responses_visible = 0
        self.rows = rows

    def locator(self, selector: str) -> _FakeLocator:
        if "conversation-row" in selector or "data-test-id='conversation'" in selector:
            return _FakeLocator(self.rows)
        if selector == "model-response":
            return _FakeLocator([_FakeTextNode("done")]) if self.responses_visible else _FakeLocator([])
        if selector == "body":
            return _FakeLocator([_FakeTextNode("")])
        return _FakeLocator([])

    async def wait_for_timeout(self, timeout_ms: int) -> None:  # noqa: ARG002
        return None

    async def close(self) -> None:
        return None


class _RootFlappingPage(_MultiRowFakePage):
    def __init__(self) -> None:
        super().__init__([])
        self.root_flaps_remaining = 3

    async def wait_for_timeout(self, timeout_ms: int) -> None:  # noqa: ARG002
        if self.url == "https://gemini.google.com/app/thread-requested" and self.root_flaps_remaining > 0:
            self.root_flaps_remaining -= 1
            self.url = "https://gemini.google.com/app"
            self.responses_visible = 0
        return None


@pytest.mark.asyncio
async def test_gemini_wait_prefers_requested_conversation_cid_over_title_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_url = "https://gemini.google.com/app/thread-requested"
    old_row = _FakeRow(
        None,  # type: ignore[arg-type]
        title="hello outline-part1.md planning thread",
        jslog='186014;track:generic_click;BardVeMetadataKey:[null,null,null,null,null,null,null,["c_thread-old",null,0,5]];mutable:true',
        click_url="https://gemini.google.com/app/thread-old",
    )
    requested_row = _FakeRow(
        None,  # type: ignore[arg-type]
        title="fresh conversation",
        jslog='186014;track:generic_click;BardVeMetadataKey:[null,null,null,null,null,null,null,["c_thread-requested",null,0,5]];mutable:true',
        click_url=requested_url,
    )
    page = _MultiRowFakePage([old_row, requested_row])
    old_row._page = page
    requested_row._page = page

    @asynccontextmanager
    async def _fake_page_slot(*_args, **_kwargs):
        yield None

    async def _fake_open(*_args, **_kwargs):
        return _FakeBrowser(), object(), page, False

    async def _fake_wait_for_url(_page, timeout_seconds: float = 0.0):  # noqa: ARG001
        return page.url

    async def _fake_last_response(_page):
        return "done", False

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(wait_mod, "_load_gemini_web_config", lambda: SimpleNamespace(cdp_url=None))
    monkeypatch.setattr(wait_mod, "_page_slot", _fake_page_slot)
    monkeypatch.setattr(wait_mod, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(wait_mod, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(wait_mod, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(wait_mod, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(wait_mod, "_gemini_last_model_response_text_and_busy", _fake_last_response)
    monkeypatch.setattr(wait_mod, "_maybe_append_call_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wait_mod, "_run_id", lambda **_kwargs: "run-sidebar-exact-cid")
    monkeypatch.setattr(wait_mod, "_without_proxy_env", lambda: nullcontext())
    monkeypatch.setattr(wait_mod, "_ask_lock", lambda: asyncio.Lock())

    result = await wait_mod.gemini_web_wait(
        conversation_url=requested_url,
        conversation_hint="hello outline-part1.md",
        timeout_seconds=2,
    )

    assert result["ok"] is True
    assert result["status"] == "in_progress"
    assert result["conversation_url"] == requested_url
    assert result["sidebar_debug"]["selected"]["reason"] == "requested_cid_match"
    assert result["sidebar_debug"]["selected"]["cid"] == "thread-requested"
    assert result["sidebar_debug"]["requested_cid_match_found"] is True


@pytest.mark.asyncio
async def test_gemini_wait_fail_closes_when_requested_conversation_cid_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_url = "https://gemini.google.com/app/thread-requested"
    old_row = _FakeRow(
        None,  # type: ignore[arg-type]
        title="hello outline-part1.md planning thread",
        jslog='186014;track:generic_click;BardVeMetadataKey:[null,null,null,null,null,null,null,["c_thread-old",null,0,5]];mutable:true',
        click_url="https://gemini.google.com/app/thread-old",
    )
    page = _MultiRowFakePage([old_row])
    old_row._page = page

    @asynccontextmanager
    async def _fake_page_slot(*_args, **_kwargs):
        yield None

    async def _fake_open(*_args, **_kwargs):
        return _FakeBrowser(), object(), page, False

    async def _fake_wait_for_url(_page, timeout_seconds: float = 0.0):  # noqa: ARG001
        return page.url

    async def _fake_last_response(_page):
        return "done", False

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(wait_mod, "_load_gemini_web_config", lambda: SimpleNamespace(cdp_url=None))
    monkeypatch.setattr(wait_mod, "_page_slot", _fake_page_slot)
    monkeypatch.setattr(wait_mod, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(wait_mod, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(wait_mod, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(wait_mod, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(wait_mod, "_gemini_last_model_response_text_and_busy", _fake_last_response)
    monkeypatch.setattr(wait_mod, "_maybe_append_call_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wait_mod, "_run_id", lambda **_kwargs: "run-sidebar-exact-cid-missing")
    monkeypatch.setattr(wait_mod, "_without_proxy_env", lambda: nullcontext())
    monkeypatch.setattr(wait_mod, "_ask_lock", lambda: asyncio.Lock())

    result = await wait_mod.gemini_web_wait(
        conversation_url=requested_url,
        conversation_hint="hello outline-part1.md",
        timeout_seconds=2,
    )

    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["error_type"] == "GeminiConversationThreadMismatch"
    assert result["conversation_url"] == requested_url
    assert result["observed_conversation_url"] == "https://gemini.google.com/app/thread-old"
    assert result["sidebar_debug"]["requested_cid"] == "thread-requested"
    assert result["sidebar_debug"]["requested_cid_match_found"] is False
    assert result["sidebar_debug"]["requested_cid_fallback"] == "body_probe_only"
    assert result["sidebar_debug"]["title_match_skipped_reason"] == "requested_cid_missing"
    assert result["sidebar_debug"]["selected"]["requested_cid_mismatch"] is True



@pytest.mark.asyncio
async def test_gemini_wait_tries_requested_thread_url_before_sidebar_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_url = "https://gemini.google.com/app/thread-requested"
    page = _MultiRowFakePage([])

    @asynccontextmanager
    async def _fake_page_slot(*_args, **_kwargs):
        yield None

    async def _fake_open(*_args, **_kwargs):
        return _FakeBrowser(), object(), page, False

    async def _fake_wait_for_url(_page, timeout_seconds: float = 0.0):  # noqa: ARG001
        return page.url

    async def _fake_last_response(_page):
        return "done", False

    async def _fake_goto(_page, target: str, ctx=None):  # noqa: ARG001
        page.url = target

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(wait_mod, "_load_gemini_web_config", lambda: SimpleNamespace(cdp_url=None))
    monkeypatch.setattr(wait_mod, "_page_slot", _fake_page_slot)
    monkeypatch.setattr(wait_mod, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(wait_mod, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(wait_mod, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(wait_mod, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(wait_mod, "_gemini_last_model_response_text_and_busy", _fake_last_response)
    monkeypatch.setattr(wait_mod, "_goto_with_retry", _fake_goto)
    monkeypatch.setattr(wait_mod, "_maybe_append_call_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wait_mod, "_run_id", lambda **_kwargs: "run-sidebar-direct-goto")
    monkeypatch.setattr(wait_mod, "_without_proxy_env", lambda: nullcontext())
    monkeypatch.setattr(wait_mod, "_ask_lock", lambda: asyncio.Lock())

    result = await wait_mod.gemini_web_wait(
        conversation_url=requested_url,
        conversation_hint="hello outline-part1.md",
        timeout_seconds=1,
    )

    assert result["ok"] is True
    assert result["status"] == "in_progress"
    assert result["conversation_url"] == requested_url
    assert result["sidebar_debug"]["requested_cid_direct_goto_attempted"] is True
    assert result["sidebar_debug"]["requested_cid_direct_goto_succeeded"] is True



@pytest.mark.asyncio
async def test_gemini_wait_attempts_same_session_repair_after_loop_reopen_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_url = "https://gemini.google.com/app/thread-requested"
    page = _RootFlappingPage()

    @asynccontextmanager
    async def _fake_page_slot(*_args, **_kwargs):
        yield None

    async def _fake_open(*_args, **_kwargs):
        return _FakeBrowser(), object(), page, False

    async def _fake_wait_for_url(_page, timeout_seconds: float = 0.0):  # noqa: ARG001
        return page.url

    async def _fake_last_response(_page):
        return "done", False

    async def _fake_goto(_page, target: str, ctx=None):  # noqa: ARG001
        page.url = target
        if target == requested_url:
            page.responses_visible = 1

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(wait_mod, "_load_gemini_web_config", lambda: SimpleNamespace(cdp_url=None))
    monkeypatch.setattr(wait_mod, "_page_slot", _fake_page_slot)
    monkeypatch.setattr(wait_mod, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(wait_mod, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(wait_mod, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(wait_mod, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(wait_mod, "_gemini_last_model_response_text_and_busy", _fake_last_response)
    monkeypatch.setattr(wait_mod, "_goto_with_retry", _fake_goto)
    monkeypatch.setattr(wait_mod, "_maybe_append_call_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wait_mod, "_run_id", lambda **_kwargs: "run-sidebar-same-session-repair")
    monkeypatch.setattr(wait_mod, "_without_proxy_env", lambda: nullcontext())
    monkeypatch.setattr(wait_mod, "_ask_lock", lambda: asyncio.Lock())

    result = await wait_mod.gemini_web_wait(
        conversation_url=requested_url,
        conversation_hint="hello outline-part1.md",
        timeout_seconds=2,
    )

    assert result["ok"] is True
    assert result["conversation_url"] == requested_url
    assert result["sidebar_debug"]["requested_cid_loop_reopen_total_attempts"] == 2
    assert result["sidebar_debug"]["requested_cid_total_recovery_attempts"] == 3
    assert result["sidebar_debug"]["requested_cid_same_session_repair_attempted"] is True
    assert result["sidebar_debug"]["requested_cid_same_session_repair_succeeded"] is True



@pytest.mark.asyncio
async def test_gemini_wait_fail_closes_when_same_session_repair_still_cannot_hold_requested_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_url = "https://gemini.google.com/app/thread-requested"
    page = _RootFlappingPage()
    page.root_flaps_remaining = 99

    @asynccontextmanager
    async def _fake_page_slot(*_args, **_kwargs):
        yield None

    async def _fake_open(*_args, **_kwargs):
        return _FakeBrowser(), object(), page, False

    async def _fake_wait_for_url(_page, timeout_seconds: float = 0.0):  # noqa: ARG001
        return page.url

    async def _fake_last_response(_page):
        return "", False

    async def _fake_goto(_page, target: str, ctx=None):  # noqa: ARG001
        page.url = target
        if target == requested_url:
            page.responses_visible = 1

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(wait_mod, "_load_gemini_web_config", lambda: SimpleNamespace(cdp_url=None))
    monkeypatch.setattr(wait_mod, "_page_slot", _fake_page_slot)
    monkeypatch.setattr(wait_mod, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(wait_mod, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(wait_mod, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(wait_mod, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(wait_mod, "_gemini_last_model_response_text_and_busy", _fake_last_response)
    monkeypatch.setattr(wait_mod, "_goto_with_retry", _fake_goto)
    monkeypatch.setattr(wait_mod, "_maybe_append_call_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wait_mod, "_run_id", lambda **_kwargs: "run-sidebar-same-session-repair-fail")
    monkeypatch.setattr(wait_mod, "_without_proxy_env", lambda: nullcontext())
    monkeypatch.setattr(wait_mod, "_ask_lock", lambda: asyncio.Lock())

    result = await wait_mod.gemini_web_wait(
        conversation_url=requested_url,
        conversation_hint="hello outline-part1.md",
        timeout_seconds=1,
    )

    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["error_type"] == "GeminiConversationThreadMismatch"
    assert result["conversation_url"] == requested_url
    assert result["observed_conversation_url"] == "https://gemini.google.com/app"
    assert result["sidebar_debug"]["requested_cid_loop_reopen_total_attempts"] == 2
    assert result["sidebar_debug"]["requested_cid_total_recovery_attempts"] == 3
    assert result["sidebar_debug"]["requested_cid_same_session_repair_attempted"] is True
    assert result["sidebar_debug"]["requested_cid_same_session_repair_succeeded"] is False
