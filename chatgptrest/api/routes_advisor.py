from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from chatgptrest.api.write_guards import (
    enforce_client_name_allowlist as _enforce_client_name_allowlist,
    enforce_write_trace_headers as _enforce_write_trace_headers,
    summarize_write_context as _summarize_write_context,
)
from chatgptrest.api.schemas import AdvisorAdviseRequest, AdvisorRunEventsView, AdvisorRunView
from chatgptrest.core.config import AppConfig
from chatgptrest.core.db import connect
from chatgptrest.core import advisor_gates, advisor_runs
from chatgptrest.core.idempotency import IdempotencyCollision
from chatgptrest.core.job_store import ConversationBusy, create_job, get_job
from chatgptrest.core.state_machine import JobStatus
from chatgptrest.providers.registry import PresetValidationError, validate_ask_preset


_REPO_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER_LOCK = threading.RLock()
_WRAPPER_MODULE_NAME = "chatgpt_wrapper_v1_runtime"
_LOG = logging.getLogger(__name__)

_BOOL_KEYS = {
    "agent_mode",
    "dry_run",
    "auto_rollback",
    "auto_client_name_repair",
    "persist_client_name_repair",
    "openclaw_required",
    "openclaw_cleanup",
    "openclaw_allow_a2a",
}
_INT_KEYS = {
    "max_turns",
    "max_retries",
    "retry_base_seconds",
    "retry_max_seconds",
    "timeout_seconds",
    "send_timeout_seconds",
    "wait_timeout_seconds",
    "max_wait_seconds",
    "min_chars",
    "openclaw_timeout_seconds",
    "openclaw_session_timeout_seconds",
}
_FLOAT_KEYS = {"poll_seconds"}
_STR_KEYS = {
    "session_id",
    "preset",
    "answer_format",
    "client_name",
    "client_instance",
    "request_id_prefix",
    "openclaw_mcp_url",
    "openclaw_agent_id",
    "openclaw_model",
    "openclaw_thinking",
    "openclaw_session_key",
}
_LIST_KEYS = {"client_name_repair_allowlist"}
_ALLOWED_AGENT_OPTION_KEYS = _BOOL_KEYS | _INT_KEYS | _FLOAT_KEYS | _STR_KEYS | _LIST_KEYS
_FORBIDDEN_AGENT_OPTION_KEYS = {"base_url", "api_token", "state_root"}


def _parse_bool(raw: Any, *, key: str) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return bool(raw)
    if isinstance(raw, str):
        v = raw.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    raise HTTPException(status_code=400, detail={"error": "invalid_option_type", "option": key, "expected": "bool"})


