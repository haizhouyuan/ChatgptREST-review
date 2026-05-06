from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, nullcontext
from types import SimpleNamespace

import pytest

from chatgpt_web_mcp import _tools_impl as tools


class _FakePage:
    def __init__(self, url: str, *, prompt_visible: bool = False, blocked: bool = False) -> None:
        self.url = url
        self.prompt_visible = prompt_visible
        self.blocked = blocked
        self.viewport = None
        self.brought_to_front = False
        self.reload_calls = 0
        self.close_calls = 0

    async def set_viewport_size(self, viewport: dict[str, int]) -> None:
        self.viewport = dict(viewport)

    async def bring_to_front(self) -> None:
        self.brought_to_front = True

    async def reload(self, *args, **kwargs) -> None:  # noqa: ANN002,ARG002
        self.reload_calls += 1

    async def close(self) -> None:
        self.close_calls += 1


class _FakeContext:
    def __init__(self, pages: list[_FakePage], *, new_page: _FakePage | None = None) -> None:
        self.pages = list(pages)
        self._new_page = new_page or _FakePage("about:blank")
        self.new_page_calls = 0
        self.close_calls = 0

    async def new_page(self) -> _FakePage:
        self.new_page_calls += 1
        return self._new_page

    async def close(self) -> None:
        self.close_calls += 1


class _FakeBrowser:
    def __init__(self, context: _FakeContext) -> None:
        self.contexts = [context]
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1


class _FakeLocator:
    def __init__(self, *, count: int = 0, box: dict[str, float] | None = None, eval_result=None) -> None:
        self._count = count
        self._box = box
        self._eval_result = eval_result

    @property
    def first(self) -> "_FakeLocator":
        return self

    async def count(self) -> int:
        return self._count

    async def scroll_into_view_if_needed(self, timeout: int = 0) -> None:  # noqa: ARG002
        return None

    async def click(self, timeout: int = 0, force: bool = False) -> None:  # noqa: ARG002
        return None

    async def evaluate(self, script: str):  # noqa: ARG002
        return self._eval_result

    async def bounding_box(self):
        return self._box


class _FakeFrameLocator:
    def locator(self, selector: str) -> _FakeLocator:  # noqa: ARG002
        return _FakeLocator(count=0)


class _FakeTurnstileFrame:
    def __init__(self, *, box: dict[str, float]) -> None:
        self.url = "https://challenges.cloudflare.com/turnstile/v0/b/example"
        self._box = box

    def locator(self, selector: str) -> _FakeLocator:  # noqa: ARG002
        return _FakeLocator(count=1, box=self._box)


class _FakeMouse:
    def __init__(self) -> None:
        self.clicks: list[tuple[float, float]] = []

    async def click(self, x: float, y: float) -> None:
        self.clicks.append((x, y))


class _FakeVerificationPage:
    def __init__(self) -> None:
        self.frames: list[object] = []
        self.mouse = _FakeMouse()
        self._locators = {
            "input[name='cf-turnstile-response']": _FakeLocator(
                count=1,
                eval_result={"x": 100.0, "y": 200.0, "width": 240.0, "height": 60.0},
            ),
            "body": _FakeLocator(count=1, box={"x": 0.0, "y": 0.0, "width": 1280.0, "height": 720.0}),
        }

    def locator(self, selector: str) -> _FakeLocator:
        return self._locators.get(selector, _FakeLocator(count=0))

    def frame_locator(self, selector: str) -> _FakeFrameLocator:  # noqa: ARG002
        return _FakeFrameLocator()

    async def wait_for_timeout(self, timeout_ms: int) -> None:  # noqa: ARG002
        return None

    async def evaluate(self, script: str):  # noqa: ARG002
        return []


class _FakeVerificationPageWithFrameAndHiddenInput(_FakeVerificationPage):
    def __init__(self) -> None:
        super().__init__()
        self.frames = [_FakeTurnstileFrame(box={"x": 420.0, "y": 320.0, "width": 400.0, "height": 120.0})]


class _FakePendingVerificationPage(_FakeVerificationPage):
    async def evaluate(self, script: str):  # noqa: ARG002
        return [
            "html:verification_success_waiting",
            "html:loading_verifying",
        ]


