from __future__ import annotations

import inspect
import re

from mcp.server.fastmcp import Context


async def _ctx_info(ctx: Context | None, message: str) -> None:
    if not ctx:
        return
    try:
        result = ctx.info(message)
        if inspect.isawaitable(result):
            await result
    except Exception:
        return


def _coerce_error_text(value: object, *, limit: int = 1500) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "_", (value or "").strip().lower()).strip("_")
    return slug or 'debug'

