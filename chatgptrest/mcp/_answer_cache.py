"""Answer prefetch cache for L0 tools — pre-fetches answers when bg wait completes."""

from __future__ import annotations

import asyncio
import time
import urllib.parse
from typing import Any


# ── Cache State ──────────────────────────────────────────────────────────

_CACHE: dict[str, dict[str, Any]] = {}  # job_id -> normalized answer payload + fetched_at
_LOCK = asyncio.Lock()
MAX_SIZE = 200
PREFETCH_CHARS = 32000
TTL_SECONDS = 3600.0


def normalize_answer_payload(answer: Any, *, requested_offset: int = 0) -> dict[str, Any] | None:
    """Normalize current and legacy /answer payload shapes into one internal form."""
    if not isinstance(answer, dict) or answer.get("ok") is False:
        return None

    offset_raw = answer.get("offset")
    try:
        offset = int(offset_raw) if offset_raw is not None else max(0, int(requested_offset))
    except Exception:
        offset = max(0, int(requested_offset))

    if "chunk" in answer or "returned_chars" in answer:
        content = str(answer.get("chunk") or "")
        returned_chars = answer.get("returned_chars")
        try:
            length = int(returned_chars) if returned_chars is not None else len(content)
        except Exception:
            length = len(content)
        next_offset_raw = answer.get("next_offset")
        try:
            next_offset = int(next_offset_raw) if next_offset_raw is not None else None
        except Exception:
            next_offset = None
        done_raw = answer.get("done")
        if isinstance(done_raw, bool):
            done = done_raw
        elif done_raw is None:
            done = next_offset is None
        else:
            done = bool(done_raw)
        total_bytes = offset + length if done else None
        return {
            "content": content,
            "offset": offset,
            "length": max(0, length),
            "total_bytes": total_bytes,
            "next_offset": next_offset,
            "done": done,
        }

    if "content" not in answer and "length" not in answer and "total_bytes" not in answer:
        return None

    content = str(answer.get("content") or "")
    length_raw = answer.get("length")
    try:
        length = int(length_raw) if length_raw is not None else len(content)
    except Exception:
        length = len(content)
    total_bytes_raw = answer.get("total_bytes")
    try:
        total_bytes = int(total_bytes_raw) if total_bytes_raw is not None else offset + length
    except Exception:
        total_bytes = offset + length
    next_offset_raw = answer.get("next_offset")
    try:
        next_offset = int(next_offset_raw) if next_offset_raw is not None else None
    except Exception:
        next_offset = None
    done_raw = answer.get("done")
    if isinstance(done_raw, bool):
        done = done_raw
    elif done_raw is None:
        done = total_bytes <= offset + length
    else:
        done = bool(done_raw)
    if next_offset is None and not done:
        next_offset = offset + length
    return {
        "content": content,
        "offset": offset,
        "length": max(0, length),
        "total_bytes": max(offset + length, total_bytes),
        "next_offset": next_offset,
        "done": done,
    }


async def prefetch(job_id: str, *, http_json_fn: Any, base_url: str, auth_headers: dict[str, str]) -> None:
    """Pre-fetch and cache the first chunk of an answer. Best-effort, never raises."""
    try:
        qs = urllib.parse.urlencode({"offset": 0, "max_chars": PREFETCH_CHARS}, doseq=False)
        answer = await asyncio.to_thread(
            http_json_fn,
            method="GET",
            url=f"{base_url}/v1/jobs/{urllib.parse.quote(str(job_id))}/answer?{qs}",
            headers=auth_headers,
            timeout_seconds=30.0,
        )
        normalized = normalize_answer_payload(answer, requested_offset=0)
        if normalized is not None:
            async with _LOCK:
                if len(_CACHE) >= MAX_SIZE:
                    oldest_key = min(_CACHE, key=lambda k: _CACHE[k].get("fetched_at", 0))
                    _CACHE.pop(oldest_key, None)
                _CACHE[str(job_id)] = {**normalized, "fetched_at": time.time()}
    except Exception:
        pass


async def get(job_id: str) -> dict[str, Any] | None:
    """Get cached answer, or None if not available / expired."""
    async with _LOCK:
        cached = _CACHE.get(str(job_id))
        if cached is None:
            return None
        if time.time() - cached.get("fetched_at", 0) > TTL_SECONDS:
            _CACHE.pop(str(job_id), None)
            return None
        return dict(cached)