class _FakeSlowPendingVerificationPage(_FakeVerificationPage):
    def __init__(self) -> None:
        super().__init__()
        self.now = 0.0

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        self.now += float(timeout_ms) / 1000.0

    async def evaluate(self, script: str):  # noqa: ARG002
        if self.now < 1.0:
            return [
                "html:verification_success_waiting",
                "html:loading_verifying",
            ]
        return []


def test_chatgpt_pick_existing_cdp_page_prefers_visible_prompt(monkeypatch) -> None:
    blocked = _FakePage("https://chatgpt.com/", prompt_visible=False, blocked=True)
    healthy = _FakePage("https://chatgpt.com/", prompt_visible=True, blocked=False)
    context = _FakeContext([blocked, healthy])

    async def _fake_snapshot(page):
        title = "Just a moment..." if page.blocked else "ChatGPT"
        return title, page.url, ""

    async def _fake_signals(page, *, title, url, body):  # noqa: ARG001
        return ["cloudflare"] if page.blocked else []

    async def _fake_has_prompt(page, *, timeout_ms=0):  # noqa: ARG001
        return bool(page.prompt_visible)

    monkeypatch.setattr(tools, "_chatgpt_page_snapshot", _fake_snapshot)
    monkeypatch.setattr(tools, "_chatgpt_cloudflare_signals", _fake_signals)
    monkeypatch.setattr(tools, "_chatgpt_has_visible_prompt_box", _fake_has_prompt)

    picked = asyncio.run(tools._chatgpt_pick_existing_cdp_page(context, conversation_url=None, ctx=None))
    assert picked is healthy


def test_chatgpt_pick_existing_cdp_page_reuses_matching_conversation(monkeypatch) -> None:
    target = "https://chatgpt.com/c/abc123"
    match_page = _FakePage(target, prompt_visible=False, blocked=False)
    other_page = _FakePage("https://chatgpt.com/c/zzz999", prompt_visible=True, blocked=False)
    context = _FakeContext([other_page, match_page])

    async def _fake_snapshot(page):
        return "ChatGPT", page.url, ""

    async def _fake_signals(page, *, title, url, body):  # noqa: ARG001
        return []

    monkeypatch.setattr(tools, "_chatgpt_page_snapshot", _fake_snapshot)
    monkeypatch.setattr(tools, "_chatgpt_cloudflare_signals", _fake_signals)

    picked = asyncio.run(tools._chatgpt_pick_existing_cdp_page(context, conversation_url=target, ctx=None))
    assert picked is match_page


def test_chatgpt_conversation_export_preserves_reused_cdp_thread_page() -> None:
    assert (
        tools._chatgpt_should_preserve_cdp_page(
            tool="chatgpt_web_conversation_export",
            close_context=False,
            conversation_url="https://chatgpt.com/c/abc123456",
            page_url="https://chatgpt.com/c/abc123456",
            reused_existing_cdp_page=True,
        )
        is True
    )
    assert (
        tools._chatgpt_should_preserve_cdp_page(
            tool="chatgpt_web_conversation_export",
            close_context=False,
            conversation_url="https://chatgpt.com/c/abc123456",
            page_url="https://chatgpt.com/c/abc123456",
            reused_existing_cdp_page=False,
        )
        is False
    )


def test_chatgpt_maybe_close_page_keeps_reused_conversation_export_page() -> None:
    page = _FakePage("https://chatgpt.com/c/abc123456")
    setattr(page, "_chatgptrest_reused_existing_cdp_page", True)

    closed = asyncio.run(
        tools._chatgpt_maybe_close_page(
            page,
            tool="chatgpt_web_conversation_export",
            close_context=False,
            conversation_url="https://chatgpt.com/c/abc123456",
        )
    )

    assert closed is False
    assert page.close_calls == 0


