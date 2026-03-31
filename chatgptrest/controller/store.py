from __future__ import annotations

import json
import time
from typing import Any


_CONTROLLER_RUN_STATUSES: frozenset[str] = frozenset(
    {
        "NEW",
        "UNDERSTOOD",
        "PLANNED",
        "RUNNING",
        "WAITING_EXTERNAL",
        "WAITING_HUMAN",
        "SYNTHESIZING",
        "DELIVERED",
        "FAILED",
        "CANCELLED",
    }
)

_WORK_ITEM_STATUSES: frozenset[str] = frozenset(
    {
        "PENDING",
        "RUNNING",
        "QUEUED",
        "WAITING_EXTERNAL",
        "WAITING_HUMAN",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    }
)

_CHECKPOINT_STATUSES: frozenset[str] = frozenset({"PENDING", "NEEDS_HUMAN", "RESOLVED", "SKIPPED"})


def _now() -> float:
    return time.time()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_loads(raw: Any, *, default: Any) -> Any:
    if raw is None:
        return default
    text = str(raw).strip()
    if not text:
        return default
    try:
        value = json.loads(text)
    except Exception:
        return default
    return value


_UNSET = object()


def _normalize_run_status(status: str | None) -> str:
    normalized = str(status or "").strip().upper()
    return normalized if normalized in _CONTROLLER_RUN_STATUSES else "NEW"


def _normalize_work_item_status(status: str | None) -> str:
    normalized = str(status or "").strip().upper()
    return normalized if normalized in _WORK_ITEM_STATUSES else "PENDING"


def _normalize_checkpoint_status(status: str | None) -> str:
    normalized = str(status or "").strip().upper()
    return normalized if normalized in _CHECKPOINT_STATUSES else "PENDING"


def _row_to_run(row: Any) -> dict[str, Any]:
    return {
        "run_id": str(row["run_id"]),
        "trace_id": (str(row["trace_id"]) if row["trace_id"] is not None else None),
        "request_id": (str(row["request_id"]) if row["request_id"] is not None else None),
        "execution_mode": str(row["execution_mode"] or "sync"),
        "controller_status": _normalize_run_status(row["controller_status"]),
        "objective_text": (str(row["objective_text"]) if row["objective_text"] is not None else None),
        "objective_kind": (str(row["objective_kind"]) if row["objective_kind"] is not None else None),
        "success_criteria": _json_loads(row["success_criteria_json"], default=[]),
        "constraints": _json_loads(row["constraints_json"], default=[]),
        "delivery_target": _json_loads(row["delivery_target_json"], default={}),
        "current_work_id": (str(row["current_work_id"]) if row["current_work_id"] is not None else None),
        "blocked_reason": (str(row["blocked_reason"]) if row["blocked_reason"] is not None else None),
        "wake_after": (float(row["wake_after"]) if row["wake_after"] is not None else None),
        "plan_version": int(row["plan_version"] or 1),
        "route": (str(row["route"]) if row["route"] is not None else None),
        "provider": (str(row["provider"]) if row["provider"] is not None else None),
        "preset": (str(row["preset"]) if row["preset"] is not None else None),
        "session_id": (str(row["session_id"]) if row["session_id"] is not None else None),
        "account_id": (str(row["account_id"]) if row["account_id"] is not None else None),
        "thread_id": (str(row["thread_id"]) if row["thread_id"] is not None else None),
        "agent_id": (str(row["agent_id"]) if row["agent_id"] is not None else None),
        "role_id": (str(row["role_id"]) if row["role_id"] is not None else None),
        "user_id": (str(row["user_id"]) if row["user_id"] is not None else None),
        "intent_hint": (str(row["intent_hint"]) if row["intent_hint"] is not None else None),
        "question": (str(row["question"]) if row["question"] is not None else None),
        "normalized_question": (str(row["normalized_question"]) if row["normalized_question"] is not None else None),
        "request": _json_loads(row["request_json"], default={}),
        "plan": _json_loads(row["plan_json"], default={}),
        "delivery": _json_loads(row["delivery_json"], default={}),
        "next_action": _json_loads(row["next_action_json"], default={}),
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
        "ended_at": (float(row["ended_at"]) if row["ended_at"] is not None else None),
    }


