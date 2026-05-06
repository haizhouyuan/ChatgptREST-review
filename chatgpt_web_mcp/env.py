from __future__ import annotations

import os
import re


def _truthy_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return int(default)
    raw = raw.strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return float(default)
    raw = raw.strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _env_int_range(name: str, default_low: int, default_high: int) -> tuple[int, int]:
    raw = (os.environ.get(name) or "").strip()
    default_low = int(default_low)
    default_high = int(default_high)
    defaults = (min(default_low, default_high), max(default_low, default_high))

    if not raw:
        return defaults

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return defaults

    try:
        if len(parts) == 1:
            val = int(parts[0])
            return (val, val)
        low = int(parts[0])
        high = int(parts[1])
        return (min(low, high), max(low, high))
    except Exception:
        return defaults


def _compile_env_regex(env_name: str, default_pattern: str, flags: int = re.I) -> re.Pattern[str]:
    override = (os.environ.get(env_name) or "").strip()
    extra = (os.environ.get(f"{env_name}_EXTRA") or "").strip()
    if override:
        pattern = override
    elif extra:
        pattern = f"(?:{default_pattern}|{extra})"
    else:
        pattern = default_pattern
    try:
        return re.compile(pattern, flags)
    except re.error:
        return re.compile(default_pattern, flags)