def test_chatgpt_pick_existing_cdp_page_without_conversation_skips_thread_tabs(monkeypatch) -> None:
    thread_page = _FakePage("https://chatgpt.com/c/abc123", prompt_visible=True, blocked=False)
    home_page = _FakePage("https://chatgpt.com/", prompt_visible=True, blocked=False)
    context = _FakeContext([thread_page, home_page])

    async def _fake_snapshot(page):
        return "ChatGPT", page.url, ""

    async def _fake_signals(page, *, title, url, body):  # noqa: ARG001
        return []

    async def _fake_has_prompt(page, *, timeout_ms=0):  # noqa: ARG001
        return bool(page.prompt_visible)

    monkeypatch.setattr(tools, "_chatgpt_page_snapshot", _fake_snapshot)
    monkeypatch.setattr(tools, "_chatgpt_cloudflare_signals", _fake_signals)
    monkeypatch.setattr(tools, "_chatgpt_has_visible_prompt_box", _fake_has_prompt)

    picked = asyncio.run(tools._chatgpt_pick_existing_cdp_page(context, conversation_url=None, ctx=None))
    assert picked is home_page


def test_chatgpt_ensure_fresh_chat_context_fails_closed_when_thread_persists(monkeypatch) -> None:
    page = _FakePage("https://chatgpt.com/c/abc123", prompt_visible=True, blocked=False)

    async def _fake_click_new_chat(_page):
        return False

    async def _fake_goto(target_page, url, ctx=None):  # noqa: ANN001,ARG001
        # Stay pinned to the same thread; this is the failure mode we want to guard.
        target_page.url = "https://chatgpt.com/c/abc123"

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(tools, "_chatgpt_click_new_chat", _fake_click_new_chat)
    monkeypatch.setattr(tools, "_goto_with_retry", _fake_goto)
    monkeypatch.setattr(tools, "_human_pause", _noop)

    result = asyncio.run(
        tools._chatgpt_ensure_fresh_chat_context(
            page,
            landing_url="https://chatgpt.com/",
            ctx=None,
        )
    )

    assert result["ok"] is False
    assert result["action"] == "failed"
    assert result["before_thread_id"] == "abc123"
    assert result["after_thread_id"] == "abc123"


def test_chatgpt_ensure_fresh_chat_context_recovers_via_home_navigation(monkeypatch) -> None:
    page = _FakePage("https://chatgpt.com/c/abc123", prompt_visible=True, blocked=False)

    async def _fake_click_new_chat(_page):
        return False

    async def _fake_goto(target_page, url, ctx=None):  # noqa: ANN001,ARG001
        target_page.url = str(url)

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(tools, "_chatgpt_click_new_chat", _fake_click_new_chat)
    monkeypatch.setattr(tools, "_goto_with_retry", _fake_goto)
    monkeypatch.setattr(tools, "_human_pause", _noop)

    result = asyncio.run(
        tools._chatgpt_ensure_fresh_chat_context(
            page,
            landing_url="https://chatgpt.com/",
            ctx=None,
        )
    )

    assert result["ok"] is True
    assert result["action"] == "landing_url"
    assert result["after_url"] == "https://chatgpt.com/"


def test_open_chatgpt_page_reuses_existing_cdp_page_without_new_tab(monkeypatch) -> None:
    existing = _FakePage("https://chatgpt.com/", prompt_visible=True, blocked=False)
    context = _FakeContext([existing])
    browser = _FakeBrowser(context)
    goto_calls: list[str] = []

    async def _noop(*_args, **_kwargs):
        return None

    async def _fake_connect(*_args, **_kwargs):
        return browser

    async def _fake_pick_existing(_context, *, conversation_url, ctx):  # noqa: ARG001
        return existing

    async def _fake_goto(page, url, ctx=None):  # noqa: ARG001
        goto_calls.append(str(url))

    monkeypatch.setattr(tools, "_ensure_local_cdp_chrome_running", _noop)
    monkeypatch.setattr(tools, "_connect_over_cdp_resilient", _fake_connect)
    monkeypatch.setattr(tools, "_restart_local_cdp_chrome", lambda *args, **kwargs: False)
    monkeypatch.setattr(tools, "_chatgpt_pick_existing_cdp_page", _fake_pick_existing)
    monkeypatch.setattr(tools, "_goto_with_retry", _fake_goto)
    monkeypatch.setattr(tools, "_raise_if_chatgpt_blocked", _noop)
    monkeypatch.setattr(tools, "_ctx_info", _noop)

    cfg = SimpleNamespace(
        cdp_url="http://127.0.0.1:9226",
        headless=False,
        viewport_width=1400,
        viewport_height=900,
        proxy_server=None,
        proxy_username=None,
        proxy_password=None,
        storage_state_path="/tmp/storage.json",
        url="https://chatgpt.com/",
    )

    browser_out, context_out, page_out, close_context = asyncio.run(
        tools._open_chatgpt_page(object(), cfg, conversation_url=None, ctx=None)
    )

    assert browser_out is browser
    assert context_out is context
    assert page_out is existing
    assert close_context is False
    assert context.new_page_calls == 0
    assert goto_calls == []
    assert existing.brought_to_front is False
    assert getattr(existing, "_chatgptrest_reused_existing_cdp_page") is True


