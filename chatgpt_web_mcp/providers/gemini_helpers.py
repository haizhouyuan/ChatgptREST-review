from __future__ import annotations

import os
import re
import time
from typing import Any
from urllib.parse import urlparse


def _looks_like_gemini_blocked_error(text: str) -> bool:
    hay = (text or "").strip().lower()
    return any(
        needle in hay
        for needle in (
            "accounts.google.com",
            "google sign-in",
            "google sign in",
            "log in to google",
            "verification/captcha",
            "captcha",
            "verify you are a human",
            "not a robot",
            "not supported in your region",
            "not available in your country",
            "not available in this region",
            "gemini is not available in this region",
        )
    )


_GEMINI_INFRA_ERROR_RE = re.compile(
    r"("
    r"cdp connect failed|"
    r"connect_over_cdp|"
    r"no chrome contexts found via cdp|"
    r"object has no attribute 'contexts'|"
    r"target page, context or browser has been closed|"
    r"target crashed|"
    r"econnrefused|"
    r"connection refused|"
    r"net::err_connection_closed|"
    r"socket hang up"
    r")",
    re.I,
)


def _looks_like_gemini_infra_error(text: str) -> bool:
    hay = (text or "").strip()
    if not hay:
        return False
    return bool(_GEMINI_INFRA_ERROR_RE.search(hay))


def _gemini_infra_retry_after_seconds() -> int:
    raw = (os.environ.get("CHATGPTREST_INFRA_RETRY_AFTER_SECONDS") or "").strip()
    try:
        val = int(raw) if raw else 120
    except Exception:
        val = 120
    return max(15, min(val, 3600))


def _gemini_classify_error_type(*, error_text: str, fallback: str) -> str:
    """Convert common Gemini UI failure modes into stable error types."""
    hay = (error_text or "").strip().lower()
    if not hay:
        return str(fallback or "RuntimeError")
    if (
        "unsupported region" in hay
        or "not supported in your region" in hay
        or "not available in your country" in hay
        or "目前不支持你所在的地区" in hay
        or "不支持你所在的地区" in hay
    ):
        return "GeminiUnsupportedRegion"
    if "gemini is not available in this region" in hay or "not available in this region" in hay:
        return "GeminiUnsupportedRegion"
    if "redirected to google sign-in" in hay or "accounts.google.com" in hay:
        return "GeminiNotLoggedIn"
    if "verification/captcha" in hay or "captcha" in hay or "verify you are a human" in hay or "not a robot" in hay:
        return "GeminiCaptcha"
    if "cannot find gemini prompt box" in hay:
        return "GeminiPromptBoxNotFound"
    if "gemini mode selector not found" in hay:
        return "GeminiModeSelectorNotFound"
    if "gemini thinking mode option not found" in hay:
        return "GeminiThinkingModeNotFound"
    if "gemini pro mode option not found" in hay:
        return "GeminiProModeNotFound"
    if "gemini tool not found" in hay and ("import code" in hay or "导入代码" in hay or "匯入程式碼" in hay):
        return "GeminiImportCodeNotFound"
    if "gemini tool not found" in hay and (
        ("deep" in hay and "research" in hay)
        or ("深入研究" in hay)
        or ("深度研究" in hay)
        or ("调研" in hay)
        or ("調研" in hay)
    ):
        return "GeminiDeepResearchToolNotFound"
    if "gemini tool not found" in hay and "deep" in hay and "think" in hay:
        return "GeminiDeepThinkToolNotFound"
    if "gemini tool switch did not apply" in hay and "deep" in hay and "think" in hay:
        return "GeminiDeepThinkDidNotApply"
    if "gemini mode switch did not apply" in hay:
        return "GeminiModeSwitchDidNotApply"
    return str(fallback or "RuntimeError")


_GEMINI_CONVERSATION_ID_FROM_URL_RE = re.compile(r"/app/([0-9a-zA-Z_-]{8,})", re.I)
_GEMINI_JSLOG_CONVERSATION_ID_RE = re.compile(r"\bc_([0-9a-zA-Z_-]{8,})\b", re.I)


def _gemini_conversation_id_from_url(conversation_url: str) -> str | None:
    raw = str(conversation_url or "").strip()
    if not raw:
        return None
    m = _GEMINI_CONVERSATION_ID_FROM_URL_RE.search(raw)
    if not m:
        return None
    cid = str(m.group(1)).strip()
    if cid.lower().startswith("c_"):
        cid = cid[2:]
    cid = cid.strip()
    return cid.lower() if cid else None


def _gemini_is_base_app_url(url: str) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    if _gemini_conversation_id_from_url(raw):
        return False
    return bool(re.match(r"^https?://gemini\.google\.com/app/?(?:\?.*)?$", raw, re.I))


def _gemini_conversation_id_from_jslog(jslog: str | None) -> str | None:
    raw = str(jslog or "").strip()
    if not raw:
        return None
    m = _GEMINI_JSLOG_CONVERSATION_ID_RE.search(raw)
    if not m:
        return None
    cid = str(m.group(1)).strip()
    return cid.lower() if cid else None


