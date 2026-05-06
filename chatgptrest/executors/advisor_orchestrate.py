from __future__ import annotations

import json
import time
from typing import Any

from chatgptrest.core import advisor_runs
from chatgptrest.core.config import AppConfig
from chatgptrest.core.db import connect
from chatgptrest.core.idempotency import IdempotencyCollision
from chatgptrest.core.job_store import ConversationBusy, create_job
from chatgptrest.executors.base import BaseExecutor, ExecutorResult
from chatgptrest.integrations.openclaw_adapter import (
    OpenClawAdapter,
    OpenClawAdapterError,
    openclaw_mcp_url_from_params,
)
from chatgptrest.providers.registry import PresetValidationError, validate_ask_preset


_ROUTE_GEMINI = "gemini"
_ROUTE_DEEP_RESEARCH = "deep_research"
_ROUTE_PRO_THEN_DR_THEN_PRO = "pro_then_dr_then_pro"
_ROUTE_PRO_GEMINI_CROSSCHECK = "pro_gemini_crosscheck"

_MODE_DEFAULT_THRESHOLD: dict[str, int] = {
    "fast": 14,
    "balanced": 17,
    "strict": 20,
}


def _safe_int(raw: Any, default: int) -> int:
    try:
        return int(raw)
    except Exception:
        return int(default)


def _safe_bool(raw: Any) -> bool:
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
    return False


def _normalize_mode(raw: Any) -> str:
    mode = str(raw or "").strip().lower()
    if mode in {"fast", "balanced", "strict"}:
        return mode
    return "balanced"


def _build_child_job(
    *,
    route: str,
    question: str,
    params: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any], str, str]:
    kind = "chatgpt_web.ask"
    provider = "chatgpt_web"
    out_params: dict[str, Any] = {}
    input_obj = {"question": str(question or "")}

    if route == _ROUTE_GEMINI:
        kind = "gemini_web.ask"
        provider = "gemini_web"

    if route in {_ROUTE_DEEP_RESEARCH, _ROUTE_PRO_THEN_DR_THEN_PRO}:
        out_params["deep_research"] = True

    preset = str(params.get("preset") or "").strip()
    if preset:
        out_params["preset"] = preset
    else:
        out_params["preset"] = ("pro" if kind == "gemini_web.ask" else "thinking_heavy")

    passthrough_keys = {
        "timeout_seconds",
        "send_timeout_seconds",
        "wait_timeout_seconds",
        "max_wait_seconds",
        "poll_seconds",
        "min_chars",
        "answer_format",
        "agent_mode",
        "web_search",
    }
    for key in passthrough_keys:
        if key in params and params.get(key) is not None:
            out_params[key] = params.get(key)

    if route == _ROUTE_PRO_GEMINI_CROSSCHECK:
        out_params.setdefault("web_search", True)

    return kind, input_obj, out_params, provider, route


