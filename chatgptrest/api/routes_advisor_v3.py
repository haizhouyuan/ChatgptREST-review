"""v3 Advisor Routes — FastAPI endpoints for OpenMind v3 LangGraph-based advisor.

Endpoints:
  POST /v2/advisor/advise     — Run the full advisor graph
  GET  /v2/advisor/trace/{id} — Retrieve a trace by ID
  POST /v2/advisor/webhook    — Feishu webhook handler
"""

from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import logging
import os
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from chatgptrest.api.write_guards import (
    enforce_client_name_allowlist as _enforce_client_name_allowlist,
    enforce_write_trace_headers as _enforce_write_trace_headers,
)
from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect
from chatgptrest.core.file_path_inputs import coerce_file_path_input
from chatgptrest.core.openmind_paths import (
    resolve_openmind_event_bus_db_path,
    resolve_openmind_kb_search_db_path,
)
from chatgptrest.core.idempotency import IdempotencyCollision
from chatgptrest.core.prompt_policy import PromptPolicyViolation, enforce_agent_ingress_prompt_policy
from chatgptrest.controller import ControllerEngine
from chatgptrest.evomap.paths import resolve_evomap_db_path
from chatgptrest.advisor.runtime import get_advisor_runtime_if_ready
from chatgptrest.advisor.scenario_packs import (
    apply_scenario_pack,
    resolve_scenario_pack,
    summarize_scenario_pack,
)
from chatgptrest.advisor.task_intake import TaskIntakeValidationError, build_task_intake_spec, summarize_task_intake

logger = logging.getLogger(__name__)


_ROUTE_TO_EXECUTION: dict[str, dict[str, str]] = {
    "kb_answer": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
    "quick_ask": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
    "clarify": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
    "hybrid": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
    "deep_research": {"provider": "chatgpt", "preset": "deep_research", "kind": "chatgpt_web.ask"},
    "report": {"provider": "chatgpt", "preset": "pro_extended", "kind": "chatgpt_web.ask"},
    "write_report": {"provider": "chatgpt", "preset": "pro_extended", "kind": "chatgpt_web.ask"},
    "funnel": {"provider": "chatgpt", "preset": "thinking_heavy", "kind": "chatgpt_web.ask"},
    "build_feature": {"provider": "chatgpt", "preset": "thinking_heavy", "kind": "chatgpt_web.ask"},
    "action": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
}


