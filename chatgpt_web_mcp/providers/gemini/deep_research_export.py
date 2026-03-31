from __future__ import annotations

from chatgpt_web_mcp.providers.gemini.core import *  # noqa: F403

_GEMINI_DR_SHARE_EXPORT_RE = re.compile(
    r"(分享和导出|分享與匯出|分享与导出|Share\s*(and|&)\s*export)",
    re.I,
)
_GEMINI_DR_EXPORT_TO_GDOC_RE = re.compile(
    r"(导出到\s*Google\s*文档|導出到\s*Google\s*文件|匯出到\s*Google\s*文件|Export\s*to\s*Google\s*Docs?)",
    re.I,
)
_GEMINI_DR_OPEN_GDOC_RE = re.compile(
    r"(打开文档|開啟文件|Open\s*doc|Open\s*document|在\s*Google\s*文档中打开)",
    re.I,
)
_GEMINI_GDOC_URL_RE = re.compile(r"https?://docs\.google\.com/document/d/([0-9A-Za-z_-]{20,})", re.I)


def _gemini_gdoc_id_from_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    m = _GEMINI_GDOC_URL_RE.search(raw)
    if not m:
        return ""
    return str(m.group(1) or "").strip()


def _gemini_gdoc_export_txt_url(doc_id: str) -> str:
    did = str(doc_id or "").strip()
    if not did:
        return ""
    return f"https://docs.google.com/document/d/{did}/export?format=txt"


async def _gemini_try_click_export_to_gdoc(page) -> bool:
    candidates = [
        page.locator(
            "div.cdk-overlay-pane:visible button, "
            "div.cdk-overlay-pane:visible [role='menuitem'], "
            "div.cdk-overlay-pane:visible [role='button']"
        ).filter(has_text=_GEMINI_DR_EXPORT_TO_GDOC_RE),
        page.locator("button, [role='menuitem'], [role='button']").filter(has_text=_GEMINI_DR_EXPORT_TO_GDOC_RE),
    ]
    for locator in candidates:
        item = await _gemini_first_visible(locator, max_scan=16)
        if item is None:
            continue
        try:
            await item.scroll_into_view_if_needed()
        except Exception:
            pass
        try:
            await item.click()
            await _human_pause(page)
            return True
        except Exception:
            continue
    return False


async def _gemini_try_open_share_export_panel(page) -> bool:
    candidates = [
        page.locator("deep-research-immersive-panel button, deep-research-immersive-panel [role='button']").filter(
            has_text=_GEMINI_DR_SHARE_EXPORT_RE
        ),
        page.locator("button, [role='button']").filter(has_text=_GEMINI_DR_SHARE_EXPORT_RE),
    ]
    for locator in candidates:
        item = await _gemini_first_visible(locator, max_scan=16)
        if item is None:
            continue
        try:
            await item.scroll_into_view_if_needed()
        except Exception:
            pass
        try:
            await item.click()
            await _human_pause(page)
            return True
        except Exception:
            continue
    return False


async def _gemini_wait_for_gdoc_url(*, page, context, timeout_seconds: float) -> str:
    deadline = time.time() + max(1.0, float(timeout_seconds))
    clicked_open_doc = False
    while time.time() < deadline:
        # 1) New tab or current tab already on docs URL.
        try:
            for p in list(getattr(context, "pages", []) or []):
                url = str(getattr(p, "url", "") or "").strip()
                if _gemini_gdoc_id_from_url(url):
                    return url
        except Exception:
            pass

        # 2) Visible links in current Gemini page.
        links = page.locator("a[href*='docs.google.com/document/d/']")
        try:
            n = await links.count()
        except Exception:
            n = 0
        for i in range(min(int(n), 8)):
            link = links.nth(i)
            href = ""
            try:
                href = str((await link.get_attribute("href")) or "").strip()
            except Exception:
                href = ""
            if _gemini_gdoc_id_from_url(href):
                return href

        # 3) Some variants show an "Open doc" action; click once if visible.
        if not clicked_open_doc:
            open_btn = await _gemini_first_visible(
                page.locator("button, [role='button'], a").filter(has_text=_GEMINI_DR_OPEN_GDOC_RE),
                max_scan=8,
            )
            if open_btn is not None:
                try:
                    await open_btn.click()
                    clicked_open_doc = True
                    await _human_pause(page)
                except Exception:
                    pass

        # 4) Last-resort parse from body text.
        try:
            body = str((await page.locator("body").inner_text(timeout=1_500)) or "")
        except Exception:
            body = ""
        m = _GEMINI_GDOC_URL_RE.search(body or "")
        if m:
            return str(m.group(0) or "").strip()

        await page.wait_for_timeout(300)
    return ""


def _decode_text_bytes(raw: bytes) -> str:
    if not raw:
        return ""
    for enc in ("utf-8-sig", "utf-16", "utf-16le", "utf-16be"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "replace")


