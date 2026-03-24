"""Rate-limit budget helpers — extracted from maint_daemon.py."""

from __future__ import annotations

from typing import Any


def parse_ts_list(value: Any) -> list[float]:
    """Parse a list of timestamps from JSON-deserialized data."""
    if not isinstance(value, list):
        return []
    out: list[float] = []
    for x in value:
        try:
            out.append(float(x))
        except Exception:
            continue
    return out


def trim_window(ts_list: list[float], *, now: float, window_seconds: float) -> list[float]:
    """Keep only timestamps within the rolling window."""
    win = max(1.0, float(window_seconds))
    return [float(t) for t in ts_list if (now - float(t)) <= win]