def test_chatgpt_refresh_page_prefers_conversation_navigation_over_homepage_reload(monkeypatch) -> None:
    page = _FakePage("https://chatgpt.com/")
    goto_calls: list[str] = []

    async def _fake_goto(target_page, url, ctx=None):  # noqa: ANN001,ARG001
        goto_calls.append(str(url))
        target_page.url = str(url)

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(tools, "_goto_with_retry", _fake_goto)
    monkeypatch.setattr(tools, "_human_pause", _noop)
    monkeypatch.setattr(tools, "_raise_if_chatgpt_blocked", _noop)
    monkeypatch.setattr(tools, "_ctx_info", _noop)

    asyncio.run(
        tools._chatgpt_refresh_page(
            page,
            ctx=None,
            reason="wait timeout",
            phase="ask_timeout_wait_start",
            preferred_url="https://chatgpt.com/c/69cb1ba2-0284-83a8-9291-003e5c03ed8d",
        )
    )

    assert goto_calls == ["https://chatgpt.com/c/69cb1ba2-0284-83a8-9291-003e5c03ed8d"]
    assert page.reload_calls == 0
    assert page.url == "https://chatgpt.com/c/69cb1ba2-0284-83a8-9291-003e5c03ed8d"


def test_chatgpt_refresh_page_reloads_when_already_on_same_conversation(monkeypatch) -> None:
    page = _FakePage("https://chatgpt.com/c/69cb1ba2-0284-83a8-9291-003e5c03ed8d")
    goto_calls: list[str] = []

    async def _fake_goto(_target_page, url, ctx=None):  # noqa: ANN001,ARG001
        goto_calls.append(str(url))

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(tools, "_goto_with_retry", _fake_goto)
    monkeypatch.setattr(tools, "_human_pause", _noop)
    monkeypatch.setattr(tools, "_raise_if_chatgpt_blocked", _noop)
    monkeypatch.setattr(tools, "_ctx_info", _noop)

    asyncio.run(
        tools._chatgpt_refresh_page(
            page,
            ctx=None,
            reason="wait timeout",
            phase="wait_timeout",
            preferred_url="https://chatgpt.com/c/69cb1ba2-0284-83a8-9291-003e5c03ed8d",
        )
    )

    assert goto_calls == []
    assert page.reload_calls == 1


def test_chatgpt_action_allowed_during_blocked_permits_probe_tools() -> None:
    assert tools._chatgpt_action_allowed_during_blocked(action="self_check", reason="cloudflare") is True
    assert tools._chatgpt_action_allowed_during_blocked(action="capture_ui", reason="unusual_activity") is True
    assert tools._chatgpt_action_allowed_during_blocked(action="send", reason="cloudflare") is False


def test_chatgpt_should_preserve_cdp_page_for_self_check_homepage() -> None:
    assert (
        tools._chatgpt_should_preserve_cdp_page(
            tool="chatgpt_web_self_check",
            close_context=False,
            conversation_url=None,
            page_url="https://chatgpt.com/",
        )
        is True
    )
    assert (
        tools._chatgpt_should_preserve_cdp_page(
            tool="chatgpt_web_self_check",
            close_context=False,
            conversation_url="https://chatgpt.com/c/abc123",
            page_url="https://chatgpt.com/c/abc123",
        )
        is False
    )
    assert (
        tools._chatgpt_should_preserve_cdp_page(
            tool="chatgpt_web_capture_ui",
            close_context=True,
            conversation_url=None,
            page_url="https://chatgpt.com/",
        )
        is False
    )


