from __future__ import annotations

import os
import random
from typing import Any

from mcp.server.fastmcp import Context

from chatgpt_web_mcp.env import _env_float, _env_int, _env_int_range, _truthy_env
from chatgpt_web_mcp.runtime.util import _ctx_info


def _delay_range_ms() -> tuple[int, int]:
    raw = (os.environ.get("CHATGPT_ACTION_DELAY_MS") or "").strip()
    if not raw:
        return (600, 1200)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return (600, 1200)
    if len(parts) == 1:
        base = max(0, int(parts[0]))
        return (base, max(base, base * 2))
    low = max(0, int(parts[0]))
    high = max(low, int(parts[1]))
    return (low, high)


def _random_log_enabled() -> bool:
    return _truthy_env("CHATGPT_RANDOMNESS_LOG", False)


async def _random_log(ctx: Context | None, message: str) -> None:
    if not _random_log_enabled():
        return
    await _ctx_info(ctx, f"[random] {message}")


async def _human_pause(page) -> None:
    low, high = _delay_range_ms()
    await page.wait_for_timeout(random.randint(low, high))


def _type_delay_profile() -> dict[str, Any]:
    raw_mean = (os.environ.get("CHATGPT_TYPE_DELAY_MEAN_MS") or "").strip()
    if raw_mean:
        mean_ms = _env_int("CHATGPT_TYPE_DELAY_MEAN_MS", 100)
    else:
        mean_ms = _env_int("CHATGPT_TYPE_DELAY_MS", 100)
    std_ms = _env_int("CHATGPT_TYPE_DELAY_STD_MS", 30)
    min_ms = _env_int("CHATGPT_TYPE_DELAY_MIN_MS", 20)
    max_ms = _env_int("CHATGPT_TYPE_DELAY_MAX_MS", 220)
    pause_chance = _env_float("CHATGPT_TYPE_THINK_PAUSE_CHANCE", 0.06)
    punct_pause_chance = _env_float("CHATGPT_TYPE_THINK_PAUSE_PUNCT_CHANCE", 0.2)
    pause_low, pause_high = _env_int_range("CHATGPT_TYPE_THINK_PAUSE_MS", 300, 1200)
    return {
        "mean_ms": max(0, int(mean_ms)),
        "std_ms": max(0, int(std_ms)),
        "min_ms": max(0, int(min_ms)),
        "max_ms": max(0, int(max_ms)),
        "pause_chance": max(0.0, float(pause_chance)),
        "punct_pause_chance": max(0.0, float(punct_pause_chance)),
        "pause_low_ms": max(0, int(pause_low)),
        "pause_high_ms": max(0, int(pause_high)),
    }


def _sample_key_delay_ms(profile: dict[str, Any]) -> int:
    mean_ms = int(profile.get("mean_ms") or 0)
    std_ms = int(profile.get("std_ms") or 0)
    min_ms = int(profile.get("min_ms") or 0)
    max_ms = int(profile.get("max_ms") or 0)
    if mean_ms <= 0:
        return 0
    if std_ms > 0:
        val = int(random.gauss(mean_ms, std_ms))
    else:
        val = int(mean_ms)
    if max_ms > 0:
        val = min(val, max_ms)
    if min_ms > 0:
        val = max(val, min_ms)
    return max(0, val)


def _should_insert_think_pause(ch: str, profile: dict[str, Any]) -> bool:
    if not ch:
        return False
    if random.random() < float(profile.get("pause_chance") or 0.0):
        return True
    if ch in ".!?,;:。！？；：" and random.random() < float(profile.get("punct_pause_chance") or 0.0):
        return True
    return False


def _sample_think_pause_ms(profile: dict[str, Any]) -> int:
    low = int(profile.get("pause_low_ms") or 0)
    high = int(profile.get("pause_high_ms") or low)
    if high < low:
        high = low
    if high <= 0:
        return 0
    return random.randint(low, high)


def _type_delay_ms() -> int:
    raw = (os.environ.get("CHATGPT_TYPE_DELAY_MS") or "").strip()
    if not raw:
        return 25
    return max(0, int(raw))