def _parse_int(raw: Any, *, key: str) -> int:
    try:
        return int(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_option_type", "option": key, "expected": "int"}) from exc


def _parse_float(raw: Any, *, key: str) -> float:
    try:
        return float(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_option_type", "option": key, "expected": "float"}) from exc


def _sanitize_token(raw: str, *, fallback: str) -> str:
    text = str(raw or "").strip() or str(fallback)
    text = re.sub(r"[^A-Za-z0-9._~-]+", "-", text)
    text = text.strip(".-_~")
    return text or fallback


def _load_wrapper_module() -> Any:
    path = _REPO_ROOT / "ops" / "chatgpt_wrapper_v1.py"
    if not path.exists():
        raise RuntimeError(f"advisor wrapper not found: {path}")
    spec = importlib.util.spec_from_file_location(_WRAPPER_MODULE_NAME, str(path))
    if not spec or not spec.loader:
        raise RuntimeError(f"failed to load advisor wrapper from {path}")
    with _WRAPPER_LOCK:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def _parse_list(raw: Any, *, key: str) -> list[str]:
    if isinstance(raw, list):
        out = [str(v).strip() for v in raw if str(v).strip()]
        return out
    if isinstance(raw, str):
        out = [p.strip() for p in re.split(r"[\s,;]+", raw) if p and p.strip()]
        return out
    raise HTTPException(status_code=400, detail={"error": "invalid_option_type", "option": key, "expected": "list|string"})


def _normalize_state_root(raw: Any) -> Path:
    if raw is None:
        p = _REPO_ROOT / "state" / "chatgpt_agent_shell_v0"
        return p.resolve(strict=False)
    p = Path(str(raw)).expanduser()
    if p.is_absolute():
        return p.resolve(strict=False)
    return (_REPO_ROOT / p).resolve(strict=False)


def _header(headers: dict[str, str], key: str) -> str:
    return str(headers.get(str(key).strip().lower()) or "").strip()


def _normalize_agent_options(*, agent_options: dict[str, Any], headers: dict[str, str], cfg: AppConfig) -> dict[str, Any]:
    forbidden = sorted(set(agent_options.keys()) & _FORBIDDEN_AGENT_OPTION_KEYS)
    if forbidden:
        raise HTTPException(
            status_code=400,
            detail={"error": "forbidden_agent_options", "forbidden_keys": forbidden},
        )
    extra = sorted(set(agent_options.keys()) - _ALLOWED_AGENT_OPTION_KEYS - _FORBIDDEN_AGENT_OPTION_KEYS)
    if extra:
        raise HTTPException(status_code=400, detail={"error": "unknown_agent_options", "unknown_keys": extra})

    out: dict[str, Any] = {
        "base_url": str(os.environ.get("CHATGPTREST_BASE_URL") or "http://127.0.0.1:18711"),
        "api_token": str(cfg.api_token or os.environ.get("CHATGPTREST_API_TOKEN") or ""),
        "state_root": _normalize_state_root(os.environ.get("CHATGPTREST_ADVISOR_STATE_ROOT")),
    }

    if "client_name" in agent_options:
        out["client_name"] = _sanitize_token(str(agent_options.get("client_name") or ""), fallback="chatgpt_advisor_api")
    else:
        hdr = _header(headers, "x-client-name")
        if hdr:
            out["client_name"] = _sanitize_token(hdr, fallback="chatgpt_advisor_api")

    if "client_instance" in agent_options:
        out["client_instance"] = _sanitize_token(str(agent_options.get("client_instance") or ""), fallback="advisor-api")
    else:
        hdr = _header(headers, "x-client-instance")
        if hdr:
            out["client_instance"] = _sanitize_token(hdr, fallback="advisor-api")

    if "request_id_prefix" in agent_options:
        out["request_id_prefix"] = _sanitize_token(str(agent_options.get("request_id_prefix") or ""), fallback="advisor-api")
    else:
        hdr = _header(headers, "x-request-id")
        if hdr:
            out["request_id_prefix"] = _sanitize_token(hdr.split("-", 1)[0], fallback="advisor-api")

    for key in _STR_KEYS:
        if key in {"base_url", "api_token", "client_name", "client_instance", "request_id_prefix"}:
            continue
        if key in agent_options:
            value = str(agent_options.get(key) or "").strip()
            out[key] = value if value else None

    for key in _INT_KEYS:
        if key in agent_options:
            out[key] = _parse_int(agent_options.get(key), key=key)

    for key in _FLOAT_KEYS:
        if key in agent_options:
            out[key] = _parse_float(agent_options.get(key), key=key)

    for key in _BOOL_KEYS:
        if key in agent_options:
            out[key] = _parse_bool(agent_options.get(key), key=key)

    for key in _LIST_KEYS:
        if key in agent_options:
            out[key] = _parse_list(agent_options.get(key), key=key)

    return out


def _plan_only_response(*, wrapper_module: Any, raw_question: str, context: dict[str, Any], force: bool) -> dict[str, Any]:
    refined = str(wrapper_module.prompt_refine(raw_question, context))
    gaps = list(wrapper_module.question_gap_check(raw_question, context))
    route_trace = _route_decision_trace(wrapper_module=wrapper_module, raw_question=raw_question)
    route = str(route_trace.get("route") or "chatgpt_pro")
    result: dict[str, Any] = {
        "ok": True,
        "status": "planned",
        "route": route,
        "route_decision": route_trace,
        "refined_question": refined,
        "followups": gaps,
        "request_id": f"advisor-v1:{uuid.uuid4().hex}",
        "action_hint": "execute_ready",
        "answer_contract": {
            "conclusion": "",
            "evidence": [],
            "uncertainty": [],
            "next_steps": [],
            "source_refs": [],
        },
    }
    if gaps and not bool(force):
        result["ok"] = False
        result["status"] = "needs_context"
        result["action_hint"] = "provide_followup_context"
        return result
    if gaps and bool(force):
        result["assumptions"] = list(gaps)
    return result


_ROUTE_DEEP_RESEARCH = "deep_research"
_ROUTE_GEMINI = "gemini"
_ROUTE_PRO_THEN_DR_THEN_PRO = "pro_then_dr_then_pro"
_ROUTE_PRO_GEMINI_CROSSCHECK = "pro_gemini_crosscheck"

_ADVISOR_MODES: frozenset[str] = frozenset({"fast", "balanced", "strict"})
_MODE_DEFAULT_QUALITY_THRESHOLD: dict[str, int] = {
    "fast": 14,
    "balanced": 17,
    "strict": 20,
}
_RUN_TERMINAL_STATUSES: frozenset[str] = frozenset({"COMPLETED", "FAILED", "CANCELLED"})


def _advisor_request_id(request: Request) -> str:
    raw = (request.headers.get("x-request-id") or "").strip()
    if raw:
        return raw
    return f"advisor-{uuid.uuid4().hex[:12]}"


def _advisor_requested_by(request: Request) -> dict[str, Any]:
    by: dict[str, Any] = {
        "transport": "http",
        "received_at": float(time.time()),
    }
    if request.client is not None:
        by["client"] = {"host": request.client.host, "port": request.client.port}
    hdr = _summarize_write_context(request)
    if hdr:
        by["headers"] = hdr
    return by


def _route_decision_trace(*, wrapper_module: Any, raw_question: str) -> dict[str, Any]:
    trace_fn = getattr(wrapper_module, "channel_strategy_trace", None)
    if callable(trace_fn):
        try:
            trace_obj = trace_fn(raw_question)
            if isinstance(trace_obj, dict):
                route = str(trace_obj.get("route") or "").strip()
                if route:
                    out = dict(trace_obj)
                    out["route"] = route
                    return out
        except Exception:
            pass
    route = str(wrapper_module.channel_strategy(raw_question))
    return {
        "route": route,
        "reason": "wrapper_channel_strategy",
        "flags": {},
        "matched_keywords": {},
        "normalized_question": str(raw_question or ""),
    }


def _normalize_mode(raw: Any) -> str:
    mode = str(raw or "").strip().lower()
    if mode in _ADVISOR_MODES:
        return mode
    return "balanced"


def _normalize_quality_threshold(*, mode: str, quality_threshold: Any) -> int:
    if quality_threshold is None:
        return int(_MODE_DEFAULT_QUALITY_THRESHOLD.get(mode, 17))
    try:
        v = int(quality_threshold)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_quality_threshold",
                "detail": "quality_threshold must be an integer",
            },
        ) from exc
    if v < 0 or v > 100:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_quality_threshold",
                "detail": "quality_threshold must be in [0, 100]",
            },
        )
    return v


def _normalize_max_retries(raw: Any) -> int:
    try:
        v = int(raw if raw is not None else 0)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_max_retries",
                "detail": "max_retries must be an integer",
            },
        ) from exc
    if v < 0 or v > 20:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_max_retries",
                "detail": "max_retries must be in [0, 20]",
            },
        )
    return v


def _run_id_for_request_id(request_id: str) -> str:
    raw = str(request_id or "").strip()
    if not raw:
        return advisor_runs.new_run_id()
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:32]


def _resolve_artifact_path(*, cfg: AppConfig, path_text: str | None) -> Path | None:
    text = str(path_text or "").strip()
    if not text:
        return None
    p = Path(text)
    if not p.is_absolute():
        p = cfg.artifacts_dir / p
    return p


def _read_answer_text(*, cfg: AppConfig, answer_path: str | None) -> str:
    p = _resolve_artifact_path(cfg=cfg, path_text=answer_path)
    if p is None:
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _event_seen_for_attempt(
    conn: Any,
    *,
    run_id: str,
    event_type: str,
    step_id: str | None,
    attempt: int,
) -> bool:
    after = 0
    while True:
        events, next_after = advisor_runs.list_events(conn, run_id=run_id, after_id=after, limit=500)
        if not events:
            return False
        for ev in events:
            if str(ev.get("type") or "") != str(event_type):
                continue
            if step_id is not None and str(ev.get("step_id") or "") != str(step_id):
                continue
            payload = dict(ev.get("payload") or {})
            if max(0, int(payload.get("attempt") or 0)) == max(0, int(attempt)):
                return True
        if next_after <= after or len(events) < 500:
            return False
        after = next_after


