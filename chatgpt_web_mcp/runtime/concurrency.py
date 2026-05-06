from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import Context


_CHATGPT_PAGE_SEMAPHORE: asyncio.Semaphore | None = None
_GEMINI_PAGE_SEMAPHORE: asyncio.Semaphore | None = None
_QWEN_PAGE_SEMAPHORE: asyncio.Semaphore | None = None

_CHATGPT_TAB_LIMIT_HITS = 0
_GEMINI_TAB_LIMIT_HITS = 0
_QWEN_TAB_LIMIT_HITS = 0

_CHATGPT_TAB_LAST_HIT_AT: float | None = None
_GEMINI_TAB_LAST_HIT_AT: float | None = None
_QWEN_TAB_LAST_HIT_AT: float | None = None


class _TabLimitReachedError(RuntimeError):
    pass


def _max_concurrent_pages_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except ValueError:
        return int(default)


def _chatgpt_max_concurrent_pages() -> int:
    # Conservative default: allow a few concurrent tabs, but prevent runaway tab explosions.
    return _max_concurrent_pages_env("CHATGPT_MAX_CONCURRENT_PAGES", 3)


def _gemini_max_concurrent_pages() -> int:
    return _max_concurrent_pages_env("GEMINI_MAX_CONCURRENT_PAGES", 2)


def _qwen_max_concurrent_pages() -> int:
    return _max_concurrent_pages_env("QWEN_MAX_CONCURRENT_PAGES", 2)


def _chatgpt_page_semaphore() -> asyncio.Semaphore | None:
    global _CHATGPT_PAGE_SEMAPHORE
    max_pages = int(_chatgpt_max_concurrent_pages())
    if max_pages <= 0:
        return None
    if _CHATGPT_PAGE_SEMAPHORE is None:
        _CHATGPT_PAGE_SEMAPHORE = asyncio.Semaphore(max_pages)
    return _CHATGPT_PAGE_SEMAPHORE


def _gemini_page_semaphore() -> asyncio.Semaphore | None:
    global _GEMINI_PAGE_SEMAPHORE
    max_pages = int(_gemini_max_concurrent_pages())
    if max_pages <= 0:
        return None
    if _GEMINI_PAGE_SEMAPHORE is None:
        _GEMINI_PAGE_SEMAPHORE = asyncio.Semaphore(max_pages)
    return _GEMINI_PAGE_SEMAPHORE


def _qwen_page_semaphore() -> asyncio.Semaphore | None:
    global _QWEN_PAGE_SEMAPHORE
    max_pages = int(_qwen_max_concurrent_pages())
    if max_pages <= 0:
        return None
    if _QWEN_PAGE_SEMAPHORE is None:
        _QWEN_PAGE_SEMAPHORE = asyncio.Semaphore(max_pages)
    return _QWEN_PAGE_SEMAPHORE


def _normalize_web_kind(kind: str) -> str:
    raw = str(kind or "").strip().lower()
    if raw in {"chatgpt", "gemini", "qwen"}:
        return raw
    raise ValueError(f"Unknown kind: {kind!r}")


def _page_slot_timeout_seconds(kind: str) -> float:
    kind = _normalize_web_kind(kind)
    if kind == "chatgpt":
        key = "CHATGPT_PAGE_SLOT_TIMEOUT_SECONDS"
    elif kind == "gemini":
        key = "GEMINI_PAGE_SLOT_TIMEOUT_SECONDS"
    else:
        key = "QWEN_PAGE_SLOT_TIMEOUT_SECONDS"
    raw = (os.environ.get(key) or "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


def _tab_limit_retry_seconds() -> int:
    raw = (os.environ.get("CHATGPT_TAB_LIMIT_RETRY_SECONDS") or "").strip()
    if not raw:
        return 300
    try:
        return max(30, int(float(raw)))
    except ValueError:
        return 300


def _is_tab_limit_error(exc: Exception) -> bool:
    return isinstance(exc, _TabLimitReachedError)


def _sema_in_use(sema: asyncio.Semaphore | None, max_pages: int) -> int | None:
    if sema is None:
        return None
    value = getattr(sema, "_value", None)
    if not isinstance(value, int):
        return None
    return max(0, max_pages - value)


def _tab_limit_result(
    *,
    tool: str,
    run_id: str,
    started_at: float,
    conversation_url: str | None = None,
    answer: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retry_after = _tab_limit_retry_seconds()
    result: dict[str, Any] = {
        "ok": False,
        "status": "cooldown",
        "answer": answer,
        "conversation_url": str(conversation_url or "").strip(),
        "elapsed_seconds": round(time.time() - started_at, 3),
        "run_id": run_id,
        "error_type": "TabLimitReached",
        "error": "tab limit reached",
        "retry_after_seconds": retry_after,
    }
    if extra:
        result.update(extra)
    return result


@asynccontextmanager
async def _page_slot(*, kind: str, ctx: Context | None) -> Any:
    # `ctx` is currently unused here but kept for a stable call site and future logging.
    kind = _normalize_web_kind(kind)
    if kind == "chatgpt":
        sema = _chatgpt_page_semaphore()
    elif kind == "gemini":
        sema = _gemini_page_semaphore()
    else:
        sema = _qwen_page_semaphore()
    if sema is None:
        yield None
        return
    timeout_sec = _page_slot_timeout_seconds(kind)
    try:
        if timeout_sec > 0:
            await asyncio.wait_for(sema.acquire(), timeout=timeout_sec)
        else:
            await sema.acquire()
    except TimeoutError as exc:
        global _CHATGPT_TAB_LIMIT_HITS, _GEMINI_TAB_LIMIT_HITS, _QWEN_TAB_LIMIT_HITS
        global _CHATGPT_TAB_LAST_HIT_AT, _GEMINI_TAB_LAST_HIT_AT, _QWEN_TAB_LAST_HIT_AT
        now = time.time()
        if kind == "chatgpt":
            _CHATGPT_TAB_LIMIT_HITS += 1
            _CHATGPT_TAB_LAST_HIT_AT = now
        elif kind == "gemini":
            _GEMINI_TAB_LIMIT_HITS += 1
            _GEMINI_TAB_LAST_HIT_AT = now
        else:
            _QWEN_TAB_LIMIT_HITS += 1
            _QWEN_TAB_LAST_HIT_AT = now
        raise _TabLimitReachedError(f"{kind} tab limit reached") from exc
    try:
        yield None
    finally:
        try:
            sema.release()
        except Exception:
            return
