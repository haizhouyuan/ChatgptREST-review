from __future__ import annotations

import asyncio
import datetime
import json
import math
import os
import random
import re
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from chatgpt_web_mcp.config import ChatGPTWebConfig, _load_config
from chatgpt_web_mcp.env import _compile_env_regex, _env_int, _truthy_env
from chatgpt_web_mcp.idempotency import (
    _IdempotencyContext,
    _hash_request,
    _idempotency_begin,
    _idempotency_namespace,
    _idempotency_update,
    _normalize_idempotency_key,
    _run_id,
)
from chatgpt_web_mcp.proxy import _without_proxy_env

from chatgpt_web_mcp.playwright.cdp import (
    _cdp_fallback_enabled,
    _connect_over_cdp_resilient,
    _ensure_local_cdp_chrome_running,
    _restart_local_cdp_chrome,
)
from chatgpt_web_mcp.playwright.evidence import _capture_debug_artifacts
from chatgpt_web_mcp.playwright.navigation import (
    _goto_with_retry,
    _navigation_timeout_ms,
    _prompt_action_timeout_ms,
)

from chatgpt_web_mcp.runtime.call_log import (
    _call_log_include_answers,
    _call_log_include_prompts,
    _maybe_append_call_log,
)
from chatgpt_web_mcp.runtime.concurrency import _is_tab_limit_error, _page_slot, _tab_limit_result
from chatgpt_web_mcp.runtime.locks import _ask_lock
from chatgpt_web_mcp.runtime.ratelimit import _gemini_min_prompt_interval_seconds, _respect_prompt_interval
from chatgpt_web_mcp.runtime.util import _ctx_info, _coerce_error_text, _slugify
from chatgpt_web_mcp.runtime.humanize import _human_pause, _type_delay_ms
from chatgpt_web_mcp.runtime.answer_classification import (
    _classify_deep_research_answer,
    _classify_non_deep_research_answer,
    _looks_like_transient_assistant_error,
)
from chatgpt_web_mcp.playwright.input import _type_question
from chatgpt_web_mcp.playwright.io import _fetch_bytes_via_browser
from chatgpt_web_mcp.providers.gemini_common import _gemini_output_dir
from chatgpt_web_mcp.providers.gemini_helpers import (
    _GEMINI_STOP_BUTTON_SELECTOR,
    _best_effort_gemini_conversation_url,
    _gemini_build_conversation_url,
    _gemini_classify_error_type,
    _gemini_conversation_hint_tokens,
    _gemini_conversation_id_from_jslog,
    _gemini_conversation_id_from_url,
    _gemini_infra_retry_after_seconds,
    _gemini_is_base_app_url,
    _gemini_wait_for_conversation_url,
    _looks_like_gemini_blocked_error,
    _looks_like_gemini_deep_research_report,
    _looks_like_gemini_infra_error,
    _slice_gemini_deep_research_report,
)


def _load_gemini_web_config() -> ChatGPTWebConfig:
    base = _load_config()
    url = (os.environ.get("GEMINI_WEB_URL") or "https://gemini.google.com/app").strip()
    storage_state = Path(os.environ.get("GEMINI_STORAGE_STATE") or str(base.storage_state_path)).expanduser().resolve()
    cdp_url = (os.environ.get("GEMINI_CDP_URL") or base.cdp_url) or None
    headless = _truthy_env("GEMINI_HEADLESS", base.headless)
    viewport_width = int(os.environ.get("GEMINI_VIEWPORT_WIDTH") or base.viewport_width)
    viewport_height = int(os.environ.get("GEMINI_VIEWPORT_HEIGHT") or base.viewport_height)

    proxy_server = os.environ.get("GEMINI_PROXY_SERVER") or base.proxy_server
    proxy_username = os.environ.get("GEMINI_PROXY_USERNAME") or base.proxy_username
    proxy_password = os.environ.get("GEMINI_PROXY_PASSWORD") or base.proxy_password

    return ChatGPTWebConfig(
        url=url,
        storage_state_path=storage_state,
        cdp_url=cdp_url,
        headless=headless,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        proxy_server=proxy_server,
        proxy_username=proxy_username,
        proxy_password=proxy_password,
    )


def _gemini_reuse_existing_cdp_page() -> bool:
    # Default to isolated tabs per invocation. Reusing an existing Gemini tab across
    # worker processes can make one process close or mutate another process's page.
    return _truthy_env("GEMINI_REUSE_EXISTING_CDP_PAGE", False)


def _gemini_import_code_fail_open() -> bool:
    return _truthy_env("GEMINI_IMPORT_CODE_FAIL_OPEN", True)


def _gemini_image_min_area() -> int:
    raw = (os.environ.get("GEMINI_IMAGE_MIN_AREA") or "").strip()
    if not raw:
        return 40_000
    try:
        return max(1_000, int(raw))
    except ValueError:
        return 40_000


def _gemini_textarea_fallback_grace_seconds() -> float:
    raw = (os.environ.get("GEMINI_TEXTAREA_FALLBACK_GRACE_SECONDS") or "").strip()
    if not raw:
        return 1.8
    try:
        return max(0.0, min(float(raw), 10.0))
    except ValueError:
        return 1.8


_GOOGLE_VERIFY_RE = _compile_env_regex(
    "GOOGLE_VERIFY_REGEX",
    r"("
    r"unusual traffic|"
    r"\bsorry\b|"
    r"verify you are a human|"
    r"not a robot|"
    r"captcha|"
    r"abnormal traffic|"
    r"异常流量|"
    r"人机验证|"
    r"请验证|"
    r"无法确认|"
    r"may not be secure"
    r")",
    re.I,
)

_GEMINI_SEND_LOCK: asyncio.Lock | None = None
_LAST_GEMINI_PROMPT_SENT_AT: float = 0.0


def _gemini_send_lock() -> asyncio.Lock:
    global _GEMINI_SEND_LOCK
    if _GEMINI_SEND_LOCK is None:
        _GEMINI_SEND_LOCK = asyncio.Lock()
    return _GEMINI_SEND_LOCK


_GEMINI_UNSUPPORTED_REGION_RE = _compile_env_regex(
    "GEMINI_UNSUPPORTED_REGION_REGEX",
    r"("
    r"Gemini\s*(目前)?不支(?:持|援)你所在的地(?:区|區)|"
    r"not\s+supported\s+in\s+your\s+region|"
    r"not\s+available\s+in\s+your\s+country|"
    r"isn['’]?t\s+available\s+in\s+your\s+country"
    r")",
    re.I,
)

_GEMINI_IMAGE_TOOL_UNAVAILABLE_RE = re.compile(
    r"("
    r"我只是一个语言模型|"
    r"不具备这方面的信息或能力|"
    r"无法生成|"
    r"不能(帮|为你)生成|"
    r"can(?:not|'t) (?:create|generate) (?:images?|pictures?)|"
    r"i(?:'m| am) (?:just|only) a language model"
    r")",
    re.I,
)