def _dispatch_retry_step(
    conn: Any,
    *,
    cfg: AppConfig,
    run: dict[str, Any],
    step: dict[str, Any],
    attempt: int,
) -> dict[str, Any]:
    run_id = str(run["run_id"])
    step_id = str(step["step_id"])
    input_obj = dict(step.get("input") or {})
    child_kind = str(input_obj.get("kind") or "chatgpt_web.ask")
    child_input = dict(input_obj.get("input") or {})
    child_params = dict(input_obj.get("params") or {})
    idem = f"advisor-orchestrate:{run_id}:{step_id}:a{max(1, int(attempt))}"
    requested_by = {
        "transport": "advisor.orchestrate.reconcile",
        "received_at": float(time.time()),
        "headers": {"x-request-id": str(run.get("request_id") or f"advisor:{run_id}")},
    }
    child_job = create_job(
        conn,
        artifacts_dir=cfg.artifacts_dir,
        idempotency_key=idem,
        kind=child_kind,
        input=child_input,
        params=child_params,
        max_attempts=cfg.max_attempts,
        parent_job_id=(str(run.get("orchestrate_job_id") or "") or None),
        client={"name": "advisor_orchestrator"},
        requested_by=requested_by,
        allow_queue=False,
        enforce_conversation_single_flight=True,
    )
    child_job_id = str(child_job.job_id)
    lease_id = advisor_runs.new_lease_id()
    lease_expires_at = float(time.time() + 300.0)
    advisor_runs.upsert_step(
        conn,
        run_id=run_id,
        step_id=step_id,
        step_type=str(step.get("step_type") or "ask"),
        status="EXECUTING",
        attempt=max(1, int(attempt)),
        job_id=child_job_id,
        lease_id=lease_id,
        lease_expires_at=lease_expires_at,
        input_obj=input_obj,
        output_obj={"job_id": child_job_id, "retry_attempt": max(1, int(attempt))},
        evidence_path=(str(step.get("evidence_path") or "") or None),
    )
    advisor_runs.upsert_lease(
        conn,
        lease_id=lease_id,
        run_id=run_id,
        step_id=step_id,
        owner=f"job:{run.get('orchestrate_job_id') or ''}",
        token=lease_id,
        status="leased",
        expires_at=lease_expires_at,
        heartbeat_at=time.time(),
    )
    advisor_runs.append_event(
        conn,
        run_id=run_id,
        step_id=step_id,
        type="step.dispatched",
        attempt=max(1, int(attempt)),
        correlation_id=str(run.get("request_id") or f"advisor:{run_id}"),
        idempotency_key=idem,
        payload={
            "step_id": step_id,
            "attempt": max(1, int(attempt)),
            "lease_id": lease_id,
            "lease_expires_at": lease_expires_at,
            "kind": child_kind,
            "retry": True,
        },
    )
    advisor_runs.append_event(
        conn,
        run_id=run_id,
        step_id=step_id,
        type="step.started",
        attempt=max(1, int(attempt)),
        correlation_id=str(run.get("request_id") or f"advisor:{run_id}"),
        idempotency_key=idem,
        payload={
            "step_id": step_id,
            "attempt": max(1, int(attempt)),
            "lease_id": lease_id,
            "job_id": child_job_id,
            "retry": True,
        },
    )
    advisor_runs.update_run(
        conn,
        run_id=run_id,
        status="RUNNING",
        final_job_id=child_job_id,
        degraded=False,
        error_type=None,
        error=None,
    )
    return advisor_runs.get_run(conn, run_id=run_id) or run


