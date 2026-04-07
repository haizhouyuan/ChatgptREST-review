"""Shared lightweight helpers used across finbot sub-modules.

Every helper in this file is a pure function with no external dependencies
beyond the standard library, making them safe to import from any finbot module.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def json_dumps(value: Any) -> str:
    """Deterministic JSON dump with sorted keys."""
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def slugify(value: str) -> str:
    """Convert text to a URL-safe slug."""
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "item"


def normalize_match_key(value: Any) -> str:
    """Reduce text to lowercase alphanumeric for fuzzy matching."""
    return re.sub(r"[^a-z0-9]+", "", text_value(value).lower())


def stable_digest(payload: dict[str, Any]) -> str:
    """Short deterministic SHA1 digest for ID generation."""
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def inbox_item_id(prefix: str, logical_key: str) -> str:
    """Build a stable inbox item identifier."""
    return f"{prefix}-{slugify(logical_key)}"


def text_value(raw: Any) -> str:
    """Coerce any value to a stripped string."""
    return str(raw or "").strip()


def as_float(raw: Any) -> float:
    """Coerce any value to float, defaulting to 0.0."""
    try:
        return float(raw)
    except Exception:
        return 0.0


def normalized_claim_text(value: Any) -> str:
    """Normalize claim text for comparison."""
    return re.sub(r"\s+", " ", text_value(value)).strip().lower()


def decision_distance(value: Any) -> int:
    """Map decision label to a distance-from-action integer."""
    text = text_value(value).lower()
    if text in {"act", "action", "invest", "invest_now"}:
        return 0
    if "prepare" in text:
        return 1
    if "watch" in text:
        return 2
    if text in {"review", "review_required", "monitor"}:
        return 3
    if text in {"archive", "archived", "ignore"}:
        return 4
    return 3
