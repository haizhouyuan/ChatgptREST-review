from __future__ import annotations

import asyncio

from chatgpt_web_mcp.providers.gemini.core import *  # noqa: F403
from chatgpt_web_mcp.providers.gemini.ask import (  # noqa: F401
    _gemini_close_surface_handles,
    _gemini_initial_prompt_surface_needs_reopen,
)
from chatgpt_web_mcp.playwright.cdp import _restart_local_cdp_chrome


async def _open_gemini_self_check_surface(
    *,
    playwright: Any,
    cfg: Any,
    conversation_url: str | None,
    ctx: Context | None,
) -> tuple[Any, Any, Any, bool]:
    reopen_budget = 2
    while True:
        browser = None
        context = None
        page = None
        close_context = False
        try:
            browser, context, page, close_context = await _open_gemini_page(
                playwright,
                cfg,
                conversation_url=conversation_url,
                ctx=ctx,
            )
            await _gemini_find_prompt_box(page)
            return browser, context, page, close_context
        except Exception as exc:
            if reopen_budget <= 0 or not _gemini_initial_prompt_surface_needs_reopen(exc=exc, page=page):
                raise
            reopen_budget -= 1
            if ctx is not None:
                await _ctx_info(
                    ctx,
                    f"Gemini self-check reopening initial prompt surface after {type(exc).__name__}: {exc}",
                )
            await _gemini_close_surface_handles(
                page=page,
                context=context,
                browser=browser,
                close_context=close_context,
            )
            if cfg.cdp_url:
                try:
                    await _restart_local_cdp_chrome(kind="gemini", cdp_url=cfg.cdp_url, ctx=ctx)
                except Exception:
                    pass
            await asyncio.sleep(1.0)


def _self_check_error_result(
    *,
    exc: Exception,
    page: Any | None,
    started_at: float,
    run_id: str,
    mode_text: str,
    tools_btn: dict[str, Any],
    tools: list[dict[str, Any]],
    artifacts: dict[str, str],
) -> dict[str, Any]:
    error_text = _coerce_error_text(exc)
    error_type = _gemini_classify_error_type(error_text=error_text, fallback=type(exc).__name__)
    return {
        "ok": False,
        "status": "error",
        "conversation_url": (str(page.url or "").strip() if page is not None else ""),
        "elapsed_seconds": round(time.time() - started_at, 3),
        "run_id": run_id,
        "mode_text": mode_text,
        "tools_button": tools_btn,
        "tools": tools,
        "deep_think_available": None,
        "deep_think_checked": None,
        "region_supported": (False if error_type == "GeminiUnsupportedRegion" else None),
        "error_type": error_type,
        "error": error_text,
        "debug_artifacts": artifacts,
    }


async def gemini_web_self_check(
    conversation_url: str | None = None,
    timeout_seconds: int = 60,
    ctx: Context | None = None,
) -> dict[str, Any]:
    cfg = _load_gemini_web_config()
    started_at = time.time()
    run_id = _run_id(tool="gemini_web_self_check")
    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _page_slot(kind="gemini", ctx=ctx), async_playwright() as p:
            browser = None
            context = None
            page = None
            close_context = False
            mode_text = ""
            tools: list[dict[str, Any]] = []
            tools_btn = {"visible": False, "has_selected_item": None, "class": None}
            open_error: str | None = None
            try:
                browser, context, page, close_context = await _open_gemini_self_check_surface(
                    playwright=p,
                    cfg=cfg,
                    conversation_url=conversation_url,
                    ctx=ctx,
                )
                await _human_pause(page)

                try:
                    mode_text = await _gemini_current_mode_text(page)
                except Exception:
                    mode_text = ""

                # Best-effort: detect the "Tools" button state (may vary by UI / language).
                btn = page.locator("button.toolbox-drawer-button").first
                try:
                    if await btn.count() and await btn.is_visible():
                        tools_btn["visible"] = True
                        klass = (await btn.get_attribute("class") or "").strip() or None
                        tools_btn["class"] = klass
                        tools_btn["has_selected_item"] = bool(klass and "has-selected-item" in klass)
                except Exception:
                    pass

                # Best-effort: open the tools drawer and list checkbox tools (no toggles).
                try:
                    await _gemini_open_tools_drawer(page)
                    tools_btn["visible"] = True
                    items = page.locator(
                        "div.cdk-overlay-pane:visible [role='menuitemcheckbox'], "
                        "div.cdk-overlay-pane:visible button[role='menuitemcheckbox'], "
                        "div.cdk-overlay-container:visible [role='menuitemcheckbox'], "
                        "div.cdk-overlay-container:visible button[role='menuitemcheckbox'], "
                        "div.cdk-overlay-pane:visible [role='menuitem'], "
                        "div.cdk-overlay-container:visible [role='menuitem'], "
                        "button.toolbox-drawer-item-list-button"
                    )
                    n = 0
                    try:
                        n = int(await items.count())
                    except Exception:
                        n = 0
                    for i in range(min(max(n, 0), 80)):
                        it = items.nth(i)
                        try:
                            text = (await it.inner_text()) or ""
                        except Exception:
                            text = ""
                        try:
                            aria = await it.get_attribute("aria-checked")
                        except Exception:
                            aria = None
                        try:
                            klass = await it.get_attribute("class")
                        except Exception:
                            klass = None
                        checked = _gemini_tool_checked_from_attr(aria, klass)
                        tools.append(
                            {
                                "text": (text or "").strip(),
                                "checked": checked,
                            }
                        )
                except Exception as exc:
                    open_error = f"{type(exc).__name__}: {exc}"
                finally:
                    try:
                        await _gemini_dismiss_overlays(page)
                    except Exception:
                        pass

                deep_think_re = _GEMINI_DEEP_THINK_TOOL_RE
                deep_think = [t for t in tools if deep_think_re.search(str(t.get("text") or ""))]
                deep_think_available = bool(deep_think)
                deep_think_checked = None
                for t in deep_think:
                    if isinstance(t.get("checked"), bool):
                        deep_think_checked = bool(t["checked"])
                        break

                return {
                    "ok": True,
                    "status": "completed",
                    "conversation_url": (str(page.url or "").strip() if page is not None else ""),
                    "elapsed_seconds": round(time.time() - started_at, 3),
                    "run_id": run_id,
                    "mode_text": mode_text,
                    "tools_button": tools_btn,
                    "tools": tools,
                    "deep_think_available": deep_think_available,
                    "deep_think_checked": deep_think_checked,
                    "region_supported": True,
                    "error_type": ("GeminiToolsDrawerError" if open_error else None),
                    "error": open_error,
                }
            except Exception as exc:
                artifacts: dict[str, str] = {}
                if page is not None:
                    artifacts = await _capture_debug_artifacts(page, label="gemini_web_self_check_error")
                    if ctx and artifacts:
                        await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")
                return _self_check_error_result(
                    exc=exc,
                    page=page,
                    started_at=started_at,
                    run_id=run_id,
                    mode_text=mode_text,
                    tools_btn=tools_btn,
                    tools=tools,
                    artifacts=artifacts,
                )
            finally:
                try:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    if close_context and context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()
