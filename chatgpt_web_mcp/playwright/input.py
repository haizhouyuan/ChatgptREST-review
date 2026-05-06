from __future__ import annotations

import asyncio
from typing import Any

from chatgpt_web_mcp.playwright.navigation import _prompt_action_timeout_ms
from chatgpt_web_mcp.runtime.humanize import (
    _sample_key_delay_ms,
    _sample_think_pause_ms,
    _should_insert_think_pause,
    _type_delay_profile,
)


async def _type_question(prompt: Any, question: str) -> None:
    timeout_ms = _prompt_action_timeout_ms()
    if "\n" in question or "\r" in question:
        await prompt.fill(question, timeout=timeout_ms)
        return
    profile = _type_delay_profile()
    if int(profile.get("mean_ms") or 0) <= 0 or len(question) > 800:
        await prompt.fill(question, timeout=timeout_ms)
        return
    await prompt.fill("", timeout=timeout_ms)
    for ch in question:
        await prompt.type(ch, delay=0, timeout=timeout_ms)
        delay_ms = _sample_key_delay_ms(profile)
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)
        if _should_insert_think_pause(ch, profile):
            pause_ms = _sample_think_pause_ms(profile)
            if pause_ms > 0:
                await asyncio.sleep(pause_ms / 1000.0)