async def gemini_web_deep_research_export_gdoc(
    conversation_url: str,
    timeout_seconds: int = 120,
    fetch_text: bool = True,
    max_chars: int = 400_000,
    ctx: Context | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    run_id = _run_id(tool="gemini_web_deep_research_export_gdoc")
    conv = str(conversation_url or "").strip()
    if not conv:
        return {
            "ok": False,
            "status": "error",
            "answer": "",
            "conversation_url": "",
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": "ValueError",
            "error": "conversation_url is required.",
        }
    if _gemini_is_base_app_url(conv):
        return {
            "ok": False,
            "status": "error",
            "answer": "",
            "conversation_url": conv,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "run_id": run_id,
            "error_type": "ValueError",
            "error": "conversation_url must be a Gemini thread URL (not /app home).",
        }

    cfg = _load_gemini_web_config()
    env_ctx = _without_proxy_env() if cfg.cdp_url else nullcontext()
    with env_ctx:
        async with _ask_lock():
            async with _page_slot(kind="gemini", ctx=ctx), async_playwright() as p:
                browser = None
                context = None
                page = None
                close_context = False
                try:
                    browser, context, page, close_context = await _open_gemini_page(
                        p,
                        cfg,
                        conversation_url=conv,
                        ctx=ctx,
                    )
                    await _gemini_find_prompt_box(page, timeout_ms=max(10_000, int(timeout_seconds * 1000)))
                    await _human_pause(page)
                    await _gemini_dismiss_overlays(page)

                    # First, check if the GDoc URL is already available (e.g. exported previously in UI).
                    gdoc_url = await _gemini_wait_for_gdoc_url(
                        page=page,
                        context=context,
                        timeout_seconds=3.0,
                    )

                    clicked_export = False
                    if not gdoc_url:
                        deadline = time.time() + max(10.0, float(timeout_seconds) * 0.55)
                        while time.time() < deadline:
                            if await _gemini_try_click_export_to_gdoc(page):
                                clicked_export = True
                                break
                            _ = await _gemini_try_open_share_export_panel(page)
                            if await _gemini_try_click_export_to_gdoc(page):
                                clicked_export = True
                                break
                            await page.wait_for_timeout(350)

                        if not clicked_export:
                            # Before failing completely, do one last check for the URL.
                            gdoc_url = await _gemini_wait_for_gdoc_url(
                                page=page,
                                context=context,
                                timeout_seconds=3.0,
                            )
                            if not gdoc_url:
                                return {
                                    "ok": False,
                                    "status": "in_progress",
                                    "answer": "",
                                    "conversation_url": str(page.url or conv),
                                    "elapsed_seconds": round(time.time() - started_at, 3),
                                    "run_id": run_id,
                                    "error_type": "GeminiDeepResearchExportToGDocNotFound",
                                    "error": "Deep Research export action not found in UI.",
                                }

                    if not gdoc_url:
                        gdoc_url = await _gemini_wait_for_gdoc_url(
                            page=page,
                            context=context,
                            timeout_seconds=max(8.0, float(timeout_seconds) * 0.45),
                        )
                    gdoc_id = _gemini_gdoc_id_from_url(gdoc_url)
                    export_txt_url = _gemini_gdoc_export_txt_url(gdoc_id)

                    if not gdoc_id:
                        return {
                            "ok": False,
                            "status": "in_progress",
                            "answer": "",
                            "conversation_url": str(page.url or conv),
                            "elapsed_seconds": round(time.time() - started_at, 3),
                            "run_id": run_id,
                            "gdoc_url": gdoc_url,
                            "gdoc_id": "",
                            "gdoc_export_txt_url": "",
                            "error_type": "GeminiDeepResearchGDocUrlNotReady",
                            "error": "Google Doc URL not available yet after export click.",
                        }

                    answer = ""
                    content_type = ""
                    if bool(fetch_text):
                        raw, content_type = await _gemini_fetch_bytes(page, context, export_txt_url)
                        answer = _decode_text_bytes(raw).strip()
                        if max_chars and int(max_chars) > 0 and len(answer) > int(max_chars):
                            answer = answer[: int(max_chars)]

                    done = bool(gdoc_id) and (not bool(fetch_text) or bool(answer.strip()))
                    return {
                        "ok": bool(done),
                        "status": ("completed" if done else "in_progress"),
                        "answer": answer,
                        "conversation_url": str(page.url or conv),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "gdoc_url": gdoc_url,
                        "gdoc_id": gdoc_id,
                        "gdoc_export_txt_url": export_txt_url,
                        "content_type": content_type,
                        "error_type": (None if done else "GeminiDeepResearchGDocTextNotReady"),
                        "error": (None if done else "Google Doc exported but text body is empty."),
                    }
                except Exception as exc:
                    artifacts: dict[str, str] = {}
                    if page is not None:
                        artifacts = await _capture_debug_artifacts(page, label="gemini_web_deep_research_export_gdoc_error")
                        if ctx and artifacts:
                            await _ctx_info(ctx, f"Saved debug artifacts: {artifacts}")
                    return {
                        "ok": False,
                        "status": "error",
                        "answer": "",
                        "conversation_url": (str(page.url or "").strip() if page is not None else conv),
                        "elapsed_seconds": round(time.time() - started_at, 3),
                        "run_id": run_id,
                        "error_type": type(exc).__name__,
                        "error": _coerce_error_text(exc),
                        "debug_artifacts": artifacts,
                    }
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

