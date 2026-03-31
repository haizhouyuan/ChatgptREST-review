from __future__ import annotations

import os
import random
from mcp.server.fastmcp import Context

from chatgpt_web_mcp.runtime.util import _ctx_info


def _navigation_timeout_ms() -> int:
    raw = (os.environ.get("CHATGPT_NAVIGATION_TIMEOUT_MS") or "").strip()
    if not raw:
        return 90_000
    try:
        return max(5_000, int(raw))
    except ValueError:
        return 90_000


def _prompt_action_timeout_ms() -> int:
    raw = (os.environ.get("CHATGPT_PROMPT_ACTION_TIMEOUT_MS") or "").strip()
    if not raw:
        return 90_000
    try:
        return max(5_000, int(raw))
    except ValueError:
        return 90_000


async def _goto_with_retry(page, url: str, *, ctx: Context | None) -> None:
    timeout_ms = _navigation_timeout_ms()
    attempts = 2
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            await page.goto(url, wait_until="commit", timeout=timeout_ms)
            return
        except Exception as exc:
            last_exc = exc
            msg = str(exc)
            transient = any(
                token in msg
                for token in [
                    "ERR_CONNECTION_RESET",
                    "ERR_CONNECTION_CLOSED",
                    "ERR_NETWORK_CHANGED",
                    "ECONNRESET",
                    "NS_ERROR_NET_RESET",
                ]
            )
            if attempt < attempts and transient:
                await _ctx_info(ctx, f"Navigation failed ({msg}); retrying…")
                await page.wait_for_timeout(random.randint(1500, 3500))
                continue
            raise
    if last_exc:
        raise last_exc