def _row_to_work_item(row: Any) -> dict[str, Any]:
    return {
        "run_id": str(row["run_id"]),
        "work_id": str(row["work_id"]),
        "title": str(row["title"] or ""),
        "kind": str(row["kind"] or "task"),
        "status": _normalize_work_item_status(row["status"]),
        "owner": (str(row["owner"]) if row["owner"] is not None else None),
        "lane": (str(row["lane"]) if row["lane"] is not None else None),
        "priority": (str(row["priority"]) if row["priority"] is not None else None),
        "job_id": (str(row["job_id"]) if row["job_id"] is not None else None),
        "depends_on": _json_loads(row["depends_on_json"], default=[]),
        "input": _json_loads(row["input_json"], default={}),
        "output": _json_loads(row["output_json"], default={}),
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
    }


def _row_to_checkpoint(row: Any) -> dict[str, Any]:
    return {
        "run_id": str(row["run_id"]),
        "checkpoint_id": str(row["checkpoint_id"]),
        "title": str(row["title"] or ""),
        "status": _normalize_checkpoint_status(row["status"]),
        "blocking": bool(int(row["blocking"] or 0)),
        "details": _json_loads(row["details_json"], default={}),
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
    }


def _row_to_artifact(row: Any) -> dict[str, Any]:
    return {
        "run_id": str(row["run_id"]),
        "artifact_id": str(row["artifact_id"]),
        "work_id": (str(row["work_id"]) if row["work_id"] is not None else None),
        "kind": str(row["kind"] or "artifact"),
        "title": str(row["title"] or ""),
        "path": (str(row["path"]) if row["path"] is not None else None),
        "uri": (str(row["uri"]) if row["uri"] is not None else None),
        "metadata": _json_loads(row["metadata_json"], default={}),
        "created_at": float(row["created_at"]),
    }


