from __future__ import annotations

import asyncio
import time
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
        self.reload_calls: list[tuple[str, int | None]] = []
        self.closed = False

    def locator(self, *_args, **_kwargs):
        return _FakeLocator()

    def is_closed(self) -> bool:
        return bool(self.closed)

    async def reload(self, *, wait_until: str = "load", timeout: int | None = None) -> None:
        self.reload_calls.append((wait_until, timeout))

    async def close(self) -> None:
        self.closed = True
        return None


def test_gemini_web_ask_pro_fail_closed_on_pre_send_timeout(monkeypatch) -> None:
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
        return "Pro"

    async def _fake_attach(*_args, **_kwargs):
        await asyncio.sleep(2.0)
        return {"attached": True}

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _fake_best_effort_url(*_args, **_kwargs):
        return ""

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
    monkeypatch.setattr(gemini_ask, "_gemini_current_mode_text", _fake_mode_text)
    monkeypatch.setattr(gemini_ask, "_gemini_maybe_attach_drive_files", _fake_attach)
    monkeypatch.setattr(gemini_ask, "_capture_debug_artifacts", _fake_debug)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    started = time.monotonic()
    result = asyncio.run(
        gemini_ask.gemini_web_ask_pro(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:provider-timeout",
            timeout_seconds=1,
            drive_files=["gdrive:/dummy.md"],
        )
    )
    elapsed = time.monotonic() - started

    assert elapsed < 1.8
    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["error_type"] == "TimeoutError"
    assert result["debug_step"] == "attach_drive_files"
    assert updates
    assert updates[-1]["status"] == "error"
    assert updates[-1]["sent"] is False


class _SlowEnterPageSlot:
    async def __aenter__(self):
        await asyncio.sleep(2.0)
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_gemini_web_ask_pro_fail_closed_on_page_slot_timeout(monkeypatch) -> None:
    updates: list[dict] = []

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    monkeypatch.setattr(gemini_ask, "_idempotency_begin", _fake_begin)
    monkeypatch.setattr(gemini_ask, "_idempotency_update", _fake_update)
    monkeypatch.setattr(
        gemini_ask,
        "_load_gemini_web_config",
        lambda: SimpleNamespace(cdp_url=None, storage_state_path=Path(__file__)),
    )
    monkeypatch.setattr(gemini_ask, "_ask_lock", lambda: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "_page_slot", lambda *args, **kwargs: _SlowEnterPageSlot())
    monkeypatch.setattr(gemini_ask, "async_playwright", lambda: _FakePlaywright())

    started = time.monotonic()
    result = asyncio.run(
        gemini_ask.gemini_web_ask_pro(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:page-slot-timeout",
            timeout_seconds=1,
        )
    )
    elapsed = time.monotonic() - started

    assert elapsed < 1.8
    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["error_type"] == "TimeoutError"
    assert result["debug_step"] == "page_slot"
    assert updates
    assert updates[-1]["status"] == "error"
    assert updates[-1]["sent"] is False


