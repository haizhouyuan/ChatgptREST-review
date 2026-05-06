from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from chatgptrest.core.db import meta_get, meta_set
from chatgptrest.providers.registry import provider_id_for_kind


_PAUSE_MODE_KEY = "pause_mode"
_PAUSE_UNTIL_KEY = "pause_until"
_PAUSE_REASON_KEY = "pause_reason"


@dataclass(frozen=True)
class PauseState:
    mode: str
    until_ts: float
    reason: str | None

    def is_active(self, *, now: float | None = None) -> bool:
        now_ts = time.time() if now is None else float(now)
        return bool(self.until_ts and now_ts < float(self.until_ts) and self.mode not in {"", "none"})


def get_pause_state(conn) -> PauseState:
    rows = conn.execute(
        "SELECT k, v FROM meta WHERE k IN (?,?,?)",
        (_PAUSE_MODE_KEY, _PAUSE_UNTIL_KEY, _PAUSE_REASON_KEY),
    ).fetchall()
    kv: dict[str, str] = {}
    for r in rows:
        try:
            k = str(r["k"])
            v = str(r["v"])
        except Exception:
            continue
        kv[k] = v

    mode = (kv.get(_PAUSE_MODE_KEY) or "").strip().lower() or "none"
    until_raw = (kv.get(_PAUSE_UNTIL_KEY) or "").strip()
    reason = (kv.get(_PAUSE_REASON_KEY) or "").strip() or None
    try:
        until_ts = float(until_raw) if until_raw else 0.0
    except Exception:
        until_ts = 0.0
    return PauseState(mode=mode, until_ts=float(until_ts), reason=reason)


def set_pause_state(
    conn,
    *,
    mode: str,
    until_ts: float,
    reason: str | None = None,
) -> PauseState:
    normalized_mode = (str(mode or "").strip().lower() or "none")
    meta_set(conn, key=_PAUSE_MODE_KEY, value=normalized_mode)
    meta_set(conn, key=_PAUSE_UNTIL_KEY, value=str(float(until_ts)))
    meta_set(conn, key=_PAUSE_REASON_KEY, value=(str(reason).strip() if reason else ""))
    return PauseState(mode=normalized_mode, until_ts=float(until_ts), reason=(str(reason).strip() if reason else None))


def clear_pause_state(conn) -> PauseState:
    return set_pause_state(conn, mode="none", until_ts=0.0, reason=None)


def pause_filter_allows_job(*, pause: PauseState, phase: str | None, kind: str | None, now: float | None = None) -> bool:
    """
    Return whether a job should be claimable under the current pause state.

    Modes:
    - none: allow all jobs.
    - send: pause only send-phase jobs (except repair.*); allow wait-phase + repair.*.
    - all: pause all non-repair jobs.
    """
    if not pause.is_active(now=now):
        return True
    k = str(kind or "").strip().lower()
    if k.startswith("repair."):
        return True
    reason = str(pause.reason or "").strip().lower()
    provider_id = provider_id_for_kind(k)
    # Auto-pause currently comes from the ChatGPT blocked-state subsystem. Keep the
    # pause narrow so a ChatGPT Cloudflare/cooldown incident does not stall Gemini
    # planning jobs on unrelated lanes.
    if reason.startswith("auto_blocked:") and provider_id == "gemini":
        return True
    mode = str(pause.mode or "").strip().lower()
    if mode == "all":
        return False
    # Default: send-only pause.
    p = str(phase or "").strip().lower() or "send"
    return p == "wait"