def get_run(conn: Any, *, run_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM controller_runs WHERE run_id = ?", (str(run_id),)).fetchone()
    return _row_to_run(row) if row is not None else None


def get_run_by_trace_id(conn: Any, *, trace_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM controller_runs
        WHERE trace_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (str(trace_id),),
    ).fetchone()
    return _row_to_run(row) if row is not None else None


def get_run_by_request_id(conn: Any, *, request_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM controller_runs
        WHERE request_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (str(request_id),),
    ).fetchone()
    return _row_to_run(row) if row is not None else None


def upsert_run(
    conn: Any,
    *,
    run_id: str,
    trace_id: str | None,
    request_id: str | None,
    execution_mode: str,
    controller_status: str,
    objective_text: str | None = None,
    objective_kind: str | None = None,
    success_criteria: list[Any] | None = None,
    constraints: list[Any] | None = None,
    delivery_target: dict[str, Any] | None = None,
    current_work_id: str | None | object = _UNSET,
    blocked_reason: str | None | object = _UNSET,
    wake_after: float | None | object = _UNSET,
    plan_version: int | None = None,
    route: str | None = None,
    provider: str | None = None,
    preset: str | None = None,
    session_id: str | None = None,
    account_id: str | None = None,
    thread_id: str | None = None,
    agent_id: str | None = None,
    role_id: str | None = None,
    user_id: str | None = None,
    intent_hint: str | None = None,
    question: str | None = None,
    normalized_question: str | None = None,
    request_obj: dict[str, Any] | None = None,
    plan_obj: dict[str, Any] | None = None,
    delivery_obj: dict[str, Any] | None = None,
    next_action_obj: dict[str, Any] | None = None,
    ended_at: float | None = None,
) -> dict[str, Any]:
    now = _now()
    existing = get_run(conn, run_id=run_id)
    normalized_controller_status = _normalize_run_status(controller_status)
    current_work_id_value = None
    if current_work_id is not _UNSET:
        current_work_id_value = (str(current_work_id).strip() or None) if current_work_id is not None else None
    blocked_reason_value = None
    if blocked_reason is not _UNSET:
        blocked_reason_value = (str(blocked_reason).strip() or None) if blocked_reason is not None else None
    wake_after_value = None
    if wake_after is not _UNSET and wake_after is not None:
        wake_after_value = float(wake_after)
    if existing is None:
        conn.execute(
            """
            INSERT INTO controller_runs(
              run_id, trace_id, request_id, execution_mode, controller_status,
              objective_text, objective_kind, success_criteria_json, constraints_json,
              delivery_target_json, current_work_id, blocked_reason, wake_after, plan_version,
              route, provider, preset, session_id, account_id, thread_id, agent_id,
              role_id, user_id, intent_hint, question, normalized_question,
              request_json, plan_json, delivery_json, next_action_json,
              created_at, updated_at, ended_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(run_id),
                (str(trace_id).strip() if trace_id else None),
                (str(request_id).strip() if request_id else None),
                str(execution_mode or "sync"),
                normalized_controller_status,
                (str(objective_text).strip() if objective_text else None),
                (str(objective_kind).strip() if objective_kind else None),
                _json_dumps(list(success_criteria or [])),
                _json_dumps(list(constraints or [])),
                _json_dumps(dict(delivery_target or {})),
                current_work_id_value,
                blocked_reason_value,
                wake_after_value,
                int(plan_version or 1),
                (str(route).strip() if route else None),
                (str(provider).strip() if provider else None),
                (str(preset).strip() if preset else None),
                (str(session_id).strip() if session_id else None),
                (str(account_id).strip() if account_id else None),
                (str(thread_id).strip() if thread_id else None),
                (str(agent_id).strip() if agent_id else None),
                (str(role_id).strip() if role_id else None),
                (str(user_id).strip() if user_id else None),
                (str(intent_hint).strip() if intent_hint else None),
                (str(question or "") if question is not None else None),
                (str(normalized_question or "") if normalized_question is not None else None),
                _json_dumps(dict(request_obj or {})),
                _json_dumps(dict(plan_obj or {})),
                _json_dumps(dict(delivery_obj or {})),
                _json_dumps(dict(next_action_obj or {})),
                float(now),
                float(now),
                (float(ended_at) if ended_at is not None else None),
            ),
        )
        created = get_run(conn, run_id=run_id)
        if created is None:
            raise RuntimeError("failed to create controller run")
        return created

    updates: dict[str, Any] = {
        "updated_at": float(now),
    }
    if trace_id is not None:
        updates["trace_id"] = (str(trace_id).strip() or None)
    if request_id is not None:
        updates["request_id"] = (str(request_id).strip() or None)
    if execution_mode is not None:
        updates["execution_mode"] = str(execution_mode or "sync")
    if controller_status is not None:
        updates["controller_status"] = normalized_controller_status
    if objective_text is not None:
        updates["objective_text"] = (str(objective_text).strip() or None)
    if objective_kind is not None:
        updates["objective_kind"] = (str(objective_kind).strip() or None)
    if success_criteria is not None:
        updates["success_criteria_json"] = _json_dumps(list(success_criteria or []))
    if constraints is not None:
        updates["constraints_json"] = _json_dumps(list(constraints or []))
    if delivery_target is not None:
        updates["delivery_target_json"] = _json_dumps(dict(delivery_target or {}))
    if current_work_id is not _UNSET:
        updates["current_work_id"] = (str(current_work_id).strip() or None) if current_work_id is not None else None
    elif normalized_controller_status in {"DELIVERED", "FAILED", "CANCELLED"}:
        updates["current_work_id"] = None
    if blocked_reason is not _UNSET:
        updates["blocked_reason"] = (str(blocked_reason).strip() or None) if blocked_reason is not None else None
    elif normalized_controller_status != "WAITING_HUMAN":
        updates["blocked_reason"] = None
    if wake_after is not _UNSET:
        updates["wake_after"] = (float(wake_after) if wake_after is not None else None)
    if plan_version is not None:
        updates["plan_version"] = max(1, int(plan_version))
    if route is not None:
        updates["route"] = (str(route).strip() or None)
    if provider is not None:
        updates["provider"] = (str(provider).strip() or None)
    if preset is not None:
        updates["preset"] = (str(preset).strip() or None)
    if session_id is not None:
        updates["session_id"] = (str(session_id).strip() or None)
    if account_id is not None:
        updates["account_id"] = (str(account_id).strip() or None)
    if thread_id is not None:
        updates["thread_id"] = (str(thread_id).strip() or None)
    if agent_id is not None:
        updates["agent_id"] = (str(agent_id).strip() or None)
    if role_id is not None:
        updates["role_id"] = (str(role_id).strip() or None)
    if user_id is not None:
        updates["user_id"] = (str(user_id).strip() or None)
    if intent_hint is not None:
        updates["intent_hint"] = (str(intent_hint).strip() or None)
    if question is not None:
        updates["question"] = str(question or "")
    if normalized_question is not None:
        updates["normalized_question"] = str(normalized_question or "")
    if request_obj is not None:
        updates["request_json"] = _json_dumps(dict(request_obj or {}))
    if plan_obj is not None:
        updates["plan_json"] = _json_dumps(dict(plan_obj or {}))
    if delivery_obj is not None:
        updates["delivery_json"] = _json_dumps(dict(delivery_obj or {}))
    if next_action_obj is not None:
        updates["next_action_json"] = _json_dumps(dict(next_action_obj or {}))
    if ended_at is not None:
        updates["ended_at"] = float(ended_at)
    elif normalized_controller_status in {"DELIVERED", "FAILED", "CANCELLED"}:
        updates["ended_at"] = float(now)

    columns = sorted(updates.keys())
    assignments = ", ".join(f"{column} = ?" for column in columns)
    values = [updates[column] for column in columns]
    values.append(str(run_id))
    conn.execute(f"UPDATE controller_runs SET {assignments} WHERE run_id = ?", values)
    return get_run(conn, run_id=run_id) or existing


def upsert_work_item(
    conn: Any,
    *,
    run_id: str,
    work_id: str,
    title: str,
    kind: str,
    status: str,
    owner: str | None = None,
    lane: str | None = None,
    priority: str | None = None,
    job_id: str | None = None,
    depends_on: list[str] | None = None,
    input_obj: dict[str, Any] | None = None,
    output_obj: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now()
    row = conn.execute(
        "SELECT * FROM controller_work_items WHERE run_id = ? AND work_id = ?",
        (str(run_id), str(work_id)),
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO controller_work_items(
              run_id, work_id, title, kind, status, owner, lane, priority, job_id,
              depends_on_json, input_json, output_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(run_id),
                str(work_id),
                str(title or ""),
                str(kind or "task"),
                _normalize_work_item_status(status),
                (str(owner).strip() if owner else None),
                (str(lane).strip() if lane else None),
                (str(priority).strip() if priority else None),
                (str(job_id).strip() if job_id else None),
                _json_dumps(list(depends_on or [])),
                _json_dumps(dict(input_obj or {})),
                _json_dumps(dict(output_obj or {})),
                float(now),
                float(now),
            ),
        )
    else:
        conn.execute(
            """
            UPDATE controller_work_items
            SET title = ?, kind = ?, status = ?, owner = ?, lane = ?, priority = ?, job_id = ?,
                depends_on_json = ?, input_json = ?, output_json = ?, updated_at = ?
            WHERE run_id = ? AND work_id = ?
            """,
            (
                str(title or ""),
                str(kind or "task"),
                _normalize_work_item_status(status),
                (str(owner).strip() if owner else None),
                (str(lane).strip() if lane else None),
                (str(priority).strip() if priority else None),
                (str(job_id).strip() if job_id else None),
                _json_dumps(list(depends_on or [])),
                _json_dumps(dict(input_obj or {})),
                _json_dumps(dict(output_obj or {})),
                float(now),
                str(run_id),
                str(work_id),
            ),
        )
    out = conn.execute(
        "SELECT * FROM controller_work_items WHERE run_id = ? AND work_id = ?",
        (str(run_id), str(work_id)),
    ).fetchone()
    if out is None:
        raise RuntimeError("failed to upsert controller work item")
    return _row_to_work_item(out)


def list_work_items(conn: Any, *, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM controller_work_items
        WHERE run_id = ?
        ORDER BY created_at ASC, work_id ASC
        """,
        (str(run_id),),
    ).fetchall()
    return [_row_to_work_item(row) for row in rows]


def upsert_checkpoint(
    conn: Any,
    *,
    run_id: str,
    checkpoint_id: str,
    title: str,
    status: str,
    blocking: bool,
    details_obj: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now()
    row = conn.execute(
        "SELECT * FROM controller_checkpoints WHERE run_id = ? AND checkpoint_id = ?",
        (str(run_id), str(checkpoint_id)),
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO controller_checkpoints(
              run_id, checkpoint_id, title, status, blocking, details_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(run_id),
                str(checkpoint_id),
                str(title or ""),
                _normalize_checkpoint_status(status),
                (1 if blocking else 0),
                _json_dumps(dict(details_obj or {})),
                float(now),
                float(now),
            ),
        )
    else:
        conn.execute(
            """
            UPDATE controller_checkpoints
            SET title = ?, status = ?, blocking = ?, details_json = ?, updated_at = ?
            WHERE run_id = ? AND checkpoint_id = ?
            """,
            (
                str(title or ""),
                _normalize_checkpoint_status(status),
                (1 if blocking else 0),
                _json_dumps(dict(details_obj or {})),
                float(now),
                str(run_id),
                str(checkpoint_id),
            ),
        )
    out = conn.execute(
        "SELECT * FROM controller_checkpoints WHERE run_id = ? AND checkpoint_id = ?",
        (str(run_id), str(checkpoint_id)),
    ).fetchone()
    if out is None:
        raise RuntimeError("failed to upsert controller checkpoint")
    return _row_to_checkpoint(out)


def list_checkpoints(conn: Any, *, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM controller_checkpoints
        WHERE run_id = ?
        ORDER BY created_at ASC, checkpoint_id ASC
        """,
        (str(run_id),),
    ).fetchall()
    return [_row_to_checkpoint(row) for row in rows]


def upsert_artifact(
    conn: Any,
    *,
    run_id: str,
    artifact_id: str,
    kind: str,
    title: str,
    work_id: str | None = None,
    path: str | None = None,
    uri: str | None = None,
    metadata_obj: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM controller_artifacts WHERE run_id = ? AND artifact_id = ?",
        (str(run_id), str(artifact_id)),
    ).fetchone()
    created_at = _now()
    if row is None:
        conn.execute(
            """
            INSERT INTO controller_artifacts(
              run_id, artifact_id, work_id, kind, title, path, uri, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(run_id),
                str(artifact_id),
                (str(work_id).strip() if work_id else None),
                str(kind or "artifact"),
                str(title or ""),
                (str(path).strip() if path else None),
                (str(uri).strip() if uri else None),
                _json_dumps(dict(metadata_obj or {})),
                float(created_at),
            ),
        )
    else:
        conn.execute(
            """
            UPDATE controller_artifacts
            SET work_id = ?, kind = ?, title = ?, path = ?, uri = ?, metadata_json = ?
            WHERE run_id = ? AND artifact_id = ?
            """,
            (
                (str(work_id).strip() if work_id else None),
                str(kind or "artifact"),
                str(title or ""),
                (str(path).strip() if path else None),
                (str(uri).strip() if uri else None),
                _json_dumps(dict(metadata_obj or {})),
                str(run_id),
                str(artifact_id),
            ),
        )
    out = conn.execute(
        "SELECT * FROM controller_artifacts WHERE run_id = ? AND artifact_id = ?",
        (str(run_id), str(artifact_id)),
    ).fetchone()
    if out is None:
        raise RuntimeError("failed to upsert controller artifact")
    return _row_to_artifact(out)


def list_artifacts(conn: Any, *, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM controller_artifacts
        WHERE run_id = ?
        ORDER BY created_at ASC, artifact_id ASC
        """,
        (str(run_id),),
    ).fetchall()
    return [_row_to_artifact(row) for row in rows]


def snapshot_run(conn: Any, *, run_id: str) -> dict[str, Any] | None:
    run = get_run(conn, run_id=run_id)
    if run is None:
        return None
    return {
        "run": run,
        "work_items": list_work_items(conn, run_id=run_id),
        "checkpoints": list_checkpoints(conn, run_id=run_id),
        "artifacts": list_artifacts(conn, run_id=run_id),
    }
