from __future__ import annotations

from typing import Any, Mapping


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def classify_stuck_wait_job(
    row: Mapping[str, Any],
    *,
    now: float,
    threshold_seconds: float,
) -> dict[str, Any]:
    status = _as_text(row.get("status")).lower()
    phase = _as_text(row.get("phase")).lower()
    updated_at = _as_float(row.get("updated_at"))
    idle_seconds = max(0.0, float(now) - updated_at)
    lease_owner = _as_text(row.get("lease_owner"))
    lease_expires_at = _as_float(row.get("lease_expires_at"))
    not_before = _as_float(row.get("not_before"))

    if status != "in_progress" or phase != "wait":
        return {"stuck": False, "reason": "not_wait_in_progress", "idle_seconds": idle_seconds}
    if idle_seconds < float(max(0.0, threshold_seconds)):
        return {"stuck": False, "reason": "recent_progress", "idle_seconds": idle_seconds}

    active_lease = bool(lease_owner) or lease_expires_at > float(now)
    expired_lease = lease_expires_at > 0.0 and lease_expires_at <= float(now)

    if active_lease:
        return {"stuck": True, "reason": "leased_wait_no_progress", "idle_seconds": idle_seconds}
    if expired_lease:
        return {"stuck": True, "reason": "expired_wait_lease", "idle_seconds": idle_seconds}
    if not_before > float(now):
        return {"stuck": False, "reason": "backoff_wait", "idle_seconds": idle_seconds}
    return {"stuck": False, "reason": "queued_wait", "idle_seconds": idle_seconds}


def is_stuck_wait_job(
    row: Mapping[str, Any],
    *,
    now: float,
    threshold_seconds: float,
) -> bool:
    return bool(classify_stuck_wait_job(row, now=now, threshold_seconds=threshold_seconds).get("stuck"))
