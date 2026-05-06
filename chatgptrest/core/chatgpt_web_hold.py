from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from chatgptrest.core.db import meta_get, meta_set


_HOLD_REASON_KEY = "chatgpt_web_hold_reason"
_HOLD_UNTIL_KEY = "chatgpt_web_hold_until"
_HOLD_SOURCE_KEY = "chatgpt_web_hold_source"
_HOLD_NOTE_KEY = "chatgpt_web_hold_note"
_HOLD_UPDATED_AT_KEY = "chatgpt_web_hold_updated_at"

CHATGPT_WEB_HOLD_REASONS = frozenset(
    {
        "frontend_rate_limit",
        "manual_pro_session",
    }
)


@dataclass(frozen=True)
class ChatGPTWebHoldState:
    reason: str
    until_ts: float
    source: str | None = None
    note: str | None = None

    def is_active(self, *, now: float | None = None) -> bool:
        now_ts = time.time() if now is None else float(now)
        return bool(self.reason and self.until_ts > now_ts)

    def retry_after_seconds(self, *, now: float | None = None) -> int:
        now_ts = time.time() if now is None else float(now)
        return max(1, int(self.until_ts - now_ts + 0.999))

    def to_detail(self, *, now: float | None = None) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "blocked_until": float(self.until_ts),
            "retry_after_seconds": self.retry_after_seconds(now=now),
            "source": self.source or "db_chatgpt_web_hold",
            "note": self.note,
        }


def get_chatgpt_web_hold(conn, *, now: float | None = None) -> ChatGPTWebHoldState | None:
    reason = (meta_get(conn, key=_HOLD_REASON_KEY) or "").strip()
    if reason not in CHATGPT_WEB_HOLD_REASONS:
        return None
    until_raw = (meta_get(conn, key=_HOLD_UNTIL_KEY) or "").strip()
    try:
        until_ts = float(until_raw) if until_raw else 0.0
    except Exception:
        return None
    state = ChatGPTWebHoldState(
        reason=reason,
        until_ts=float(until_ts),
        source=(meta_get(conn, key=_HOLD_SOURCE_KEY) or "").strip() or None,
        note=(meta_get(conn, key=_HOLD_NOTE_KEY) or "").strip() or None,
    )
    return state if state.is_active(now=now) else None


def set_chatgpt_web_hold(
    conn,
    *,
    reason: str,
    until_ts: float,
    source: str = "",
    note: str = "",
    now: float | None = None,
) -> ChatGPTWebHoldState:
    normalized_reason = str(reason or "").strip()
    if normalized_reason not in CHATGPT_WEB_HOLD_REASONS:
        raise ValueError(f"unsupported ChatGPT Web hold reason: {normalized_reason}")
    now_ts = time.time() if now is None else float(now)
    desired_until = max(float(until_ts), now_ts)
    existing = get_chatgpt_web_hold(conn, now=now_ts)
    effective_until = max(float(existing.until_ts), desired_until) if existing else desired_until
    meta_set(conn, key=_HOLD_REASON_KEY, value=normalized_reason)
    meta_set(conn, key=_HOLD_UNTIL_KEY, value=str(float(effective_until)))
    meta_set(conn, key=_HOLD_SOURCE_KEY, value=str(source or "").strip())
    meta_set(conn, key=_HOLD_NOTE_KEY, value=str(note or "").strip())
    meta_set(conn, key=_HOLD_UPDATED_AT_KEY, value=str(float(now_ts)))
    return ChatGPTWebHoldState(
        reason=normalized_reason,
        until_ts=float(effective_until),
        source=str(source or "").strip() or None,
        note=str(note or "").strip() or None,
    )


def clear_chatgpt_web_hold(conn) -> None:
    meta_set(conn, key=_HOLD_REASON_KEY, value="")
    meta_set(conn, key=_HOLD_UNTIL_KEY, value="0")
    meta_set(conn, key=_HOLD_SOURCE_KEY, value="")
    meta_set(conn, key=_HOLD_NOTE_KEY, value="")
    meta_set(conn, key=_HOLD_UPDATED_AT_KEY, value=str(float(time.time())))


def chatgpt_web_hold_blocks_kind(kind: str | None) -> bool:
    return str(kind or "").strip().lower().startswith("chatgpt_web.")