def test_chatgpt_try_auto_verification_click_uses_hidden_turnstile_fallback(monkeypatch) -> None:
    page = _FakeVerificationPage()

    async def _fake_snapshot(_page):
        return "ChatGPT", "https://chatgpt.com/", ""

    async def _fake_signals(_page, *, title, url, body):  # noqa: ARG001
        return []

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(tools, "_chatgpt_page_snapshot", _fake_snapshot)
    monkeypatch.setattr(tools, "_chatgpt_cloudflare_signals", _fake_signals)
    monkeypatch.setattr(tools, "_ctx_info", _noop)

    result = asyncio.run(tools._chatgpt_try_auto_verification_click(page, ctx=None, phase="open"))

    assert result["attempted"] is True
    assert result["clicks"] == 1
    assert "fallback:hidden_turnstile_ancestor" in result["steps"]
    assert result["resolved"] is True
    assert page.mouse.clicks == [(119.2, 230.0)]


def test_chatgpt_try_auto_verification_click_prefers_hidden_turnstile_ancestor_over_frame_center(monkeypatch) -> None:
    page = _FakeVerificationPageWithFrameAndHiddenInput()

    async def _fake_snapshot(_page):
        return "ChatGPT", "https://chatgpt.com/", ""

    async def _fake_signals(_page, *, title, url, body):  # noqa: ARG001
        return []

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(tools, "_chatgpt_page_snapshot", _fake_snapshot)
    monkeypatch.setattr(tools, "_chatgpt_cloudflare_signals", _fake_signals)
    monkeypatch.setattr(tools, "_ctx_info", _noop)

    result = asyncio.run(tools._chatgpt_try_auto_verification_click(page, ctx=None, phase="open"))

    assert result["attempted"] is True
    assert result["clicks"] == 1
    assert result["steps"] == ["fallback:hidden_turnstile_ancestor"]
    assert page.mouse.clicks == [(119.2, 230.0)]


def test_chatgpt_verification_pending_signals_detect_hidden_waiting_copy() -> None:
    page = _FakePendingVerificationPage()

    signals = asyncio.run(
        tools._chatgpt_verification_pending_signals(
            page,
            title="Just a moment...",
            url="https://chatgpt.com/",
            body="",
        )
    )

    assert "html:verification_success_waiting" in signals
    assert "html:loading_verifying" in signals


def test_chatgpt_try_auto_verification_click_extends_observation_for_success_waiting(monkeypatch) -> None:
    page = _FakeSlowPendingVerificationPage()

    async def _fake_snapshot(_page):
        if page.now < 1.0:
            return "Just a moment...", "https://chatgpt.com/", "Verifying..."
        return "ChatGPT", "https://chatgpt.com/", ""

    async def _fake_signals(_page, *, title, url, body):  # noqa: ARG001
        return []

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(tools, "_chatgpt_page_snapshot", _fake_snapshot)
    monkeypatch.setattr(tools, "_chatgpt_cloudflare_signals", _fake_signals)
    monkeypatch.setattr(tools, "_ctx_info", _noop)
    monkeypatch.setattr(tools, "_chatgpt_auto_verification_click_wait_ms", lambda: 100)
    monkeypatch.setattr(tools, "_chatgpt_auto_verification_observe_seconds", lambda: 0.25)
    monkeypatch.setattr(tools, "_chatgpt_auto_verification_pending_success_wait_seconds", lambda: 2.0)
    monkeypatch.setattr(tools, "_chatgpt_auto_verification_poll_ms", lambda: 250)
    monkeypatch.setattr(tools.time, "time", lambda: page.now)

    result = asyncio.run(tools._chatgpt_try_auto_verification_click(page, ctx=None, phase="open"))

    assert result["attempted"] is True
    assert result["pending"] is True
    assert result["resolved"] is True
    assert page.now >= 1.0