def _reconcile_run_status(conn: Any, *, cfg: AppConfig, run_id: str) -> dict[str, Any] | None:
    run = advisor_runs.get_run(conn, run_id=run_id)
    if run is None:
        return None
    advisor_runs.reclaim_expired_leases(conn, run_id=run_id, now_ts=time.time())

    if str(run.get("status") or "").upper() in (_RUN_TERMINAL_STATUSES | {"DEGRADED", "MANUAL_TAKEOVER"}):
        replay = advisor_runs.replay_run(conn, run_id=run_id, persist_snapshot=False)
        advisor_runs.write_snapshot_json(
            cfg.artifacts_dir,
            run_id=run_id,
            run=run,
            steps=advisor_runs.list_steps(conn, run_id=run_id),
            replay_snapshot=replay,
        )
        return run

    final_job_id = str(run.get("final_job_id") or "").strip()
    if not final_job_id:
        replay = advisor_runs.replay_run(conn, run_id=run_id, persist_snapshot=False)
        advisor_runs.write_snapshot_json(
            cfg.artifacts_dir,
            run_id=run_id,
            run=run,
            steps=advisor_runs.list_steps(conn, run_id=run_id),
            replay_snapshot=replay,
        )
        return run
    child = get_job(conn, job_id=final_job_id)
    if child is None:
        return run

    child_status = str(child.status.value)
    step = advisor_runs.get_step(conn, run_id=run_id, step_id="ask_primary") or {
        "run_id": run_id,
        "step_id": "ask_primary",
        "step_type": "ask",
        "status": "EXECUTING",
        "attempt": 1,
        "input": {},
        "output": {},
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    attempt = max(1, int(step.get("attempt") or 1))
    answer_path = (str(getattr(child, "answer_path", "") or "") or None)

    if child_status == JobStatus.COMPLETED.value:
        answer_text = _read_answer_text(cfg=cfg, answer_path=answer_path)
        gate_report = advisor_gates.evaluate_gate_report(
            run=run,
            step=step,
            answer_text=answer_text,
            evidence_path=str(_resolve_artifact_path(cfg=cfg, path_text=answer_path) or ""),
        )
        gate_type = "gate.passed" if bool(gate_report.get("passed")) else "gate.failed"
        if not _event_seen_for_attempt(conn, run_id=run_id, event_type=gate_type, step_id="ask_primary", attempt=attempt):
            advisor_runs.append_event(
                conn,
                run_id=run_id,
                step_id="ask_primary",
                type=gate_type,
                attempt=attempt,
                correlation_id=str(run.get("request_id") or f"advisor:{run_id}"),
                evidence_path=answer_path,
                payload={
                    "step_id": "ask_primary",
                    "attempt": attempt,
                    "report": gate_report,
                },
            )
        if bool(gate_report.get("passed")):
            advisor_runs.upsert_step(
                conn,
                run_id=run_id,
                step_id="ask_primary",
                step_type="ask",
                status="SUCCEEDED",
                attempt=attempt,
                job_id=final_job_id,
                lease_id=(str(step.get("lease_id") or "") or advisor_runs.new_lease_id()),
                lease_expires_at=time.time(),
                input_obj=dict(step.get("input") or {}),
                output_obj={"job_id": final_job_id, "status": child_status, "gates": gate_report},
                evidence_path=answer_path,
            )
            if not _event_seen_for_attempt(conn, run_id=run_id, event_type="step.succeeded", step_id="ask_primary", attempt=attempt):
                advisor_runs.append_event(
                    conn,
                    run_id=run_id,
                    step_id="ask_primary",
                    type="step.succeeded",
                    attempt=attempt,
                    evidence_path=answer_path,
                    payload={"step_id": "ask_primary", "attempt": attempt, "job_id": final_job_id},
                )
            if not advisor_runs.has_event(conn, run_id=run_id, type="run.completed"):
                advisor_runs.append_event(
                    conn,
                    run_id=run_id,
                    type="run.completed",
                    payload={"child_job_id": final_job_id, "status": child_status, "gates": gate_report},
                )
            run_out = advisor_runs.update_run(
                conn,
                run_id=run_id,
                status="COMPLETED",
                degraded=False,
                error_type=None,
                error=None,
                ended_at=time.time(),
            )
            replay = advisor_runs.replay_run(conn, run_id=run_id, persist_snapshot=False)
            advisor_runs.write_snapshot_json(
                cfg.artifacts_dir,
                run_id=run_id,
                run=(run_out or run),
                steps=advisor_runs.list_steps(conn, run_id=run_id),
                replay_snapshot=replay,
            )
            return run_out or run

        max_retries = max(0, int(run.get("max_retries") or 0))
        retries_remaining = max(0, max_retries - (attempt - 1))
        advisor_runs.upsert_step(
            conn,
            run_id=run_id,
            step_id="ask_primary",
            step_type="ask",
            status="RETRY_WAIT",
            attempt=attempt,
            job_id=final_job_id,
            lease_id=(str(step.get("lease_id") or "") or advisor_runs.new_lease_id()),
            lease_expires_at=time.time(),
            input_obj=dict(step.get("input") or {}),
            output_obj={
                "job_id": final_job_id,
                "status": child_status,
                "gates": gate_report,
                "retries_remaining": retries_remaining,
            },
            evidence_path=answer_path,
        )
        advisor_runs.update_run(conn, run_id=run_id, status="WAITING_GATES", degraded=False)
        if retries_remaining > 0:
            try:
                run_retry = _dispatch_retry_step(conn, cfg=cfg, run=run, step=step, attempt=attempt + 1)
                replay = advisor_runs.replay_run(conn, run_id=run_id, persist_snapshot=False)
                advisor_runs.write_snapshot_json(
                    cfg.artifacts_dir,
                    run_id=run_id,
                    run=run_retry,
                    steps=advisor_runs.list_steps(conn, run_id=run_id),
                    replay_snapshot=replay,
                )
                return run_retry
            except (ConversationBusy, IdempotencyCollision, ValueError) as exc:
                advisor_runs.append_event(
                    conn,
                    run_id=run_id,
                    step_id="ask_primary",
                    type="step.failed",
                    attempt=attempt,
                    payload={
                        "step_id": "ask_primary",
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "reason": "retry_dispatch_failed",
                    },
                )
                if not advisor_runs.has_event(conn, run_id=run_id, type="run.degraded"):
                    advisor_runs.append_event(
                        conn,
                        run_id=run_id,
                        type="run.degraded",
                        payload={
                            "reason_type": type(exc).__name__,
                            "reason": str(exc),
                            "fallback_action": "manual_takeover_required",
                        },
                    )
                run_out = advisor_runs.update_run(
                    conn,
                    run_id=run_id,
                    status="DEGRADED",
                    degraded=True,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                replay = advisor_runs.replay_run(conn, run_id=run_id, persist_snapshot=False)
                advisor_runs.write_snapshot_json(
                    cfg.artifacts_dir,
                    run_id=run_id,
                    run=(run_out or run),
                    steps=advisor_runs.list_steps(conn, run_id=run_id),
                    replay_snapshot=replay,
                )
                return run_out or run

        if not advisor_runs.has_event(conn, run_id=run_id, type="run.degraded"):
            advisor_runs.append_event(
                conn,
                run_id=run_id,
                type="run.degraded",
                payload={
                    "reason_type": "GateFailed",
                    "reason": "quality/role/evidence gate failed and retries exhausted",
                    "report": gate_report,
                    "fallback_action": "manual_takeover_required",
                },
            )
        run_out = advisor_runs.update_run(
            conn,
            run_id=run_id,
            status="DEGRADED",
            degraded=True,
            error_type="GateFailed",
            error="quality/role/evidence gate failed",
        )
        replay = advisor_runs.replay_run(conn, run_id=run_id, persist_snapshot=False)
        advisor_runs.write_snapshot_json(
            cfg.artifacts_dir,
            run_id=run_id,
            run=(run_out or run),
            steps=advisor_runs.list_steps(conn, run_id=run_id),
            replay_snapshot=replay,
        )
        return run_out or run

    if child_status in {
        JobStatus.ERROR.value,
        JobStatus.CANCELED.value,
        JobStatus.BLOCKED.value,
        JobStatus.COOLDOWN.value,
        JobStatus.NEEDS_FOLLOWUP.value,
    }:
        advisor_runs.upsert_step(
            conn,
            run_id=run_id,
            step_id="ask_primary",
            step_type="ask",
            status="FAILED",
            attempt=attempt,
            job_id=final_job_id,
            lease_id=(str(step.get("lease_id") or "") or advisor_runs.new_lease_id()),
            lease_expires_at=time.time(),
            input_obj=dict(step.get("input") or {}),
            output_obj={
                "job_id": final_job_id,
                "status": child_status,
                "error_type": str(getattr(child, "last_error_type", "") or ""),
                "error": str(getattr(child, "last_error", "") or ""),
            },
            evidence_path=answer_path,
        )
        if not _event_seen_for_attempt(conn, run_id=run_id, event_type="step.failed", step_id="ask_primary", attempt=attempt):
            advisor_runs.append_event(
                conn,
                run_id=run_id,
                step_id="ask_primary",
                type="step.failed",
                attempt=attempt,
                evidence_path=answer_path,
                payload={
                    "step_id": "ask_primary",
                    "attempt": attempt,
                    "job_id": final_job_id,
                    "status": child_status,
                    "error_type": str(getattr(child, "last_error_type", "") or ""),
                    "error": str(getattr(child, "last_error", "") or ""),
                },
            )
        if not advisor_runs.has_event(conn, run_id=run_id, type="run.degraded"):
            advisor_runs.append_event(
                conn,
                run_id=run_id,
                type="run.degraded",
                payload={
                    "child_job_id": final_job_id,
                    "status": child_status,
                    "error_type": str(getattr(child, "last_error_type", "") or ""),
                    "error": str(getattr(child, "last_error", "") or ""),
                    "fallback_action": "manual_takeover_required",
                },
            )
        run_out = advisor_runs.update_run(
            conn,
            run_id=run_id,
            status="DEGRADED",
            degraded=True,
            error_type=str(getattr(child, "last_error_type", "") or child_status),
            error=str(getattr(child, "last_error", "") or child_status),
        )
        replay = advisor_runs.replay_run(conn, run_id=run_id, persist_snapshot=False)
        advisor_runs.write_snapshot_json(
            cfg.artifacts_dir,
            run_id=run_id,
            run=(run_out or run),
            steps=advisor_runs.list_steps(conn, run_id=run_id),
            replay_snapshot=replay,
        )
        return run_out or run
    return run


def _build_orchestrate_params(*, req: AdvisorAdviseRequest, normalized_opts: dict[str, Any]) -> dict[str, Any]:
    mode = _normalize_mode(req.mode)
    quality_threshold = _normalize_quality_threshold(mode=mode, quality_threshold=req.quality_threshold)
    max_retries = _normalize_max_retries(req.max_retries)
    out: dict[str, Any] = {
        "mode": mode,
        "quality_threshold": quality_threshold,
        "crosscheck": bool(req.crosscheck),
        "max_retries": max_retries,
    }
    passthrough_keys = {
        "preset",
        "timeout_seconds",
        "send_timeout_seconds",
        "wait_timeout_seconds",
        "max_wait_seconds",
        "min_chars",
        "poll_seconds",
        "answer_format",
        "agent_mode",
        "dry_run",
        "openclaw_mcp_url",
        "openclaw_agent_id",
        "openclaw_model",
        "openclaw_thinking",
        "openclaw_session_key",
        "openclaw_timeout_seconds",
        "openclaw_session_timeout_seconds",
        "openclaw_required",
        "openclaw_cleanup",
        "openclaw_allow_a2a",
    }
    for key in passthrough_keys:
        if key in normalized_opts and normalized_opts.get(key) is not None:
            out[key] = normalized_opts.get(key)
    return out


def _submit_advisor_orchestrate_job(
    *,
    cfg: AppConfig,
    request: Request,
    req: AdvisorAdviseRequest,
    plan: dict[str, Any],
    execution_question: str,
    normalized_opts: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    route = str(plan.get("route") or "chatgpt_pro")
    run_id = _run_id_for_request_id(request_id)
    mode = _normalize_mode(req.mode)
    quality_threshold = _normalize_quality_threshold(mode=mode, quality_threshold=req.quality_threshold)
    max_retries = _normalize_max_retries(req.max_retries)
    run_params = _build_orchestrate_params(req=req, normalized_opts=normalized_opts)

    input_obj = {
        "run_id": run_id,
        "request_id": request_id,
        "route": route,
        "raw_question": str(req.raw_question or ""),
        "question": execution_question,
        "context": dict(req.context or {}),
    }
    idem = _sanitize_token(f"advisor-orch-{request_id}", fallback=f"advisor-orch-{uuid.uuid4().hex}")
    requested_by = _advisor_requested_by(request)
    try:
        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = advisor_runs.get_run(conn, run_id=run_id)
            if existing is None:
                advisor_runs.create_run(
                    conn,
                    run_id=run_id,
                    request_id=request_id,
                    mode=mode,
                    status="PLAN_COMPILED",
                    route=route,
                    raw_question=str(req.raw_question or ""),
                    normalized_question=execution_question,
                    context=dict(req.context or {}),
                    quality_threshold=quality_threshold,
                    crosscheck=bool(req.crosscheck),
                    max_retries=max_retries,
                    orchestrate_job_id=None,
                    final_job_id=None,
                    degraded=False,
                )
                advisor_runs.append_event(
                    conn,
                    run_id=run_id,
                    type="run.created",
                    payload={"run_id": run_id, "request_id": request_id, "mode": mode},
                )
                advisor_runs.append_event(
                    conn,
                    run_id=run_id,
                    type="run.planned",
                    payload={
                        "route": route,
                        "quality_threshold": quality_threshold,
                        "crosscheck": bool(req.crosscheck),
                        "max_retries": max_retries,
                    },
                )
                advisor_runs.write_run_json(
                    cfg.artifacts_dir,
                    run_id=run_id,
                    name="request.json",
                    payload={
                        "run_id": run_id,
                        "request_id": request_id,
                        "raw_question": str(req.raw_question or ""),
                        "execution_question": execution_question,
                        "context": dict(req.context or {}),
                        "mode": mode,
                        "quality_threshold": quality_threshold,
                        "crosscheck": bool(req.crosscheck),
                        "max_retries": max_retries,
                        "route": route,
                    },
                )
            else:
                advisor_runs.update_run(
                    conn,
                    run_id=run_id,
                    mode=mode,
                    route=route,
                    normalized_question=execution_question,
                    quality_threshold=quality_threshold,
                    crosscheck=bool(req.crosscheck),
                    max_retries=max_retries,
                )
            job = create_job(
                conn,
                artifacts_dir=cfg.artifacts_dir,
                idempotency_key=idem,
                kind="advisor.orchestrate",
                input=input_obj,
                params=run_params,
                max_attempts=max(1, int(cfg.max_attempts)),
                parent_job_id=None,
                client={"name": _sanitize_token(str(normalized_opts.get("client_name") or ""), fallback="chatgpt_advisor_api")},
                requested_by=requested_by,
                allow_queue=False,
                enforce_conversation_single_flight=True,
            )
            advisor_runs.update_run(conn, run_id=run_id, orchestrate_job_id=str(job.job_id))
            conn.commit()
    except ConversationBusy as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conversation_busy",
                "error_type": "ConversationBusy",
                "reason": str(exc),
                "active_job_id": exc.active_job_id,
                "retry_after_seconds": max(5, int(cfg.min_prompt_interval_seconds or 30)),
            },
        ) from exc
    except IdempotencyCollision as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "idempotency_collision",
                "error_type": "IdempotencyCollision",
                "reason": str(exc),
                "idempotency_key": getattr(exc, "idempotency_key", None),
                "existing_job_id": getattr(exc, "existing_job_id", None),
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_orchestrate_payload",
                "error_type": type(exc).__name__,
                "reason": str(exc),
            },
        ) from exc

    retry_after = (
        max(0, int(float(job.not_before) - time.time()))
        if getattr(job, "not_before", None) and float(job.not_before) > time.time()
        else None
    )
    status = str(job.status.value)
    if status == "cooldown":
        return {
            "ok": False,
            "status": "cooldown",
            "action_hint": "retry_after_cooldown",
            "provider": "advisor_orchestrate",
            "fallback_action": "none",
            "run_id": run_id,
            "orchestrate_job_id": str(job.job_id),
            "job_id": str(job.job_id),
            "phase": str(getattr(job, "phase", "") or ""),
            "job_status": status,
            "retry_after_seconds": retry_after,
            "reason": str(getattr(job, "last_error", "") or "cooldown"),
            "degraded": False,
        }
    return {
        "ok": True,
        "status": "job_created",
        "action_hint": "wait_for_job_completion",
        "provider": "advisor_orchestrate",
        "fallback_action": "none",
        "run_id": run_id,
        "orchestrate_job_id": str(job.job_id),
        "job_id": str(job.job_id),
        "phase": str(getattr(job, "phase", "") or ""),
        "job_status": status,
        "retry_after_seconds": retry_after,
        "degraded": False,
    }


