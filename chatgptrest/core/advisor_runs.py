from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from chatgptrest.telemetry_contract import extract_identity_fields


_RUN_STATUSES: frozenset[str] = frozenset(
    {
        "NEW",
        "INTAKE_NORMALIZED",
        "PLAN_COMPILED",
        "DISPATCHING",
        "RUNNING",
        "WAITING_GATES",
        "PAUSED",
        "DEGRADED",
        "MANUAL_TAKEOVER",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    }
)

_RUN_TERMINAL_STATUSES: frozenset[str] = frozenset({"COMPLETED", "FAILED", "CANCELLED"})

_STEP_STATUSES: frozenset[str] = frozenset(
    {"PENDING", "LEASED", "EXECUTING", "RETRY_WAIT", "SUCCEEDED", "FAILED", "COMPENSATED"}
)

_LEASE_STATUSES: frozenset[str] = frozenset({"leased", "released", "expired"})


def _now() -> float:
    return time.time()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_loads_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    text = str(raw).strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def _normalize_run_status(status: str | None) -> str:
    s = str(status or "").strip().upper()
    if s in _RUN_STATUSES:
        return s
    return "NEW"


def _normalize_step_status(status: str | None) -> str:
    s = str(status or "").strip().upper()
    if s in _STEP_STATUSES:
        return s
    return "PENDING"


def _normalize_lease_status(status: str | None) -> str:
    s = str(status or "").strip().lower()
    if s in _LEASE_STATUSES:
        return s
    return "leased"


def _row_to_run(row: Any) -> dict[str, Any]:
    return {
        "run_id": str(row["run_id"]),
        "request_id": (str(row["request_id"]) if row["request_id"] is not None else None),
        "mode": str(row["mode"] or "balanced"),
        "status": _normalize_run_status(row["status"]),
        "route": (str(row["route"]) if row["route"] is not None else None),
        "raw_question": (str(row["raw_question"]) if row["raw_question"] is not None else None),
        "normalized_question": (str(row["normalized_question"]) if row["normalized_question"] is not None else None),
        "context": _json_loads_dict(row["context_json"]),
        "quality_threshold": (int(row["quality_threshold"]) if row["quality_threshold"] is not None else None),
        "crosscheck": bool(int(row["crosscheck"] or 0)),
        "max_retries": int(row["max_retries"] or 0),
        "orchestrate_job_id": (str(row["orchestrate_job_id"]) if row["orchestrate_job_id"] is not None else None),
        "final_job_id": (str(row["final_job_id"]) if row["final_job_id"] is not None else None),
        "degraded": bool(int(row["degraded"] or 0)),
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
        "ended_at": (float(row["ended_at"]) if row["ended_at"] is not None else None),
        "error_type": (str(row["error_type"]) if row["error_type"] is not None else None),
        "error": (str(row["error"]) if row["error"] is not None else None),
    }


def _row_to_step(row: Any) -> dict[str, Any]:
    return {
        "run_id": str(row["run_id"]),
        "step_id": str(row["step_id"]),
        "step_type": str(row["step_type"]),
        "status": _normalize_step_status(row["status"]),
        "attempt": int(row["attempt"] or 0),
        "job_id": (str(row["job_id"]) if row["job_id"] is not None else None),
        "lease_id": (str(row["lease_id"]) if row["lease_id"] is not None else None),
        "lease_expires_at": (float(row["lease_expires_at"]) if row["lease_expires_at"] is not None else None),
        "input": _json_loads_dict(row["input_json"]),
        "output": _json_loads_dict(row["output_json"]),
        "evidence_path": (str(row["evidence_path"]) if row["evidence_path"] is not None else None),
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
    }


def _row_to_lease(row: Any) -> dict[str, Any]:
    return {
        "lease_id": str(row["lease_id"]),
        "run_id": str(row["run_id"]),
        "step_id": str(row["step_id"]),
        "owner": (str(row["owner"]) if row["owner"] is not None else None),
        "token": (str(row["token"]) if row["token"] is not None else None),
        "status": _normalize_lease_status(row["status"]),
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
        "expires_at": (float(row["expires_at"]) if row["expires_at"] is not None else None),
        "heartbeat_at": (float(row["heartbeat_at"]) if row["heartbeat_at"] is not None else None),
    }


