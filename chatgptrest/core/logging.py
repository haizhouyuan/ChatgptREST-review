"""Structured logging setup with idempotency guard.

``setup_logging()`` is safe to call multiple times — subsequent calls are
no-ops, preventing duplicate handlers during testing or multi-worker setups.

Log format is controlled by ``CHATGPTREST_LOG_FORMAT``:
  - ``"json"`` → one JSON object per log line  (default for production)
  - ``"text"`` → human-readable format           (default for development)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

_CONFIGURED = False


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(obj, ensure_ascii=False)


_TEXT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(
    *,
    level: int | str | None = None,
    force_format: str | None = None,
) -> None:
    """Configure root logger — **idempotent**: second call is a no-op.

    Args:
        level: Log level override (default: ``INFO``).
        force_format: Override format (``"json"`` or ``"text"``).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    fmt = force_format or os.environ.get("CHATGPTREST_LOG_FORMAT", "text").strip().lower()
    log_level = level if level is not None else logging.INFO

    root = logging.getLogger()
    root.setLevel(log_level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(log_level)

    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT))

    root.addHandler(handler)


def reset_logging() -> None:
    """Reset for testing — allow ``setup_logging()`` to run again."""
    global _CONFIGURED
    _CONFIGURED = False
