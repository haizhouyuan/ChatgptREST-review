from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any

from chatgptrest.core import job_store
from chatgptrest.core.prompt_policy import looks_like_synthetic_or_trivial_agent_prompt


_DEFAULT_REPAIR_AUTOFIX_MODEL = "gpt-5.3-codex-spark"


def requested_by_transport(transport: str) -> dict[str, Any]:
    return {
        "transport": str(transport),
        "received_at": time.time(),
        "server": {"hostname": socket.gethostname(), "pid": os.getpid()},
    }


def default_repair_autofix_model() -> str:
    raw = str(os.environ.get("CHATGPTREST_CODEX_AUTOFIX_MODEL_DEFAULT") or "").strip()
    return raw or _DEFAULT_REPAIR_AUTOFIX_MODEL


def build_repair_input(
    *,
    job_id: str | None = None,
    symptom: str | None = None,
    conversation_url: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if job_id and str(job_id).strip():
        payload["job_id"] = str(job_id).strip()
    if symptom and str(symptom).strip():
        payload["symptom"] = str(symptom).strip()
    if conversation_url and str(conversation_url).strip():
        payload["conversation_url"] = str(conversation_url).strip()
    return payload


def build_repair_check_params(
    *,
    mode: str = "quick",
    timeout_seconds: int = 60,
    probe_driver: bool = True,
    capture_ui: bool = False,
    recent_failures: int = 5,
) -> dict[str, Any]:
    return {
        "mode": str(mode),
        "timeout_seconds": int(timeout_seconds),
        "probe_driver": bool(probe_driver),
        "capture_ui": bool(capture_ui),
        "recent_failures": int(recent_failures),
    }


def build_repair_autofix_params(
    *,
    timeout_seconds: int = 600,
    model: str | None = None,
    max_risk: str = "low",
    allow_actions: str | list[str] | None = None,
    apply_actions: bool = True,
) -> dict[str, Any]:
    resolved_model = str(model or "").strip() or default_repair_autofix_model()
    params: dict[str, Any] = {
        "timeout_seconds": int(timeout_seconds),
        "max_risk": str(max_risk or "").strip() or "medium",
        "apply_actions": bool(apply_actions),
        "model": resolved_model,
    }
    if allow_actions is not None:
        params["allow_actions"] = allow_actions
    return params


def source_job_uses_synthetic_or_trivial_prompt(conn: Any, source_job_id: str | None) -> bool:
    source_id = str(source_job_id or "").strip()
    if not source_id:
        return False
    row = conn.execute(
        "SELECT input_json FROM jobs WHERE job_id = ? LIMIT 1",
        (source_id,),
    ).fetchone()
    if row is None:
        return False
    raw_input = row["input_json"] if hasattr(row, "__getitem__") else row[0]
    try:
        input_obj = json.loads(str(raw_input or "{}"))
    except Exception:
        return False
    question = str((input_obj or {}).get("question") or "")
    return looks_like_synthetic_or_trivial_agent_prompt(question)


def create_repair_check_job(
    *,
    conn: Any,
    artifacts_dir: Path,
    idempotency_key: str,
    client_name: str,
    requested_by: dict[str, Any] | None = None,
    max_attempts: int = 1,
    enforce_conversation_single_flight: bool = False,
    job_id: str | None = None,
    symptom: str | None = None,
    conversation_url: str | None = None,
    mode: str = "quick",
    timeout_seconds: int = 60,
    probe_driver: bool = True,
    capture_ui: bool = False,
    recent_failures: int = 5,
) -> Any:
    return job_store.create_job(
        conn,
        artifacts_dir=artifacts_dir,
        idempotency_key=idempotency_key,
        kind="repair.check",
        input=build_repair_input(job_id=job_id, symptom=symptom, conversation_url=conversation_url),
        params=build_repair_check_params(
            mode=mode,
            timeout_seconds=timeout_seconds,
            probe_driver=probe_driver,
            capture_ui=capture_ui,
            recent_failures=recent_failures,
        ),
        max_attempts=max_attempts,
        client={"name": str(client_name)},
        requested_by=requested_by,
        enforce_conversation_single_flight=enforce_conversation_single_flight,
    )


def create_repair_autofix_job(
    *,
    conn: Any,
    artifacts_dir: Path,
    idempotency_key: str,
    client_name: str,
    requested_by: dict[str, Any] | None = None,
    max_attempts: int = 1,
    enforce_conversation_single_flight: bool = False,
    job_id: str,
    symptom: str | None = None,
    conversation_url: str | None = None,
    timeout_seconds: int = 600,
    model: str | None = None,
    max_risk: str = "low",
    allow_actions: str | list[str] | None = None,
    apply_actions: bool = True,
) -> Any:
    return job_store.create_job(
        conn,
        artifacts_dir=artifacts_dir,
        idempotency_key=idempotency_key,
        kind="repair.autofix",
        input=build_repair_input(job_id=job_id, symptom=symptom, conversation_url=conversation_url),
        params=build_repair_autofix_params(
            timeout_seconds=timeout_seconds,
            model=model,
            max_risk=max_risk,
            allow_actions=allow_actions,
            apply_actions=apply_actions,
        ),
        max_attempts=max_attempts,
        client={"name": str(client_name)},
        requested_by=requested_by,
        enforce_conversation_single_flight=enforce_conversation_single_flight,
    )