def new_run_id() -> str:
    return uuid.uuid4().hex


def new_lease_id() -> str:
    return uuid.uuid4().hex


def get_run(conn: Any, *, run_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM advisor_runs WHERE run_id = ?", (str(run_id),)).fetchone()
    if row is None:
        return None
    return _row_to_run(row)


def execution_identity_for_run(
    run: dict[str, Any],
    *,
    trace_id: str = "",
    job_id: str = "",
    task_ref: str = "",
    logical_task_id: str = "",
) -> dict[str, Any]:
    context = run.get("context") if isinstance(run.get("context"), dict) else {}
    resolved_trace_id = str(trace_id or context.get("trace_id") or "").strip()
    resolved_task_ref = str(task_ref or context.get("task_ref") or context.get("task_id") or "").strip()
    resolved_logical_task_id = str(logical_task_id or context.get("logical_task_id") or "").strip()
    resolved_job_id = str(
        job_id
        or run.get("final_job_id")
        or run.get("orchestrate_job_id")
        or context.get("job_id")
        or ""
    ).strip()
    return extract_identity_fields(
        {
            **context,
            "trace_id": resolved_trace_id,
            "run_id": str(run.get("run_id") or "").strip(),
            "job_id": resolved_job_id,
            "task_ref": resolved_task_ref,
            "logical_task_id": resolved_logical_task_id,
        }
    )


def create_run(
    conn: Any,
    *,
    run_id: str,
    request_id: str | None,
    mode: str,
    status: str,
    route: str | None,
    raw_question: str,
    normalized_question: str,
    context: dict[str, Any] | None,
    quality_threshold: int | None,
    crosscheck: bool,
    max_retries: int,
    orchestrate_job_id: str | None = None,
    final_job_id: str | None = None,
    degraded: bool = False,
) -> dict[str, Any]:
    now = _now()
    run_id_norm = str(run_id).strip()
    if not run_id_norm:
        raise ValueError("run_id is required")
    conn.execute(
        """
        INSERT INTO advisor_runs(
          run_id, request_id, mode, status, route, raw_question, normalized_question,
          context_json, quality_threshold, crosscheck, max_retries, orchestrate_job_id,
          final_job_id, degraded, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id_norm,
            (str(request_id).strip() if request_id else None),
            str(mode or "balanced"),
            _normalize_run_status(status),
            (str(route).strip() if route else None),
            str(raw_question or ""),
            str(normalized_question or ""),
            _json_dumps(dict(context or {})),
            (int(quality_threshold) if quality_threshold is not None else None),
            (1 if bool(crosscheck) else 0),
            max(0, int(max_retries)),
            (str(orchestrate_job_id).strip() if orchestrate_job_id else None),
            (str(final_job_id).strip() if final_job_id else None),
            (1 if bool(degraded) else 0),
            float(now),
            float(now),
        ),
    )
    run = get_run(conn, run_id=run_id_norm)
    if run is None:
        raise RuntimeError("failed to create advisor run")
    return run


def update_run(
    conn: Any,
    *,
    run_id: str,
    status: str | None = None,
    route: str | None = None,
    mode: str | None = None,
    normalized_question: str | None = None,
    quality_threshold: int | None = None,
    crosscheck: bool | None = None,
    max_retries: int | None = None,
    orchestrate_job_id: str | None = None,
    final_job_id: str | None = None,
    degraded: bool | None = None,
    error_type: str | None = None,
    error: str | None = None,
    ended_at: float | None = None,
) -> dict[str, Any] | None:
    existing = get_run(conn, run_id=run_id)
    if existing is None:
        return None
    updates: dict[str, Any] = {}
    if status is not None:
        updates["status"] = _normalize_run_status(status)
    if route is not None:
        updates["route"] = (str(route).strip() or None)
    if mode is not None:
        updates["mode"] = str(mode or "balanced")
    if normalized_question is not None:
        updates["normalized_question"] = str(normalized_question or "")
    if quality_threshold is not None:
        updates["quality_threshold"] = int(quality_threshold)
    if crosscheck is not None:
        updates["crosscheck"] = (1 if bool(crosscheck) else 0)
    if max_retries is not None:
        updates["max_retries"] = max(0, int(max_retries))
    if orchestrate_job_id is not None:
        updates["orchestrate_job_id"] = (str(orchestrate_job_id).strip() or None)
    if final_job_id is not None:
        updates["final_job_id"] = (str(final_job_id).strip() or None)
    if degraded is not None:
        updates["degraded"] = (1 if bool(degraded) else 0)
    if error_type is not None:
        updates["error_type"] = (str(error_type).strip() or None)
    if error is not None:
        updates["error"] = (str(error).strip() or None)

    status_next = str(updates.get("status") or existing.get("status") or "").strip().upper()
    if ended_at is not None:
        updates["ended_at"] = float(ended_at)
    elif status_next in _RUN_TERMINAL_STATUSES:
        updates["ended_at"] = float(_now())

    updates["updated_at"] = float(_now())
    if not updates:
        return existing
    cols = sorted(updates.keys())
    assignments = ", ".join([f"{c} = ?" for c in cols])
    values = [updates[c] for c in cols]
    values.append(str(run_id))
    conn.execute(f"UPDATE advisor_runs SET {assignments} WHERE run_id = ?", values)
    updated = get_run(conn, run_id=run_id)
    if updated is None:
        return None
    if status_next in _RUN_TERMINAL_STATUSES:
        try:
            from chatgptrest.quality.outcome_ledger import upsert_execution_outcome

            artifacts_dir = Path(
                os.environ.get("CHATGPTREST_ARTIFACTS_DIR", "artifacts")
            )
            upsert_execution_outcome(conn, run=updated, artifacts_dir=artifacts_dir)
        except Exception:
            # Observer-only ledger must not break the durable run spine.
            pass
    return updated


def get_step(conn: Any, *, run_id: str, step_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM advisor_steps WHERE run_id = ? AND step_id = ?",
        (str(run_id), str(step_id)),
    ).fetchone()
    if row is None:
        return None
    return _row_to_step(row)


def list_steps(conn: Any, *, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM advisor_steps WHERE run_id = ? ORDER BY created_at ASC, step_id ASC",
        (str(run_id),),
    ).fetchall()
    return [_row_to_step(r) for r in rows]


def upsert_step(
    conn: Any,
    *,
    run_id: str,
    step_id: str,
    step_type: str,
    status: str,
    attempt: int = 0,
    job_id: str | None = None,
    lease_id: str | None = None,
    lease_expires_at: float | None = None,
    input_obj: dict[str, Any] | None = None,
    output_obj: dict[str, Any] | None = None,
    evidence_path: str | None = None,
) -> dict[str, Any]:
    now = _now()
    existing = get_step(conn, run_id=run_id, step_id=step_id)
    if existing is None:
        conn.execute(
            """
            INSERT INTO advisor_steps(
              run_id, step_id, step_type, status, attempt, job_id, lease_id, lease_expires_at,
              input_json, output_json, evidence_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(run_id),
                str(step_id),
                str(step_type or "task"),
                _normalize_step_status(status),
                max(0, int(attempt)),
                (str(job_id).strip() if job_id else None),
                (str(lease_id).strip() if lease_id else None),
                (float(lease_expires_at) if lease_expires_at is not None else None),
                _json_dumps(dict(input_obj or {})),
                _json_dumps(dict(output_obj or {})),
                (str(evidence_path).strip() if evidence_path else None),
                float(now),
                float(now),
            ),
        )
    else:
        conn.execute(
            """
            UPDATE advisor_steps
            SET step_type = ?, status = ?, attempt = ?, job_id = ?, lease_id = ?, lease_expires_at = ?,
                input_json = ?, output_json = ?, evidence_path = ?, updated_at = ?
            WHERE run_id = ? AND step_id = ?
            """,
            (
                str(step_type or existing.get("step_type") or "task"),
                _normalize_step_status(status),
                max(0, int(attempt)),
                (str(job_id).strip() if job_id else None),
                (str(lease_id).strip() if lease_id else None),
                (float(lease_expires_at) if lease_expires_at is not None else None),
                _json_dumps(dict(input_obj or {})),
                _json_dumps(dict(output_obj or {})),
                (str(evidence_path).strip() if evidence_path else None),
                float(now),
                str(run_id),
                str(step_id),
            ),
        )
    row = get_step(conn, run_id=run_id, step_id=step_id)
    if row is None:
        raise RuntimeError("failed to upsert advisor step")
    return row


def upsert_lease(
    conn: Any,
    *,
    lease_id: str,
    run_id: str,
    step_id: str,
    owner: str | None,
    token: str | None,
    status: str,
    expires_at: float | None,
    heartbeat_at: float | None = None,
) -> None:
    now = _now()
    row = conn.execute("SELECT lease_id FROM advisor_leases WHERE lease_id = ?", (str(lease_id),)).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO advisor_leases(
              lease_id, run_id, step_id, owner, token, status, created_at, updated_at, expires_at, heartbeat_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(lease_id),
                str(run_id),
                str(step_id),
                (str(owner).strip() if owner else None),
                (str(token).strip() if token else None),
                _normalize_lease_status(status),
                float(now),
                float(now),
                (float(expires_at) if expires_at is not None else None),
                (float(heartbeat_at) if heartbeat_at is not None else None),
            ),
        )
        return
    conn.execute(
        """
        UPDATE advisor_leases
        SET owner = ?, token = ?, status = ?, updated_at = ?, expires_at = ?, heartbeat_at = ?
        WHERE lease_id = ?
        """,
        (
            (str(owner).strip() if owner else None),
            (str(token).strip() if token else None),
            _normalize_lease_status(status),
            float(now),
            (float(expires_at) if expires_at is not None else None),
            (float(heartbeat_at) if heartbeat_at is not None else None),
            str(lease_id),
        ),
    )