def _env_flag_enabled(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _kb_direct_synthesis_enabled() -> bool:
    """Guard optional KB direct answer synthesis.

    Direct KB hits are on the sync /v2/advisor/advise hot path. If synthesis
    falls through to slow external LLM chains, a single request can block the
    worker long enough to stall unrelated requests. Keep synthesis opt-in and
    return the raw KB answer by default.
    """
    return _env_flag_enabled("OPENMIND_KB_DIRECT_SYNTHESIS", default=False)


def _kb_direct_completion_allowed(state: dict[str, Any]) -> bool:
    """Allow sync KB completion only for simple factual asks."""
    if str(state.get("selected_route", "") or "") != "kb_answer":
        return False
    if str(state.get("intent_top", "") or "") != "QUICK_QUESTION":
        return False
    if bool(state.get("multi_intent", False)):
        return False
    if bool(state.get("action_required", False)):
        return False
    if bool(state.get("verification_need", False)):
        return False
    print(f"DEBUG _kb_direct_completion_allowed step_count_est={state.get('step_count_est')} multi_intent={state.get('multi_intent')} action_required={state.get('action_required')} answerability={state.get('kb_answerability')}")
    if int(state.get("step_count_est", 1) or 1) > 1:
        return False
    if int(state.get("constraint_count", 0) or 0) > 0:
        return False
    return float(state.get("kb_answerability", 0.0) or 0.0) >= 0.85


def _openmind_kb_search_db_path() -> str:
    return resolve_openmind_kb_search_db_path()


def _openmind_event_bus_db_path() -> str:
    return resolve_openmind_event_bus_db_path()


def _stable_json_hash(payload: Any) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8", errors="replace")).hexdigest()


_VOLATILE_IDEMPOTENCY_CONTEXT_KEYS = {
    "agent_id",
    "request_id",
    "session_key",
    "span_id",
    "timestamp",
    "trace_id",
    "ts",
}


def _sanitize_idempotency_context(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            key_str = str(key or "").strip().lower()
            if key_str in _VOLATILE_IDEMPOTENCY_CONTEXT_KEYS:
                continue
            sanitized[str(key)] = _sanitize_idempotency_context(value)
        return sanitized
    if isinstance(payload, list):
        return [_sanitize_idempotency_context(value) for value in payload]
    return payload


def _advisor_ask_request_fingerprint(
    *,
    question: str,
    intent_hint: str,
    role_id: str,
    user_id: str,
    session_id: str,
    context: dict[str, Any],
) -> str:
    return _stable_json_hash(
        {
            "question": str(question or ""),
            "intent_hint": str(intent_hint or ""),
            "role_id": str(role_id or ""),
            "user_id": str(user_id or ""),
            "session_id": str(session_id or ""),
            # Auto-generated idempotency should survive volatile trace/session
            # decorations added by clients, while still distinguishing stable
            # business context such as incident ids.
            "context": _sanitize_idempotency_context(dict(context or {})),
        }
    )


def _advisor_ask_auto_idempotency_key(
    *,
    question: str,
    intent_hint: str,
    role_id: str,
    user_id: str,
    session_id: str,
    context: dict[str, Any],
) -> str:
    fingerprint = _advisor_ask_request_fingerprint(
        question=question,
        intent_hint=intent_hint,
        role_id=role_id,
        user_id=user_id,
        session_id=session_id,
        context=context,
    )
    return f"advisor-ask:{fingerprint[:24]}:{int(time.time()) // 60}"


def _advisor_ask_recent_duplicate_window_seconds() -> int:
    return _clamp_int(
        os.environ.get("CHATGPTREST_ADVISOR_ASK_RECENT_DUPLICATE_WINDOW_SECONDS", 21600),
        default=21600,
        minimum=0,
        maximum=86400 * 7,
    )


def _advisor_ask_recent_duplicate_reuse_enabled() -> bool:
    return _env_flag_enabled("CHATGPTREST_ADVISOR_ASK_RECENT_DUPLICATE_REUSE", default=True)


def _advisor_ask_legacy_request_fingerprint(*, question: str, session_id: str) -> str:
    prefix = str(question or "")[:4]
    if not prefix:
        return ""
    return f"{str(session_id or '')}:{prefix}"


def _advisor_kind_provider(kind: str) -> str:
    raw = str(kind or "").strip().lower()
    if raw == "chatgpt_web.ask":
        return "chatgpt"
    if raw == "gemini_web.ask":
        return "gemini"
    return ""


def _json_obj(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _resolve_artifact_path(*, artifacts_dir: Path, raw_path: str) -> Path | None:
    value = str(raw_path or "").strip()
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return artifacts_dir / value


def _read_answer_if_available(*, artifacts_dir: Path, answer_path: str, max_chars: int = 24000) -> str | None:
    resolved = _resolve_artifact_path(artifacts_dir=artifacts_dir, raw_path=answer_path)
    if resolved is None or not resolved.exists() or not resolved.is_file():
        return None
    try:
        return resolved.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception:
        return None


def _find_recent_advisor_ask_duplicate(
    *,
    request_fingerprint: str,
    question: str,
    intent_hint: str,
    session_id: str,
    user_id: str,
    role_id: str,
) -> dict[str, Any] | None:
    def _query_duplicate_row(*, fingerprint_value: str) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT
              job_id,
              kind,
              status,
              phase,
              created_at,
              updated_at,
              conversation_url,
              answer_path,
              client_json,
              params_json
            FROM jobs
            WHERE json_extract(client_json, '$.name') = 'advisor_ask'
              AND coalesce(json_extract(client_json, '$.session_id'), '') = ?
              AND coalesce(json_extract(client_json, '$.user_id'), '') = ?
              AND coalesce(json_extract(client_json, '$.role_id'), '') = ?
              AND created_at >= ?
              AND status NOT IN ('error', 'canceled')
              AND json_extract(client_json, '$.request_fingerprint') = ?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """,
            (
                str(session_id or ""),
                str(user_id or ""),
                str(role_id or ""),
                cutoff,
                str(fingerprint_value or ""),
            ),
        ).fetchone()

    if not _advisor_ask_recent_duplicate_reuse_enabled():
        return None
    fingerprint = str(request_fingerprint or "").strip()[:32]
    if not fingerprint:
        return None
    window_seconds = _advisor_ask_recent_duplicate_window_seconds()
    if window_seconds <= 0:
        return None
    cfg = load_config()
    cutoff = float(time.time()) - float(window_seconds)
    with connect(cfg.db_path) as conn:
        row = _query_duplicate_row(fingerprint_value=fingerprint)
        if row is None:
            legacy_fingerprint = _advisor_ask_legacy_request_fingerprint(
                question=question,
                session_id=session_id,
            )
            if legacy_fingerprint:
                row = _query_duplicate_row(fingerprint_value=legacy_fingerprint)
    if row is None:
        return None
    payload = dict(row)
    payload["client_obj"] = _json_obj(payload.get("client_json"))
    payload["params_obj"] = _json_obj(payload.get("params_json"))
    payload["provider"] = _advisor_kind_provider(str(payload.get("kind") or ""))
    payload["answer"] = _read_answer_if_available(
        artifacts_dir=cfg.artifacts_dir,
        answer_path=str(payload.get("answer_path") or ""),
    )
    return payload


def _build_recent_advisor_ask_duplicate_response(
    *,
    trace_id: str,
    request_metadata: dict[str, Any],
    degradation: list[dict[str, Any]],
    duplicate_job: dict[str, Any],
) -> dict[str, Any]:
    client_obj = dict(duplicate_job.get("client_obj") or {})
    params_obj = dict(duplicate_job.get("params_obj") or {})
    status = str(duplicate_job.get("status") or "").strip().lower() or "submitted"
    duplicate_reason = "recent_request_fingerprint_reused"
    return {
        "ok": True,
        "trace_id": trace_id,
        "run_id": str(client_obj.get("run_id") or ""),
        "job_id": str(duplicate_job.get("job_id") or ""),
        "route": str(client_obj.get("route") or ""),
        "route_rationale": "reused recent advisor_ask request with matching request_fingerprint",
        "role_id": str(client_obj.get("role_id") or ""),
        "provider": str(duplicate_job.get("provider") or ""),
        "preset": str(params_obj.get("preset") or ""),
        "kb_used": False,
        "kb_hit_count": 0,
        "status": status,
        "answer": duplicate_job.get("answer"),
        "conversation_url": str(duplicate_job.get("conversation_url") or "") or None,
        "routing_ms": 0.0,
        "total_ms": 0.0,
        "request_metadata": dict(request_metadata or {}),
        "degradation": list(degradation or [])
        + [
            {
                "component": "advisor_ask",
                "status": "deduplicated",
                "reason": duplicate_reason,
                "existing_job_id": str(duplicate_job.get("job_id") or ""),
                "existing_run_id": str(client_obj.get("run_id") or ""),
            }
        ],
        "controller_status": "DUPLICATE_REUSED",
        "duplicate_reused": True,
        "duplicate_reason": duplicate_reason,
        "existing_job_id": str(duplicate_job.get("job_id") or ""),
        "existing_run_id": str(client_obj.get("run_id") or ""),
        "existing_trace_id": str(client_obj.get("trace_id") or ""),
        "existing_status": status,
        "existing_phase": str(duplicate_job.get("phase") or ""),
    }


def _clamp_int(raw: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _advisor_request_metadata(
    *,
    trace_id: str,
    session_id: str,
    account_id: str,
    thread_id: str,
    agent_id: str,
    role_id: str,
    user_id: str,
    intent_hint: str = "",
    idempotency_key: str = "",
    request_fingerprint: str = "",
    timeout_seconds: int | None = None,
    max_retries: int | None = None,
    quality_threshold: int | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "trace_id": str(trace_id or ""),
        "session_id": str(session_id or ""),
        "account_id": str(account_id or ""),
        "thread_id": str(thread_id or ""),
        "agent_id": str(agent_id or ""),
        "role_id": str(role_id or ""),
        "user_id": str(user_id or ""),
        "intent_hint": str(intent_hint or ""),
    }
    if idempotency_key:
        metadata["idempotency_key"] = str(idempotency_key)
    if request_fingerprint:
        metadata["request_fingerprint"] = str(request_fingerprint)
    if timeout_seconds is not None:
        metadata["timeout_seconds"] = int(timeout_seconds)
    if max_retries is not None:
        metadata["max_retries"] = int(max_retries)
    if quality_threshold is not None:
        metadata["quality_threshold"] = int(quality_threshold)
    return metadata


def _merge_advisor_entry_context(
    *,
    context: dict[str, Any],
    file_paths: list[str] | None,
    auto_context: bool,
    auto_context_top_k: int,
) -> dict[str, Any]:
    merged = dict(context or {})
    if file_paths:
        merged["files"] = list(file_paths)
    merged["advisor_auto_context"] = bool(auto_context)
    merged["advisor_auto_context_top_k"] = int(auto_context_top_k)
    return merged


def _merge_request_metadata(
    base: dict[str, Any],
    *,
    trace_id: str = "",
) -> dict[str, Any]:
    merged = dict(base or {})
    actual_trace_id = str(trace_id or "").strip()
    if actual_trace_id and not str(merged.get("trace_id", "")).strip():
        merged["trace_id"] = actual_trace_id
    return merged


def _llm_subsystem_status(state: dict[str, Any]) -> dict[str, Any]:
    llm = state.get("llm")
    if llm is None:
        return {"status": "not_initialized"}
    if getattr(llm, "_mock_fn", None) is not None:
        return {
            "status": "mock",
            "mode": "kb_only_stub",
            "reason": "live_llm_backend_not_configured",
        }
    return {"status": "ok", "mode": "live"}


def _routing_subsystem_status(state: dict[str, Any]) -> dict[str, Any]:
    routing_fabric = state.get("routing_fabric")
    circuit_breaker = state.get("circuit_breaker")
    return {
        "status": "ok" if routing_fabric else "not_initialized",
        "routing_fabric": bool(routing_fabric),
        "circuit_breaker": bool(circuit_breaker),
    }


def _runtime_degradation(state: dict[str, Any]) -> list[dict[str, Any]]:
    degradation: list[dict[str, Any]] = []
    llm_status = _llm_subsystem_status(state)
    if llm_status.get("status") == "mock":
        degradation.append(
            {
                "component": "llm",
                "status": "mock",
                "reason": llm_status.get("reason", "mock connector active"),
                "mode": llm_status.get("mode", "mock"),
            }
        )
    return degradation


def make_v3_advisor_router() -> APIRouter:
    """Create the v3 advisor FastAPI router.

    Wires up the LangGraph-based Advisor with:
    - Real LLMConnector (using ChatgptREST /v1/jobs API)
    - Feishu handler with security
    - Effects Outbox
    - EvoMap observer
    """
    # ── Auth Guard (applied to ALL endpoints) ─────────────────────
    _api_key = os.environ.get("OPENMIND_API_KEY", "")
    _auth_mode = os.environ.get("OPENMIND_AUTH_MODE", "strict")  # "open" or "strict"

    # ── R7: Shared Rate Limiter (all non-health, non-webhook endpoints) ────
    _rate_limits: dict[str, list[float]] = {}
    _rate_window = 60.0  # seconds
    _rate_max = int(os.environ.get("OPENMIND_RATE_LIMIT", "10"))

    def _check_rate_limit(client_ip: str) -> bool:
        import time

        now = time.time()
        window = _rate_limits.get(client_ip, [])
        window = [t for t in window if now - t < _rate_window]
        if len(window) >= _rate_max:
            return False
        window.append(now)
        _rate_limits[client_ip] = window
        return True

    async def _require_openmind_auth(request: Request) -> None:
        """#57 fix: Shared auth guard for all /v2/advisor/* endpoints.

        In 'strict' mode (default), ALL requests must provide a valid API key.
        In 'open' mode, auth is not enforced.
        /health endpoint is exempted for monitoring.
        """
        # Exempt /health for monitoring probes
        if request.url.path.endswith("/health"):
            return
        # Exempt webhook challenge verification (Feishu handshake)
        if request.url.path.endswith("/webhook") and request.method == "POST":
            # Challenge is validated inside FeishuHandler, not here
            return

        if _api_key:
            provided = request.headers.get("X-Api-Key", "")
            if provided != _api_key:
                raise HTTPException(status_code=401, detail="Invalid or missing API key")
        elif _auth_mode == "strict":
            raise HTTPException(status_code=503, detail="API key not configured but AUTH_MODE=strict")

    async def _require_openmind_rate_limit(request: Request) -> None:
        if request.url.path.endswith("/health"):
            return
        if request.url.path.endswith("/webhook") and request.method == "POST":
            return
        from chatgptrest.api.client_ip import get_client_ip

        client_ip = get_client_ip(request)
        if not _check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429,
                detail={"error": "Rate limit exceeded", "limit": f"{_rate_max} req/{int(_rate_window)}s"},
            )

    def _control_plane_key() -> str:
        return str(os.environ.get("OPENMIND_CONTROL_API_KEY") or "").strip()

    def _is_loopback_ip(value: str) -> bool:
        try:
            return ipaddress.ip_address(str(value or "").strip()).is_loopback
        except ValueError:
            return False

    async def _require_cc_control_access(request: Request) -> None:
        from chatgptrest.api.client_ip import get_client_ip

        control_key = _control_plane_key()
        provided = str(request.headers.get("X-Control-Api-Key") or "").strip()
        if control_key:
            if provided != control_key:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "cc_control_requires_control_key",
                        "detail": "cc control routes require X-Control-Api-Key",
                    },
                )
            return
        client_ip = get_client_ip(request)
        if _is_loopback_ip(client_ip):
            return
        raise HTTPException(
            status_code=403,
            detail={
                "error": "cc_control_requires_loopback",
                "detail": "cc control routes are loopback-only unless OPENMIND_CONTROL_API_KEY is configured",
                "client_ip": client_ip,
            },
        )

    def _init_scorecard_store(evo_db: str):
        """Create TeamScorecardStore using same EvoMap DB path."""
        try:
            from chatgptrest.evomap.team_scorecard import TeamScorecardStore
            store = TeamScorecardStore(db_path=evo_db)
            logger.info("TeamScorecardStore initialized (%s)", evo_db)
            return store
        except Exception as e:
            logger.warning("TeamScorecardStore init failed: %s", e)
            return None

    def _init_team_policy(evo_db: str):
        """Create TeamPolicy backed by a TeamScorecardStore."""
        try:
            from chatgptrest.evomap.team_scorecard import TeamScorecardStore
            from chatgptrest.kernel.team_policy import TeamPolicy
            store = TeamScorecardStore(db_path=evo_db)
            policy = TeamPolicy(scorecard_store=store)
            logger.info("TeamPolicy initialized")
            return policy
        except Exception as e:
            logger.warning("TeamPolicy init failed: %s", e)
            return None

    router = APIRouter(
        prefix="/v2/advisor",
        tags=["advisor-v3"],
        dependencies=[Depends(_require_openmind_auth), Depends(_require_openmind_rate_limit)],
    )
    cc_control_dependencies = [Depends(_require_cc_control_access)]

    def _publish_runtime_to_app(app: Any, state: dict[str, Any]) -> None:
        """Expose shared EvoMap runtime objects for cross-router reuse."""
        app.state.evomap_observer = state.get("observer")
        app.state.event_bus = state.get("event_bus")
        app.state.evomap_knowledge_db = state.get("evomap_knowledge_db")
        app.state.circuit_breaker = state.get("circuit_breaker")
        app.state.kb_scorer = state.get("kb_scorer")
        app.state.gate_tuner = state.get("gate_tuner")
        app.state.team_control_plane = state.get("team_control_plane")
        app.state._evomap_registered = True

    def _emit_runtime_event(
        state: dict[str, Any],
        *,
        event_type: str,
        source: str,
        trace_id: str,
        data: dict[str, Any],
    ) -> None:
        """Emit an advisor runtime event through EventBus with observer fallback."""
        bus = state.get("event_bus")
        if bus is not None:
            try:
                from chatgptrest.kernel.event_bus import TraceEvent

                bus.emit(
                    TraceEvent.create(
                        source=source,
                        event_type=event_type,
                        trace_id=trace_id,
                        data=data,
                    )
                )
                return
            except Exception as e:
                logger.debug("runtime EventBus emit failed for %s: %s", event_type, e)

        obs = state.get("observer")
        if obs is None:
            return
        try:
            obs.record_event(
                trace_id=trace_id,
                signal_type=event_type,
                source=source,
                domain="routing",
                data=data,
            )
        except Exception:
            logger.debug("observer fallback emit failed for %s", event_type, exc_info=True)

    def _init_once() -> dict[str, Any]:
        from chatgptrest.advisor.runtime import get_advisor_runtime

        return get_advisor_runtime()

    def _bind_role(role_id: str):
        role_name = str(role_id or "").strip()
        if not role_name:
            return nullcontext(None)
        from chatgptrest.kernel.role_context import with_role
        from chatgptrest.kernel.role_loader import get_role

        role = get_role(role_name)
        if role is None:
            raise HTTPException(status_code=400, detail={"error": "invalid_role_id", "role_id": role_name})
        return with_role(role)

    @router.post("/advise")
    async def advise(request: Request, body: dict = Body(...)):
        """Run the advisor graph on a user message."""
        state = _init_once()

        if not getattr(request.app.state, "_evomap_registered", False):
            _publish_runtime_to_app(request.app, state)

        api = state["api"]
        msg = body.get("message", "")
        role_id = str(body.get("role_id", "")).strip()
        session_id = str(body.get("session_id", "")).strip()
        account_id = str(body.get("account_id", "")).strip()
        thread_id = str(body.get("thread_id", "")).strip()
        agent_id = str(body.get("agent_id", "")).strip()
        context = dict(body.get("context", {}) or {})
        trace_id = str(body.get("trace_id", "")).strip()
        user_id = str(body.get("user_id", "")).strip() or account_id or "api"
        try:
            task_intake = build_task_intake_spec(
                ingress_lane="advisor_advise_v2",
                default_source="rest",
                raw_source=str(body.get("source", "")).strip(),
                raw_task_intake=body.get("task_intake") if isinstance(body.get("task_intake"), dict) else None,
                message=msg,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                account_id=account_id,
                thread_id=thread_id,
                agent_id=agent_id,
                role_id=role_id,
                context=context,
                attachments=[],
                client_name=str(request.headers.get("X-Client-Name", "")).strip(),
            )
        except TaskIntakeValidationError as exc:
            return JSONResponse(status_code=400, content={"ok": False, **exc.detail})
        scenario_pack = resolve_scenario_pack(task_intake, context=context)
        if scenario_pack is not None:
            task_intake = apply_scenario_pack(task_intake, scenario_pack)
            context["scenario_pack"] = scenario_pack.to_dict()
        context["task_intake"] = task_intake.to_dict()
        request_metadata = _advisor_request_metadata(
            trace_id=trace_id,
            session_id=session_id,
            account_id=account_id,
            thread_id=thread_id,
            agent_id=agent_id,
            role_id=role_id,
            user_id=user_id,
        )
        request_metadata["task_intake"] = summarize_task_intake(task_intake)
        if scenario_pack is not None:
            request_metadata["scenario_pack"] = summarize_scenario_pack(scenario_pack)
        degradation = _runtime_degradation(state)

        # Start Langfuse request trace
        lf_trace = None
        try:
            from chatgptrest.observability import start_request_trace
            lf_trace = start_request_trace(
                name="advisor",
                user_id=user_id,
                session_id=session_id,
                tags=["openmind", "advisor"],
                metadata={"message_len": len(msg)},
            )
        except Exception as e:
            logger.warning("Langfuse trace start failed: %s", e)

        try:
            def _run_advise() -> Any:
                controller = ControllerEngine(state)
                with _bind_role(role_id):
                    return controller.advise(
                        message=msg,
                        trace_id=trace_id or "",
                        request_metadata=request_metadata,
                        degradation=degradation,
                        role_id=role_id,
                        session_id=session_id,
                        account_id=account_id,
                        thread_id=thread_id,
                        agent_id=agent_id,
                        user_id=user_id,
                        context=context,
                    )

            result = await run_in_threadpool(_run_advise)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Advisor graph error: %s", e, exc_info=True)
            if lf_trace:
                try:
                    lf_trace.update(metadata={"error": str(e)})
                    lf_trace.end()
                except Exception:
                    pass
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "error": str(e)[:500],
                    "error_type": type(e).__name__,
                    "hint": "Check server logs for full traceback",
                    "request_metadata": request_metadata,
                    "degradation": degradation,
                },
            )

        # End trace with route info
        if lf_trace:
            try:
                lf_trace.update(
                    metadata={
                        "intent": result.get("intent_top", ""),
                        "route": result.get("selected_route", ""),
                        "kb_has_answer": result.get("kb_has_answer", False),
                    },
                )
                lf_trace.end()
            except Exception as e:
                logger.warning("Langfuse trace end failed: %s", e)

        if isinstance(result, dict):
            payload = dict(result)
            effective_request_metadata = _merge_request_metadata(
                request_metadata,
                trace_id=str(payload.get("trace_id", "")).strip(),
            )
            payload.setdefault("request_metadata", effective_request_metadata)
            payload.setdefault("degradation", degradation)
            return payload
        return result

    @router.get("/trace/{trace_id}")
    async def get_trace(trace_id: str, request: Request):
        """Retrieve a trace by ID."""
        # Auth handled by router-level _require_openmind_auth dependency
        state = _init_once()
        api = state["api"]
        trace = api.get_trace(trace_id) if hasattr(api, "get_trace") else None
        if trace is None:
            controller = ControllerEngine(state)
            trace = await run_in_threadpool(controller.get_trace_snapshot, trace_id=trace_id)
        if trace is None:
            return JSONResponse(status_code=404, content={"error": "trace_not_found"})
        return trace

    @router.get("/run/{run_id}")
    async def get_run(run_id: str, request: Request):
        """Retrieve the durable controller run snapshot."""
        state = _init_once()
        controller = ControllerEngine(state)
        snapshot = await run_in_threadpool(controller.get_run_snapshot, run_id=run_id)
        if snapshot is None:
            return JSONResponse(status_code=404, content={"error": "run_not_found"})
        return snapshot

    # P1-fix #36: Removed duplicate GET /traces here — kept the Langfuse-enriched
    # version below (originally at ~line 560).

    @router.post("/webhook")
    async def webhook(request: Request):
        """Handle Feishu webhook."""
        state = _init_once()
        feishu = state["feishu"]
        raw_body = await request.body()
        payload = await request.json()
        headers = {k: v for k, v in request.headers.items()}
        result = feishu.handle_webhook(payload, raw_body=raw_body, headers=headers)
        return result

    @router.get("/health")
    async def health():
        """P1-4: Enhanced health check with sub-system status."""
        subsystems = {}
        try:
            state = get_advisor_runtime_if_ready()
            if state is None:
                return {
                    "status": "not_initialized",
                    "version": "v3",
                    "subsystems": {
                        "kb": {"status": "not_initialized"},
                        "llm": {"status": "not_initialized"},
                        "memory": {"status": "not_initialized"},
                        "langfuse": {"status": "unknown"},
                        "event_bus": {"status": "not_initialized"},
                        "routing": {"status": "not_initialized", "routing_fabric": False, "circuit_breaker": False},
                        "auth": {"mode": _auth_mode, "key_set": bool(_api_key)},
                    },
                }
            # KB status
            kb = state.get("kb_hub")
            if kb:
                try:
                    import sqlite3 as _sql3
                    conn = _sql3.connect(_openmind_kb_search_db_path())
                    fts_count = conn.execute("SELECT count(*) FROM kb_fts_meta").fetchone()[0]
                    conn.close()
                    subsystems["kb"] = {"status": "ok", "fts_docs": fts_count}
                except Exception:
                    subsystems["kb"] = {"status": "ok", "fts_docs": "unknown"}
            else:
                subsystems["kb"] = {"status": "not_initialized"}

            subsystems["llm"] = _llm_subsystem_status(state)

            # Memory status
            mem = state.get("memory")
            if mem:
                try:
                    records = mem.count_total()
                    subsystems["memory"] = {"status": "ok", "records": records}
                except Exception:
                    subsystems["memory"] = {"status": "ok"}
            else:
                subsystems["memory"] = {"status": "not_initialized"}

            # Langfuse status
            try:
                from chatgptrest.observability import get_langfuse
                lf = get_langfuse()
                subsystems["langfuse"] = {"status": "ok" if lf else "disabled"}
            except Exception:
                subsystems["langfuse"] = {"status": "error"}

            # EventBus status
            eb = state.get("event_bus")
            subsystems["event_bus"] = {"status": "ok" if eb else "not_initialized"}
            subsystems["routing"] = _routing_subsystem_status(state)

            # Auth mode
            subsystems["auth"] = {"mode": _auth_mode, "key_set": bool(_api_key)}

        except Exception as e:
            return {"status": "degraded", "version": "v3", "error": str(e)}
        degradation = _runtime_degradation(state)
        status = "degraded" if degradation else "ok"
        return {"status": status, "version": "v3", "subsystems": subsystems, "degradation": degradation}

    @router.get("/evomap/signals")
    async def evomap_signals(trace_id: str = "", limit: int = 50):
        """Query EvoMap signals — JSON API."""
        state = _init_once()
        obs = state.get("observer")
        if not obs:
            return {"signals": [], "error": "observer not initialized"}
        sigs = obs.query(trace_id=trace_id, limit=limit)
        return {"signals": [s.to_dict() for s in sigs], "count": len(sigs)}

    @router.get("/evomap/stats")
    async def evomap_stats():
        """EvoMap aggregate stats."""
        state = _init_once()
        obs = state.get("observer")
        if not obs:
            return {"error": "observer not initialized"}
        return {
            "by_type": obs.aggregate_by_type(),
            "by_domain": obs.aggregate_by_domain(),
            "total": obs.count(),
        }

    @router.get("/kb/artifacts")
    async def kb_artifacts(limit: int = 20):
        """List KB artifacts."""
        state = _init_once()
        try:
            import sqlite3, json
            kb_db = os.environ.get("OPENMIND_KB_DB",
                                   os.path.expanduser("~/.openmind/kb_registry.db"))
            conn = sqlite3.connect(kb_db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT artifact_id, source_system, para_bucket, structural_role, "
                "source_path, content_type, file_size, created_at "
                "FROM artifacts ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            conn.close()
            return {"artifacts": [dict(r) for r in rows], "count": len(rows)}
        except Exception as e:
            return {"error": str(e)}

    @router.get("/dashboard")
    async def dashboard():
        """Pipeline flow dashboard — HTML."""
        from fastapi.responses import HTMLResponse
        state = _init_once()
        obs = state.get("observer")

        # Gather data
        signals = obs.query(limit=200) if obs else []
        by_type = obs.aggregate_by_type() if obs else {}
        by_domain = obs.aggregate_by_domain() if obs else {}

        # Group signals by trace
        traces = {}
        for s in signals:
            tid = s.trace_id[:12] if s.trace_id else "unknown"
            traces.setdefault(tid, []).append(s)

        # Build HTML
        html = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><title>OpenMind Pipeline Dashboard</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', -apple-system, sans-serif; background: #0f1117; color: #e0e0e0; padding: 24px; }
h1 { color: #60a5fa; margin-bottom: 8px; font-size: 24px; }
h2 { color: #818cf8; margin: 24px 0 12px; font-size: 18px; }
.subtitle { color: #888; margin-bottom: 24px; }
.stats { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
.stat-card { background: linear-gradient(135deg, #1a1f2e, #252a3a); border: 1px solid #2d3348;
  border-radius: 12px; padding: 16px 20px; min-width: 140px; }
.stat-card .label { color: #888; font-size: 12px; text-transform: uppercase; }
.stat-card .value { color: #60a5fa; font-size: 28px; font-weight: 700; margin-top: 4px; }
.trace-card { background: #1a1f2e; border: 1px solid #2d3348; border-radius: 12px;
  padding: 16px; margin-bottom: 16px; }
.trace-id { font-family: monospace; color: #fbbf24; font-size: 13px; }
.pipeline-flow { display: flex; align-items: center; gap: 0; flex-wrap: wrap; margin: 12px 0; }
.stage { padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.stage.routing { background: #1e3a5f; color: #60a5fa; }
.stage.funnel { background: #1e3a4f; color: #34d399; }
.stage.gate { background: #2a1f3e; color: #a78bfa; }
.stage.dispatch { background: #3a2a1a; color: #fbbf24; }
.stage.kb { background: #1a3a2a; color: #4ade80; }
.stage.report { background: #3a1a2a; color: #f472b6; }
.arrow { color: #555; margin: 0 4px; }
.domain-bar { display: flex; gap: 8px; margin: 8px 0; }
.domain-tag { padding: 2px 8px; border-radius: 4px; font-size: 11px; }
table { width: 100%; border-collapse: collapse; margin: 16px 0; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #2d3348; font-size: 13px; }
th { color: #888; font-weight: 600; }
</style></head><body>
<h1>🔮 OpenMind Pipeline Dashboard</h1>
<p class="subtitle">Real-time LangGraph pipeline flow visualization</p>
"""

        # Stats cards
        total = sum(by_type.values()) if by_type else 0
        # P0-fix #23: html.escape all dynamic content to prevent stored XSS
        _esc = html.escape

        html += '<div class="stats">'
        html += f'<div class="stat-card"><div class="label">总信号</div><div class="value">{total}</div></div>'
        html += f'<div class="stat-card"><div class="label">活跃 Trace</div><div class="value">{len(traces)}</div></div>'
        for domain, cnt in sorted(by_domain.items(), key=lambda x: -x[1]):
            html += f'<div class="stat-card"><div class="label">{_esc(str(domain))}</div><div class="value">{cnt}</div></div>'
        html += '</div>'

        # Signal type breakdown
        html += '<h2>📊 Signal Types</h2><table><tr><th>Type</th><th>Count</th></tr>'
        for st, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
            html += f'<tr><td>{_esc(str(st))}</td><td>{cnt}</td></tr>'
        html += '</table>'

        # Per-trace pipeline flows
        html += '<h2>🔗 Pipeline Traces</h2>'
        for tid, sigs in sorted(traces.items(), key=lambda x: x[1][0].timestamp if x[1] else "", reverse=True):
            sigs.sort(key=lambda s: s.timestamp)
            html += f'<div class="trace-card"><span class="trace-id">{_esc(tid)}</span>'
            html += f' <span style="color:#666;font-size:12px">({len(sigs)} signals)</span>'
            html += '<div class="pipeline-flow">'
            for i, s in enumerate(sigs):
                domain_class = s.domain if s.domain in ('routing','funnel','gate','dispatch','kb','report') else 'routing'
                html += f'<span class="stage {_esc(domain_class)}">{_esc(s.signal_type)}</span>'
                if i < len(sigs) - 1:
                    html += '<span class="arrow">→</span>'
            html += '</div>'
            # Show data for each signal
            for s in sigs:
                data_str = ", ".join(f"{k}={v}" for k,v in (s.data or {}).items() if k != "trace_id")
                if data_str:
                    html += f'<div style="color:#666;font-size:11px;margin-left:8px">⤷ {_esc(s.signal_type)}: {_esc(data_str[:100])}</div>'
            html += '</div>'

        html += '</body></html>'
        return HTMLResponse(content=html)

    @router.get("/traces")
    async def get_traces(limit: int = 20):
        """Agent-readable trace summary from Langfuse.

        Returns structured JSON that agents can consume for self-monitoring:
        - Recent request routes, intents, KB usage
        - Latency breakdown per trace
        - Error patterns and failure rates
        - Model usage statistics
        """
        try:
            from chatgptrest.observability import get_langfuse
            lf = get_langfuse()
            if not lf:
                return {
                    "status": "disabled",
                    "hint": "Langfuse not configured. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY.",
                    "traces": [],
                }

            # Fetch recent traces via Langfuse API v3
            try:
                result = lf.api.trace.list(limit=limit)
                traces = result.data if hasattr(result, 'data') else (result if isinstance(result, list) else [])
            except Exception:
                traces = []
            summary = []
            route_counts = {}
            error_count = 0
            total_latency = 0
            latency_count = 0

            for t in traces:
                meta = t.metadata or {} if hasattr(t, 'metadata') else {}
                route = meta.get("route", "unknown")
                route_counts[route] = route_counts.get(route, 0) + 1

                entry = {
                    "trace_id": t.id if hasattr(t, 'id') else str(t),
                    "name": t.name if hasattr(t, 'name') else "",
                    "timestamp": str(t.timestamp) if hasattr(t, 'timestamp') else "",
                    "route": route,
                    "intent": meta.get("intent", ""),
                    "kb_has_answer": meta.get("kb_has_answer", None),
                    "error": meta.get("error", None),
                    "user_id": t.user_id if hasattr(t, 'user_id') else "",
                    "session_id": t.session_id if hasattr(t, 'session_id') else "",
                }
                if meta.get("error"):
                    error_count += 1
                # Calculate latency if available
                if hasattr(t, 'latency') and t.latency:
                    entry["latency_ms"] = int(t.latency * 1000)
                    total_latency += t.latency
                    latency_count += 1
                summary.append(entry)

            return {
                "status": "ok",
                "trace_count": len(summary),
                "route_distribution": route_counts,
                "error_rate": f"{error_count}/{len(summary)}" if summary else "0/0",
                "avg_latency_ms": int(total_latency / latency_count * 1000) if latency_count else None,
                "traces": summary,
                "hint": "Use this data for agent self-monitoring. Query /v2/advisor/traces?limit=N for more.",
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "traces": []}

    @router.get("/routing-stats")
    async def routing_stats(task_type: str = "default"):
        """Query RoutingFabric health/status for a task type."""
        state = _init_once()
        fabric = state.get("routing_fabric")
        if not fabric:
            return {"error": "RoutingFabric not initialized"}

        status = fabric.status()
        return {
            "task_type": task_type,
            "status": status,
        }

    @router.get("/insights")
    async def get_insights(hours: int = 1):
        """Agent-readable fusion of EvoMap signals + Langfuse traces.

        Combines business-layer signals (routing, KB, gates) with LLM-layer
        metrics (latency, errors, model usage) for agent self-monitoring.
        """
        import datetime
        state = _init_once()
        obs = state.get("observer")

        result = {
            "period": f"last_{hours}h",
            "timestamp": datetime.datetime.now().isoformat(),
        }

        # ── EvoMap signals ──
        if obs:
            all_sigs = obs.query(limit=500)
            cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)
            cutoff_str = cutoff.isoformat()
            recent = [s for s in all_sigs if s.timestamp >= cutoff_str]

            # Route distribution
            route_counts = {}
            for s in recent:
                if s.signal_type == "route_selected":
                    route = s.data.get("route", "unknown")
                    route_counts[route] = route_counts.get(route, 0) + 1
            result["route_distribution"] = route_counts
            result["request_count"] = sum(route_counts.values())

            # LLM stats from EvoMap signals
            llm_sigs = [s for s in recent if s.domain == "llm"]
            completed = [s for s in llm_sigs if s.signal_type == "llm.call_completed"]
            failed = [s for s in llm_sigs if s.signal_type == "llm.call_failed"]

            latencies = [s.data.get("latency_ms", 0) for s in completed if s.data.get("latency_ms")]
            model_usage = {}
            for s in completed:
                m = s.data.get("model", "unknown")
                model_usage[m] = model_usage.get(m, 0) + 1

            result["llm_stats"] = {
                "total_calls": len(completed) + len(failed),
                "success": len(completed),
                "failed": len(failed),
                "error_rate": f"{len(failed)}/{len(completed) + len(failed)}" if llm_sigs else "0/0",
                "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else None,
                "p95_latency_ms": int(sorted(latencies)[int(len(latencies) * 0.95)]) if len(latencies) > 1 else None,
                "model_usage": model_usage,
                "errors": [{"model": s.data.get("model"), "error": s.data.get("error")} for s in failed[-5:]],
            }

            # KB stats
            kb_sigs = [s for s in recent if s.domain == "kb"]
            result["kb_stats"] = {
                "search_hits": len([s for s in kb_sigs if s.signal_type == "kb.search_hit"]),
                "writebacks": len([s for s in kb_sigs if s.signal_type == "kb.writeback"]),
            }

            # Gate stats
            gate_passed = len([s for s in recent if s.signal_type == "gate.passed"])
            gate_failed = len([s for s in recent if s.signal_type == "gate.failed"])
            result["gate_stats"] = {"passed": gate_passed, "failed": gate_failed}

            # Anomaly detection
            anomalies = []
            for s in completed:
                lat = s.data.get("latency_ms", 0)
                if lat > 3000:
                    anomalies.append({
                        "type": "high_latency",
                        "model": s.data.get("model"),
                        "latency_ms": lat,
                        "threshold": 3000,
                    })
            if len(failed) >= 3:
                anomalies.append({
                    "type": "high_error_rate",
                    "failed_count": len(failed),
                    "total": len(llm_sigs),
                })
            result["anomalies"] = anomalies[:10]
            result["signal_count"] = len(recent)
        else:
            result["error"] = "EvoMap observer not initialized"

        # ── Langfuse trace count ──
        try:
            from chatgptrest.observability import get_langfuse
            lf = get_langfuse()
            result["langfuse"] = {"status": "ok" if lf else "disabled"}
        except Exception:
            result["langfuse"] = {"status": "error"}

        return result

    # ── CC Dispatch Endpoints ─────────────────────────────────────

    @router.post("/cc-dispatch", dependencies=cc_control_dependencies)
    async def cc_dispatch(request: Request):
        """Dispatch a task to a CC agent via CcExecutor.

        Body (all optional except task_type & description):
            task_type, description, files, timeout,
            model, fallback_model, max_turns, max_budget_usd,
            mcp_config, agents_json, json_schema, system_prompt,
            cwd, permission_mode, stateless, session_id, effort,
            allowed_tools, add_dirs
        """
        state = _init_once()
        cc = state.get("cc_native")
        if cc is None:
            return {"ok": False, "error": "CcNativeExecutor not initialized"}

        body = await request.json()
        from chatgptrest.kernel.cc_executor import CcTask

        task = CcTask(
            task_type=body.get("task_type", "code_review"),
            description=body.get("description", ""),
            files=body.get("files", []),
            context=body.get("context", {}),
            timeout=body.get("timeout", 300),
            
            # Headless parameters
            model=body.get("model", "sonnet"),
            fallback_model=body.get("fallback_model", ""),
            max_turns=body.get("max_turns", 25),
            max_budget_usd=body.get("max_budget_usd", 10.0),
            mcp_config=body.get("mcp_config"),
            agents_json=body.get("agents_json"),
            json_schema=body.get("json_schema"),
            system_prompt=body.get("system_prompt", ""),
            cwd=body.get("cwd", ""),
            permission_mode=body.get("permission_mode", "bypassPermissions"),
            stateless=body.get("stateless", True),
            session_id=body.get("session_id", ""),
            effort=body.get("effort", ""),
            allowed_tools=body.get("allowed_tools"),
            add_dirs=body.get("add_dirs", []),
        )

        template = body.get("template")

        # Use new async dispatch_headless directly
        result = await cc.dispatch_headless(task, template=template)

        return {
            "ok": result.ok,
            "agent": result.agent,
            "task_type": result.task_type,
            "elapsed_seconds": result.elapsed_seconds,
            "findings_count": result.findings_count,
            "files_modified": result.files_modified,
            "quality_score": result.quality_score,
            "template_used": result.template_used,
            "output_preview": result.output[:500] if result.output else "",
            "error": result.error,
            "trace_id": result.trace_id,
            "dispatch_mode": result.dispatch_mode,
            "session_id": result.session_id,
            "model_used": result.model_used,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": result.cost_usd,
            "num_turns": result.num_turns,
            "structured_output": result.structured_output,
        }

    from sse_starlette.sse import EventSourceResponse

    @router.post("/cc-dispatch-stream", dependencies=cc_control_dependencies)
    async def cc_dispatch_stream(request: Request):
        """Dispatch a headless CC task with real-time stream-json SSE."""
        state = _init_once()
        cc = state.get("cc_native")
        if cc is None:
            return {"ok": False, "error": "CcNativeExecutor not initialized"}

        body = await request.json()
        from chatgptrest.kernel.cc_executor import CcTask
        import asyncio
        import json

        task = CcTask(
            task_type=body.get("task_type", "code_review"),
            description=body.get("description", ""),
            files=body.get("files", []),
            context=body.get("context", {}),
            timeout=body.get("timeout", 600),
            model=body.get("model", "sonnet"),
            mcp_config=body.get("mcp_config"),
            agents_json=body.get("agents_json"),
            json_schema=body.get("json_schema"),
            stateless=body.get("stateless", True),
            session_id=body.get("session_id", ""),
        )

        queue = asyncio.Queue()

        def on_progress(evt):
            # Put event in queue without blocking
            try:
                queue.put_nowait(evt)
            except asyncio.QueueFull:
                pass

        async def _generator():
            # Start dispatch in a background task
            dispatch_task = asyncio.create_task(
                cc.dispatch_headless(task, progress_callback=on_progress)
            )

            while not dispatch_task.done() or not queue.empty():
                try:
                    # Wait for next event or 0.1s tick
                    evt = await asyncio.wait_for(queue.get(), timeout=0.1)
                    yield dict(data=json.dumps(evt))
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    yield dict(event="error", data=str(e))
                    break

            try:
                result = await dispatch_task
                final_state = {
                    "ok": result.ok, "agent": result.agent,
                    "elapsed_seconds": result.elapsed_seconds,
                    "quality_score": result.quality_score,
                    "session_id": result.session_id,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "cost_usd": result.cost_usd,
                    "error": result.error,
                    "structured_output": result.structured_output,
                }
                yield dict(event="done", data=json.dumps(final_state))
            except Exception as e:
                yield dict(event="error", data=str(e))

        return EventSourceResponse(_generator())

    @router.post("/cc-dispatch-conversation", dependencies=cc_control_dependencies)
    async def cc_dispatch_conversation(request: Request):
        """Dispatch a sequence of tasks as a continuous conversation."""
        state = _init_once()
        cc = state.get("cc_native")
        if cc is None:
            return {"ok": False, "error": "CcNativeExecutor not initialized"}

        body = await request.json()
        from chatgptrest.kernel.cc_executor import CcTask
        
        tasks_data = body.get("tasks", [])
        if not tasks_data:
            return {"ok": False, "error": "Missing 'tasks' list"}
            
        tasks = []
        for t in tasks_data:
            tasks.append(CcTask(
                task_type=t.get("task_type", "code_review"),
                description=t.get("description", ""),
                files=t.get("files", []),
                timeout=t.get("timeout", 300),
                model=t.get("model", "sonnet"),
                mcp_config=t.get("mcp_config"),
                stateless=t.get("stateless", False),
            ))
            
        results = await cc.dispatch_conversation(tasks)
        
        return {
            "ok": all(r.ok for r in results),
            "results": [
                {
                    "ok": r.ok,
                    "agent": r.agent,
                    "elapsed_seconds": r.elapsed_seconds,
                    "quality_score": r.quality_score,
                    "output_preview": r.output[:200] if r.output else "",
                    "session_id": r.session_id,
                    "error": r.error
                } for r in results
            ],
            "final_session_id": tasks[-1].session_id if tasks else "",
        }

    @router.post("/cc-dispatch-team", dependencies=cc_control_dependencies)
    async def cc_dispatch_team(request: Request):
        """Dispatch a task to a CC agent team.

        If no ``team`` is provided in the body, the system will consult
        the TeamPolicy to recommend a team based on scorecard history.
        """
        state = _init_once()
        cc = state.get("cc_native")
        if cc is None:
            return {"ok": False, "error": "CcNativeExecutor not initialized"}

        body = await request.json()
        from chatgptrest.kernel.cc_executor import CcTask
        from chatgptrest.kernel.team_types import TeamSpec

        task = CcTask(
            task_type=body.get("task_type", "architecture_review"),
            description=body.get("description", ""),
            files=body.get("files", []),
            timeout=body.get("timeout", 900),
            model=body.get("model", "sonnet"),
            mcp_config=body.get("mcp_config"),
            system_prompt=body.get("system_prompt", ""),
            cwd=body.get("cwd", ""),
            context={"repo": body.get("repo", ""), "team_request": True},
        )

        team_raw = body.get("team")
        topology_id = str(body.get("topology_id", "")).strip()
        team_spec = None
        if team_raw:
            team_spec = TeamSpec.from_dict(team_raw)
        elif cc._team_policy:
            # Policy-aware: auto-select team if none provided
            try:
                team_spec = cc._team_policy.recommend(
                    repo=body.get("repo", ""),
                    task_type=task.task_type,
                )
            except Exception as e:
                logger.debug("team policy recommendation failed: %s", e)
        topology = None
        control_plane = getattr(cc, "_team_control_plane", None)
        if control_plane is not None:
            try:
                team_spec, topology = control_plane.resolve_team_spec(
                    team=team_spec or team_raw,
                    topology_id=topology_id,
                    task_type=task.task_type,
                )
            except Exception as e:
                logger.debug("team control plane resolution failed: %s", e)

        result = await cc.dispatch_team(
            task, team=team_spec or team_raw,
        )

        return {
            "ok": result.ok,
            "agent": result.agent,
            "elapsed_seconds": result.elapsed_seconds,
            "quality_score": result.quality_score,
            "output_preview": result.output[:500] if result.output else "",
            "error": result.error,
            "cost_usd": result.cost_usd,
            "tools_used": result.tools_used,
            "files_read": result.files_read,
            "team_id": team_spec.team_id if team_spec else "",
            "team_roles": [r.name for r in team_spec.roles] if team_spec else [],
            "team_run_id": getattr(result, "team_run_id", ""),
            "team_digest": getattr(result, "team_digest", ""),
            "team_checkpoints": getattr(result, "team_checkpoints", []),
            "role_results": getattr(result, "role_results", {}),
            "topology_id": getattr(topology, "topology_id", topology_id or ""),
        }

    @router.get("/cc-team-topologies", dependencies=cc_control_dependencies)
    async def cc_team_topologies():
        """List configured team topologies and role catalog entries."""
        state = _init_once()
        cc = state.get("cc_native")
        if cc is None:
            return {"ok": False, "error": "CcNativeExecutor not initialized"}
        plane = getattr(cc, "_team_control_plane", None)
        if plane is None:
            return {"ok": True, "topologies": [], "roles": []}
        return {
            "ok": True,
            "topologies": [
                {
                    "topology_id": topology.topology_id,
                    "description": topology.description,
                    "roles": topology.role_ids,
                    "task_types": topology.task_types,
                    "execution_mode": topology.execution_mode,
                    "synthesis_role": topology.synthesis_role,
                    "gate_ids": topology.gate_ids,
                }
                for topology in plane.catalog.topologies.values()
            ],
            "roles": [
                {
                    "role_id": role.role_id,
                    "runtime": role.runtime,
                    "agent_type": role.agent_type,
                    "model": role.model,
                    "write_access": role.write_access,
                    "output_schema": role.output_schema,
                }
                for role in plane.catalog.roles.values()
            ],
        }

    @router.get("/cc-team-runs", dependencies=cc_control_dependencies)
    async def cc_team_runs(status: str = "", limit: int = 20):
        """List recent team control plane runs."""
        state = _init_once()
        cc = state.get("cc_native")
        if cc is None:
            return {"ok": False, "error": "CcNativeExecutor not initialized"}
        plane = getattr(cc, "_team_control_plane", None)
        if plane is None:
            return {"ok": True, "runs": []}
        return {"ok": True, "runs": plane.list_runs(status=status, limit=limit)}

    @router.get("/cc-team-runs/{team_run_id}", dependencies=cc_control_dependencies)
    async def cc_team_run_detail(team_run_id: str):
        """Fetch one team run with role and checkpoint state."""
        state = _init_once()
        cc = state.get("cc_native")
        if cc is None:
            return {"ok": False, "error": "CcNativeExecutor not initialized"}
        plane = getattr(cc, "_team_control_plane", None)
        if plane is None:
            return {"ok": False, "error": "team control plane unavailable"}
        payload = plane.get_run(team_run_id)
        if payload is None:
            raise HTTPException(status_code=404, detail={"error": "team_run_not_found", "team_run_id": team_run_id})
        return {"ok": True, "run": payload}

    @router.get("/cc-team-checkpoints", dependencies=cc_control_dependencies)
    async def cc_team_checkpoints(status: str = "pending", limit: int = 50):
        """List pending or resolved team checkpoints."""
        state = _init_once()
        cc = state.get("cc_native")
        if cc is None:
            return {"ok": False, "error": "CcNativeExecutor not initialized"}
        plane = getattr(cc, "_team_control_plane", None)
        if plane is None:
            return {"ok": True, "checkpoints": []}
        return {"ok": True, "checkpoints": plane.list_checkpoints(status=status, limit=limit)}

    @router.post("/cc-team-checkpoints/{checkpoint_id}/approve", dependencies=cc_control_dependencies)
    async def cc_team_checkpoint_approve(checkpoint_id: str, body: dict = Body(default={})):
        state = _init_once()
        cc = state.get("cc_native")
        if cc is None:
            return {"ok": False, "error": "CcNativeExecutor not initialized"}
        plane = getattr(cc, "_team_control_plane", None)
        if plane is None:
            return {"ok": False, "error": "team control plane unavailable"}
        payload = plane.approve_checkpoint(
            checkpoint_id,
            actor=str(body.get("actor", "controller") or "controller"),
            reason=str(body.get("reason", "") or ""),
        )
        if payload is None:
            raise HTTPException(status_code=404, detail={"error": "checkpoint_not_found", "checkpoint_id": checkpoint_id})
        return {"ok": True, "checkpoint": payload}

    @router.post("/cc-team-checkpoints/{checkpoint_id}/reject", dependencies=cc_control_dependencies)
    async def cc_team_checkpoint_reject(checkpoint_id: str, body: dict = Body(default={})):
        state = _init_once()
        cc = state.get("cc_native")
        if cc is None:
            return {"ok": False, "error": "CcNativeExecutor not initialized"}
        plane = getattr(cc, "_team_control_plane", None)
        if plane is None:
            return {"ok": False, "error": "team control plane unavailable"}
        payload = plane.reject_checkpoint(
            checkpoint_id,
            actor=str(body.get("actor", "controller") or "controller"),
            reason=str(body.get("reason", "") or ""),
        )
        if payload is None:
            raise HTTPException(status_code=404, detail={"error": "checkpoint_not_found", "checkpoint_id": checkpoint_id})
        return {"ok": True, "checkpoint": payload}

    @router.get("/cc-team-scores", dependencies=cc_control_dependencies)
    async def cc_team_scores(
        repo: str = "", task_type: str = "", limit: int = 10,
    ):
        """Query team scorecard rankings.

        Returns teams ranked by composite score for a repo/task combination.
        """
        state = _init_once()
        cc = state.get("cc_native")
        if cc is None:
            return {"ok": False, "error": "CcNativeExecutor not initialized"}

        store = getattr(cc, "_scorecard_store", None)
        if store is None:
            return {"ok": False, "error": "Team scorecard store not initialized"}

        scores = store.rank_teams(repo=repo, task_type=task_type, limit=limit)
        return {
            "ok": True,
            "repo": repo,
            "task_type": task_type,
            "teams": [
                {
                    "team_id": s.team_id,
                    "total_runs": s.total_runs,
                    "success_rate": round(s.success_rate, 3),
                    "avg_quality": round(s.avg_quality, 3),
                    "avg_latency_s": round(s.avg_latency_s, 1),
                    "composite_score": round(s.composite_score, 3),
                    "total_cost_usd": round(s.total_cost_usd, 4),
                    "last_run_at": s.last_run_at,
                }
                for s in scores
            ],
        }

    @router.get("/cc-health", dependencies=cc_control_dependencies)
    async def cc_health():
        """Check CC pipeline health: daemon, agents, zombies."""
        state = _init_once()
        cc = state.get("cc_executor")
        if cc is None:
            return {"ok": False, "error": "CcExecutor not initialized"}
        return cc.check_health()

    @router.get("/cc-agents", dependencies=cc_control_dependencies)
    async def cc_agents():
        """List CC agents with EvoMap capability profiles."""
        state = _init_once()
        cc = state.get("cc_executor")
        if cc is None:
            return {"ok": False, "error": "CcExecutor not initialized"}

        cc._refresh_profiles_from_evomap()
        agents = cc.list_agents()
        profiles = {}
        for name, profile in cc._agent_profiles.items():
            profiles[name] = {
                "capabilities": profile.capabilities,
                "total_tasks": profile.total_tasks,
                "success_rate": (
                    profile.total_successes / max(profile.total_tasks, 1)
                    if profile.total_tasks > 0 else 0.0
                ),
            }
        return {
            "agents": agents,
            "profiles": profiles,
        }

    # ── Phase 2/3: Eval, A/B Test, Stats, Templates ──────────────

    @router.post("/cc-eval", dependencies=cc_control_dependencies)
    async def cc_eval(request: Request):
        """Run batch evaluation of CC agents to accumulate EvoMap signals.

        Body (optional): scenarios[] (custom), agents[] (force specific)
        """
        state = _init_once()
        cc = state.get("cc_executor")
        if cc is None:
            return {"ok": False, "error": "CcExecutor not initialized"}

        from chatgptrest.kernel.cc_eval_runner import CcEvalRunner
        runner = CcEvalRunner(cc)

        body = {}
        try:
            body = await request.json()
        except Exception:
            pass

        import asyncio
        agents = body.get("agents")
        level = body.get("level")  # L1, L2, L3, L4
        results = await asyncio.get_event_loop().run_in_executor(
            None, runner.run_batch, None, level, agents,
        )

        return {
            "ok": True,
            "level": level or "all",
            "total": len(results),
            "passed": sum(1 for r in results if r.get("passed")),
            "results": results,
        }

    @router.post("/cc-ab-test", dependencies=cc_control_dependencies)
    async def cc_ab_test(request: Request):
        """A/B test prompt templates for a task type.

        Body: task_type, description?, files[]?, agents[]?
        """
        state = _init_once()
        cc = state.get("cc_executor")
        if cc is None:
            return {"ok": False, "error": "CcExecutor not initialized"}

        body = await request.json()
        from chatgptrest.kernel.cc_eval_runner import CcEvalRunner
        runner = CcEvalRunner(cc)

        import asyncio
        result = await asyncio.get_event_loop().run_in_executor(
            None, runner.run_ab_test,
            body.get("task_type", "code_review"),
            body.get("description", ""),
            body.get("files"),
            body.get("agents"),
        )

        return {
            "ok": True,
            "task_type": result.task_type,
            "winner": result.winner,
            "confidence": result.confidence,
            "variants": result.variants,
        }

    @router.get("/cc-stats", dependencies=cc_control_dependencies)
    async def cc_stats():
        """View accumulated CC pipeline performance data."""
        state = _init_once()
        cc = state.get("cc_executor")
        if cc is None:
            return {"ok": False, "error": "CcExecutor not initialized"}

        from chatgptrest.kernel.cc_eval_runner import CcEvalRunner
        runner = CcEvalRunner(cc)
        return runner.get_stats()

    @router.get("/cc-templates", dependencies=cc_control_dependencies)
    async def cc_templates():
        """View template performance + trigger evolution."""
        state = _init_once()
        cc = state.get("cc_executor")
        if cc is None:
            return {"ok": False, "error": "CcExecutor not initialized"}

        return {
            "templates": cc.get_template_report(),
            "evolution": cc.evolve_templates(),
        }

    # ── Unified Advisor Ask ─────────────────────────────────────────
    #
    # POST /v2/advisor/ask — intelligent routing + execution in one call.
    #
    # Runs v3 graph's routing pipeline (normalize → kb_probe →
    # analyze_intent → route_decision), maps route to provider/preset,
    # creates a ChatgptREST ask job, and returns trace + job info.
    #
    # This is the endpoint behind the chatgptrest_advisor_ask MCP tool.

    @router.post("/ask")
    async def advisor_ask(request: Request, body: dict = Body(...)):
        """Intelligent ask — route decision + job execution in one call.

        Body:
            question (str, required): User question
            intent_hint (str): "research" | "report" | "quick" | ""
            context (dict): Additional context (files, errors, etc.)
            timeout_seconds (int): Execution timeout (default 300)
            max_retries (int): Quality gate retries (default 1, Phase 2)
            quality_threshold (int): 0=auto (Phase 2)
            idempotency_key (str): Job idempotency key (auto-generated if blank)

        Returns:
            {ok, trace_id, job_id, route, route_rationale, provider, preset,
             kb_used, kb_hit_count, status, answer?, conversation_url?}
        """
        import uuid as _uuid

        _enforce_client_name_allowlist(request)
        _enforce_write_trace_headers(request, operation="advisor_ask")
        state = _init_once()
        if not getattr(request.app.state, "_evomap_registered", False):
            _publish_runtime_to_app(request.app, state)
        question = str(body.get("question", body.get("message", ""))).strip()
        if not question:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "question is required"},
            )
        try:
            enforce_agent_ingress_prompt_policy(
                question=question,
                allow_synthetic_prompt=bool(body.get("allow_synthetic_prompt") or False),
            )
        except PromptPolicyViolation as e:
            return JSONResponse(status_code=400, content={"ok": False, **e.detail})

        trace_id = str(body.get("trace_id", "")).strip() or str(_uuid.uuid4())
        intent_hint = str(body.get("intent_hint", "")).strip().lower()
        role_id = str(body.get("role_id", "")).strip()
        session_id = str(body.get("session_id", "")).strip()
        account_id = str(body.get("account_id", "")).strip()
        thread_id = str(body.get("thread_id", "")).strip()
        agent_id = str(body.get("agent_id", "")).strip()
        user_id = str(body.get("user_id", "")).strip() or account_id or "mcp"
        extra_context = dict(body.get("context", {}) or {})
        file_paths = coerce_file_path_input(body.get("file_paths"))
        auto_context = bool(body.get("auto_context", True))
        auto_context_top_k = _clamp_int(body.get("auto_context_top_k", 3), default=3, minimum=1, maximum=10)
        merged_context = _merge_advisor_entry_context(
            context=extra_context,
            file_paths=file_paths,
            auto_context=auto_context,
            auto_context_top_k=auto_context_top_k,
        )
        stable_context = _sanitize_idempotency_context(merged_context)
        if not isinstance(stable_context, dict):
            stable_context = {}
        timeout_seconds = _clamp_int(body.get("timeout_seconds", 300), default=300, minimum=30, maximum=1800)
        max_retries = _clamp_int(body.get("max_retries", 1), default=1, minimum=0, maximum=10)
        quality_threshold = _clamp_int(body.get("quality_threshold", 0), default=0, minimum=0, maximum=100)
        idempotency_key = str(body.get("idempotency_key", "")).strip()
        if not idempotency_key:
            idempotency_key = _advisor_ask_auto_idempotency_key(
                question=question,
                intent_hint=intent_hint,
                role_id=role_id,
                user_id=user_id,
                session_id=session_id,
                context=stable_context,
            )
        request_fingerprint = _advisor_ask_request_fingerprint(
            question=question,
            intent_hint=intent_hint,
            role_id=role_id,
            user_id=user_id,
            session_id=session_id,
            context=stable_context,
        )
        stable_context_hash = _stable_json_hash(stable_context) if stable_context else ""
        try:
            task_intake = build_task_intake_spec(
                ingress_lane="advisor_ask_v2",
                default_source="rest",
                raw_source=str(body.get("source", "")).strip(),
                raw_task_intake=body.get("task_intake") if isinstance(body.get("task_intake"), dict) else None,
                question=question,
                intent_hint=intent_hint,
                goal_hint=intent_hint,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                account_id=account_id,
                thread_id=thread_id,
                agent_id=agent_id,
                role_id=role_id,
                context=stable_context,
                attachments=file_paths or [],
                client_name=str(request.headers.get("X-Client-Name", "")).strip(),
            )
        except TaskIntakeValidationError as exc:
            return JSONResponse(status_code=400, content={"ok": False, **exc.detail})
        scenario_pack = resolve_scenario_pack(task_intake, goal_hint=intent_hint, context=stable_context)
        if scenario_pack is not None:
            task_intake = apply_scenario_pack(task_intake, scenario_pack)
            stable_context["scenario_pack"] = scenario_pack.to_dict()
        stable_context["task_intake"] = task_intake.to_dict()
        request_metadata = _advisor_request_metadata(
            trace_id=trace_id,
            session_id=session_id,
            account_id=account_id,
            thread_id=thread_id,
            agent_id=agent_id,
            role_id=role_id,
            user_id=user_id,
            intent_hint=intent_hint,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint[:32],
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            quality_threshold=quality_threshold,
        )
        request_metadata["auto_context"] = bool(auto_context)
        request_metadata["auto_context_top_k"] = int(auto_context_top_k)
        request_metadata["task_intake"] = summarize_task_intake(task_intake)
        if scenario_pack is not None:
            request_metadata["scenario_pack"] = summarize_scenario_pack(scenario_pack)
        if file_paths:
            request_metadata["file_paths_count"] = len(file_paths)
        degradation = _runtime_degradation(state)
        allow_duplicate_recent = bool(body.get("allow_duplicate_recent") or False)
        if not allow_duplicate_recent:
            duplicate_job = _find_recent_advisor_ask_duplicate(
                request_fingerprint=request_fingerprint,
                question=question,
                intent_hint=intent_hint,
                session_id=session_id,
                user_id=user_id,
                role_id=role_id,
            )
            if duplicate_job is not None:
                return _build_recent_advisor_ask_duplicate_response(
                    trace_id=trace_id,
                    request_metadata=request_metadata,
                    degradation=degradation,
                    duplicate_job=duplicate_job,
                )
        try:
            controller = ControllerEngine(state)
            with _bind_role(role_id):
                result = await run_in_threadpool(
                    controller.ask,
                    question=question,
                    trace_id=trace_id,
                    intent_hint=intent_hint,
                    role_id=role_id,
                    session_id=session_id,
                    account_id=account_id,
                    thread_id=thread_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    stable_context=stable_context,
                    idempotency_key=idempotency_key,
                    request_fingerprint=request_fingerprint,
                    timeout_seconds=timeout_seconds,
                    max_retries=max_retries,
                    quality_threshold=quality_threshold,
                    request_metadata=request_metadata,
                    degradation=degradation,
                    route_mapping=_ROUTE_TO_EXECUTION,
                    kb_direct_completion_allowed=_kb_direct_completion_allowed,
                    kb_direct_synthesis_enabled=_kb_direct_synthesis_enabled,
                    sanitize_context_hash=stable_context_hash,
                )
        except IdempotencyCollision as e:
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": "idempotency_collision",
                    "trace_id": trace_id,
                    "idempotency_key": getattr(e, "idempotency_key", idempotency_key),
                    "existing_job_id": getattr(e, "existing_job_id", None),
                    "route": "unknown",
                    "route_rationale": "",
                    "request_metadata": request_metadata,
                    "degradation": degradation,
                },
            )
        except PromptPolicyViolation as e:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": str(e.error),
                    "error_type": type(e).__name__,
                    "detail": dict(e.detail),
                    "trace_id": trace_id,
                    "route": "unknown",
                    "route_rationale": "",
                    "request_metadata": request_metadata,
                    "degradation": degradation,
                },
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("advisor_ask controller failed: %s", e, exc_info=True)
            return JSONResponse(
                status_code=502,
                content={
                    "ok": False,
                    "error": f"controller_failed: {type(e).__name__}: {e}",
                    "error_type": type(e).__name__,
                    "trace_id": trace_id,
                    "route": "unknown",
                    "route_rationale": "",
                    "request_metadata": request_metadata,
                    "degradation": degradation + [
                        {
                            "component": "advisor_ask",
                            "status": "error",
                            "reason": "controller_failed",
                            "error_type": type(e).__name__,
                        }
                    ],
                },
            )
        total_ms = float(result.get("total_ms") or 0.0)
        _emit_runtime_event(
            state,
            event_type="advisor_ask.dispatched",
            source="advisor_ask",
            trace_id=trace_id,
            data={
                "route": result.get("route"),
                "role_id": role_id,
                "provider": result.get("provider"),
                "preset": result.get("preset"),
                "job_id": result.get("job_id"),
                "kb_used": result.get("kb_used"),
                "kb_hit_count": result.get("kb_hit_count"),
                "intent": (result.get("delivery", {}) or {}).get("intent_top", ""),
                "routing_ms": round(float(result.get("routing_ms") or 0.0), 1),
                "total_ms": round(total_ms, 1),
                "controller_status": result.get("controller_status"),
                "run_id": result.get("run_id"),
            },
        )

        # ── 5. Langfuse trace ────────────────────────────────────────

        try:
            from chatgptrest.observability import start_request_trace
            lf_trace = start_request_trace(
                name="advisor_ask",
                user_id=user_id,
                session_id=session_id,
                tags=["advisor_ask", str(result.get("route") or "")],
                metadata={
                    "trace_id": trace_id,
                    "route": result.get("route"),
                    "provider": result.get("provider"),
                    "preset": result.get("preset"),
                    "kb_used": result.get("kb_used"),
                    "routing_ms": round(float(result.get("routing_ms") or 0.0), 1),
                    "job_id": result.get("job_id"),
                    "run_id": result.get("run_id"),
                },
            )
            if lf_trace:
                lf_trace.end()
        except Exception:
            pass

        logger.info(
            "advisor_ask: dispatched (trace=%s run=%s route=%s provider=%s preset=%s job=%s kb=%s routing=%.0fms controller=%s)",
            trace_id[:12],
            str(result.get("run_id") or "")[:12] or "-",
            result.get("route"),
            result.get("provider"),
            result.get("preset"),
            str(result.get("job_id") or "")[:12] if result.get("job_id") else "-",
            result.get("kb_used"),
            float(result.get("routing_ms") or 0.0),
            result.get("controller_status"),
        )
        return result

    return router
