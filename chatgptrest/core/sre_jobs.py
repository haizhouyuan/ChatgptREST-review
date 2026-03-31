from __future__ import annotations

import os
import socket
import time
from pathlib import Path
from typing import Any

from chatgptrest.core import job_store


def requested_by_transport(transport: str) -> dict[str, Any]:
    return {
        "transport": str(transport),
        "received_at": time.time(),
        "server": {"hostname": socket.gethostname(), "pid": os.getpid()},
    }


def build_sre_fix_request_input(
    *,
    issue_id: str | None = None,
    incident_id: str | None = None,
    job_id: str | None = None,
    symptom: str | None = None,
    instructions: str | None = None,
    lane_id: str | None = None,
    context: Any | None = None,
    context_pack: Any | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if issue_id and str(issue_id).strip():
        payload["issue_id"] = str(issue_id).strip()
    if incident_id and str(incident_id).strip():
        payload["incident_id"] = str(incident_id).strip()
    if job_id and str(job_id).strip():
        payload["job_id"] = str(job_id).strip()
    if symptom and str(symptom).strip():
        payload["symptom"] = str(symptom).strip()
    if instructions and str(instructions).strip():
        payload["instructions"] = str(instructions).strip()
    if lane_id and str(lane_id).strip():
        payload["lane_id"] = str(lane_id).strip()
    if context is not None:
        if isinstance(context, (dict, list, str, int, float, bool)) or context is None:
            payload["context"] = context
        else:
            payload["context"] = str(context)
    if context_pack is not None:
        if isinstance(context_pack, (dict, list, str, int, float, bool)) or context_pack is None:
            payload["context_pack"] = context_pack
        else:
            payload["context_pack"] = str(context_pack)
    return payload


def build_sre_fix_request_params(
    *,
    timeout_seconds: int = 600,
    model: str | None = None,
    resume_lane: bool = True,
    route_mode: str = "auto_best_effort",
    runtime_apply_actions: bool = True,
    runtime_max_risk: str = "low",
    runtime_allow_actions: str | list[str] | None = None,
    open_pr_mode: str = "p0",
    open_pr_run_tests: bool | None = None,
    gitnexus_limit: int = 5,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "timeout_seconds": int(timeout_seconds),
        "resume_lane": bool(resume_lane),
        "route_mode": str(route_mode or "").strip() or "auto_best_effort",
        "runtime_apply_actions": bool(runtime_apply_actions),
        "runtime_max_risk": str(runtime_max_risk or "").strip() or "low",
        "open_pr_mode": str(open_pr_mode or "").strip() or "p0",
        "gitnexus_limit": max(1, int(gitnexus_limit)),
    }
    if model and str(model).strip():
        params["model"] = str(model).strip()
    if runtime_allow_actions is not None:
        params["runtime_allow_actions"] = runtime_allow_actions
    if open_pr_run_tests is not None:
        params["open_pr_run_tests"] = bool(open_pr_run_tests)
    return params


def create_sre_fix_request_job(
    *,
    conn: Any,
    artifacts_dir: Path,
    idempotency_key: str,
    client_name: str,
    requested_by: dict[str, Any] | None = None,
    max_attempts: int = 1,
    issue_id: str | None = None,
    incident_id: str | None = None,
    job_id: str | None = None,
    symptom: str | None = None,
    instructions: str | None = None,
    lane_id: str | None = None,
    context: Any | None = None,
    context_pack: Any | None = None,
    timeout_seconds: int = 600,
    model: str | None = None,
    resume_lane: bool = True,
    route_mode: str = "auto_best_effort",
    runtime_apply_actions: bool = True,
    runtime_max_risk: str = "low",
    runtime_allow_actions: str | list[str] | None = None,
    open_pr_mode: str = "p0",
    open_pr_run_tests: bool | None = None,
    gitnexus_limit: int = 5,
) -> Any:
    return job_store.create_job(
        conn,
        artifacts_dir=artifacts_dir,
        idempotency_key=idempotency_key,
        kind="sre.fix_request",
        input=build_sre_fix_request_input(
            issue_id=issue_id,
            incident_id=incident_id,
            job_id=job_id,
            symptom=symptom,
            instructions=instructions,
            lane_id=lane_id,
            context=context,
            context_pack=context_pack,
        ),
        params=build_sre_fix_request_params(
            timeout_seconds=timeout_seconds,
            model=model,
            resume_lane=resume_lane,
            route_mode=route_mode,
            runtime_apply_actions=runtime_apply_actions,
            runtime_max_risk=runtime_max_risk,
            runtime_allow_actions=runtime_allow_actions,
            open_pr_mode=open_pr_mode,
            open_pr_run_tests=open_pr_run_tests,
            gitnexus_limit=gitnexus_limit,
        ),
        max_attempts=max_attempts,
        client={"name": str(client_name)},
        requested_by=requested_by,
        enforce_conversation_single_flight=False,
    )
