"""Phase normalization — DB layer and executor layer.

Two separate concerns with intentionally different vocabularies:

- **DB layer** (``normalize_db_phase``):  ``send`` or ``wait`` — the only values
  stored in the ``jobs.phase`` column.

- **Executor layer** (``normalize_execution_phase``):  ``send``, ``wait``, or
  ``full`` — ``full`` means "run both send and wait in one shot", which is the
  default for executor callers.
"""
from __future__ import annotations

from typing import Any


def normalize_db_phase(value: Any) -> str:
    """Normalize phase for job_store DB column: ``send`` or ``wait``."""
    raw = str(value or "").strip().lower()
    if raw == "wait":
        return "wait"
    return "send"


def normalize_execution_phase(value: Any) -> str:
    """Normalize phase for executors: ``send``, ``wait``, or ``full``."""
    raw = str(value or "").strip().lower()
    if raw in {"send", "wait"}:
        return raw
    if raw in {"all", "full", "both"}:
        return "full"
    return "full"