def list_leases(
    conn: Any,
    *,
    run_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    q = "SELECT * FROM advisor_leases"
    cond: list[str] = []
    vals: list[Any] = []
    if run_id is not None:
        cond.append("run_id = ?")
        vals.append(str(run_id))
    if status is not None:
        cond.append("status = ?")
        vals.append(_normalize_lease_status(status))
    if cond:
        q += " WHERE " + " AND ".join(cond)
    q += " ORDER BY updated_at ASC, lease_id ASC"
    rows = conn.execute(q, vals).fetchall()
    return [_row_to_lease(row) for row in rows]


def reclaim_expired_leases(
    conn: Any,
    *,
    run_id: str | None = None,
    now_ts: float | None = None,
) -> list[dict[str, Any]]:
    now = float(now_ts if now_ts is not None else _now())
    q = (
        "SELECT * FROM advisor_leases "
        "WHERE status = 'leased' AND expires_at IS NOT NULL AND expires_at <= ?"
    )
    vals: list[Any] = [now]
    if run_id is not None:
        q += " AND run_id = ?"
        vals.append(str(run_id))
    q += " ORDER BY expires_at ASC, lease_id ASC"
    rows = conn.execute(q, vals).fetchall()
    reclaimed: list[dict[str, Any]] = []
    for row in rows:
        lease = _row_to_lease(row)
        conn.execute(
            "UPDATE advisor_leases SET status = 'expired', updated_at = ?, heartbeat_at = ? WHERE lease_id = ?",
            (now, now, lease["lease_id"]),
        )
        step = get_step(conn, run_id=lease["run_id"], step_id=lease["step_id"])
        if step is not None and str(step.get("status") or "").upper() in {"LEASED", "EXECUTING"}:
            upsert_step(
                conn,
                run_id=lease["run_id"],
                step_id=lease["step_id"],
                step_type=str(step.get("step_type") or "task"),
                status="RETRY_WAIT",
                attempt=max(0, int(step.get("attempt") or 0)),
                job_id=(str(step.get("job_id") or "") or None),
                lease_id=str(lease["lease_id"]),
                lease_expires_at=(float(lease["expires_at"]) if lease.get("expires_at") is not None else None),
                input_obj=dict(step.get("input") or {}),
                output_obj=dict(step.get("output") or {}),
                evidence_path=(str(step.get("evidence_path") or "") or None),
            )
        append_event(
            conn,
            run_id=lease["run_id"],
            step_id=lease["step_id"],
            type="step.failed",
            attempt=max(0, int((step or {}).get("attempt") or 0)),
            payload={
                "reason_type": "LeaseExpired",
                "reason": "lease expired before step completion",
                "lease_id": lease["lease_id"],
                "expired_at": now,
            },
        )
        reclaimed.append(lease)
    return reclaimed


def append_event(
    conn: Any,
    *,
    run_id: str,
    type: str,
    step_id: str | None = None,
    payload: dict[str, Any] | None = None,
    ts: float | None = None,
    attempt: int | None = None,
    agent_id: str | None = None,
    session_key: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    evidence_path: str | None = None,
) -> int:
    event_ts = float(ts if ts is not None else _now())
    payload_out = dict(payload or {})
    payload_out.setdefault("run_id", str(run_id))
    payload_out.setdefault("step_id", (str(step_id) if step_id else None))
    payload_out.setdefault("attempt", (int(attempt) if attempt is not None else None))
    payload_out.setdefault("agent_id", (str(agent_id) if agent_id else None))
    payload_out.setdefault("session_key", (str(session_key) if session_key else None))
    payload_out.setdefault("correlation_id", (str(correlation_id) if correlation_id else None))
    payload_out.setdefault("idempotency_key", (str(idempotency_key) if idempotency_key else None))
    payload_out.setdefault("event_ts", event_ts)
    payload_out.setdefault("evidence_path", (str(evidence_path) if evidence_path else None))
    cur = conn.execute(
        """
        INSERT INTO advisor_events(run_id, step_id, ts, type, payload_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(run_id),
            (str(step_id).strip() if step_id else None),
            event_ts,
            str(type),
            _json_dumps(payload_out),
        ),
    )
    try:
        return int(cur.lastrowid or 0)
    except Exception:
        return 0


def has_event(conn: Any, *, run_id: str, type: str, step_id: str | None = None) -> bool:
    if step_id is None:
        row = conn.execute(
            "SELECT 1 FROM advisor_events WHERE run_id = ? AND type = ? LIMIT 1",
            (str(run_id), str(type)),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM advisor_events WHERE run_id = ? AND step_id = ? AND type = ? LIMIT 1",
            (str(run_id), str(step_id), str(type)),
        ).fetchone()
    return row is not None


def list_events(
    conn: Any,
    *,
    run_id: str,
    after_id: int = 0,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], int]:
    lim = max(1, min(1000, int(limit)))
    rows = conn.execute(
        """
        SELECT id, run_id, step_id, ts, type, payload_json
        FROM advisor_events
        WHERE run_id = ? AND id > ?
        ORDER BY id ASC
        LIMIT ?
        """,
        (str(run_id), max(0, int(after_id)), lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    next_after = max(0, int(after_id))
    for row in rows:
        ev_id = int(row["id"])
        out.append(
            {
                "id": ev_id,
                "run_id": str(row["run_id"]),
                "step_id": (str(row["step_id"]) if row["step_id"] is not None else None),
                "ts": float(row["ts"]),
                "type": str(row["type"]),
                "payload": _json_loads_dict(row["payload_json"]),
            }
        )
        next_after = ev_id
    return out, next_after


def replay_run(
    conn: Any,
    *,
    run_id: str,
    persist_snapshot: bool = False,
) -> dict[str, Any] | None:
    run = get_run(conn, run_id=run_id)
    if run is None:
        return None

    events: list[dict[str, Any]] = []
    after = 0
    while True:
        chunk, next_after = list_events(conn, run_id=run_id, after_id=after, limit=1000)
        if not chunk:
            break
        events.extend(chunk)
        if next_after <= after or len(chunk) < 1000:
            break
        after = next_after

    replay_status = str(run.get("status") or "NEW").upper()
    replay_degraded = bool(run.get("degraded"))
    replay_final_job_id = (str(run.get("final_job_id")) if run.get("final_job_id") is not None else None)
    replay_error_type = (str(run.get("error_type")) if run.get("error_type") is not None else None)
    replay_error = (str(run.get("error")) if run.get("error") is not None else None)
    replay_ended_at = (float(run.get("ended_at")) if run.get("ended_at") is not None else None)
    steps_by_id: dict[str, dict[str, Any]] = {}

    for ev in events:
        ev_type = str(ev.get("type") or "").strip()
        payload = dict(ev.get("payload") or {})
        step_id = str(ev.get("step_id") or payload.get("step_id") or "").strip()
        ts = float(ev.get("ts") or _now())
        attempt = max(0, int(payload.get("attempt") or 0))
        if step_id:
            step = steps_by_id.get(step_id)
            if step is None:
                step = {
                    "step_id": step_id,
                    "step_type": str(payload.get("step_type") or "task"),
                    "status": "PENDING",
                    "attempt": attempt,
                    "job_id": (str(payload.get("job_id")) if payload.get("job_id") else None),
                    "lease_id": (str(payload.get("lease_id")) if payload.get("lease_id") else None),
                    "lease_expires_at": (
                        float(payload.get("lease_expires_at")) if payload.get("lease_expires_at") is not None else None
                    ),
                    "evidence_path": (str(payload.get("evidence_path")) if payload.get("evidence_path") else None),
                    "created_at": ts,
                    "updated_at": ts,
                    "input": {},
                    "output": {},
                }
                steps_by_id[step_id] = step
            step["attempt"] = max(int(step.get("attempt") or 0), attempt)
            step["updated_at"] = ts
            if payload.get("job_id"):
                step["job_id"] = str(payload.get("job_id"))
            if payload.get("lease_id"):
                step["lease_id"] = str(payload.get("lease_id"))
            if payload.get("lease_expires_at") is not None:
                try:
                    step["lease_expires_at"] = float(payload.get("lease_expires_at"))
                except Exception:
                    pass
            if payload.get("evidence_path"):
                step["evidence_path"] = str(payload.get("evidence_path"))
            if ev_type in {"step.dispatched"}:
                step["status"] = "LEASED"
                replay_status = "DISPATCHING"
            elif ev_type in {"step.started"}:
                step["status"] = "EXECUTING"
                replay_status = "RUNNING"
            elif ev_type == "step.heartbeat":
                step["status"] = "EXECUTING"
            elif ev_type == "step.succeeded":
                step["status"] = "SUCCEEDED"
            elif ev_type == "step.failed":
                step["status"] = "FAILED"
            elif ev_type == "step.compensated":
                step["status"] = "COMPENSATED"

        if ev_type == "run.created":
            replay_status = "NEW"
        elif ev_type == "run.planned":
            replay_status = "PLAN_COMPILED"
        elif ev_type == "gate.passed":
            replay_status = "WAITING_GATES"
        elif ev_type == "gate.failed":
            replay_status = "WAITING_GATES"
        elif ev_type == "run.degraded":
            replay_status = "DEGRADED"
            replay_degraded = True
            replay_error_type = str(payload.get("reason_type") or payload.get("error_type") or replay_error_type or "")
            replay_error = str(payload.get("reason") or payload.get("error") or replay_error or "")
        elif ev_type == "run.taken_over":
            replay_status = "MANUAL_TAKEOVER"
            replay_degraded = True
        elif ev_type == "run.completed":
            replay_status = "COMPLETED"
            replay_ended_at = ts
            if payload.get("child_job_id"):
                replay_final_job_id = str(payload.get("child_job_id"))
        elif ev_type == "run.failed":
            replay_status = "FAILED"
            replay_ended_at = ts
        elif ev_type == "run.cancelled":
            replay_status = "CANCELLED"
            replay_ended_at = ts

        if payload.get("job_id") and ev_type in {"step.started", "step.succeeded"}:
            replay_final_job_id = str(payload.get("job_id"))

    replay_steps = [steps_by_id[k] for k in sorted(steps_by_id.keys())]
    snapshot: dict[str, Any] = {
        "run_id": str(run_id),
        "status": _normalize_run_status(replay_status),
        "degraded": bool(replay_degraded),
        "final_job_id": replay_final_job_id,
        "error_type": (replay_error_type if replay_error_type else None),
        "error": (replay_error if replay_error else None),
        "ended_at": replay_ended_at,
        "events_count": len(events),
        "last_event_id": (int(events[-1]["id"]) if events else 0),
        "steps": replay_steps,
    }

    if persist_snapshot:
        update_run(
            conn,
            run_id=run_id,
            status=snapshot["status"],
            final_job_id=snapshot.get("final_job_id"),
            degraded=bool(snapshot.get("degraded")),
            error_type=snapshot.get("error_type"),
            error=snapshot.get("error"),
            ended_at=(float(snapshot["ended_at"]) if snapshot.get("ended_at") is not None else None),
        )
        for step in replay_steps:
            upsert_step(
                conn,
                run_id=run_id,
                step_id=str(step["step_id"]),
                step_type=str(step.get("step_type") or "task"),
                status=str(step.get("status") or "PENDING"),
                attempt=max(0, int(step.get("attempt") or 0)),
                job_id=(str(step.get("job_id")) if step.get("job_id") else None),
                lease_id=(str(step.get("lease_id")) if step.get("lease_id") else None),
                lease_expires_at=(
                    float(step.get("lease_expires_at")) if step.get("lease_expires_at") is not None else None
                ),
                input_obj=dict(step.get("input") or {}),
                output_obj=dict(step.get("output") or {}),
                evidence_path=(str(step.get("evidence_path")) if step.get("evidence_path") else None),
            )
    return snapshot


def run_dir(artifacts_dir: Path, run_id: str) -> Path:
    return artifacts_dir / "advisor_runs" / str(run_id)


def write_snapshot_json(
    artifacts_dir: Path,
    *,
    run_id: str,
    run: dict[str, Any],
    steps: list[dict[str, Any]],
    replay_snapshot: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "run_id": str(run_id),
        "snapshot_at": float(_now()),
        "run": dict(run or {}),
        "steps": list(steps or []),
    }
    if replay_snapshot is not None:
        payload["replay"] = dict(replay_snapshot)
    return write_run_json(artifacts_dir, run_id=run_id, name="snapshot.json", payload=payload)


def write_run_json(artifacts_dir: Path, *, run_id: str, name: str, payload: dict[str, Any]) -> str:
    d = run_dir(artifacts_dir, run_id)
    d.mkdir(parents=True, exist_ok=True)
    out = d / str(name)
    tmp = out.with_suffix(out.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out)
    return out.relative_to(artifacts_dir).as_posix()


def list_run_artifacts(artifacts_dir: Path, *, run_id: str) -> list[dict[str, Any]]:
    d = run_dir(artifacts_dir, run_id)
    if not d.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(d.rglob("*")):
        if not p.is_file():
            continue
        try:
            st = p.stat()
            out.append(
                {
                    "path": p.relative_to(artifacts_dir).as_posix(),
                    "size": int(st.st_size),
                    "mtime": float(st.st_mtime),
                }
            )
        except Exception:
            continue
    return out