def _build_execution_question(plan_obj: dict[str, Any], *, force: bool) -> str:
    refined = str(plan_obj.get("refined_question") or "").strip()
    followups = [str(x).strip() for x in list(plan_obj.get("followups") or []) if str(x).strip()]
    assumptions = [str(x).strip() for x in list(plan_obj.get("assumptions") or []) if str(x).strip()]
    if not refined:
        raise HTTPException(status_code=500, detail={"error": "advisor_plan_invalid", "detail": "refined_question is empty"})
    if followups and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "advisor_needs_context",
                "reason": "followup_questions_required",
                "followups": followups,
                "action_hint": "provide_followup_context",
            },
        )
    if assumptions:
        lines = "\n".join(f"- {item}" for item in assumptions)
        return f"{refined}\n\n已识别待确认信息（先基于合理假设继续）：\n{lines}"
    return refined


def _build_advisor_job_request(
    *,
    execution_question: str,
    route: str,
    normalized_opts: dict[str, Any],
    request_id: str,
) -> tuple[str, dict[str, Any], dict[str, Any], str, str, str]:
    kind = "chatgpt_web.ask"
    provider = "chatgpt_web"
    fallback_action = "none"

    if route == _ROUTE_GEMINI:
        kind = "gemini_web.ask"
        provider = "gemini_web"
    elif route == _ROUTE_PRO_GEMINI_CROSSCHECK:
        # Keep execute=true single-flight; cross-check can be run as a follow-up job.
        fallback_action = "crosscheck_degraded_to_single_job"

    input_obj: dict[str, Any] = {"question": execution_question}
    params_obj: dict[str, Any] = {}

    if route in {_ROUTE_DEEP_RESEARCH, _ROUTE_PRO_THEN_DR_THEN_PRO}:
        params_obj["deep_research"] = True

    if "preset" not in normalized_opts:
        if route == _ROUTE_GEMINI:
            params_obj["preset"] = "pro"
        else:
            params_obj["preset"] = "thinking_heavy"

    passthrough_keys = {
        "preset",
        "timeout_seconds",
        "send_timeout_seconds",
        "wait_timeout_seconds",
        "max_wait_seconds",
        "min_chars",
        "poll_seconds",
        "answer_format",
        "agent_mode",
        "dry_run",
    }
    for key in passthrough_keys:
        if key in normalized_opts and normalized_opts.get(key) is not None:
            params_obj[key] = normalized_opts.get(key)

    if route in {_ROUTE_DEEP_RESEARCH, _ROUTE_PRO_THEN_DR_THEN_PRO}:
        params_obj["deep_research"] = True

    if route == _ROUTE_PRO_GEMINI_CROSSCHECK:
        params_obj.setdefault("web_search", True)

    # Deterministic idempotency for retries of the same request.
    idem = _sanitize_token(f"advisor-exec-{request_id}", fallback=f"advisor-exec-{uuid.uuid4().hex}")
    return kind, input_obj, params_obj, idem, provider, fallback_action


