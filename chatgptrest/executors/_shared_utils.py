"""Shared utilities for ChatgptREST executors — DRY extraction of duplicated helpers.

This module consolidates functions that were independently defined in 3-4 executor
files (chatgpt_web_mcp.py, gemini_web_mcp.py, qwen_web_mcp.py, repair.py).
"""
from __future__ import annotations

import os
import time
from typing import Any


def truthy_env(name: str, default: bool) -> bool:
    """Parse boolean from environment variable.

    Replaces 3 duplicated ``_truthy_env()`` implementations.
    """
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    raw = raw.strip().lower()
    if not raw:
        return bool(default)
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def coerce_int(value: Any, default: int) -> int:
    """Coerce to int with fallback.

    Replaces 4 duplicated ``_coerce_int()`` implementations.
    """
    if value is None:
        return int(default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def normalize_phase(value: Any) -> str:
    """Normalize execution phase string.

    Replaces 3 duplicated ``_normalize_phase()`` implementations.
    """
    raw = str(value or "").strip().lower()
    if raw in {"send", "wait", "full"}:
        return raw
    return "full"


def now_monotonic() -> float:
    """Return current time as float timestamp.

    Replaces 4 duplicated ``_now()`` implementations. Uses ``time.time()``
    for wall-clock accuracy (matching existing behavior).
    """
    return time.time()


def as_int(value: object, default: int) -> int:
    """Robust int coercion used by repair.py."""
    if value is None:
        return int(default)
    if isinstance(value, bool):
        return int(default)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    raw = str(value).strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


def as_bool(value: object, default: bool) -> bool:
    """Robust bool coercion used by repair.py."""
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def as_str(value: object, default: str = "") -> str:
    """Robust str coercion used by repair.py."""
    if value is None:
        return str(default)
    return str(value)
