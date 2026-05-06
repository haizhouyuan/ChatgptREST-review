"""Incident correlation helpers — extracted from maint_daemon.py for shared use."""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chatgptrest.ops_shared.models import IncidentState


# ---------------------------------------------------------------------------
# Signature hashing
# ---------------------------------------------------------------------------


def sig_hash(text: str) -> str:
    """Deterministic 12-char hex hash of incident/error signature text."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Infra error classification
# ---------------------------------------------------------------------------


_INFRA_JOB_ERROR_RE = re.compile(
    r"("
    r"CDP connect failed|"
    r"connect_over_cdp|"
    r"TargetClosedError|"
    r"Target page, context or browser has been closed|"
    r"BrowserContext\.new_page: Target page|"
    r"ws://127\.0\.0\.1:9222/"
    r")",
    re.I,
)


def looks_like_infra_job_error(*, error_type: str, error: str) -> bool:
    """True if the error pattern suggests infrastructure (driver/chrome) failure."""
    et = str(error_type or "").strip().lower()
    if et in {"infraerror", "targetclosederror"}:
        return True
    return bool(_INFRA_JOB_ERROR_RE.search(str(error or "")))


# ---------------------------------------------------------------------------
# Error normalization
# ---------------------------------------------------------------------------


def normalize_error(text: str) -> str:
    """Trim and normalize error text for incident storage."""
    s = (text or "").strip().replace("\r\n", "\n")
    if len(s) > 500:
        s = s[:500] + "..."
    return s


# ---------------------------------------------------------------------------
# Incident signal freshness
# ---------------------------------------------------------------------------


def incident_signal_is_fresh(
    *, signal_ts: float, last_seen_ts: float, epsilon: float = 1e-6,
) -> bool:
    """True if signal_ts is strictly newer than last_seen_ts (within epsilon)."""
    return float(signal_ts) > (float(last_seen_ts) + float(epsilon))


def incident_should_rollover_for_signal(
    *,
    signal_ts: float,
    last_seen_ts: float,
    dedupe_seconds: int,
) -> bool:
    """True if the time gap justifies creating a new incident (rollover)."""
    if not incident_signal_is_fresh(signal_ts=signal_ts, last_seen_ts=last_seen_ts):
        return False
    return (float(signal_ts) - float(last_seen_ts)) >= float(max(60, int(dedupe_seconds)))


def incident_freshness_gate(
    *,
    incident: "IncidentState",
    signal_ts: float,
    is_new_incident: bool,
    job_id: str,
) -> dict[str, bool]:
    """Decide whether an incident needs further work based on signal freshness."""
    has_fresh_signal = bool(is_new_incident) or incident_signal_is_fresh(
        signal_ts=signal_ts,
        last_seen_ts=float(incident.last_seen_ts),
    )
    if str(job_id) not in incident.job_ids:
        has_fresh_signal = True
    needs_followup_work = (incident.repair_job_id is None) or (incident.codex_last_run_ts is None)
    should_skip_touch = (not has_fresh_signal) and (not needs_followup_work)
    return {
        "has_fresh_signal": bool(has_fresh_signal),
        "needs_followup_work": bool(needs_followup_work),
        "should_skip_touch": bool(should_skip_touch),
    }
