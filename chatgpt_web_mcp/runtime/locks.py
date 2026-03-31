from __future__ import annotations

import asyncio


_ASK_LOCK: asyncio.Lock | None = None


def _ask_lock() -> asyncio.Lock:
    global _ASK_LOCK
    if _ASK_LOCK is None:
        _ASK_LOCK = asyncio.Lock()
    return _ASK_LOCK
