from __future__ import annotations

import json
import sqlite3
import time
from typing import Any


def try_reserve(conn: sqlite3.Connection, *, key: str, min_interval_seconds: int) -> float:
    """
    Reserve a slot for an action that must be spaced by `min_interval_seconds`.

    Returns:
      - 0.0 if the slot was reserved (and last_ts was updated)
      - wait_seconds (>0) if the caller should wait and retry
    """
    if min_interval_seconds <= 0:
        return 0.0
    k = str(key or "").strip()
    if not k:
        raise ValueError("key is empty")

    now = time.time()
    row = conn.execute("SELECT last_ts FROM rate_limits WHERE k = ?", (k,)).fetchone()
    last_ts = float(row["last_ts"]) if row is not None and row["last_ts"] is not None else 0.0
    if now < last_ts:
        # System clock moved backwards: clamp to avoid long stalls until "time catches up".
        conn.execute(
            """
            INSERT INTO rate_limits(k, last_ts) VALUES(?, ?)
            ON CONFLICT(k) DO UPDATE SET last_ts = excluded.last_ts
            """,
            (k, now),
        )
        last_ts = now
    next_allowed = last_ts + float(min_interval_seconds)
    if now < next_allowed:
        return float(next_allowed - now)

    conn.execute(
        """
        INSERT INTO rate_limits(k, last_ts) VALUES(?, ?)
        ON CONFLICT(k) DO UPDATE SET last_ts = excluded.last_ts
        """,
        (k, now),
    )
    return 0.0


def cooldown_wait_seconds(
    conn: sqlite3.Connection,
    *,
    key: str,
    now: float | None = None,
) -> float:
    """
    Return remaining cooldown seconds for a key, or 0.0 when no cooldown is active.
    Expired rows are deleted opportunistically by the caller's transaction.
    """
    k = str(key or "").strip()
    if not k:
        raise ValueError("key is empty")

    now_ts = time.time() if now is None else float(now)
    row = conn.execute("SELECT until_ts FROM cooldowns WHERE k = ?", (k,)).fetchone()
    if row is None or row["until_ts"] is None:
        return 0.0
    try:
        until_ts = float(row["until_ts"])
    except Exception:
        conn.execute("DELETE FROM cooldowns WHERE k = ?", (k,))
        return 0.0
    if until_ts <= now_ts:
        conn.execute("DELETE FROM cooldowns WHERE k = ?", (k,))
        return 0.0
    return max(0.0, until_ts - now_ts)


def set_cooldown_until(
    conn: sqlite3.Connection,
    *,
    key: str,
    until_ts: float,
    reason: str = "",
    payload: dict[str, Any] | None = None,
    now: float | None = None,
) -> float:
    """
    Set or extend a cooldown. Existing later cooldowns are never shortened.
    Returns the effective cooldown timestamp.
    """
    k = str(key or "").strip()
    if not k:
        raise ValueError("key is empty")

    now_ts = time.time() if now is None else float(now)
    try:
        desired_until = float(until_ts)
    except Exception:
        desired_until = now_ts
    desired_until = max(now_ts, desired_until)

    row = conn.execute("SELECT until_ts FROM cooldowns WHERE k = ?", (k,)).fetchone()
    existing_until = 0.0
    if row is not None and row["until_ts"] is not None:
        try:
            existing_until = float(row["until_ts"])
        except Exception:
            existing_until = 0.0
    effective_until = max(existing_until, desired_until)
    payload_json = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    conn.execute(
        """
        INSERT INTO cooldowns(k, until_ts, updated_at, reason, payload_json)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(k) DO UPDATE SET
          until_ts = excluded.until_ts,
          updated_at = excluded.updated_at,
          reason = excluded.reason,
          payload_json = excluded.payload_json
        """,
        (k, float(effective_until), float(now_ts), str(reason or ""), payload_json),
    )
    return float(effective_until)


def try_reserve_fixed_window(
    conn: sqlite3.Connection,
    *,
    key: str,
    window_seconds: int,
    max_per_window: int,
    now: float | None = None,
) -> float:
    """
    Reserve a slot for an action that must not exceed `max_per_window` per fixed window.

    Returns:
      - 0.0 if the slot was reserved (and the window counter incremented)
      - wait_seconds (>0) if the caller should wait until the next window
    """
    if max_per_window <= 0:
        return 0.0
    if window_seconds <= 0:
        return 0.0
    k = str(key or "").strip()
    if not k:
        raise ValueError("key is empty")

    win = int(window_seconds)
    if win <= 0:
        return 0.0
    max_n = int(max_per_window)
    if max_n <= 0:
        return 0.0

    now_ts = time.time() if now is None else float(now)
    window_start = int(now_ts // float(win)) * win
    next_window = float(window_start + win)

    started = False
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
        started = True
    try:
        # Keep the table bounded: we only need the current window row for this key.
        conn.execute("DELETE FROM usage_counters WHERE k = ? AND window_start < ?", (k, int(window_start)))

        row = conn.execute(
            "SELECT count FROM usage_counters WHERE k = ? AND window_start = ?",
            (k, int(window_start)),
        ).fetchone()
        cur = int(row["count"] or 0) if row is not None and row["count"] is not None else 0
        if cur >= max_n:
            if started:
                conn.rollback()
            return max(0.0, next_window - float(now_ts))

        conn.execute(
            """
            INSERT INTO usage_counters(k, window_start, count) VALUES(?, ?, 1)
            ON CONFLICT(k, window_start) DO UPDATE SET count = count + 1
            """,
            (k, int(window_start)),
        )
        if started:
            conn.commit()
        return 0.0
    except Exception:
        if started:
            conn.rollback()
        raise
