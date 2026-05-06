from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


DEFAULT_STALE_BACKLOG_SECONDS_BY_STATUS: dict[str, float] = {
    "needs_followup": 24.0 * 3600.0,
    "blocked": 24.0 * 3600.0,
    "cooldown": 24.0 * 3600.0,
}


@dataclass(frozen=True)
class JobBacklogCounts:
    raw_by_status: dict[str, int]
    active_by_status: dict[str, int]
    stale_by_status: dict[str, int]

    @property
    def stale_total(self) -> int:
        return int(sum(int(v) for v in self.stale_by_status.values()))


def _normalized_stale_thresholds(
    stale_after_seconds_by_status: dict[str, float] | None = None,
) -> dict[str, float]:
    normalized = dict(DEFAULT_STALE_BACKLOG_SECONDS_BY_STATUS)
    for key, value in dict(stale_after_seconds_by_status or {}).items():
        status = str(key or "").strip().lower()
        if not status:
            continue
        try:
            seconds = float(value)
        except Exception:
            continue
        if seconds <= 0:
            normalized.pop(status, None)
            continue
        normalized[status] = float(seconds)
    return normalized


def summarize_job_backlog_counts(
    rows: list[Any],
    *,
    now: float,
    stale_after_seconds_by_status: dict[str, float] | None = None,
) -> JobBacklogCounts:
    thresholds = _normalized_stale_thresholds(stale_after_seconds_by_status)
    raw = Counter()
    active = Counter()
    stale = Counter()

    for row in rows:
        status = str(row["status"] or "").strip()
        if not status:
            continue
        normalized_status = status.lower()
        raw[status] += 1
        try:
            updated_at = float(row["updated_at"] or 0.0)
        except Exception:
            updated_at = 0.0
        cutoff_seconds = thresholds.get(normalized_status)
        is_stale = bool(cutoff_seconds and updated_at > 0 and updated_at <= float(now - cutoff_seconds))
        if is_stale:
            stale[status] += 1
        else:
            active[status] += 1

    return JobBacklogCounts(
        raw_by_status=dict(sorted(raw.items())),
        active_by_status=dict(sorted(active.items())),
        stale_by_status=dict(sorted(stale.items())),
    )
