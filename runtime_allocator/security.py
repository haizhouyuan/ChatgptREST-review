"""Security utilities for runtime_allocator."""

from __future__ import annotations

import re


def safe_slug(value: str, max_len: int = 40) -> str:
    """Sanitize a string for safe use in filenames.

    Strips path separators, limits length, allows only alphanumerics + dash/underscore.
    """
    safe = re.sub(r"[^\w\-]", "_", value)
    safe = safe.strip("_.")
    safe = safe.replace("..", "_")
    return safe[:max_len]
