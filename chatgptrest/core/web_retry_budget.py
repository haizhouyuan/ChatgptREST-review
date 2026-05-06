from __future__ import annotations

import math
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from chatgptrest.core import env as _env_registry
from chatgptrest.providers.registry import provider_id_for_kind, provider_specs


BROWSER_RETRY_SCHEDULED_EVENT = "browser_retry_scheduled"
BROWSER_RETRY_BUDGET_EXCEEDED_EVENT = "browser_retry_budget_exceeded"


@dataclass(frozen=True)
class WebRetryBudgetSnapshot:
    provider_id: str | None
    window_seconds: int
    max_per_job: int
    max_per_provider: int
    warn_ratio: float
    recent_job_retry_count: int
    recent_provider_retry_count: int
    warn_at_job: int
    warn_at_provider: int
    hot: bool
    exceeded: bool

    def as_payload(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "window_seconds": int(self.window_seconds),
            "max_per_job": int(self.max_per_job),
            "max_per_provider": int(self.max_per_provider),
            "warn_ratio": float(self.warn_ratio),
            "recent_job_retry_count": int(self.recent_job_retry_count),
            "recent_provider_retry_count": int(self.recent_provider_retry_count),
            "warn_at_job": int(self.warn_at_job),
            "warn_at_provider": int(self.warn_at_provider),
            "hot": bool(self.hot),
            "exceeded": bool(self.exceeded),
        }


def web_retry_budget_window_seconds() -> int:
    return max(60, int(_env_registry.get_int("CHATGPTREST_WEB_RETRY_BUDGET_WINDOW_SECONDS") or 900))


def web_retry_budget_max_per_job() -> int:
    return max(0, int(_env_registry.get_int("CHATGPTREST_WEB_RETRY_BUDGET_MAX_PER_JOB") or 0))


def web_retry_budget_max_per_provider() -> int:
    return max(0, int(_env_registry.get_int("CHATGPTREST_WEB_RETRY_BUDGET_MAX_PER_PROVIDER") or 0))


def web_retry_budget_warn_ratio() -> float:
    raw = float(_env_registry.get_float("CHATGPTREST_WEB_RETRY_BUDGET_WARN_RATIO") or 0.8)
    if not math.isfinite(raw):
        raw = 0.8
    return max(0.1, min(raw, 1.0))


def _warn_threshold(limit: int, ratio: float) -> int:
    if limit <= 0:
        return 0
    return max(1, int(math.ceil(float(limit) * float(ratio))))


def _count_recent_job_retries(conn: sqlite3.Connection, *, job_id: str, since_ts: float) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM job_events
        WHERE job_id = ?
          AND type = ?
          AND ts >= ?
        """,
        (str(job_id), BROWSER_RETRY_SCHEDULED_EVENT, float(since_ts)),
    ).fetchone()
    return int((row["n"] if row is not None else 0) or 0)


def _count_recent_provider_retries(conn: sqlite3.Connection, *, provider_id: str, since_ts: float) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM job_events
        WHERE type = ?
          AND ts >= ?
          AND coalesce(json_extract(payload_json, '$.provider_id'), '') = ?
        """,
        (BROWSER_RETRY_SCHEDULED_EVENT, float(since_ts), str(provider_id)),
    ).fetchone()
    return int((row["n"] if row is not None else 0) or 0)


def evaluate_web_retry_budget(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    kind: str | None,
    now: float | None = None,
) -> WebRetryBudgetSnapshot:
    provider_id = provider_id_for_kind(kind)
    window_seconds = web_retry_budget_window_seconds()
    max_per_job = web_retry_budget_max_per_job()
    max_per_provider = web_retry_budget_max_per_provider()
    warn_ratio = web_retry_budget_warn_ratio()
    if not provider_id:
        return WebRetryBudgetSnapshot(
            provider_id=None,
            window_seconds=window_seconds,
            max_per_job=max_per_job,
            max_per_provider=max_per_provider,
            warn_ratio=warn_ratio,
            recent_job_retry_count=0,
            recent_provider_retry_count=0,
            warn_at_job=_warn_threshold(max_per_job, warn_ratio),
            warn_at_provider=_warn_threshold(max_per_provider, warn_ratio),
            hot=False,
            exceeded=False,
        )
    now_ts = float(now if isinstance(now, (int, float)) else time.time())
    since_ts = float(now_ts - float(window_seconds))
    recent_job_retry_count = _count_recent_job_retries(conn, job_id=str(job_id), since_ts=since_ts)
    recent_provider_retry_count = _count_recent_provider_retries(conn, provider_id=str(provider_id), since_ts=since_ts)
    warn_at_job = _warn_threshold(max_per_job, warn_ratio)
    warn_at_provider = _warn_threshold(max_per_provider, warn_ratio)
    hot = (
        (warn_at_job > 0 and recent_job_retry_count >= warn_at_job)
        or (warn_at_provider > 0 and recent_provider_retry_count >= warn_at_provider)
    )
    exceeded = (
        (max_per_job > 0 and recent_job_retry_count >= max_per_job)
        or (max_per_provider > 0 and recent_provider_retry_count >= max_per_provider)
    )
    return WebRetryBudgetSnapshot(
        provider_id=str(provider_id),
        window_seconds=window_seconds,
        max_per_job=max_per_job,
        max_per_provider=max_per_provider,
        warn_ratio=warn_ratio,
        recent_job_retry_count=recent_job_retry_count,
        recent_provider_retry_count=recent_provider_retry_count,
        warn_at_job=warn_at_job,
        warn_at_provider=warn_at_provider,
        hot=bool(hot),
        exceeded=bool(exceeded),
    )


