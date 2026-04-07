"""v3 Agent Routes — public advisor-agent facade with wait/finalize semantics.

The public agent surface should feel session-first to clients. This module keeps
the facade compatibility goals from the initial scaffold, but now:

- waits for normal controller-backed jobs to finish when possible
- routes high-value goals (consult / gemini research / image) to the right substrate
- keeps session state tied to underlying job(s)
- exposes status/cancel in terms of the same session contract
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Mapping

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from chatgptrest.api.write_guards import (
    enforce_client_name_allowlist as _enforce_client_name_allowlist,
    enforce_write_trace_headers as _enforce_write_trace_headers,
)
from chatgptrest.api.agent_session_store import AgentSessionStore
from chatgptrest.advisor.ask_contract import AskContract, normalize_ask_contract, RiskClass
from chatgptrest.advisor.scenario_packs import (
    apply_scenario_pack,
    resolve_scenario_pack,
    summarize_scenario_pack,
)
from chatgptrest.advisor.ask_strategist import AskStrategyPlan, build_strategy_plan
from chatgptrest.advisor.post_review import generate_basic_review, PostAskReview
from chatgptrest.advisor.prompt_builder import PromptBuildResult, build_prompt_from_contract, build_prompt_from_strategy
from chatgptrest.advisor.task_intake import (
    TaskIntakeSpec,
    TaskIntakeValidationError,
    build_task_intake_spec,
    summarize_task_intake,
    task_intake_to_contract_seed,
)
from chatgptrest.advisor.runtime import get_advisor_runtime_if_ready
from chatgptrest.controller import ControllerEngine
from chatgptrest.controller.coding_agent_executor import (
    available_coding_agent_executors,
    resolve_coding_agent_executor,
)
from chatgptrest.core.attachment_contract import detect_missing_attachment_contract
from chatgptrest.core import artifacts
from chatgptrest.core.completion_contract import (
    canonical_answer_from_job_like,
    completion_contract_from_job_like,
    get_answer_provenance,
    get_authoritative_answer_path,
    get_authoritative_job_id,
    get_completion_answer_state,
    is_research_final,
)
from chatgptrest.core.config import load_config
from chatgptrest.core.db import connect
from chatgptrest.core.file_path_inputs import coerce_file_path_input
from chatgptrest.core.job_store import (
    _chatgpt_is_base_app_url,
    _gemini_is_base_app_url,
    create_job,
    get_job,
    request_cancel,
)
from chatgpt_web_mcp.providers.gemini_helpers import _looks_like_gemini_infra_error
from chatgptrest.core.pause import get_pause_state
from chatgptrest.core.prompt_policy import PromptPolicyViolation, enforce_agent_ingress_prompt_policy
from chatgptrest.core.state_machine import JobStatus
from chatgptrest.workspace.contracts import (
    WorkspaceRequest,
    WorkspaceRequestValidationError,
    build_workspace_request,
    merge_workspace_request,
    recommended_workspace_patch,
    summarize_workspace_request,
    workspace_action_summary,
    workspace_clarify_questions,
    workspace_missing_fields,
)
from chatgptrest.workspace.service import WorkspaceService
from chatgptrest.cognitive.memory_capture_service import MemoryCaptureItem, MemoryCaptureService
from chatgptrest.cognitive.work_memory_triggers import plan_auto_work_memory_capture
from chatgptrest.planning.meeting_task_store import (
    MeetingTaskStore,
    PlanningTaskResolutionError,
    enrich_planning_task_payload,
    resolve_planning_task_type,
)

logger = logging.getLogger(__name__)

_JOB_DONEISH = {
    JobStatus.COMPLETED,
    JobStatus.ERROR,
    JobStatus.CANCELED,
    JobStatus.BLOCKED,
    JobStatus.NEEDS_FOLLOWUP,
}
_DEFAULT_POLL_SECONDS = 1.0
_TERMINAL_AGENT_STATUSES = {
    "blocked",
    "canceled",
    "cancelled",
    "completed",
    "failed",
    "needs_followup",
    "needs_input",
}
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
_DIRECT_AGENT_REST_BLOCKED_CLIENTS = {
    "antigravity",
    "chatgptrestctl",
    "claude",
    "claude-code",
    "claudecode",
    "codex",
    "codex2",
}
_DIRECT_AGENT_REST_ALLOWED_CLIENTS = {
    "chatgptrest-mcp",
    "chatgptrestctl-maint",
    "openclaw-advisor",
}
_PUBLIC_AGENT_GENERIC_CLIENT_NAMES = {"", "agent", "mcp-agent"}
_PUBLIC_AGENT_GENERIC_CLIENT_INSTANCES = {"", "public-mcp"}
_PUBLIC_AGENT_MICROTASK_ROLE_HINTS = (
    "你是一个产业链知识图谱构建助手",
    "你是一个竞品分析助手",
    "you are a knowledge graph extraction assistant",
    "you are a competitive analysis assistant",
)
_PUBLIC_AGENT_MICROTASK_EXTRACTION_HINTS = (
    "知识图谱",
    "竞品分析",
    "结构化提取",
    "triple extractor",
    "extract triples",
    "extract entities",
    "extract competitors",
)
_PUBLIC_AGENT_STRUCTURED_OUTPUT_HINTS = (
    "只返回json",
    "只输出json",
    "只返回 json",
    "只输出 json",
    "return only json",
    "respond with json only",
    "only output json",
    "json array",
    "json object",
)
_PUBLIC_AGENT_SUFFICIENCY_HINTS = (
    "判断这批检索结果是否足以支撑当前查询",
    "只回答 sufficient 或 insufficient",
    "只回答sufficient或insufficient",
    "only answer sufficient or insufficient",
    "sufficient or insufficient",
)
_MANUAL_REPAIR_COOLDOWN_ERROR_TYPES = {
    "blocked",
    "geminiconversationthreadmismatch",
    "uitransienterror",
    "verificationrequired",
}
_MANUAL_REPAIR_COOLDOWN_MARKERS = (
    "cloudflare",
    "verification",
    "captcha",
    "just a moment",
    "upload menu button not found",
    "sse stream timeout",
    "sse stream ended without a json-rpc response",
)
_PUBLIC_COMPLETION_FIELDS = (
    "answer_state",
    "authoritative_job_id",
    "authoritative_answer_path",
    "answer_provenance",
    "research_final",
    "completion_contract",
    "canonical_answer",
)


def _make_agent_session_id() -> str:
    return f"agent_sess_{uuid.uuid4().hex[:16]}"


def _make_stream_url(session_id: str) -> str:
    return f"/v3/agent/session/{session_id}/stream"


def _public_agent_duplicate_window_seconds() -> float:
    raw = str(os.environ.get("CHATGPTREST_PUBLIC_AGENT_DUPLICATE_WINDOW_SECONDS") or "").strip()
    try:
        value = float(raw) if raw else 90 * 60
    except Exception:
        value = 90 * 60
    return max(300.0, value)


def _normalize_public_agent_text(value: Any, *, max_chars: int = 1600) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    if not text:
        return ""
    return text[:max_chars]


def _non_generic_public_agent_value(value: Any, *, generic_values: set[str]) -> str:
    text = _normalize_public_agent_text(value, max_chars=200)
    if not text or text in generic_values:
        return ""
    return text


def _public_agent_client_key(client_payload: Any) -> str:
    if not isinstance(client_payload, dict):
        return ""
    parts = [
        _non_generic_public_agent_value(
            client_payload.get("mcp_client_name") or client_payload.get("name"),
            generic_values=_PUBLIC_AGENT_GENERIC_CLIENT_NAMES,
        ),
        _normalize_public_agent_text(client_payload.get("mcp_client_version"), max_chars=120),
        _normalize_public_agent_text(client_payload.get("mcp_client_id"), max_chars=200),
        _non_generic_public_agent_value(
            client_payload.get("instance"),
            generic_values=_PUBLIC_AGENT_GENERIC_CLIENT_INSTANCES,
        ),
    ]
    return "|".join(part for part in parts if part)


def _task_intake_client_payload(task_intake: TaskIntakeSpec) -> dict[str, Any]:
    context = dict(task_intake.context or {})
    client_payload = context.get("client")
    return dict(client_payload or {}) if isinstance(client_payload, dict) else {}


def _is_public_mcp_submission(*, request: Request, task_intake: TaskIntakeSpec, client_info: dict[str, Any]) -> bool:
    header_client_name = str(request.headers.get("x-client-name") or "").strip().lower()
    client_instance = str(client_info.get("instance") or "").strip().lower()
    return header_client_name == "chatgptrest-mcp" or client_instance == "public-mcp" or task_intake.source == "mcp"


def _public_agent_microtask_block_detail(
    *,
    request: Request,
    message: str,
    task_intake: TaskIntakeSpec,
    client_info: dict[str, Any],
) -> dict[str, Any] | None:
    if not _is_public_mcp_submission(request=request, task_intake=task_intake, client_info=client_info):
        return None
    normalized = _normalize_public_agent_text(message or task_intake.objective)
    if not normalized:
        return None
    reason = ""
    if any(token in normalized for token in _PUBLIC_AGENT_SUFFICIENCY_HINTS):
        reason = "research_sufficiency_gate"
    elif (
        any(token in normalized for token in _PUBLIC_AGENT_MICROTASK_ROLE_HINTS)
        and any(token in normalized for token in _PUBLIC_AGENT_STRUCTURED_OUTPUT_HINTS)
    ) or (
        any(token in normalized for token in _PUBLIC_AGENT_MICROTASK_EXTRACTION_HINTS)
        and any(token in normalized for token in _PUBLIC_AGENT_STRUCTURED_OUTPUT_HINTS)
    ):
        reason = "structured_extractor_microtask"
    if not reason:
        return None
    caller = (
        str(client_info.get("mcp_client_name") or client_info.get("name") or "").strip()
        or str(request.headers.get("x-client-name") or "").strip()
        or "public-mcp"
    )
    return {
        "error": "public_agent_microtask_blocked",
        "error_type": "PublicAgentMicrotaskBlocked",
        "reason": reason,
        "caller": caller,
        "message": (
            "Public advisor-agent only accepts user-facing end-to-end turns. "
            "Structured extractor and sufficiency-gate microtasks must not call /v3/agent/turn."
        ),
        "hint": (
            "Run extraction/gating inside the caller pipeline or another non-public substrate, "
            "then submit only the final research/code-review/report turn to the public advisor-agent surface."
        ),
    }


def _should_guard_duplicate_public_agent_submission(
    *,
    task_intake: TaskIntakeSpec,
    provider_request: dict[str, Any] | None,
    message: str,
    route_hint: str,
) -> bool:
    normalized = _normalize_public_agent_text(message or task_intake.objective)
    if not normalized:
        return False
    goal_hint = str(task_intake.goal_hint or "").strip().lower()
    github_repo = _normalize_github_repo_ref(dict(task_intake.context or {}).get("github_repo"))
    if goal_hint in {"research", "report"} or str(route_hint or "").strip().lower() in {"deep_research", "report"}:
        return True
    if goal_hint != "code_review":
        return False
    if github_repo or list(task_intake.attachments or []):
        return True
    return len(normalized) >= 120


def _enforce_public_mcp_first_direct_rest_guard(request: Request, *, operation: str) -> None:
    raw = str(os.environ.get("CHATGPTREST_ENFORCE_AGENT_DIRECT_REST_BLOCK") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return
    client_name = (request.headers.get("x-client-name") or "").strip().lower()
    if not client_name or client_name in _DIRECT_AGENT_REST_ALLOWED_CLIENTS:
        return
    if client_name in _DIRECT_AGENT_REST_BLOCKED_CLIENTS:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "coding_agent_direct_rest_blocked",
                "error_type": "CodingAgentDirectRestBlocked",
                "reason": "public_mcp_is_required_for_coding_agents",
                "operation": operation,
                "x_client_name": client_name,
                "allowed_clients": sorted(_DIRECT_AGENT_REST_ALLOWED_CLIENTS),
                "hint": "Use the public advisor-agent MCP at http://127.0.0.1:18712/mcp instead of direct /v3/agent/* REST.",
            },
        )


def _advisor_runtime() -> dict[str, Any]:
    from chatgptrest.advisor.runtime import get_advisor_runtime

    return get_advisor_runtime()


def _bind_role(role_id: str):
    role_name = str(role_id or "").strip()
    if not role_name:
        return nullcontext(None)
    try:
        from chatgptrest.kernel.role_context import with_role
        from chatgptrest.kernel.role_loader import get_role

        role = get_role(role_name)
        if role is None:
            return nullcontext(None)
        return with_role(role)
    except Exception:
        return nullcontext(None)


def _advisor_request_metadata(**kwargs):
    return kwargs


def _runtime_degradation(_state):
    return []


def _emit_runtime_event(
    state: Any,
    *,
    event_type: str,
    source: str,
    trace_id: str = "",
    session_id: str = "",
    domain: str = "execution",
    security_label: str = "internal",
    run_id: str = "",
    parent_run_id: str = "",
    job_id: str = "",
    issue_id: str = "",
    task_ref: str = "",
    logical_task_id: str = "",
    repo_name: str = "ChatgptREST",
    repo_path: str = _REPO_ROOT,
    repo_branch: str = "",
    repo_head: str = "",
    repo_upstream: str = "",
    agent_name: str = "",
    agent_source: str = "chatgptrest.api.routes_agent_v3",
    provider: str = "",
    model: str = "",
    commit_sha: str = "",
    data: dict[str, Any] | None = None,
) -> None:
    event_type = str(event_type or "").strip()
    source = str(source or "").strip()
    if not event_type or not source:
        return None

    runtime = None
    if getattr(state, "event_bus", None) is not None or getattr(state, "observer", None) is not None:
        runtime = state
    else:
        runtime = get_advisor_runtime_if_ready()
    if runtime is None:
        logger.debug("Skipping runtime telemetry emit: runtime not ready (%s)", event_type)
        return None

    try:
        from chatgptrest.cognitive.telemetry_service import TelemetryEventInput, TelemetryIngestService

        service = TelemetryIngestService(runtime)
        service.ingest(
            trace_id=str(trace_id or "").strip(),
            session_id=str(session_id or "").strip(),
            events=[
                TelemetryEventInput(
                    event_type=event_type,
                    source=source,
                    domain=str(domain or "execution").strip() or "execution",
                    data=dict(data or {}),
                    session_id=str(session_id or "").strip(),
                    security_label=str(security_label or "internal").strip() or "internal",
                    run_id=str(run_id or "").strip(),
                    parent_run_id=str(parent_run_id or "").strip(),
                    job_id=str(job_id or "").strip(),
                    issue_id=str(issue_id or "").strip(),
                    task_ref=str(task_ref or "").strip(),
                    logical_task_id=str(logical_task_id or "").strip(),
                    repo_name=str(repo_name or "ChatgptREST").strip(),
                    repo_path=str(repo_path or _REPO_ROOT).strip(),
                    repo_branch=str(repo_branch or "").strip(),
                    repo_head=str(repo_head or "").strip(),
                    repo_upstream=str(repo_upstream or "").strip(),
                    agent_name=str(agent_name or source).strip(),
                    agent_source=str(agent_source or "chatgptrest.api.routes_agent_v3").strip(),
                    provider=str(provider or "").strip(),
                    model=str(model or "").strip(),
                    commit_sha=str(commit_sha or "").strip(),
                )
            ],
        )
    except Exception:
        logger.debug("runtime telemetry emit failed for %s", event_type, exc_info=True)
    return None


def _normalize_timeout(raw: Any, *, default: int = 300, minimum: int = 30, maximum: int = 7200) -> int:
    try:
        value = int(raw)
    except Exception:
        value = default
    return max(minimum, min(value, maximum))


def _agent_status_from_job_status(status: str) -> str:
    raw = str(status or "").strip().lower()
    if raw == JobStatus.COMPLETED.value:
        return "completed"
    if raw == JobStatus.ERROR.value:
        return "failed"
    if raw == JobStatus.CANCELED.value:
        return "cancelled"
    if raw in {JobStatus.BLOCKED.value, JobStatus.NEEDS_FOLLOWUP.value}:
        return "needs_followup"
    return "running"


def _cooldown_requires_same_session_repair(
    *,
    phase: str,
    conversation_url: str,
    conversation_id: str,
    last_error_type: str,
    last_error: str,
) -> bool:
    if str(phase or "").strip().lower() != "send":
        return False
    error_type = str(last_error_type or "").strip().lower()
    error_text = str(last_error or "").strip().lower()
    if _has_provider_thread_evidence(conversation_url=conversation_url, conversation_id=conversation_id):
        return False
    normalized_conversation_url = str(conversation_url or "").strip()
    if not normalized_conversation_url:
        if error_type in _MANUAL_REPAIR_COOLDOWN_ERROR_TYPES:
            return True
        return any(marker in error_text for marker in _MANUAL_REPAIR_COOLDOWN_MARKERS)
    if not normalized_conversation_url or not _gemini_is_base_app_url(normalized_conversation_url):
        if _chatgpt_is_base_app_url(normalized_conversation_url):
            if error_type in _MANUAL_REPAIR_COOLDOWN_ERROR_TYPES:
                return True
            return any(marker in error_text for marker in _MANUAL_REPAIR_COOLDOWN_MARKERS)
        return False
    if error_type in _MANUAL_REPAIR_COOLDOWN_ERROR_TYPES:
        return True
    if error_type == "infraerror" and _looks_like_gemini_infra_error(str(last_error or "")):
        return True
    return any(marker in error_text for marker in _MANUAL_REPAIR_COOLDOWN_MARKERS)


def _has_provider_thread_evidence(*, conversation_url: str, conversation_id: str) -> bool:
    normalized_conversation_id = str(conversation_id or "").strip()
    if normalized_conversation_id:
        return True
    normalized_conversation_url = str(conversation_url or "").strip()
    if not normalized_conversation_url:
        return False
    if _gemini_is_base_app_url(normalized_conversation_url) or _chatgpt_is_base_app_url(normalized_conversation_url):
        return False
    return True


def _queued_pause_requires_same_session_repair(
    *,
    phase: str,
    retry_after: Any,
    pause_mode: str,
    pause_reason: str,
    conversation_url: str,
    conversation_id: str,
) -> bool:
    if str(phase or "").strip().lower() != "send":
        return False
    if not isinstance(retry_after, int) or retry_after <= 0:
        return False
    normalized_conversation_id = str(conversation_id or "").strip()
    normalized_conversation_url = str(conversation_url or "").strip()
    if normalized_conversation_id:
        return False
    if not normalized_conversation_url or not _gemini_is_base_app_url(normalized_conversation_url):
        return False
    mode = str(pause_mode or "").strip().lower()
    if mode not in {"send", "all"}:
        return False
    reason = str(pause_reason or "").strip().lower()
    if not reason:
        return False
    if reason.startswith("auto_blocked:"):
        return True
    return any(marker in reason for marker in _MANUAL_REPAIR_COOLDOWN_MARKERS)


def _error_requires_same_session_repair(
    *,
    phase: str,
    conversation_url: str,
    conversation_id: str,
    last_error_type: str,
    last_error: str,
) -> bool:
    if str(phase or "").strip().lower() == "send" and not _has_provider_thread_evidence(
        conversation_url=conversation_url,
        conversation_id=conversation_id,
    ):
        error_type = str(last_error_type or "").strip().lower()
        error_text = str(last_error or "").strip().lower()
        if error_type in _MANUAL_REPAIR_COOLDOWN_ERROR_TYPES:
            return True
        if error_type == "maxattemptsexceeded" and any(
            marker in error_text for marker in _MANUAL_REPAIR_COOLDOWN_MARKERS
        ):
            return True
        if any(marker in error_text for marker in _MANUAL_REPAIR_COOLDOWN_MARKERS):
            return True
    error_type = str(last_error_type or "").strip().lower()
    if error_type == "geminiblanksendtimeout":
        return True
    has_thread = _has_provider_thread_evidence(
        conversation_url=conversation_url,
        conversation_id=conversation_id,
    )
    if not has_thread:
        return False
    if error_type == "geminiconversationthreadmismatch":
        return True
    error_text = str(last_error or "").strip().lower()
    return "different gemini thread than requested" in error_text


def _project_job_snapshot_for_public_agent(snapshot: dict[str, Any]) -> dict[str, Any]:
    data = dict(snapshot or {})
    job_status = str(data.get("job_status") or "").strip().lower()
    phase = str(data.get("phase") or "").strip().lower()
    conversation_url = str(data.get("conversation_url") or "").strip()
    conversation_id = str(data.get("conversation_id") or "").strip()
    last_error_type = str(data.get("last_error_type") or "").strip()
    last_error = str(data.get("last_error") or "").strip()
    retry_after = data.get("retry_after_seconds")
    pause_reason = str(data.get("pause_reason") or "").strip()
    pause_mode = str(data.get("pause_mode") or "").strip()
    job_id = str(data.get("job_id") or "").strip()
    if job_status == JobStatus.QUEUED.value and _queued_pause_requires_same_session_repair(
        phase=phase,
        retry_after=retry_after,
        pause_mode=pause_mode,
        pause_reason=pause_reason,
        conversation_url=conversation_url,
        conversation_id=conversation_id,
    ):
        next_action = _default_next_action(status="needs_followup", job_id=job_id)
        if isinstance(retry_after, int) and retry_after > 0:
            next_action = dict(next_action)
            next_action["retry_after_seconds"] = retry_after
        if pause_reason:
            next_action = dict(next_action)
            next_action["pause_reason"] = pause_reason
        data["agent_status"] = "needs_followup"
        data["next_action"] = next_action
        return data
    if job_status == JobStatus.COOLDOWN.value and _cooldown_requires_same_session_repair(
        phase=phase,
        conversation_url=conversation_url,
        conversation_id=conversation_id,
        last_error_type=last_error_type,
        last_error=last_error,
    ):
        next_action = _default_next_action(status="needs_followup", job_id=job_id)
        if isinstance(retry_after, int) and retry_after > 0:
            next_action = dict(next_action)
            next_action["retry_after_seconds"] = retry_after
        if last_error_type:
            next_action = dict(next_action)
            next_action["error_type"] = last_error_type
        data["agent_status"] = "needs_followup"
        data["next_action"] = next_action
        return data
    if job_status == JobStatus.ERROR.value and _error_requires_same_session_repair(
        phase=phase,
        conversation_url=conversation_url,
        conversation_id=conversation_id,
        last_error_type=last_error_type,
        last_error=last_error,
    ):
        next_action = _default_next_action(status="needs_followup", job_id=job_id)
        if isinstance(retry_after, int) and retry_after > 0:
            next_action = dict(next_action)
            next_action["retry_after_seconds"] = retry_after
        if last_error_type:
            next_action = dict(next_action)
            next_action["error_type"] = last_error_type
        data["agent_status"] = "needs_followup"
        data["next_action"] = next_action
        return data
    data["agent_status"] = _agent_status_from_job_status(job_status)
    data["next_action"] = _default_next_action(status=str(data.get("agent_status") or ""), job_id=job_id)
    return data


def _agent_status_from_controller_status(status: str) -> str:
    raw = str(status or "").strip().upper()
    if raw == "DELIVERED":
        return "completed"
    if raw == "FAILED":
        return "failed"
    if raw == "CANCELLED":
        return "cancelled"
    if raw == "WAITING_HUMAN":
        return "needs_followup"
    return "running"


def _default_next_action(*, status: str, job_id: str = "") -> dict[str, Any]:
    if status == "completed":
        return {"type": "followup", "safe_hint": "可以继续追问或要求改写成其他格式"}
    if status == "needs_input":
        return {
            "type": "attachment_confirmation_required",
            "safe_hint": "确认识别出的本地路径是否为附件；如是，请通过 input.file_paths 传入，否则请改写提示词",
            **({"job_id": job_id} if job_id else {}),
        }
    if status == "needs_followup":
        return {
            "type": "same_session_repair",
            "safe_hint": "需要处理阻塞或人工确认，再继续同一个 session",
            **({"job_id": job_id} if job_id else {}),
        }
    if status == "failed":
        return {
            "type": "retry_or_investigate",
            "safe_hint": "先检查底层错误，再决定是否重试同一个 session",
            **({"job_id": job_id} if job_id else {}),
        }
    if status == "cancelled":
        return {"type": "new_turn", "safe_hint": "如需继续，请新开一轮 turn 或重试当前请求"}
    return {
        "type": "check_status",
        "safe_hint": "任务仍在进行，可稍后查询 session 状态",
        **({"job_id": job_id} if job_id else {}),
    }


def _lifecycle_phase(*, status: str, accepted: bool = False) -> str:
    raw = str(status or "").strip().lower()
    if accepted:
        return "accepted"
    if raw in {"needs_followup", "needs_input"}:
        return "clarify_required"
    if raw == "completed":
        return "completed"
    if raw == "failed":
        return "failed"
    if raw == "cancelled":
        return "cancelled"
    return "progress"


def _build_delivery_surface(
    *,
    session_id: str,
    status: str,
    answer: str,
    answer_state: str = "",
    existing: dict[str, Any] | None = None,
    delivery_mode: str = "",
    accepted: bool = False,
    artifacts_list: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    existing_delivery = dict(existing or {})
    raw_mode = str(existing_delivery.get("mode") or delivery_mode or "").strip().lower()
    if not raw_mode:
        raw_mode = "deferred" if accepted else "sync"
    answer_text = str(answer or "")
    stream_url = str(existing_delivery.get("stream_url") or "").strip() or _make_stream_url(session_id)
    artifacts = list(artifacts_list or [])
    return {
        "format": str(existing_delivery.get("format") or "markdown"),
        "mode": raw_mode,
        "stream_url": stream_url,
        "answer_chars": int(existing_delivery.get("answer_chars") or len(answer_text)),
        "accepted": bool(accepted),
        "answer_ready": (
            str(answer_state or "").strip().lower() == "final"
            if str(answer_state or "").strip()
            else bool(answer_text.strip())
        ),
        "watchable": bool(stream_url),
        "artifact_count": len(artifacts),
        "terminal": str(status or "").strip().lower() in {"completed", "failed", "cancelled"},
    }


def _artifact_delivery_surface(artifacts: list[dict[str, Any]] | None) -> dict[str, Any]:
    items = list(artifacts or [])
    kinds = sorted({str(item.get("kind") or "").strip() for item in items if str(item.get("kind") or "").strip()})
    return {
        "count": len(items),
        "available": bool(items),
        "kinds": kinds,
    }


def _completion_projection_fields(job_or_result: Any) -> dict[str, Any]:
    contract = completion_contract_from_job_like(job_or_result)
    canonical = canonical_answer_from_job_like(job_or_result)
    return {
        "answer_state": get_completion_answer_state(job_or_result),
        "authoritative_job_id": get_authoritative_job_id(job_or_result),
        "authoritative_answer_path": get_authoritative_answer_path(job_or_result),
        "answer_provenance": get_answer_provenance(job_or_result),
        "research_final": bool(is_research_final(job_or_result)),
        "completion_contract": dict(contract),
        "canonical_answer": dict(canonical),
    }


def _workspace_effect_status(
    *,
    status: str,
    workspace_result: dict[str, Any] | None,
    workspace_diagnostics: dict[str, Any] | None,
) -> str:
    if isinstance(workspace_result, dict) and str(workspace_result.get("status") or "").strip():
        return str(workspace_result.get("status") or "").strip()
    if isinstance(workspace_diagnostics, dict):
        return "clarify_required"
    if str(status or "").strip().lower() == "failed":
        return "failed"
    return "pending"


def _build_effects_surface(payload: dict[str, Any]) -> dict[str, Any]:
    artifacts = list(payload.get("artifacts") or [])
    effects: dict[str, Any] = {
        "artifact_delivery": _artifact_delivery_surface(artifacts),
    }
    memory_capture = payload.get("memory_capture")
    if isinstance(memory_capture, dict):
        effects["memory_capture"] = dict(memory_capture)
    planning_memory_writeback = payload.get("planning_memory_writeback")
    if isinstance(planning_memory_writeback, dict):
        effects["planning_memory_writeback"] = dict(planning_memory_writeback)
    workspace_request = payload.get("workspace_request")
    workspace_result = payload.get("workspace_result")
    workspace_diagnostics = payload.get("workspace_diagnostics")
    if isinstance(workspace_request, dict):
        workspace_effect: dict[str, Any] = {
            "action": str(workspace_request.get("action") or "").strip(),
            "status": _workspace_effect_status(
                status=str(payload.get("status") or ""),
                workspace_result=workspace_result if isinstance(workspace_result, dict) else None,
                workspace_diagnostics=workspace_diagnostics if isinstance(workspace_diagnostics, dict) else None,
            ),
        }
        if isinstance(workspace_request.get("payload"), dict):
            workspace_effect["payload_keys"] = sorted(dict(workspace_request.get("payload") or {}).keys())
        if isinstance(workspace_result, dict):
            workspace_effect["result"] = workspace_action_summary(workspace_result)
        if isinstance(workspace_diagnostics, dict):
            workspace_effect["diagnostics"] = {
                "missing_fields": list(workspace_diagnostics.get("missing_fields") or []),
                "clarify_gate_reason": str(workspace_diagnostics.get("clarify_gate_reason") or ""),
            }
        effects["workspace_action"] = workspace_effect
    return effects


def _finalize_public_agent_surface(payload: dict[str, Any], *, accepted: bool | None = None) -> dict[str, Any]:
    data = dict(payload)
    session_id = str(data.get("session_id") or "").strip()
    status = str(data.get("status") or "").strip().lower()
    answer = str(data.get("answer") or data.get("last_answer") or "")
    next_action = dict(data.get("next_action") or {})
    delivery_mode = str(data.pop("delivery_mode", "") or "")
    effective_accepted = bool(data.get("accepted")) if accepted is None else bool(accepted)
    data["delivery"] = _build_delivery_surface(
        session_id=session_id,
        status=status,
        answer=answer,
        answer_state=str(data.get("answer_state") or ""),
        existing=data.get("delivery") if isinstance(data.get("delivery"), dict) else None,
        delivery_mode=delivery_mode,
        accepted=effective_accepted,
        artifacts_list=list(data.get("artifacts") or []),
    )
    phase = _lifecycle_phase(status=status, accepted=effective_accepted)
    data["lifecycle"] = {
        "phase": phase,
        "status": status,
        "turn_terminal": status in _TERMINAL_AGENT_STATUSES,
        "session_terminal": status in {"completed", "failed", "cancelled"},
        "blocking": phase == "clarify_required",
        "resumable": phase in {"accepted", "clarify_required", "progress"},
        "same_session_patch_allowed": status in {"needs_followup", "needs_input"},
        "next_action_type": str(next_action.get("type") or ""),
        "stream_supported": bool(str(data["delivery"].get("stream_url") or "").strip()),
    }
    data["effects"] = _build_effects_surface(data)
    return data


def _planning_query_read_semantics(
    *,
    surface: str,
    read_mode: str,
    writes_back_on_divergence: bool,
    authority: str,
) -> dict[str, Any]:
    return {
        "surface": str(surface or "").strip(),
        "read_mode": str(read_mode or "").strip(),
        "writes_back_on_divergence": bool(writes_back_on_divergence),
        "authority": str(authority or "").strip(),
    }


def _build_planning_query(
    *,
    kind: str,
    read_semantics: Mapping[str, Any],
    source_field: str,
    canonical_field: str,
    snapshot: Mapping[str, Any] | None = None,
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": str(kind or "").strip(),
        "surface": str(read_semantics.get("surface") or "").strip(),
        "authority": str(read_semantics.get("authority") or "").strip(),
        "read_mode": str(read_semantics.get("read_mode") or "").strip(),
        "writes_back_on_divergence": bool(read_semantics.get("writes_back_on_divergence")),
        "source_field": str(source_field or "").strip(),
        "canonical_field": str(canonical_field or "").strip(),
    }
    if isinstance(snapshot, Mapping):
        payload["snapshot"] = dict(snapshot)
    if items is not None:
        payload["items"] = [dict(item) for item in list(items or [])]
    return payload


def _planning_memory_writeback_receipt(
    receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        return {}

    def _text_list(values: Any) -> list[str]:
        results: list[str] = []
        for item in list(values or []):
            text = str(item or "").strip()
            if text:
                results.append(text)
        return results

    writes: list[dict[str, Any]] = []
    for item in list(receipt.get("writes") or []):
        if not isinstance(item, Mapping):
            continue
        writes.append(
            {
                "ok": bool(item.get("ok")),
                "category": str(item.get("category") or "").strip(),
                "record_id": str(item.get("record_id") or "").strip(),
                "message": str(item.get("message") or "").strip(),
            }
        )
    try:
        applied_count = int(receipt.get("applied_count") or 0)
    except Exception:
        applied_count = 0
    if applied_count <= 0 and writes:
        applied_count = sum(1 for item in writes if bool(item.get("ok")))
    return {
        "attempted": bool(receipt.get("attempted")),
        "eligible": bool(receipt.get("eligible")),
        "ok": bool(receipt.get("ok")),
        "status": str(receipt.get("status") or "").strip(),
        "reason": str(receipt.get("reason") or "").strip(),
        "requested_categories": _text_list(receipt.get("requested_categories")),
        "candidate_categories": _text_list(receipt.get("candidate_categories")),
        "applied_count": applied_count,
        "writes": writes,
    }


def _planning_response_artifact_refs(response: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in list(response.get("artifacts") or []):
        if not isinstance(item, Mapping):
            continue
        ref = str(item.get("path") or item.get("uri") or item.get("url") or "").strip()
        if ref:
            refs.append(ref)
    return refs


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    raw = str(value).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _memory_capture_failure_receipt(
    *,
    title: str,
    message: str,
    blocked_by: list[str],
    identity_gaps: list[str],
    provenance_quality: str,
    require_complete_identity: bool,
    trace_id: str,
    category: str = "captured_memory",
) -> dict[str, Any]:
    return {
        "attempted": True,
        "ok": False,
        "trace_id": trace_id,
        "title": title,
        "record_id": "",
        "category": category,
        "tier": "",
        "duplicate": False,
        "message": message,
        "provenance_quality": provenance_quality,
        "identity_gaps": list(identity_gaps),
        "blocked_by": list(blocked_by),
        "quality_gate": {},
        "audit_trail": [],
        "require_complete_identity": bool(require_complete_identity),
    }


def _maybe_capture_agent_turn_memory(
    *,
    runtime: Any,
    memory_capture_request: Any,
    session_id: str,
    account_id: str,
    thread_id: str,
    agent_id: str,
    role_id: str,
    trace_id: str,
    route: str,
    answer: str,
    message: str,
    source_system: str,
    status: str = "",
    next_action: dict[str, Any] | None = None,
    scenario_pack: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    auto_generated = False
    trigger = ""
    if memory_capture_request is None:
        auto_capture = plan_auto_work_memory_capture(
            session_id=session_id,
            trace_id=trace_id,
            route=route,
            status=status,
            answer=answer,
            message=message,
            agent_id=agent_id,
            scenario_pack=scenario_pack,
            next_action=next_action or _default_next_action(status=status),
        )
        if auto_capture is None:
            return None
        if getattr(runtime, "memory", None) is None:
            return None
        config = auto_capture.to_capture_request()
        auto_generated = True
        trigger = auto_capture.trigger
    if isinstance(memory_capture_request, bool):
        if not memory_capture_request:
            return None
        config: dict[str, Any] = {}
    elif isinstance(memory_capture_request, dict):
        config = dict(memory_capture_request)
        if not _coerce_bool(config.get("enabled", True), True):
            return None
    elif memory_capture_request is not None:
        return None

    title = str(config.get("title") or "").strip() or "Advisor agent memory capture"
    summary = str(config.get("summary") or "").strip()
    explicit_content = str(config.get("content") or "").strip()
    capture_answer = _coerce_bool(config.get("capture_answer", not explicit_content), not explicit_content)
    capture_message = _coerce_bool(config.get("capture_message", False), False)
    content_source = "custom"
    content = explicit_content
    if not content and capture_answer and str(answer or "").strip():
        content = str(answer or "").strip()
        content_source = "answer"
    elif not content and capture_message and str(message or "").strip():
        content = str(message or "").strip()
        content_source = "message"
    source_ref = str(config.get("source_ref") or "").strip() or f"advisor-agent://session/{session_id}/{route or 'turn'}/memory-capture"
    require_complete_identity = _coerce_bool(config.get("require_complete_identity", False), False)
    category = str(config.get("category") or "captured_memory").strip() or "captured_memory"
    security_label = str(config.get("security_label") or "internal").strip() or "internal"
    object_payload = dict(config.get("object_payload") or {}) if isinstance(config.get("object_payload"), dict) else {}
    auto_generated = auto_generated or _coerce_bool(config.get("auto_generated", False), False)
    trigger = trigger or str(config.get("trigger") or "").strip()
    try:
        confidence = float(config.get("confidence") or 0.85)
    except Exception:
        confidence = 0.85

    if not str(content or "").strip():
        return _memory_capture_failure_receipt(
            title=title,
            message="memory capture content empty",
            blocked_by=["empty_content"],
            identity_gaps=[],
            provenance_quality="missing_authority",
            require_complete_identity=require_complete_identity,
            trace_id=trace_id,
            category=category,
        ) | {"content_source": content_source, "auto_generated": auto_generated, "trigger": trigger}

    if getattr(runtime, "memory", None) is None:
        return _memory_capture_failure_receipt(
            title=title,
            message="memory unavailable",
            blocked_by=["memory_unavailable"],
            identity_gaps=["memory_unavailable"],
            provenance_quality="missing_authority",
            require_complete_identity=require_complete_identity,
            trace_id=trace_id,
            category=category,
        ) | {"content_source": content_source, "auto_generated": auto_generated, "trigger": trigger}

    service = MemoryCaptureService(runtime)
    result = service.capture(
        [
            MemoryCaptureItem(
                title=title,
                content=content,
                summary=summary,
                trace_id=trace_id,
                session_id=session_id,
                account_id=account_id,
                thread_id=thread_id,
                agent_id=agent_id,
                role_id=role_id,
                source_system=source_system or "advisor_agent",
                source_ref=source_ref,
                security_label=security_label,
                confidence=confidence,
                category=category,
                object_payload=object_payload,
                require_complete_identity=require_complete_identity,
            )
        ]
    )
    item = result.results[0].to_dict() if result.results else _memory_capture_failure_receipt(
        title=title,
        message="memory capture returned no result",
        blocked_by=["memory_unavailable"],
        identity_gaps=["memory_unavailable"],
        provenance_quality="missing_authority",
        require_complete_identity=require_complete_identity,
        trace_id=trace_id,
        category=category,
    )
    item["attempted"] = True
    item["content_source"] = content_source
    item["source_ref"] = source_ref
    item["require_complete_identity"] = require_complete_identity
    item["auto_generated"] = auto_generated
    if trigger:
        item["trigger"] = trigger
    return item


def _extract_conversation_url_from_artifacts(artifact_rows: list[dict[str, Any]]) -> str:
    for artifact in artifact_rows:
        if str(artifact.get("kind") or "") == "conversation_url":
            uri = str(artifact.get("uri") or "").strip()
            if uri:
                return uri
    return ""


def _canonical_provider_name(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"chatgpt", "chatgpt_web"}:
        return "chatgpt"
    if raw in {"gemini", "gemini_web"}:
        return "gemini"
    if raw in {"qwen", "qwen_web"}:
        return "qwen"
    return raw


def _normalize_github_repo_ref(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    parts = [part for part in raw.strip("/").split("/") if part]
    if len(parts) == 2:
        return f"https://github.com/{parts[0]}/{parts[1]}"
    return raw


def _dedupe_agent_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _append_available_input_notes(existing: Any, *, notes: list[str]) -> str | dict[str, Any] | None:
    clean_notes = _dedupe_agent_strings(notes)
    if not clean_notes:
        return existing
    if existing is None:
        return {"notes": clean_notes}
    if isinstance(existing, dict):
        payload = dict(existing)
        existing_notes = [str(item).strip() for item in list(payload.get("notes") or []) if str(item).strip()]
        payload["notes"] = _dedupe_agent_strings(existing_notes + clean_notes)
        return payload
    text = str(existing or "").strip()
    note_block = "\n".join(f"- {item}" for item in clean_notes)
    if text:
        return f"{text}\nNotes:\n{note_block}"
    return f"Notes:\n{note_block}"


def _planning_note_excerpt(value: Any, *, max_chars: int = 320) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return f"{text[: max(0, max_chars - 1)].rstrip()}…"


def _planning_memory_identity_gaps(*, account_id: str, thread_id: str, role_id: str) -> list[str]:
    gaps: list[str] = []
    if not str(role_id or "").strip():
        gaps.append("missing_role_id")
    if not str(account_id or "").strip():
        gaps.append("missing_account_id")
    if not str(thread_id or "").strip():
        gaps.append("missing_thread_id")
    return gaps


def _planning_memory_provenance_quality(*, account_id: str, thread_id: str, role_id: str) -> str:
    return "partial" if _planning_memory_identity_gaps(account_id=account_id, thread_id=thread_id, role_id=role_id) else "complete"


def _planning_writeback_candidate_categories(values: Any) -> list[str]:
    categories: list[str] = []
    seen: set[str] = set()
    for raw in list(values or []):
        text = str(raw or "").strip()
        if not text:
            continue
        head = text.split(":", 1)[0].strip().lower()
        if head not in {"active_project", "decision_ledger"} or head in seen:
            continue
        seen.add(head)
        categories.append(head)
    return categories


def _planning_memory_source_refs(checkpoint: Mapping[str, Any], response: Mapping[str, Any] | None = None) -> list[str]:
    refs = _dedupe_agent_strings(
        [
            *[str(item).strip() for item in list(checkpoint.get("writeback_evidence") or []) if str(item).strip()],
            *[str(item).strip() for item in list(checkpoint.get("artifact_refs") or []) if str(item).strip()],
            *[str(item).strip() for item in list(checkpoint.get("current_artifact_refs") or []) if str(item).strip()],
        ]
    )
    if refs:
        return refs
    if isinstance(response, Mapping):
        conversation_url = _extract_conversation_url_from_artifacts(list(response.get("artifacts") or []))
        if conversation_url:
            return [conversation_url]
    return []


def _planning_project_scope(task_intake: TaskIntakeSpec) -> str:
    def _candidate(mapping: Mapping[str, Any] | None) -> str:
        if not isinstance(mapping, Mapping):
            return ""
        for key in ("project_id", "project_ref", "project_or_topic_ref", "topic_ref"):
            value = str(mapping.get(key) or "").strip()
            if value:
                return value
        return ""

    for mapping in (
        task_intake.available_inputs if isinstance(task_intake.available_inputs, Mapping) else None,
        task_intake.context if isinstance(task_intake.context, Mapping) else None,
    ):
        value = _candidate(mapping)
        if value:
            return value

    context = task_intake.context if isinstance(task_intake.context, Mapping) else {}
    for key in ("planning_context", "planning_task", "control_plane"):
        nested = context.get(key)
        if key == "control_plane" and isinstance(nested, Mapping):
            nested = nested.get("planning_task")
        value = _candidate(nested if isinstance(nested, Mapping) else None)
        if value:
            return value
    return ""


def _planning_active_project_payload(
    *,
    task_id: str,
    task_type: str,
    checkpoint: Mapping[str, Any],
    task_title: str,
    objective: str,
    source_refs: list[str],
) -> dict[str, Any]:
    project_ref = str(checkpoint.get("project_or_topic_ref") or "").strip()
    next_steps = _dedupe_agent_strings(
        [
            *[str(item).strip() for item in list(checkpoint.get("pending_actions") or []) if str(item).strip()],
            *[str(item).strip() for item in list(checkpoint.get("next_actions") or []) if str(item).strip()],
            str(checkpoint.get("next_recommended_step") or "").strip(),
        ]
    )
    blockers = _dedupe_agent_strings(list(checkpoint.get("open_questions") or []))
    label = project_ref or task_title or objective or task_id
    return {
        "kind": "active_project",
        "project_id": project_ref or task_id,
        "name": label[:160],
        "phase": task_type or "planning",
        "status": "active",
        "blockers": blockers[:5],
        "next_steps": next_steps[:5],
        "key_files": source_refs[:5],
        "owner": str(checkpoint.get("last_surface") or "agent_v3").strip() or "agent_v3",
        "review_status": "approved",
        "source_refs": source_refs[:5],
    }


def _planning_decision_ledger_payload(
    *,
    task_id: str,
    task_type: str,
    checkpoint: Mapping[str, Any],
    source_refs: list[str],
) -> dict[str, Any]:
    decision_summary = str(checkpoint.get("decision_summary") or "").strip()
    stable_facts = [str(item).strip() for item in list(checkpoint.get("stable_facts") or []) if str(item).strip()]
    statement = decision_summary or (stable_facts[0] if stable_facts else "")
    return {
        "kind": "decision_ledger",
        "decision_id": f"{task_id}:decision",
        "statement": statement[:240],
        "domain": task_type or "planning",
        "confidence": 0.88 if decision_summary else 0.8,
        "review_status": "approved",
        "source_refs": source_refs[:5],
    }


def _maybe_apply_planning_knowledge_ingress(
    *,
    runtime: Any,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    scenario_pack: Mapping[str, Any] | None,
    query: str,
) -> dict[str, Any] | None:
    pack = dict(scenario_pack or {}) if isinstance(scenario_pack, Mapping) else {}
    scenario = str(pack.get("scenario") or task_intake.scenario or "").strip().lower()
    normalized_goal = str(goal_hint or task_intake.goal_hint or "").strip().lower()
    if scenario != "planning" and normalized_goal not in {"planning", "implementation_planning"}:
        return None

    receipt: dict[str, Any] = {
        "applied": False,
        "degraded": False,
        "query": _planning_note_excerpt(query, max_chars=180),
        "work_memory": {
            "attempted": False,
            "loaded": False,
            "category_counts": {},
            "identity_gaps": [],
            "scope_hits": {},
            "import_hits": [],
            "excerpt": "",
        },
        "planning_pack": {
            "attempted": False,
            "available": False,
            "ready_for_explicit_consumption": False,
            "hit_count": 0,
            "titles": [],
            "pack_version": "",
            "bundle_generated_at": "",
            "bundle_age_hours": None,
            "bundle_freshness": "",
            "scope": {},
            "checks": {},
        },
    }
    notes: list[str] = []
    project_scope = _planning_project_scope(task_intake)

    if getattr(runtime, "memory", None) is not None:
        try:
            from chatgptrest.kernel.work_memory_manager import WorkMemoryManager

            active_context_text, active_context_meta = WorkMemoryManager(runtime.memory).build_active_context(
                query=query,
                session_id=str(task_intake.session_id or "").strip(),
                account_id=str(task_intake.account_id or "").strip(),
                agent_id=str(task_intake.agent_id or "").strip(),
                role_id=str(task_intake.role_id or "").strip(),
                thread_id=str(task_intake.thread_id or "").strip(),
                project_id=project_scope,
            )
            receipt["work_memory"]["attempted"] = True
            receipt["work_memory"]["loaded"] = bool(active_context_text)
            receipt["work_memory"]["category_counts"] = dict(active_context_meta.get("category_counts") or {})
            receipt["work_memory"]["identity_gaps"] = list(active_context_meta.get("identity_gaps") or [])
            receipt["work_memory"]["scope_hits"] = dict(active_context_meta.get("scope_hits") or {})
            receipt["work_memory"]["import_hits"] = list(active_context_meta.get("import_hits") or [])
            receipt["work_memory"]["excerpt"] = _planning_note_excerpt(active_context_text, max_chars=360)
            if receipt["work_memory"]["identity_gaps"]:
                receipt["degraded"] = True
            if active_context_text:
                notes.append(f"Planning work memory: {receipt['work_memory']['excerpt']}")
        except Exception as exc:
            receipt["work_memory"] = {
                "attempted": True,
                "loaded": False,
                "reason": "work_memory_lookup_failed",
                "error": str(exc)[:200],
            }
            receipt["degraded"] = True

    try:
        from chatgptrest.evomap.knowledge.planning_runtime_pack_search import (
            planning_runtime_pack_bundle_status,
            search_planning_runtime_pack,
        )

        bundle_status = planning_runtime_pack_bundle_status()
        hits = search_planning_runtime_pack(query=query, top_k=3)
        first_meta = (
            dict(hits[0].get("planning_pack_meta") or {})
            if hits and isinstance(hits[0], dict)
            else {}
        )
        titles = [
            _planning_note_excerpt(hit.get("title"), max_chars=90)
            for hit in hits
            if isinstance(hit, dict) and str(hit.get("title") or "").strip()
        ]
        receipt["planning_pack"] = {
            "attempted": True,
            "available": bool(bundle_status.get("available")),
            "ready_for_explicit_consumption": bool(bundle_status.get("ready_for_explicit_consumption")),
            "hit_count": len(hits),
            "titles": titles,
            "pack_version": str(first_meta.get("pack_version") or bundle_status.get("pack_version") or "").strip(),
            "bundle_generated_at": str(
                first_meta.get("bundle_generated_at") or bundle_status.get("bundle_generated_at") or ""
            ).strip(),
            "bundle_age_hours": first_meta.get("bundle_age_hours", bundle_status.get("bundle_age_hours")),
            "bundle_freshness": str(
                first_meta.get("bundle_freshness") or bundle_status.get("bundle_freshness") or ""
            ).strip(),
            "scope": dict(bundle_status.get("scope") or {}),
            "checks": dict(bundle_status.get("checks") or {}),
        }
        if str(receipt["planning_pack"].get("bundle_freshness") or "") == "stale":
            receipt["degraded"] = True
        if hits:
            freshness = str(receipt["planning_pack"].get("bundle_freshness") or "").strip()
            freshness_text = f"; freshness={freshness}" if freshness else ""
            notes.append(
                "Planning runtime pack: "
                f"{len(hits)} approved hit(s); pack={receipt['planning_pack'].get('pack_version') or 'unknown'}"
                f"{freshness_text}; top_hits={'; '.join(titles[:2])}"
            )
    except Exception as exc:
        receipt["planning_pack"] = {
            "attempted": True,
            "available": False,
            "hit_count": 0,
            "reason": "planning_runtime_pack_lookup_failed",
            "error": str(exc)[:200],
        }
        receipt["degraded"] = True

    if not notes:
        return receipt

    task_intake.available_inputs = _append_available_input_notes(task_intake.available_inputs, notes=notes)
    updated_context = dict(task_intake.context or {})
    receipt["applied"] = True
    updated_context["planning_knowledge_ingress"] = dict(receipt)
    task_intake.context = updated_context
    return receipt


def _maybe_writeback_planning_work_memory(
    *,
    runtime: Any,
    task_intake: TaskIntakeSpec,
    task_layer: Mapping[str, Any] | None,
    response: Mapping[str, Any],
    account_id: str,
    thread_id: str,
    agent_id: str,
    role_id: str,
    trace_id: str,
) -> dict[str, Any] | None:
    if not isinstance(task_layer, Mapping):
        return None
    status = str(response.get("status") or "").strip().lower()
    if status != "completed":
        return {
            "attempted": False,
            "eligible": False,
            "status": status,
            "reason": "planning_memory_writeback_requires_completed_status",
        }
    if getattr(runtime, "memory", None) is None:
        return {
            "attempted": False,
            "eligible": False,
            "status": status,
            "reason": "memory_unavailable",
        }

    task_id = str(task_layer.get("task_id") or "").strip()
    checkpoint = dict(task_layer.get("checkpoint") or {})
    task_type = str(task_layer.get("task_type") or checkpoint.get("task_type") or "").strip().lower()
    if not task_id or not checkpoint:
        return {
            "attempted": False,
            "eligible": False,
            "status": status,
            "reason": "planning_task_checkpoint_missing",
        }

    explicit_categories = _planning_writeback_candidate_categories(checkpoint.get("memory_writeback_candidates"))
    has_project_state = any(
        [
            str(checkpoint.get("project_or_topic_ref") or "").strip(),
            str(checkpoint.get("task_title") or "").strip(),
            list(checkpoint.get("pending_actions") or []),
            list(checkpoint.get("next_actions") or []),
            str(checkpoint.get("next_recommended_step") or "").strip(),
        ]
    )
    has_decision_state = bool(str(checkpoint.get("decision_summary") or "").strip() or list(checkpoint.get("stable_facts") or []))
    requested_categories: list[str] = []
    if explicit_categories:
        requested_categories = list(explicit_categories)
    else:
        if has_project_state:
            requested_categories.append("active_project")
        if has_decision_state:
            requested_categories.append("decision_ledger")
    if not requested_categories:
        return {
            "attempted": False,
            "eligible": False,
            "status": status,
            "reason": "no_memory_writeback_candidates",
            "candidate_categories": explicit_categories,
        }

    source_refs = _planning_memory_source_refs(checkpoint, response=response)
    content = str(checkpoint.get("latest_output") or response.get("answer") or "").strip()
    summary = _planning_note_excerpt(
        checkpoint.get("decision_summary")
        or checkpoint.get("task_title")
        or checkpoint.get("project_or_topic_ref")
        or task_intake.objective,
        max_chars=200,
    )
    source_ref = f"planning-task://{task_id}/checkpoint"
    provenance_quality = _planning_memory_provenance_quality(
        account_id=account_id,
        thread_id=thread_id,
        role_id=role_id,
    )
    identity_gaps = _planning_memory_identity_gaps(
        account_id=account_id,
        thread_id=thread_id,
        role_id=role_id,
    )
    items: list[MemoryCaptureItem] = []
    plan: list[dict[str, Any]] = []
    if "active_project" in requested_categories:
        active_payload = _planning_active_project_payload(
            task_id=task_id,
            task_type=task_type,
            checkpoint=checkpoint,
            task_title=str(checkpoint.get("task_title") or "").strip(),
            objective=str(task_layer.get("objective") or task_intake.objective or "").strip(),
            source_refs=source_refs,
        )
        items.append(
            MemoryCaptureItem(
                title=f"Planning active project {active_payload['name']}",
                content=content or active_payload["name"],
                summary=summary or active_payload["name"],
                trace_id=trace_id,
                session_id=str(task_intake.session_id or response.get("session_id") or "").strip(),
                account_id=account_id,
                agent_id=agent_id,
                role_id=role_id,
                thread_id=thread_id,
                source_system="planning_task_plane",
                source_ref=source_ref,
                confidence=0.84,
                category="active_project",
                object_payload=active_payload,
            )
        )
        plan.append({"category": "active_project", "project_id": active_payload["project_id"], "source_refs": source_refs[:5]})
    if "decision_ledger" in requested_categories:
        decision_payload = _planning_decision_ledger_payload(
            task_id=task_id,
            task_type=task_type,
            checkpoint=checkpoint,
            source_refs=source_refs,
        )
        items.append(
            MemoryCaptureItem(
                title=f"Planning decision {decision_payload['statement'] or task_id}",
                content=content or decision_payload["statement"],
                summary=decision_payload["statement"] or summary,
                trace_id=trace_id,
                session_id=str(task_intake.session_id or response.get("session_id") or "").strip(),
                account_id=account_id,
                agent_id=agent_id,
                role_id=role_id,
                thread_id=thread_id,
                source_system="planning_task_plane",
                source_ref=source_ref,
                confidence=0.88 if str(checkpoint.get("decision_summary") or "").strip() else 0.8,
                category="decision_ledger",
                object_payload=decision_payload,
            )
        )
        plan.append({"category": "decision_ledger", "decision_id": decision_payload["decision_id"], "source_refs": source_refs[:5]})
    capture_result = MemoryCaptureService(runtime).capture(items)
    writes = [item.to_dict() for item in capture_result.results]
    return {
        "attempted": True,
        "eligible": True,
        "ok": bool(capture_result.ok),
        "status": status,
        "requested_categories": requested_categories,
        "candidate_categories": explicit_categories,
        "identity_gaps": identity_gaps,
        "provenance_quality": provenance_quality,
        "source_ref": source_ref,
        "plan": plan,
        "writes": writes,
        "applied_count": sum(1 for item in writes if bool(item.get("ok"))),
    }


def _augment_task_intake_for_public_repo(task_intake: TaskIntakeSpec) -> TaskIntakeSpec:
    context = dict(task_intake.context or {})
    github_repo = _normalize_github_repo_ref(context.get("github_repo"))
    if not github_repo:
        return task_intake
    notes = [
        f"Public repo URL: {github_repo}",
        "For public ChatGPT web review, the repo URL itself is sufficient; review repos are only needed for private mirrors, curated subsets, or import-size control.",
    ]
    if bool(context.get("enable_import_code")):
        notes.append(f"Gemini imported-code review requested for repo: {github_repo}")
    task_intake.available_inputs = _append_available_input_notes(task_intake.available_inputs, notes=notes)
    return task_intake


def _lane_policy_default_provider(
    *,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    scenario_pack: Mapping[str, Any] | None,
) -> tuple[str, str]:
    normalized_goal = str(goal_hint or "").strip().lower()
    pack = dict(scenario_pack or {}) if isinstance(scenario_pack, Mapping) else {}
    scenario = str(pack.get("scenario") or task_intake.scenario or "").strip().lower()
    if normalized_goal not in {"planning", "implementation_planning"} and scenario != "planning":
        return "", ""
    profile = str(pack.get("profile") or "").strip().lower()
    route_hint = str(pack.get("route_hint") or "").strip().lower()
    provider_hints = dict(pack.get("provider_hints") or {})
    planning_mode = str(provider_hints.get("planning_mode") or "").strip().lower()
    if profile == "implementation_plan" and planning_mode == "compact_next_steps" and route_hint == "quick_ask":
        return "chatgpt", "compact_implementation_next_steps_default_chatgpt"
    if scenario == "planning" and profile in _PLANNING_WEB_DEFAULT_PROFILES:
        return "chatgpt", "stable_planning_profile_default_chatgpt"
    return "", ""


_PLANNING_EXECUTION_LAYER_VERSION = "planning-execution-layer-v2"
_PLANNING_EXECUTION_SCOPE = "phase2_multi_executor_subset"
_PLANNING_AVAILABLE_EXECUTION_LANES = ["web", "coding_agent"]
_PLANNING_FUTURE_EXECUTION_LANES = ["workspace", "specialized"]
_PLANNING_WEB_DEFAULT_PROFILES = {
    "business_planning",
    "meeting_summary",
    "interview_notes",
    "workforce_planning",
    "implementation_plan",
    "project_diagnosis",
    "research_decision",
    "leadership_report",
    "planning_general",
}
_PLANNING_EXECUTION_SCOPE_REASON = (
    "planning_task_plane currently models the web-backed subset plus explicit coding-agent executors; "
    "workspace and specialized executors remain outside this contract"
)
_PLANNING_CODING_AGENT_DEFAULT_PROFILES = {"implementation_plan"}
_PLANNING_REPO_CONTEXT_KEYS = (
    "repo",
    "repo_root",
    "workspace_root",
    "project_root",
    "cwd",
    "codebase_path",
    "github_repo",
)
_PLANNING_CODE_ATTACHMENT_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".kt",
    ".mjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}


def _canonical_requested_preset(value: Any) -> str:
    return str(value or "").strip().lower()


def _canonical_requested_execution_lane(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in {"web", "provider", "provider_job"}:
        return "web"
    if raw in {"coding", "coding_agent", "codingagent", "executor", "agent"}:
        return "coding_agent"
    return ""


def _planning_repo_scope_signal(
    *,
    task_intake: TaskIntakeSpec,
    scenario_pack: Mapping[str, Any] | None = None,
) -> tuple[bool, str]:
    pack = dict(scenario_pack or {}) if isinstance(scenario_pack, Mapping) else {}
    if str(pack.get("scenario") or task_intake.scenario or "").strip().lower() != "planning":
        return False, ""
    profile = str(pack.get("profile") or "").strip().lower()
    if profile and profile not in _PLANNING_CODING_AGENT_DEFAULT_PROFILES:
        return False, ""
    context = dict(task_intake.context or {})
    for key in _PLANNING_REPO_CONTEXT_KEYS:
        if key == "github_repo":
            if _normalize_github_repo_ref(context.get(key)):
                return True, f"task_intake.context.{key}"
            continue
        if str(context.get(key) or "").strip():
            return True, f"task_intake.context.{key}"
    attachment_inventory = dict(context.get("attachment_inventory") or {})
    if list(attachment_inventory.get("repos") or []):
        return True, "task_intake.context.attachment_inventory.repos"
    for raw_path in list(task_intake.attachments or []):
        suffix = Path(str(raw_path or "").strip()).suffix.lower()
        if suffix in _PLANNING_CODE_ATTACHMENT_SUFFIXES:
            return True, "task_intake.attachments.code_files"
    notes = list(dict(task_intake.available_inputs or {}).get("notes") or []) if isinstance(task_intake.available_inputs, Mapping) else []
    for item in notes:
        text = str(item or "").strip()
        if text.startswith("Review repo:") or text.startswith("Public repo URL:"):
            return True, "task_intake.available_inputs.notes"
    return False, ""


def _default_coding_execution_request(
    *,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    scenario_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    normalized_goal = str(goal_hint or "").strip().lower()
    pack = dict(scenario_pack or {}) if isinstance(scenario_pack, Mapping) else {}
    scenario = str(pack.get("scenario") or task_intake.scenario or "").strip().lower()
    if normalized_goal not in {"planning", "implementation_planning"} and scenario != "planning":
        return None
    context = dict(task_intake.context or {})
    if _canonical_provider_name(context.get("requested_provider")) in {"chatgpt", "gemini", "qwen"}:
        return None
    if _canonical_provider_name(context.get("legacy_provider")) in {"chatgpt", "gemini", "qwen"}:
        return None
    has_repo_scope, scope_source = _planning_repo_scope_signal(task_intake=task_intake, scenario_pack=pack)
    if not has_repo_scope:
        return None
    return {
        "requested_execution_lane": "coding_agent",
        "request_source": "lane_policy.default_execution_lane",
        "requested_executor_family": "codex",
        "policy_reason": "repo_backed_planning_defaults_to_coding_agent",
        "scope_signal": scope_source,
    }


def _execution_request_from_task_intake(
    *,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    scenario_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    context = dict(task_intake.context or {})
    default_execution_request: dict[str, Any] | None = None
    lane = _canonical_requested_execution_lane(
        context.get("requested_execution_lane")
        or context.get("execution_lane")
        or context.get("executor_lane")
    )
    request_source = ""
    if lane:
        request_source = "task_intake.context.requested_execution_lane"
    if not lane and (
        context.get("requested_executor")
        or context.get("requested_executor_id")
        or context.get("requested_executor_family")
        or context.get("legacy_executor")
    ):
        lane = "coding_agent"
        request_source = "task_intake.context.requested_executor"
    if not lane:
        default_execution_request = _default_coding_execution_request(
            task_intake=task_intake,
            goal_hint=goal_hint,
            scenario_pack=scenario_pack,
        )
        if default_execution_request:
            lane = "coding_agent"
            request_source = str(default_execution_request.get("request_source") or "lane_policy.default_execution_lane")
            context = {
                **context,
                "requested_executor_family": str(default_execution_request.get("requested_executor_family") or "").strip(),
            }
        else:
            default_execution_request = None
    if not lane:
        provider_request = _provider_request_from_task_intake(
            task_intake=task_intake,
            goal_hint=goal_hint,
            scenario_pack=scenario_pack,
        )
        if provider_request:
            lane = "web"
            request_source = str(provider_request.get("request_source") or "task_intake.context")
    payload: dict[str, Any] = {
        "requested_execution_lane": lane or "",
        "request_source": request_source or "runtime_default",
        "available_execution_lanes": list(_PLANNING_AVAILABLE_EXECUTION_LANES),
        "future_execution_lanes": list(_PLANNING_FUTURE_EXECUTION_LANES),
    }
    if lane == "coding_agent":
        requested_executor = (
            context.get("requested_executor")
            or context.get("requested_executor_id")
            or context.get("legacy_executor")
        )
        requested_family = context.get("requested_executor_family") or context.get("executor_family")
        resolved = resolve_coding_agent_executor(
            requested_executor=requested_executor,
            requested_family=requested_family,
            requested_model=context.get("requested_model"),
            requested_effort=context.get("requested_effort"),
            request_source=request_source or "task_intake.context.requested_executor",
        )
        payload.update(
            {
                "requested_executor": str(requested_executor or "").strip().lower(),
                "requested_executor_family": str(requested_family or "").strip().lower(),
                "requested_model": str(context.get("requested_model") or "").strip(),
                "requested_effort": str(context.get("requested_effort") or "").strip(),
                "available_coding_executors": list(available_coding_agent_executors().values()),
            }
        )
        if default_execution_request:
            payload["policy_reason"] = str(default_execution_request.get("policy_reason") or "").strip()
            payload["scope_signal"] = str(default_execution_request.get("scope_signal") or "").strip()
        if resolved is not None:
            payload["selected_executor"] = resolved.executor_id
            payload["selected_executor_family"] = resolved.family
            payload["executor_resolution"] = resolved.resolution_reason
            payload["defaulted_executor"] = bool(resolved.defaulted)
            payload["executor_ready"] = bool(resolved.ready)
    return payload


def _provider_request_from_task_intake(
    *,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    scenario_pack: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    context = dict(task_intake.context or {})
    explicit_execution_lane = _canonical_requested_execution_lane(
        context.get("requested_execution_lane")
        or context.get("execution_lane")
        or context.get("executor_lane")
    )
    if explicit_execution_lane == "coding_agent" or any(
        context.get(key)
        for key in ("requested_executor", "requested_executor_id", "requested_executor_family", "legacy_executor")
    ):
        return None
    requested_provider = ""
    request_source = ""
    policy_reason = ""
    if str(goal_hint or "").strip().lower() in {"gemini_research", "gemini_deep_research"}:
        requested_provider = "gemini"
        request_source = "goal_hint"
    elif _canonical_provider_name(context.get("requested_provider")) in {"chatgpt", "gemini", "qwen"}:
        requested_provider = _canonical_provider_name(context.get("requested_provider"))
        request_source = "task_intake.context.requested_provider"
    elif _canonical_provider_name(context.get("legacy_provider")) in {"chatgpt", "gemini", "qwen"}:
        requested_provider = _canonical_provider_name(context.get("legacy_provider"))
        request_source = "task_intake.context.legacy_provider"
    else:
        requested_provider, policy_reason = _lane_policy_default_provider(
            task_intake=task_intake,
            goal_hint=goal_hint,
            scenario_pack=scenario_pack,
        )
        if requested_provider:
            request_source = "lane_policy.default_provider"
    if not requested_provider:
        return None
    payload = {
        "requested_provider": requested_provider,
        "request_source": request_source or "task_intake.context",
        "github_repo": _normalize_github_repo_ref(context.get("github_repo")),
        "enable_import_code": bool(context.get("enable_import_code")),
        "drive_name_fallback": bool(context.get("drive_name_fallback")),
    }
    requested_preset = _canonical_requested_preset(context.get("requested_preset"))
    preset_source = ""
    if requested_preset:
        preset_source = "task_intake.context.requested_preset"
    else:
        requested_preset = _canonical_requested_preset(context.get("legacy_preset"))
        if requested_preset:
            preset_source = "task_intake.context.legacy_preset"
    if requested_preset:
        payload["requested_preset"] = requested_preset
        payload["preset_source"] = preset_source or "task_intake.context"
    if policy_reason:
        payload["policy_reason"] = policy_reason
    return payload


def _lane_policy_payload(
    *,
    task_intake: TaskIntakeSpec,
    goal_hint: str,
    scenario_pack: Mapping[str, Any] | None,
    provider_request: Mapping[str, Any] | None,
    execution_request: Mapping[str, Any] | None,
) -> dict[str, Any]:
    pack = dict(scenario_pack or {}) if isinstance(scenario_pack, Mapping) else {}
    provider_hints = dict(pack.get("provider_hints") or {})
    scenario = str(pack.get("scenario") or task_intake.scenario or "").strip().lower()
    profile = str(pack.get("profile") or provider_hints.get("planning_profile") or "").strip().lower()
    route_hint = str(pack.get("route_hint") or "").strip().lower()
    if normalized_goal := str(goal_hint or "").strip().lower():
        goal_source = normalized_goal
    else:
        goal_source = ""
    default_provider, default_reason = _lane_policy_default_provider(
        task_intake=task_intake,
        goal_hint=goal_hint,
        scenario_pack=pack,
    )
    selected_provider = str((provider_request or {}).get("requested_provider") or default_provider or "").strip().lower()
    request_source = str((provider_request or {}).get("request_source") or "").strip()
    execution_lane = str((execution_request or {}).get("requested_execution_lane") or "").strip().lower() or "web"
    selected_executor = str((execution_request or {}).get("selected_executor") or "").strip().lower()
    selected_executor_family = str((execution_request or {}).get("selected_executor_family") or "").strip().lower()
    if not scenario and goal_source in {"planning", "implementation_planning"}:
        scenario = "planning"
    if scenario != "planning" and not profile and not route_hint:
        return {}
    if execution_lane == "coding_agent":
        return {
            "policy_version": "planning-lane-policy-v2",
            "scenario": scenario,
            "profile": profile,
            "route_hint": route_hint,
            "execution_lane": "coding_agent",
            "executor_scope": _PLANNING_EXECUTION_SCOPE,
            "execution_preference": str(pack.get("execution_preference") or "").strip().lower(),
            "planning_mode": str(provider_hints.get("planning_mode") or "").strip().lower(),
            "request_source": str((execution_request or {}).get("request_source") or "").strip(),
            "selected_executor": selected_executor,
            "selected_executor_family": selected_executor_family,
            "executor_resolution": str((execution_request or {}).get("executor_resolution") or "").strip(),
            "defaulted_executor": bool((execution_request or {}).get("defaulted_executor")),
            "executor_ready": bool((execution_request or {}).get("executor_ready", False)),
            "manual_selection_required": not bool(selected_executor),
            "reason": (
                str((execution_request or {}).get("policy_reason") or "").strip()
                or str((execution_request or {}).get("scope_signal") or "").strip()
                or str((execution_request or {}).get("executor_resolution") or "").strip()
                or "coding_agent_execution_lane_requested"
            ),
            "selection_source": str((execution_request or {}).get("request_source") or "").strip(),
            "scope_signal": str((execution_request or {}).get("scope_signal") or "").strip(),
            "automatic_default": str((execution_request or {}).get("request_source") or "").strip()
            == "lane_policy.default_execution_lane",
            "available_execution_lanes": list(_PLANNING_AVAILABLE_EXECUTION_LANES),
            "not_in_scope_execution_lanes": list(_PLANNING_FUTURE_EXECUTION_LANES),
            "scope_reason": _PLANNING_EXECUTION_SCOPE_REASON,
        }
    if request_source == "lane_policy.default_provider":
        provider_resolution = "policy_default"
    elif selected_provider:
        provider_resolution = "manual_override"
    elif default_provider:
        provider_resolution = "policy_default"
    else:
        provider_resolution = "runtime_default_unfrozen"
    return {
        "policy_version": "planning-lane-policy-v2",
        "scenario": scenario,
        "profile": profile,
        "route_hint": route_hint,
        "execution_lane": "web",
        "executor_scope": _PLANNING_EXECUTION_SCOPE,
        "execution_preference": str(pack.get("execution_preference") or "").strip().lower(),
        "planning_mode": str(provider_hints.get("planning_mode") or "").strip().lower(),
        "default_provider": default_provider,
        "selected_provider": selected_provider,
        "request_source": request_source,
        "provider_resolution": provider_resolution,
        "manual_selection_required": scenario == "planning" and not bool(default_provider),
        "reason": str(
            (provider_request or {}).get("policy_reason")
            or default_reason
            or (
                "provider_default_not_frozen_for_this_planning_profile"
                if scenario == "planning"
                else ""
            )
        ).strip(),
        "available_execution_lanes": list(_PLANNING_AVAILABLE_EXECUTION_LANES),
        "not_in_scope_execution_lanes": list(_PLANNING_FUTURE_EXECUTION_LANES),
        "scope_reason": _PLANNING_EXECUTION_SCOPE_REASON,
    }


def _provider_selection_payload(*, provider_request: dict[str, Any] | None, final_provider: str) -> dict[str, Any] | None:
    if not isinstance(provider_request, dict):
        return None
    requested_provider = str(provider_request.get("requested_provider") or "").strip()
    if not requested_provider:
        return None
    payload: dict[str, Any] = {
        "requested_provider": requested_provider,
        "request_source": str(provider_request.get("request_source") or "").strip(),
        "execution_lane": "web",
        "executor_scope": _PLANNING_EXECUTION_SCOPE,
    }
    requested_preset = _canonical_requested_preset(provider_request.get("requested_preset"))
    if requested_preset:
        payload["requested_preset"] = requested_preset
        payload["preset_source"] = str(provider_request.get("preset_source") or "").strip()
    github_repo = str(provider_request.get("github_repo") or "").strip()
    if github_repo:
        payload["github_repo"] = github_repo
    if bool(provider_request.get("enable_import_code")):
        payload["enable_import_code"] = True
    if bool(provider_request.get("drive_name_fallback")):
        payload["drive_name_fallback"] = True
    final_provider_raw = str(final_provider or "").strip()
    if not final_provider_raw:
        payload["request_pending"] = True
        return payload
    final_provider_family = _canonical_provider_name(final_provider_raw)
    payload["final_provider_family"] = final_provider_family or final_provider_raw
    payload["request_honored"] = final_provider_family == requested_provider
    payload["fallback"] = final_provider_family != requested_provider
    if payload["fallback"]:
        payload["fallback_reason"] = "requested_provider_not_selected"
    return payload


# Phase-1 planning surfaces intentionally expose only the web-backed execution
# subset. Coding-agent and workspace executors are tracked as future lanes, not
# implied by the current planning task-plane contract.
def _planning_execution_layer_payload(
    *,
    lane_policy: Mapping[str, Any] | None,
    execution_request: Mapping[str, Any] | None,
    provider_request: Mapping[str, Any] | None,
    final_provider: str,
) -> dict[str, Any]:
    execution_lane = str((lane_policy or {}).get("execution_lane") or "").strip().lower()
    requested_provider = _canonical_provider_name((provider_request or {}).get("requested_provider"))
    selected_provider = _canonical_provider_name(final_provider) or _canonical_provider_name((lane_policy or {}).get("selected_provider"))
    if not selected_provider:
        selected_provider = _canonical_provider_name((lane_policy or {}).get("default_provider")) or requested_provider
    if not execution_lane and (requested_provider or selected_provider or str(final_provider or "").strip()):
        execution_lane = "web"
    if execution_lane == "coding_agent":
        selected_executor = str((lane_policy or {}).get("selected_executor") or "").strip().lower()
        final_executor = str(final_provider or "").strip().lower()
        if final_executor and final_executor in available_coding_agent_executors():
            selected_executor = final_executor
        return {
            "contract_version": _PLANNING_EXECUTION_LAYER_VERSION,
            "execution_lane": "coding_agent",
            "executor_scope": _PLANNING_EXECUTION_SCOPE,
            "scope_reason": _PLANNING_EXECUTION_SCOPE_REASON,
            "selected_executor": selected_executor,
            "selected_executor_family": str((lane_policy or {}).get("selected_executor_family") or "").strip().lower(),
            "requested_executor": str((execution_request or {}).get("requested_executor") or "").strip().lower(),
            "requested_executor_family": str((execution_request or {}).get("requested_executor_family") or "").strip().lower(),
            "requested_model": str((execution_request or {}).get("requested_model") or "").strip(),
            "requested_effort": str((execution_request or {}).get("requested_effort") or "").strip(),
            "selection_state": "resolved" if selected_executor else "pending",
            "selection_source": str((lane_policy or {}).get("selection_source") or "").strip(),
            "automatic_default": bool((lane_policy or {}).get("automatic_default")),
            "executor_ready": bool((lane_policy or {}).get("executor_ready", False)),
            "available_execution_lanes": list(_PLANNING_AVAILABLE_EXECUTION_LANES),
            "available_coding_executors": list((execution_request or {}).get("available_coding_executors") or []),
            "not_in_scope_execution_lanes": list(_PLANNING_FUTURE_EXECUTION_LANES),
        }
    if execution_lane != "web":
        return {
            "contract_version": _PLANNING_EXECUTION_LAYER_VERSION,
            "execution_lane": execution_lane or "",
            "executor_scope": _PLANNING_EXECUTION_SCOPE,
            "scope_reason": _PLANNING_EXECUTION_SCOPE_REASON,
            "available_execution_lanes": list(_PLANNING_AVAILABLE_EXECUTION_LANES),
            "not_in_scope_execution_lanes": list(_PLANNING_FUTURE_EXECUTION_LANES),
        }
    return {
        "contract_version": _PLANNING_EXECUTION_LAYER_VERSION,
        "execution_lane": "web",
        "executor_scope": _PLANNING_EXECUTION_SCOPE,
        "scope_reason": _PLANNING_EXECUTION_SCOPE_REASON,
        "selected_provider": selected_provider,
        "requested_provider": requested_provider,
        "requested_preset": _canonical_requested_preset((provider_request or {}).get("requested_preset")),
        "selection_state": "resolved" if _canonical_provider_name(final_provider) else "pending",
        "available_execution_lanes": list(_PLANNING_AVAILABLE_EXECUTION_LANES),
        "not_in_scope_execution_lanes": list(_PLANNING_FUTURE_EXECUTION_LANES),
    }


_PLANNING_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "action_items": ("action items", "行动项", "执行动作"),
    "candidate_context": ("candidate context", "候选人背景", "候选人情况"),
    "chairman_summary": ("chairman summary", "executive summary", "董事长摘要", "管理层摘要"),
    "concerns": ("concerns", "担忧", "风险点"),
    "core_judgment": ("core judgment", "judgment", "结论判断", "核心判断", "判断"),
    "current_state": ("current state", "现状", "当前状态"),
    "current_stage": ("current stage", "当前阶段", "项目阶段"),
    "decision_summary": ("decision summary", "结论", "判断"),
    "decision_needed": ("decision needed", "拍板建议", "需要决策", "决策请求"),
    "decisions": ("decisions", "决策", "决定"),
    "dependencies": ("dependencies", "依赖", "前置条件"),
    "demand_drivers": ("demand drivers", "需求驱动", "需求来源"),
    "evidence": ("evidence", "依据", "证据"),
    "goal": ("goal", "目标"),
    "headcount_plan": ("headcount plan", "编制计划", "人力计划"),
    "hiring_sequence": ("hiring sequence", "招聘顺序", "招聘节奏"),
    "key_findings": ("key findings", "关键发现", "诊断结论"),
    "key_points": ("key points", "关键点", "重点"),
    "key_risks": ("key risks", "主要风险", "核心风险"),
    "key_updates": ("key updates", "关键更新", "最新进展"),
    "meeting_context": ("meeting context", "会议背景", "会议上下文"),
    "next_steps": ("next steps", "下一步", "后续动作"),
    "next_milestone": ("next milestone", "下一里程碑", "下个里程碑"),
    "objective": ("objective", "目标"),
    "open_questions": ("open questions", "待确认", "开放问题"),
    "options": ("options", "选项", "方案对比"),
    "outline": ("outline", "框架", "大纲"),
    "plan": ("plan", "计划", "方案", "实施计划", "执行计划"),
    "recommended_plan": ("recommended plan", "推荐方案", "建议方案"),
    "recommendation": ("recommendation", "建议", "推荐"),
    "risks": ("risks", "风险"),
    "staffing_goal": ("staffing goal", "编制目标", "人员目标"),
    "strengths": ("strengths", "优势", "亮点"),
    "suggested_action": ("suggested action", "建议动作", "建议行动"),
    "supporting_evidence": ("supporting evidence", "支撑依据", "支持证据"),
    "summary": ("summary", "摘要", "总结"),
    "validation": ("validation", "验证", "验收"),
}


def _planning_list_line_count(text: str) -> int:
    count = 0
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ", "• ")):
            count += 1
            continue
        idx = 0
        while idx < len(line) and line[idx].isdigit():
            idx += 1
        if idx and idx < len(line) and line[idx] in {".", ")", "、", "．"}:
            count += 1
    return count


def _planning_answer_has_section(answer: str, section: str) -> bool:
    text = str(answer or "").strip()
    if not text:
        return False
    normalized_section = str(section or "").strip().lower().replace("_", " ")
    candidates = {
        normalized_section,
        normalized_section.replace(" ", "_"),
        *[str(item).strip().lower() for item in _PLANNING_SECTION_ALIASES.get(str(section or "").strip().lower(), ()) if str(item).strip()],
    }
    lines = [str(item).strip().lower().strip("#*`- ") for item in text.splitlines() if str(item).strip()]
    for candidate in candidates:
        if not candidate:
            continue
        candidate_with_colons = {candidate, f"{candidate}:", f"{candidate}："}
        for line in lines:
            compact = line.replace("_", " ").replace("-", " ").strip()
            if any(compact.startswith(item) for item in candidate_with_colons):
                return True
            if f"**{candidate}**" in line:
                return True
    flattened = " ".join(line.replace("_", " ").replace("-", " ") for line in lines)
    return any(candidate in flattened for candidate in candidates if candidate)


def _planning_required_sections(*, task_intake: TaskIntakeSpec, scenario_pack: Mapping[str, Any] | None) -> list[str]:
    acceptance = dict(task_intake.acceptance.to_dict())
    if isinstance(scenario_pack, Mapping):
        acceptance.update(dict(scenario_pack.get("acceptance") or {}))
    return [str(item).strip().lower() for item in list(acceptance.get("required_sections") or []) if str(item).strip()]


def _planning_quality_gate_payload(
    *,
    task_intake: TaskIntakeSpec,
    scenario_pack: Mapping[str, Any] | None,
    planning_task: Mapping[str, Any] | None,
    response: Mapping[str, Any],
    execution_layer: Mapping[str, Any] | None,
) -> dict[str, Any]:
    pack = dict(scenario_pack or {}) if isinstance(scenario_pack, Mapping) else {}
    if str(pack.get("scenario") or task_intake.scenario or "").strip().lower() != "planning":
        return {}
    status = str(response.get("status") or "").strip().lower()
    answer = str(response.get("answer") or "").strip()
    provider_hints = dict(pack.get("provider_hints") or {})
    watch_policy = dict(pack.get("watch_policy") or {})
    required_sections = _planning_required_sections(task_intake=task_intake, scenario_pack=pack)
    covered_sections = [item for item in required_sections if item == "answer" or _planning_answer_has_section(answer, item)]
    missing_sections = [item for item in required_sections if item not in covered_sections]
    compact_mode = str(provider_hints.get("planning_mode") or "").strip().lower() == "compact_next_steps"
    list_line_count = _planning_list_line_count(answer)
    task_payload = dict(planning_task or {})
    checkpoint = dict(task_payload.get("checkpoint") or {})
    handoff = dict(task_payload.get("handoff") or {})
    next_recommended_step = str(
        handoff.get("next_recommended_step")
        or checkpoint.get("next_recommended_step")
        or ""
    ).strip()
    pending_actions = [
        str(item).strip()
        for item in (
            list(handoff.get("pending_actions") or [])
            + list(checkpoint.get("pending_actions") or [])
            + list(checkpoint.get("next_actions") or [])
        )
        if str(item).strip()
    ]
    continuation_ready = bool(
        str(response.get("task_id") or task_payload.get("task_id") or "").strip()
        and (next_recommended_step or pending_actions or str(dict(response.get("next_action") or {}).get("type") or "").strip())
    )
    action_contract = str(checkpoint.get("source_material_action_contract") or "").strip().lower()
    action_posture = str(checkpoint.get("source_material_action_posture") or "").strip().lower()
    grounding_ready = action_contract not in {"await_workspace_patch"} and action_posture != "preflight_blocked"
    execution_truth_visible = bool(str(dict(execution_layer or {}).get("execution_lane") or "").strip())
    section_threshold = 0
    section_coverage_ratio = 1.0
    if compact_mode:
        directly_usable = bool(answer) and list_line_count >= 3
    else:
        non_answer_sections = [item for item in required_sections if item != "answer"]
        covered_non_answer = [item for item in covered_sections if item != "answer"]
        required_non_answer_count = len(non_answer_sections)
        if required_non_answer_count >= 5:
            section_threshold = required_non_answer_count - 1
        elif required_non_answer_count:
            section_threshold = required_non_answer_count
        else:
            section_threshold = 0
        section_coverage_ratio = (
            float(len(covered_non_answer)) / float(required_non_answer_count)
            if required_non_answer_count
            else 1.0
        )
        section_coverage_ok = not required_non_answer_count or len(covered_non_answer) >= section_threshold
        directly_usable = bool(answer) and (
            section_coverage_ok
            and (
                len(answer) >= 280
                or bool(list_line_count >= 3)
                or len(covered_non_answer) == required_non_answer_count
            )
        )
    pass_value = bool(
        status == "completed"
        and answer
        and continuation_ready
        and grounding_ready
        and execution_truth_visible
        and directly_usable
    )
    return {
        "profile": "planning",
        "scenario_profile": str(pack.get("profile") or "").strip().lower(),
        "watch_checkpoint": str(watch_policy.get("checkpoint") or "").strip().lower(),
        "required_sections": required_sections,
        "covered_sections": covered_sections,
        "missing_sections": missing_sections,
        "answer_chars": len(answer),
        "list_line_count": list_line_count,
        "checklist": {
            "understands_request": status == "completed" and bool(answer),
            "continuation_ready": continuation_ready,
            "directly_usable": directly_usable,
            "grounding_ready": grounding_ready,
            "execution_truth_visible": execution_truth_visible,
            "trustworthy_status": status in {"completed", "failed", "cancelled", "needs_followup", "needs_input"},
        },
        "required_section_minimum": section_threshold if not compact_mode else 0,
        "section_coverage_ratio": section_coverage_ratio if not compact_mode else 1.0,
        "pass": pass_value,
    }


def _planning_artifact_refs_from_response(response: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in list(response.get("artifacts") or []):
        if not isinstance(item, Mapping):
            continue
        for key in ("path", "uri"):
            value = str(item.get(key) or "").strip()
            if value:
                refs.append(value)
    return refs


def _sync_planning_task_after_response(
    *,
    planning_task_store: MeetingTaskStore | None,
    planning_task: Mapping[str, Any] | None,
    response: Mapping[str, Any],
    task_intake: TaskIntakeSpec,
) -> dict[str, Any]:
    payload = dict(planning_task or {})
    if planning_task_store is None or not payload:
        return payload
    task_id = str(payload.get("task_id") or "").strip()
    session_id = str(response.get("session_id") or task_intake.session_id or "").strip()
    target_status = str(response.get("status") or "").strip().lower()
    if not task_id or not session_id or not target_status:
        return payload
    checkpoint = dict(payload.get("checkpoint") or {})
    current_status = str(
        payload.get("status")
        or checkpoint.get("current_status")
        or checkpoint.get("current_state")
        or ""
    ).strip().lower()
    current_next_action = dict(checkpoint.get("next_action") or {})
    target_next_action = dict(response.get("next_action") or {})
    if current_status == target_status and current_next_action == target_next_action:
        return payload
    try:
        updated = planning_task_store.update_checkpoint(
            task_id,
            status=target_status,
            answer=str(response.get("answer") or ""),
            next_action=target_next_action,
            source_materials=list(task_intake.attachments or []),
            surface="agent_v3",
            session_id=session_id,
            artifact_refs=_planning_artifact_refs_from_response(response),
        )
    except Exception:
        logger.warning("post-response planning task sync failed for task %s", task_id, exc_info=True)
        return payload
    if updated is None:
        return payload
    updated["resolution"] = str(payload.get("resolution") or updated.get("resolution") or "continue")
    updated["reason"] = str(payload.get("reason") or updated.get("reason") or "")
    return updated


def _project_execution_layer_on_planning_task(
    task_payload: Mapping[str, Any] | None,
    *,
    execution_layer: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(task_payload or {})
    normalized_execution_layer = dict(execution_layer or {})
    if normalized_execution_layer:
        payload["execution_layer"] = normalized_execution_layer
    return payload


def _execution_layer_from_session(session: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(session or {})
    control_plane = dict(source.get("control_plane") or {})
    execution_layer = dict(control_plane.get("execution_layer") or {})
    if execution_layer:
        return execution_layer
    return _planning_execution_layer_payload(
        lane_policy=dict(control_plane.get("lane_policy") or {}),
        execution_request=dict(control_plane.get("execution_request") or {}),
        provider_request=dict(dict(source.get("provenance") or {}).get("provider_selection") or {}),
        final_provider=str(dict(source.get("provenance") or {}).get("final_provider") or ""),
    )


def _build_provenance(
    *,
    route: str,
    provider_path: list[str],
    final_provider: str,
    job_id: str = "",
    consultation_id: str = "",
    provider_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "route": route or "unknown",
        "provider_path": [item for item in provider_path if str(item).strip()],
        "final_provider": final_provider or "unknown",
    }
    if job_id:
        provenance["job_id"] = job_id
    if consultation_id:
        provenance["consultation_id"] = consultation_id
    provider_selection = _provider_selection_payload(provider_request=provider_request, final_provider=final_provider)
    if provider_selection:
        provenance["provider_selection"] = provider_selection
    return provenance


def _provider_request_conflict(
    *,
    provider_request: dict[str, Any] | None,
    route_hint: str,
) -> dict[str, Any] | None:
    if not isinstance(provider_request, dict):
        return None
    requested_provider = str(provider_request.get("requested_provider") or "").strip()
    if requested_provider == "qwen":
        return {
            "error": "provider_removed",
            "message": "Requested provider qwen has been retired and is no longer available.",
            "hint": "Use chatgpt or gemini instead.",
        }
    if requested_provider != "gemini":
        return None
    github_repo = str(provider_request.get("github_repo") or "").strip()
    enable_import_code = bool(provider_request.get("enable_import_code"))
    if enable_import_code and not github_repo:
        return {
            "error": "gemini_import_code_requires_github_repo",
            "message": "Gemini imported-code review requires github_repo when enable_import_code=true.",
            "hint": "Pass a public GitHub repo URL or owner/repo, or disable enable_import_code.",
        }
    if enable_import_code and str(route_hint or "").strip().lower() == "deep_research":
        return {
            "error": "gemini_import_code_deep_research_conflict",
            "message": "Gemini imported-code review cannot be combined with deep-research routing.",
            "hint": "For public repos, keep the repo URL and disable enable_import_code; for imported-code review, stay on a non-deep-research Gemini lane.",
        }
    return None


def _should_use_direct_gemini_lane(*, provider_request: dict[str, Any] | None, goal_hint: str) -> bool:
    if str(goal_hint or "").strip().lower() in {"gemini_research", "gemini_deep_research"}:
        return True
    return isinstance(provider_request, dict) and str(provider_request.get("requested_provider") or "").strip() == "gemini"


def _gemini_route_name(*, strategy_plan: AskStrategyPlan, goal_hint: str) -> str:
    goal = str(goal_hint or "").strip().lower()
    if goal == "gemini_deep_research":
        return "deep_research"
    if goal == "gemini_research":
        return "research"
    route_name = str(strategy_plan.route_hint or "").strip().lower()
    if route_name:
        return route_name
    return "research"


def _gemini_execution_spec(
    *,
    provider_request: dict[str, Any] | None,
    strategy_plan: AskStrategyPlan,
    goal_hint: str,
    timeout_seconds: int,
) -> tuple[str, dict[str, Any]]:
    route_name = _gemini_route_name(strategy_plan=strategy_plan, goal_hint=goal_hint)
    deep_research = route_name == "deep_research"
    requested_preset = _canonical_requested_preset((provider_request or {}).get("requested_preset"))
    preset = requested_preset or ("deep_think" if route_name == "analysis_heavy" else "pro")
    params_obj: dict[str, Any] = {
        "preset": preset,
        "timeout_seconds": timeout_seconds,
        "max_wait_seconds": timeout_seconds * 3,
        "answer_format": "markdown",
    }
    if deep_research:
        params_obj["deep_research"] = True
    if isinstance(provider_request, dict):
        if bool(provider_request.get("enable_import_code")):
            params_obj["enable_import_code"] = True
        if bool(provider_request.get("drive_name_fallback")):
            params_obj["drive_name_fallback"] = True
    return route_name, params_obj


def _attachment_candidate_confidence(candidate: str) -> str:
    raw = str(candidate or "").strip()
    suffix = Path(raw).suffix.lower()
    normalized = raw.replace("\\", "/")
    if suffix:
        return "high"
    if normalized.startswith(("./", "../", "~/")):
        return "high"
    if len(raw) > 2 and raw[1] == ":" and raw[2] in {"/", "\\"}:
        return "high"
    if normalized.startswith(("/vol", "/tmp", "/home", "/mnt", "/Users", "/var")):
        return "high"
    return "medium"


def _attachment_confirmation_payload(signal: dict[str, Any]) -> dict[str, Any]:
    refs = [str(item).strip() for item in list(signal.get("local_file_refs") or []) if str(item).strip()]
    candidates = [
        {
            "text": ref,
            "reason": "explicit_local_file_reference",
            "confidence": _attachment_candidate_confidence(ref),
        }
        for ref in refs
    ]
    overall_confidence = "high" if any(item["confidence"] == "high" for item in candidates) else "medium"
    return {
        "error_type": "attachment_confirmation_required",
        "status": "needs_input",
        "confidence": overall_confidence,
        "attachment_candidates": candidates,
        "client_actions": [
            "provide_input_file_paths",
            "mark_candidates_as_not_attachments",
            "rewrite_prompt_without_path_like_tokens",
        ],
        "message": (
            "Detected possible local attachment references. Confirm whether these are real local files. "
            "If yes, resend with input.file_paths. If not, rewrite the prompt or explicitly mark them as non-attachments."
        ),
        "next_action": {
            "type": "attachment_confirmation_required",
            "status": "needs_input",
            "attachment_candidates": candidates,
        },
    }


def _attachment_confirmation_for_job(*, cfg, job_id: str) -> dict[str, Any] | None:
    with connect(cfg.db_path) as conn:
        row = conn.execute(
            "SELECT kind, input_json, params_json, last_error_type FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    if row is None:
        return None
    if str(row["last_error_type"] or "").strip() != "AttachmentContractMissing":
        return None
    try:
        input_obj = json.loads(str(row["input_json"] or "{}"))
    except Exception:
        input_obj = {}
    try:
        params_obj = json.loads(str(row["params_json"] or "{}"))
    except Exception:
        params_obj = {}
    signal = detect_missing_attachment_contract(
        kind=str(row["kind"] or ""),
        input_obj=input_obj if isinstance(input_obj, dict) else {},
        params_obj=params_obj if isinstance(params_obj, dict) else {},
    )
    if signal is None:
        return {
            "error_type": "attachment_confirmation_required",
            "status": "needs_input",
            "confidence": "medium",
            "attachment_candidates": [],
            "client_actions": [
                "provide_input_file_paths",
                "mark_candidates_as_not_attachments",
                "rewrite_prompt_without_path_like_tokens",
            ],
            "message": (
                "The request was blocked because local attachments may be missing. "
                "Confirm whether your prompt referenced local files; if yes, resend with input.file_paths."
            ),
            "next_action": {
                "type": "attachment_confirmation_required",
                "status": "needs_input",
                "attachment_candidates": [],
            },
        }
    return _attachment_confirmation_payload(signal)


def _read_answer_preview(*, cfg, answer_path: str) -> str:
    path = str(answer_path or "").strip()
    if not path:
        return ""
    try:
        return artifacts.read_text_preview(
            artifacts_dir=cfg.artifacts_dir,
            path=path,
            max_chars=24000,
        )
    except Exception:
        return ""


def _render_context_text(context: dict[str, Any]) -> str:
    if not context:
        return ""
    lines: list[str] = []
    for key, value in context.items():
        if value in (None, "", [], {}):
            continue
        if str(key).startswith("advisor_"):
            continue
        if key in {"goal_hint", "depth", "client"}:
            continue
        if key == "files" and isinstance(value, list):
            rendered = ", ".join(str(item).strip() for item in value if str(item).strip())
            if rendered:
                lines.append(f"- files: {rendered}")
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip()


def _enrich_message(message: str, context: dict[str, Any]) -> str:
    compiled_prompt_dict = context.get("compiled_prompt")
    if isinstance(compiled_prompt_dict, dict):
        try:
            compiled_prompt = PromptBuildResult.from_dict(compiled_prompt_dict)
            if compiled_prompt.user_prompt:
                return compiled_prompt.user_prompt
        except Exception as e:
            logger.warning(f"Failed to load compiled prompt from context: {e}")

    ask_contract_dict = context.get("ask_contract")
    if ask_contract_dict:
        try:
            contract = AskContract.from_dict(ask_contract_dict)
            provider = context.get("provider", "chatgpt")
            strategy_plan = None
            if isinstance(context.get("ask_strategy"), dict):
                strategy_plan = AskStrategyPlan.from_dict(dict(context.get("ask_strategy") or {}))
            prompt_result = build_prompt_from_strategy(
                strategy_plan=strategy_plan or build_strategy_plan(
                    message=message,
                    contract=contract,
                    goal_hint=str(context.get("goal_hint") or ""),
                    context=context,
                ),
                contract=contract,
                model_provider=provider,
                custom_context=context,
            )
            return prompt_result.user_prompt
        except Exception as e:
            logger.warning(f"Failed to build prompt from contract: {e}, falling back to basic enrichment")

    # Keep the final user-visible prompt clean. Context remains in structured
    # request/session metadata instead of being inlined into the question body.
    return message


def _write_review_to_evomap(
    review: PostAskReview,
    contract: AskContract,
    answer: str,
    route: str,
    provider: str,
    session_id: str,
    trace_id: str,
) -> None:
    """Write post-ask review signals to EventBus for EvoMap persistence.

    This writes structured signals that the EvoMap observer can consume
    for quality tracking and feedback loop.
    """
    try:
        from chatgptrest.kernel.event_bus import TraceEvent
        runtime = get_advisor_runtime_if_ready()
        event_bus = getattr(runtime, "event_bus", None) if runtime is not None else None
        if event_bus is None:
            logger.debug(
                "Skipping premium review EvoMap writeback: advisor runtime event_bus not ready "
                "(session=%s trace=%s)",
                session_id,
                trace_id or getattr(review, "trace_id", ""),
            )
            return

        effective_trace_id = str(trace_id or getattr(review, "trace_id", "")).strip()

        # Write review signals as TraceEvents
        signals_to_emit = [
            ("premium_ask.review.contract_completeness", {
                "contract_id": contract.contract_id,
                "completeness": review.contract_completeness,
                "source": review.contract_source,
            }),
            ("premium_ask.review.question_quality", {
                "quality": review.question_quality,
                "clarity_score": review.question_clarity,
            }),
            ("premium_ask.review.answer_quality", {
                "quality": review.answer_quality,
                "length_adequate": review.answer_length_adequate,
                "has_structure": review.answer_has_structure,
                "actionability": review.actionability,
            }),
            ("premium_ask.review.model_route_fit", {
                "model_fit": review.model_fit,
                "route_fit": review.route_fit,
                "provider": provider,
                "route": route,
            }),
            ("premium_ask.review.hallucination_risk", {
                "risk": review.hallucination_risk,
            }),
        ]
        if review.missing_info_detected:
            signals_to_emit.append(
                ("premium_ask.review.missing_inputs", {
                    "missing_info_detected": list(review.missing_info_detected),
                    "task_template": str(contract.task_template or ""),
                })
            )
        if review.prompt_improvement_hint and (
            review.contract_completeness < 0.7
            or review.question_quality in {"fair", "poor"}
            or review.route_fit in {"fair", "poor"}
            or review.model_fit in {"fair", "poor"}
        ):
            signals_to_emit.append(
                ("premium_ask.review.prompt_rewrite", {
                    "prompt_improvement_hint": review.prompt_improvement_hint,
                    "template_improvement_hint": review.template_improvement_hint,
                })
            )
        if review.route_fit in {"fair", "poor"} or review.model_fit in {"fair", "poor"}:
            signals_to_emit.append(
                ("premium_ask.review.route_or_model_miss", {
                    "route_fit": review.route_fit,
                    "model_fit": review.model_fit,
                    "route": route,
                    "provider": provider,
                })
            )

        emitted = 0
        for event_type, data in signals_to_emit:
            event = TraceEvent.create(
                source="advisor",
                event_type=event_type,
                trace_id=effective_trace_id,
                session_id=session_id,
                data=data,
            )
            if event_bus.emit(event):
                emitted += 1

        logger.info(
            "Wrote %d premium review signals to EvoMap: session=%s trace=%s quality=%s",
            emitted,
            session_id,
            effective_trace_id,
            review.question_quality,
        )
    except Exception as e:
        # Non-fatal: log but don't fail the request
        logger.warning(f"Failed to write review to EvoMap: {e}")


def _build_agent_response(
    *,
    session_id: str,
    run_id: str,
    status: str,
    answer: str,
    route: str,
    provider_path: list[str],
    final_provider: str,
    job_id: str = "",
    consultation_id: str = "",
    artifacts_list: list[dict[str, Any]] | None = None,
    next_action: dict[str, Any] | None = None,
    recovery_state: str = "clean",
    contract: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    trace_id: str = "",
    attachment_confirmation: dict[str, Any] | None = None,
    provider_request: dict[str, Any] | None = None,
    memory_capture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_answer = str(answer or "")
    payload: dict[str, Any] = {
        "ok": True,
        "session_id": session_id,
        "run_id": run_id,
        "status": status,
        "answer": clean_answer,
        "stream_url": _make_stream_url(session_id),
        "delivery": {
            "format": "markdown",
            "answer_chars": len(clean_answer),
            "mode": "sync",
        },
        "provenance": _build_provenance(
            route=route,
            provider_path=provider_path,
            final_provider=final_provider,
            job_id=job_id,
            consultation_id=consultation_id,
            provider_request=provider_request,
        ),
        "next_action": next_action or _default_next_action(status=status, job_id=job_id),
        "recovery_status": {
            "attempted": False,
            "final_state": recovery_state,
        },
    }

    # Add contract metadata to response
    if contract:
        payload["contract"] = contract

    # Add review metadata to response
    if review:
        payload["review"] = review
        # Also write to EvoMap if we have a review and contract
        if contract:
            try:
                ask_contract = AskContract.from_dict(contract) if isinstance(contract, dict) else contract
                post_review = PostAskReview.from_dict(review) if isinstance(review, dict) else review
                _write_review_to_evomap(
                    review=post_review,
                    contract=ask_contract,
                    answer=clean_answer,
                    route=route,
                    provider=final_provider,
                    session_id=session_id,
                    trace_id=trace_id,
                )
            except Exception as e:
                logger.debug(f"Failed to write review to EvoMap: {e}")
    elif contract and clean_answer:
        # Auto-generate review if we have contract and answer
        try:
            from chatgptrest.advisor.ask_contract import AskContract
            from chatgptrest.advisor.post_review import generate_basic_review

            ask_contract = AskContract.from_dict(contract) if isinstance(contract, dict) else contract
            generated_review = generate_basic_review(
                contract=ask_contract,
                answer=clean_answer,
                route=route,
                provider=final_provider,
                session_id=session_id,
                trace_id=trace_id,
            )
            payload["review"] = generated_review.to_dict()
            # Write to EvoMap
            _write_review_to_evomap(
                review=generated_review,
                contract=ask_contract,
                answer=clean_answer,
                route=route,
                provider=final_provider,
                session_id=session_id,
                trace_id=trace_id,
            )
        except Exception as e:
            logger.debug(f"Failed to generate review: {e}")

    if artifacts_list:
        payload["artifacts"] = list(artifacts_list)
    if attachment_confirmation:
        payload["attachment_confirmation"] = dict(attachment_confirmation)
    if memory_capture:
        payload["memory_capture"] = dict(memory_capture)
    return _finalize_public_agent_surface(payload)


def _job_snapshot(*, cfg, job_id: str) -> dict[str, Any]:
    with connect(cfg.db_path) as conn:
        job = get_job(conn, job_id=job_id)
        pause = get_pause_state(conn)
    if job is None:
        return _project_job_snapshot_for_public_agent({
            "job_id": job_id,
            "job_status": "missing",
            "answer": "",
            "conversation_url": "",
            "last_error": "job not found",
            "last_error_type": "NotFound",
            "phase": "",
            "retry_after_seconds": None,
        })
    job_status = str(job.status.value)
    retry_after = None
    now = time.time()
    if job.not_before and job.not_before > now:
        retry_after = max(0, int(job.not_before - now))
    pause_reason = ""
    pause_mode = ""
    if pause.is_active(now=now):
        pause_reason = str(pause.reason or "").strip()
        pause_mode = str(pause.mode or "").strip()
    answer = ""
    if job.status == JobStatus.COMPLETED and job.answer_path:
        answer = _read_answer_preview(cfg=cfg, answer_path=str(job.answer_path))
    return _project_job_snapshot_for_public_agent({
        "job_id": str(job.job_id),
        "job_status": job_status,
        "answer": answer,
        "conversation_url": str(job.conversation_url or "").strip(),
        "conversation_id": str(job.conversation_id or "").strip(),
        "answer_path": str(job.answer_path or "").strip(),
        "last_error": str(job.last_error or "").strip(),
        "last_error_type": str(job.last_error_type or "").strip(),
        "phase": str(job.phase or "").strip(),
        "retry_after_seconds": retry_after,
        "pause_reason": pause_reason,
        "pause_mode": pause_mode,
        **_completion_projection_fields(job),
    })


def _wait_for_job_completion(*, cfg, job_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + max(0.0, float(timeout_seconds))
    snapshot = _job_snapshot(cfg=cfg, job_id=job_id)
    while True:
        status = str(snapshot.get("job_status") or "")
        if status in {st.value for st in _JOB_DONEISH}:
            return snapshot
        now = time.time()
        if now >= deadline:
            return snapshot
        retry_after = snapshot.get("retry_after_seconds")
        if status == JobStatus.COOLDOWN.value and isinstance(retry_after, int) and retry_after > 0:
            time.sleep(min(float(retry_after), max(0.2, deadline - now), 30.0))
        else:
            time.sleep(min(_DEFAULT_POLL_SECONDS, max(0.2, deadline - now)))
        snapshot = _job_snapshot(cfg=cfg, job_id=job_id)


def _cancel_job(*, cfg, job_id: str, reason: str = "agent_session_cancelled") -> None:
    with connect(cfg.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        request_cancel(
            conn,
            artifacts_dir=cfg.artifacts_dir,
            job_id=job_id,
            requested_by={"name": "agent_v3"},
            reason=reason,
        )
        conn.commit()


def _submit_direct_job(
    *,
    cfg,
    kind: str,
    input_obj: dict[str, Any],
    params_obj: dict[str, Any],
    client_obj: dict[str, Any],
    idempotency_key: str,
) -> str:
    with connect(cfg.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = create_job(
            conn,
            artifacts_dir=cfg.artifacts_dir,
            idempotency_key=idempotency_key,
            kind=kind,
            input=input_obj,
            params=params_obj,
            max_attempts=max(1, int(cfg.max_attempts)),
            parent_job_id=None,
            client=client_obj,
        )
        conn.commit()
    return str(job.job_id)


def _consult_models_for_goal(goal_hint: str) -> list[str]:
    from chatgptrest.api import routes_consult as consult_routes

    if goal_hint in {"consult", "dual_review"}:
        return list(consult_routes.DEFAULT_MODELS)
    return list(consult_routes.DEFAULT_MODELS)


def _submit_consultation(
    *,
    cfg,
    question: str,
    file_paths: list[str] | None,
    timeout_seconds: int,
    session_id: str,
    goal_hint: str,
    user_id: str,
) -> dict[str, Any]:
    from chatgptrest.api import routes_consult as consult_routes

    consultation_id = f"cons-{uuid.uuid4().hex[:16]}"
    models = _consult_models_for_goal(goal_hint)
    jobs: list[dict[str, Any]] = []
    provider_next_at: dict[str, float] = {}
    now_ts = time.time()
    with connect(cfg.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        for model_key in models:
            model_cfg = consult_routes._MODEL_MAP[model_key]
            provider = str(model_cfg["provider"])
            stagger = consult_routes._PROVIDER_STAGGER_SECONDS.get(provider, 0.0)
            not_before_ts = 0.0
            if provider in provider_next_at and stagger > 0:
                not_before_ts = provider_next_at[provider]
            provider_next_at[provider] = max(provider_next_at.get(provider, now_ts), now_ts) + stagger

            input_obj: dict[str, Any] = {"question": question}
            if file_paths:
                input_obj["file_paths"] = list(file_paths)

            params_obj: dict[str, Any] = {
                "preset": model_cfg["preset"],
                "timeout_seconds": timeout_seconds,
                "max_wait_seconds": timeout_seconds * 3,
                "answer_format": "markdown",
            }
            if model_cfg.get("deep_research"):
                params_obj["deep_research"] = True
            if not_before_ts > 0:
                params_obj["not_before"] = not_before_ts

            job = create_job(
                conn,
                artifacts_dir=cfg.artifacts_dir,
                idempotency_key=f"agent-consult-{session_id}-{model_key}-{int(now_ts)}",
                kind=str(model_cfg["kind"]),
                input=input_obj,
                params=params_obj,
                max_attempts=max(1, int(cfg.max_attempts)),
                parent_job_id=None,
                client={"name": "advisor_agent_turn", "consult_model": model_key, "user_id": user_id},
                allow_queue=False,
                enforce_conversation_single_flight=False,
            )
            jobs.append(
                {
                    "model": model_key,
                    "provider": provider,
                    "kind": str(model_cfg["kind"]),
                    "job_id": str(job.job_id),
                    "status": str(job.status.value),
                    "preset": str(model_cfg["preset"]),
                    "deep_research": bool(model_cfg.get("deep_research")),
                    "staggered": bool(not_before_ts > 0),
                    "not_before": (not_before_ts if not_before_ts > 0 else None),
                }
            )
        conn.commit()

    consultation = {
        "consultation_id": consultation_id,
        "question": question,
        "models": models,
        "jobs": jobs,
        "created_at": time.time(),
        "status": "submitted",
    }
    consult_routes._store_consultation(consultation_id, consultation)
    return consultation


def _consultation_snapshot(*, cfg, consultation_id: str) -> dict[str, Any]:
    from chatgptrest.api import routes_consult as consult_routes

    consultation = consult_routes._get_consultation(consultation_id)
    if consultation is None:
        return {
            "consultation_id": consultation_id,
            "status": "missing",
            "agent_status": "failed",
            "jobs": [],
            "answers": {},
            "answer": "",
        }

    jobs = list(consultation.get("jobs") or [])
    all_completed = True
    any_error = False
    with connect(cfg.db_path) as conn:
        for job_info in jobs:
            job_id = str(job_info.get("job_id") or "")
            if not job_id:
                continue
            child = get_job(conn, job_id=job_id)
            if child is None:
                all_completed = False
                continue
            status = str(child.status.value)
            job_info["status"] = status
            job_info["answer_path"] = str(getattr(child, "answer_path", "") or "").strip() or None
            job_info["conversation_url"] = str(getattr(child, "conversation_url", "") or "").strip() or None
            if status != JobStatus.COMPLETED.value:
                all_completed = False
            if status in {JobStatus.ERROR.value, JobStatus.CANCELED.value, JobStatus.BLOCKED.value, JobStatus.NEEDS_FOLLOWUP.value}:
                any_error = True

    answers: dict[str, str] = {}
    for job_info in jobs:
        if job_info.get("status") == JobStatus.COMPLETED.value and job_info.get("answer_path"):
            text = _read_answer_preview(cfg=cfg, answer_path=str(job_info["answer_path"]))
            if text:
                answers[str(job_info["model"])] = text

    if all_completed:
        overall_status = "completed"
        agent_status = "completed"
    elif any_error:
        overall_status = "partial"
        agent_status = "needs_followup"
    else:
        overall_status = "submitted"
        agent_status = "running"

    parts = [f"## {model}\n\n{text}" for model, text in answers.items() if text]
    combined_answer = "\n\n---\n\n".join(parts)
    consultation["status"] = overall_status
    consultation["jobs"] = jobs
    return {
        "consultation_id": consultation_id,
        "status": overall_status,
        "agent_status": agent_status,
        "jobs": jobs,
        "answers": answers,
        "answer": combined_answer,
        "models": list(consultation.get("models") or []),
    }


def _wait_for_consultation_completion(*, cfg, consultation_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + max(0.0, float(timeout_seconds))
    snapshot = _consultation_snapshot(cfg=cfg, consultation_id=consultation_id)
    while True:
        if str(snapshot.get("status") or "") in {"completed", "partial", "missing"}:
            return snapshot
        now = time.time()
        if now >= deadline:
            return snapshot
        time.sleep(min(_DEFAULT_POLL_SECONDS, max(0.2, deadline - now)))
        snapshot = _consultation_snapshot(cfg=cfg, consultation_id=consultation_id)


def _controller_snapshot(
    controller: ControllerEngine,
    *,
    run_id: str,
    fallback_job_id: str = "",
) -> dict[str, Any]:
    snapshot = controller.get_run_snapshot(run_id=run_id) or {}
    run = dict(snapshot.get("run") or {})
    delivery = dict(run.get("delivery") or {})
    artifact_rows = list(snapshot.get("artifacts") or [])
    answer = str(delivery.get("answer") or "")
    conversation_url = str(delivery.get("conversation_url") or "").strip() or _extract_conversation_url_from_artifacts(artifact_rows)
    cfg = load_config()
    job_id = str(run.get("final_job_id") or delivery.get("job_id") or fallback_job_id or "")
    controller_status = str(run.get("controller_status") or "")
    attachment_confirmation = None
    if controller_status == "FAILED" and job_id:
        try:
            attachment_confirmation = _attachment_confirmation_for_job(cfg=cfg, job_id=job_id)
        except Exception:
            attachment_confirmation = None
    if attachment_confirmation:
        return {
            "run": run,
            "answer": str(attachment_confirmation.get("message") or ""),
            "conversation_url": conversation_url,
            "artifacts": artifact_rows,
            "job_id": job_id,
            "agent_status": "needs_input",
            "controller_status": controller_status,
            "next_action": dict(attachment_confirmation.get("next_action") or {}),
            "attachment_confirmation": dict(attachment_confirmation),
        }
    child_snapshot = _job_snapshot(cfg=cfg, job_id=job_id) if job_id else {}
    child_status = str(child_snapshot.get("job_status") or "").strip().lower()
    child_agent_status = str(child_snapshot.get("agent_status") or "").strip().lower()
    controller_agent_status = _agent_status_from_controller_status(controller_status)
    child_contract_fields = {
        key: child_snapshot.get(key)
        for key in _PUBLIC_COMPLETION_FIELDS
        if child_snapshot.get(key) not in (None, "", {}, [])
    }
    child_has_authoritative_answer = bool(
        str(child_snapshot.get("authoritative_answer_path") or "").strip()
        or str(child_snapshot.get("authoritative_job_id") or "").strip()
    )
    controller_missing_answer = not bool(str(answer or "").strip())
    should_prefer_child = (
        child_status not in {"", "missing"}
        and child_agent_status in _TERMINAL_AGENT_STATUSES
        and (
            controller_agent_status in {"running", "failed"}
            or (controller_agent_status == "completed" and child_has_authoritative_answer and controller_missing_answer)
        )
    )
    if should_prefer_child:
        child_conversation_url = str(child_snapshot.get("conversation_url") or "").strip()
        merged_artifacts = list(artifact_rows)
        if child_conversation_url and not any(
            str(item.get("kind") or "").strip() == "conversation_url" and str(item.get("uri") or "").strip() == child_conversation_url
            for item in merged_artifacts
            if isinstance(item, dict)
        ):
            merged_artifacts.append({"kind": "conversation_url", "uri": child_conversation_url})
        merged_next_action = dict(child_snapshot.get("next_action") or {})
        if not merged_next_action:
            merged_next_action = _default_next_action(
                status=child_agent_status,
                job_id=str(child_snapshot.get("job_id") or job_id),
            )
        retry_after = child_snapshot.get("retry_after_seconds")
        if isinstance(retry_after, int) and retry_after > 0 and merged_next_action.get("type") == "same_session_repair":
            merged_next_action = dict(merged_next_action)
            merged_next_action["retry_after_seconds"] = retry_after
        if str(child_snapshot.get("last_error_type") or "").strip() and merged_next_action.get("type") == "same_session_repair":
            merged_next_action = dict(merged_next_action)
            merged_next_action["error_type"] = str(child_snapshot.get("last_error_type") or "").strip()
        return {
            "run": run,
            "answer": str(child_snapshot.get("answer") or answer),
            "conversation_url": child_conversation_url or conversation_url,
            "artifacts": merged_artifacts,
            "job_id": str(child_snapshot.get("job_id") or job_id),
            "agent_status": child_agent_status,
            "controller_status": controller_status,
            "next_action": merged_next_action,
            **child_contract_fields,
        }
    return {
        "run": run,
        "answer": answer,
        "conversation_url": conversation_url,
        "artifacts": artifact_rows,
        "job_id": job_id,
        "agent_status": _agent_status_from_controller_status(controller_status),
        "controller_status": controller_status,
        "next_action": dict(run.get("next_action") or {}),
        **child_contract_fields,
    }


def _wait_for_controller_delivery(
    controller: ControllerEngine,
    *,
    run_id: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.time() + max(0.0, float(timeout_seconds))
    snapshot = _controller_snapshot(controller, run_id=run_id)
    while True:
        if snapshot["agent_status"] in {"completed", "failed", "cancelled", "needs_followup", "needs_input"}:
            return snapshot
        now = time.time()
        if now >= deadline:
            return snapshot
        time.sleep(min(_DEFAULT_POLL_SECONDS, max(0.2, deadline - now)))
        snapshot = _controller_snapshot(controller, run_id=run_id)


def _session_response(session: dict[str, Any]) -> dict[str, Any]:
    control_plane = dict(session.get("control_plane") or {})
    planning_task = control_plane.get("planning_task")
    if isinstance(planning_task, dict):
        enriched_planning_task = enrich_planning_task_payload(planning_task)
        control_plane["planning_task"] = enriched_planning_task
    else:
        enriched_planning_task = {}
    payload = {
        "ok": True,
        "session_id": session["session_id"],
        "run_id": session.get("run_id", ""),
        "job_id": session.get("job_id", ""),
        "consultation_id": session.get("consultation_id", ""),
        "status": session.get("status", "running"),
        "last_message": session.get("last_message", ""),
        "last_answer": session.get("last_answer", ""),
        "route": session.get("route", ""),
        "stream_url": session.get("stream_url") or _make_stream_url(str(session["session_id"])),
        "updated_at": session.get("updated_at", 0),
        "provenance": session.get("provenance", {}),
        "next_action": session.get("next_action") or _default_next_action(
            status=str(session.get("status") or "running"),
            job_id=str(session.get("job_id") or ""),
        ),
        "artifacts": list(session.get("artifacts") or []),
        "delivery_mode": str(session.get("delivery_mode") or ""),
    }
    for key in _PUBLIC_COMPLETION_FIELDS:
        value = session.get(key)
        if value not in (None, "", {}, []):
            payload[key] = dict(value) if isinstance(value, dict) else value
    if isinstance(session.get("task_intake"), dict):
        payload["task_intake"] = dict(session.get("task_intake") or {})
    if isinstance(session.get("contract"), dict):
        payload["contract"] = dict(session.get("contract") or {})
    if isinstance(session.get("scenario_pack"), dict):
        payload["scenario_pack"] = dict(session.get("scenario_pack") or {})
    if control_plane:
        payload["control_plane"] = control_plane
    elif isinstance(session.get("control_plane"), dict):
        payload["control_plane"] = dict(session.get("control_plane") or {})
    if isinstance(session.get("clarify_diagnostics"), dict):
        payload["clarify_diagnostics"] = dict(session.get("clarify_diagnostics") or {})
    if enriched_planning_task:
        payload["planning_task"] = enriched_planning_task
    workspace_request = _workspace_request_from_session(session)
    if workspace_request:
        payload["workspace_request"] = workspace_request
    workspace_result = _workspace_result_from_session(session)
    if workspace_result:
        payload["workspace_result"] = workspace_result
    workspace_diagnostics = _workspace_diagnostics_from_session(session)
    if workspace_diagnostics:
        payload["workspace_diagnostics"] = workspace_diagnostics
    attachment_confirmation = session.get("attachment_confirmation")
    if attachment_confirmation:
        payload["attachment_confirmation"] = dict(attachment_confirmation)
    if isinstance(session.get("memory_capture"), dict):
        payload["memory_capture"] = dict(session.get("memory_capture") or {})
    return _finalize_public_agent_surface(payload)


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if value is None:
            continue
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dict(existing, value)
        else:
            merged[key] = value
    return merged


def _missing_contract_fields(contract: AskContract) -> list[str]:
    missing: list[str] = []
    if not str(contract.objective or "").strip():
        missing.append("objective")
    if not str(contract.decision_to_support or "").strip():
        missing.append("decision_to_support")
    if not str(contract.audience or "").strip():
        missing.append("audience")
    if not str(contract.output_shape or "").strip():
        missing.append("output_shape")
    return missing


def _recommended_contract_patch(contract: AskContract, *, missing_fields: list[str]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "objective" in missing_fields:
        patch["objective"] = str(contract.objective or "").strip() or "<what needs to be produced>"
    if "decision_to_support" in missing_fields:
        patch["decision_to_support"] = "<what decision/action this should support>"
    if "audience" in missing_fields:
        patch["audience"] = "<who will use this output>"
    if "output_shape" in missing_fields:
        patch["output_shape"] = str(contract.output_shape or "").strip() or "text_answer"
    return patch


def _workspace_request_from_session(session: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(session, dict):
        return {}
    control_plane = session.get("control_plane")
    if isinstance(control_plane, dict) and isinstance(control_plane.get("workspace_request"), dict):
        return dict(control_plane.get("workspace_request") or {})
    workspace_request = session.get("workspace_request")
    if isinstance(workspace_request, dict):
        return dict(workspace_request or {})
    return {}


def _workspace_result_from_session(session: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(session, dict):
        return {}
    control_plane = session.get("control_plane")
    if isinstance(control_plane, dict) and isinstance(control_plane.get("workspace_result"), dict):
        return dict(control_plane.get("workspace_result") or {})
    workspace_result = session.get("workspace_result")
    if isinstance(workspace_result, dict):
        return dict(workspace_result or {})
    return {}


def _workspace_diagnostics_from_session(session: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(session, dict):
        return {}
    control_plane = session.get("control_plane")
    if isinstance(control_plane, dict) and isinstance(control_plane.get("workspace_diagnostics"), dict):
        return dict(control_plane.get("workspace_diagnostics") or {})
    workspace_diagnostics = session.get("workspace_diagnostics")
    if isinstance(workspace_diagnostics, dict):
        return dict(workspace_diagnostics or {})
    return {}


def _contract_patch_workspace_request(patch: Any) -> dict[str, Any]:
    if not isinstance(patch, dict):
        return {}
    nested = patch.get("workspace_request")
    if isinstance(nested, dict):
        return dict(nested or {})
    return {}


def _build_workspace_control_plane(
    *,
    workspace_request: WorkspaceRequest,
    workspace_result: dict[str, Any] | None = None,
    workspace_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    control_plane: dict[str, Any] = {
        "workspace_request": workspace_request.to_dict(),
        "workspace_request_summary": summarize_workspace_request(workspace_request),
    }
    if workspace_result:
        control_plane["workspace_result"] = dict(workspace_result)
    if workspace_diagnostics:
        control_plane["workspace_diagnostics"] = dict(workspace_diagnostics)
    return control_plane


def _build_workspace_clarify_diagnostics(*, session_id: str, workspace_request: WorkspaceRequest) -> dict[str, Any]:
    missing_fields = workspace_missing_fields(workspace_request)
    recommended_patch = recommended_workspace_patch(workspace_request)
    return {
        "missing_fields": missing_fields,
        "clarify_gate_reason": "workspace_action_missing_fields",
        "clarify_reason_detail": (
            f"Workspace action '{workspace_request.action}' is missing required payload fields: "
            + ", ".join(missing_fields)
        ),
        "recommended_contract_patch": recommended_patch,
        "recommended_resubmit_payload": {
            "session_id": session_id,
            "contract_patch": recommended_patch,
        },
    }


def _workspace_action_answer(result: dict[str, Any]) -> str:
    action = str(result.get("action") or "").strip()
    data = dict(result.get("data") or {})
    message = str(result.get("message") or "").strip()
    if action == "search_drive_files":
        files = list(data.get("files") or [])
        if not files:
            return "No matching Google Drive files found."
        lines = [f"Found {len(files)} Google Drive file(s):"]
        for item in files[:5]:
            name = str(item.get("name") or "untitled")
            link = str(item.get("webViewLink") or "").strip()
            lines.append(f"- {name}{f' ({link})' if link else ''}")
        return "\n".join(lines)
    if action == "fetch_drive_file":
        return f"Downloaded Google Drive file to {str(data.get('local_path') or '').strip()}."
    if action == "deliver_report_to_docs":
        url = str(data.get("url") or "").strip()
        answer = f"Delivered report to Google Docs: {url}" if url else "Delivered report to Google Docs."
        if dict(data.get("gmail") or {}):
            answer += "\nGmail notification sent."
        return answer
    if action == "append_sheet_rows":
        updated_rows = int(data.get("updated_rows") or 0)
        spreadsheet_id = str(data.get("spreadsheet_id") or "").strip()
        return f"Appended {updated_rows} row(s) to Google Sheet {spreadsheet_id}."
    if action == "send_gmail_notice":
        gmail = dict(data.get("gmail") or {})
        return f"Gmail notice sent ({str(gmail.get('id') or '').strip() or 'message queued'})."
    return message or "Workspace action completed."


def _build_control_plane_state(
    *,
    task_intake: TaskIntakeSpec,
    ask_contract: AskContract,
    scenario_pack: dict[str, Any] | None,
    lane_policy: dict[str, Any] | None,
    requested_execution_profile: str,
    parser_fallback_used: bool,
) -> dict[str, Any]:
    effective_execution_profile = str(task_intake.execution_profile or "").strip() or "default"
    task_context = dict(task_intake.context or {})
    payload = {
        "requested_execution_profile": str(requested_execution_profile or "").strip() or effective_execution_profile,
        "effective_execution_profile": effective_execution_profile,
        "contract_source": str(ask_contract.contract_source or ""),
        "contract_completeness": float(ask_contract.contract_completeness or 0.0),
        "acceptance": dict(task_intake.acceptance.to_dict()),
        "evidence_required": dict(task_intake.evidence_required.to_dict()),
        "scenario_pack": dict(summarize_scenario_pack(scenario_pack) or {}),
        "parser_fallback_used": bool(parser_fallback_used),
    }
    if lane_policy:
        payload["lane_policy"] = dict(lane_policy)
    knowledge_ingress = dict(task_context.get("planning_knowledge_ingress") or {})
    if knowledge_ingress:
        payload["knowledge_ingress"] = knowledge_ingress
    return payload


def _scenario_pack_payload(pack: Any) -> dict[str, Any]:
    payload = dict(summarize_scenario_pack(pack) or {})
    if pack is None:
        return payload
    source = pack.to_dict() if hasattr(pack, "to_dict") else dict(pack or {})
    clarify_questions = [str(question).strip() for question in list(source.get("clarify_questions") or []) if str(question).strip()]
    if clarify_questions:
        payload["clarify_questions"] = clarify_questions
    watch_policy = source.get("watch_policy")
    if isinstance(watch_policy, dict) and watch_policy:
        payload["watch_policy"] = dict(watch_policy)
    return payload


def _scenario_pack_runtime_payload(pack: Any, *, lane_policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = _scenario_pack_payload(pack)
    if pack is None:
        if lane_policy:
            payload["lane_policy"] = dict(lane_policy)
        return payload
    source = pack.to_dict() if hasattr(pack, "to_dict") else dict(pack or {})
    for key in ("acceptance", "evidence_required", "provider_hints"):
        value = source.get(key)
        if isinstance(value, dict) and value:
            payload[key] = dict(value)
    review_rubric = [str(item).strip() for item in list(source.get("review_rubric") or []) if str(item).strip()]
    if review_rubric:
        payload["review_rubric"] = review_rubric
    prompt_template_override = str(source.get("prompt_template_override") or "").strip()
    if prompt_template_override:
        payload["prompt_template_override"] = prompt_template_override
    intent_top = str(source.get("intent_top") or "").strip()
    if intent_top:
        payload["intent_top"] = intent_top
    funnel_profile = str(source.get("funnel_profile") or "").strip()
    if funnel_profile:
        payload["funnel_profile"] = funnel_profile
    if lane_policy:
        payload["lane_policy"] = dict(lane_policy)
    return payload


def _build_clarify_diagnostics(
    *,
    session_id: str,
    message: str,
    ask_contract: AskContract,
    strategy_plan: AskStrategyPlan,
    execution_profile: str,
) -> dict[str, Any]:
    missing_fields = _missing_contract_fields(ask_contract)
    recommended_patch = _recommended_contract_patch(ask_contract, missing_fields=missing_fields)
    recommended_resubmit_payload: dict[str, Any] = {
        "session_id": session_id,
        "message": message,
        "contract_patch": dict(recommended_patch),
    }
    if str(execution_profile or "").strip():
        recommended_resubmit_payload["execution_profile"] = str(execution_profile).strip()
    return {
        "missing_fields": missing_fields,
        "contract_completeness": float(ask_contract.contract_completeness or 0.0),
        "clarify_gate_reason": str(strategy_plan.clarify_reason_code or ""),
        "clarify_reason_detail": str(strategy_plan.clarify_reason or ""),
        "recommended_contract_patch": recommended_patch,
        "recommended_resubmit_payload": recommended_resubmit_payload,
    }


def _augment_agent_response(
    response: dict[str, Any],
    *,
    task_intake: TaskIntakeSpec,
    ask_contract: AskContract,
    scenario_pack: dict[str, Any] | None,
    control_plane: dict[str, Any],
    clarify_diagnostics: dict[str, Any] | None = None,
    runtime: Any = None,
    account_id: str = "",
    thread_id: str = "",
    agent_id: str = "",
    role_id: str = "",
    trace_id: str = "",
    planning_task_store: MeetingTaskStore | None = None,
) -> dict[str, Any]:
    payload = dict(response)
    if str(task_intake.task_id or "").strip():
        payload["task_id"] = str(task_intake.task_id or "").strip()
    payload["task_intake"] = task_intake.to_dict()
    payload["scenario_pack"] = dict(summarize_scenario_pack(scenario_pack) or {})
    planning_task = dict(control_plane.get("planning_task") or {})
    execution_layer = _planning_execution_layer_payload(
        lane_policy=dict(control_plane.get("lane_policy") or {}),
        execution_request=dict(control_plane.get("execution_request") or {}),
        provider_request=dict(dict(payload.get("provenance") or {}).get("provider_selection") or {}),
        final_provider=str(dict(payload.get("provenance") or {}).get("final_provider") or ""),
    )
    if execution_layer:
        control_plane["execution_layer"] = dict(execution_layer)
        if planning_task:
            planning_task = _project_execution_layer_on_planning_task(
                control_plane.get("planning_task") or planning_task,
                execution_layer=execution_layer,
            )
            control_plane["planning_task"] = dict(planning_task)
    quality_gate = _planning_quality_gate_payload(
        task_intake=task_intake,
        scenario_pack=scenario_pack,
        planning_task=planning_task,
        response=payload,
        execution_layer=execution_layer,
    )
    if quality_gate:
        control_plane["quality_gate"] = dict(quality_gate)
        payload["quality_gate"] = dict(quality_gate)
        if planning_task:
            planning_task = dict(control_plane.get("planning_task") or planning_task)
            planning_task["quality_gate"] = dict(quality_gate)
            control_plane["planning_task"] = dict(planning_task)
        if (
            str(quality_gate.get("watch_checkpoint") or "").strip().lower() == "quality_gate"
            and str(payload.get("status") or "").strip().lower() == "completed"
            and not bool(quality_gate.get("pass"))
        ):
            missing_sections = [str(item).strip() for item in list(quality_gate.get("missing_sections") or []) if str(item).strip()]
            repair_hint = "当前结果还不够直接可用，请沿用同一 task_id 继续补齐结构后再交付。"
            if missing_sections:
                repair_hint = (
                    "当前结果还不够直接可用，请沿用同一 task_id 补齐这些缺口后再交付："
                    + ", ".join(missing_sections[:5])
                )
            payload["status"] = "needs_followup"
            payload["next_action"] = {
                "type": "same_session_repair",
                "safe_hint": repair_hint,
                "reason": "planning_quality_gate_failed",
                "missing_sections": missing_sections[:5],
                **({"task_id": str(payload.get("task_id") or "")} if str(payload.get("task_id") or "").strip() else {}),
            }
            quality_gate["pass"] = False
            quality_gate["status_override"] = "needs_followup"
            quality_gate["status_override_reason"] = "planning_quality_gate_failed"
            control_plane["quality_gate"] = dict(quality_gate)
            payload["quality_gate"] = dict(quality_gate)
            if planning_task:
                planning_task = dict(control_plane.get("planning_task") or planning_task)
                planning_task["quality_gate"] = dict(quality_gate)
                control_plane["planning_task"] = dict(planning_task)
    if planning_task:
        synced_planning_task = _sync_planning_task_after_response(
            planning_task_store=planning_task_store,
            planning_task=planning_task,
            response=payload,
            task_intake=task_intake,
        )
        if synced_planning_task:
            planning_task = dict(synced_planning_task)
            if quality_gate:
                planning_task["quality_gate"] = dict(quality_gate)
            control_plane["planning_task"] = dict(planning_task)
    if planning_task:
        planning_memory_writeback = _maybe_writeback_planning_work_memory(
            runtime=runtime,
            task_intake=task_intake,
            task_layer=planning_task,
            response=payload,
            account_id=str(account_id or "").strip() or str(task_intake.account_id or "").strip(),
            thread_id=str(thread_id or "").strip() or str(task_intake.thread_id or "").strip(),
            agent_id=str(agent_id or "").strip() or str(task_intake.agent_id or "").strip(),
            role_id=str(role_id or "").strip() or str(task_intake.role_id or "").strip(),
            trace_id=str(trace_id or payload.get("trace_id") or "").strip(),
        )
        if planning_memory_writeback:
            control_plane["memory_writeback"] = dict(planning_memory_writeback)
            payload["planning_memory_writeback"] = dict(planning_memory_writeback)
            durable_receipt = _planning_memory_writeback_receipt(planning_memory_writeback)
            if durable_receipt:
                planning_task_payload = dict(control_plane.get("planning_task") or planning_task)
                checkpoint_patch = {"memory_writeback_receipt": durable_receipt}
                persisted_task: dict[str, Any] | None = None
                if planning_task_store is not None:
                    persisted_task = planning_task_store.update_checkpoint(
                        str(planning_task_payload.get("task_id") or ""),
                        status=str(payload.get("status") or ""),
                        answer=str(payload.get("answer") or ""),
                        next_action=dict(payload.get("next_action") or {}),
                        source_materials=list(task_intake.attachments or []),
                        surface="agent_v3",
                        session_id=str(payload.get("session_id") or task_intake.session_id or "").strip(),
                        artifact_refs=_planning_response_artifact_refs(payload),
                        checkpoint_patch=checkpoint_patch,
                    )
                if persisted_task is None:
                    checkpoint = dict(planning_task_payload.get("checkpoint") or {})
                    checkpoint["memory_writeback_receipt"] = dict(durable_receipt)
                    planning_task_payload["checkpoint"] = checkpoint
                    persisted_task = enrich_planning_task_payload(planning_task_payload)
                original_resolution = str(planning_task_payload.get("resolution") or "").strip()
                original_reason = str(planning_task_payload.get("reason") or "").strip()
                if original_resolution:
                    persisted_task["resolution"] = original_resolution
                if original_reason:
                    persisted_task["reason"] = original_reason
                if execution_layer:
                    persisted_task = _project_execution_layer_on_planning_task(
                        persisted_task,
                        execution_layer=execution_layer,
                    )
                control_plane["planning_task"] = dict(persisted_task)
                planning_task = dict(persisted_task)
    payload["control_plane"] = dict(control_plane)
    if planning_task:
        payload["planning_task"] = dict(control_plane.get("planning_task") or planning_task)
    if clarify_diagnostics:
        payload["clarify_diagnostics"] = dict(clarify_diagnostics)
        next_action = dict(payload.get("next_action") or {})
        next_action["clarify_diagnostics"] = dict(clarify_diagnostics)
        payload["next_action"] = next_action
    return _finalize_public_agent_surface(payload)


def _contract_patch_payload(patch: Any) -> dict[str, Any]:
    if not isinstance(patch, dict):
        return {}
    if isinstance(patch.get("task_intake"), dict):
        return dict(patch.get("task_intake") or {})
    return dict(patch)


def _contract_patch_contract_fields(patch: Any) -> dict[str, Any]:
    source = _contract_patch_payload(patch)
    if not source:
        return {}
    allowed = {
        "objective",
        "decision_to_support",
        "audience",
        "constraints",
        "available_inputs",
        "missing_inputs",
        "output_shape",
        "risk_class",
        "opportunity_cost",
        "task_template",
    }
    return {key: value for key, value in source.items() if key in allowed and value is not None}


def make_v3_agent_router() -> APIRouter:
    _api_key = os.environ.get("OPENMIND_API_KEY", "")
    _bearer_token = os.environ.get("CHATGPTREST_API_TOKEN", "")
    _auth_mode = os.environ.get("OPENMIND_AUTH_MODE", "strict")

    _rate_limits: dict[str, list[float]] = {}
    _rate_window = 60.0
    _rate_max = int(os.environ.get("OPENMIND_RATE_LIMIT", "10"))

    def _check_rate_limit(client_ip: str) -> bool:
        now = time.time()
        window = _rate_limits.get(client_ip, [])
        window = [t for t in window if now - t < _rate_window]
        if len(window) >= _rate_max:
            return False
        window.append(now)
        _rate_limits[client_ip] = window
        return True

    async def _require_agent_auth(request: Request) -> None:
        if request.url.path.endswith("/health"):
            return

        api_key = request.headers.get("X-Api-Key", "")
        bearer = request.headers.get("Authorization", "")
        bearer_token = ""
        if bearer.startswith("Bearer "):
            bearer_token = bearer[7:].strip()

        if _api_key and api_key == _api_key:
            return
        if _bearer_token and bearer_token == _bearer_token:
            return

        if not _api_key and not _bearer_token:
            raise HTTPException(
                status_code=503,
                detail="API key not configured: neither OPENMIND_API_KEY nor CHATGPTREST_API_TOKEN is set",
            )

        if _auth_mode == "strict":
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    async def _require_agent_rate_limit(request: Request) -> None:
        if request.url.path.endswith("/health"):
            return
        from chatgptrest.api.client_ip import get_client_ip

        client_ip = get_client_ip(request)
        if not _check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429,
                detail={"error": "Rate limit exceeded", "limit": f"{_rate_max} req/{int(_rate_window)}s"},
            )

    router = APIRouter(
        prefix="/v3/agent",
        tags=["agent-v3"],
        dependencies=[Depends(_require_agent_auth), Depends(_require_agent_rate_limit)],
    )

    _session_store = AgentSessionStore.from_env()
    _planning_task_store = MeetingTaskStore.from_env()
    _store_lock = threading.RLock()

    def _safe_context_text_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        if not isinstance(value, (list, tuple, set)):
            return []
        seen: set[str] = set()
        results: list[str] = []
        for item in value:
            if item is None or isinstance(item, (list, tuple, set, dict)):
                continue
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            results.append(text)
        return results

    def _planning_material_action_from_preflight(
        *,
        status: str,
        ready_count: int,
        pending_count: int,
        required_actions: Sequence[str],
    ) -> tuple[str, str]:
        normalized_status = str(status or "").strip().lower()
        actions = [str(item).strip() for item in list(required_actions or []) if str(item).strip()]
        if normalized_status == "ready":
            summary = f"All attached materials are directly reviewable (ready={ready_count})."
            return "ready", summary
        if normalized_status == "mixed":
            summary = (
                f"Some attached materials still need preprocessing (ready={ready_count}; pending={pending_count}); "
                "continue with the ready subset first."
            )
            if actions:
                summary += " Required actions: " + ", ".join(actions) + "."
            return "advisory_continue", summary
        if normalized_status == "preflight_required":
            summary = f"All attached materials currently require preprocessing before deep execution (pending={pending_count})."
            if actions:
                summary += " Required actions: " + ", ".join(actions) + "."
            return "preflight_blocked", summary
        if normalized_status == "none":
            return "no_materials", "No source materials are attached yet."
        if normalized_status:
            summary = f"Material preflight status is {normalized_status}."
            if actions:
                summary += " Required actions: " + ", ".join(actions) + "."
            return "unknown", summary
        return "", ""

    def _planning_material_action_contract_from_preflight(
        *,
        status: str,
        ready_count: int,
        pending_count: int,
    ) -> tuple[str, str]:
        del ready_count
        normalized_status = str(status or "").strip().lower()
        if normalized_status in {"", "none", "ready"}:
            return "continue", "materials_ready_or_absent"
        if normalized_status == "mixed" and pending_count > 0:
            return "preprocess_first", "mixed_materials_require_preflight"
        if normalized_status == "preflight_required" and pending_count > 0:
            return "blocked", "all_materials_require_preflight"
        if normalized_status:
            return "preprocess_first", "material_preflight_status_unknown"
        return "", ""

    def _planning_checkpoint_seed(task_intake: TaskIntakeSpec, *, message: str) -> dict[str, Any]:
        planning_context = dict(task_intake.context or {})
        output_target = str(
            planning_context.get("current_output_target")
            or planning_context.get("output_target")
            or ""
        ).strip()
        if not output_target:
            output_shape = str(task_intake.output_shape or "").strip()
            if output_shape and output_shape not in {"other", "text_answer", "brief_answer"}:
                output_target = output_shape
        attachment_inventory = dict(planning_context.get("attachment_inventory") or {})
        preflight = dict(attachment_inventory.get("preflight") or {})
        flagged_items = [
            f"{str(item.get('path') or '').strip()} -> {str(item.get('required_action') or '').strip()}"
            for item in list(preflight.get("flagged_items") or [])
            if str(item.get("path") or "").strip() and str(item.get("required_action") or "").strip()
        ]
        material_families = _safe_context_text_list(preflight.get("material_families"))
        required_actions = _safe_context_text_list(preflight.get("required_actions"))
        status = str(preflight.get("status") or "").strip()
        ready_count = int(preflight.get("direct_review_ready_files") or 0)
        pending_count = int(preflight.get("preflight_required_files") or 0)
        preflight_summary = ""
        if status:
            preflight_summary = f"status={status}; ready={ready_count}; pending={pending_count}"
            if material_families:
                preflight_summary += "; families=" + ", ".join(material_families)
        action_posture, action_summary = _planning_material_action_from_preflight(
            status=status,
            ready_count=ready_count,
            pending_count=pending_count,
            required_actions=required_actions,
        )
        action_contract, action_reason = _planning_material_action_contract_from_preflight(
            status=status,
            ready_count=ready_count,
            pending_count=pending_count,
        )
        return {
            "task_title": str(
                planning_context.get("planning_task_title")
                or planning_context.get("task_title")
                or ""
            ).strip(),
            "project_or_topic_ref": str(
                planning_context.get("project_or_topic_ref")
                or planning_context.get("project_ref")
                or planning_context.get("topic_ref")
                or ""
            ).strip(),
            "current_objective": str(message or task_intake.objective or "").strip(),
            "current_output_target": output_target,
            "decision_summary": str(planning_context.get("decision_summary") or "").strip(),
            "confirmed_scope": _safe_context_text_list(planning_context.get("confirmed_scope")),
            "open_questions": _safe_context_text_list(planning_context.get("open_questions")),
            "next_actions": _safe_context_text_list(planning_context.get("next_actions")),
            "memory_writeback_candidates": _safe_context_text_list(
                planning_context.get("memory_writeback_candidates")
            ),
            "artifact_refs": _safe_context_text_list(planning_context.get("artifact_refs")),
            "source_material_preflight_status": status,
            "source_material_preflight_summary": preflight_summary,
            "source_material_action_posture": action_posture,
            "source_material_action_summary": action_summary,
            "source_material_action_contract": action_contract,
            "source_material_action_reason": action_reason,
            "source_material_families": material_families,
            "source_material_required_actions": required_actions,
            "source_material_pending_items": flagged_items,
        }

    def _planning_source_material_policy(task_layer: Mapping[str, Any] | None) -> dict[str, Any]:
        checkpoint = dict((task_layer or {}).get("checkpoint") or {})
        if not checkpoint:
            return {}
        action_contract = str(checkpoint.get("source_material_action_contract") or "").strip()
        action_reason = str(checkpoint.get("source_material_action_reason") or "").strip()
        action_posture = str(checkpoint.get("source_material_action_posture") or "").strip()
        summary = str(
            checkpoint.get("source_material_action_summary")
            or checkpoint.get("source_material_preflight_summary")
            or ""
        ).strip()
        if not any([action_contract, action_reason, action_posture, summary]):
            return {}
        return {
            "preflight_status": str(checkpoint.get("source_material_preflight_status") or "").strip(),
            "action_posture": action_posture,
            "action_contract": action_contract,
            "action_reason": action_reason,
            "summary": summary,
            "families": _safe_context_text_list(checkpoint.get("source_material_families")),
            "required_actions": _safe_context_text_list(checkpoint.get("source_material_required_actions")),
            "pending_items": _safe_context_text_list(checkpoint.get("source_material_pending_items")),
        }

    def _maybe_resolve_planning_task_layer(
        *,
        task_intake: TaskIntakeSpec,
        scenario_pack: dict[str, Any] | None,
        session_id: str,
        account_id: str,
        thread_id: str,
        user_id: str,
        agent_id: str,
        message: str,
    ) -> dict[str, Any] | None:
        task_type = resolve_planning_task_type(
            task_intake=task_intake,
            scenario_pack=scenario_pack,
            context=task_intake.context,
        )
        if not task_type:
            return None
        planning_context = dict(task_intake.context or {})
        try:
            task_layer = _planning_task_store.resolve_task(
                task_type=task_type,
                explicit_task_id=str(task_intake.task_id or "").strip(),
                action_hint=str(planning_context.get("planning_task_action") or "").strip(),
                objective=message,
                source_materials=list(task_intake.attachments or []),
                session_id=session_id,
                account_id=account_id,
                thread_id=thread_id,
                user_id=user_id,
                agent_id=agent_id,
                surface=str(task_intake.source or "agent_v3"),
                checkpoint_seed=_planning_checkpoint_seed(task_intake, message=message),
            )
        except PlanningTaskResolutionError as exc:
            normalized_reason = str(exc.reason or "").strip()
            if normalized_reason == "planning_task_contract_mismatch":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "ok": False,
                        "error": normalized_reason,
                        "task_id": exc.task_id,
                        "hint": "Use planning_task_action=branch when the output target or planning task type changes.",
                    },
                ) from exc
            raise HTTPException(
                status_code=404,
                detail={"ok": False, "error": normalized_reason or "planning_task_not_found", "task_id": exc.task_id},
            ) from exc
        task_id = str(task_layer.get("task_id") or "").strip()
        if task_id:
            task_intake.task_id = task_id
            planning_context["planning_task_type"] = str(task_layer.get("task_type") or task_type)
            planning_context["planning_task_id"] = task_id
            planning_context["task_id"] = task_id
            planning_context["logical_task_id"] = task_id
            task_intake.context = planning_context
        return task_layer

    def _maybe_update_planning_task_layer(
        task_layer: dict[str, Any] | None,
        *,
        status: str,
        answer: str,
        next_action: dict[str, Any] | None,
        task_intake: TaskIntakeSpec,
        session_id: str,
        artifact_refs: list[str] | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(task_layer, dict):
            return None
        task_id = str(task_layer.get("task_id") or "").strip()
        if not task_id:
            return None
        updated = _planning_task_store.update_checkpoint(
            task_id,
            status=status,
            answer=answer,
            next_action=next_action,
            source_materials=list(task_intake.attachments or []),
            surface="agent_v3",
            session_id=session_id,
            artifact_refs=artifact_refs or [],
            checkpoint_patch=_planning_checkpoint_seed(
                task_intake,
                message=str(task_intake.objective or ""),
            ),
        )
        if updated is not None:
            updated["resolution"] = str(task_layer.get("resolution") or updated.get("resolution") or "continue")
            updated["reason"] = str(task_layer.get("reason") or updated.get("reason") or "")
            task_type = str(task_layer.get("task_type") or "").strip().lower()
            if task_type:
                task_intake.context["planning_task_type"] = task_type
            task_intake.context["planning_task_id"] = task_id
            task_intake.context["task_id"] = task_id
            task_intake.context["logical_task_id"] = task_id
        return updated

    def _restore_task_intake_spec(
        task_intake_payload: Mapping[str, Any],
        *,
        fallback_session_id: str,
        trace_prefix: str,
    ) -> TaskIntakeSpec | None:
        payload = dict(task_intake_payload or {})
        if not payload:
            return None
        try:
            return TaskIntakeSpec(**payload)
        except Exception:
            try:
                return build_task_intake_spec(
                    ingress_lane=str(payload.get("ingress_lane") or "agent_v3"),
                    default_source=str(payload.get("source") or "openclaw"),
                    raw_source=str(payload.get("source") or ""),
                    raw_task_intake=payload,
                    message=str(payload.get("objective") or ""),
                    question=str(payload.get("objective") or ""),
                    goal_hint=str(payload.get("goal_hint") or ""),
                    execution_profile=str(payload.get("execution_profile") or ""),
                    trace_id=str(payload.get("trace_id") or f"{trace_prefix}-{uuid.uuid4().hex[:12]}"),
                    session_id=str(payload.get("session_id") or fallback_session_id),
                    user_id=str(payload.get("user_id") or ""),
                    account_id=str(payload.get("account_id") or ""),
                    thread_id=str(payload.get("thread_id") or ""),
                    agent_id=str(payload.get("agent_id") or ""),
                    role_id=str(payload.get("role_id") or ""),
                    context=dict(payload.get("context") or {}),
                    attachments=list(payload.get("attachments") or []),
                    client_name="openclaw-advisor",
                )
            except Exception:
                return None

    def _maybe_cancel_planning_task_layer_for_session(
        session: Mapping[str, Any],
        *,
        session_id: str,
        next_action: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        control_plane = dict(session.get("control_plane") or {})
        task_layer = dict(control_plane.get("planning_task") or {})
        if not task_layer:
            task_intake_payload = dict(session.get("task_intake") or {})
            task_id = str(
                session.get("task_id")
                or task_intake_payload.get("task_id")
                or dict(task_intake_payload.get("context") or {}).get("planning_task_id")
                or ""
            ).strip()
            if task_id:
                task_layer = dict(_planning_task_store.get_public(task_id) or {})
        if not task_layer:
            return None
        task_intake = _restore_task_intake_spec(
            dict(session.get("task_intake") or {}),
            fallback_session_id=session_id,
            trace_prefix="planning-cancel",
        )
        if task_intake is None:
            logger.warning("planning task cancel sync skipped: invalid task_intake for session %s", session_id)
            return None
        if not task_intake.attachments:
            task_intake.attachments = list(dict(task_layer.get("checkpoint") or {}).get("source_materials") or [])
        try:
            return _maybe_update_planning_task_layer(
                task_layer,
                status="cancelled",
                answer=str(session.get("last_answer") or ""),
                next_action=dict(next_action or {}),
                task_intake=task_intake,
                session_id=session_id,
                artifact_refs=_planning_artifact_refs_from_session(session),
            )
        except Exception:
            logger.warning(
                "planning task cancel sync failed for task %s session %s",
                str(task_layer.get("task_id") or ""),
                session_id,
                exc_info=True,
            )
            return None

    def _planning_artifact_refs_from_session(session: Mapping[str, Any]) -> list[str]:
        refs: list[str] = []
        for item in list(session.get("artifacts") or []):
            if not isinstance(item, Mapping):
                continue
            ref = str(item.get("uri") or item.get("path") or "").strip()
            if ref:
                refs.append(ref)
        return refs

    def _planning_public_status(status: str) -> str:
        normalized = str(status or "").strip().lower()
        if normalized == "completed":
            return "completed"
        if normalized in {"needs_followup", "needs_input"}:
            return "awaiting_input"
        if normalized == "failed":
            return "needs_attention"
        if normalized == "cancelled":
            return "cancelled"
        return "active"

    def _planning_checkpoint_state(status: str) -> str:
        normalized = str(status or "").strip().lower()
        if normalized in {"completed", "failed", "needs_followup", "needs_input", "running", "cancelled"}:
            return normalized
        return "intake_received"

    def _planning_clip_output(answer: str) -> str:
        text = str(answer or "").strip()
        if len(text) <= 1200:
            return text
        return f"{text[:1199].rstrip()}…"

    def _planning_mode(task_intake: TaskIntakeSpec, scenario_pack: Mapping[str, Any] | None = None) -> str:
        del task_intake
        source = dict(scenario_pack or {}) if isinstance(scenario_pack, Mapping) else {}
        provider_hints = dict(source.get("provider_hints") or {})
        return str(provider_hints.get("planning_mode") or "").strip().lower()

    def _planning_profile(task_intake: TaskIntakeSpec, scenario_pack: Mapping[str, Any] | None = None) -> str:
        del task_intake
        source = dict(scenario_pack or {}) if isinstance(scenario_pack, Mapping) else {}
        profile = str(source.get("profile") or "").strip().lower()
        if profile:
            return profile
        provider_hints = dict(source.get("provider_hints") or {})
        return str(provider_hints.get("planning_profile") or "").strip().lower()

    def _strip_compact_item_prefix(line: str) -> str:
        raw = str(line or "").strip()
        if not raw:
            return ""
        for prefix in ("- ", "* ", "• "):
            if raw.startswith(prefix):
                return raw[len(prefix):].strip()
        idx = 0
        while idx < len(raw) and raw[idx].isdigit():
            idx += 1
        if idx and idx < len(raw) and raw[idx] in {".", ")", "、", "．"}:
            tail = raw[idx + 1 :].strip()
            if tail:
                return tail
        return raw

    def _is_compact_answer_heading(line: str) -> bool:
        raw = str(line or "").strip()
        if not raw:
            return False
        trimmed = raw.strip().strip(":：- ").strip()
        if trimmed.lower() in {"answer", "response"}:
            return True
        return trimmed in {"答案", "回答"}

    def _planning_count_list_lines(text: str) -> int:
        count = 0
        for raw in str(text or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith(("- ", "* ", "• ")):
                count += 1
                continue
            idx = 0
            while idx < len(line) and line[idx].isdigit():
                idx += 1
            if idx and idx < len(line) and line[idx] in {".", ")", "、", "．"}:
                count += 1
        return count

    def _planning_normalize_answer(
        answer: str,
        *,
        task_intake: TaskIntakeSpec,
        scenario_pack: Mapping[str, Any] | None = None,
    ) -> str:
        text = str(answer or "").strip()
        if not text:
            return ""
        if _planning_mode(task_intake, scenario_pack) != "compact_next_steps":
            return text
        if _planning_profile(task_intake, scenario_pack) != "implementation_plan":
            return text
        if text.startswith("```"):
            return text
        lines = [str(item).strip() for item in text.splitlines() if str(item).strip()]
        if lines and _is_compact_answer_heading(lines[0]):
            lines = lines[1:]
            text = "\n".join(lines).strip()
        if not text:
            return ""
        if _planning_count_list_lines(text) >= 3:
            return text
        if len(lines) != 3:
            return text
        normalized_items: list[str] = []
        for line in lines:
            item = _strip_compact_item_prefix(line)
            if not item:
                return text
            normalized_items.append(f"- {item}")
        return "\n".join(normalized_items)

    def _planning_normalize_refs(values: Any) -> list[str]:
        refs: list[str] = []
        for item in list(values or []):
            ref = str(item or "").strip()
            if ref:
                refs.append(ref)
        return refs

    def _planning_read_semantics(*, refresh: bool, surface: str) -> dict[str, Any]:
        if refresh:
            return _planning_query_read_semantics(
                surface=surface,
                read_mode="stateful_runtime_refresh",
                writes_back_on_divergence=True,
                authority="planning_task_store+session_refresh",
            )
        return _planning_query_read_semantics(
            surface=surface,
            read_mode="snapshot_only",
            writes_back_on_divergence=False,
            authority="planning_task_store",
        )

    def _planning_task_requires_visibility_refresh(task_payload: Mapping[str, Any]) -> bool:
        latest_session_id = str(task_payload.get("latest_session_id") or "").strip()
        if not latest_session_id:
            return False
        checkpoint = dict(task_payload.get("checkpoint") or {})
        record_status = str(task_payload.get("status") or "").strip().lower()
        checkpoint_state = str(checkpoint.get("current_state") or "").strip().lower()
        if record_status in {"active", "awaiting_input"}:
            return True
        if checkpoint_state in {"intake_received", "running"}:
            return True
        return False

    def _planning_task_visibility_needs_writeback(
        task_payload: Mapping[str, Any],
        *,
        status: str,
        answer: str,
        session_id: str,
        artifact_refs: list[str],
    ) -> bool:
        checkpoint = dict(task_payload.get("checkpoint") or {})
        expected_status = _planning_public_status(status)
        expected_state = _planning_checkpoint_state(status)
        current_status = str(task_payload.get("status") or "").strip().lower()
        current_state = str(checkpoint.get("current_state") or "").strip().lower()
        current_checkpoint_status = str(checkpoint.get("current_status") or "").strip().lower()
        current_session_id = str(
            task_payload.get("latest_session_id")
            or checkpoint.get("last_session_id")
            or ""
        ).strip()
        current_output = str(checkpoint.get("latest_output") or "").strip()
        current_artifact_refs = _planning_normalize_refs(
            checkpoint.get("current_artifact_refs") or checkpoint.get("artifact_refs")
        )
        expected_output = _planning_clip_output(answer)
        expected_artifact_refs = _planning_normalize_refs(artifact_refs)
        if current_status != expected_status:
            return True
        if current_state != expected_state or current_checkpoint_status != expected_state:
            return True
        if session_id and current_session_id != session_id:
            return True
        if expected_output and current_output != expected_output:
            return True
        if expected_artifact_refs and current_artifact_refs != expected_artifact_refs:
            return True
        return False

    def _maybe_refresh_planning_task_visibility(task_payload: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(task_payload or {})
        latest_session_id = str(payload.get("latest_session_id") or "").strip()
        if not latest_session_id:
            return payload
        session = _session_copy(latest_session_id)
        if not session:
            return payload
        refreshed_session = _refresh_session_state(dict(session))
        projected_execution_layer = _execution_layer_from_session(refreshed_session)
        if not _planning_task_requires_visibility_refresh(payload):
            if projected_execution_layer:
                return _project_execution_layer_on_planning_task(
                    payload,
                    execution_layer=projected_execution_layer,
                )
            return payload
        task_intake_payload = dict(refreshed_session.get("task_intake") or {})
        if not task_intake_payload:
            return payload
        task_intake = _restore_task_intake_spec(
            task_intake_payload,
            fallback_session_id=str(refreshed_session.get("session_id") or latest_session_id),
            trace_prefix="planning-refresh",
        )
        if task_intake is None:
            logger.warning("planning task visibility refresh skipped: invalid task_intake for session %s", latest_session_id)
            return payload
        if not task_intake.attachments:
            task_intake.attachments = list(dict(payload.get("checkpoint") or {}).get("source_materials") or [])
        refreshed_status = str(refreshed_session.get("status") or "")
        refreshed_answer = str(refreshed_session.get("last_answer") or "")
        refreshed_artifact_refs = _planning_artifact_refs_from_session(refreshed_session)
        if not _planning_task_visibility_needs_writeback(
            payload,
            status=refreshed_status,
            answer=refreshed_answer,
            session_id=latest_session_id,
            artifact_refs=refreshed_artifact_refs,
        ):
            if projected_execution_layer:
                return _project_execution_layer_on_planning_task(
                    payload,
                    execution_layer=projected_execution_layer,
                )
            return payload
        try:
            updated = _maybe_update_planning_task_layer(
                payload,
                status=refreshed_status,
                answer=refreshed_answer,
                next_action=dict(refreshed_session.get("next_action") or {}),
                task_intake=task_intake,
                session_id=latest_session_id,
                artifact_refs=refreshed_artifact_refs,
            )
        except Exception:
            logger.warning(
                "planning task visibility refresh failed for task %s session %s",
                str(payload.get("task_id") or ""),
                latest_session_id,
                exc_info=True,
            )
            return payload
        refreshed_payload = dict(updated or payload)
        if projected_execution_layer:
            refreshed_payload = _project_execution_layer_on_planning_task(
                refreshed_payload,
                execution_layer=projected_execution_layer,
            )
        return refreshed_payload

    def _append_session_event(session_id: str, event_type: str, **payload: Any) -> dict[str, Any]:
        with _store_lock:
            seq = int(_session_store.latest_event_seq(session_id)) + 1
            event = {
                "seq": seq,
                "type": event_type,
                "session_id": session_id,
                "ts": time.time(),
            }
            event.update(payload)
            stored = _session_store.append_event(session_id, event)
        if str(event_type).startswith("session."):
            session = _session_copy(session_id) or {}
            telemetry_data = {
                "status": str(stored.get("status") or session.get("status") or ""),
                "route": str(stored.get("route") or session.get("route") or ""),
                "run_id": str(stored.get("run_id") or session.get("run_id") or ""),
                "job_id": str(stored.get("job_id") or session.get("job_id") or ""),
                "consultation_id": str(stored.get("consultation_id") or session.get("consultation_id") or ""),
                "answer_chars": int(stored.get("answer_chars") or len(str(session.get("last_answer") or "")) or 0),
                "event_seq": int(stored.get("seq") or 0),
                "event_ts": float(stored.get("ts") or 0.0),
            }
            if "cancelled_job_ids" in stored:
                telemetry_data["cancelled_job_ids"] = list(stored.get("cancelled_job_ids") or [])
            if "error" in stored:
                telemetry_data["error"] = str(stored.get("error") or "")
            if "error_type" in stored:
                telemetry_data["error_type"] = str(stored.get("error_type") or "")
            _emit_runtime_event(
                None,
                event_type=str(event_type),
                source="agent_v3",
                domain="agent",
                trace_id=str(stored.get("trace_id") or session.get("trace_id") or ""),
                session_id=session_id,
                run_id=telemetry_data["run_id"],
                job_id=telemetry_data["job_id"],
                repo_name="ChatgptREST",
                repo_path=_REPO_ROOT,
                agent_name="agent_v3",
                agent_source="chatgptrest.api.routes_agent_v3",
                data=telemetry_data,
            )
        return stored

    def _session_events_after(session_id: str, after_seq: int) -> list[dict[str, Any]]:
        with _store_lock:
            return [dict(item) for item in _session_store.events_after(session_id, after_seq)]

    def _session_copy(session_id: str) -> dict[str, Any] | None:
        with _store_lock:
            current = _session_store.get(session_id)
            return dict(current) if current else None

    def _upsert_session(session_id: str, **updates: Any) -> dict[str, Any]:
        with _store_lock:
            current = dict(_session_store.get(session_id) or {"session_id": session_id})
            created = "updated_at" not in current
            previous_status = str(current.get("status") or "")
            current.update(updates)
            current["updated_at"] = time.time()
            current["stream_url"] = _make_stream_url(session_id)
            _session_store.put(session_id, current)
            event_payload = {
                "status": str(current.get("status") or ""),
                "route": str(current.get("route") or ""),
                "run_id": str(current.get("run_id") or ""),
                "job_id": str(current.get("job_id") or ""),
                "consultation_id": str(current.get("consultation_id") or ""),
                "answer_chars": len(str(current.get("last_answer") or "")),
                "trace_id": str(current.get("trace_id") or ""),
            }
        if created:
            _append_session_event(session_id, "session.created", **event_payload)
        elif event_payload["status"] and event_payload["status"] != previous_status:
            _append_session_event(session_id, "session.status", **event_payload)
        return current

    def _session_status_is_terminal(status: Any) -> bool:
        return str(status or "").strip().lower() in _TERMINAL_AGENT_STATUSES

    def _refresh_session_state(session: dict[str, Any]) -> dict[str, Any]:
        # Session state must stay monotonic after the facade reaches a terminal
        # status such as cancelled. Underlying jobs may still report stale
        # snapshots for a short window, but the public lifecycle must not regress.
        if _session_status_is_terminal(session.get("status")):
            return _upsert_session(
                str(session["session_id"]),
                **{k: v for k, v in session.items() if k != "session_id"},
            )
        cfg = load_config()
        kind = str(session.get("kind") or "")
        if kind == "job" and session.get("job_id"):
            snapshot = _job_snapshot(cfg=cfg, job_id=str(session["job_id"]))
            artifacts_list: list[dict[str, Any]] = []
            if snapshot.get("conversation_url"):
                artifacts_list.append({"kind": "conversation_url", "uri": snapshot["conversation_url"]})
            session["status"] = snapshot["agent_status"]
            session["last_answer"] = snapshot.get("answer", "")
            session["artifacts"] = artifacts_list
            session["next_action"] = snapshot.get("next_action") or _default_next_action(
                status=str(snapshot["agent_status"]),
                job_id=str(snapshot["job_id"]),
            )
            for key in _PUBLIC_COMPLETION_FIELDS:
                if key in snapshot:
                    session[key] = snapshot.get(key)
                else:
                    session.pop(key, None)
        elif kind == "consult" and session.get("consultation_id"):
            snapshot = _consultation_snapshot(cfg=cfg, consultation_id=str(session["consultation_id"]))
            session["status"] = snapshot["agent_status"]
            session["last_answer"] = snapshot.get("answer", "")
            session["next_action"] = _default_next_action(status=str(snapshot["agent_status"]))
            for key in _PUBLIC_COMPLETION_FIELDS:
                session.pop(key, None)
        elif kind == "controller" and session.get("run_id"):
            controller = ControllerEngine(_advisor_runtime())
            snapshot = _controller_snapshot(
                controller,
                run_id=str(session["run_id"]),
                fallback_job_id=str(session.get("job_id") or ""),
            )
            session["status"] = snapshot["agent_status"]
            session["last_answer"] = snapshot.get("answer", "")
            session["artifacts"] = list(snapshot.get("artifacts") or [])
            session["job_id"] = snapshot.get("job_id") or session.get("job_id", "")
            session["attachment_confirmation"] = dict(snapshot.get("attachment_confirmation") or {})
        session["next_action"] = snapshot.get("next_action") or _default_next_action(
            status=str(snapshot["agent_status"]),
            job_id=str(session.get("job_id") or ""),
        )
        for key in _PUBLIC_COMPLETION_FIELDS:
            if key in snapshot:
                session[key] = snapshot.get(key)
            else:
                session.pop(key, None)
        return _upsert_session(str(session["session_id"]), **{k: v for k, v in session.items() if k != "session_id"})

    def _find_duplicate_public_agent_session(
        *,
        request: Request,
        session_id: str,
        message: str,
        task_intake: TaskIntakeSpec,
        provider_request: dict[str, Any] | None,
        client_info: dict[str, Any],
        route_hint: str,
    ) -> dict[str, Any] | None:
        if not _is_public_mcp_submission(request=request, task_intake=task_intake, client_info=client_info):
            return None
        if not _should_guard_duplicate_public_agent_submission(
            task_intake=task_intake,
            provider_request=provider_request,
            message=message,
            route_hint=route_hint,
        ):
            return None

        normalized_message = _normalize_public_agent_text(message or task_intake.objective)
        current_repo = _normalize_github_repo_ref(dict(task_intake.context or {}).get("github_repo"))
        current_provider = _canonical_provider_name(
            (provider_request or {}).get("requested_provider")
            or dict(task_intake.context or {}).get("requested_provider")
            or dict(task_intake.context or {}).get("legacy_provider")
        )
        current_goal_hint = str(task_intake.goal_hint or "").strip().lower()
        current_client_key = _public_agent_client_key(client_info)
        now = time.time()
        cutoff = now - _public_agent_duplicate_window_seconds()

        try:
            paths = sorted(
                _session_store.base_dir.glob("*.json"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            paths = list(_session_store.base_dir.glob("*.json"))

        for path in paths[:200]:
            candidate = _session_store.get(path.stem)
            if not isinstance(candidate, dict):
                continue
            if str(candidate.get("session_id") or "") == session_id:
                continue
            updated_at = float(candidate.get("updated_at") or 0.0)
            if updated_at and updated_at < cutoff:
                continue
            if str(candidate.get("status") or "").strip().lower() != "running":
                continue
            candidate_task_intake = candidate.get("task_intake")
            if not isinstance(candidate_task_intake, dict):
                continue
            candidate_context = dict(candidate_task_intake.get("context") or {})
            candidate_message = _normalize_public_agent_text(
                candidate.get("last_message") or candidate_task_intake.get("objective")
            )
            if not candidate_message or candidate_message != normalized_message:
                continue
            if str(candidate_task_intake.get("goal_hint") or "").strip().lower() != current_goal_hint:
                continue
            if current_repo and _normalize_github_repo_ref(candidate_context.get("github_repo")) != current_repo:
                continue
            candidate_provider = _canonical_provider_name(
                candidate_context.get("requested_provider") or candidate_context.get("legacy_provider")
            )
            if current_provider and candidate_provider and candidate_provider != current_provider:
                continue
            candidate_client_payload = dict(candidate_context.get("client") or candidate.get("client") or {})
            candidate_client_key = _public_agent_client_key(candidate_client_payload)
            if current_client_key:
                if not candidate_client_key or candidate_client_key != current_client_key:
                    continue
            elif not current_repo and len(normalized_message) < 240:
                continue
            return candidate
        return None

    @router.post("/turn")
    async def agent_turn(request: Request, body: dict = Body(...)):
        _enforce_client_name_allowlist(request)
        _enforce_write_trace_headers(request, operation="agent_turn")
        _enforce_public_mcp_first_direct_rest_guard(request, operation="agent_turn")
        session_id = str(body.get("session_id", "")).strip() or _make_agent_session_id()
        existing_session = _session_copy(session_id) if body.get("session_id") else None
        message = str(body.get("message", "")).strip()
        raw_task_intake_body = body.get("task_intake") if isinstance(body.get("task_intake"), dict) else None
        raw_workspace_request_body = body.get("workspace_request") if isinstance(body.get("workspace_request"), dict) else None
        contract_patch = body.get("contract_patch") if isinstance(body.get("contract_patch"), dict) else None
        contract_patch_task_intake = _contract_patch_payload(contract_patch)
        contract_patch_workspace_request = _contract_patch_workspace_request(contract_patch)
        if contract_patch and not existing_session:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "contract_patch_requires_existing_session",
                    "session_id": session_id,
                },
            )
        state = _advisor_runtime()
        delivery_mode = str(body.get("delivery_mode", "")).strip().lower()
        wait_for_answer_raw = body.get("wait_for_answer")
        if wait_for_answer_raw is False and not delivery_mode:
            delivery_mode = "deferred"
        if not delivery_mode:
            delivery_mode = "sync"
        deferred_mode = delivery_mode in {"deferred", "background", "async"}
        attachments = body.get("attachments")
        goal_hint = str(body.get("goal_hint", "")).strip().lower()
        depth = str(body.get("depth", "standard")).strip().lower()
        execution_profile = str(body.get("execution_profile", "")).strip().lower()
        context = dict(body.get("context", {}) or {})
        raw_task_intake_context = (
            dict(raw_task_intake_body.get("context") or {})
            if isinstance(raw_task_intake_body, dict) and isinstance(raw_task_intake_body.get("context"), dict)
            else {}
        )
        if raw_task_intake_context:
            merged_context = dict(raw_task_intake_context)
            merged_context.update(context)
            context = merged_context
        client_info = dict(body.get("client", {}) or {})
        timeout_seconds = _normalize_timeout(body.get("timeout_seconds"), default=300)

        file_paths = None
        if attachments:
            file_paths = coerce_file_path_input(attachments)
        if file_paths:
            context["files"] = list(file_paths)

        context["goal_hint"] = goal_hint
        context["depth"] = depth
        if execution_profile:
            context["execution_profile"] = execution_profile
        context["client"] = client_info

        intent_hint = ""
        if goal_hint in {"code_review", "research"}:
            intent_hint = "research"
        elif goal_hint == "report":
            intent_hint = "report"
        elif goal_hint == "image":
            intent_hint = "action"

        role_id = str(body.get("role_id", "")).strip()
        account_id = str(body.get("account_id", "")).strip()
        thread_id = str(body.get("thread_id", "")).strip()
        agent_id = str(body.get("agent_id", "")).strip()
        raw_memory_capture_request = body.get("memory_capture")
        user_id = str(body.get("user_id", "")).strip() or client_info.get("name", "agent")
        trace_id = str(body.get("trace_id", "")).strip() or str(uuid.uuid4())
        task_intake: TaskIntakeSpec | None = None
        planning_task_layer: dict[str, Any] | None = None
        control_plane: dict[str, Any] | None = None
        existing_workspace_request = _workspace_request_from_session(existing_session)

        def _mark_meeting_task_failed(*, error_text: str = "") -> dict[str, Any] | None:
            nonlocal planning_task_layer
            if task_intake is None:
                return None
            updated = _maybe_update_planning_task_layer(
                planning_task_layer,
                status="failed",
                answer=error_text,
                next_action=_default_next_action(status="failed"),
                task_intake=task_intake,
                session_id=session_id,
            )
            if updated is not None:
                planning_task_layer = updated
                if isinstance(control_plane, dict):
                    control_plane["planning_task"] = dict(updated)
            return updated

        def _persist_agent_turn_failure(*, error_text: str, error_type: str) -> None:
            try:
                _mark_meeting_task_failed(error_text=error_text)
            except Exception as checkpoint_exc:
                logger.error(
                    "agent_turn failure checkpoint update failed: %s",
                    checkpoint_exc,
                    exc_info=True,
                )

            failure_task_intake: dict[str, Any] | None = None
            if task_intake is not None:
                try:
                    failure_task_intake = task_intake.to_dict()
                except Exception as task_intake_exc:
                    logger.error(
                        "agent_turn failure task_intake serialization failed: %s",
                        task_intake_exc,
                        exc_info=True,
                    )

            failure_control_plane = dict(control_plane) if isinstance(control_plane, dict) else None
            try:
                _upsert_session(
                    session_id,
                    status="failed",
                    last_answer="",
                    next_action=_default_next_action(status="failed"),
                    task_intake=failure_task_intake,
                    control_plane=failure_control_plane,
                )
            except Exception as session_exc:
                logger.error(
                    "agent_turn failure session persistence failed: %s",
                    session_exc,
                    exc_info=True,
                )
                try:
                    _upsert_session(
                        session_id,
                        status="failed",
                        last_answer="",
                        next_action=_default_next_action(status="failed"),
                    )
                except Exception as minimal_session_exc:
                    logger.error(
                        "agent_turn minimal failure session persistence failed: %s",
                        minimal_session_exc,
                        exc_info=True,
                    )

            try:
                _append_session_event(
                    session_id,
                    "session.error",
                    error=error_text,
                    error_type=error_type,
                )
            except Exception as event_exc:
                logger.error(
                    "agent_turn failure event append failed: %s",
                    event_exc,
                    exc_info=True,
                )

        try:
            workspace_request = merge_workspace_request(
                existing_workspace_request,
                raw_workspace_request_body,
                trace_id=trace_id,
                session_id=session_id,
            )
            if contract_patch_workspace_request:
                workspace_request = merge_workspace_request(
                    workspace_request.to_dict() if workspace_request else None,
                    contract_patch_workspace_request,
                    trace_id=trace_id,
                    session_id=session_id,
                )
        except WorkspaceRequestValidationError as exc:
            return JSONResponse(status_code=400, content={"ok": False, **exc.detail})

        if workspace_request is not None and not message:
            workspace_control_plane = _build_workspace_control_plane(workspace_request=workspace_request)
            missing_workspace_fields = workspace_missing_fields(workspace_request)
            if missing_workspace_fields:
                diagnostics = _build_workspace_clarify_diagnostics(
                    session_id=session_id,
                    workspace_request=workspace_request,
                )
                control_plane = _build_workspace_control_plane(
                    workspace_request=workspace_request,
                    workspace_diagnostics=diagnostics,
                )
                questions = workspace_clarify_questions(workspace_request)
                clarification_message = diagnostics["clarify_reason_detail"]
                if questions:
                    clarification_message += "\n\nQuestions:\n" + "\n".join(f"- {item}" for item in questions)
                response = _build_agent_response(
                    session_id=session_id,
                    run_id=f"run_{uuid.uuid4().hex[:12]}",
                    status="needs_followup",
                    answer=clarification_message,
                    route="workspace_clarify",
                    provider_path=["google_workspace"],
                    final_provider="google_workspace",
                    next_action={
                        "type": "await_workspace_patch",
                        "status": "blocking",
                        "questions": questions,
                        "clarify_diagnostics": diagnostics,
                    },
                    recovery_state="workspace_clarify_blocked",
                    trace_id=trace_id,
                    memory_capture=_maybe_capture_agent_turn_memory(
                        runtime=state,
                        memory_capture_request=raw_memory_capture_request,
                        session_id=session_id,
                        account_id=account_id,
                        thread_id=thread_id,
                        agent_id=agent_id,
                        role_id=role_id,
                        trace_id=trace_id,
                        route="workspace_clarify",
                        answer=clarification_message,
                        message=message,
                        source_system="advisor_agent",
                        status="needs_followup",
                        next_action={
                            "type": "await_workspace_patch",
                            "status": "blocking",
                            "questions": questions,
                            "clarify_diagnostics": diagnostics,
                        },
                    ),
                )
                response["control_plane"] = control_plane
                response["workspace_request"] = workspace_request.to_dict()
                response["workspace_diagnostics"] = diagnostics
                response = _finalize_public_agent_surface(response)
                _upsert_session(
                    session_id,
                    kind="workspace",
                    run_id=str(response.get("run_id") or ""),
                    status="needs_followup",
                    route="workspace_clarify",
                    last_message="",
                    last_answer=clarification_message,
                    provenance=response.get("provenance") or {},
                    next_action=response.get("next_action") or {},
                    trace_id=trace_id,
                    control_plane=control_plane,
                )
                _append_session_event(
                    session_id,
                    "turn.workspace_clarify_required",
                    trace_id=trace_id,
                    action=workspace_request.action,
                    missing_fields=missing_workspace_fields,
                )
                return response

            workspace_control_plane = _build_workspace_control_plane(workspace_request=workspace_request)
            _upsert_session(
                session_id,
                kind="workspace",
                run_id="",
                status="running",
                route="workspace_action",
                last_message="",
                last_answer="",
                provenance={"route": "workspace_action", "provider_path": ["google_workspace"], "final_provider": "google_workspace"},
                next_action=_default_next_action(status="running"),
                delivery_mode=delivery_mode,
                trace_id=trace_id,
                control_plane=workspace_control_plane,
            )
            _append_session_event(
                session_id,
                "turn.workspace_submitted",
                trace_id=trace_id,
                action=workspace_request.action,
                deferred=bool(deferred_mode),
            )

            def _run_workspace_turn() -> dict[str, Any]:
                result = WorkspaceService().execute(workspace_request)
                result_payload = result.to_dict()
                response = _build_agent_response(
                    session_id=session_id,
                    run_id=f"run_{uuid.uuid4().hex[:12]}",
                    status=("completed" if result.ok else "failed"),
                    answer=_workspace_action_answer(result_payload),
                    route="workspace_action",
                    provider_path=["google_workspace"],
                    final_provider="google_workspace",
                    artifacts_list=list(result_payload.get("artifacts") or []),
                    recovery_state=("clean" if result.ok else "failed"),
                    trace_id=trace_id,
                )
                control_plane = _build_workspace_control_plane(
                    workspace_request=workspace_request,
                    workspace_result=workspace_action_summary(result),
                )
                response["control_plane"] = control_plane
                response["workspace_request"] = workspace_request.to_dict()
                response["workspace_result"] = result_payload
                response = _finalize_public_agent_surface(response)
                _upsert_session(
                    session_id,
                    status=response["status"],
                    last_answer=response["answer"],
                    artifacts=list(response.get("artifacts") or []),
                    next_action=response["next_action"],
                    provenance=response["provenance"],
                    trace_id=trace_id,
                    control_plane=control_plane,
                )
                if not result.ok:
                    _append_session_event(
                        session_id,
                        "session.error",
                        error=str(result.message or "workspace action failed"),
                        error_type="WorkspaceActionError",
                    )
                return response

            if deferred_mode:
                accepted = _session_response(_session_copy(session_id) or {"session_id": session_id, "status": "running"})
                accepted["accepted"] = True
                accepted["answer"] = ""
                accepted["delivery"] = {
                    "mode": "deferred",
                    "stream_url": _make_stream_url(session_id),
                }
                accepted["control_plane"] = workspace_control_plane
                accepted["workspace_request"] = workspace_request.to_dict()

                def _workspace_background_runner() -> None:
                    try:
                        response = _run_workspace_turn()
                    except Exception as exc:
                        logger.error("workspace deferred execution failed: %s", exc, exc_info=True)
                        _upsert_session(
                            session_id,
                            status="failed",
                            last_answer="",
                            next_action=_default_next_action(status="failed"),
                            control_plane=workspace_control_plane,
                        )
                        _append_session_event(
                            session_id,
                            "session.error",
                            error=str(exc)[:500],
                            error_type=type(exc).__name__,
                        )
                    else:
                        _emit_runtime_event(
                            state,
                            event_type="workspace_action.completed",
                            source="workspace_action",
                            trace_id=trace_id,
                            data={
                                "session_id": session_id,
                                "status": response.get("status"),
                                "action": workspace_request.action,
                            },
                        )

                worker = threading.Thread(
                    target=_workspace_background_runner,
                    name=f"workspace-turn-{session_id[:24]}",
                    daemon=True,
                )
                worker.start()
                return JSONResponse(status_code=202, content=_finalize_public_agent_surface(accepted, accepted=True))

            response = await run_in_threadpool(_run_workspace_turn)
            _emit_runtime_event(
                state,
                event_type="workspace_action.completed",
                source="workspace_action",
                trace_id=trace_id,
                data={
                    "session_id": session_id,
                    "status": response.get("status"),
                    "action": workspace_request.action,
                },
            )
            return response

        # === Ask Contract / Funnel Front Gate ===
        # Extract contract fields from request body
        body_contract = body.get("contract")
        if not isinstance(body_contract, dict):
            body_contract = {}
        raw_contract = dict(body_contract)
        if not raw_contract:
            # Try individual contract fields for backward compatibility
            raw_contract = {
                "objective": body.get("objective"),
                "decision_to_support": body.get("decision_to_support"),
                "audience": body.get("audience"),
                "constraints": body.get("constraints"),
                "available_inputs": body.get("available_inputs"),
                "missing_inputs": body.get("missing_inputs"),
                "output_shape": body.get("output_shape"),
                "risk_class": body.get("risk_class"),
                "opportunity_cost": body.get("opportunity_cost"),
                "task_template": body.get("task_template"),
            }
            # Filter out None values
            raw_contract = {k: v for k, v in raw_contract.items() if v is not None}
        if contract_patch and existing_session and isinstance(existing_session.get("contract"), dict):
            raw_contract = _deep_merge_dict(dict(existing_session.get("contract") or {}), raw_contract)
        patch_contract = _contract_patch_contract_fields(contract_patch)
        if patch_contract:
            raw_contract = _deep_merge_dict(raw_contract, patch_contract)

        raw_task_intake = dict(raw_task_intake_body or {})
        if contract_patch and existing_session and isinstance(existing_session.get("task_intake"), dict):
            raw_task_intake = _deep_merge_dict(dict(existing_session.get("task_intake") or {}), raw_task_intake)
        if contract_patch_task_intake:
            raw_task_intake = _deep_merge_dict(raw_task_intake, contract_patch_task_intake)
        if contract_patch and message:
            explicit_objective = bool(
                (raw_task_intake_body or {}).get("objective")
                or contract_patch_task_intake.get("objective")
                or body_contract.get("objective")
                or patch_contract.get("objective")
            )
            prior_objective = str(raw_task_intake.get("objective") or raw_contract.get("objective") or "").strip()
            if not explicit_objective and len(message) >= max(12, len(prior_objective)):
                raw_task_intake["objective"] = message
                raw_contract["objective"] = message

        if not message:
            message = str(
                raw_task_intake.get("objective")
                or raw_contract.get("objective")
                or (existing_session or {}).get("last_message")
                or ""
            ).strip()
        if not message:
            return JSONResponse(status_code=400, content={"ok": False, "error": "message is required"})
        try:
            enforce_agent_ingress_prompt_policy(
                question=message,
                allow_synthetic_prompt=bool(
                    body.get("allow_synthetic_prompt")
                    or raw_task_intake
                    or contract_patch
                ),
            )
        except PromptPolicyViolation as e:
            return JSONResponse(status_code=400, content={"ok": False, **e.detail})

        try:
            task_intake = build_task_intake_spec(
                ingress_lane="agent_v3",
                default_source="rest",
                raw_source=str(body.get("source", "")).strip(),
                raw_task_intake=raw_task_intake or None,
                raw_contract=raw_contract,
                message=message,
                goal_hint=goal_hint,
                execution_profile=execution_profile,
                depth=depth,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                account_id=account_id,
                thread_id=thread_id,
                agent_id=agent_id,
                role_id=role_id,
                context=context,
                attachments=file_paths or [],
                client_name=str(request.headers.get("X-Client-Name", "")).strip(),
            )
        except TaskIntakeValidationError as exc:
            return JSONResponse(status_code=400, content={"ok": False, **exc.detail})
        scenario_pack = resolve_scenario_pack(task_intake, goal_hint=goal_hint, context=context)
        if scenario_pack is not None:
            task_intake = apply_scenario_pack(task_intake, scenario_pack)
        task_intake = _augment_task_intake_for_public_repo(task_intake)
        planning_task_layer = _maybe_resolve_planning_task_layer(
            task_intake=task_intake,
            scenario_pack=_scenario_pack_payload(scenario_pack),
            session_id=session_id,
            account_id=account_id,
            thread_id=thread_id,
            user_id=user_id,
            agent_id=agent_id,
            message=message,
        )
        if planning_task_layer is not None:
            context["planning_task_type"] = str(planning_task_layer.get("task_type") or "")
            context["planning_task_id"] = str(planning_task_layer.get("task_id") or "")
            context["task_id"] = str(planning_task_layer.get("task_id") or "")
            context["logical_task_id"] = str(planning_task_layer.get("task_id") or "")
        planning_knowledge_ingress = _maybe_apply_planning_knowledge_ingress(
            runtime=state,
            task_intake=task_intake,
            goal_hint=goal_hint,
            scenario_pack=_scenario_pack_payload(scenario_pack),
            query=message,
        )
        if planning_knowledge_ingress:
            context["planning_knowledge_ingress"] = dict(planning_knowledge_ingress)
        task_intake_client_info = _task_intake_client_payload(task_intake) or dict(client_info)
        scenario_pack_runtime = _scenario_pack_runtime_payload(scenario_pack)
        provider_request = _provider_request_from_task_intake(
            task_intake=task_intake,
            goal_hint=goal_hint,
            scenario_pack=scenario_pack_runtime,
        )
        execution_request = _execution_request_from_task_intake(
            task_intake=task_intake,
            goal_hint=goal_hint,
            scenario_pack=scenario_pack_runtime,
        )
        lane_policy = _lane_policy_payload(
            task_intake=task_intake,
            goal_hint=goal_hint,
            scenario_pack=scenario_pack_runtime,
            provider_request=provider_request,
            execution_request=execution_request,
        )
        context["scenario_pack"] = _scenario_pack_runtime_payload(scenario_pack, lane_policy=lane_policy)
        if lane_policy:
            context["lane_policy"] = dict(lane_policy)
        if execution_request:
            context["execution_request"] = dict(execution_request)
        context["task_intake"] = task_intake.to_dict()
        contract_seed = task_intake_to_contract_seed(task_intake)
        merged_contract = dict(contract_seed)
        merged_contract.update(raw_contract)

        # Normalize and synthesize contract
        ask_contract, was_synthesized = normalize_ask_contract(
            message=message,
            raw_contract=merged_contract if merged_contract else None,
            goal_hint=goal_hint,
            context=context,
        )
        strategy_plan = build_strategy_plan(
            message=message,
            contract=ask_contract,
            goal_hint=goal_hint,
            context=context,
        )
        compiled_prompt = build_prompt_from_strategy(
            strategy_plan=strategy_plan,
            contract=ask_contract,
            model_provider=(
                "gemini"
                if goal_hint == "image" or str((provider_request or {}).get("requested_provider") or "") == "gemini"
                else "chatgpt"
            ),
            custom_context=context,
        )

        # Store contract in context for downstream use
        context["ask_contract"] = ask_contract.to_dict()
        context["ask_strategy"] = strategy_plan.to_dict()
        context["compiled_prompt"] = compiled_prompt.to_dict()
        context["contract_source"] = ask_contract.contract_source
        context["contract_completeness"] = ask_contract.contract_completeness
        parser_fallback_used = bool(dict(task_intake.context).get("message_contract_parser", {}).get("used"))
        if parser_fallback_used and not raw_task_intake_body and not body_contract and ask_contract.contract_source == "client":
            ask_contract.contract_source = "message_parser"
            context["contract_source"] = ask_contract.contract_source
        control_plane = _build_control_plane_state(
            task_intake=task_intake,
            ask_contract=ask_contract,
            scenario_pack=_scenario_pack_payload(scenario_pack),
            lane_policy=lane_policy,
            requested_execution_profile=execution_profile,
            parser_fallback_used=parser_fallback_used,
        )
        execution_layer = _planning_execution_layer_payload(
            lane_policy=lane_policy,
            execution_request=execution_request,
            provider_request=provider_request,
            final_provider="",
        )
        if execution_layer:
            control_plane["execution_layer"] = dict(execution_layer)
        if execution_request:
            control_plane["execution_request"] = dict(execution_request)
        if planning_task_layer is not None:
            control_plane["planning_task"] = dict(planning_task_layer)
        source_material_policy = _planning_source_material_policy(planning_task_layer)
        if source_material_policy:
            control_plane["source_material_policy"] = dict(source_material_policy)
        if str(source_material_policy.get("action_contract") or "").strip() == "blocked":
            blocked_message = str(source_material_policy.get("summary") or "").strip() or (
                "Attached materials require preprocessing before this planning task can continue."
            )
            blocked_next_action = {
                "type": "await_workspace_patch",
                "status": "blocking",
                "source_material_policy": dict(source_material_policy),
                "required_actions": list(source_material_policy.get("required_actions") or []),
                "pending_items": list(source_material_policy.get("pending_items") or []),
            }
            updated_planning_task_layer = _maybe_update_planning_task_layer(
                planning_task_layer,
                status="needs_input",
                answer=blocked_message,
                next_action=blocked_next_action,
                task_intake=task_intake,
                session_id=session_id,
            )
            if updated_planning_task_layer is not None:
                planning_task_layer = updated_planning_task_layer
                control_plane["planning_task"] = dict(updated_planning_task_layer)
            review = generate_basic_review(
                contract=ask_contract,
                answer="",
                route="clarify",
                provider="attachment_preflight",
                session_id=session_id,
                trace_id=trace_id,
            )
            response = _build_agent_response(
                session_id=session_id,
                run_id=f"run_{uuid.uuid4().hex[:12]}",
                status="needs_input",
                answer=blocked_message,
                route="clarify",
                provider_path=["attachment_preflight"],
                final_provider="attachment_preflight",
                next_action=blocked_next_action,
                recovery_state="source_material_preflight_blocked",
                contract=ask_contract.to_dict(),
                review=review.to_dict(),
                trace_id=trace_id,
                memory_capture=_maybe_capture_agent_turn_memory(
                    runtime=state,
                    memory_capture_request=raw_memory_capture_request,
                    session_id=session_id,
                    account_id=account_id,
                    thread_id=thread_id,
                    agent_id=agent_id,
                    role_id=role_id,
                    trace_id=trace_id,
                    route="clarify",
                    answer=blocked_message,
                    message=message,
                    source_system="advisor_agent",
                    status="needs_input",
                    next_action=blocked_next_action,
                    scenario_pack=_scenario_pack_payload(scenario_pack),
                ),
                provider_request=provider_request,
            )
            response = _augment_agent_response(
                response,
                task_intake=task_intake,
                ask_contract=ask_contract,
                scenario_pack=_scenario_pack_payload(scenario_pack),
                control_plane=control_plane,
                runtime=state,
                account_id=account_id,
                thread_id=thread_id,
                agent_id=agent_id,
                role_id=role_id,
                trace_id=trace_id,
                planning_task_store=_planning_task_store,
            )
            _upsert_session(
                session_id,
                kind="clarify",
                run_id=str(response.get("run_id") or ""),
                status="needs_input",
                route="clarify",
                last_message=message,
                last_answer=blocked_message,
                provenance=response.get("provenance") or {},
                next_action=response.get("next_action") or {},
                trace_id=trace_id,
                task_intake=task_intake.to_dict(),
                contract=ask_contract.to_dict(),
                scenario_pack=_scenario_pack_payload(scenario_pack),
                control_plane=control_plane,
            )
            _append_session_event(
                session_id,
                "turn.source_material_preflight_blocked",
                trace_id=trace_id,
                required_actions=list(source_material_policy.get("required_actions") or []),
                pending_items=list(source_material_policy.get("pending_items") or []),
            )
            return response
        provider_conflict = _provider_request_conflict(
            provider_request=provider_request,
            route_hint=str(strategy_plan.route_hint or ""),
        )
        if provider_conflict:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "session_id": session_id,
                    **provider_conflict,
                    "provider_selection": _provider_selection_payload(provider_request=provider_request, final_provider=""),
                },
            )
        public_mcp_microtask_block = _public_agent_microtask_block_detail(
            request=request,
            message=message,
            task_intake=task_intake,
            client_info=task_intake_client_info,
        )
        if public_mcp_microtask_block:
            logger.warning(
                "blocked public advisor-agent microtask caller=%s reason=%s session_id=%s",
                str(task_intake_client_info.get("mcp_client_name") or task_intake_client_info.get("name") or request.headers.get("x-client-name") or ""),
                str(public_mcp_microtask_block.get("reason") or ""),
                session_id,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "session_id": session_id,
                    **public_mcp_microtask_block,
                    "provider_selection": _provider_selection_payload(provider_request=provider_request, final_provider=""),
                },
            )
        if existing_session is None:
            duplicate_session = _find_duplicate_public_agent_session(
                request=request,
                session_id=session_id,
                message=message,
                task_intake=task_intake,
                provider_request=provider_request,
                client_info=task_intake_client_info,
                route_hint=str(strategy_plan.route_hint or ""),
            )
            if duplicate_session is not None:
                duplicate_session_id = str(duplicate_session.get("session_id") or "")
                _append_session_event(
                    duplicate_session_id,
                    "turn.duplicate_rejected",
                    trace_id=trace_id,
                    duplicate_trace_id=trace_id,
                    duplicate_message=message[:240],
                    duplicate_goal_hint=goal_hint,
                )
                duplicate_view = _finalize_public_agent_surface(_session_response(duplicate_session))
                return JSONResponse(
                    status_code=409,
                    content={
                        "ok": False,
                        "error": "duplicate_public_agent_session_in_progress",
                        "error_type": "DuplicatePublicAgentSessionInProgress",
                        "message": (
                            "An equivalent public advisor-agent session from the same MCP caller is already running."
                        ),
                        "hint": (
                            "Reuse the running session instead of resubmitting the same heavy public-agent turn."
                        ),
                        "session_id": duplicate_session_id,
                        "existing_session_id": duplicate_session_id,
                        "recommended_client_action": "wait",
                        "wait_tool": "advisor_agent_wait",
                        "existing_session": duplicate_view,
                    },
                )
        # === End Ask Contract ===

        if strategy_plan.clarify_required:
            logger.info(
                "Clarify gate triggered: contract_id=%s completeness=%.2f plan_id=%s",
                ask_contract.contract_id,
                ask_contract.contract_completeness,
                strategy_plan.plan_id,
            )
            clarification_message = strategy_plan.clarify_reason
            if strategy_plan.clarify_questions:
                clarification_message = (
                    f"{clarification_message}\n\nQuestions:\n" +
                    "\n".join(f"- {item}" for item in strategy_plan.clarify_questions)
                )
            clarify_next_action = {
                "type": "await_user_clarification",
                "status": "blocking",
                "questions": list(strategy_plan.clarify_questions),
                "recommended_reask_template": strategy_plan.recommended_reask_template,
            }
            updated_planning_task_layer = _maybe_update_planning_task_layer(
                planning_task_layer,
                status="needs_followup",
                answer=clarification_message,
                next_action=clarify_next_action,
                task_intake=task_intake,
                session_id=session_id,
            )
            if updated_planning_task_layer is not None:
                planning_task_layer = updated_planning_task_layer
                control_plane["planning_task"] = dict(updated_planning_task_layer)
            review = generate_basic_review(
                contract=ask_contract,
                answer="",  # No answer yet
                route="clarify",
                provider="ask_strategist",
                session_id=session_id,
                trace_id=trace_id,
            )
            response = _build_agent_response(
                session_id=session_id,
                run_id=f"run_{uuid.uuid4().hex[:12]}",
                status="needs_followup",
                answer=clarification_message,
                route="clarify",
                provider_path=["ask_strategist"],
                final_provider="ask_strategist",
                next_action=clarify_next_action,
                recovery_state="clarify_gate_blocked",
                contract=ask_contract.to_dict(),
                review=review.to_dict(),
                trace_id=trace_id,
                memory_capture=_maybe_capture_agent_turn_memory(
                    runtime=state,
                    memory_capture_request=raw_memory_capture_request,
                    session_id=session_id,
                    account_id=account_id,
                    thread_id=thread_id,
                    agent_id=agent_id,
                    role_id=role_id,
                    trace_id=trace_id,
                    route="clarify",
                    answer=clarification_message,
                    message=message,
                    source_system="advisor_agent",
                    status="needs_followup",
                    next_action=clarify_next_action,
                    scenario_pack=_scenario_pack_payload(scenario_pack),
                ),
                provider_request=provider_request,
            )
            clarify_diagnostics = _build_clarify_diagnostics(
                session_id=session_id,
                message=message,
                ask_contract=ask_contract,
                strategy_plan=strategy_plan,
                execution_profile=task_intake.execution_profile,
            )
            response = _augment_agent_response(
                response,
                task_intake=task_intake,
                ask_contract=ask_contract,
                scenario_pack=_scenario_pack_payload(scenario_pack),
                control_plane=control_plane,
                clarify_diagnostics=clarify_diagnostics,
                runtime=state,
                account_id=account_id,
                thread_id=thread_id,
                agent_id=agent_id,
                role_id=role_id,
                trace_id=trace_id,
                planning_task_store=_planning_task_store,
            )
            _upsert_session(
                session_id,
                kind="clarify",
                run_id=str(response.get("run_id") or ""),
                status="needs_followup",
                route="clarify",
                last_message=message,
                last_answer=clarification_message,
                provenance=response.get("provenance") or {},
                next_action=response.get("next_action") or {},
                trace_id=trace_id,
                task_intake=task_intake.to_dict(),
                contract=ask_contract.to_dict(),
                scenario_pack=_scenario_pack_payload(scenario_pack),
                control_plane=control_plane,
                clarify_diagnostics=clarify_diagnostics,
            )
            _append_session_event(
                session_id,
                "turn.clarify_required",
                trace_id=trace_id,
                plan_id=str(strategy_plan.plan_id or ""),
                clarify_questions=list(strategy_plan.clarify_questions or []),
            )
            return response
        # === End Clarify Gate ===

        request_metadata = _advisor_request_metadata(
            trace_id=trace_id,
            session_id=session_id,
            account_id=account_id,
            thread_id=thread_id,
            agent_id=agent_id,
            role_id=role_id,
            user_id=user_id,
            intent_hint=intent_hint,
            timeout_seconds=timeout_seconds,
        )
        request_metadata["depth"] = depth
        request_metadata["goal_hint"] = goal_hint
        if execution_profile:
            request_metadata["execution_profile"] = execution_profile
        request_metadata["task_intake"] = summarize_task_intake(task_intake)
        if scenario_pack is not None:
            request_metadata["scenario_pack"] = summarize_scenario_pack(scenario_pack)
        degradation = _runtime_degradation(state)
        cfg = load_config()
        _upsert_session(
            session_id,
            kind="pending",
            run_id="",
            status="running",
            route=str(strategy_plan.route_hint or goal_hint or ""),
            last_message=message,
            last_answer="",
            provenance=_build_provenance(
                route=str(strategy_plan.route_hint or goal_hint or "unknown"),
                provider_path=[],
                final_provider="",
                provider_request=provider_request,
            ),
            next_action=_default_next_action(status="running"),
            delivery_mode=delivery_mode,
            trace_id=trace_id,
            task_intake=task_intake.to_dict(),
            contract=ask_contract.to_dict(),
            scenario_pack=_scenario_pack_payload(scenario_pack),
            control_plane=control_plane,
        )
        _append_session_event(
            session_id,
            "turn.submitted",
            goal_hint=goal_hint,
            depth=depth,
            deferred=bool(deferred_mode),
            trace_id=trace_id,
        )

        # Extract contract for response building
        response_contract = context.get("ask_contract")

        try:
            def _run_turn() -> dict[str, Any]:
                nonlocal planning_task_layer
                enriched_message = _enrich_message(message, context)

                if goal_hint == "image":
                    run_id = f"run_{uuid.uuid4().hex[:12]}"
                    job_id = _submit_direct_job(
                        cfg=cfg,
                        kind="gemini_web.generate_image",
                        input_obj={
                            "prompt": enriched_message,
                            **({"file_paths": list(file_paths)} if file_paths else {}),
                        },
                        params_obj={"timeout_seconds": timeout_seconds},
                        client_obj={"name": "agent_v3", "goal_hint": goal_hint, "session_id": session_id},
                        idempotency_key=f"agent-image:{session_id}:{int(time.time())}",
                    )
                    _upsert_session(
                        session_id,
                        kind="job",
                        run_id=run_id,
                        job_id=job_id,
                        status="running",
                        route="image",
                        last_message=message,
                        last_answer="",
                        provenance=_build_provenance(
                            route="image",
                            provider_path=["gemini_web"],
                            final_provider="gemini_web",
                            job_id=job_id,
                            provider_request=provider_request,
                        ),
                    )
                    snapshot = _wait_for_job_completion(cfg=cfg, job_id=job_id, timeout_seconds=timeout_seconds)
                    normalized_answer = _planning_normalize_answer(
                        str(snapshot.get("answer") or ""),
                        task_intake=task_intake,
                        scenario_pack=context.get("scenario_pack"),
                    )
                    artifacts_list = []
                    if snapshot.get("conversation_url"):
                        artifacts_list.append({"kind": "conversation_url", "uri": snapshot["conversation_url"]})
                    updated_planning_task_layer = _maybe_update_planning_task_layer(
                        planning_task_layer,
                        status=str(snapshot["agent_status"]),
                        answer=normalized_answer,
                        next_action=dict(snapshot.get("next_action") or {}),
                        task_intake=task_intake,
                        session_id=session_id,
                        artifact_refs=artifacts_list,
                    )
                    if updated_planning_task_layer is not None:
                        planning_task_layer = updated_planning_task_layer
                        control_plane["planning_task"] = dict(updated_planning_task_layer)
                    response = _build_agent_response(
                        session_id=session_id,
                        run_id=run_id,
                        status=str(snapshot["agent_status"]),
                        answer=normalized_answer,
                        route="image",
                        provider_path=["gemini_web"],
                        final_provider="gemini_web",
                        job_id=job_id,
                        artifacts_list=artifacts_list,
                        recovery_state=("clean" if str(snapshot["agent_status"]) == "completed" else str(snapshot["agent_status"])),
                        contract=response_contract,
                        trace_id=trace_id,
                        memory_capture=_maybe_capture_agent_turn_memory(
                            runtime=state,
                            memory_capture_request=raw_memory_capture_request,
                            session_id=session_id,
                            account_id=account_id,
                            thread_id=thread_id,
                            agent_id=agent_id,
                            role_id=role_id,
                            trace_id=trace_id,
                            route="image",
                            answer=str(snapshot.get("answer") or ""),
                            message=message,
                            source_system="advisor_agent",
                            status=str(snapshot["agent_status"]),
                            scenario_pack=_scenario_pack_payload(scenario_pack),
                        ),
                        provider_request=provider_request,
                    )
                    response = _augment_agent_response(
                        response,
                        task_intake=task_intake,
                        ask_contract=ask_contract,
                        scenario_pack=_scenario_pack_payload(scenario_pack),
                        control_plane=control_plane,
                        runtime=state,
                        account_id=account_id,
                        thread_id=thread_id,
                        agent_id=agent_id,
                        role_id=role_id,
                        trace_id=trace_id,
                        planning_task_store=_planning_task_store,
                    )
                    _upsert_session(
                        session_id,
                        status=response["status"],
                        last_answer=response["answer"],
                        artifacts=artifacts_list,
                        next_action=response["next_action"],
                        provenance=response["provenance"],
                        memory_capture=dict(response.get("memory_capture") or {}) or None,
                        task_intake=task_intake.to_dict(),
                        contract=ask_contract.to_dict(),
                        scenario_pack=_scenario_pack_payload(scenario_pack),
                        control_plane=control_plane,
                    )
                    return response

                if goal_hint in {"consult", "dual_review"}:
                    consultation = _submit_consultation(
                        cfg=cfg,
                        question=enriched_message,
                        file_paths=list(file_paths) if file_paths else None,
                        timeout_seconds=timeout_seconds,
                        session_id=session_id,
                        goal_hint=goal_hint,
                        user_id=user_id,
                    )
                    run_id = str(consultation["consultation_id"])
                    job_ids = [str(job["job_id"]) for job in consultation["jobs"]]
                    _upsert_session(
                        session_id,
                        kind="consult",
                        run_id=run_id,
                        consultation_id=run_id,
                        job_ids=job_ids,
                        status="running",
                        route="consult",
                        last_message=message,
                        last_answer="",
                        provenance=_build_provenance(
                            route="consult",
                            provider_path=[str(job.get("provider") or "") for job in consultation["jobs"]],
                            final_provider="consult",
                            consultation_id=run_id,
                            provider_request=provider_request,
                        ),
                    )
                    snapshot = _wait_for_consultation_completion(cfg=cfg, consultation_id=run_id, timeout_seconds=timeout_seconds)
                    response = _build_agent_response(
                        session_id=session_id,
                        run_id=run_id,
                        status=str(snapshot["agent_status"]),
                        answer=str(snapshot.get("answer") or ""),
                        route="consult",
                        provider_path=[str(job.get("provider") or "") for job in snapshot.get("jobs", [])],
                        final_provider="consult",
                        consultation_id=run_id,
                        recovery_state=("clean" if str(snapshot["agent_status"]) == "completed" else str(snapshot["agent_status"])),
                        contract=response_contract,
                        trace_id=trace_id,
                        memory_capture=_maybe_capture_agent_turn_memory(
                            runtime=state,
                            memory_capture_request=raw_memory_capture_request,
                            session_id=session_id,
                            account_id=account_id,
                            thread_id=thread_id,
                            agent_id=agent_id,
                            role_id=role_id,
                            trace_id=trace_id,
                            route="consult",
                            answer=str(snapshot.get("answer") or ""),
                            message=message,
                            source_system="advisor_agent",
                            status=str(snapshot["agent_status"]),
                            scenario_pack=_scenario_pack_payload(scenario_pack),
                        ),
                        provider_request=provider_request,
                    )
                    response = _augment_agent_response(
                        response,
                        task_intake=task_intake,
                        ask_contract=ask_contract,
                        scenario_pack=_scenario_pack_payload(scenario_pack),
                        control_plane=control_plane,
                        runtime=state,
                        account_id=account_id,
                        thread_id=thread_id,
                        agent_id=agent_id,
                        role_id=role_id,
                        trace_id=trace_id,
                        planning_task_store=_planning_task_store,
                    )
                    _upsert_session(
                        session_id,
                        status=response["status"],
                        last_answer=response["answer"],
                        next_action=response["next_action"],
                        provenance=response["provenance"],
                        memory_capture=dict(response.get("memory_capture") or {}) or None,
                        task_intake=task_intake.to_dict(),
                        contract=ask_contract.to_dict(),
                        scenario_pack=_scenario_pack_payload(scenario_pack),
                        control_plane=control_plane,
                    )
                    return response

                if _should_use_direct_gemini_lane(provider_request=provider_request, goal_hint=goal_hint):
                    route_name, params_obj = _gemini_execution_spec(
                        provider_request=provider_request,
                        strategy_plan=strategy_plan,
                        goal_hint=goal_hint,
                        timeout_seconds=timeout_seconds,
                    )
                    run_id = f"run_{uuid.uuid4().hex[:12]}"
                    input_obj = {
                        "question": enriched_message,
                        **({"file_paths": list(file_paths)} if file_paths else {}),
                    }
                    github_repo = str((provider_request or {}).get("github_repo") or "").strip()
                    # Preserve the public repo as authoritative review context even when
                    # imported-code mode is disabled. Gemini provider fallback logic uses
                    # this repo hint to continue safely when Drive attachment UI is unavailable.
                    if github_repo:
                        input_obj["github_repo"] = github_repo
                    job_id = _submit_direct_job(
                        cfg=cfg,
                        kind="gemini_web.ask",
                        input_obj=input_obj,
                        params_obj=params_obj,
                        client_obj={"name": "agent_v3", "goal_hint": goal_hint, "session_id": session_id},
                        idempotency_key=f"agent-gemini:{session_id}:{route_name}:{int(time.time())}",
                    )
                    _upsert_session(
                        session_id,
                        kind="job",
                        run_id=run_id,
                        job_id=job_id,
                        status="running",
                        route=route_name,
                        last_message=message,
                        last_answer="",
                        provenance=_build_provenance(
                            route=route_name,
                            provider_path=["gemini_web"],
                            final_provider="gemini_web",
                            job_id=job_id,
                            provider_request=provider_request,
                        ),
                    )
                    snapshot = _wait_for_job_completion(cfg=cfg, job_id=job_id, timeout_seconds=timeout_seconds)
                    normalized_answer = _planning_normalize_answer(
                        str(snapshot.get("answer") or ""),
                        task_intake=task_intake,
                        scenario_pack=context.get("scenario_pack"),
                    )
                    artifacts_list = []
                    if snapshot.get("conversation_url"):
                        artifacts_list.append({"kind": "conversation_url", "uri": snapshot["conversation_url"]})
                    updated_planning_task_layer = _maybe_update_planning_task_layer(
                        planning_task_layer,
                        status=str(snapshot["agent_status"]),
                        answer=normalized_answer,
                        next_action=dict(snapshot.get("next_action") or {}),
                        task_intake=task_intake,
                        session_id=session_id,
                        artifact_refs=artifacts_list,
                    )
                    if updated_planning_task_layer is not None:
                        planning_task_layer = updated_planning_task_layer
                        control_plane["planning_task"] = dict(updated_planning_task_layer)
                    response = _build_agent_response(
                        session_id=session_id,
                        run_id=run_id,
                        status=str(snapshot["agent_status"]),
                        answer=normalized_answer,
                        route=route_name,
                        provider_path=["gemini_web"],
                        final_provider="gemini_web",
                        job_id=job_id,
                        artifacts_list=artifacts_list,
                        recovery_state=("clean" if str(snapshot["agent_status"]) == "completed" else str(snapshot["agent_status"])),
                        contract=response_contract,
                        trace_id=trace_id,
                        memory_capture=_maybe_capture_agent_turn_memory(
                            runtime=state,
                            memory_capture_request=raw_memory_capture_request,
                            session_id=session_id,
                            account_id=account_id,
                            thread_id=thread_id,
                            agent_id=agent_id,
                            role_id=role_id,
                            trace_id=trace_id,
                            route=route_name,
                            answer=normalized_answer,
                            message=message,
                            source_system="advisor_agent",
                            status=str(snapshot["agent_status"]),
                            scenario_pack=_scenario_pack_payload(scenario_pack),
                        ),
                        provider_request=provider_request,
                    )
                    response = _augment_agent_response(
                        response,
                        task_intake=task_intake,
                        ask_contract=ask_contract,
                        scenario_pack=_scenario_pack_payload(scenario_pack),
                        control_plane=control_plane,
                        runtime=state,
                        account_id=account_id,
                        thread_id=thread_id,
                        agent_id=agent_id,
                        role_id=role_id,
                        trace_id=trace_id,
                        planning_task_store=_planning_task_store,
                    )
                    _upsert_session(
                        session_id,
                        status=response["status"],
                        last_answer=response["answer"],
                        artifacts=artifacts_list,
                        next_action=response["next_action"],
                        provenance=response["provenance"],
                        memory_capture=dict(response.get("memory_capture") or {}) or None,
                        task_intake=task_intake.to_dict(),
                        contract=ask_contract.to_dict(),
                        scenario_pack=_scenario_pack_payload(scenario_pack),
                        control_plane=control_plane,
                    )
                    return response

                controller = ControllerEngine(state)
                route_mapping = {
                    "kb_answer": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
                    "quick_ask": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
                    "clarify": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
                    "hybrid": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
                    "analysis_heavy": {"provider": "chatgpt", "preset": "thinking_heavy", "kind": "chatgpt_web.ask"},
                    "deep_research": {"provider": "chatgpt", "preset": "deep_research", "kind": "chatgpt_web.ask"},
                    "report": {"provider": "chatgpt", "preset": "pro_extended", "kind": "chatgpt_web.ask"},
                    "write_report": {"provider": "chatgpt", "preset": "pro_extended", "kind": "chatgpt_web.ask"},
                    "funnel": {"provider": "chatgpt", "preset": "thinking_heavy", "kind": "chatgpt_web.ask"},
                    "build_feature": {"provider": "chatgpt", "preset": "thinking_heavy", "kind": "chatgpt_web.ask"},
                    "action": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
                }

                with _bind_role(role_id):
                    result = controller.ask(
                        question=message,
                        trace_id=trace_id,
                        intent_hint=intent_hint,
                        role_id=role_id,
                        session_id=session_id,
                        account_id=account_id,
                        thread_id=thread_id,
                        agent_id=agent_id,
                        user_id=user_id,
                        stable_context=context,
                        idempotency_key=f"agent-turn:{session_id}:{int(time.time())}",
                        request_fingerprint=f"{session_id}:{message[:64]}",
                        timeout_seconds=timeout_seconds,
                        max_retries=1,
                        quality_threshold=0,
                        request_metadata=request_metadata,
                        degradation=degradation,
                        route_mapping=route_mapping,
                        kb_direct_completion_allowed=lambda s: False,
                        kb_direct_synthesis_enabled=lambda: False,
                        sanitize_context_hash="",
                    )

                run_id = str(result.get("run_id") or f"run_{uuid.uuid4().hex[:12]}")
                _upsert_session(
                    session_id,
                    kind="controller",
                    run_id=run_id,
                    job_id=str(result.get("job_id") or ""),
                    status=_agent_status_from_controller_status(str(result.get("controller_status") or "")),
                    route=str(result.get("route") or ""),
                    last_message=message,
                    last_answer=str(result.get("answer") or ""),
                    provenance=_build_provenance(
                        route=str(result.get("route") or "unknown"),
                        provider_path=[str(result.get("provider") or "chatgpt")],
                        final_provider=str(result.get("provider") or "chatgpt"),
                        job_id=str(result.get("job_id") or ""),
                        provider_request=provider_request,
                    ),
                )
                if result.get("answer"):
                    normalized_answer = _planning_normalize_answer(
                        str(result.get("answer") or ""),
                        task_intake=task_intake,
                        scenario_pack=context.get("scenario_pack"),
                    )
                    updated_planning_task_layer = _maybe_update_planning_task_layer(
                        planning_task_layer,
                        status="completed",
                        answer=normalized_answer,
                        next_action=None,
                        task_intake=task_intake,
                        session_id=session_id,
                        artifact_refs=[str(item.get("uri") or item.get("path") or "").strip() for item in list(result.get("artifacts") or []) if str(item.get("uri") or item.get("path") or "").strip()],
                    )
                    if updated_planning_task_layer is not None:
                        planning_task_layer = updated_planning_task_layer
                        control_plane["planning_task"] = dict(updated_planning_task_layer)
                    response = _build_agent_response(
                        session_id=session_id,
                        run_id=run_id,
                        status="completed",
                        answer=normalized_answer,
                        route=str(result.get("route") or ""),
                        provider_path=[str(result.get("provider") or "chatgpt")],
                        final_provider=str(result.get("provider") or "chatgpt"),
                        job_id=str(result.get("job_id") or ""),
                        artifacts_list=list(result.get("artifacts") or []),
                        contract=response_contract,
                        trace_id=trace_id,
                        memory_capture=_maybe_capture_agent_turn_memory(
                            runtime=state,
                            memory_capture_request=raw_memory_capture_request,
                            session_id=session_id,
                            account_id=account_id,
                            thread_id=thread_id,
                            agent_id=agent_id,
                            role_id=role_id,
                            trace_id=trace_id,
                            route=str(result.get("route") or ""),
                            answer=normalized_answer,
                            message=message,
                            source_system="advisor_agent",
                            status="completed",
                            scenario_pack=_scenario_pack_payload(scenario_pack),
                        ),
                        provider_request=provider_request,
                    )
                    response = _augment_agent_response(
                        response,
                        task_intake=task_intake,
                        ask_contract=ask_contract,
                        scenario_pack=_scenario_pack_payload(scenario_pack),
                        control_plane=control_plane,
                        runtime=state,
                        account_id=account_id,
                        thread_id=thread_id,
                        agent_id=agent_id,
                        role_id=role_id,
                        trace_id=trace_id,
                        planning_task_store=_planning_task_store,
                    )
                    _upsert_session(
                        session_id,
                        status=response["status"],
                        last_answer=response["answer"],
                        artifacts=list(response.get("artifacts") or []),
                        next_action=response["next_action"],
                        provenance=response["provenance"],
                        memory_capture=dict(response.get("memory_capture") or {}) or None,
                        task_intake=task_intake.to_dict(),
                        contract=ask_contract.to_dict(),
                        scenario_pack=_scenario_pack_payload(scenario_pack),
                        control_plane=control_plane,
                    )
                    return response

                snapshot = _wait_for_controller_delivery(controller, run_id=run_id, timeout_seconds=timeout_seconds)
                run = snapshot["run"]
                normalized_answer = _planning_normalize_answer(
                    str(snapshot.get("answer") or ""),
                    task_intake=task_intake,
                    scenario_pack=context.get("scenario_pack"),
                )
                updated_planning_task_layer = _maybe_update_planning_task_layer(
                    planning_task_layer,
                    status=str(snapshot["agent_status"]),
                    answer=normalized_answer,
                    next_action=dict(snapshot.get("next_action") or {}),
                    task_intake=task_intake,
                    session_id=session_id,
                    artifact_refs=[str(item.get("uri") or item.get("path") or "").strip() for item in list(snapshot.get("artifacts") or []) if str(item.get("uri") or item.get("path") or "").strip()],
                )
                if updated_planning_task_layer is not None:
                    planning_task_layer = updated_planning_task_layer
                    control_plane["planning_task"] = dict(updated_planning_task_layer)
                response = _build_agent_response(
                    session_id=session_id,
                    run_id=run_id,
                    status=str(snapshot["agent_status"]),
                    answer=normalized_answer,
                    route=str(run.get("route") or result.get("route") or ""),
                    provider_path=[str(run.get("provider") or result.get("provider") or "chatgpt")],
                    final_provider=str(run.get("provider") or result.get("provider") or "chatgpt"),
                    job_id=str(snapshot.get("job_id") or result.get("job_id") or ""),
                    artifacts_list=list(snapshot.get("artifacts") or []),
                    next_action=dict(snapshot.get("next_action") or {}),
                    recovery_state=("clean" if str(snapshot["agent_status"]) == "completed" else str(snapshot["agent_status"])),
                    contract=response_contract,
                    trace_id=trace_id,
                    attachment_confirmation=dict(snapshot.get("attachment_confirmation") or {}) or None,
                    memory_capture=_maybe_capture_agent_turn_memory(
                        runtime=state,
                        memory_capture_request=raw_memory_capture_request,
                        session_id=session_id,
                        account_id=account_id,
                        thread_id=thread_id,
                        agent_id=agent_id,
                        role_id=role_id,
                        trace_id=trace_id,
                        route=str(run.get("route") or result.get("route") or ""),
                        answer=normalized_answer,
                        message=message,
                        source_system="advisor_agent",
                        status=str(snapshot["agent_status"]),
                        next_action=dict(snapshot.get("next_action") or {}),
                        scenario_pack=_scenario_pack_payload(scenario_pack),
                    ),
                    provider_request=provider_request,
                )
                response = _augment_agent_response(
                    response,
                    task_intake=task_intake,
                    ask_contract=ask_contract,
                    scenario_pack=_scenario_pack_payload(scenario_pack),
                    control_plane=control_plane,
                    runtime=state,
                    account_id=account_id,
                    thread_id=thread_id,
                    agent_id=agent_id,
                    role_id=role_id,
                    trace_id=trace_id,
                    planning_task_store=_planning_task_store,
                )
                _upsert_session(
                    session_id,
                    status=response["status"],
                    job_id=str(response["provenance"].get("job_id") or ""),
                    last_answer=response["answer"],
                    artifacts=list(response.get("artifacts") or []),
                    attachment_confirmation=dict(response.get("attachment_confirmation") or {}),
                    next_action=response["next_action"],
                    provenance=response["provenance"],
                    memory_capture=dict(response.get("memory_capture") or {}) or None,
                    task_intake=task_intake.to_dict(),
                    contract=ask_contract.to_dict(),
                    scenario_pack=_scenario_pack_payload(scenario_pack),
                    control_plane=control_plane,
                )
                return response

            if deferred_mode:
                accepted = _session_response(_session_copy(session_id) or {"session_id": session_id, "status": "running"})
                accepted["accepted"] = True
                accepted["answer"] = ""
                accepted["delivery"] = {
                    "mode": "deferred",
                    "stream_url": _make_stream_url(session_id),
                }

                def _background_runner() -> None:
                    try:
                        response = _run_turn()
                    except Exception as exc:
                        logger.error("agent_turn deferred execution failed: %s", exc, exc_info=True)
                        error_text = str(exc)[:500]
                        _persist_agent_turn_failure(error_text=error_text, error_type=type(exc).__name__)
                    else:
                        _emit_runtime_event(
                            state,
                            event_type="agent_turn.completed",
                            source="agent_turn",
                            trace_id=trace_id,
                            data={
                                "session_id": session_id,
                                "run_id": response.get("run_id"),
                                "status": response.get("status"),
                                "route": response.get("provenance", {}).get("route"),
                            },
                        )

                worker = threading.Thread(
                    target=_background_runner,
                    name=f"agent-turn-{session_id[:24]}",
                    daemon=True,
                )
                worker.start()
                return JSONResponse(status_code=202, content=_finalize_public_agent_surface(accepted, accepted=True))

            response = await run_in_threadpool(_run_turn)
            _emit_runtime_event(
                state,
                event_type="agent_turn.completed",
                source="agent_turn",
                trace_id=trace_id,
                data={
                    "session_id": session_id,
                    "run_id": response.get("run_id"),
                    "status": response.get("status"),
                    "route": response.get("provenance", {}).get("route"),
                },
            )
            return response

        except Exception as exc:
            logger.error("agent_turn failed: %s", exc, exc_info=True)
            error_text = str(exc)[:500]
            _persist_agent_turn_failure(error_text=error_text, error_type=type(exc).__name__)
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "error": error_text,
                    "error_type": type(exc).__name__,
                    "session_id": session_id,
                },
            )

    @router.get("/session/{session_id}")
    async def get_session(session_id: str, request: Request):
        session = _session_copy(session_id)
        if not session:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": "session_not_found", "session_id": session_id},
            )
        refreshed = await run_in_threadpool(lambda: _refresh_session_state(dict(session)))
        response = _session_response(refreshed)
        planning_task = dict(response.get("planning_task") or {})
        if planning_task:
            read_semantics = _planning_query_read_semantics(
                surface="rest",
                read_mode="session_snapshot",
                writes_back_on_divergence=False,
                authority="agent_session.control_plane",
            )
            response["read_semantics"] = read_semantics
            response["planning_query"] = _build_planning_query(
                kind="snapshot",
                read_semantics=read_semantics,
                source_field="planning_task",
                canonical_field="planning_query.snapshot",
                snapshot=planning_task,
            )
        return response

    @router.get("/planning/task/{task_id}")
    async def get_planning_task(
        task_id: str,
        request: Request,
        account_id: str = "",
        thread_id: str = "",
        user_id: str = "",
        session_id: str = "",
        refresh: bool = True,
    ):
        task_payload = _planning_task_store.get_public(
            task_id,
            account_id=account_id,
            thread_id=thread_id,
            user_id=user_id,
            session_id=session_id,
        )
        if task_payload is None:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": "planning_task_not_found", "task_id": task_id},
            )
        if refresh:
            task_payload = await run_in_threadpool(lambda: _maybe_refresh_planning_task_visibility(dict(task_payload)))
        read_semantics = _planning_read_semantics(refresh=bool(refresh), surface="rest")
        return {
            "ok": True,
            "task_id": str(task_payload.get("task_id") or task_id),
            "planning_task": dict(task_payload),
            "read_semantics": read_semantics,
            "planning_query": _build_planning_query(
                kind="snapshot",
                read_semantics=read_semantics,
                source_field="planning_task",
                canonical_field="planning_query.snapshot",
                snapshot=dict(task_payload),
            ),
        }

    @router.get("/planning/tasks")
    async def list_planning_tasks(
        request: Request,
        account_id: str = "",
        thread_id: str = "",
        user_id: str = "",
        session_id: str = "",
        task_type: str = "",
        status: str = "",
        limit: int = 20,
        refresh: bool = True,
    ):
        items = _planning_task_store.list_public(
            account_id=account_id,
            thread_id=thread_id,
            user_id=user_id,
            session_id=session_id,
            task_type=task_type,
            status=status,
            limit=limit,
        )
        if refresh:
            items = await run_in_threadpool(
                lambda: [_maybe_refresh_planning_task_visibility(dict(item)) for item in list(items or [])]
            )
        read_semantics = _planning_read_semantics(refresh=bool(refresh), surface="rest")
        return {
            "ok": True,
            "count": len(items),
            "planning_tasks": items,
            "read_semantics": read_semantics,
            "planning_query": _build_planning_query(
                kind="collection",
                read_semantics=read_semantics,
                source_field="planning_tasks",
                canonical_field="planning_query.items",
                items=[dict(item) for item in list(items or [])],
            ),
        }

    @router.get("/session/{session_id}/stream")
    async def stream_session(session_id: str, request: Request, after_seq: int = 0):
        session = _session_copy(session_id)
        if not session:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": "session_not_found", "session_id": session_id},
            )

        from sse_starlette.sse import EventSourceResponse

        async def _generator():
            last_seq = max(0, int(after_seq or 0))
            bootstrap_sent = False
            while True:
                if await request.is_disconnected():
                    break
                current = _session_copy(session_id)
                if current is None:
                    yield {"event": "error", "data": json.dumps({"error": "session_not_found", "session_id": session_id})}
                    break
                refreshed = await run_in_threadpool(lambda: _refresh_session_state(dict(current)))
                events = _session_events_after(session_id, last_seq)
                if not events and not bootstrap_sent:
                    bootstrap_sent = True
                    yield {
                        "event": "snapshot",
                        "data": json.dumps({"seq": last_seq, "session": _session_response(refreshed)}),
                    }
                for event in events:
                    last_seq = max(last_seq, int(event.get("seq") or 0))
                    yield {"event": str(event.get("type") or "update"), "data": json.dumps(event)}
                latest = _session_copy(session_id) or refreshed
                if str(latest.get("status") or "") in _TERMINAL_AGENT_STATUSES:
                    yield {
                        "event": "done",
                        "data": json.dumps({"seq": last_seq, "session": _session_response(latest)}),
                    }
                    break
                await asyncio.sleep(0.5)

        return EventSourceResponse(_generator())

    @router.post("/cancel")
    async def cancel_session(request: Request, body: dict = Body(...)):
        _enforce_public_mcp_first_direct_rest_guard(request, operation="agent_cancel")
        session_id = str(body.get("session_id", "")).strip()
        if not session_id:
            return JSONResponse(status_code=400, content={"ok": False, "error": "session_id is required"})

        session = _session_copy(session_id)
        if not session:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": "session_not_found", "session_id": session_id},
            )

        cfg = load_config()
        canceled_job_ids: list[str] = []
        for job_id in [str(session.get("job_id") or "").strip(), *[str(v).strip() for v in list(session.get("job_ids") or [])]]:
            if not job_id or job_id in canceled_job_ids:
                continue
            try:
                await run_in_threadpool(lambda jid=job_id: _cancel_job(cfg=cfg, job_id=jid))
                canceled_job_ids.append(job_id)
            except Exception as exc:
                logger.warning("failed to cancel underlying job %s: %s", job_id, exc)

        cancel_next_action = _default_next_action(status="cancelled")
        updated_control_plane = dict(session.get("control_plane") or {})
        planning_task = _maybe_cancel_planning_task_layer_for_session(
            session,
            session_id=session_id,
            next_action=cancel_next_action,
        )
        if planning_task is not None:
            updated_control_plane["planning_task"] = dict(planning_task)
        session_updates: dict[str, Any] = {
            "status": "cancelled",
            "next_action": cancel_next_action,
        }
        if updated_control_plane:
            session_updates["control_plane"] = updated_control_plane

        updated = _upsert_session(session_id, **session_updates)
        _append_session_event(session_id, "session.cancelled", cancelled_job_ids=list(canceled_job_ids))
        payload = _session_response(updated)
        payload["cancelled_job_ids"] = canceled_job_ids
        payload["message"] = "Session cancelled successfully"
        return payload

    @router.get("/health")
    async def health():
        state = get_advisor_runtime_if_ready()
        if state is None:
            return {"status": "not_initialized", "version": "v3-agent"}
        return {"status": "ok", "version": "v3-agent", "active_sessions": _session_store.count_sessions()}

    return router
