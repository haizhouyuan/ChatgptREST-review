from __future__ import annotations

import asyncio
import os
import random
import time

from mcp.server.fastmcp import Context

from chatgpt_web_mcp.runtime.util import _ctx_info


def _min_prompt_interval_seconds() -> float:
    raw = (os.environ.get("CHATGPT_MIN_PROMPT_INTERVAL_SECONDS") or "").strip()
    if not raw:
        # Default to conservative pacing to reduce the chance of triggering web UI anti-abuse.
        # Set CHATGPT_MIN_PROMPT_INTERVAL_SECONDS=0 to disable.
        return 61.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 61.0


def _gemini_min_prompt_interval_seconds() -> float:
    raw = (os.environ.get("GEMINI_MIN_PROMPT_INTERVAL_SECONDS") or "").strip()
    if not raw:
        return _min_prompt_interval_seconds()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return _min_prompt_interval_seconds()


def _qwen_min_prompt_interval_seconds() -> float:
    raw = (os.environ.get("QWEN_MIN_PROMPT_INTERVAL_SECONDS") or "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


async def _respect_prompt_interval(
    *,
    last_sent_at: float,
    min_interval_seconds: float,
    label: str,
    ctx: Context | None,
) -> None:
    if min_interval_seconds <= 0:
        return
    if last_sent_at <= 0:
        return

    elapsed = time.time() - last_sent_at
    if elapsed >= min_interval_seconds:
        return

    target_interval = max(min_interval_seconds, 60.0 + random.uniform(0.0, 3.0))
    wait_s = target_interval - elapsed
    if wait_s <= 0:
        return
    await _ctx_info(ctx, f"Rate-limit guard: waiting {wait_s:.1f}s before next {label} prompt…")
    await asyncio.sleep(wait_s)
