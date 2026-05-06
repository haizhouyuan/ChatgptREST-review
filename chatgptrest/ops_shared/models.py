"""Shared data models for maint daemon and ops subsystems."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class IncidentState:
    """In-memory state for an active incident tracked by the maint daemon."""

    incident_id: str
    signature: str
    sig_hash: str
    created_ts: float
    last_seen_ts: float
    count: int
    job_ids: list[str]
    repair_job_id: str | None = None
    codex_input_hash: str | None = None
    codex_last_run_ts: float | None = None
    codex_run_count: int = 0
    codex_last_ok: bool | None = None
    codex_last_error: str | None = None
    codex_autofix_last_ts: float | None = None
    codex_autofix_run_count: int = 0


# ---------------------------------------------------------------------------
# Job parameter helpers
# ---------------------------------------------------------------------------


def job_expected_max_seconds(params_json: str) -> int:
    """Estimate max wall-clock seconds a job should take based on its params."""
    try:
        params = json.loads(params_json or "{}")
    except Exception:
        params = {}
    if not isinstance(params, dict):
        params = {}
    timeout_s = int(params.get("timeout_seconds") or 0)
    max_wait_s = int(params.get("max_wait_seconds") or 0)
    if timeout_s <= 0:
        timeout_s = 600
    if max_wait_s <= 0:
        max_wait_s = 1800
    return int(timeout_s + max_wait_s + 120)