def _submit_advisor_job(
    *,
    cfg: AppConfig,
    request: Request,
    execution_question: str,
    route: str,
    normalized_opts: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    client_name = _sanitize_token(str(normalized_opts.get("client_name") or ""), fallback="chatgpt_advisor_api")
    kind, input_obj, params_obj, idempotency_key, provider, fallback_action = _build_advisor_job_request(
        execution_question=execution_question,
        route=route,
        normalized_opts=normalized_opts,
        request_id=request_id,
    )
    requested_by = _advisor_requested_by(request)
    if kind in {"chatgpt_web.ask", "gemini_web.ask"}:
        try:
            validate_ask_preset(kind=kind, params_obj=params_obj)
        except PresetValidationError as exc:
            raise HTTPException(status_code=400, detail=exc.detail) from exc
    try:
        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            job = create_job(
                conn,
                artifacts_dir=cfg.artifacts_dir,
                idempotency_key=idempotency_key,
                kind=kind,
                input=input_obj,
                params=params_obj,
                max_attempts=cfg.max_attempts,
                parent_job_id=None,
                client={"name": client_name},
                requested_by=requested_by,
                allow_queue=False,
                enforce_conversation_single_flight=True,
            )
            conn.commit()
    except ConversationBusy as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conversation_busy",
                "error_type": "ConversationBusy",
                "reason": str(exc),
                "active_job_id": exc.active_job_id,
                "retry_after_seconds": max(5, int(cfg.min_prompt_interval_seconds or 30)),
            },
        ) from exc
    except IdempotencyCollision as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "idempotency_collision",
                "error_type": "IdempotencyCollision",
                "reason": str(exc),
                "idempotency_key": getattr(exc, "idempotency_key", None),
                "existing_job_id": getattr(exc, "existing_job_id", None),
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_job_payload",
                "error_type": type(exc).__name__,
                "reason": str(exc),
            },
        ) from exc

    retry_after = (
        max(0, int(float(job.not_before) - time.time()))
        if getattr(job, "not_before", None) and float(job.not_before) > time.time()
        else None
    )
    degraded = str(fallback_action or "") == "crosscheck_degraded_to_single_job"
    status = str(job.status.value)
    if status == "cooldown":
        return {
            "ok": False,
            "status": "cooldown",
            "action_hint": "retry_after_cooldown",
            "provider": provider,
            "fallback_action": fallback_action,
            "kind": kind,
            "job_id": str(job.job_id),
            "phase": str(getattr(job, "phase", "") or ""),
            "job_status": status,
            "retry_after_seconds": retry_after,
            "reason": str(getattr(job, "last_error", "") or "cooldown"),
            "degraded": degraded,
        }
    return {
        "ok": True,
        "status": "degraded_job_created" if degraded else "job_created",
        "action_hint": "wait_for_job_completion",
        "provider": provider,
        "fallback_action": fallback_action,
        "kind": kind,
        "job_id": str(job.job_id),
        "phase": str(getattr(job, "phase", "") or ""),
        "job_status": status,
        "retry_after_seconds": retry_after,
        "degraded": degraded,
    }