async def _list_big_images(page, *, min_area: int) -> list[dict[str, Any]]:
    imgs = page.locator("main img")
    count = await imgs.count()
    found: list[dict[str, Any]] = []
    for i in range(min(count, 20)):
        img = imgs.nth(i)
        try:
            box = await img.bounding_box()
        except Exception:
            continue
        if not box:
            continue
        area = float(box.get("width", 0)) * float(box.get("height", 0))
        if area < min_area:
            continue
        src = (await img.get_attribute("src")) or ""
        if not src:
            continue
        alt = (await img.get_attribute("alt")) or ""
        found.append(
            {
                "src": src,
                "alt": alt,
                "width": round(float(box.get("width", 0))),
                "height": round(float(box.get("height", 0))),
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in found:
        src = str(item.get("src") or "")
        if not src or src in seen:
            continue
        seen.add(src)
        deduped.append(item)
    return deduped


async def _wait_for_generated_images(
    page,
    *,
    started_at: float,
    timeout_seconds: int,
    min_area: int,
    stable_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    deadline = started_at + timeout_seconds
    stop_btn = page.locator(_GEMINI_STOP_BUTTON_SELECTOR).first

    prev_srcs: list[str] = []
    stable_for = 0.0
    while time.time() < deadline:
        try:
            last_text = await _gemini_last_model_response_text(page)
        except Exception:
            last_text = ""
        if last_text and _GEMINI_IMAGE_TOOL_UNAVAILABLE_RE.search(last_text):
            raise RuntimeError(f"Gemini did not generate images: {last_text}")

        items = await _list_big_images(page, min_area=min_area)
        srcs = [str(item.get("src") or "") for item in items]

        stop_visible = False
        try:
            if await stop_btn.count():
                stop_visible = await stop_btn.is_visible()
        except PlaywrightTimeoutError:
            stop_visible = False

        if srcs and srcs == prev_srcs and not stop_visible:
            stable_for += 0.5
        else:
            stable_for = 0.0
            prev_srcs = srcs

        if srcs and stable_for >= stable_seconds:
            return items

    await page.wait_for_timeout(500)
    raise TimeoutError("Timed out waiting for generated images to appear.")


_GEMINI_SIGN_IN_CTA_RE = _compile_env_regex(
    "GEMINI_SIGN_IN_CTA_REGEX",
    r"("
    r"\b(sign\s*in|log\s*in)\b|"
    r"登录|登入|继续登录|使用\s*Google\s*帐号"
    r")",
    re.I,
)


async def _raise_if_gemini_blocked(page) -> None:
    title = ""
    try:
        title = (await page.title()).strip()
    except Exception:
        title = ""

    url = page.url or ""

    body = ""
    try:
        body = (await page.locator("body").inner_text(timeout=2_000)).strip()
    except Exception:
        body = ""

    if "accounts.google.com" in (url or ""):
        artifacts = await _capture_debug_artifacts(page, label="gemini_login")
        msg = "Gemini redirected to Google Sign-in. Log in to Google in the Chrome instance used by CDP, then retry."
        if artifacts:
            msg += f" Debug artifacts: {artifacts}"
        raise RuntimeError(msg)

    hay = " ".join([title, url, body])
    if _GOOGLE_VERIFY_RE.search(hay):
        artifacts = await _capture_debug_artifacts(page, label="gemini_verify")
        msg = (
            "Gemini is blocked by a Google verification/captcha page. "
            "Open Gemini in the same Chrome via noVNC, complete the verification manually, then retry."
        )
        if artifacts:
            msg += f" Debug artifacts: {artifacts}"
        raise RuntimeError(msg)

    if _GEMINI_UNSUPPORTED_REGION_RE.search(hay):
        artifacts = await _capture_debug_artifacts(page, label="gemini_unsupported_region")
        msg = (
            "Gemini is not available in this region (page indicates: 'Gemini 目前不支持你所在的地区'). "
            "Switch the CDP Chrome proxy/egress to a supported region (e.g. via CHROME_PROXY_SERVER/ALL_PROXY), "
            "restart Chrome, then retry."
        )
        if artifacts:
            msg += f" Debug artifacts: {artifacts}"
        raise RuntimeError(msg)

    # Some Gemini states show an in-app sign-in CTA without redirecting to accounts.google.com yet.
    if "gemini.google.com" in (url or "") and _GEMINI_SIGN_IN_CTA_RE.search(hay):
        artifacts = await _capture_debug_artifacts(page, label="gemini_sign_in")
        msg = (
            "Gemini appears to require Google Sign-in (in-app sign-in CTA detected). "
            "Log in to Google in the same Chrome instance used by CDP, then retry."
        )
        if artifacts:
            msg += f" Debug artifacts: {artifacts}"
        raise RuntimeError(msg)


async def _open_gemini_page(p, cfg: ChatGPTWebConfig, *, conversation_url: str | None, ctx: Context | None):
    if cfg.cdp_url:
        await _ctx_info(ctx, f"Connecting over CDP: {cfg.cdp_url}")
    else:
        await _ctx_info(ctx, f"Launching Chromium (headless={cfg.headless})")

    use_cdp = bool(cfg.cdp_url)
    if use_cdp:
        await _ensure_local_cdp_chrome_running(kind="gemini", cdp_url=cfg.cdp_url, ctx=ctx)

        def _looks_like_closed_cdp_new_page_error(exc: Exception) -> bool:
            hay = str(exc or "").strip().lower()
            if not hay:
                return False
            if "target page, context or browser has been closed" not in hay and "target closed" not in hay:
                return False
            return "browsercontext.new_page" in hay or "context.new_page" in hay

        def _pick_reusable_cdp_page(context: Any) -> Any | None:
            if not _gemini_reuse_existing_cdp_page():
                return None
            for existing in context.pages:
                if "gemini.google.com" in (existing.url or ""):
                    return existing
            return None

        async def _fresh_cdp_browser_context() -> tuple[Any, Any]:
            browser = await _connect_over_cdp_resilient(p, cfg.cdp_url, ctx=ctx)
            if browser is None:
                raise RuntimeError("connect_over_cdp returned null browser")
            if not browser.contexts:
                raise RuntimeError("No Chrome contexts found via CDP.")
            return browser, browser.contexts[0]

        async def _open_over_cdp() -> tuple[Any, Any, Any, bool]:
            nonlocal local_new_page_retry_spent
            browser, context = await _fresh_cdp_browser_context()
            page = _pick_reusable_cdp_page(context)
            if page is None:
                try:
                    page = await context.new_page()
                except Exception as exc:
                    if not _looks_like_closed_cdp_new_page_error(exc) or local_new_page_retry_spent:
                        raise
                    local_new_page_retry_spent = True
                    await _ctx_info(
                        ctx,
                        "Gemini CDP new_page hit a closed page/context/browser; waiting briefly and retrying fresh CDP attach once before Chrome restart …",
                    )
                    await _ensure_local_cdp_chrome_running(kind="gemini", cdp_url=cfg.cdp_url, ctx=ctx)
                    await asyncio.sleep(1.0)
                    browser, context = await _fresh_cdp_browser_context()
                    page = _pick_reusable_cdp_page(context)
                    if page is None:
                        page = await context.new_page()

            target_url = conversation_url or cfg.url
            current_url = page.url or ""
            if conversation_url:
                should_navigate = True
            else:
                if not current_url or current_url == "about:blank":
                    should_navigate = True
                else:
                    should_navigate = not bool(re.match(r"^https?://gemini\.google\.com/app/?($|\?)", current_url, re.I))

            if should_navigate:
                await _ctx_info(ctx, f"Navigating to {target_url}")
                await _goto_with_retry(page, target_url, ctx=ctx)

            close_context = False
            return browser, context, page, close_context

        local_new_page_retry_spent = False

        cdp_ok = False
        try:
            browser, context, page, close_context = await _open_over_cdp()
            cdp_ok = True
        except Exception as e:
            restarted = await _restart_local_cdp_chrome(kind="gemini", cdp_url=cfg.cdp_url, ctx=ctx)
            if restarted:
                await _ctx_info(ctx, "Gemini: retrying CDP connect after Chrome restart …")
                try:
                    browser, context, page, close_context = await _open_over_cdp()
                    cdp_ok = True
                except Exception as e2:
                    e = e2

            if not cdp_ok:
                if not _cdp_fallback_enabled(kind="gemini"):
                    msg = (
                        f"CDP connect failed ({type(e).__name__}: {e}). "
                        "CDP fallback is disabled. Ensure the noVNC Chrome is running and reachable via GEMINI_CDP_URL "
                        "(try: DISPLAY=:99 ops/chrome_start.sh), then retry."
                    )
                    raise RuntimeError(msg) from e
                await _ctx_info(ctx, f"CDP connect failed ({type(e).__name__}: {e}). Falling back to storage_state launch.")
                use_cdp = False

        if use_cdp:
            await _raise_if_gemini_blocked(page)
            return browser, context, page, close_context

    if not use_cdp:
        proxy = None
        if cfg.proxy_server:
            proxy = {"server": cfg.proxy_server}
            if cfg.proxy_username:
                proxy["username"] = cfg.proxy_username
            if cfg.proxy_password:
                proxy["password"] = cfg.proxy_password
            await _ctx_info(ctx, f"Using proxy: {cfg.proxy_server}")

        browser = await p.chromium.launch(headless=cfg.headless, proxy=proxy)
        context = await browser.new_context(
            storage_state=str(cfg.storage_state_path),
            viewport={"width": cfg.viewport_width, "height": cfg.viewport_height},
        )
        page = await context.new_page()

        url = conversation_url or cfg.url
        await _ctx_info(ctx, f"Navigating to {url}")
        await _goto_with_retry(page, url, ctx=ctx)
        close_context = True

    await _raise_if_gemini_blocked(page)
    return browser, context, page, close_context


async def _gemini_click_new_chat(page) -> None:
    candidates = [
        "a:has-text('发起新对话')",
        "button:has-text('发起新对话')",
        "a:has-text('New chat')",
        "button:has-text('New chat')",
        "[data-test-id='new-chat-button']",
    ]
    for selector in candidates:
        locator = page.locator(selector).first
        try:
            if await locator.count() and await locator.is_visible():
                await locator.click()
                await _human_pause(page)
                return
        except Exception:
            continue


async def _gemini_find_prompt_box(page, *, timeout_ms: int = 15_000) -> Any:
    candidates = [
        "div[role='textbox'][aria-label*='提示']",
        "div[role='textbox'][aria-label*='prompt']",
        "div[role='textbox'][aria-label*='输入']",
        "div[role='textbox']",
        "div[contenteditable='true'][role='textbox']",
        "div.ql-editor[contenteditable='true']",
        "div[contenteditable='true']",
        # Gemini UI can render the real editor inside a closed shadow root. In those variants we
        # can't reliably locate a textarea/contenteditable element, but clicking the input shell
        # still focuses the editor so we can type via page.keyboard.
        "input-area-v2",
        # Keep textarea as a late fallback for older Gemini variants. Newer Gemini UIs often
        # render a transient textarea during bootstrap before the real contenteditable editor is
        # ready; preferring textarea first makes send click time out on that stale shell.
        "textarea[aria-label*='prompt']",
        "textarea[aria-label*='提示']",
        "textarea[aria-label*='输入']",
        "textarea",
    ]
    deadline = time.time() + max(0.5, timeout_ms / 1000)
    textarea_seen_at: float | None = None
    while time.time() < deadline:
        textarea_fallback = None
        for selector in candidates:
            locator = page.locator(selector)
            count = await locator.count()
            if count <= 0:
                continue
            for i in range(min(count, 5)):
                item = locator.nth(i)
                try:
                    if await item.is_visible():
                        if selector.startswith("textarea"):
                            textarea_fallback = item
                            if textarea_seen_at is None:
                                textarea_seen_at = time.time()
                            continue
                        return item
                except PlaywrightTimeoutError:
                    continue
        if textarea_fallback is not None:
            now = time.time()
            grace = _gemini_textarea_fallback_grace_seconds()
            if (textarea_seen_at is not None and (now - textarea_seen_at) >= grace) or (deadline - now) <= 0.25:
                return textarea_fallback
        await page.wait_for_timeout(200)
    # Surface clearer errors when Gemini is blocked (captcha / region unsupported / sign-in redirect)
    # but the initial page check ran too early (Gemini landing can finish rendering after navigation).
    await _raise_if_gemini_blocked(page)
    raise RuntimeError("Cannot find Gemini prompt box. Are you logged in?")


_GEMINI_APP_MENTION_TOKENS: list[tuple[str, re.Pattern[str]]] = [
    (
        "google_drive",
        re.compile(r"@\s*Google\s*(云端硬盘|雲端硬碟|Drive)\b", re.I),
    ),
    (
        "google_docs",
        re.compile(r"@\s*Google\s*(文档|Docs?)\b", re.I),
    ),
    (
        "youtube",
        re.compile(r"@\s*YouTube\b", re.I),
    ),
]

_GEMINI_APP_MENU_LABEL_RES: dict[str, re.Pattern[str]] = {
    "google_drive": re.compile(r"^Google\s*(云端硬盘|雲端硬碟|Drive)\s*$", re.I),
    "google_docs": re.compile(r"^Google\s*(文档|Docs?)\s*$", re.I),
    "youtube": re.compile(r"YouTube", re.I),
}


def _gemini_parse_app_mentions(question: str) -> list[tuple[str, str]]:
    """
    Parse question into a sequence of tokens:
      - ('text', <literal text>)
      - ('mention', <app_key>) where app_key is e.g. 'google_drive'

    This enables reliable insertion of Gemini '@' app mentions (Drive/Docs) instead of
    sending a plain-text '@Google ...' string which does not activate the integration.
    """
    text = str(question or "")
    if not text:
        return [("text", "")]

    # Find the earliest next mention match among supported tokens.
    out: list[tuple[str, str]] = []
    idx = 0
    while idx < len(text):
        best = None
        best_key = ""
        for key, pat in _GEMINI_APP_MENTION_TOKENS:
            m = pat.search(text, idx)
            if m is None:
                continue
            if best is None or m.start() < best.start():
                best = m
                best_key = key
            elif best is not None and m.start() == best.start() and (m.end() - m.start()) > (best.end() - best.start()):
                best = m
                best_key = key
        if best is None:
            out.append(("text", text[idx:]))
            break
        if best.start() > idx:
            out.append(("text", text[idx : best.start()]))
        out.append(("mention", best_key))
        idx = best.end()
    return out


_GEMINI_APP_MENTION_FALLBACKS: dict[str, str] = {
    "google_drive": "@Google Drive",
    "google_docs": "@Google Docs",
    "youtube": "@YouTube",
}

async def _gemini_insert_app_mention(page, *, app_key: str, ctx: Context | None) -> bool:
    label_re = _GEMINI_APP_MENU_LABEL_RES.get(str(app_key))
    if label_re is None:
        raise RuntimeError(f"Unsupported Gemini app mention: {app_key}")

    prompt_box = await _gemini_find_prompt_box(page)
    prompt_box = await _gemini_focus_prompt_box(page, prompt_box)

    # Open the '@' app selector menu and click the desired app.
    await page.keyboard.type("@", delay=max(0, _type_delay_ms()) or 80)
    await page.wait_for_timeout(400)

    overlay = page.locator("div.cdk-overlay-pane:visible").first
    try:
        await overlay.wait_for(state="visible", timeout=10_000)
    except Exception:
        # Fallback: sometimes the menu is attached without a visible backdrop.
        overlay = page.locator("div.cdk-overlay-pane").last

    # Prefer exact menu entries; fall back to any element that matches the label.
    option = overlay.locator("button, div[role='button'], div[role='menuitem'], span").filter(has_text=label_re).first
    if not await option.count():
        option = page.locator("div.cdk-overlay-pane:visible").locator("text=/./").filter(has_text=label_re).first

    if not await option.count():
        await _ctx_info(ctx, f"Gemini '@' menu did not contain expected app: {app_key}")
        # Close the @ menu by pressing Escape
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        await _human_pause(page)
        return False

    await option.click()
    await _human_pause(page)
    await _gemini_dismiss_overlays(page)
    return True


async def _gemini_type_question_with_app_mentions(page, *, question: str, ctx: Context | None) -> None:
    prompt_box = await _gemini_find_prompt_box(page)
    tokens = _gemini_parse_app_mentions(question)
    if not any(t[0] == "mention" for t in tokens):
        try:
            await _type_question(prompt_box, question)
            return
        except Exception:
            # Fallback for Gemini UI variants where the editor lives in a closed shadow root.
            prompt_box = await _gemini_focus_prompt_box(page, prompt_box)
            try:
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
            except Exception:
                pass
            await page.keyboard.insert_text(question)
        return

    timeout_ms = _prompt_action_timeout_ms()
    try:
        await prompt_box.fill("", timeout=timeout_ms)
    except Exception:
        prompt_box = await _gemini_focus_prompt_box(page, prompt_box)
        try:
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
        except Exception:
            pass
    prompt_box = await _gemini_focus_prompt_box(page, prompt_box)

    for kind, value in tokens:
        if kind == "text":
            if value:
                # insert_text avoids Enter-key sending semantics and preserves inserted chips.
                await page.keyboard.insert_text(value)
                await _human_pause(page)
            continue
        if kind == "mention":
            success = await _gemini_insert_app_mention(page, app_key=value, ctx=ctx)
            if not success:
                # Type the fallback text smoothly so the input catches it.
                # Since we previously typed '@' and pressed Escape, we need to delete that '@' first.
                await page.keyboard.press("Backspace")
                fallback = _GEMINI_APP_MENTION_FALLBACKS.get(value, f"@{value}")
                await page.keyboard.insert_text(fallback)
                await _human_pause(page)
            continue
        raise RuntimeError(f"Unknown token kind: {kind}")


async def _gemini_focus_prompt_box(page, prompt_box):
    await _gemini_dismiss_overlays(page)
    candidates = [
        prompt_box,
        page.locator("div[role='textbox']").first,
        page.locator("div.ql-editor[contenteditable='true']").first,
        page.locator("input-area-v2").first,
        page.locator("textarea").first,
    ]
    for candidate in candidates:
        try:
            if not await candidate.count():
                continue
            if not await candidate.is_visible():
                continue
        except Exception:
            continue
        try:
            await candidate.click(timeout=1_500)
            await _human_pause(page)
            return candidate
        except Exception:
            continue
    return prompt_box


def _gemini_resolve_drive_files(drive_files: str | list[str] | None) -> list[str]:
    if not drive_files:
        return []
    raw: list[str]
    if isinstance(drive_files, str):
        raw = [drive_files]
    else:
        raw = list(drive_files)
    out: list[str] = []
    for item in raw:
        s = str(item or "").strip()
        if s:
            out.append(s)
    return out


async def _gemini_collect_send_observation(page, *, start_response_count: int) -> dict[str, Any]:
    before = max(0, int(start_response_count))
    observation: dict[str, Any] = {
        "response_count_before_send": before,
    }
    try:
        after = await page.locator("model-response").count()
    except Exception as exc:
        observation["send_observation_error"] = f"{type(exc).__name__}: {exc}"
        return observation
    after_count = max(0, int(after))
    response_started = after_count > before
    observation["response_count_after_error"] = after_count
    observation["response_started"] = bool(response_started)
    if not response_started:
        observation["send_without_new_response_start"] = True
    return observation


_GEMINI_UPLOAD_MENU_BUTTON_SELECTORS: tuple[str, ...] = (
    # Prefer stable structure-based selectors over localized aria-labels.
    "button[aria-controls='upload-file-menu']",
    "button.upload-card-button",
    "button[aria-label='打开输入区域菜单，以选择工具和上传内容类型']",
    "button[aria-label='Open input area menu to select tools and upload content types']",
    "button[aria-label*='输入区域菜单']",
    "button[aria-label*='上传内容类型']",
    "button[aria-label*='input area menu' i]",
    "button[aria-label*='upload content type' i]",
    "button[aria-label='打开文件上传菜单']",
    "button[aria-label='开启文件上传菜单']",
    "button[aria-label='開啟檔案上傳選單']",
    "button[aria-label='Open file upload menu']",
)

_GEMINI_DRIVE_MENU_ITEM_RE = re.compile(
    r"(从\s*云端硬盘\s*添加|從\s*雲端硬碟\s*(?:新增|加入|添加)|云端硬盘|雲端硬碟|Google\s*Drive|From\s*Drive|Add\s*from\s*Drive)",
    re.I,
)

_GEMINI_MORE_UPLOAD_OPTIONS_RE = re.compile(
    r"(更多上传选项|更多上傳選項|More\s*upload\s*options)",
    re.I,
)

_GEMINI_WORKSPACE_CONSENT_DIALOG_RE = re.compile(
    r"(关联\s*Google\s*Workspace|關聯\s*Google\s*Workspace|Connect\s*Google\s*Workspace|Link\s*Google\s*Workspace)",
    re.I,
)

_GEMINI_WORKSPACE_CONSENT_ACCEPT_RE = re.compile(
    r"^(关联|關聯|连接|連結|Connect|Link|继续|繼續|允许|允許|Allow)$",
    re.I,
)

_GEMINI_WORKSPACE_CONSENT_CANCEL_RE = re.compile(
    r"^(取消|關閉|关闭|Cancel|Close|Not\s*now)$",
    re.I,
)


async def _gemini_open_upload_menu(page, *, ctx: Context | None) -> None:
    async def _find_btn(*, timeout_seconds: float) -> Any | None:
        deadline = time.time() + float(max(0.1, timeout_seconds))
        while time.time() < deadline:
            for sel in _GEMINI_UPLOAD_MENU_BUTTON_SELECTORS:
                loc = page.locator(sel).first
                try:
                    if not await loc.count():
                        continue
                    if not await loc.is_visible():
                        continue
                    return loc
                except Exception:
                    continue
            await page.wait_for_timeout(250)
        return None

    await _gemini_dismiss_overlays(page)
    btn = await _find_btn(timeout_seconds=8.0)

    if btn is None:
        # Some Gemini variants occasionally show a "can't load conversation" toast which hides the upload UI.
        load_err_re = re.compile(r"(无法加载对话|Unable to load conversation|Couldn't load conversation|请尝试重新加载)", re.I)
        reload_reason = ""
        try:
            toast = page.get_by_text(load_err_re).first
            if await toast.count():
                try:
                    reload_reason = str(await toast.inner_text() or "").strip()
                except Exception:
                    reload_reason = "conversation load error"
        except Exception:
            reload_reason = ""

        if reload_reason:
            await _ctx_info(ctx, f"Gemini: conversation failed to load; reloading once ({reload_reason[:120]})")
            try:
                await page.reload(wait_until="domcontentloaded", timeout=_navigation_timeout_ms())
            except Exception:
                pass
            await _human_pause(page)
            await _gemini_dismiss_overlays(page)
            btn = await _find_btn(timeout_seconds=8.0)

    if btn is None:
        raise RuntimeError("Gemini upload menu button not found.")

    await _gemini_dismiss_overlays(page)
    await btn.click()
    await _human_pause(page)


async def _gemini_click_upload_menu_item(page, *, label_re: re.Pattern[str]) -> None:
    async def _visible_menu_candidates() -> list[Any]:
        selectors = [
            "div.cdk-overlay-pane:visible .mat-mdc-list-item, "
            "div.cdk-overlay-pane:visible button, "
            "div.cdk-overlay-pane:visible [role='menuitem'], "
            "div.cdk-overlay-pane:visible [role='button']",
            ".mat-mdc-list-item, button, [role='menuitem'], [role='button']",
        ]
        out: list[Any] = []
        for selector in selectors:
            locator = page.locator(selector)
            try:
                count = await locator.count()
            except Exception:
                count = 0
            for idx in range(min(80, count)):
                el = locator.nth(idx)
                try:
                    if not await el.is_visible():
                        continue
                except Exception:
                    continue
                out.append(el)
        return out

    async def _element_matches(el: Any, *, pattern: re.Pattern[str]) -> bool:
        bits: list[str] = []
        try:
            bits.append(str((await el.inner_text(timeout=500)) or "").strip())
        except Exception:
            pass
        for attr in ("aria-label", "title"):
            try:
                bits.append(str((await el.get_attribute(attr)) or "").strip())
            except Exception:
                pass
        hay = " ".join(part for part in bits if part)
        return bool(hay and pattern.search(hay))

    async def _visible_menu_labels() -> list[str]:
        labels: list[str] = []
        for el in await _visible_menu_candidates():
            bits: list[str] = []
            try:
                bits.append(str((await el.inner_text(timeout=500)) or "").strip())
            except Exception:
                pass
            for attr in ("aria-label", "title"):
                try:
                    bits.append(str((await el.get_attribute(attr)) or "").strip())
                except Exception:
                    pass
            label = " | ".join(part for part in bits if part)
            if label and label not in labels:
                labels.append(label)
            if len(labels) >= 12:
                break
        return labels

    async def _find_item(*, pattern: re.Pattern[str]) -> Any | None:
        for el in await _visible_menu_candidates():
            if await _element_matches(el, pattern=pattern):
                return el
        return None

    item = await _find_item(pattern=label_re)
    if item is None:
        more = await _find_item(pattern=_GEMINI_MORE_UPLOAD_OPTIONS_RE)
        if more is not None:
            try:
                await more.click()
                await _human_pause(page)
            except Exception:
                pass
            item = await _find_item(pattern=label_re)
    if item is None:
        visible = await _visible_menu_labels()
        suffix = f" visible_items={visible}" if visible else ""
        raise RuntimeError(f"Gemini upload menu item not found: {label_re.pattern}{suffix}")
    try:
        await item.scroll_into_view_if_needed(timeout=2_000)
    except Exception:
        pass
    await item.click()
    await _human_pause(page)


async def _gemini_maybe_accept_workspace_consent(
    page,
    *,
    ctx: Context | None,
    timeout_ms: int = 5_000,
) -> bool:
    deadline = time.time() + max(0.5, float(timeout_ms) / 1000.0)
    while time.time() < deadline:
        dialogs = page.locator("div.cdk-overlay-pane:visible, mat-dialog-container:visible, [role='dialog']:visible")
        try:
            count = await dialogs.count()
        except Exception:
            count = 0

        for idx in range(min(6, count)):
            dialog = dialogs.nth(idx)
            try:
                text = " ".join(((await dialog.inner_text(timeout=500)) or "").split())
            except Exception:
                text = ""
            if not text or not _GEMINI_WORKSPACE_CONSENT_DIALOG_RE.search(text):
                continue

            buttons = dialog.locator("button, [role='button']")
            try:
                button_count = await buttons.count()
            except Exception:
                button_count = 0

            for button_idx in range(min(12, button_count)):
                button = buttons.nth(button_idx)
                try:
                    if not await button.is_visible() or not await button.is_enabled():
                        continue
                    label_bits: list[str] = []
                    try:
                        label_bits.append(str((await button.inner_text(timeout=500)) or "").strip())
                    except Exception:
                        pass
                    for attr in ("aria-label", "title"):
                        try:
                            label_bits.append(str((await button.get_attribute(attr)) or "").strip())
                        except Exception:
                            pass
                    label = " ".join(bit for bit in label_bits if bit)
                    if not label or _GEMINI_WORKSPACE_CONSENT_CANCEL_RE.search(label):
                        continue
                    if not _GEMINI_WORKSPACE_CONSENT_ACCEPT_RE.search(label):
                        continue
                    await button.click()
                    await _human_pause(page)
                    await _ctx_info(ctx, "Gemini: accepted Google Workspace consent gate before opening Drive picker.")
                    return True
                except Exception:
                    continue
        await page.wait_for_timeout(200)
    return False


async def _gemini_open_drive_picker(page, *, ctx: Context | None, attempts: int = 3) -> None:
    last_error: Exception | None = None
    errors: list[str] = []
    max_attempts = max(1, int(attempts))
    for attempt in range(1, max_attempts + 1):
        await _gemini_wait_for_drive_picker_closed_before_retry(page, timeout_ms=2_500)
        try:
            await _gemini_open_upload_menu(page, ctx=ctx)
            await page.wait_for_timeout(250)
            await _gemini_click_upload_menu_item(page, label_re=_GEMINI_DRIVE_MENU_ITEM_RE)
            consent_clicked = await _gemini_maybe_accept_workspace_consent(page, ctx=ctx)
            await _gemini_wait_for_drive_picker_modal_open(
                page,
                timeout_ms=(18_000 if consent_clicked else (12_000 if attempt == 1 else 18_000)),
            )
            return
        except Exception as exc:
            last_error = exc
            errors.append(f"attempt_{attempt}:{type(exc).__name__}: {exc}")
            try:
                await _ctx_info(
                    ctx,
                    f"Gemini Drive picker attempt {attempt}/{max_attempts} failed: {type(exc).__name__}: {exc}",
                )
            except Exception:
                pass
            try:
                await _gemini_dismiss_overlays(page)
            except Exception:
                pass
            await page.wait_for_timeout(400)

    summary = "; ".join(errors[-max_attempts:])
    if last_error is None:
        raise RuntimeError("Gemini Drive picker unavailable.")
    raise RuntimeError(f"Gemini Drive picker unavailable after {max_attempts} attempt(s): {summary}") from last_error


async def _gemini_import_code_repo(page, *, repo_url: str, ctx: Context | None) -> None:
    repo = str(repo_url or "").strip()
    if not repo:
        return

    label_re = re.compile(
        r"(导入代码|導入代碼|導入程式碼|匯入程式碼|匯入代碼|Import\s*code|Import\s*repository)",
        re.I,
    )
    await _ctx_info(ctx, f"Gemini: importing code from repo URL… ({repo})")
    await _gemini_dismiss_overlays(page)

    opened = False
    try:
        await _gemini_open_upload_menu(page, ctx=ctx)
        item = page.locator("div.cdk-overlay-pane:visible button, div.cdk-overlay-pane:visible [role='menuitem']").filter(has_text=label_re).first
        if await item.count() and await item.is_visible():
            await item.click()
            await _human_pause(page)
            opened = True
    except Exception:
        opened = False

    if not opened:
        # Fallback: some Gemini variants expose Import code under the Tools drawer.
        try:
            await _gemini_select_tool(page, label_re=label_re)
        except Exception as exc:
            raise RuntimeError(f"Gemini import code unavailable: {exc}") from exc
        await _gemini_dismiss_overlays(page)

    dialog_hint_re = re.compile(
        r"(导入代码|導入代碼|導入程式碼|匯入程式碼|Import\s*code|GitHub|仓库|倉庫|repository|repo)",
        re.I,
    )
    dialog = None
    try:
        dialog = page.locator("mat-dialog-container:visible, [role='dialog']:visible").filter(has_text=dialog_hint_re).first
        if not await dialog.count():
            dialog = page.locator("div.cdk-overlay-pane:visible").filter(has_text=dialog_hint_re).first
    except Exception:
        dialog = None

    scope = dialog if dialog is not None and await dialog.count() else page

    input_selectors = [
        "input[type='url']",
        "input[placeholder*='GitHub']",
        "input[aria-label*='GitHub']",
        "input[placeholder*='仓库']",
        "input[aria-label*='仓库']",
        "input[placeholder*='倉庫']",
        "input[aria-label*='倉庫']",
        "input[placeholder*='程式']",
        "input[aria-label*='程式']",
        "input[placeholder*='URL']",
        "input[aria-label*='URL']",
        "input[type='text']",
        "textarea",
    ]

    url_box = None
    deadline = time.time() + 20.0
    last_err: Exception | None = None
    while time.time() < deadline and url_box is None:
        try:
            for sel in input_selectors:
                candidate = scope.locator(sel).first
                if await candidate.count() and await candidate.is_visible():
                    url_box = candidate
                    break
        except Exception as exc:
            last_err = exc
        if url_box is None:
            await page.wait_for_timeout(250)

    if url_box is None:
        msg = "Gemini Import code URL input not found."
        if last_err is not None:
            msg = f"{msg} ({type(last_err).__name__}: {last_err})"
        raise RuntimeError(msg)

    await url_box.click()
    await _human_pause(page)
    await url_box.fill(repo)
    await _human_pause(page)
    try:
        await url_box.press("Enter")
    except Exception:
        pass
    await _human_pause(page)

    confirm_re = re.compile(
        r"(导入|導入|匯入|Import|确定|確認|Confirm|继续|繼續|Continue|下一步|Next|添加|加入|Add)",
        re.I,
    )
    cancel_re = re.compile(r"(取消|Cancel|關閉|关闭|Close)", re.I)
    btn = None
    buttons = scope.locator("button, [role='button']")
    try:
        n = await buttons.count()
    except Exception:
        n = 0
    for idx in range(min(40, n)):
        candidate = buttons.nth(idx)
        try:
            if not await candidate.is_visible() or not await candidate.is_enabled():
                continue
            text = " ".join(((await candidate.inner_text(timeout=500)) or "").split())
            if not text:
                continue
            if cancel_re.search(text):
                continue
            if confirm_re.search(text):
                btn = candidate
                break
        except Exception:
            continue

    if btn is None:
        btn = scope.get_by_text(confirm_re).first
        if not await btn.count():
            raise RuntimeError("Gemini Import code confirm button not found.")

    await btn.click()
    await _human_pause(page)

    try:
        # Best-effort: the import dialog typically closes after submitting the repo URL.
        if dialog is not None and await dialog.count():
            await dialog.wait_for(state="hidden", timeout=30_000)
    except Exception:
        pass
    await _gemini_dismiss_overlays(page)


def _gemini_import_code_fallback_allowed(
    *,
    repo_url: str,
    drive_files: list[str],
    error_text: str,
) -> bool:
    if not _gemini_import_code_fail_open():
        return False
    if not str(repo_url or "").strip():
        return False
    if not list(drive_files or []):
        return False
    return _gemini_classify_error_type(error_text=error_text, fallback="RuntimeError") == "GeminiImportCodeUnavailable"


def _gemini_drive_attach_fallback_allowed(
    *,
    repo_url: str,
    drive_files: list[str],
    error_text: str,
) -> bool:
    if not _gemini_import_code_fail_open():
        return False
    if not str(repo_url or "").strip():
        return False
    if not list(drive_files or []):
        return False
    return _gemini_classify_error_type(error_text=error_text, fallback="RuntimeError") == "GeminiDriveAttachUnavailable"


async def _gemini_maybe_import_code_repo(
    page,
    *,
    repo_url: str,
    drive_files: list[str],
    ctx: Context | None,
) -> dict[str, Any] | None:
    repo = str(repo_url or "").strip()
    if not repo:
        return None
    try:
        await _gemini_import_code_repo(page, repo_url=repo, ctx=ctx)
        return None
    except Exception as exc:
        error_text = str(exc or "").strip()
        if not _gemini_import_code_fallback_allowed(
            repo_url=repo,
            drive_files=list(drive_files or []),
            error_text=error_text,
        ):
            raise
        payload = {
            "fallback_used": True,
            "repo_url": repo,
            "error_type": _gemini_classify_error_type(error_text=error_text, fallback=type(exc).__name__),
            "error": error_text,
            "reason": "import_code_unavailable_but_review_packet_present",
        }
        await _ctx_info(
            ctx,
            "Gemini import-code unavailable; continuing with review packet attachments and repo URL only.",
        )
        return payload


async def _gemini_maybe_attach_drive_files(
    page,
    *,
    drive_files: list[str],
    repo_url: str,
    ctx: Context | None,
) -> dict[str, Any] | None:
    files = [str(item or "").strip() for item in list(drive_files or []) if str(item or "").strip()]
    if not files:
        return None
    await _ctx_info(ctx, f"Gemini: attaching {len(files)} Drive file(s)…")
    attached_before_failure: list[str] = []
    for q in files:
        try:
            await _gemini_attach_drive_file(page, query=q, ctx=ctx)
            attached_before_failure.append(q)
            await _human_pause(page)
        except Exception as exc:
            error_text = str(exc or "").strip()
            if not _gemini_drive_attach_fallback_allowed(
                repo_url=repo_url,
                drive_files=files,
                error_text=error_text,
            ):
                raise
            payload = {
                "fallback_used": True,
                "repo_url": str(repo_url or "").strip(),
                "error_type": _gemini_classify_error_type(
                    error_text=error_text,
                    fallback=type(exc).__name__,
                ),
                "error": error_text,
                "reason": "drive_attach_unavailable_but_repo_present",
                "requested_drive_files": list(files),
                "attached_before_failure": list(attached_before_failure),
            }
            await _ctx_info(
                ctx,
                "Gemini Drive attachment UI unavailable; continuing with repo URL only.",
            )
            return payload
    return None


def _gemini_is_drive_picker_url(url: str) -> bool:
    raw = str(url or "").strip().lower()
    return "docs.google.com/picker" in raw


async def _gemini_drive_picker_popup_pages(page) -> list[Any]:
    context = getattr(page, "context", None)
    pages = list(getattr(context, "pages", []) or [])
    out: list[Any] = []
    for candidate in pages:
        if candidate is page:
            continue
        try:
            url = str(getattr(candidate, "url", "") or "")
        except Exception:
            url = ""
        if _gemini_is_drive_picker_url(url):
            out.append(candidate)
    return out


async def _gemini_collect_drive_picker_debug(page) -> dict[str, Any]:
    debug: dict[str, Any] = {
        "picker_frame_urls": [],
        "popup_pages": [],
        "dom_iframes": [],
        "visible_modal_count": None,
        "visible_overlays": [],
    }
    try:
        debug["picker_frame_urls"] = [
            str(getattr(frame, "url", "") or "")
            for frame in list(getattr(page, "frames", []) or [])
            if _gemini_is_drive_picker_url(str(getattr(frame, "url", "") or ""))
        ]
    except Exception:
        pass
    try:
        debug["popup_pages"] = [
            str(getattr(candidate, "url", "") or "")
            for candidate in await _gemini_drive_picker_popup_pages(page)
        ]
    except Exception:
        pass
    try:
        debug["visible_modal_count"] = int(await page.locator("div.google-picker.modal-dialog:visible").count())
    except Exception:
        pass
    try:
        debug["dom_iframes"] = await page.evaluate(
            """() => Array.from(document.querySelectorAll('iframe')).slice(0, 8).map((el) => {
                const style = window.getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return {
                  src: el.src || '',
                  title: el.getAttribute('title') || '',
                  visible: !(style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || '1') === 0 || r.width === 0 || r.height === 0),
                  rect: { x: r.x, y: r.y, width: r.width, height: r.height },
                };
            })""",
        )
    except Exception:
        pass
    try:
        debug["visible_overlays"] = await page.evaluate(
            """() => Array.from(document.querySelectorAll('div.cdk-overlay-pane, mat-dialog-container, [role=\"dialog\"]'))
                .map((el) => {
                    const style = window.getComputedStyle(el);
                    const r = el.getBoundingClientRect();
                    const visible = !(style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || '1') === 0 || r.width === 0 || r.height === 0);
                    return {
                        visible,
                        text: (el.innerText || '').trim().slice(0, 500),
                        className: el.className || '',
                    };
                })
                .filter((item) => item.visible && item.text)
                .slice(0, 6)""",
        )
    except Exception:
        pass
    return debug


async def _gemini_get_visible_drive_picker_frame(page, *, timeout_ms: int = 15_000):
    deadline = time.time() + max(1.0, float(timeout_ms) / 1000.0)
    last_err: Exception | None = None
    while time.time() < deadline:
        # Prefer the picker iframe inside the visible modal. Gemini keeps stale picker iframes in the
        # DOM (display:none), so scanning page.frames by URL is unreliable.
        try:
            modal = page.locator("div.google-picker.modal-dialog:visible").first
            if await modal.count():
                iframe = modal.locator("iframe[src*='docs.google.com/picker']").first
                if await iframe.count():
                    await iframe.wait_for(state="visible", timeout=2_000)
                    handle = await iframe.element_handle()
                    if handle is not None:
                        frame = await handle.content_frame()
                        if frame is not None:
                            return frame
        except Exception as exc:
            last_err = exc

        # Fallback: some variants expose the iframe without the modal wrapper.
        try:
            iframe = page.locator("iframe[src*='docs.google.com/picker']:visible").first
            if await iframe.count():
                handle = await iframe.element_handle()
                if handle is not None:
                    frame = await handle.content_frame()
                    if frame is not None:
                        return frame
        except Exception as exc:
            last_err = exc

        # Some Gemini variants surface the picker as a separate popup page instead of an iframe.
        try:
            popup_pages = await _gemini_drive_picker_popup_pages(page)
            if popup_pages:
                return popup_pages[-1]
        except Exception as exc:
            last_err = exc

        # When visibility heuristics drift, the newest attached picker frame is usually still
        # the right scope for later search/insert operations.
        try:
            picker_frames = [
                frame
                for frame in list(getattr(page, "frames", []) or [])
                if _gemini_is_drive_picker_url(str(getattr(frame, "url", "") or ""))
            ]
            if len(picker_frames) == 1:
                return picker_frames[0]
            if len(picker_frames) > 1:
                return picker_frames[-1]
        except Exception as exc:
            last_err = exc

        await page.wait_for_timeout(200)

    msg = "Timed out waiting for visible Google Drive picker iframe."
    if last_err is not None:
        msg = f"{msg} ({type(last_err).__name__}: {last_err})"
    try:
        picker_debug = await _gemini_collect_drive_picker_debug(page)
        if picker_debug:
            msg = f"{msg} picker_debug={json.dumps(picker_debug, ensure_ascii=False, sort_keys=True)}"
    except Exception:
        pass
    raise TimeoutError(msg)


async def _gemini_wait_for_drive_picker_modal_open(page, *, timeout_ms: int = 15_000) -> None:
    await _gemini_get_visible_drive_picker_frame(page, timeout_ms=timeout_ms)


async def _gemini_wait_for_drive_picker_search(page, *, timeout_ms: int = 20_000):
    deadline = time.time() + max(1.0, float(timeout_ms) / 1000.0)
    last_err: Exception | None = None
    selector = (
        "input[aria-label*='云端硬盘'], "
        "input[aria-label*='雲端硬碟'], "
        "input[aria-label*='Drive'], "
        "input[aria-label*='search'], "
        "input[type='text']"
    )
    while time.time() < deadline:
        try:
            frame = await _gemini_get_visible_drive_picker_frame(page, timeout_ms=2_000)
        except Exception as exc:
            last_err = exc
            await page.wait_for_timeout(200)
            continue

        try:
            loc = frame.locator(selector)
            n = await loc.count()
        except Exception as exc:
            last_err = exc
            await page.wait_for_timeout(200)
            continue

        for idx in range(min(6, n)):
            el = loc.nth(idx)
            try:
                if await el.is_visible():
                    return frame, el
            except Exception as exc:
                last_err = exc
                continue
        await page.wait_for_timeout(200)

    msg = "Timed out waiting for Drive picker search input."
    if last_err is not None:
        msg = f"{msg} ({type(last_err).__name__}: {last_err})"
    raise TimeoutError(msg)


async def _gemini_drive_picker_click_tab(picker_frame, *, label_re: re.Pattern[str]) -> bool:
    tab = picker_frame.locator("[role='tab'], button, [role='button']").filter(has_text=label_re).first
    if not await tab.count():
        return False
    try:
        await tab.click()
    except Exception:
        return False
    try:
        await picker_frame.wait_for_timeout(600)
    except Exception:
        pass
    return True


async def _gemini_drive_picker_find_item(picker_frame, *, name: str, timeout_ms: int = 15_000):
    deadline = time.time() + max(1.0, float(timeout_ms) / 1000.0)
    needle = str(name or "").strip()
    if not needle:
        return None
    rows = picker_frame.locator("[role='row'], [role='gridcell'], [role='option'], [role='listitem']")
    while time.time() < deadline:
        try:
            n = await rows.count()
        except Exception:
            n = 0
        for idx in range(min(80, n)):
            el = rows.nth(idx)
            try:
                if not await el.is_visible():
                    continue
                aria = (await el.get_attribute("aria-label")) or ""
                title = (await el.get_attribute("title")) or ""
                if needle and needle in (aria + " " + title):
                    return el
                txt = ""
                try:
                    txt = (await el.inner_text(timeout=250)) or ""
                except Exception:
                    txt = ""
                if needle and needle in txt:
                    return el
            except Exception:
                continue
        await picker_frame.wait_for_timeout(400)
    return None


async def _gemini_drive_picker_try_open_chatgptrest_uploads(
    page,
    *,
    picker_frame,
    search,
    filename: str,
    ctx: Context | None,
) -> bool:
    # When Drive "search" indexing is delayed, selecting from the known uploads folder is more
    # reliable than searching by filename. This is intentionally conservative: only used for
    # filenames that look like ChatgptREST uploads (<job_id>_<idx>_<basename>).
    try:
        await search.fill("", timeout=5_000)
        await search.press("Enter")
        await picker_frame.wait_for_timeout(300)
    except Exception:
        pass

    await _gemini_drive_picker_click_tab(
        picker_frame,
        label_re=re.compile(r"(我的云端硬盘|My Drive)", re.I),
    )

    folder = await _gemini_drive_picker_find_item(picker_frame, name="chatgptrest_uploads", timeout_ms=10_000)
    if folder is None:
        await _ctx_info(ctx, "Gemini Drive picker: uploads folder not visible (chatgptrest_uploads).")
        return False

    try:
        await folder.dblclick()
    except Exception:
        try:
            await folder.click()
            await picker_frame.wait_for_timeout(200)
            await page.keyboard.press("Enter")
        except Exception:
            return False

    try:
        await picker_frame.wait_for_timeout(800)
    except Exception:
        pass

    item = await _gemini_drive_picker_find_item(picker_frame, name=filename, timeout_ms=12_000)
    if item is None:
        await _ctx_info(ctx, f"Gemini Drive picker: file not found in uploads folder: {filename}")
        return False

    try:
        await item.click()
    except Exception:
        return False
    await picker_frame.wait_for_timeout(250)

    await _gemini_click_drive_picker_insert(page, picker_frame=picker_frame, timeout_ms=15_000)
    await _gemini_wait_for_drive_picker_close(page, timeout_ms=15_000)
    await page.wait_for_timeout(300)
    return True


async def _gemini_wait_for_drive_picker_close(page, *, timeout_ms: int = 15_000) -> None:
    deadline = time.time() + max(1.0, float(timeout_ms) / 1000.0)
    while time.time() < deadline:
        try:
            if not await page.locator("div.google-picker.modal-dialog:visible").count() and not await page.locator(
                "iframe[src*='docs.google.com/picker']:visible"
            ).count():
                return
        except Exception:
            # If the DOM is mid-transition, retry until the deadline.
            pass
        await page.wait_for_timeout(200)
    raise TimeoutError("Timed out waiting for Google Drive picker to close.")


async def _gemini_wait_for_drive_picker_closed_before_retry(page, *, timeout_ms: int = 2_500) -> None:
    # Best-effort: if the picker is half-open/stuck from a previous run, dismiss it before retrying.
    try:
        await _gemini_wait_for_drive_picker_close(page, timeout_ms=timeout_ms)
        return
    except Exception:
        pass
    try:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
    except Exception:
        pass
    try:
        await _gemini_wait_for_drive_picker_close(page, timeout_ms=timeout_ms)
    except Exception:
        pass


async def _gemini_click_drive_picker_insert(page, *, picker_frame, timeout_ms: int = 15_000) -> None:
    insert_re = re.compile(r"(插入|Insert)", re.I)
    deadline = time.time() + max(1.0, float(timeout_ms) / 1000.0)
    last_err: Exception | None = None

    async def _try_scope(scope) -> bool:
        nonlocal last_err
        try:
            # Prefer real buttons; then fall back to clicking the visible text (bubbles up).
            btn = scope.locator("button, [role='button']").filter(has_text=insert_re).first
            if await btn.count():
                try:
                    await btn.scroll_into_view_if_needed(timeout=2_000)
                except Exception:
                    pass
                if await btn.is_visible():
                    await btn.click()
                    return True

            txt = scope.get_by_text(insert_re).first
            if await txt.count():
                try:
                    await txt.scroll_into_view_if_needed(timeout=2_000)
                except Exception:
                    pass
                if await txt.is_visible():
                    await txt.click()
                    return True
        except Exception as exc:
            last_err = exc
        return False

    while time.time() < deadline:
        # The picker may render action buttons either inside the docs iframe or in an outer layer.
        scopes = [picker_frame]
        for fr in list(page.frames):
            try:
                url = str(getattr(fr, "url", "") or "")
            except Exception:
                url = ""
            if fr is picker_frame:
                continue
            if "docs.google.com/picker" in url:
                scopes.append(fr)
        scopes.append(page)

        for scope in scopes:
            if await _try_scope(scope):
                return
        await page.wait_for_timeout(250)

    msg = "Timed out waiting for Drive picker Insert button."
    if last_err is not None:
        msg = f"{msg} ({type(last_err).__name__}: {last_err})"
    raise TimeoutError(msg)


async def _gemini_attach_drive_file(page, *, query: str, ctx: Context | None) -> None:
    q = str(query or "").strip()
    if not q:
        return
    is_url = bool(re.match(r"^https?://", q, re.I))
    looks_like_upload = bool(re.match(r"^[0-9a-f]{32}_\\d{2}_", q, re.I))

    await _gemini_open_drive_picker(page, ctx=ctx)

    deadline = time.time() + 60.0
    last_err: Exception | None = None
    needle = q if len(q) <= 80 else q[-80:]
    while time.time() < deadline:
        frame = None
        try:
            frame, search = await _gemini_wait_for_drive_picker_search(page, timeout_ms=5_000)
            if not is_url and looks_like_upload:
                try:
                    if await _gemini_drive_picker_try_open_chatgptrest_uploads(
                        page,
                        picker_frame=frame,
                        search=search,
                        filename=q,
                        ctx=ctx,
                    ):
                        return
                except Exception:
                    pass
            await search.fill("", timeout=10_000)
            if is_url:
                await search.fill(q, timeout=15_000)
            else:
                await search.type(q, delay=max(10, _type_delay_ms()) or 50, timeout=15_000)
            await search.press("Enter")
            await frame.wait_for_timeout(1200)

            # Prefer selecting a row/cell with aria-label/title containing the filename.
            rows = frame.locator("[role='row']:visible, [role='gridcell']:visible, [role='option']:visible, [role='listitem']:visible")
            await rows.first.wait_for(state="visible", timeout=8_000)
            picked = False
            try:
                n = await rows.count()
            except Exception:
                n = 0
            for idx in range(min(60, n)):
                el = rows.nth(idx)
                try:
                    if not await el.is_visible():
                        continue
                    if is_url:
                        await el.click()
                        picked = True
                        break
                    aria = (await el.get_attribute("aria-label")) or ""
                    title = (await el.get_attribute("title")) or ""
                    if q and q in (aria + " " + title):
                        await el.click()
                        picked = True
                        break
                    txt = ""
                    try:
                        txt = (await el.inner_text(timeout=500)) or ""
                    except Exception:
                        txt = ""
                    if needle and needle in txt:
                        await el.click()
                        picked = True
                        break
                except Exception:
                    continue
            if not picked:
                await rows.first.click()
            await frame.wait_for_timeout(300)

            await _gemini_click_drive_picker_insert(page, picker_frame=frame, timeout_ms=15_000)
            await _gemini_wait_for_drive_picker_close(page, timeout_ms=15_000)
            await page.wait_for_timeout(300)
            return
        except Exception as exc:
            last_err = exc
            try:
                if frame is not None:
                    await frame.wait_for_timeout(1_000)
                else:
                    await page.wait_for_timeout(1_000)
            except Exception:
                pass
            continue

    msg = f"Drive file not found or not selectable: {q}"
    if last_err is not None:
        msg = f"{msg} ({type(last_err).__name__}: {last_err})"
    await _ctx_info(ctx, msg)
    raise RuntimeError(msg)


# ── Gemini thinking-trace capture ───────────────────────────────────────
#
# Gemini Deep Think renders a collapsible "显示思路 / Show thinking" section
# at the top of the response. This function expands it (if collapsed) and
# extracts the reasoning text.

_GEMINI_THINKING_TOGGLE_RE = re.compile(r"(显示思路|Show\s*(thoughts?|reasoning|thinking))", re.I)

_GEMINI_THINKING_TRACE_JS = r"""
(responseEl) => {
  if (!responseEl) return null;
  const MAX_CHARS = 32000;

  /* Strategy 1: Find a expandable/collapsible thinking section.
   * Gemini Deep Think typically renders a toggle button with text like
   * "显示思路" / "Show thinking" and the thinking content in a sibling/child. */
  const allEls = Array.from(responseEl.querySelectorAll("*"));
  const toggleRe = /(显示思路|Show\s*(thoughts?|reasoning|thinking))/i;
  const hideRe = /(隐藏思路|Hide\s*(thoughts?|reasoning|thinking))/i;

  for (const el of allEls) {
    const txt = (el.innerText || el.textContent || "").trim();
    if (!txt) continue;
    if (txt.length > 200) continue;
    if (!toggleRe.test(txt) && !hideRe.test(txt)) continue;

    /* Found the toggle. Look for thinking content nearby. */
    /* Check: parent > next sibling, or aria-controls target */
    let content = "";

    /* Check aria-controls */
    const controlsId = el.getAttribute("aria-controls");
    if (controlsId) {
      const panel = document.getElementById(controlsId);
      if (panel) {
        content = (panel.innerText || panel.textContent || "").trim();
      }
    }

    /* Check next siblings */
    if (!content) {
      let sib = el.nextElementSibling;
      for (let i = 0; i < 5 && sib; i++, sib = sib.nextElementSibling) {
        const sibText = (sib.innerText || sib.textContent || "").trim();
        if (sibText.length > 50 && sibText.length < MAX_CHARS) {
          content = sibText;
          break;
        }
      }
    }

    /* Check parent's next sibling */
    if (!content && el.parentElement) {
      let sib = el.parentElement.nextElementSibling;
      for (let i = 0; i < 3 && sib; i++, sib = sib.nextElementSibling) {
        const sibText = (sib.innerText || sib.textContent || "").trim();
        if (sibText.length > 50 && sibText.length < MAX_CHARS) {
          content = sibText;
          break;
        }
      }
    }

    /* Check grandparent container for collapsed sections */
    if (!content) {
      const container = el.closest("[class*='think'], [class*='thought'], [class*='reason']");
      if (container) {
        const allText = (container.innerText || container.textContent || "").trim();
        /* Remove the toggle label from the captured text */
        const cleanedText = allText.replace(toggleRe, "").replace(hideRe, "").trim();
        if (cleanedText.length > 50 && cleanedText.length < MAX_CHARS) {
          content = cleanedText;
        }
      }
    }

    if (content) {
      return {
        provider: "gemini",
        steps: [{ label: txt, content: content.slice(0, MAX_CHARS), has_content: true }],
        total_steps: 1,
        total_content_chars: Math.min(content.length, MAX_CHARS),
        toggle_label: txt,
      };
    }

    /* Toggle found but no adjacent content — may need to click to expand. */
    return {
      provider: "gemini",
      steps: [{ label: txt, content: "", has_content: false }],
      total_steps: 1,
      total_content_chars: 0,
      toggle_label: txt,
      needs_expand: true,
    };
  }

  /* Strategy 2: Look for any container with thinking-related class names
   * that contains substantial text (Gemini sometimes pre-expands the thinking). */
  const thinkContainers = responseEl.querySelectorAll(
    "[class*='think'], [class*='thought'], [class*='reason']"
  );
  for (const container of thinkContainers) {
    const cText = (container.innerText || container.textContent || "").trim();
    if (cText.length > 100 && cText.length < MAX_CHARS) {
      return {
        provider: "gemini",
        steps: [{ label: "thinking_container", content: cText.slice(0, MAX_CHARS), has_content: true }],
        total_steps: 1,
        total_content_chars: Math.min(cText.length, MAX_CHARS),
      };
    }
  }

  return null;
};
"""


async def _gemini_capture_thinking_trace(
    page,
    *,
    ctx: Context | None = None,
) -> dict[str, Any] | None:
    """Best-effort capture of Gemini Deep Think thinking trace from the DOM.

    Returns a structured dict with steps/content, or None if no thinking
    trace is detectable.
    """
    if not _truthy_env("GEMINI_CAPTURE_THINKING_TRACE", True):
        return None
    try:
        responses = page.locator("model-response")
        count = await responses.count()
        if count <= 0:
            return None
        response = responses.nth(count - 1)

        # First try: extract from DOM directly
        handle = await response.element_handle()
        if handle is None:
            return None
        raw = await page.evaluate(_GEMINI_THINKING_TRACE_JS, handle)
        if not raw or not isinstance(raw, dict):
            return None

        # If the thinking section needs expanding, try to click the toggle
        if raw.get("needs_expand"):
            try:
                toggle = response.get_by_text(_GEMINI_THINKING_TOGGLE_RE).first
                if await toggle.count() and await toggle.is_visible():
                    await toggle.click()
                    await page.wait_for_timeout(1000)
                    # Re-extract after expanding
                    raw2 = await page.evaluate(_GEMINI_THINKING_TRACE_JS, handle)
                    if raw2 and isinstance(raw2, dict) and raw2.get("total_content_chars", 0) > 0:
                        raw = raw2
            except Exception:
                pass

        raw["captured_at"] = time.time()
        return raw
    except Exception:
        return None


def _gemini_clean_response_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    lines = [ln.rstrip() for ln in raw.splitlines()]

    # Gemini can briefly surface transcript chrome or anchor-only labels before the
    # real answer arrives. Strip only exact label lines so we avoid accepting them
    # as a completed answer while keeping real content intact.
    leading_label_re = re.compile(
        r"("
        r"显示思路|顯示思路|"
        r"Show\s*(thoughts?|reasoning|thinking)|"
        r"分析|Analysis|"
        r"Gemini\s*(said|说|說)|"
        r"你说|你說|You\s*said"
        r")\s*",
        re.I,
    )

    while True:
        while lines and not lines[0].strip():
            lines.pop(0)
        if not lines or not re.fullmatch(leading_label_re, lines[0].strip()):
            break
        lines.pop(0)

    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


async def _gemini_extract_markdown_text(markdown) -> str:
    try:
        raw = (await markdown.inner_text(timeout=2_000)).strip()
    except PlaywrightTimeoutError:
        raw = ""

    if not raw:
        return ""

    if "\n" in raw or len(raw) < 400:
        return raw

    try:
        rebuilt = await markdown.evaluate(
            """
            (el) => {
              const normalize = (s) => String(s || '')
                .replace(/\\r\\n?/g, '\\n')
                .replace(/\\u00a0/g, ' ')
                .trim();

              const textOf = (node) => normalize((node && (node.innerText || node.textContent)) || '');
              const blocks = [];

              const push = (s) => {
                const t = normalize(s);
                if (!t) return;
                blocks.push(t);
              };

              const pushLines = (prefix, txt) => {
                const t = normalize(txt);
                if (!t) return;
                const lines = t.split('\\n');
                blocks.push(prefix + lines[0]);
                for (const ln of lines.slice(1)) {
                  blocks.push('  ' + ln);
                }
              };

              const handle = (node) => {
                if (!node || node.nodeType !== 1) return;
                const tag = String(node.tagName || '').toUpperCase();

                if (/^H[1-6]$/.test(tag)) {
                  const level = parseInt(tag.slice(1), 10) || 2;
                  push('#'.repeat(level) + ' ' + textOf(node));
                  return;
                }
                if (tag === 'P') {
                  push(textOf(node));
                  return;
                }
                if (tag === 'UL') {
                  const items = Array.from(node.querySelectorAll(':scope > li'));
                  if (items.length) {
                    for (const li of items) {
                      pushLines('- ', (li.innerText || li.textContent) || '');
                    }
                    return;
                  }
                }
                if (tag === 'OL') {
                  const items = Array.from(node.querySelectorAll(':scope > li'));
                  if (items.length) {
                    let i = 1;
                    for (const li of items) {
                      pushLines(i + '. ', (li.innerText || li.textContent) || '');
                      i += 1;
                    }
                    return;
                  }
                }
                if (tag === 'PRE') {
                  const code = String((node.innerText || node.textContent) || '')
                    .replace(/\\r\\n?/g, '\\n')
                    .trimEnd();
                  if (code.trim()) {
                    blocks.push('```\\n' + code + '\\n```');
                  }
                  return;
                }
                if (tag === 'BLOCKQUOTE') {
                  const t = textOf(node);
                  if (t) {
                    blocks.push(t.split('\\n').map((ln) => '> ' + ln).join('\\n'));
                  }
                  return;
                }
                if (tag === 'TABLE') {
                  const rows = Array.from(node.querySelectorAll('tr'));
                  const cellText = (cell) => normalize((cell && (cell.innerText || cell.textContent)) || '');
                  const getCells = (row) => Array.from(row.querySelectorAll('th,td')).map(cellText);
                  if (rows.length) {
                    const head = getCells(rows[0]);
                    if (head.length) {
                      const sep = head.map(() => '---');
                      const lines = [];
                      lines.push('| ' + head.join(' | ') + ' |');
                      lines.push('| ' + sep.join(' | ') + ' |');
                      for (const row of rows.slice(1)) {
                        const cells = getCells(row);
                        if (!cells.length) continue;
                        while (cells.length < head.length) cells.push('');
                        lines.push('| ' + cells.slice(0, head.length).join(' | ') + ' |');
                      }
                      blocks.push(lines.join('\\n'));
                      return;
                    }
                  }
                }

                const children = Array.from(node.children || []);
                const hasStructuredChildren = children.some((c) => {
                  const t = String((c && c.tagName) || '').toUpperCase();
                  return /^H[1-6]$/.test(t) || ['P','UL','OL','PRE','BLOCKQUOTE','TABLE'].includes(t);
                });

                if (hasStructuredChildren) {
                  for (const c of children) handle(c);
                  return;
                }
                push(textOf(node));
              };

              const children = Array.from(el.children || []);
              if (!children.length) return textOf(el);
              for (const c of children) handle(c);

              return blocks.join('\\n\\n').replace(/\\n{3,}/g, '\\n\\n').trim() || textOf(el);
            }
            """,
        )
    except Exception:
        rebuilt = ""

    rebuilt = str(rebuilt or "").strip()
    if rebuilt and "\n" in rebuilt:
        return rebuilt

    return raw


def _looks_like_gemini_transient_response(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return True
    # Gemini Pro UI can briefly render a standalone "分析" (analysis) marker before the real answer
    # appears (and without aria-busy/stop-button being visible). Treat such markers as not-done.
    if re.fullmatch(r"(分析|analysis)", s, re.I):
        return True
    if re.fullmatch(r"(正在研究|Researching websites)", s, re.I):
        return True

    # Gemini Deep Think can emit a placeholder like:
    #   "Responses with Deep Think can take some time ... Generating your response..."
    # Treat that as "not done" so we keep waiting.
    normalized = s.replace("…", "...").lower()
    if len(s) <= 800 and ("generating your response" in normalized or "正在生成" in s):
        if any(tok in normalized for tok in ("deep think", "check back", "back later")) or any(tok in s for tok in ("稍后", "一会儿")):
            return True
        if normalized.strip() in {"generating your response", "generating your response..."}:
            return True
        if s.strip().startswith("正在生成") and len(s.strip()) <= 80:
            return True

    return False


_GEMINI_DEEP_THINK_OVERLOADED_RE = re.compile(
    r"("
    r"a lot of people are using deep think right now|"
    r"unselect it from your tools|"
    r"try again in a bit|"
    r"deep think is busy|"
    r"deep think is currently unavailable"
    r")",
    re.I,
)


# Deep Think label variants drift across locales / A-B experiments.
# Keep this broad enough to catch known variants while still targeting Deep Think UI entries.
_GEMINI_DEEP_THINK_TOOL_RE = re.compile(
    r"(Deep\s*Think|Thinking\s+with\s+3\s*Pro|深度思考|深入思考|3\s*Pro\s*思考)",
    re.I,
)

_GEMINI_DEEP_THINK_RETRY_BUTTON_RE = re.compile(
    r"("
    r"try again|"
    r"retry|"
    r"重试|"
    r"再试|"
    r"再试一次|"
    r"重新生成"
    r")",
    re.I,
)


def _looks_like_gemini_deep_think_overloaded(text: str) -> bool:
    trimmed = (text or "").strip()
    if not trimmed:
        return False
    if len(trimmed) > 1200:
        return False
    normalized = trimmed.replace("…", "...")
    if _GEMINI_DEEP_THINK_OVERLOADED_RE.search(normalized):
        return True
    _RETRY_TOKENS_CJK = ("很多人", "人太多", "拥挤", "稍后", "一会儿", "再试", "重试", "大量")
    # Best-effort CJK variants (exact "深度思考").
    if "深度思考" in normalized and any(tok in normalized for tok in _RETRY_TOKENS_CJK):
        return True
    # Mixed CN/EN: Gemini may return "大量用户正在使用 Deep Think ... 请稍后再试"
    if re.search(r"deep\s*think", normalized, re.I) and any(tok in normalized for tok in _RETRY_TOKENS_CJK):
        return True
    # Fuzzy CJK: "深度的思考", "深度 思考" etc. (particle insertion)
    if re.search(r"深度.{0,2}思考", normalized) and any(tok in normalized for tok in _RETRY_TOKENS_CJK):
        return True
    return False


async def _gemini_click_deep_think_retry(page, *, ctx: Context | None = None) -> bool:
    responses = page.locator("model-response")
    try:
        count = await responses.count()
    except Exception:
        count = 0

    candidate_locators = []
    if count > 0:
        latest = responses.nth(count - 1)
        candidate_locators.extend(
            [
                latest.locator("button").filter(has_text=_GEMINI_DEEP_THINK_RETRY_BUTTON_RE),
                latest.locator("[role='button']").filter(has_text=_GEMINI_DEEP_THINK_RETRY_BUTTON_RE),
            ]
        )
    candidate_locators.extend(
        [
            page.locator("button").filter(has_text=_GEMINI_DEEP_THINK_RETRY_BUTTON_RE),
            page.locator("[role='button']").filter(has_text=_GEMINI_DEEP_THINK_RETRY_BUTTON_RE),
        ]
    )

    for loc in candidate_locators:
        try:
            n = await loc.count()
        except Exception:
            n = 0
        if n <= 0:
            continue
        for i in range(min(int(n), 5)):
            btn = loc.nth(i)
            try:
                if not await btn.is_visible():
                    continue
                try:
                    enabled = await btn.is_enabled()
                except Exception:
                    enabled = True
                if not enabled:
                    continue
                try:
                    label = " ".join(((await btn.inner_text()) or "").split())
                except Exception:
                    label = ""
                if ctx:
                    if label:
                        await _ctx_info(ctx, f"Gemini Deep Think: clicking retry control ({label!r})")
                    else:
                        await _ctx_info(ctx, "Gemini Deep Think: clicking retry control")
                try:
                    await btn.scroll_into_view_if_needed()
                except Exception:
                    pass
                await btn.click()
                await _human_pause(page)
                return True
            except Exception:
                continue
    return False


def _gemini_deep_think_retry_attempts() -> int:
    """In-place retries per round (clicking retry button in same conversation)."""
    raw = (os.environ.get("GEMINI_DEEP_THINK_INPLACE_RETRIES_PER_ROUND") or
           os.environ.get("GEMINI_DEEP_THINK_RETRY_ATTEMPTS") or "").strip()
    try:
        value = int(raw) if raw else 3
    except Exception:
        value = 3
    return max(0, min(int(value), 10))


def _gemini_deep_think_new_conv_max_rounds() -> int:
    """Max new-conversation rounds for Deep Think overloaded retry."""
    raw = (os.environ.get("GEMINI_DEEP_THINK_NEW_CONV_MAX_ROUNDS") or "").strip()
    try:
        value = int(raw) if raw else 5
    except Exception:
        value = 5
    return max(1, min(int(value), 10))


def _gemini_deep_think_retry_wait_timeout_seconds() -> int:
    raw = (os.environ.get("GEMINI_DEEP_THINK_RETRY_WAIT_TIMEOUT_SECONDS") or "").strip()
    try:
        value = int(raw) if raw else 180
    except Exception:
        value = 180
    return max(30, min(int(value), 900))


async def _gemini_retry_deep_think_overloaded_answer(
    page,
    *,
    answer: str,
    timeout_seconds: int,
    ctx: Context | None,
    new_conversation_sender=None,
) -> tuple[str, dict[str, Any] | None]:
    """Retry Deep Think when overloaded, preferring new conversations.

    Strategy:
      Round 1: in-place retry (click retry button) up to N times in current conversation
      Round 2..M: open NEW conversation via new_conversation_sender callback
      If all rounds exhausted -> return last answer + retry info

    Args:
        new_conversation_sender: async callable() -> (answer_str, conversation_url)
            Creates a new Gemini page, selects Deep Think, sends the question,
            waits for the answer, and closes the page. Returns (answer, url).
            If None, only in-place retry is attempted (legacy behavior).
    """
    current = str(answer or "")
    inplace_retries = _gemini_deep_think_retry_attempts()
    max_rounds = _gemini_deep_think_new_conv_max_rounds()
    wait_timeout = _gemini_deep_think_retry_wait_timeout_seconds()

    if not _looks_like_gemini_deep_think_overloaded(current):
        return current, None

    rounds: list[dict[str, Any]] = []

    # --- Round 1: in-place retry in the existing page ---
    round_info: dict[str, Any] = {"round": 1, "type": "inplace", "attempts": []}
    for idx in range(1, inplace_retries + 1):
        if not _looks_like_gemini_deep_think_overloaded(current):
            break
        attempt_info: dict[str, Any] = {"attempt": idx}
        if ctx:
            await _ctx_info(ctx, f"Gemini Deep Think overloaded: in-place retry {idx}/{inplace_retries} (round 1)")
        clicked = await _gemini_click_deep_think_retry(page, ctx=ctx)
        attempt_info["clicked"] = bool(clicked)
        if not clicked:
            attempt_info["reason"] = "retry_control_not_found"
            round_info["attempts"].append(attempt_info)
            break
        try:
            response_count = await page.locator("model-response").count()
        except Exception:
            response_count = 0
        retry_timeout = max(30, min(int(timeout_seconds), int(wait_timeout)))
        try:
            current = await _gemini_wait_for_model_response(
                page,
                started_at=time.time(),
                start_response_count=max(0, int(response_count) - 1),
                timeout_seconds=retry_timeout,
                min_chars=0,
                require_new=False,
            )
        except Exception as exc:
            attempt_info["wait_error"] = f"{type(exc).__name__}: {exc}"
            round_info["attempts"].append(attempt_info)
            break

        overloaded = _looks_like_gemini_deep_think_overloaded(current)
        attempt_info["answer_chars"] = len((current or "").strip())
        attempt_info["overloaded"] = bool(overloaded)
        round_info["attempts"].append(attempt_info)
        if not overloaded:
            break

    round_info["final_overloaded"] = bool(_looks_like_gemini_deep_think_overloaded(current))
    rounds.append(round_info)

    # --- Rounds 2..M: new conversation retry ---
    if _looks_like_gemini_deep_think_overloaded(current) and new_conversation_sender is not None:
        for round_num in range(2, max_rounds + 1):
            if not _looks_like_gemini_deep_think_overloaded(current):
                break

            round_info = {"round": round_num, "type": "new_conversation", "attempts": []}
            if ctx:
                await _ctx_info(
                    ctx,
                    f"Gemini Deep Think overloaded: opening new conversation (round {round_num}/{max_rounds})"
                )

            # Call the sender to open a new page, send, and get the answer
            try:
                new_answer, new_url = await new_conversation_sender()
                current = str(new_answer or "")
                round_info["conversation_url"] = str(new_url or "")
                round_info["answer_chars"] = len(current.strip())
                round_info["final_overloaded"] = bool(_looks_like_gemini_deep_think_overloaded(current))
            except Exception as exc:
                round_info["error"] = f"{type(exc).__name__}: {exc}"
                round_info["final_overloaded"] = True
                rounds.append(round_info)
                continue

            rounds.append(round_info)
            if not _looks_like_gemini_deep_think_overloaded(current):
                break

    final_overloaded = bool(_looks_like_gemini_deep_think_overloaded(current))
    return current, {
        "max_rounds": int(max_rounds),
        "inplace_retries_per_round": int(inplace_retries),
        "rounds": rounds,
        "final_overloaded": final_overloaded,
    }


class _GeminiModeQuotaError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        not_before: float | None = None,
        reset_at: float | None = None,
        notice: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.not_before = not_before
        self.reset_at = reset_at
        self.notice = notice


_GEMINI_USAGE_LIMIT_RE = re.compile(r"(用量限额|用量限制|usage limit|usage limits?)", re.I)
_GEMINI_USAGE_LIMIT_FALLBACK_RE = re.compile(r"(其他模型|different model|another model|use other model)", re.I)
_GEMINI_USAGE_LIMIT_RESET_RE = re.compile(r"(将于|重置|reset)", re.I)


def _gemini_parse_usage_limit_reset_at(text: str, *, now: datetime.datetime | None = None) -> float | None:
    """
    Best-effort parse for Gemini UI quota banners like:
      - 用量限额将于 1月1日 15:39 重置
      - 用量限额将于 15:39 重置
    Returns a unix timestamp (seconds) in the local timezone, or None if unknown.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    if now is None:
        now = datetime.datetime.now().astimezone()
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)

    m = re.search(r"用量限额将于\s*(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})\s*重置", raw)
    if m:
        month, day, hour, minute = (int(x) for x in m.groups())
        year = now.year
        try:
            reset = datetime.datetime(year, month, day, hour, minute, tzinfo=now.tzinfo)
        except ValueError:
            return None
        if reset < now - datetime.timedelta(minutes=1):
            try:
                reset = reset.replace(year=year + 1)
            except ValueError:
                return None
        return reset.timestamp()

    m = re.search(r"用量限额将于\s*(\d{1,2}):(\d{2})\s*重置", raw)
    if m:
        hour, minute = (int(x) for x in m.groups())
        try:
            reset = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            return None
        if reset < now - datetime.timedelta(minutes=1):
            reset = reset + datetime.timedelta(days=1)
        return reset.timestamp()

    return None


def _gemini_quota_notice_from_text(text: str, *, now: datetime.datetime | None = None) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if not _GEMINI_USAGE_LIMIT_RE.search(raw):
        return None

    # Avoid reacting to unrelated banners by requiring a "mode/tool" hint or an explicit fallback/reset clue.
    if not (
        re.search(r"(思考|thinking\b|pro\b|deep\s*think\b)", raw, re.I)
        or _GEMINI_USAGE_LIMIT_FALLBACK_RE.search(raw)
        or _GEMINI_USAGE_LIMIT_RESET_RE.search(raw)
    ):
        return None

    if now is None:
        now = datetime.datetime.now().astimezone()
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    now_ts = now.timestamp()

    reset_at = _gemini_parse_usage_limit_reset_at(raw, now=now)
    if reset_at is not None:
        retry_after_seconds = max(60, int(math.ceil(reset_at - now_ts)))
        not_before = max(now_ts + 60.0, float(reset_at))
    else:
        retry_after_seconds = 3600
        not_before = now_ts + float(retry_after_seconds)

    # Keep the payload small (avoid dumping full page text).
    snippet = _coerce_error_text(raw.replace("\n", " "), limit=520)
    return {
        "reset_at": reset_at,
        "retry_after_seconds": int(retry_after_seconds),
        "not_before": float(not_before),
        "notice": snippet,
    }


_GEMINI_MODE_SELECTOR_RE = re.compile(r"(思考|Thinking|快速|Fast|Pro|模式|Mode)", re.I)


def _gemini_normalize_mode_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _gemini_mode_is_pro(text: str) -> bool:
    norm = _gemini_normalize_mode_text(text)
    if not norm:
        return False
    return bool(re.search(r"^pro\b|\bpro\b", norm, re.I))


def _gemini_mode_is_ambiguous(text: str) -> bool:
    norm = _gemini_normalize_mode_text(text)
    if not norm:
        return False
    return bool(re.fullmatch(r"(模式|mode|模式选择|mode\s*selector)", norm, re.I))


async def _gemini_mode_menu_overlay(page, *, label_re: re.Pattern[str] | None = None) -> Any:
    # Gemini mode/tool menus are rendered in Angular overlay panes.
    overlay_selectors = [
        "div.cdk-overlay-pane:visible",
        "div.cdk-overlay-pane",
    ]
    for sel in overlay_selectors:
        try:
            loc = page.locator(sel)
            count = await loc.count()
        except Exception:
            continue
        for i in range(min(int(count), 8)):
            pane = loc.nth(i)
            try:
                if not await pane.is_visible():
                    continue
            except Exception:
                continue
            if label_re is None:
                return pane
            try:
                cand = pane.locator("[role='menuitemradio'],[role='menuitem'],button").filter(has_text=label_re)
                if await cand.count():
                    return pane
            except Exception:
                continue
    return page.locator("div.cdk-overlay-pane").first


async def _gemini_click_mode_option(page, *, label_re: re.Pattern[str]) -> bool:
    overlay = await _gemini_mode_menu_overlay(page, label_re=label_re)
    try:
        await overlay.wait_for(state="visible", timeout=10_000)
    except Exception:
        return False

    # Newer Gemini UIs sometimes render mode items as role=menuitemradio
    # instead of plain <button>; include both to avoid selector drift.
    option = overlay.locator("[role='menuitemradio'],[role='menuitem'],button").filter(has_text=label_re).first
    try:
        if not await option.count():
            return False
    except Exception:
        return False

    try:
        enabled = await option.is_enabled()
    except Exception:
        enabled = True
    if not enabled:
        return False

    try:
        await option.scroll_into_view_if_needed()
    except Exception:
        pass
    await option.click()
    await _human_pause(page)
    return True


async def _gemini_find_mode_button(page) -> Any | None:
    """
    Gemini web uses a mode selector (Fast / Thinking / Pro).

    The DOM may contain multiple matching buttons (some disabled/hidden).
    Prefer a visible+enabled button, else fall back to visible, else first match.
    """
    # Prefer stable mode/tool menu buttons when present.
    preferred_selectors = [
        "[data-test-id='bard-mode-menu-button']",
        "[data-test-id='bard-mode-menu-button'] button",
        "bard-mode-switcher [aria-haspopup='menu'] button",
        "bard-mode-switcher [aria-haspopup='menu']",
        "button.toolbox-drawer-button",
    ]
    for sel in preferred_selectors:
        preferred = page.locator(sel).first
        try:
            if await preferred.count() and await preferred.is_visible():
                if await preferred.is_enabled():
                    return preferred
                return preferred
        except Exception:
            continue

    # Fallback 1: mode-like labels rendered in visible buttons.
    btns = page.locator("button").filter(has_text=_GEMINI_MODE_SELECTOR_RE)
    try:
        n = await btns.count()
    except Exception:
        n = 0
    if n > 0:
        best_visible = None
        for i in range(min(int(n), 20)):
            cand = btns.nth(i)
            try:
                if not await cand.is_visible():
                    continue
                best_visible = cand
                if await cand.is_enabled():
                    return cand
            except Exception:
                continue
        if best_visible is not None:
            return best_visible
        return btns.first

    # Fallback 2: generic popup menu buttons nearest to composer area.
    generic = page.locator("button[aria-haspopup='menu']")
    try:
        gcount = await generic.count()
    except Exception:
        gcount = 0
    if gcount <= 0:
        return None
    best_cand = None
    best_score: float | None = None
    for i in range(min(int(gcount), 40)):
        cand = generic.nth(i)
        try:
            if not await cand.is_visible():
                continue
            box = await cand.bounding_box()
            if not box:
                continue
            # Prefer controls nearer the lower half (composer/tool area), avoid top-nav menus.
            score = float(box.get("y", 0.0))
            if best_score is None or score > best_score:
                best_score = score
                best_cand = cand
        except Exception:
            continue
    return best_cand


async def _gemini_current_mode_text(page) -> str:
    btn = await _gemini_find_mode_button(page)
    if btn is None:
        return ""
    try:
        return _gemini_normalize_mode_text((await btn.inner_text()) or "")
    except Exception:
        return ""


async def _gemini_raise_if_quota_limited(page, *, wanted: str, ctx: Context | None) -> None:
    hint = ""
    try:
        hint = (await page.locator("body").inner_text(timeout=2_000)).strip()
    except Exception:
        hint = ""

    info = _gemini_quota_notice_from_text(hint)
    if not info:
        return

    reset_at = info.get("reset_at")
    reset_msg = ""
    try:
        if isinstance(reset_at, (int, float)) and float(reset_at) > 0:
            reset_dt = datetime.datetime.fromtimestamp(float(reset_at), tz=datetime.datetime.now().astimezone().tzinfo)
            reset_msg = f" (reset_at={reset_dt.isoformat(timespec='minutes')})"
    except Exception:
        reset_msg = ""

    msg = (
        f"Gemini {wanted} mode appears quota-limited; refusing to send to avoid degraded responses.{reset_msg} "
        f"notice={info.get('notice')!r}"
    )
    await _ctx_info(ctx, msg)
    raise _GeminiModeQuotaError(
        msg,
        retry_after_seconds=int(info.get("retry_after_seconds") or 3600),
        not_before=float(info.get("not_before") or (time.time() + 3600.0)),
        reset_at=(float(reset_at) if isinstance(reset_at, (int, float)) else None),
        notice=str(info.get("notice") or ""),
    )


def _gemini_mode_switch_fail_open() -> bool:
    # Fail-open by default: when the UI cannot switch modes (selector missing / A/B),
    # continue in the current mode instead of failing the whole job.
    return _truthy_env("GEMINI_MODE_SWITCH_FAIL_OPEN", True)


async def _gemini_ensure_thinking_mode(page, *, ctx: Context | None) -> None:
    # Gemini web recently added a 3-mode selector: Fast / Thinking / Pro.
    btn = await _gemini_find_mode_button(page)
    if btn is None:
        if _gemini_mode_switch_fail_open():
            await _ctx_info(ctx, "Gemini mode selector not found; continuing without switching (wanted=Thinking).")
            await _gemini_raise_if_quota_limited(page, wanted="Thinking", ctx=ctx)
            return
        raise RuntimeError("Gemini mode selector not found.")

    current = " ".join(((await btn.inner_text()) or "").split())
    if re.search(r"^(思考|Thinking)\b", current, re.I):
        await _gemini_raise_if_quota_limited(page, wanted="Thinking", ctx=ctx)
        return

    await _ctx_info(ctx, "Gemini: switching mode → Thinking")

    try:
        await btn.scroll_into_view_if_needed()
    except Exception:
        pass
    try:
        enabled = await btn.is_enabled()
    except Exception:
        enabled = True
    if not enabled:
        await _gemini_raise_if_quota_limited(page, wanted="Thinking", ctx=ctx)
        msg = "Gemini mode selector is disabled; cannot switch mode."
        if _gemini_mode_switch_fail_open():
            await _ctx_info(ctx, msg + " Continuing without switching.")
            return
        raise RuntimeError(msg)

    await btn.click()
    await _human_pause(page)
    clicked = await _gemini_click_mode_option(page, label_re=re.compile(r"(思考|Thinking)", re.I))
    if clicked:
        current = await _gemini_current_mode_text(page)
        if not re.search(r"^(思考|Thinking)\b", current, re.I):
            msg = f"Gemini mode switch did not apply (wanted=Thinking, current={current!r})."
            if _gemini_mode_switch_fail_open():
                await _ctx_info(ctx, msg + " Continuing without switching.")
                return
            raise RuntimeError(msg)
        await _gemini_raise_if_quota_limited(page, wanted="Thinking", ctx=ctx)
        return

    await page.keyboard.press("Escape")
    await _human_pause(page)
    if _gemini_mode_switch_fail_open():
        await _ctx_info(ctx, "Gemini Thinking mode option not found; continuing without switching.")
        await _gemini_raise_if_quota_limited(page, wanted="Thinking", ctx=ctx)
        return
    raise RuntimeError("Gemini Thinking mode option not found.")


async def _gemini_ensure_pro_mode(page, *, ctx: Context | None) -> None:
    btn = await _gemini_find_mode_button(page)
    if btn is None:
        # DOM can re-render around import-code / tool toggles; retry once before failing.
        try:
            await page.wait_for_timeout(350)
        except Exception:
            pass
        btn = await _gemini_find_mode_button(page)
    if btn is None:
        if _gemini_mode_switch_fail_open():
            await _ctx_info(ctx, "Gemini mode selector not found; continuing without switching (wanted=Pro).")
            await _gemini_raise_if_quota_limited(page, wanted="Pro", ctx=ctx)
            return
        raise RuntimeError("Gemini mode selector not found.")

    current = _gemini_normalize_mode_text((await btn.inner_text()) or "")
    if _gemini_mode_is_pro(current):
        await _gemini_raise_if_quota_limited(page, wanted="Pro", ctx=ctx)
        return

    await _ctx_info(ctx, "Gemini: switching mode → Pro")

    try:
        await btn.scroll_into_view_if_needed()
    except Exception:
        pass
    try:
        enabled = await btn.is_enabled()
    except Exception:
        enabled = True
    if not enabled:
        await _gemini_raise_if_quota_limited(page, wanted="Pro", ctx=ctx)
        msg = "Gemini mode selector is disabled; cannot switch mode."
        if _gemini_mode_switch_fail_open():
            await _ctx_info(ctx, msg + " Continuing without switching.")
            return
        raise RuntimeError(msg)

    await btn.click()
    await _human_pause(page)
    clicked = await _gemini_click_mode_option(page, label_re=re.compile(r"\bPro\b", re.I))
    if clicked:
        current = await _gemini_current_mode_text(page)
        if not _gemini_mode_is_pro(current):
            if _gemini_mode_is_ambiguous(current):
                # Some A/B variants show generic "Mode/模式" even when Pro is selected.
                await _ctx_info(ctx, f"Gemini mode text ambiguous after Pro switch ({current!r}); continuing.")
                await _gemini_raise_if_quota_limited(page, wanted="Pro", ctx=ctx)
                return
            msg = f"Gemini mode switch did not apply (wanted=Pro, current={current!r})."
            if _gemini_mode_switch_fail_open():
                await _ctx_info(ctx, msg + " Continuing without switching.")
                return
            raise RuntimeError(msg)
        await _gemini_raise_if_quota_limited(page, wanted="Pro", ctx=ctx)
        return

    await page.keyboard.press("Escape")
    await _human_pause(page)
    current_after = await _gemini_current_mode_text(page)
    if _gemini_mode_is_pro(current_after):
        await _ctx_info(ctx, "Gemini Pro option not found but current mode is Pro; continuing.")
        await _gemini_raise_if_quota_limited(page, wanted="Pro", ctx=ctx)
        return
    if _gemini_mode_is_ambiguous(current_after):
        await _ctx_info(ctx, f"Gemini Pro option not found and mode label is ambiguous ({current_after!r}); continuing.")
        await _gemini_raise_if_quota_limited(page, wanted="Pro", ctx=ctx)
        return
    if _gemini_mode_switch_fail_open():
        await _ctx_info(ctx, "Gemini Pro mode option not found; continuing without switching.")
        await _gemini_raise_if_quota_limited(page, wanted="Pro", ctx=ctx)
        return
    raise RuntimeError("Gemini Pro mode option not found.")


async def _gemini_locator_has_visible(locator, *, max_scan: int = 10) -> bool:
    try:
        count = await locator.count()
    except Exception:
        return False
    for i in range(min(int(count), max(1, int(max_scan)))):
        try:
            if await locator.nth(i).is_visible():
                return True
        except Exception:
            continue
    return False


async def _gemini_first_visible(locator, *, max_scan: int = 10) -> Any | None:
    try:
        count = await locator.count()
    except Exception:
        return None
    for i in range(min(int(count), max(1, int(max_scan)))):
        item = locator.nth(i)
        try:
            if await item.is_visible():
                return item
        except Exception:
            continue
    return None


_GEMINI_DEEP_RESEARCH_TOOL_FALLBACK_RE = re.compile(
    r"("
    r"deep\s*research|"
    r"research\s*(mode|tool)|"
    r"(深度|深入)\s*(研究|調研|调研)|"
    r"深度研究|深入研究|深度調研|深度调研|深入調研|深入调研|"
    r"調研|调研"
    r")",
    re.I,
)


def _gemini_is_deep_research_label_pattern(label_re: re.Pattern[str]) -> bool:
    pattern = str(getattr(label_re, "pattern", "") or "")
    if not pattern:
        return False
    lower = pattern.lower()
    if ("deep" in lower and "research" in lower) or ("深入研究" in pattern) or ("深度研究" in pattern):
        return True
    if ("调研" in pattern) or ("調研" in pattern):
        return True
    return False


def _gemini_tool_label_matches(*, label_re: re.Pattern[str], text: str) -> bool:
    hay = str(text or "").strip()
    if not hay:
        return False
    try:
        if label_re.search(hay):
            return True
    except Exception:
        pass
    if _gemini_is_deep_research_label_pattern(label_re):
        return bool(_GEMINI_DEEP_RESEARCH_TOOL_FALLBACK_RE.search(hay))
    return False


async def _gemini_open_tools_drawer(page) -> Any:
    try:
        await _gemini_find_prompt_box(page, timeout_ms=12_000)
    except Exception:
        pass

    open_markers = [
        "button.toolbox-drawer-item-list-button:visible",
        "div.cdk-overlay-pane:visible button.toolbox-drawer-item-list-button",
        "div.cdk-overlay-container:visible button.toolbox-drawer-item-list-button",
        "div.cdk-overlay-pane:visible [role='menuitemcheckbox']",
        "div.cdk-overlay-container:visible [role='menuitemcheckbox']",
        # Gemini 2026-01 UI: the "tools" are in an Angular Material menu (mode dropdown).
        "div.cdk-overlay-pane:visible [role='menuitem']",
        "div.cdk-overlay-container:visible [role='menuitem']",
        "div.cdk-overlay-pane:visible .mat-mdc-menu-content",
        "div.cdk-overlay-container:visible .mat-mdc-menu-content",
        "mat-menu[data-test-id='desktop-nested-mode-menu']:visible",
        "[data-test-id='bard-mode-menu-button'][aria-expanded='true']",
        "[data-test-id='bard-mode-menu-button'] [aria-expanded='true']",
        "button.toolbox-drawer-button[aria-expanded='true']",
        "button.toolbox-drawer-button.menu-open",
    ]
    async def _menu_open() -> bool:
        for marker in open_markers:
            try:
                if await _gemini_locator_has_visible(page.locator(marker), max_scan=10):
                    return True
            except Exception:
                continue
        return False

    if await _menu_open():
        return

    tools_btn_candidates = [
        "button.toolbox-drawer-button",
        "button.toolbox-drawer-button[aria-haspopup='menu']",
        "toolbox-drawer button",
        "button:has-text('工具')",
        "button:has-text('Tools')",
        "button[aria-label='工具']",
        "button[aria-label='Tools']",
        # Gemini 2026-01 UI: tool selection moved into the "mode" dropdown under the prompt box.
        "[data-test-id='bard-mode-menu-button'] button",
        "[data-test-id='bard-mode-menu-button']",
        "bard-mode-switcher [aria-haspopup='menu'] button",
        "bard-mode-switcher [aria-haspopup='menu']",
    ]

    deadline = time.time() + 10.0
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            await _gemini_dismiss_overlays(page)
        except Exception:
            pass
        btn = None
        for selector in tools_btn_candidates:
            candidate = page.locator(selector)
            try:
                visible = await _gemini_first_visible(candidate, max_scan=10)
                if visible is not None:
                    try:
                        if await visible.is_enabled():
                            btn = visible
                            break
                    except Exception:
                        btn = visible
                        break
                    btn = visible
                    break
            except Exception as exc:
                last_error = exc
                continue
        if btn is None:
            await page.wait_for_timeout(250)
            continue

        expanded_open = False
        try:
            expanded_open = ((await btn.get_attribute("aria-expanded")) or "").strip().lower() == "true"
        except Exception:
            expanded_open = False
        if not expanded_open:
            try:
                btn_class = str((await btn.get_attribute("class")) or "").strip().lower()
            except Exception:
                btn_class = ""
            expanded_open = "menu-open" in btn_class

        if expanded_open:
            if await _menu_open():
                return
            await page.wait_for_timeout(150)
            if await _menu_open():
                return

        try:
            await btn.click()
        except Exception as exc:
            last_error = exc
            if await _menu_open():
                return
            await page.wait_for_timeout(250)
            if await _menu_open():
                return
            continue
        await _human_pause(page)

        if await _menu_open():
            return

        await page.wait_for_timeout(350)

    if last_error:
        raise RuntimeError(f"Cannot find Gemini Tools button: {last_error}") from last_error
    raise RuntimeError("Cannot find Gemini Tools button.")


async def _gemini_select_tool(page, *, label_re: re.Pattern[str]) -> None:
    await _gemini_open_tools_drawer(page)

    candidates = [
        page.locator("div.cdk-overlay-pane:visible button").filter(has_text=label_re),
        page.locator("div.cdk-overlay-container:visible button").filter(has_text=label_re),
        page.locator("div.cdk-overlay-pane:visible [role='menuitem']").filter(has_text=label_re),
        page.locator("div.cdk-overlay-container:visible [role='menuitem']").filter(has_text=label_re),
        page.locator("button.toolbox-drawer-item-list-button").filter(has_text=label_re),
        page.locator("button").filter(has_text=label_re),
    ]

    deadline = time.time() + 10.0
    while time.time() < deadline:
        for locator in candidates:
            try:
                item = await _gemini_first_visible(locator, max_scan=12)
                if item is None:
                    continue
                try:
                    await item.scroll_into_view_if_needed()
                except Exception:
                    pass
                # Tool items are rendered as checkboxes in current Gemini UI. Clicking an already-selected
                # item would toggle it off, so treat it as a no-op when already checked.
                try:
                    checked_attr = (await item.get_attribute("aria-checked") or "").strip().lower()
                except Exception:
                    checked_attr = ""
                if checked_attr == "true":
                    return
                try:
                    klass = (await item.get_attribute("class") or "").strip()
                except Exception:
                    klass = ""
                if "is-selected" in klass:
                    return
                await item.click()
                await _human_pause(page)
                return
            except Exception:
                continue
        await page.wait_for_timeout(250)

    await page.keyboard.press("Escape")
    await _human_pause(page)
    raise RuntimeError(f"Gemini tool not found: {label_re.pattern}")


def _gemini_tool_checked_from_attr(aria_checked: str | None, klass: str | None) -> bool | None:
    raw = (aria_checked or "").strip().lower()
    if raw in {"true", "false"}:
        return raw == "true"
    if not klass:
        return None
    klass_l = str(klass).strip().lower()
    if "is-selected" in klass_l:
        return True
    # Gemini 2026-02+ frequently renders the currently selected tool as a
    # "deselect" chip/button instead of exposing aria-checked on the menu item.
    if "toolbox-drawer-item-deselect-button" in klass_l:
        return True
    return None


_GEMINI_DEEP_RESEARCH_PLACEHOLDER_RE = re.compile(
    r"(你想研究什[么麼]|研究什么|What do you want to research)",
    re.I,
)
_GEMINI_GENERATE_IMAGE_PLACEHOLDER_RE = re.compile(
    r"(描述.*图片|描述.*圖|Describe your image)",
    re.I,
)


def _gemini_infer_tool_checked_from_placeholder(*, label_pattern: str, placeholder: str) -> bool | None:
    pattern = str(label_pattern or "")
    ph = str(placeholder or "").strip()
    if not ph:
        return None
    if (("deep" in pattern.lower()) and ("research" in pattern.lower())) or ("深入研究" in pattern) or ("深度研究" in pattern):
        if _GEMINI_DEEP_RESEARCH_PLACEHOLDER_RE.search(ph):
            return True
    if ("generate" in pattern.lower() and "image" in pattern.lower()) or ("生成图片" in pattern) or ("生成圖像" in pattern) or ("生成图像" in pattern):
        if _GEMINI_GENERATE_IMAGE_PLACEHOLDER_RE.search(ph):
            return True
    return None


async def _gemini_infer_tool_checked_state(page, *, label_re: re.Pattern[str]) -> bool | None:
    # 1) Selected-tool "deselect chip" is the strongest signal in recent Gemini UI.
    saw_visible_chip = False
    try:
        chips = page.locator("button.toolbox-drawer-item-deselect-button")
        count = await chips.count()
    except Exception:
        count = 0
    for i in range(min(int(count), 8)):
        chip = chips.nth(i)
        try:
            if not await chip.is_visible():
                continue
            saw_visible_chip = True
        except Exception:
            continue
        text = ""
        try:
            text = str((await chip.inner_text()) or "")
        except Exception:
            text = ""
        try:
            aria = str((await chip.get_attribute("aria-label")) or "")
        except Exception:
            aria = ""
        hay = " ".join([text, aria]).strip()
        if hay and label_re.search(hay):
            return True

    # If a selected-tool chip is visible but does not match this label, this label is not selected.
    if saw_visible_chip:
        return False

    # 2) "Tools" button selected-state is reliable when no specific chip is visible.
    tools_has_selected: bool | None = None
    try:
        tools_btn = page.locator("button.toolbox-drawer-button").first
        if await tools_btn.count() and await tools_btn.is_visible():
            klass = str((await tools_btn.get_attribute("class")) or "").strip()
            tools_has_selected = "has-selected-item" in klass
    except Exception:
        tools_has_selected = None
    if tools_has_selected is False:
        return False

    # 3) Placeholder text changes for some tools (Deep Research / Generate image).
    placeholder = ""
    try:
        box = page.locator("div[role='textbox'][data-placeholder]").first
        if await box.count() and await box.is_visible():
            placeholder = str((await box.get_attribute("data-placeholder")) or "").strip()
    except Exception:
        placeholder = ""
    inferred = _gemini_infer_tool_checked_from_placeholder(
        label_pattern=str(label_re.pattern or ""),
        placeholder=placeholder,
    )
    if inferred is not None:
        return inferred

    return None


async def _gemini_find_tool_item(page, *, label_re: re.Pattern[str], timeout_seconds: float = 10.0) -> Any | None:
    await _gemini_open_tools_drawer(page)

    candidates = [
        page.locator("div.cdk-overlay-pane:visible [role='menuitemcheckbox']").filter(has_text=label_re),
        page.locator("div.cdk-overlay-container:visible [role='menuitemcheckbox']").filter(has_text=label_re),
        page.locator("div.cdk-overlay-pane:visible button[role='menuitemcheckbox']").filter(has_text=label_re),
        page.locator("div.cdk-overlay-container:visible button[role='menuitemcheckbox']").filter(has_text=label_re),
        page.locator("div.cdk-overlay-pane:visible button").filter(has_text=label_re),
        page.locator("div.cdk-overlay-container:visible button").filter(has_text=label_re),
        page.locator("div.cdk-overlay-pane:visible [role='menuitem']").filter(has_text=label_re),
        page.locator("div.cdk-overlay-container:visible [role='menuitem']").filter(has_text=label_re),
        page.locator("button.toolbox-drawer-item-list-button").filter(has_text=label_re),
        page.locator("button.toolbox-drawer-item-deselect-button").filter(has_text=label_re),
    ]
    fuzzy_candidates = [
        page.locator(
            "div.cdk-overlay-pane:visible [role='menuitemcheckbox'], "
            "div.cdk-overlay-container:visible [role='menuitemcheckbox'], "
            "div.cdk-overlay-pane:visible button[role='menuitemcheckbox'], "
            "div.cdk-overlay-container:visible button[role='menuitemcheckbox'], "
            "button.toolbox-drawer-item-list-button, "
            "button.toolbox-drawer-item-deselect-button"
        )
    ]

    deadline = time.time() + max(0.5, float(timeout_seconds))
    while time.time() < deadline:
        for locator in candidates:
            try:
                item = await _gemini_first_visible(locator, max_scan=12)
                if item is not None:
                    return item
            except Exception:
                continue
        for locator in fuzzy_candidates:
            try:
                count = await locator.count()
            except Exception:
                count = 0
            for i in range(min(int(count), 16)):
                item = locator.nth(i)
                try:
                    if not await item.is_visible():
                        continue
                except Exception:
                    continue
                text = ""
                try:
                    text = str((await item.inner_text()) or "").strip()
                except Exception:
                    text = ""
                if not _gemini_tool_label_matches(label_re=label_re, text=text):
                    continue
                return item
        await page.wait_for_timeout(250)
    return None


async def _gemini_set_tool_checked(
    page,
    *,
    label_re: re.Pattern[str],
    checked: bool,
    ctx: Context | None,
    fail_open: bool,
) -> bool:
    """
    Ensure a Gemini tool checkbox is enabled/disabled (no prompt send).

    Gemini 2026-02 UI renders tools (Deep Research / Generate image / Canvas / Deep Think) as
    checkbox-like menu items (`role=menuitemcheckbox`, `aria-checked=true|false`).
    """

    item = await _gemini_find_tool_item(page, label_re=label_re, timeout_seconds=10.0)
    if item is None:
        msg = f"Gemini tool not found: {label_re.pattern}"
        if fail_open:
            await _ctx_info(ctx, msg + " (fail_open)")
            await _gemini_dismiss_overlays(page)
            return False
        await _gemini_dismiss_overlays(page)
        raise RuntimeError(msg)

    try:
        aria_checked = await item.get_attribute("aria-checked")
    except Exception:
        aria_checked = None
    try:
        klass = await item.get_attribute("class")
    except Exception:
        klass = None
    cur = _gemini_tool_checked_from_attr(aria_checked, klass)
    if cur is not None and cur == bool(checked):
        await _gemini_dismiss_overlays(page)
        return bool(cur)

    try:
        await item.scroll_into_view_if_needed()
    except Exception:
        pass
    await item.click()
    await _human_pause(page)
    await _gemini_dismiss_overlays(page)

    # Verify (avoid silently toggling the wrong direction).
    verify = await _gemini_find_tool_item(page, label_re=label_re, timeout_seconds=6.0)
    if verify is None:
        msg = f"Gemini tool disappeared after toggle: {label_re.pattern}"
        if fail_open:
            await _ctx_info(ctx, msg + " (fail_open)")
            await _gemini_dismiss_overlays(page)
            return False
        await _gemini_dismiss_overlays(page)
        raise RuntimeError(msg)

    try:
        aria_checked2 = await verify.get_attribute("aria-checked")
    except Exception:
        aria_checked2 = None
    try:
        klass2 = await verify.get_attribute("class")
    except Exception:
        klass2 = None
    cur2 = _gemini_tool_checked_from_attr(aria_checked2, klass2)
    await _gemini_dismiss_overlays(page)

    if cur2 is None:
        # Some Gemini variants hide checkbox attrs after selection and only expose
        # selected-state via chip/placeholder. Infer from those stable signals.
        inferred = await _gemini_infer_tool_checked_state(page, label_re=label_re)
        if inferred is not None:
            cur2 = bool(inferred)
            await _ctx_info(
                ctx,
                f"Gemini tool state inferred from fallback signals (wanted={checked}, inferred={cur2}): {label_re.pattern}",
            )

    if cur2 is None:
        msg = f"Gemini tool state unknown after toggle: {label_re.pattern}"
        if fail_open:
            await _ctx_info(ctx, msg + " (fail_open)")
            return bool(checked)
        raise RuntimeError(msg)
    if bool(cur2) != bool(checked):
        msg = f"Gemini tool switch did not apply (wanted={checked}, current={cur2}): {label_re.pattern}"
        if fail_open:
            await _ctx_info(ctx, msg + " (fail_open)")
            return bool(cur2)
        raise RuntimeError(msg)
    return bool(cur2)


async def _gemini_clear_selected_tools(page, *, ctx: Context | None) -> None:
    """
    Best-effort: ensure no Gemini tool checkbox is enabled (no prompt send).

    This matters because the tool selection can persist across chats and would
    silently change behavior/quota consumption for plain `gemini_web_ask*` calls.
    """

    tools_btn = page.locator("button.toolbox-drawer-button").first
    try:
        if not await tools_btn.count() or not await tools_btn.is_visible():
            return
        klass = (await tools_btn.get_attribute("class") or "").strip()
        if "has-selected-item" not in klass:
            return
    except Exception:
        # If we can't inspect state, don't try to clear (avoid random clicks).
        return

    try:
        await _gemini_open_tools_drawer(page)
    except Exception:
        return

    # Toggle off any checked tool items.
    for _ in range(10):
        checked_item = page.locator(
            "div.cdk-overlay-pane:visible button[role='menuitemcheckbox'][aria-checked='true'], "
            "div.cdk-overlay-pane:visible [role='menuitemcheckbox'][aria-checked='true']"
        ).first
        try:
            if not await checked_item.count() or not await checked_item.is_visible():
                break
        except Exception:
            break
        try:
            await checked_item.click()
            await _human_pause(page)
        except Exception:
            break

    await _gemini_dismiss_overlays(page)


async def _gemini_wait_for_prompt_placeholder(page, *, placeholder_re: re.Pattern[str], timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + max(0.5, timeout_seconds)
    box = page.locator("div[role='textbox'][data-placeholder]").first
    last_placeholder = ""
    while time.time() < deadline:
        try:
            if await box.count() and await box.is_visible():
                last_placeholder = str(await box.get_attribute("data-placeholder") or "").strip()
                if last_placeholder and placeholder_re.search(last_placeholder):
                    return
        except Exception:
            pass
        await page.wait_for_timeout(200)
    raise RuntimeError(f"Gemini prompt placeholder did not match {placeholder_re.pattern!r} (last={last_placeholder!r})")


async def _gemini_confirm_new_chat_if_needed(page) -> None:
    title_re = re.compile(r"(发起新对话|Start new chat)", re.I)
    confirm_re = re.compile(r"^\s*(发起新对话|Start new chat)\s*$", re.I)
    deadline = time.time() + 5.0

    while time.time() < deadline:
        modal = page.locator("mat-dialog-container, [role='dialog']").filter(has_text=title_re)
        try:
            if not await modal.count():
                await page.wait_for_timeout(250)
                continue
        except Exception:
            await page.wait_for_timeout(250)
            continue

        container = modal.first
        try:
            if not await container.is_visible():
                await page.wait_for_timeout(250)
                continue
        except Exception:
            await page.wait_for_timeout(250)
            continue

        confirm = container.locator("button.start-chat-button").first
        if not await confirm.count():
            confirm = container.locator("button").filter(has_text=confirm_re).first

        if await confirm.count():
            await confirm.click()
            await _human_pause(page)
            return

        close_btn = container.locator(
            "button.close-button, "
            "button[aria-label='关闭对话框'], "
            "button[aria-label='Close dialog'], "
            "button[aria-label='Close']"
        ).first
        if await close_btn.count():
            await close_btn.click()
            await _human_pause(page)
            return

        await page.keyboard.press("Escape")
        await _human_pause(page)
        return

    # Sometimes a backdrop blocks clicks even if the dialog isn't detectable via locators.
    backdrop = page.locator("div.cdk-overlay-backdrop.cdk-overlay-backdrop-showing:visible").first
    if await backdrop.count():
        try:
            await page.keyboard.press("Escape")
        except Exception:
            try:
                await backdrop.click()
            except Exception:
                pass
        await _human_pause(page)


async def _gemini_accept_usage_policy_if_present(page) -> None:
    # Gemini sometimes shows a one-time usage/policy dialog (e.g. for image workflows) that blocks the UI.
    # Prefer clicking "同意/Agree" rather than dismissing with Escape.
    dialog = page.locator("mat-dialog-container, [role='dialog']").filter(
        has_text=re.compile(r"(请确保你对上传的所有图片|使用此生成式\\s*AI\\s*服务时须遵守|Usage restrictions|policy)", re.I)
    ).first
    try:
        if not await dialog.count() or not await dialog.is_visible():
            return
    except Exception:
        return

    agree_re = re.compile(r"^\\s*(同意|Agree|I\\s*agree|Accept)\\s*$", re.I)
    agree = dialog.locator("button").filter(has_text=agree_re).first
    if not await agree.count():
        agree = page.locator("button").filter(has_text=agree_re).first
    if await agree.count():
        try:
            await agree.click()
            await _human_pause(page)
            return
        except Exception:
            return


async def _gemini_dismiss_overlays(page) -> None:
    await _gemini_confirm_new_chat_if_needed(page)
    await _gemini_accept_usage_policy_if_present(page)
    backdrop = page.locator("div.cdk-overlay-backdrop.cdk-overlay-backdrop-showing:visible").first
    if await backdrop.count():
        try:
            await page.keyboard.press("Escape")
        except Exception:
            try:
                await backdrop.click()
            except Exception:
                pass
        await _human_pause(page)


async def _gemini_click_send(page, prompt_box, *, ctx: Context | None = None) -> None:
    """Serialize ONLY the 'send new prompt' action across concurrent Gemini tool calls."""
    global _LAST_GEMINI_PROMPT_SENT_AT

    async with _gemini_send_lock():
        await _respect_prompt_interval(
            last_sent_at=float(_LAST_GEMINI_PROMPT_SENT_AT or 0.0),
            min_interval_seconds=_gemini_min_prompt_interval_seconds(),
            label="Gemini",
            ctx=ctx,
        )

        send_btn = page.locator(
            "button[aria-label='发送'], "
            "button[aria-label='傳送'], "
            "button[aria-label='Send'], "
            "button.send-button"
        ).first
        try:
            if await send_btn.count() and await send_btn.is_enabled():
                await send_btn.click()
            else:
                try:
                    await prompt_box.press("Enter")
                except Exception:
                    await page.keyboard.press("Enter")
        except PlaywrightTimeoutError:
            try:
                await prompt_box.press("Enter")
            except Exception:
                await page.keyboard.press("Enter")

        _LAST_GEMINI_PROMPT_SENT_AT = time.time()


async def _gemini_last_model_response_text_and_busy(page) -> tuple[str, bool]:
    """
    Return (answer_text, is_busy) for the latest Gemini model response.

    In Gemini "Thinking" UI, the response container may briefly show transient
    processing-state text before the real markdown answer is ready. Prefer the
    markdown body (which exposes aria-busy) to avoid returning those transient strings.
    """
    responses = page.locator("model-response")
    count = await responses.count()
    if count <= 0:
        return "", False

    response = responses.nth(count - 1)

    markdown = response.locator(
        "message-content .markdown, "
        "message-content .markdown-main-panel, "
        "div.markdown-main-panel, "
        "div.markdown"
    ).last

    if await markdown.count():
        busy_attr = ""
        try:
            busy_attr = (await markdown.get_attribute("aria-busy")) or ""
        except Exception:
            busy_attr = ""
        is_busy = busy_attr.strip().lower() == "true"
        raw = await _gemini_extract_markdown_text(markdown)
        return _gemini_clean_response_text(raw), is_busy

    try:
        raw = (await response.inner_text(timeout=2_000)).strip()
    except PlaywrightTimeoutError:
        return "", False
    return _gemini_clean_response_text(raw), False


async def _gemini_last_model_response_text(page) -> str:
    text, _is_busy = await _gemini_last_model_response_text_and_busy(page)
    return text


async def _gemini_wait_for_model_response(
    page,
    *,
    started_at: float,
    start_response_count: int,
    timeout_seconds: int,
    min_chars: int = 0,
    require_new: bool = True,
) -> str:
    deadline = started_at + timeout_seconds
    responses = page.locator("model-response")
    stop_btn = page.locator(_GEMINI_STOP_BUTTON_SELECTOR).first

    stable_for_ms = 0
    last_text = ""
    while time.time() < deadline:
        count = await responses.count()
        if require_new and count <= start_response_count:
            await page.wait_for_timeout(500)
            continue
        if count <= 0:
            await page.wait_for_timeout(500)
            continue

        text, is_busy = await _gemini_last_model_response_text_and_busy(page)
        if not text.strip():
            stable_for_ms = 0
            last_text = text
            await page.wait_for_timeout(650)
            continue
        if _looks_like_gemini_transient_response(text):
            stable_for_ms = 0
            last_text = text
            await page.wait_for_timeout(650)
            continue
        if min_chars and len(text) < min_chars:
            stable_for_ms = 0
            last_text = text
            await page.wait_for_timeout(650)
            continue

        if is_busy:
            stable_for_ms = 0
            last_text = text
            await page.wait_for_timeout(700)
            continue

        stop_visible = False
        try:
            if await stop_btn.count():
                stop_visible = await stop_btn.is_visible()
        except PlaywrightTimeoutError:
            stop_visible = False

        if stop_visible:
            stable_for_ms = 0
            last_text = text
            await page.wait_for_timeout(700)
            continue

        if text and text == last_text:
            stable_for_ms += 500
            if stable_for_ms >= 1200:
                return text
        else:
            stable_for_ms = 0
            last_text = text

        await page.wait_for_timeout(500)

    raise TimeoutError("Timed out waiting for Gemini response.")


async def _gemini_fetch_bytes(page, context, url: str) -> tuple[bytes, str]:
    fetch_exc: Exception | None = None
    try:
        return await _fetch_bytes_via_browser(page, url)
    except Exception as exc:
        fetch_exc = exc

    if not str(url).startswith("http"):
        if fetch_exc is not None:
            raise fetch_exc
        raise RuntimeError(f"Unsupported Gemini asset URL: {url}")

    download_page = await context.new_page()
    try:
        resp = await download_page.goto(url, wait_until="domcontentloaded", timeout=_navigation_timeout_ms())
        if resp is None:
            raise RuntimeError(f"Failed to download Gemini asset (no response): {url}")
        raw = await resp.body()
        content_type = (resp.headers.get("content-type") or "application/octet-stream").split(";", 1)[0].strip()
        return raw, content_type
    finally:
        try:
            await download_page.close()
        except Exception:
            pass



# Allow split entrypoint modules + compat facade to `import *` and still get
# underscore-prefixed helpers (matches old monolith import surface).
__all__ = [name for name in globals().keys() if not name.startswith("__")]
