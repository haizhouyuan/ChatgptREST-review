from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from chatgptrest.core import advisor_runs


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_loads_list(raw: Any) -> list[Any]:
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        value = json.loads(text)
    except Exception:
        return []
    return list(value) if isinstance(value, list) else []


def _json_loads_dict(raw: Any) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
    except Exception:
        return {}
    return dict(value) if isinstance(value, dict) else {}


def _now() -> float:
    return time.time()


def _artifact_refs(artifacts_dir: Path | None, run_id: str) -> list[dict[str, Any]]:
    if artifacts_dir is None:
        return []
    try:
        return advisor_runs.list_run_artifacts(artifacts_dir, run_id=run_id)
    except Exception:
        return []


def _retrieval_refs(context: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if not isinstance(context, dict):
        return refs

    query_id = str(context.get("query_id") or "").strip()
    if query_id:
        refs.append({"kind": "query_id", "value": query_id})

    query_identity = context.get("query_identity")
    if isinstance(query_identity, dict):
        compact = {
            key: value
            for key, value in query_identity.items()
            if value not in ("", None, [], {}, ())
        }
        if compact:
            refs.append({"kind": "query_identity", "value": compact})

    retrieval_refs = context.get("retrieval_refs")
    if isinstance(retrieval_refs, list):
        refs.extend(item for item in retrieval_refs if isinstance(item, dict))
    return refs


def _row_to_outcome(row: Any) -> dict[str, Any]:
    return {
        "outcome_id": str(row["outcome_id"]),
        "run_id": str(row["run_id"]),
        "trace_id": str(row["trace_id"] or ""),
        "job_id": str(row["job_id"] or ""),
        "task_ref": str(row["task_ref"] or ""),
        "logical_task_id": str(row["logical_task_id"] or ""),
        "identity_confidence": str(row["identity_confidence"] or ""),
        "route": str(row["route"] or ""),
        "provider": str(row["provider"] or ""),
        "channel": str(row["channel"] or ""),
        "session_id": str(row["session_id"] or ""),
        "status": str(row["status"] or ""),
        "degraded": bool(int(row["degraded"] or 0)),
        "fallback_chain": _json_loads_list(row["fallback_chain_json"]),
        "retrieval_refs": _json_loads_list(row["retrieval_refs_json"]),
        "artifacts": _json_loads_list(row["artifacts_json"]),
        "metadata": _json_loads_dict(row["metadata_json"]),
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
    }


def get_execution_outcome(conn: Any, *, run_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM execution_outcomes WHERE run_id = ?",
        (str(run_id),),
    ).fetchone()
    if row is None:
        return None
    return _row_to_outcome(row)


def upsert_execution_outcome(
    conn: Any,
    *,
    run: dict[str, Any],
    artifacts_dir: Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_id = str(run.get("run_id") or "").strip()
    if not run_id:
        raise ValueError("run.run_id is required")

    existing = get_execution_outcome(conn, run_id=run_id)
    identity = advisor_runs.execution_identity_for_run(run)
    context = run.get("context") if isinstance(run.get("context"), dict) else {}
    outcome_id = str(existing.get("outcome_id") if existing else "") or uuid.uuid4().hex
    created_at = float(existing.get("created_at") if existing else _now())
    updated_at = _now()

    route = str(run.get("route") or "").strip()
    provider = str(context.get("provider") or "").strip()
    channel = str(context.get("channel") or context.get("source") or "").strip()
    session_id = str(
        context.get("session_id")
        or context.get("session_key")
        or identity.get("session_id")
        or ""
    ).strip()
    status = str(run.get("status") or "").strip()
    degraded = 1 if bool(run.get("degraded")) else 0
    fallback_chain = context.get("fallback_chain") if isinstance(context.get("fallback_chain"), list) else []
    retrieval_refs = _retrieval_refs(context)
    artifacts = _artifact_refs(artifacts_dir, run_id)
    merged_metadata = {
        "observer_only": True,
        "raw_status": status,
        "error_type": run.get("error_type"),
        "error": run.get("error"),
    }
    if isinstance(metadata, dict):
        merged_metadata.update(metadata)

    conn.execute(
        """
        INSERT INTO execution_outcomes(
          outcome_id, run_id, trace_id, job_id, task_ref, logical_task_id,
          identity_confidence, route, provider, channel, session_id, status,
          degraded, fallback_chain_json, retrieval_refs_json, artifacts_json,
          metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
          trace_id = excluded.trace_id,
          job_id = excluded.job_id,
          task_ref = excluded.task_ref,
          logical_task_id = excluded.logical_task_id,
          identity_confidence = excluded.identity_confidence,
          route = excluded.route,
          provider = excluded.provider,
          channel = excluded.channel,
          session_id = excluded.session_id,
          status = excluded.status,
          degraded = excluded.degraded,
          fallback_chain_json = excluded.fallback_chain_json,
          retrieval_refs_json = excluded.retrieval_refs_json,
          artifacts_json = excluded.artifacts_json,
          metadata_json = excluded.metadata_json,
          updated_at = excluded.updated_at
        """,
        (
            outcome_id,
            run_id,
            str(identity.get("trace_id") or ""),
            str(identity.get("job_id") or ""),
            str(identity.get("task_ref") or ""),
            str(identity.get("logical_task_id") or ""),
            str(identity.get("identity_confidence") or ""),
            route,
            provider,
            channel,
            session_id,
            status,
            degraded,
            _json_dumps(list(fallback_chain)),
            _json_dumps(retrieval_refs),
            _json_dumps(artifacts),
            _json_dumps(merged_metadata),
            created_at,
            updated_at,
        ),
    )
    return get_execution_outcome(conn, run_id=run_id) or {}
