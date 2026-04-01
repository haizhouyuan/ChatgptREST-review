from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from chatgptrest.api.schemas import (
    BuildInfoView,
    GlobalJobEvents,
    IdempotencyRecordView,
    IncidentView,
    IncidentsList,
    JobsList,
    JobSummary,
    OpsStatusView,
    PauseSetRequest,
    PauseView,
    RemediationActionsList,
    RemediationActionView,
)
from chatgptrest.core.backlog_health import summarize_job_backlog_counts
from chatgptrest.core.config import AppConfig
from chatgptrest.core.build_info import get_build_info
from chatgptrest.core import client_issues
from chatgptrest.core.db import connect
from chatgptrest.core.pause import clear_pause_state, get_pause_state, set_pause_state
from chatgptrest.ops_shared.queue_health import is_stuck_wait_job


def _pause_view(*, pause, now: float) -> PauseView:
    active = bool(pause.is_active(now=now))
    remaining = max(0.0, float(pause.until_ts) - float(now)) if active else 0.0
    return PauseView(
        mode=str(pause.mode),
        until_ts=float(pause.until_ts),
        active=active,
        now=float(now),
        seconds_remaining=float(remaining),
        reason=(pause.reason or None),
    )


def _parse_json_object(raw: Any | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        obj = json.loads(str(raw))
    except Exception:
        return {"_raw": str(raw)}
    if isinstance(obj, dict):
        return obj
    return {"_raw": obj}


def _ops_issue_family_id(issue: client_issues.ClientIssueRecord) -> str:
    metadata = dict(issue.metadata or {})
    explicit = str(metadata.get("family_id") or "").strip()
    if explicit:
        return explicit
    return f"fp:{issue.fingerprint_hash}"


def _ops_stuck_wait_threshold_seconds() -> float:
    try:
        raw = float(os.environ.get("CHATGPTREST_OPS_STUCK_WAIT_SECONDS") or 240.0)
    except Exception:
        raw = 240.0
    return max(60.0, min(raw, 86_400.0))


def _read_ui_canary_summary(*, artifacts_dir: Path) -> tuple[bool | None, list[str]]:
    latest = artifacts_dir / "monitor" / "ui_canary" / "latest.json"
    try:
        obj = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return None, []
    providers = obj.get("providers")
    if not isinstance(providers, list) or not providers:
        return None, []
    failed: list[str] = []
    for item in providers:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        ok = bool(item.get("ok"))
        try:
            threshold = max(1, int(item.get("threshold") or 1))
        except Exception:
            threshold = 1
        try:
            consecutive_failures = int(item.get("consecutive_failures") or 0)
        except Exception:
            consecutive_failures = 0
        if provider and not ok and consecutive_failures >= threshold:
            failed.append(provider)
    return not failed, failed


def _incident_from_row(r: Any) -> IncidentView:
    """Build an IncidentView from a SQLite Row — shared by list & get."""
    job_ids: list[str] = []
    raw_jobs = r["job_ids_json"]
    if raw_jobs:
        try:
            obj = json.loads(str(raw_jobs))
            if isinstance(obj, list):
                job_ids = [str(x) for x in obj if str(x or "").strip()]
        except Exception:
            job_ids = []

    return IncidentView(
        incident_id=str(r["incident_id"]),
        fingerprint_hash=str(r["fingerprint_hash"]),
        signature=str(r["signature"]),
        category=(str(r["category"]).strip() if r["category"] is not None else None) or None,
        severity=(str(r["severity"]).strip() if r["severity"] is not None else "P2"),
        status=str(r["status"]),
        created_at=float(r["created_at"]),
        updated_at=float(r["updated_at"]),
        last_seen_at=float(r["last_seen_at"]),
        count=int(r["count"] or 0),
        job_ids=job_ids,
        evidence_dir=(str(r["evidence_dir"]).strip() if r["evidence_dir"] is not None else None) or None,
        repair_job_id=(str(r["repair_job_id"]).strip() if r["repair_job_id"] is not None else None) or None,
        codex_input_hash=(str(r["codex_input_hash"]).strip() if r["codex_input_hash"] is not None else None) or None,
        codex_last_run_ts=(float(r["codex_last_run_ts"]) if r["codex_last_run_ts"] is not None else None),
        codex_run_count=int(r["codex_run_count"] or 0),
        codex_last_ok=(
            None
            if r["codex_last_ok"] is None
            else bool(int(r["codex_last_ok"]))
            if str(r["codex_last_ok"]).isdigit()
            else bool(r["codex_last_ok"])
        ),
        codex_last_error=(str(r["codex_last_error"]).strip() if r["codex_last_error"] is not None else None) or None,
        codex_autofix_last_ts=(float(r["codex_autofix_last_ts"]) if r["codex_autofix_last_ts"] is not None else None),
        codex_autofix_run_count=int(r["codex_autofix_run_count"] or 0),
    )


def action_hint_for_status(*, status: str, phase: str | None) -> str | None:
    """Return a recommended next-action hint given job status and phase.

    Shared by routes_jobs (single-job view) and routes_ops (jobs-list summary).
    """
    st = str(status or "").strip().lower()
    ph = str(phase or "").strip().lower()
    if st == "completed":
        return "fetch_answer"
    if st == "canceled":
        return "resubmit_if_needed"
    if st == "error":
        return "inspect_error_and_run_repair_check"
    if st == "blocked":
        return "inspect_block_reason_and_recover"
    if st == "needs_followup":
        return "submit_followup_or_enable_autofix"
    if st == "cooldown":
        return "retry_after_cooldown"
    if st in {"queued", "in_progress"}:
        if ph == "send":
            return "wait_or_poll_send_queue"
        if ph == "wait":
            return "wait_for_completion_or_fetch_conversation"
        return "wait_for_completion"
    return None


def make_ops_router(cfg: AppConfig) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/ops/pause", response_model=PauseView)
    def ops_pause_get() -> PauseView:
        with connect(cfg.db_path) as conn:
            pause = get_pause_state(conn)
        now = time.time()
        return _pause_view(pause=pause, now=now)

    @router.post("/v1/ops/pause", response_model=PauseView)
    def ops_pause_set(req: PauseSetRequest) -> PauseView:
        mode = str(req.mode or "").strip().lower()
        if mode in {"", "none"}:
            now = time.time()
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                pause = clear_pause_state(conn)
                # Wake jobs that were explicitly deferred by pause at enqueue time.
                # Safety: only touch queued jobs with a future not_before AND a matching defer event.
                conn.execute(
                    """
                    UPDATE jobs
                    SET not_before = ?
                    WHERE status = 'queued'
                      AND not_before > ?
                      AND job_id IN (
                        SELECT job_id
                        FROM job_events
                        WHERE type = 'job_deferred_by_pause'
                      )
                    """,
                    (float(now), float(now)),
                )
                conn.commit()
            return _pause_view(pause=pause, now=now)

        if mode not in {"send", "all"}:
            raise HTTPException(status_code=400, detail={"error": "invalid_pause_mode", "mode": mode})

        if req.until_ts is not None and req.duration_seconds is not None:
            raise HTTPException(status_code=400, detail={"error": "ambiguous_pause_until", "detail": "Provide either until_ts or duration_seconds"})

        now = time.time()
        until_ts: float | None = None
        if req.until_ts is not None:
            try:
                until_ts = float(req.until_ts)
            except Exception:
                until_ts = None
        elif req.duration_seconds is not None:
            try:
                until_ts = now + float(int(req.duration_seconds))
            except Exception:
                until_ts = None

        if until_ts is None or until_ts <= now:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_pause_until",
                    "detail": "until_ts must be in the future (or use duration_seconds)",
                },
            )

        reason = (str(req.reason).strip() if req.reason else None) or None
        if reason and len(reason) > 200:
            reason = reason[:200]

        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            pause = set_pause_state(conn, mode=mode, until_ts=float(until_ts), reason=reason)
            conn.commit()
        return _pause_view(pause=pause, now=time.time())

    @router.get("/v1/ops/incidents", response_model=IncidentsList)
    def ops_incidents_list(
        status: str | None = None,
        severity: str | None = None,
        before_ts: float | None = None,
        before_incident_id: str | None = None,
        limit: int = 200,
    ) -> IncidentsList:
        limit = max(1, min(1000, int(limit)))
        status_raw = (status or "").strip()
        severity_raw = (severity or "").strip().upper()
        before = float(before_ts) if before_ts is not None else None

        status_values: list[str] = []
        active_alias = False
        if status_raw:
            parts = [p.strip().lower() for p in status_raw.split(",") if p.strip()]
            if parts:
                active_alias = "active" in parts
                status_values = [p for p in parts if p != "active"]

        with connect(cfg.db_path) as conn:
            clauses: list[str] = []
            params: list[Any] = []
            if before is not None:
                if before_incident_id:
                    clauses.append("(updated_at < ? OR (updated_at = ? AND incident_id < ?))")
                    params.extend([float(before), float(before), str(before_incident_id)])
                else:
                    clauses.append("updated_at < ?")
                    params.append(float(before))

            if active_alias:
                # "active" is a status alias meaning "not resolved".
                # If the caller also includes "resolved", the filter becomes a no-op (all statuses).
                if "resolved" not in status_values:
                    clauses.append("LOWER(status) != 'resolved'")
            elif status_values:
                placeholders = ",".join(["?"] * len(status_values))
                clauses.append(f"LOWER(status) IN ({placeholders})")
                params.extend([str(s) for s in status_values])
            if severity_raw:
                clauses.append("UPPER(severity) = ?")
                params.append(str(severity_raw))

            where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(
                f"""
                SELECT *
                FROM incidents
                {where_sql}
                ORDER BY updated_at DESC, incident_id DESC
                LIMIT ?
                """,
                (*params, int(limit)),
            ).fetchall()

        incidents: list[IncidentView] = []
        next_before: float | None = None
        next_before_id: str | None = None
        for r in rows:
            incidents.append(_incident_from_row(r))
            next_before = float(r["updated_at"])
            next_before_id = str(r["incident_id"])

        return IncidentsList(next_before_ts=next_before, next_before_incident_id=next_before_id, incidents=incidents)

    @router.get("/v1/ops/incidents/{incident_id}", response_model=IncidentView)
    def ops_incident_get(incident_id: str) -> IncidentView:
        with connect(cfg.db_path) as conn:
            row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (str(incident_id),)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return _incident_from_row(row)

    @router.get("/v1/ops/incidents/{incident_id}/actions", response_model=RemediationActionsList)
    def ops_incident_actions_list(incident_id: str, limit: int = 200) -> RemediationActionsList:
        limit = max(1, min(1000, int(limit)))
        with connect(cfg.db_path) as conn:
            exists = conn.execute("SELECT 1 FROM incidents WHERE incident_id = ?", (str(incident_id),)).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail="incident not found")
            rows = conn.execute(
                """
                SELECT *
                FROM remediation_actions
                WHERE incident_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (str(incident_id), int(limit)),
            ).fetchall()

        actions: list[RemediationActionView] = []
        for r in rows:
            actions.append(
                RemediationActionView(
                    action_id=str(r["action_id"]),
                    incident_id=str(r["incident_id"]),
                    action_type=str(r["action_type"]),
                    status=str(r["status"]),
                    risk_level=str(r["risk_level"] or "low"),
                    created_at=float(r["created_at"]),
                    started_at=(float(r["started_at"]) if r["started_at"] is not None else None),
                    completed_at=(float(r["completed_at"]) if r["completed_at"] is not None else None),
                    result=_parse_json_object(r["result_json"]),
                    error_type=(str(r["error_type"]).strip() if r["error_type"] is not None else None) or None,
                    error=(str(r["error"]).strip() if r["error"] is not None else None) or None,
                )
            )
        return RemediationActionsList(incident_id=str(incident_id), actions=actions)

    @router.get("/v1/ops/events", response_model=GlobalJobEvents)
    def ops_events(after_id: int = 0, limit: int = 200) -> GlobalJobEvents:
        after_id = max(0, int(after_id))
        limit = max(1, min(5000, int(limit)))
        with connect(cfg.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, job_id, ts, type, payload_json
                FROM job_events
                WHERE id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (after_id, limit),
            ).fetchall()

        events = []
        for r in rows:
            payload = _parse_json_object(r["payload_json"])
            if payload is not None and not isinstance(payload, dict):
                payload = {"_raw": payload}
            events.append(
                {
                    "id": int(r["id"]),
                    "job_id": str(r["job_id"]),
                    "ts": float(r["ts"]),
                    "type": str(r["type"]),
                    "payload": payload,
                }
            )
        next_after = int(events[-1]["id"]) if events else after_id
        return GlobalJobEvents(after_id=after_id, next_after_id=next_after, events=events)  # type: ignore[arg-type]

    @router.get("/v1/ops/idempotency/{idempotency_key}", response_model=IdempotencyRecordView)
    def ops_idempotency_get(idempotency_key: str) -> IdempotencyRecordView:
        with connect(cfg.db_path) as conn:
            row = conn.execute(
                "SELECT idempotency_key, request_hash, job_id, created_at FROM idempotency WHERE idempotency_key = ?",
                (str(idempotency_key),),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="idempotency key not found")
        return IdempotencyRecordView(
            idempotency_key=str(row["idempotency_key"]),
            request_hash=str(row["request_hash"]),
            job_id=str(row["job_id"]),
            created_at=float(row["created_at"]),
        )

    @router.get("/v1/ops/jobs", response_model=JobsList)
    def ops_jobs_list(
        status: str | None = None,
        kind_prefix: str | None = None,
        phase: str | None = None,
        before_ts: float | None = None,
        before_job_id: str | None = None,
        limit: int = 200,
    ) -> JobsList:
        limit = max(1, min(1000, int(limit)))
        status_raw = (status or "").strip()
        statuses: list[str] | None = None
        if status_raw:
            parts = [p.strip().lower() for p in status_raw.split(",") if p.strip()]
            if parts:
                statuses = parts
        kind_like = None
        kind_prefix_raw = (kind_prefix or "").strip()
        if kind_prefix_raw:
            kind_like = f"{kind_prefix_raw}%"
        phase_raw = (phase or "").strip().lower()
        if phase_raw and phase_raw not in {"send", "wait"}:
            raise HTTPException(status_code=400, detail={"error": "invalid_phase", "phase": phase_raw})
        before = float(before_ts) if before_ts is not None else None

        with connect(cfg.db_path) as conn:
            clauses: list[str] = []
            params: list[Any] = []
            if before is not None:
                if before_job_id:
                    clauses.append("(created_at < ? OR (created_at = ? AND job_id < ?))")
                    params.extend([float(before), float(before), str(before_job_id)])
                else:
                    clauses.append("created_at < ?")
                    params.append(float(before))
            if statuses:
                placeholders = ",".join(["?"] * len(statuses))
                clauses.append(f"LOWER(status) IN ({placeholders})")
                params.extend([str(s) for s in statuses])
            if kind_like is not None:
                clauses.append("kind LIKE ?")
                params.append(kind_like)
            if phase_raw:
                clauses.append("COALESCE(phase, 'send') = ?")
                params.append(str(phase_raw))
            where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(
                f"""
                SELECT job_id, kind, parent_job_id, phase, status, created_at, updated_at,
                       not_before, attempts, max_attempts, conversation_url,
                       answer_path, conversation_export_path, last_error_type, last_error
                FROM jobs
                {where_sql}
                ORDER BY created_at DESC, job_id DESC
                LIMIT ?
                """,
                (*params, int(limit)),
            ).fetchall()

        jobs: list[JobSummary] = []
        next_before: float | None = None
        next_before_id: str | None = None
        for r in rows:
            st = str(r["status"])
            phase_value = (str(r["phase"]).strip() if r["phase"] is not None else None) or None
            reason_visible = st in {"error", "blocked", "cooldown", "needs_followup", "canceled"}
            jobs.append(
                JobSummary(
                    job_id=str(r["job_id"]),
                    kind=str(r["kind"]),
                    parent_job_id=(str(r["parent_job_id"]).strip() if r["parent_job_id"] is not None else None) or None,
                    phase=phase_value,
                    status=st,
                    created_at=float(r["created_at"]),
                    updated_at=float(r["updated_at"]),
                    not_before=(float(r["not_before"]) if r["not_before"] is not None else None),
                    attempts=(int(r["attempts"]) if r["attempts"] is not None else None),
                    max_attempts=(int(r["max_attempts"]) if r["max_attempts"] is not None else None),
                    conversation_url=(str(r["conversation_url"]).strip() if r["conversation_url"] is not None else None) or None,
                    answer_path=(str(r["answer_path"]).strip() if r["answer_path"] is not None else None) or None,
                    conversation_export_path=(str(r["conversation_export_path"]).strip() if r["conversation_export_path"] is not None else None) or None,
                    action_hint=action_hint_for_status(status=st, phase=phase_value),
                    reason_type=(str(r["last_error_type"]).strip() if reason_visible and r["last_error_type"] is not None else None) or None,
                    reason=(str(r["last_error"]).strip() if reason_visible and r["last_error"] is not None else None) or None,
                )
            )
            next_before = float(r["created_at"])
            next_before_id = str(r["job_id"])
        return JobsList(next_before_ts=next_before, next_before_job_id=next_before_id, jobs=jobs)

    @router.get("/v1/ops/status", response_model=OpsStatusView)
    def ops_status() -> OpsStatusView:
        now = time.time()
        build = BuildInfoView(**get_build_info(include_dirty=True))
        active_open_issues = 0
        active_issue_families = 0
        with connect(cfg.db_path) as conn:
            pause = get_pause_state(conn)
            rows = conn.execute("SELECT status, updated_at FROM jobs").fetchall()
            backlog_counts = summarize_job_backlog_counts(rows, now=now)
            by_status = dict(backlog_counts.active_by_status)
            row = conn.execute("SELECT COUNT(1) AS n FROM incidents WHERE status != 'resolved'").fetchone()
            active_incidents = int(row["n"] or 0) if row is not None else 0
            row = conn.execute(
                "SELECT COUNT(DISTINCT COALESCE(NULLIF(fingerprint_hash, ''), signature)) AS n "
                "FROM incidents WHERE status != 'resolved'"
            ).fetchone()
            active_incident_families = int(row["n"] or 0) if row is not None else 0
            last_event = conn.execute("SELECT MAX(id) AS id FROM job_events").fetchone()
            last_event_id = int(last_event["id"]) if last_event is not None and last_event["id"] is not None else None
            threshold_seconds = float(_ops_stuck_wait_threshold_seconds())
            wait_rows = conn.execute(
                """
                SELECT status, phase, updated_at, not_before, lease_owner, lease_expires_at
                FROM jobs
                WHERE phase = 'wait'
                  AND status = 'in_progress'
                """
            ).fetchall()
            stuck_wait_jobs = sum(
                1
                for row in wait_rows
                if is_stuck_wait_job(dict(row), now=float(now), threshold_seconds=threshold_seconds)
            )
            issues, _, _ = client_issues.list_issues(conn, status="open,in_progress", limit=1000)
            active_open_issues = len(issues)
            active_issue_families = len({_ops_issue_family_id(issue) for issue in issues})

        ui_canary_ok, ui_canary_failed_providers = _read_ui_canary_summary(artifacts_dir=cfg.artifacts_dir)
        attention_reasons: list[str] = []
        if active_incidents > 0:
            attention_reasons.append("active_incidents")
        if active_open_issues > 0:
            attention_reasons.append("active_open_issues")
        if stuck_wait_jobs > 0:
            attention_reasons.append("stuck_wait_jobs")
        if backlog_counts.stale_total > 0:
            attention_reasons.append("stale_backlog")
        if ui_canary_ok is False:
            attention_reasons.append("ui_canary_failed")
        return OpsStatusView(
            now=float(now),
            pause=_pause_view(pause=pause, now=now),
            jobs_by_status=by_status,
            raw_jobs_by_status=dict(backlog_counts.raw_by_status),
            stale_jobs_by_status=dict(backlog_counts.stale_by_status),
            stale_jobs_total=int(backlog_counts.stale_total),
            active_incidents=active_incidents,
            active_incident_families=active_incident_families,
            active_open_issues=active_open_issues,
            active_issue_families=active_issue_families,
            stuck_wait_jobs=stuck_wait_jobs,
            ui_canary_ok=ui_canary_ok,
            ui_canary_failed_providers=ui_canary_failed_providers,
            attention_reasons=attention_reasons,
            last_job_event_id=last_event_id,
            build=build,
        )

    @router.get("/v1/ops/config")
    def ops_config_get() -> dict[str, Any]:
        """Dump all registered env vars with dual-layer redaction.

        Sensitive values (explicit flag OR name pattern TOKEN/SECRET/KEY/...)
        are masked with ``***`` before leaving the process.
        """
        from chatgptrest.core.env import dump_all

        return {"ok": True, "config": dump_all()}

    @router.post("/v1/ops/graceful-restart")
    def ops_graceful_restart() -> dict[str, Any]:
        """Signal worker processes to drain and restart for hot code reload.

        Sends SIGUSR1 to all chatgptrest worker processes. Each worker will:
        1. Finish its currently executing job (if any)
        2. Exit cleanly (exit code 0)
        3. Be restarted by the process supervisor with new code

        In-flight jobs are NOT interrupted. New jobs are held in the queue
        until the worker restarts (~seconds).
        """
        import os as _os
        import signal as _signal
        import subprocess as _sp

        signaled_pids: list[int] = []
        errors: list[str] = []

        try:
            # Find worker processes by command pattern
            result = _sp.run(
                ["pgrep", "-f", "chatgptrest.worker"],
                capture_output=True, text=True, timeout=5,
            )
            pids = [int(p.strip()) for p in result.stdout.strip().split("\n") if p.strip().isdigit()]

            my_pid = _os.getpid()
            for pid in pids:
                if pid == my_pid:
                    continue  # Don't signal ourselves (API server)
                try:
                    _os.kill(pid, _signal.SIGUSR1)
                    signaled_pids.append(pid)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    errors.append(f"pid={pid}: permission denied")
        except Exception as exc:
            errors.append(f"pgrep failed: {exc}")

        return {
            "ok": len(signaled_pids) > 0 or not errors,
            "action": "graceful_restart",
            "signaled_pids": signaled_pids,
            "signal": "SIGUSR1",
            "errors": errors or None,
            "hint": "Workers will finish current job then exit. Supervisor should auto-restart them with new code.",
        }

    return router