def make_advisor_router(cfg: AppConfig) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/advisor/advise")
    async def advisor_advise(req: AdvisorAdviseRequest, request: Request) -> dict[str, Any]:
        started = time.perf_counter()
        request_id = _advisor_request_id(request)
        client_name_for_log = (request.headers.get("x-client-name") or "").strip() or None
        route_for_log = "unknown"
        provider_for_log = "unknown"
        fallback_for_log = "none"
        final_status_for_log = "unknown"
        if not str(req.raw_question or "").strip():
            raise HTTPException(status_code=400, detail={"error": "invalid_raw_question", "detail": "raw_question is required"})
        if bool(req.execute):
            _enforce_client_name_allowlist(request)
            _enforce_write_trace_headers(request, operation="advisor_advise_execute")
        if not isinstance(req.context, dict):
            raise HTTPException(status_code=400, detail={"error": "invalid_context", "detail": "context must be an object"})
        if not isinstance(req.agent_options, dict):
            raise HTTPException(status_code=400, detail={"error": "invalid_agent_options", "detail": "agent_options must be an object"})

        lower_headers = {str(k).lower(): str(v) for k, v in request.headers.items()}
        normalized_opts = _normalize_agent_options(agent_options=dict(req.agent_options), headers=lower_headers, cfg=cfg)
        try:
            wrapper_module = await asyncio.to_thread(_load_wrapper_module)
            plan = await asyncio.to_thread(
                _plan_only_response,
                wrapper_module=wrapper_module,
                raw_question=str(req.raw_question),
                context=dict(req.context),
                force=bool(req.force),
            )
            if not isinstance(plan, dict):
                raise HTTPException(status_code=502, detail={"error": "advisor_invalid_response", "detail": "wrapper returned non-object"})
            plan.setdefault("ok", bool(plan.get("ok")))
            plan.setdefault("status", str(plan.get("status") or "unknown"))
            plan["request_id"] = request_id
            plan["mode"] = _normalize_mode(req.mode)
            plan["orchestrate"] = bool(req.orchestrate)
            plan["quality_threshold"] = _normalize_quality_threshold(
                mode=str(plan["mode"]),
                quality_threshold=req.quality_threshold,
            )
            plan["crosscheck"] = bool(req.crosscheck)
            plan["max_retries"] = _normalize_max_retries(req.max_retries)

            route_for_log = str(plan.get("route") or "unknown")
            if route_for_log == _ROUTE_GEMINI:
                provider_for_log = "gemini_web"
            else:
                provider_for_log = "chatgpt_web"
            if route_for_log == _ROUTE_PRO_GEMINI_CROSSCHECK:
                fallback_for_log = "crosscheck_degraded_to_single_job"

            if not bool(req.execute):
                final_status_for_log = str(plan.get("status") or "planned")
                return plan

            execution_question = _build_execution_question(plan, force=bool(req.force))
            if bool(req.orchestrate):
                submitted = await asyncio.to_thread(
                    _submit_advisor_orchestrate_job,
                    cfg=cfg,
                    request=request,
                    req=req,
                    plan=plan,
                    execution_question=execution_question,
                    normalized_opts=normalized_opts,
                    request_id=request_id,
                )
                provider_for_log = "advisor_orchestrate"
            else:
                submitted = await asyncio.to_thread(
                    _submit_advisor_job,
                    cfg=cfg,
                    request=request,
                    execution_question=execution_question,
                    route=route_for_log,
                    normalized_opts=normalized_opts,
                    request_id=request_id,
                )
            submitted.setdefault("fallback_action", fallback_for_log)
            fallback_for_log = str(submitted.get("fallback_action") or fallback_for_log)
            provider_for_log = str(submitted.get("provider") or provider_for_log)
            out = dict(plan)
            out.update(submitted)
            out["execute"] = True
            final_status_for_log = str(out.get("status") or "unknown")
            return out
        except HTTPException as exc:
            final_status_for_log = f"http_{exc.status_code}"
            raise
        except Exception as exc:
            final_status_for_log = "error"
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "advisor_execution_failed",
                    "error_type": type(exc).__name__,
                    "reason": str(exc),
                    "retry_after_seconds": None,
                },
            ) from exc
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000.0)
            _LOG.info(
                "advisor_advise request_id=%s client_name=%s execute=%s route=%s provider=%s elapsed_ms=%s fallback_action=%s final_status=%s",
                request_id,
                client_name_for_log,
                bool(req.execute),
                route_for_log,
                provider_for_log,
                elapsed_ms,
                fallback_for_log,
                final_status_for_log,
            )

    @router.get("/v1/advisor/runs/{run_id}", response_model=AdvisorRunView)
    def advisor_run_get(run_id: str) -> dict[str, Any]:
        with connect(cfg.db_path) as conn:
            run = advisor_runs.get_run(conn, run_id=run_id)
            if run is None:
                raise HTTPException(status_code=404, detail={"error": "advisor_run_not_found", "run_id": run_id})
            steps = advisor_runs.list_steps(conn, run_id=run_id)
        out = dict(run)
        out["ok"] = True
        out["steps"] = steps
        return out

    @router.post("/v1/advisor/runs/{run_id}/reconcile", response_model=AdvisorRunView)
    def advisor_run_reconcile(run_id: str, request: Request) -> dict[str, Any]:
        _enforce_client_name_allowlist(request)
        _enforce_write_trace_headers(request, operation="advisor_run_reconcile")
        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            run = _reconcile_run_status(conn, cfg=cfg, run_id=run_id)
            if run is None:
                conn.rollback()
                raise HTTPException(status_code=404, detail={"error": "advisor_run_not_found", "run_id": run_id})
            steps = advisor_runs.list_steps(conn, run_id=run_id)
            conn.commit()
        out = dict(run)
        out["ok"] = True
        out["steps"] = steps
        return out

    @router.get("/v1/advisor/runs/{run_id}/events", response_model=AdvisorRunEventsView)
    def advisor_run_events(
        run_id: str,
        after_id: int = Query(default=0, ge=0),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> dict[str, Any]:
        with connect(cfg.db_path) as conn:
            run = advisor_runs.get_run(conn, run_id=run_id)
            if run is None:
                raise HTTPException(status_code=404, detail={"error": "advisor_run_not_found", "run_id": run_id})
            events, next_after_id = advisor_runs.list_events(conn, run_id=run_id, after_id=after_id, limit=limit)
        return {
            "ok": True,
            "run_id": run_id,
            "after_id": int(after_id),
            "next_after_id": int(next_after_id),
            "events": events,
        }

    @router.get("/v1/advisor/runs/{run_id}/replay")
    def advisor_run_replay(
        run_id: str,
        persist: bool = Query(default=False),
    ) -> dict[str, Any]:
        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            run = advisor_runs.get_run(conn, run_id=run_id)
            if run is None:
                conn.rollback()
                raise HTTPException(status_code=404, detail={"error": "advisor_run_not_found", "run_id": run_id})
            replay = advisor_runs.replay_run(conn, run_id=run_id, persist_snapshot=bool(persist))
            run_next = advisor_runs.get_run(conn, run_id=run_id) or run
            steps = advisor_runs.list_steps(conn, run_id=run_id)
            snapshot_path = advisor_runs.write_snapshot_json(
                cfg.artifacts_dir,
                run_id=run_id,
                run=run_next,
                steps=steps,
                replay_snapshot=replay,
            )
            conn.commit()
        return {
            "ok": True,
            "run_id": run_id,
            "persisted": bool(persist),
            "snapshot_path": snapshot_path,
            "run": run_next,
            "steps": steps,
            "replay": replay,
        }

    @router.post("/v1/advisor/runs/{run_id}/takeover")
    def advisor_run_takeover(
        run_id: str,
        request: Request,
        body: dict[str, Any] | None = Body(default=None),
    ) -> dict[str, Any]:
        _enforce_client_name_allowlist(request)
        _enforce_write_trace_headers(request, operation="advisor_run_takeover")
        payload = dict(body or {})
        note = str(payload.get("note") or "").strip()
        actor = str(payload.get("actor") or "manual").strip() or "manual"
        compensation = dict(payload.get("compensation") or {})
        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            run = advisor_runs.get_run(conn, run_id=run_id)
            if run is None:
                conn.rollback()
                raise HTTPException(status_code=404, detail={"error": "advisor_run_not_found", "run_id": run_id})
            step = advisor_runs.upsert_step(
                conn,
                run_id=run_id,
                step_id="manual_takeover",
                step_type="takeover",
                status="COMPENSATED",
                attempt=1,
                job_id=None,
                lease_id=None,
                lease_expires_at=None,
                input_obj={"note": note, "actor": actor, "compensation": compensation},
                output_obj={"status": "ack", "actor": actor},
                evidence_path=None,
            )
            advisor_runs.append_event(
                conn,
                run_id=run_id,
                step_id="manual_takeover",
                type="step.compensated",
                attempt=1,
                agent_id=actor,
                payload={
                    "step_id": "manual_takeover",
                    "attempt": 1,
                    "note": note,
                    "compensation": compensation,
                },
            )
            advisor_runs.append_event(
                conn,
                run_id=run_id,
                type="run.taken_over",
                agent_id=actor,
                payload={"actor": actor, "note": note, "compensation": compensation},
            )
            run_next = advisor_runs.update_run(
                conn,
                run_id=run_id,
                status="MANUAL_TAKEOVER",
                degraded=True,
                error_type="ManualTakeover",
                error=(note or "manual takeover requested"),
            ) or run
            takeover_path = advisor_runs.write_run_json(
                cfg.artifacts_dir,
                run_id=run_id,
                name="takeover.json",
                payload={
                    "run_id": run_id,
                    "actor": actor,
                    "note": note,
                    "compensation": compensation,
                    "ts": float(time.time()),
                },
            )
            replay = advisor_runs.replay_run(conn, run_id=run_id, persist_snapshot=False)
            snapshot_path = advisor_runs.write_snapshot_json(
                cfg.artifacts_dir,
                run_id=run_id,
                run=run_next,
                steps=advisor_runs.list_steps(conn, run_id=run_id),
                replay_snapshot=replay,
            )
            conn.commit()
        return {
            "ok": True,
            "run_id": run_id,
            "status": str(run_next.get("status") or "MANUAL_TAKEOVER"),
            "takeover_path": takeover_path,
            "snapshot_path": snapshot_path,
            "step": step,
        }

    @router.get("/v1/advisor/runs/{run_id}/artifacts")
    def advisor_run_artifacts(run_id: str) -> dict[str, Any]:
        linked_job_artifacts: list[dict[str, Any]] = []
        with connect(cfg.db_path) as conn:
            run = advisor_runs.get_run(conn, run_id=run_id)
            if run is None:
                raise HTTPException(status_code=404, detail={"error": "advisor_run_not_found", "run_id": run_id})
            final_job_id = str(run.get("final_job_id") or "").strip()
            if final_job_id:
                child = get_job(conn, job_id=final_job_id)
                if child is not None:
                    for key in ("answer_path", "conversation_export_path"):
                        value = str(getattr(child, key, "") or "").strip()
                        if value:
                            linked_job_artifacts.append({"path": value, "job_id": final_job_id, "type": key})
        files = advisor_runs.list_run_artifacts(cfg.artifacts_dir, run_id=run_id)
        return {
            "ok": True,
            "run_id": run_id,
            "artifacts": files,
            "linked_job_artifacts": linked_job_artifacts,
        }

    return router
