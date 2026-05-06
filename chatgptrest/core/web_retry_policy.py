from __future__ import annotations

import math
import os
import random


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def web_human_retry_floor_seconds() -> float:
    raw = _env_float("CHATGPTREST_WEB_HUMAN_RETRY_FLOOR_SECONDS", 90.0)
    if not math.isfinite(raw):
        raw = 90.0
    return max(30.0, min(raw, 3600.0))


def web_human_retry_jitter_max_seconds() -> float:
    raw = _env_float("CHATGPTREST_WEB_HUMAN_RETRY_JITTER_MAX_SECONDS", 15.0)
    if not math.isfinite(raw):
        raw = 15.0
    return max(0.0, min(raw, 300.0))


def human_visible_web_retry_after_seconds(
    base_seconds: float | int,
    *,
    max_seconds: float | int | None = 3600.0,
    jitter: bool = True,
) -> float:
    floor = web_human_retry_floor_seconds()
    try:
        value = float(base_seconds)
    except Exception:
        value = floor
    if not math.isfinite(value):
        value = floor
    value = max(floor, value)

    upper: float | None = None
    if max_seconds is not None:
        try:
            upper = float(max_seconds)
        except Exception:
            upper = None
        if upper is not None and not math.isfinite(upper):
            upper = None
        if upper is not None:
            upper = max(floor, upper)
            value = min(value, upper)

    if not jitter:
        return value

    jitter_cap = web_human_retry_jitter_max_seconds()
    if upper is not None:
        jitter_cap = min(jitter_cap, max(0.0, upper - value))
    if jitter_cap <= 0:
        return value
    return value + random.uniform(0.0, jitter_cap)


def human_visible_web_retry_after_int(
    base_seconds: float | int,
    *,
    max_seconds: float | int | None = 3600.0,
    jitter: bool = True,
) -> int:
    value = human_visible_web_retry_after_seconds(base_seconds, max_seconds=max_seconds, jitter=jitter)
    return int(math.ceil(value))