def _gemini_conversation_hint_tokens(conversation_hint: str | None, *, max_tokens: int = 24) -> list[str]:
    raw = str(conversation_hint or "").strip()
    if not raw:
        return []
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return []

    max_tokens = max(0, int(max_tokens))
    if max_tokens <= 0:
        return []

    chinese_tokens: list[str] = []
    ascii_tokens: list[str] = []
    seen: set[str] = set()

    for tok in re.findall(r"[\u4e00-\u9fff]{2,}", raw):
        tok = str(tok or "").strip()
        if not tok:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        chinese_tokens.append(tok)

    for tok in re.findall(r"[A-Za-z0-9_./-]{4,}", raw):
        tok = str(tok or "").strip()
        if not tok:
            continue
        key = tok.lower()
        if key in seen:
            continue
        seen.add(key)
        ascii_tokens.append(tok)

    max_chinese = int(round(max_tokens * 0.67))
    max_chinese = max(0, min(max_tokens, max_chinese))
    max_ascii = max(0, max_tokens - max_chinese)

    tokens: list[str] = []
    tokens.extend(chinese_tokens[:max_chinese])
    tokens.extend(ascii_tokens[:max_ascii])

    for tok in chinese_tokens[max_chinese:]:
        if len(tokens) >= max_tokens:
            break
        tokens.append(tok)

    for tok in ascii_tokens[max_ascii:]:
        if len(tokens) >= max_tokens:
            break
        tokens.append(tok)

    return tokens


def _gemini_build_conversation_url(*, base_url: str, conversation_id: str) -> str:
    cid = str(conversation_id or "").strip()
    if not cid:
        return str(base_url or "").strip()
    parsed = urlparse(str(base_url or "").strip() or "https://gemini.google.com/app")
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or "gemini.google.com"
    query = parsed.query
    out = f"{scheme}://{netloc}/app/{cid}"
    if query:
        out = f"{out}?{query}"
    return out


async def _best_effort_gemini_conversation_url(page: Any) -> str:
    url = (page.url or "").strip()
    if _gemini_conversation_id_from_url(url):
        return url

    href = ""
    try:
        href = await page.evaluate("() => window.location && window.location.href ? String(window.location.href) : ''")
        href = (str(href or "").strip() if href is not None else "")
        if _gemini_conversation_id_from_url(href):
            return href
    except Exception:
        href = ""

    base = href or url or "https://gemini.google.com/app"

    try:
        selected = page.locator("div[data-test-id='conversation'].selected").first
        if await selected.count():
            jslog = await selected.get_attribute("jslog")
            cid = _gemini_conversation_id_from_jslog(jslog)
            if cid:
                return _gemini_build_conversation_url(base_url=base, conversation_id=cid)
    except Exception:
        pass

    try:
        btn = page.locator("button.send-button").first
        if await btn.count():
            jslog = await btn.get_attribute("jslog")
            cid = _gemini_conversation_id_from_jslog(jslog)
            if cid:
                return _gemini_build_conversation_url(base_url=base, conversation_id=cid)
    except Exception:
        pass

    return url


async def _gemini_wait_for_conversation_url(page: Any, *, timeout_seconds: float = 8.0) -> str:
    deadline = time.time() + max(0.2, timeout_seconds)
    last = (page.url or "").strip()
    started_at = time.time()
    tried_best_effort = False
    best_effort: str = ""
    while time.time() < deadline:
        url = (page.url or "").strip()
        if url and url != last:
            last = url
        if _gemini_conversation_id_from_url(url):
            return url
        try:
            href = await page.evaluate("() => window.location && window.location.href ? String(window.location.href) : ''")
            href = (str(href or "").strip() if href is not None else "")
            if href and href != last:
                last = href
            if _gemini_conversation_id_from_url(href):
                return href
        except Exception:
            pass
        if not tried_best_effort and (time.time() - started_at) >= 1.0:
            tried_best_effort = True
            try:
                alt = await _best_effort_gemini_conversation_url(page)
                if alt:
                    best_effort = alt
            except Exception:
                pass
        await page.wait_for_timeout(250)

    if not _gemini_conversation_id_from_url(last):
        try:
            alt = await _best_effort_gemini_conversation_url(page)
            if alt:
                last = alt
        except Exception:
            pass

    if not _gemini_conversation_id_from_url(last) and best_effort:
        last = best_effort
    return last


_GEMINI_DEEP_RESEARCH_REPORT_RE = re.compile(
    r"("
    r"(分享和导出|Share and export|Share|Export).{0,80}(目录|Table of contents|Contents)|"
    r"(目录|Table of contents|Contents).{0,80}(分享和导出|Share and export|Share|Export)|"
    r"(调研报告|Research report|Report:|报告：)"
    r")",
    re.I | re.S,
)


def _looks_like_gemini_deep_research_report(text: str) -> bool:
    trimmed = (text or "").strip()
    if len(trimmed) < 800:
        return False
    return bool(_GEMINI_DEEP_RESEARCH_REPORT_RE.search(trimmed))


def _slice_gemini_deep_research_report(text: str) -> str:
    body = (text or "").strip()
    if not body:
        return ""
    m = re.search(r"(调研报告|Research report|Report:|报告：).{0,200}", body, re.I)
    if m:
        return body[m.start() :].strip()
    m = re.search(r"(^|\n)(第一章|Chapter\\s+1)\\b", body, re.I)
    if m:
        return body[m.start() :].strip()
    return body


_GEMINI_STOP_BUTTON_SELECTOR = (
    "button[aria-label='停止'], "
    "button[aria-label='Stop'], "
    "button[aria-label='Stop generating']"
)