def test_raise_if_chatgpt_blocked_uses_verification_pending_state(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def _fake_snapshot(_page):
        return "Just a moment...", "https://chatgpt.com/", ""

    async def _fake_signals(_page, *, title, url, body):  # noqa: ARG001
        return ["title"]

    async def _fake_auto(_page, *, ctx, phase):  # noqa: ARG001
        return {
            "enabled": True,
            "attempted": True,
            "clicks": 1,
            "steps": ["fallback:hidden_turnstile_ancestor"],
            "errors": [],
            "resolved": False,
            "pending": True,
            "pending_signals": ["html:verification_success_waiting"],
            "phase": phase,
        }

    async def _fake_artifacts(_page, *, label):  # noqa: ARG001
        return {"screenshot": "artifacts/test.png"}

    async def _fake_set_blocked(*, reason, cooldown_seconds, artifacts=None, extra=None):
        calls.append(
            {
                "reason": reason,
                "cooldown_seconds": cooldown_seconds,
                "artifacts": artifacts,
                "extra": extra,
            }
        )
        return {"blocked_until": 9999999999.0, "reason": reason, "cooldown_seconds": cooldown_seconds}

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(tools, "_chatgpt_page_snapshot", _fake_snapshot)
    monkeypatch.setattr(tools, "_chatgpt_cloudflare_signals", _fake_signals)
    monkeypatch.setattr(tools, "_chatgpt_try_auto_verification_click", _fake_auto)
    monkeypatch.setattr(tools, "_capture_debug_artifacts", _fake_artifacts)
    monkeypatch.setattr(tools, "_chatgpt_set_blocked", _fake_set_blocked)
    monkeypatch.setattr(tools, "_ctx_info", _noop)

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(tools._raise_if_chatgpt_blocked(object(), ctx=None, phase="open", connection="cdp"))

    assert calls
    assert calls[0]["reason"] == "verification_pending"
    assert calls[0]["cooldown_seconds"] == tools._chatgpt_verification_pending_cooldown_seconds()
    assert "verification appears to be in progress" in str(exc.value).lower()


def test_raise_if_chatgpt_blocked_uses_frontend_rate_limit_state(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def _fake_snapshot(_page):
        return "ChatGPT", "https://chatgpt.com/c/abc", ""

    async def _fake_rate_limit(_page, *, error_text=None):  # noqa: ARG001
        return {
            "signals": ["dom:conversation_history_rate_limit_modal"],
            "modal_text": "Too many requests",
        }

    async def _fake_artifacts(_page, *, label):  # noqa: ARG001
        return {"screenshot": "artifacts/rate-limit.png"}

    async def _fake_set_blocked(*, reason, cooldown_seconds, artifacts=None, extra=None):
        calls.append(
            {
                "reason": reason,
                "cooldown_seconds": cooldown_seconds,
                "artifacts": artifacts,
                "extra": extra,
            }
        )
        return {"blocked_until": 9999999999.0, "reason": reason, "cooldown_seconds": cooldown_seconds}

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(tools, "_chatgpt_page_snapshot", _fake_snapshot)
    monkeypatch.setattr(tools, "_chatgpt_frontend_rate_limit_observation", _fake_rate_limit)
    monkeypatch.setattr(tools, "_capture_debug_artifacts", _fake_artifacts)
    monkeypatch.setattr(tools, "_chatgpt_set_blocked", _fake_set_blocked)
    monkeypatch.setattr(tools, "_ctx_info", _noop)

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(tools._raise_if_chatgpt_blocked(object(), ctx=None, phase="send", connection="cdp"))

    assert calls
    assert calls[0]["reason"] == "frontend_rate_limit"
    assert calls[0]["cooldown_seconds"] == tools._chatgpt_frontend_rate_limit_cooldown_seconds()
    assert "frontend rate-limit modal" in str(exc.value).lower()


def test_frontend_rate_limit_error_marker_detects_modal_id() -> None:
    assert tools._chatgpt_frontend_rate_limit_error_marker(
        "subtree from modal-conversation-history-rate-limit intercepts pointer events"
    )


def test_frontend_rate_limit_blocks_probe_actions() -> None:
    assert tools._chatgpt_action_allowed_during_blocked(
        action="self_check", reason="frontend_rate_limit"
    ) is False
    assert tools._chatgpt_action_allowed_during_blocked(
        action="capture_ui", reason="frontend_rate_limit"
    ) is False
    assert tools._chatgpt_action_allowed_during_blocked(
        action="self_check", reason="verification_pending"
    ) is True


def test_frontend_rate_limit_exception_result_writes_blocked_state(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def _fake_rate_limit(_page, *, error_text=None):
        calls.append({"error_text": error_text})
        return {"signals": ["error_text:conversation_history_rate_limit_modal"]}

    async def _fake_set_frontend(page, **kwargs):  # noqa: ANN001
        calls.append({"page_url": getattr(page, "url", ""), **kwargs})
        return {
            "reason": "frontend_rate_limit",
            "blocked_until": 9999999999.0,
            "cooldown_seconds": 3600,
        }

    monkeypatch.setattr(tools, "_chatgpt_frontend_rate_limit_observation", _fake_rate_limit)
    monkeypatch.setattr(tools, "_chatgpt_set_frontend_rate_limit_blocked", _fake_set_frontend)

    result = asyncio.run(
        tools._chatgpt_frontend_rate_limit_result_from_exception(
            _FakePage("https://chatgpt.com/c/abc"),
            ctx=None,
            phase="wait_error",
            exc=RuntimeError("modal-conversation-history-rate-limit intercepted pointer events"),
            started_at=100.0,
            run_id="run-frontend-limit",
            conversation_url="https://chatgpt.com/c/abc",
            artifacts={"text": "artifacts/rate-limit.txt"},
            extra_result={"answer": ""},
        )
    )

    assert result is not None
    assert result["status"] == "blocked"
    assert result["error_type"] == "ChatGPTFrontendRateLimit"
    assert result["blocked_state"]["reason"] == "frontend_rate_limit"
    assert result["debug_artifacts"]["text"] == "artifacts/rate-limit.txt"
    assert calls[1]["phase"] == "wait_error"


def test_blocked_status_from_state_maps_verification_pending_to_cooldown() -> None:
    assert tools._blocked_status_from_state({"reason": "verification_pending"}) == "cooldown"
    assert tools._blocked_status_from_state({"reason": "frontend_rate_limit"}) == "blocked"


def test_chatgpt_self_check_keeps_warm_cdp_page_and_clears_stale_blocked_state(monkeypatch) -> None:
    page = _FakePage("https://chatgpt.com/", prompt_visible=True, blocked=False)
    context = _FakeContext([page])
    browser = _FakeBrowser(context)
    clear_calls: list[dict[str, object]] = []

    async def _fake_open(*_args, **_kwargs):
        return browser, context, page, False

    async def _fake_find_prompt(*_args, **_kwargs):
        return object()

    async def _noop(*_args, **_kwargs):
        return None

    async def _fake_title():
        return "ChatGPT"

    page.title = _fake_title  # type: ignore[method-assign]

    blocked_states = iter(
        [
            {"reason": "cloudflare", "blocked_until": 9999999999.0},
            {"blocked_until": 0.0, "cleared_at": 123.0},
        ]
    )

    @asynccontextmanager
    async def _fake_page_slot(*_args, **_kwargs):
        yield None

    class _FakePlaywright:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(tools, "_chatgpt_enforce_not_blocked", _noop)
    monkeypatch.setattr(tools, "_load_config", lambda: SimpleNamespace(cdp_url="http://127.0.0.1:9226"))
    monkeypatch.setattr(tools, "_page_slot", _fake_page_slot)
    monkeypatch.setattr(tools, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(tools, "_open_chatgpt_page", _fake_open)
    monkeypatch.setattr(tools, "_chatgpt_install_netlog", _noop)
    monkeypatch.setattr(tools, "_find_prompt_box", _fake_find_prompt)
    monkeypatch.setattr(tools, "_wait_for_message_list_to_settle", _noop)
    monkeypatch.setattr(tools, "_current_model_text", lambda _page: asyncio.sleep(0, result="GPT-5 Pro"))
    monkeypatch.setattr(tools, "_chatgpt_read_blocked_state", lambda: asyncio.sleep(0, result=next(blocked_states)))

    async def _fake_clear_blocked_state():
        clear_calls.append({"called": True})
        return {"reason": "cloudflare", "blocked_until": 9999999999.0}

    monkeypatch.setattr(tools, "_chatgpt_clear_blocked_state", _fake_clear_blocked_state)
    monkeypatch.setattr(tools, "_maybe_append_call_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(tools, "_run_id", lambda **_kwargs: "run-1")
    monkeypatch.setattr(tools, "_ctx_info", _noop)
    monkeypatch.setattr(tools, "_without_proxy_env", lambda: nullcontext())

    result = asyncio.run(tools.chatgpt_web_self_check(conversation_url=None, timeout_seconds=5, ctx=None))

    assert result["ok"] is True
    assert result["cleared_stale_blocked_state"] is True
    assert len(clear_calls) == 1
    assert page.close_calls == 0
    assert browser.close_calls == 1