class AdvisorOrchestrateExecutor(BaseExecutor):
    def __init__(self, *, cfg: AppConfig) -> None:
        self._cfg = cfg

    async def run(self, *, job_id: str, kind: str, input: dict[str, Any], params: dict[str, Any]) -> ExecutorResult:  # noqa: A002
        run_id = str((input or {}).get("run_id") or "").strip()
        request_id = str((input or {}).get("request_id") or "").strip()
        question = str((input or {}).get("question") or "").strip()
        route = str((input or {}).get("route") or "chatgpt_pro").strip()
        raw_question = str((input or {}).get("raw_question") or question).strip()
        context = dict((input or {}).get("context") or {})
        mode = _normalize_mode((params or {}).get("mode"))
        quality_threshold = _safe_int((params or {}).get("quality_threshold"), _MODE_DEFAULT_THRESHOLD[mode])
        crosscheck = _safe_bool((params or {}).get("crosscheck"))
        max_retries = max(0, _safe_int((params or {}).get("max_retries"), 0))

        if not run_id:
            return ExecutorResult(
                status="error",
                answer="",
                meta={"error_type": "ValueError", "error": "advisor.orchestrate missing input.run_id"},
            )
        if not question:
            return ExecutorResult(
                status="error",
                answer="",
                meta={"error_type": "ValueError", "error": "advisor.orchestrate missing input.question"},
            )

        step_id = "ask_primary"
        lease_id = advisor_runs.new_lease_id()
        now = time.time()
        lease_ttl_seconds = max(60, _safe_int((params or {}).get("lease_ttl_seconds"), 300))
        lease_expires_at = now + float(lease_ttl_seconds)
        child_job_id: str | None = None
        child_kind: str | None = None
        provider: str | None = None
        fallback_action = "none"
        corr_id = (request_id or f"advisor:{run_id}")
        openclaw_trace: dict[str, Any] | None = None
        openclaw_required = _safe_bool((params or {}).get("openclaw_required"))

        try:
            openclaw_url = openclaw_mcp_url_from_params(dict(params or {}))
            if openclaw_url:
                adapter = OpenClawAdapter(url=openclaw_url)
                try:
                    session_trace = adapter.run_protocol(
                        run_id=run_id,
                        step_id=step_id,
                        question=question,
                        params=dict(params or {}),
                    )
                    openclaw_trace = {
                        "mcp_url": openclaw_url,
                        "session_key": session_trace.session_key,
                        "spawn": session_trace.spawn,
                        "send": session_trace.send,
                        "status": session_trace.status,
                    }
                except OpenClawAdapterError as exc:
                    if openclaw_required:
                        raise ValueError(f"openclaw_required failed at {exc.stage}: {exc}") from exc
                    openclaw_trace = {
                        "mcp_url": openclaw_url,
                        "error_type": "OpenClawAdapterError",
                        "error": str(exc),
                        "stage": exc.stage,
                    }

            child_kind, child_input, child_params, provider, _ = _build_child_job(
                route=route,
                question=question,
                params=dict(params or {}),
            )
            if child_kind in {"chatgpt_web.ask", "gemini_web.ask", "qwen_web.ask"}:
                validate_ask_preset(kind=child_kind, params_obj=child_params)

            idem = f"advisor-orchestrate:{run_id}:{step_id}:a1"
            with connect(self._cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                run = advisor_runs.get_run(conn, run_id=run_id)
                if run is None:
                    advisor_runs.create_run(
                        conn,
                        run_id=run_id,
                        request_id=(request_id or None),
                        mode=mode,
                        status="PLAN_COMPILED",
                        route=route,
                        raw_question=raw_question,
                        normalized_question=question,
                        context=context,
                        quality_threshold=quality_threshold,
                        crosscheck=crosscheck,
                        max_retries=max_retries,
                        orchestrate_job_id=job_id,
                    )
                    advisor_runs.append_event(
                        conn,
                        run_id=run_id,
                        type="run.created",
                        correlation_id=corr_id,
                        payload={"run_id": run_id, "mode": mode, "route": route},
                    )
                    advisor_runs.append_event(
                        conn,
                        run_id=run_id,
                        type="run.planned",
                        correlation_id=corr_id,
                        payload={
                            "run_id": run_id,
                            "orchestrate_job_id": job_id,
                            "quality_threshold": quality_threshold,
                            "crosscheck": crosscheck,
                            "openclaw_trace": openclaw_trace,
                        },
                    )
                else:
                    advisor_runs.update_run(
                        conn,
                        run_id=run_id,
                        mode=mode,
                        route=route,
                        normalized_question=question,
                        quality_threshold=quality_threshold,
                        crosscheck=crosscheck,
                        max_retries=max_retries,
                        orchestrate_job_id=job_id,
                    )

                advisor_runs.update_run(conn, run_id=run_id, status="DISPATCHING")
                advisor_runs.upsert_step(
                    conn,
                    run_id=run_id,
                    step_id=step_id,
                    step_type="ask",
                    status="LEASED",
                    attempt=1,
                    lease_id=lease_id,
                    lease_expires_at=lease_expires_at,
                    input_obj={
                        "kind": child_kind,
                        "input": child_input,
                        "params": child_params,
                        "openclaw": openclaw_trace,
                    },
                )
                advisor_runs.upsert_lease(
                    conn,
                    lease_id=lease_id,
                    run_id=run_id,
                    step_id=step_id,
                    owner=f"job:{job_id}",
                    token=lease_id,
                    status="leased",
                    expires_at=lease_expires_at,
                    heartbeat_at=now,
                )
                advisor_runs.append_event(
                    conn,
                    run_id=run_id,
                    step_id=step_id,
                    type="step.dispatched",
                    attempt=1,
                    correlation_id=corr_id,
                    idempotency_key=idem,
                    session_key=str((openclaw_trace or {}).get("session_key") or ""),
                    payload={
                        "step_id": step_id,
                        "attempt": 1,
                        "lease_id": lease_id,
                        "lease_expires_at": lease_expires_at,
                        "kind": child_kind,
                        "openclaw_trace": openclaw_trace,
                    },
                )
                if openclaw_trace:
                    advisor_runs.append_event(
                        conn,
                        run_id=run_id,
                        step_id=step_id,
                        type="step.heartbeat",
                        attempt=1,
                        correlation_id=corr_id,
                        idempotency_key=idem,
                        session_key=str((openclaw_trace or {}).get("session_key") or ""),
                        payload={
                            "source": "openclaw",
                            "status": dict((openclaw_trace or {}).get("status") or {}),
                        },
                    )

                child_job = create_job(
                    conn,
                    artifacts_dir=self._cfg.artifacts_dir,
                    idempotency_key=idem,
                    kind=child_kind,
                    input=child_input,
                    params=child_params,
                    max_attempts=self._cfg.max_attempts,
                    parent_job_id=job_id,
                    client={"name": "advisor_orchestrator"},
                    requested_by={
                        "transport": "advisor.orchestrate",
                        "received_at": float(time.time()),
                        "headers": {"x-request-id": request_id or f"advisor-orchestrate:{run_id}"},
                    },
                    allow_queue=False,
                    enforce_conversation_single_flight=True,
                )
                child_job_id = str(child_job.job_id)

                advisor_runs.upsert_step(
                    conn,
                    run_id=run_id,
                    step_id=step_id,
                    step_type="ask",
                    status="EXECUTING",
                    attempt=1,
                    job_id=child_job_id,
                    lease_id=lease_id,
                    lease_expires_at=lease_expires_at,
                    input_obj={
                        "kind": child_kind,
                        "input": child_input,
                        "params": child_params,
                    },
                    output_obj={"job_id": child_job_id},
                )
                advisor_runs.append_event(
                    conn,
                    run_id=run_id,
                    step_id=step_id,
                    type="step.started",
                    attempt=1,
                    correlation_id=corr_id,
                    idempotency_key=idem,
                    session_key=str((openclaw_trace or {}).get("session_key") or ""),
                    payload={
                        "step_id": step_id,
                        "attempt": 1,
                        "lease_id": lease_id,
                        "job_id": child_job_id,
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
                conn.commit()
        except (ConversationBusy, IdempotencyCollision, PresetValidationError, ValueError) as exc:
            fallback_action = "degraded"
            with connect(self._cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                advisor_runs.update_run(
                    conn,
                    run_id=run_id,
                    status="DEGRADED",
                    degraded=True,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                advisor_runs.upsert_step(
                    conn,
                    run_id=run_id,
                    step_id=step_id,
                    step_type="ask",
                    status="FAILED",
                    attempt=1,
                    job_id=child_job_id,
                    lease_id=lease_id,
                    lease_expires_at=lease_expires_at,
                    input_obj={"kind": child_kind, "question": question},
                    output_obj={"error_type": type(exc).__name__, "error": str(exc)},
                )
                advisor_runs.upsert_lease(
                    conn,
                    lease_id=lease_id,
                    run_id=run_id,
                    step_id=step_id,
                    owner=f"job:{job_id}",
                    token=lease_id,
                    status="released",
                    expires_at=lease_expires_at,
                    heartbeat_at=time.time(),
                )
                advisor_runs.append_event(
                    conn,
                    run_id=run_id,
                    step_id=step_id,
                    type="step.failed",
                    attempt=1,
                    correlation_id=corr_id,
                    session_key=str((openclaw_trace or {}).get("session_key") or ""),
                    payload={"step_id": step_id, "attempt": 1, "error_type": type(exc).__name__, "error": str(exc)},
                )
                advisor_runs.append_event(
                    conn,
                    run_id=run_id,
                    type="run.degraded",
                    correlation_id=corr_id,
                    payload={"reason_type": type(exc).__name__, "reason": str(exc), "fallback_action": fallback_action},
                )
                conn.commit()
            return ExecutorResult(
                status="completed",
                answer=f"advisor.orchestrate degraded: {type(exc).__name__}: {exc}",
                answer_format="text",
                meta={
                    "run_id": run_id,
                    "degraded": True,
                    "fallback_action": fallback_action,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )

        payload = {
            "ok": True,
            "run_id": run_id,
            "orchestrate_job_id": job_id,
            "child_job_id": child_job_id,
            "child_kind": child_kind,
            "route": route,
            "provider": provider,
            "quality_threshold": quality_threshold,
            "mode": mode,
            "crosscheck": crosscheck,
            "max_retries": max_retries,
        }
        return ExecutorResult(
            status="completed",
            answer=json.dumps(payload, ensure_ascii=False, indent=2),
            answer_format="text",
            meta=payload,
        )