def test_gemini_web_ask_pro_sent_timeout_returns_wait_handoff(monkeypatch) -> None:
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

    async def _fake_focus_prompt_box(_page, prompt_box):
        return prompt_box

    async def _fake_mode_text(*_args, **_kwargs):
        return "Pro"

    async def _fake_wait_for_url(*_args, **_kwargs):
        return "https://gemini.google.com/app"

    async def _fake_wait_for_model_response(*_args, **_kwargs):
        raise TimeoutError()

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _fake_collect_send_observation(*_args, **_kwargs):
        return {}

    async def _fake_best_effort_url(*_args, **_kwargs):
        return "https://gemini.google.com/app"

    monkeypatch.setattr(gemini_ask, "_idempotency_begin", _fake_begin)
    monkeypatch.setattr(gemini_ask, "_idempotency_update", _fake_update)
    monkeypatch.setattr(
        gemini_ask,
        "_load_gemini_web_config",
        lambda: SimpleNamespace(cdp_url=None, storage_state_path=Path(__file__)),
    )
    monkeypatch.setattr(gemini_ask, "_ask_lock", lambda: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "_page_slot", lambda *args, **kwargs: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(gemini_ask, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_gemini_focus_prompt_box", _fake_focus_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_clear_selected_tools", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_ensure_pro_mode", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_current_mode_text", _fake_mode_text)
    monkeypatch.setattr(gemini_ask, "_gemini_type_question_with_app_mentions", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_raise_if_quota_limited", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_click_send", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_model_response", _fake_wait_for_model_response)
    monkeypatch.setattr(gemini_ask, "_capture_debug_artifacts", _fake_debug)
    monkeypatch.setattr(gemini_ask, "_gemini_collect_send_observation", _fake_collect_send_observation)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask_pro(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:sent-timeout-handoff",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is False
    assert result["status"] == "in_progress"
    assert result["conversation_url"] == "https://gemini.google.com/app"
    assert result["error_type"] == "GeminiSendPendingRecovery"
    assert result["wait_handoff_ready"] is True
    assert result["wait_handoff_reason"] == "timeout_after_send"
    assert result["debug_step"] == "wait_model_response"
    assert updates
    assert updates[-1]["status"] == "in_progress"
    assert updates[-1]["sent"] is True


def test_gemini_web_ask_pro_reloads_once_when_initial_prompt_box_times_out(monkeypatch) -> None:
    updates: list[dict] = []
    page = _FakePage()
    prompt_calls = {"count": 0}
    new_chat_calls: list[str] = []

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        return None, None, page, False

    async def _fake_find_prompt_box(*_args, **_kwargs):
        prompt_calls["count"] += 1
        if prompt_calls["count"] == 1:
            raise TimeoutError()
        return object()

    async def _fake_mode_text(*_args, **_kwargs):
        return "Pro"

    async def _fake_focus_prompt_box(_page, prompt_box):
        return prompt_box

    async def _fake_wait_for_url(*_args, **_kwargs):
        return "https://gemini.google.com/app/threads/recovered"

    async def _fake_wait_for_model_response(*_args, **_kwargs):
        return "整理后的三条计划"

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _fake_best_effort_url(*_args, **_kwargs):
        return ""

    async def _fake_collect_send_observation(*_args, **_kwargs):
        return {}

    async def _record_new_chat(*_args, **_kwargs):
        new_chat_calls.append("new_chat")

    async def _fake_restart_local_cdp_chrome(*, kind: str, cdp_url: str, ctx):
        restart_calls.append((kind, cdp_url))
        return True

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(gemini_ask, "_idempotency_begin", _fake_begin)
    monkeypatch.setattr(gemini_ask, "_idempotency_update", _fake_update)
    monkeypatch.setattr(
        gemini_ask,
        "_load_gemini_web_config",
        lambda: SimpleNamespace(cdp_url=None, storage_state_path=Path(__file__)),
    )
    monkeypatch.setattr(gemini_ask, "_ask_lock", lambda: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "_page_slot", lambda *args, **kwargs: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(gemini_ask, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(gemini_ask, "_restart_local_cdp_chrome", _fake_restart_local_cdp_chrome)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _record_new_chat)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_clear_selected_tools", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_ensure_pro_mode", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_current_mode_text", _fake_mode_text)
    monkeypatch.setattr(gemini_ask, "_gemini_focus_prompt_box", _fake_focus_prompt_box)
    monkeypatch.setattr(gemini_ask, "_gemini_type_question_with_app_mentions", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_raise_if_quota_limited", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_click_send", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_model_response", _fake_wait_for_model_response)
    monkeypatch.setattr(gemini_ask, "_capture_debug_artifacts", _fake_debug)
    monkeypatch.setattr(gemini_ask, "_gemini_collect_send_observation", _fake_collect_send_observation)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask_pro(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:initial-prompt-reload-success",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["conversation_url"] == "https://gemini.google.com/app/threads/recovered"
    assert prompt_calls["count"] == 3
    assert page.reload_calls == [("domcontentloaded", gemini_ask._navigation_timeout_ms())]
    assert len(new_chat_calls) == 2


def test_gemini_web_ask_pro_reopens_page_once_when_initial_surface_target_crashes(monkeypatch) -> None:
    updates: list[dict] = []
    first_page = _FakePage()
    second_page = _FakePage()
    prompt_calls = {"count": 0}
    open_calls: list[str] = []
    new_chat_calls: list[str] = []
    restart_calls: list[tuple[str, str]] = []

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        open_calls.append("open")
        if len(open_calls) == 1:
            return None, None, first_page, False
        return None, None, second_page, False

    async def _fake_find_prompt_box(page, *_args, **_kwargs):
        prompt_calls["count"] += 1
        if page is first_page:
            raise RuntimeError("Locator.count: Target crashed")
        return object()

    async def _fake_mode_text(*_args, **_kwargs):
        return "Pro"

    async def _fake_focus_prompt_box(_page, prompt_box):
        return prompt_box

    async def _fake_wait_for_url(*_args, **_kwargs):
        return "https://gemini.google.com/app/threads/reopened"

    async def _fake_wait_for_model_response(*_args, **_kwargs):
        return "整理后的三条计划"

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _fake_best_effort_url(*_args, **_kwargs):
        return ""

    async def _fake_collect_send_observation(*_args, **_kwargs):
        return {}

    async def _record_new_chat(*_args, **_kwargs):
        new_chat_calls.append("new_chat")

    async def _fake_restart_local_cdp_chrome(*, kind: str, cdp_url: str, ctx):
        restart_calls.append((kind, cdp_url))
        return True

    async def _noop(*_args, **_kwargs):
        return None

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
    monkeypatch.setattr(gemini_ask, "_restart_local_cdp_chrome", _fake_restart_local_cdp_chrome)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _record_new_chat)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_clear_selected_tools", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_ensure_pro_mode", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_current_mode_text", _fake_mode_text)
    monkeypatch.setattr(gemini_ask, "_gemini_focus_prompt_box", _fake_focus_prompt_box)
    monkeypatch.setattr(gemini_ask, "_gemini_type_question_with_app_mentions", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_raise_if_quota_limited", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_click_send", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_model_response", _fake_wait_for_model_response)
    monkeypatch.setattr(gemini_ask, "_capture_debug_artifacts", _fake_debug)
    monkeypatch.setattr(gemini_ask, "_gemini_collect_send_observation", _fake_collect_send_observation)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask_pro(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:initial-surface-reopen-success",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["conversation_url"] == "https://gemini.google.com/app/threads/reopened"
    assert prompt_calls["count"] == 3
    assert restart_calls == [("gemini", "http://127.0.0.1:9222")]
    assert open_calls == ["open", "open"]
    assert first_page.closed is True
    assert second_page.closed is True
    assert first_page.reload_calls == []
    assert len(new_chat_calls) == 2


def test_gemini_web_ask_pro_retries_reopen_page_when_cdp_reconnect_lags(monkeypatch) -> None:
    updates: list[dict] = []
    first_page = _FakePage()
    second_page = _FakePage()
    prompt_calls = {"count": 0}
    open_calls: list[str] = []
    restart_calls: list[tuple[str, str]] = []
    new_chat_calls: list[str] = []

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        open_calls.append("open")
        if len(open_calls) == 1:
            return None, None, first_page, False
        if len(open_calls) == 2:
            raise RuntimeError("CDP connect failed without a specific error")
        return None, None, second_page, False

    async def _fake_find_prompt_box(page, *_args, **_kwargs):
        prompt_calls["count"] += 1
        if page is first_page:
            raise RuntimeError("Locator.count: Target page, context or browser has been closed")
        return object()

    async def _fake_mode_text(*_args, **_kwargs):
        return "Pro"

    async def _fake_focus_prompt_box(_page, prompt_box):
        return prompt_box

    async def _fake_wait_for_url(*_args, **_kwargs):
        return "https://gemini.google.com/app/threads/reopened-after-cdp-retry"

    async def _fake_wait_for_model_response(*_args, **_kwargs):
        return "整理后的三条计划"

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _fake_best_effort_url(*_args, **_kwargs):
        return ""

    async def _fake_collect_send_observation(*_args, **_kwargs):
        return {}

    async def _record_new_chat(*_args, **_kwargs):
        new_chat_calls.append("new_chat")

    async def _fake_restart_local_cdp_chrome(*, kind: str, cdp_url: str, ctx):
        restart_calls.append((kind, cdp_url))
        return True

    async def _noop(*_args, **_kwargs):
        return None

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
    monkeypatch.setattr(gemini_ask, "_restart_local_cdp_chrome", _fake_restart_local_cdp_chrome)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _record_new_chat)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_clear_selected_tools", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_ensure_pro_mode", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_current_mode_text", _fake_mode_text)
    monkeypatch.setattr(gemini_ask, "_gemini_focus_prompt_box", _fake_focus_prompt_box)
    monkeypatch.setattr(gemini_ask, "_gemini_type_question_with_app_mentions", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_raise_if_quota_limited", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_click_send", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_model_response", _fake_wait_for_model_response)
    monkeypatch.setattr(gemini_ask, "_capture_debug_artifacts", _fake_debug)
    monkeypatch.setattr(gemini_ask, "_gemini_collect_send_observation", _fake_collect_send_observation)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask_pro(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:reopen-cdp-retry-success",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["conversation_url"] == "https://gemini.google.com/app/threads/reopened-after-cdp-retry"
    assert prompt_calls["count"] == 3
    assert restart_calls == [("gemini", "http://127.0.0.1:9222")]
    assert open_calls == ["open", "open", "open"]
    assert first_page.closed is True
    assert second_page.closed is True
    assert len(new_chat_calls) == 2


def test_gemini_web_ask_pro_reopens_twice_when_initial_surface_keeps_closing(monkeypatch) -> None:
    updates: list[dict] = []
    first_page = _FakePage()
    second_page = _FakePage()
    third_page = _FakePage()
    prompt_calls = {"count": 0}
    open_calls: list[str] = []
    restart_calls: list[tuple[str, str]] = []
    new_chat_calls: list[str] = []

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        open_calls.append("open")
        if len(open_calls) == 1:
            return None, None, first_page, False
        if len(open_calls) == 2:
            return None, None, second_page, False
        return None, None, third_page, False

    async def _fake_find_prompt_box(page, *_args, **_kwargs):
        prompt_calls["count"] += 1
        if page is first_page or page is second_page:
            raise RuntimeError("Locator.count: Target page, context or browser has been closed")
        return object()

    async def _fake_mode_text(*_args, **_kwargs):
        return "Pro"

    async def _fake_focus_prompt_box(_page, prompt_box):
        return prompt_box

    async def _fake_wait_for_url(*_args, **_kwargs):
        return "https://gemini.google.com/app/threads/reopened-after-double-crash"

    async def _fake_wait_for_model_response(*_args, **_kwargs):
        return "整理后的三条计划"

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _fake_best_effort_url(*_args, **_kwargs):
        return ""

    async def _fake_collect_send_observation(*_args, **_kwargs):
        return {}

    async def _record_new_chat(*_args, **_kwargs):
        new_chat_calls.append("new_chat")

    async def _fake_restart_local_cdp_chrome(*, kind: str, cdp_url: str, ctx):
        restart_calls.append((kind, cdp_url))
        return True

    async def _noop(*_args, **_kwargs):
        return None

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
    monkeypatch.setattr(gemini_ask, "_restart_local_cdp_chrome", _fake_restart_local_cdp_chrome)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _record_new_chat)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_clear_selected_tools", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_ensure_pro_mode", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_current_mode_text", _fake_mode_text)
    monkeypatch.setattr(gemini_ask, "_gemini_focus_prompt_box", _fake_focus_prompt_box)
    monkeypatch.setattr(gemini_ask, "_gemini_type_question_with_app_mentions", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_raise_if_quota_limited", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_click_send", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_model_response", _fake_wait_for_model_response)
    monkeypatch.setattr(gemini_ask, "_capture_debug_artifacts", _fake_debug)
    monkeypatch.setattr(gemini_ask, "_gemini_collect_send_observation", _fake_collect_send_observation)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask_pro(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:double-initial-reopen-success",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["conversation_url"] == "https://gemini.google.com/app/threads/reopened-after-double-crash"
    assert prompt_calls["count"] == 4
    assert restart_calls == [("gemini", "http://127.0.0.1:9222"), ("gemini", "http://127.0.0.1:9222")]
    assert open_calls == ["open", "open", "open"]
    assert first_page.closed is True
    assert second_page.closed is True
    assert third_page.closed is True
    assert len(new_chat_calls) == 3


def test_gemini_web_ask_pro_reopens_once_when_prepare_prompt_surface_target_crashes(monkeypatch) -> None:
    updates: list[dict] = []
    first_page = _FakePage()
    second_page = _FakePage()
    prompt_calls = {"count": 0}
    open_calls: list[str] = []
    restart_calls: list[tuple[str, str]] = []
    new_chat_calls: list[str] = []

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        open_calls.append("open")
        if len(open_calls) == 1:
            return None, None, first_page, False
        return None, None, second_page, False

    async def _fake_find_prompt_box(page, *_args, **_kwargs):
        prompt_calls["count"] += 1
        if page is first_page and prompt_calls["count"] == 2:
            raise RuntimeError("Locator.count: Target crashed")
        return object()

    async def _fake_mode_text(*_args, **_kwargs):
        return "Pro"

    async def _fake_focus_prompt_box(_page, prompt_box):
        return prompt_box

    async def _fake_wait_for_url(*_args, **_kwargs):
        return "https://gemini.google.com/app/threads/reopened-after-prepare"

    async def _fake_wait_for_model_response(*_args, **_kwargs):
        return "整理后的三条计划"

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _fake_best_effort_url(*_args, **_kwargs):
        return ""

    async def _fake_collect_send_observation(*_args, **_kwargs):
        return {}

    async def _record_new_chat(*_args, **_kwargs):
        new_chat_calls.append("new_chat")

    async def _fake_restart_local_cdp_chrome(*, kind: str, cdp_url: str, ctx):
        restart_calls.append((kind, cdp_url))
        return True

    async def _noop(*_args, **_kwargs):
        return None

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
    monkeypatch.setattr(gemini_ask, "_restart_local_cdp_chrome", _fake_restart_local_cdp_chrome)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _record_new_chat)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_clear_selected_tools", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_ensure_pro_mode", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_current_mode_text", _fake_mode_text)
    monkeypatch.setattr(gemini_ask, "_gemini_focus_prompt_box", _fake_focus_prompt_box)
    monkeypatch.setattr(gemini_ask, "_gemini_type_question_with_app_mentions", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_raise_if_quota_limited", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_click_send", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_model_response", _fake_wait_for_model_response)
    monkeypatch.setattr(gemini_ask, "_capture_debug_artifacts", _fake_debug)
    monkeypatch.setattr(gemini_ask, "_gemini_collect_send_observation", _fake_collect_send_observation)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask_pro(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:prepare-prompt-reopen-success",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["conversation_url"] == "https://gemini.google.com/app/threads/reopened-after-prepare"
    assert prompt_calls["count"] == 4
    assert restart_calls == [("gemini", "http://127.0.0.1:9222")]
    assert open_calls == ["open", "open"]
    assert first_page.closed is True
    assert second_page.closed is True
    assert len(new_chat_calls) == 2


def test_gemini_web_ask_pro_fail_closed_after_initial_prompt_box_reload_retry(monkeypatch) -> None:
    updates: list[dict] = []
    page = _FakePage()
    prompt_calls = {"count": 0}
    new_chat_calls: list[str] = []

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        return None, None, page, False

    async def _fake_find_prompt_box(*_args, **_kwargs):
        prompt_calls["count"] += 1
        raise TimeoutError()

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _fake_best_effort_url(*_args, **_kwargs):
        return ""

    async def _record_new_chat(*_args, **_kwargs):
        new_chat_calls.append("new_chat")

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(gemini_ask, "_idempotency_begin", _fake_begin)
    monkeypatch.setattr(gemini_ask, "_idempotency_update", _fake_update)
    monkeypatch.setattr(
        gemini_ask,
        "_load_gemini_web_config",
        lambda: SimpleNamespace(cdp_url=None, storage_state_path=Path(__file__)),
    )
    monkeypatch.setattr(gemini_ask, "_ask_lock", lambda: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "_page_slot", lambda *args, **kwargs: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(gemini_ask, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _record_new_chat)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_dismiss_overlays", _noop)
    monkeypatch.setattr(gemini_ask, "_capture_debug_artifacts", _fake_debug)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask_pro(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:initial-prompt-reload-fail",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["error_type"] == "TimeoutError"
    assert result["debug_step"] == "find_prompt_box_initial"
    assert prompt_calls["count"] == 2
    assert page.reload_calls == [("domcontentloaded", gemini_ask._navigation_timeout_ms())]
    assert len(new_chat_calls) == 2
    assert updates
    assert updates[-1]["status"] == "error"
    assert updates[-1]["sent"] is False


def test_gemini_web_ask_sent_timeout_uses_effective_conversation_url_for_wait_handoff(monkeypatch) -> None:
    updates: list[dict] = []
    page = _FakePage()
    page.url = ""

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        return None, None, page, False

    async def _noop(*_args, **_kwargs):
        return None

    async def _fake_find_prompt_box(*_args, **_kwargs):
        return object()

    async def _fake_focus_prompt_box(_page, prompt_box):
        return prompt_box

    async def _fake_wait_for_url(*_args, **_kwargs):
        return "https://gemini.google.com/app"

    async def _fake_wait_for_model_response(*_args, **_kwargs):
        raise TimeoutError()

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _fake_collect_send_observation(*_args, **_kwargs):
        return {}

    async def _fake_best_effort_url(*_args, **_kwargs):
        return ""

    monkeypatch.setattr(gemini_ask, "_idempotency_begin", _fake_begin)
    monkeypatch.setattr(gemini_ask, "_idempotency_update", _fake_update)
    monkeypatch.setattr(
        gemini_ask,
        "_load_gemini_web_config",
        lambda: SimpleNamespace(cdp_url=None, storage_state_path=Path(__file__)),
    )
    monkeypatch.setattr(gemini_ask, "_ask_lock", lambda: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "_page_slot", lambda *args, **kwargs: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(gemini_ask, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_gemini_focus_prompt_box", _fake_focus_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_clear_selected_tools", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_type_question_with_app_mentions", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_click_send", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_model_response", _fake_wait_for_model_response)
    monkeypatch.setattr(gemini_ask, "_capture_debug_artifacts", _fake_debug)
    monkeypatch.setattr(gemini_ask, "_gemini_collect_send_observation", _fake_collect_send_observation)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:ask-sent-timeout-handoff",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is False
    assert result["status"] == "in_progress"
    assert result["conversation_url"] == "https://gemini.google.com/app"
    assert result["error_type"] == "GeminiSendPendingRecovery"
    assert result["wait_handoff_ready"] is True
    assert result["wait_handoff_reason"] == "timeout_after_send"
    assert result["debug_step"] == "wait_model_response"
    assert updates
    assert updates[-1]["status"] == "in_progress"
    assert updates[-1]["sent"] is True


def test_gemini_web_ask_sent_timeout_prefers_specific_wait_thread_over_base_app(monkeypatch) -> None:
    updates: list[dict] = []
    page = _FakePage()
    page.url = "https://gemini.google.com/app"

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        return None, None, page, False

    async def _noop(*_args, **_kwargs):
        return None

    async def _fake_find_prompt_box(*_args, **_kwargs):
        return object()

    async def _fake_focus_prompt_box(_page, prompt_box):
        return prompt_box

    async def _fake_wait_for_url(*_args, **_kwargs):
        return "https://gemini.google.com/app/thread-from-wait"

    async def _fake_wait_for_model_response(*_args, **_kwargs):
        raise TimeoutError()

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _fake_collect_send_observation(*_args, **_kwargs):
        return {}

    async def _fake_best_effort_url(*_args, **_kwargs):
        return "https://gemini.google.com/app"

    monkeypatch.setattr(gemini_ask, "_idempotency_begin", _fake_begin)
    monkeypatch.setattr(gemini_ask, "_idempotency_update", _fake_update)
    monkeypatch.setattr(
        gemini_ask,
        "_load_gemini_web_config",
        lambda: SimpleNamespace(cdp_url=None, storage_state_path=Path(__file__)),
    )
    monkeypatch.setattr(gemini_ask, "_ask_lock", lambda: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "_page_slot", lambda *args, **kwargs: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(gemini_ask, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_gemini_focus_prompt_box", _fake_focus_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_clear_selected_tools", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_type_question_with_app_mentions", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_click_send", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_model_response", _fake_wait_for_model_response)
    monkeypatch.setattr(gemini_ask, "_capture_debug_artifacts", _fake_debug)
    monkeypatch.setattr(gemini_ask, "_gemini_collect_send_observation", _fake_collect_send_observation)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:ask-sent-timeout-thread-preferred",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is False
    assert result["status"] == "in_progress"
    assert result["conversation_url"] == "https://gemini.google.com/app/thread-from-wait"
    assert result["error_type"] == "GeminiSendPendingRecovery"
    assert result["wait_handoff_ready"] is True
    assert updates
    assert updates[-1]["conversation_url"] == "https://gemini.google.com/app/thread-from-wait"


def test_gemini_web_ask_success_keeps_specific_wait_thread_over_base_app(monkeypatch) -> None:
    updates: list[dict] = []
    page = _FakePage()
    page.url = "https://gemini.google.com/app"

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        return None, None, page, False

    async def _noop(*_args, **_kwargs):
        return None

    async def _fake_find_prompt_box(*_args, **_kwargs):
        return object()

    async def _fake_focus_prompt_box(_page, prompt_box):
        return prompt_box

    async def _fake_wait_for_url(*_args, **_kwargs):
        return "https://gemini.google.com/app/thread-from-wait-success"

    async def _fake_wait_for_model_response(*_args, **_kwargs):
        return "整理后的三条计划"

    async def _fake_best_effort_url(*_args, **_kwargs):
        return "https://gemini.google.com/app"

    monkeypatch.setattr(gemini_ask, "_idempotency_begin", _fake_begin)
    monkeypatch.setattr(gemini_ask, "_idempotency_update", _fake_update)
    monkeypatch.setattr(
        gemini_ask,
        "_load_gemini_web_config",
        lambda: SimpleNamespace(cdp_url=None, storage_state_path=Path(__file__)),
    )
    monkeypatch.setattr(gemini_ask, "_ask_lock", lambda: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "_page_slot", lambda *args, **kwargs: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(gemini_ask, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_gemini_focus_prompt_box", _fake_focus_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_clear_selected_tools", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_type_question_with_app_mentions", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_click_send", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_model_response", _fake_wait_for_model_response)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:ask-success-thread-preferred",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["conversation_url"] == "https://gemini.google.com/app/thread-from-wait-success"
    assert updates
    assert updates[-1]["conversation_url"] == "https://gemini.google.com/app/thread-from-wait-success"


def test_gemini_web_ask_success_prefers_best_effort_conversation_url(monkeypatch) -> None:
    updates: list[dict] = []
    page = _FakePage()
    page.url = ""

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        return None, None, page, False

    async def _noop(*_args, **_kwargs):
        return None

    async def _fake_find_prompt_box(*_args, **_kwargs):
        return object()

    async def _fake_focus_prompt_box(_page, prompt_box):
        return prompt_box

    async def _fake_wait_for_url(*_args, **_kwargs):
        return ""

    async def _fake_wait_for_model_response(*_args, **_kwargs):
        return "整理后的三条计划"

    async def _fake_best_effort_url(*_args, **_kwargs):
        return "https://gemini.google.com/app/threads/success-from-best-effort"

    monkeypatch.setattr(gemini_ask, "_idempotency_begin", _fake_begin)
    monkeypatch.setattr(gemini_ask, "_idempotency_update", _fake_update)
    monkeypatch.setattr(
        gemini_ask,
        "_load_gemini_web_config",
        lambda: SimpleNamespace(cdp_url=None, storage_state_path=Path(__file__)),
    )
    monkeypatch.setattr(gemini_ask, "_ask_lock", lambda: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "_page_slot", lambda *args, **kwargs: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, "async_playwright", lambda: _FakePlaywright())
    monkeypatch.setattr(gemini_ask, "_open_gemini_page", _fake_open)
    monkeypatch.setattr(gemini_ask, "_gemini_click_new_chat", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_find_prompt_box", _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, "_gemini_focus_prompt_box", _fake_focus_prompt_box)
    monkeypatch.setattr(gemini_ask, "_human_pause", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_clear_selected_tools", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_type_question_with_app_mentions", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_click_send", _noop)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_conversation_url", _fake_wait_for_url)
    monkeypatch.setattr(gemini_ask, "_gemini_wait_for_model_response", _fake_wait_for_model_response)
    monkeypatch.setattr(gemini_ask, "_best_effort_gemini_conversation_url", _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask(
            question="请整理附件。",
            idempotency_key="chatgptrest:test:gemini:ask-success-best-effort-url",
            timeout_seconds=30,
        )
    )

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["conversation_url"] == "https://gemini.google.com/app/threads/success-from-best-effort"
    assert updates
    assert updates[-1]["status"] == "completed"


def test_gemini_web_ask_pro_sent_timeout_preserves_base_app_url_for_wait_handoff(monkeypatch) -> None:
    updates: list[dict] = []
    page = _FakePage()

    async def _fake_begin(_idem):
        return True, None

    async def _fake_update(_idem, **kwargs):
        updates.append(dict(kwargs))

    async def _fake_open(*_args, **_kwargs):
        return None, None, page, False

    async def _noop(*_args, **_kwargs):
        return None

    async def _fake_find_prompt_box(*_args, **_kwargs):
        return object()

    async def _fake_focus_prompt_box(_page, prompt_box):
        return prompt_box

    async def _fake_mode_text(*_args, **_kwargs):
        return "Pro"

    async def _fake_wait_for_url(*_args, **_kwargs):
        raise RuntimeError('no thread url yet')

    async def _fake_wait_for_model_response(*_args, **_kwargs):
        page.url = ''
        raise TimeoutError()

    async def _fake_debug(*_args, **_kwargs):
        return {}

    async def _fake_collect_send_observation(*_args, **_kwargs):
        return {}

    async def _fake_best_effort_url(*_args, **_kwargs):
        return ''

    monkeypatch.setattr(gemini_ask, '_idempotency_begin', _fake_begin)
    monkeypatch.setattr(gemini_ask, '_idempotency_update', _fake_update)
    monkeypatch.setattr(
        gemini_ask,
        '_load_gemini_web_config',
        lambda: SimpleNamespace(cdp_url=None, storage_state_path=Path(__file__)),
    )
    monkeypatch.setattr(gemini_ask, '_ask_lock', lambda: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, '_page_slot', lambda *args, **kwargs: _fake_async_cm())
    monkeypatch.setattr(gemini_ask, 'async_playwright', lambda: _FakePlaywright())
    monkeypatch.setattr(gemini_ask, '_open_gemini_page', _fake_open)
    monkeypatch.setattr(gemini_ask, '_gemini_click_new_chat', _noop)
    monkeypatch.setattr(gemini_ask, '_gemini_find_prompt_box', _fake_find_prompt_box)
    monkeypatch.setattr(gemini_ask, '_gemini_focus_prompt_box', _fake_focus_prompt_box)
    monkeypatch.setattr(gemini_ask, '_human_pause', _noop)
    monkeypatch.setattr(gemini_ask, '_gemini_clear_selected_tools', _noop)
    monkeypatch.setattr(gemini_ask, '_gemini_ensure_pro_mode', _noop)
    monkeypatch.setattr(gemini_ask, '_gemini_current_mode_text', _fake_mode_text)
    monkeypatch.setattr(gemini_ask, '_gemini_type_question_with_app_mentions', _noop)
    monkeypatch.setattr(gemini_ask, '_gemini_raise_if_quota_limited', _noop)
    monkeypatch.setattr(gemini_ask, '_gemini_click_send', _noop)
    monkeypatch.setattr(gemini_ask, '_gemini_wait_for_conversation_url', _fake_wait_for_url)
    monkeypatch.setattr(gemini_ask, '_gemini_wait_for_model_response', _fake_wait_for_model_response)
    monkeypatch.setattr(gemini_ask, '_capture_debug_artifacts', _fake_debug)
    monkeypatch.setattr(gemini_ask, '_gemini_collect_send_observation', _fake_collect_send_observation)
    monkeypatch.setattr(gemini_ask, '_best_effort_gemini_conversation_url', _fake_best_effort_url)

    result = asyncio.run(
        gemini_ask.gemini_web_ask_pro(
            question='请整理附件。',
            idempotency_key='chatgptrest:test:gemini:provider-timeout-base-app',
            timeout_seconds=1,
        )
    )

    assert result['status'] == 'in_progress'
    assert result['error_type'] == 'GeminiSendPendingRecovery'
    assert result['wait_handoff_ready'] is True
    assert result['conversation_url'] == 'https://gemini.google.com/app'
    assert updates
    assert updates[-1]['conversation_url'] == 'https://gemini.google.com/app'


def test_gemini_send_timeout_pending_uses_base_app_hint_for_wait_steps() -> None:
    result = gemini_ask._gemini_maybe_mark_send_timeout_pending(
        {
            'status': 'in_progress',
            'error_type': 'UiTransientError',
            'error': '<TimeoutError: empty error>',
            'conversation_url': '',
            'debug_step': 'wait_model_response',
        },
        sent=True,
    )

    assert result['status'] == 'in_progress'
    assert result['error_type'] == 'GeminiSendPendingRecovery'
    assert result['wait_handoff_ready'] is True
    assert result['wait_handoff_reason'] == 'timeout_after_send'
    assert result['conversation_url'] == 'https://gemini.google.com/app'