def summarize_recent_web_retry_budget(conn: sqlite3.Connection, *, now: float | None = None) -> dict[str, Any]:
    window_seconds = web_retry_budget_window_seconds()
    max_per_job = web_retry_budget_max_per_job()
    max_per_provider = web_retry_budget_max_per_provider()
    warn_ratio = web_retry_budget_warn_ratio()
    now_ts = float(now if isinstance(now, (int, float)) else time.time())
    since_ts = float(now_ts - float(window_seconds))

    scheduled_counts: dict[str, int] = {}
    for row in conn.execute(
        """
        SELECT coalesce(json_extract(payload_json, '$.provider_id'), '') AS provider_id, COUNT(*) AS n
        FROM job_events
        WHERE type = ?
          AND ts >= ?
        GROUP BY provider_id
        """,
        (BROWSER_RETRY_SCHEDULED_EVENT, float(since_ts)),
    ).fetchall():
        provider_id = str(row["provider_id"] or "").strip()
        if not provider_id:
            continue
        scheduled_counts[provider_id] = int(row["n"] or 0)

    exceeded_counts: dict[str, int] = {}
    for row in conn.execute(
        """
        SELECT coalesce(json_extract(payload_json, '$.provider_id'), '') AS provider_id, COUNT(*) AS n
        FROM job_events
        WHERE type = ?
          AND ts >= ?
        GROUP BY provider_id
        """,
        (BROWSER_RETRY_BUDGET_EXCEEDED_EVENT, float(since_ts)),
    ).fetchall():
        provider_id = str(row["provider_id"] or "").strip()
        if not provider_id:
            continue
        exceeded_counts[provider_id] = int(row["n"] or 0)

    providers: list[dict[str, Any]] = []
    hot_providers: list[str] = []
    warn_at_provider = _warn_threshold(max_per_provider, warn_ratio)
    total_exceeded_events = 0
    seen_provider_ids = {spec.provider_id for spec in provider_specs()}
    seen_provider_ids.update(scheduled_counts.keys())
    seen_provider_ids.update(exceeded_counts.keys())
    for provider_id in sorted(pid for pid in seen_provider_ids if pid):
        recent_retry_count = int(scheduled_counts.get(provider_id, 0))
        recent_budget_exceeded_count = int(exceeded_counts.get(provider_id, 0))
        total_exceeded_events += recent_budget_exceeded_count
        hot = bool(warn_at_provider > 0 and recent_retry_count >= warn_at_provider)
        exceeded = bool(max_per_provider > 0 and recent_retry_count >= max_per_provider)
        if hot:
            hot_providers.append(provider_id)
        providers.append(
            {
                "provider_id": provider_id,
                "recent_retry_count": recent_retry_count,
                "recent_budget_exceeded_count": recent_budget_exceeded_count,
                "max_per_provider": int(max_per_provider),
                "warn_at": int(warn_at_provider),
                "hot": hot,
                "exceeded": exceeded,
            }
        )
    return {
        "now": float(now_ts),
        "window_seconds": int(window_seconds),
        "max_per_job": int(max_per_job),
        "max_per_provider": int(max_per_provider),
        "warn_ratio": float(warn_ratio),
        "recent_budget_exceeded_events": int(total_exceeded_events),
        "hot_providers": hot_providers,
        "providers": providers,
        "recent_by_provider": {item["provider_id"]: int(item["recent_retry_count"]) for item in providers},
    }
