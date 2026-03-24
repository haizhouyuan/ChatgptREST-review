from __future__ import annotations

import asyncio
import hmac
import json
import os
import sqlite3
import socket
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from chatgptrest.core.config import AppConfig
from chatgptrest.core.db import connect
from chatgptrest.core.env import get_bool as _env_get_bool
from chatgptrest.core.env import truthy_env as _truthy_env
from chatgptrest.core.file_path_inputs import normalize_file_path_entries
from chatgptrest.core.idempotency import IdempotencyCollision
from chatgptrest.core.job_store import ConversationBusy, create_job, get_job, request_cancel
from chatgptrest.core.prompt_policy import PromptPolicyViolation, enforce_prompt_submission_policy
from chatgptrest.core.control_plane import parse_host_port_from_url, port_open
from chatgptrest.core.state_machine import JobStatus
from chatgptrest.core import artifacts as job_artifacts
from chatgptrest.api.client_ip import get_client_ip
from chatgptrest.api.schemas import AnswerChunk, ConversationChunk, JobCreateRequest, JobEvent, JobEvents, JobView
from chatgptrest.api.write_guards import (
    enforce_cancel_client_name_allowlist as _enforce_cancel_client_name_allowlist,
    enforce_client_name_allowlist as _enforce_client_name_allowlist,
    enforce_direct_live_chatgpt_submission as _enforce_direct_live_chatgpt_submission,
    enforce_write_trace_headers as _enforce_write_trace_headers,
    extract_cancel_reason as _extract_cancel_reason,
    _normalize_reason_text,
)
from chatgptrest.api.routes_ops import action_hint_for_status as _action_hint_for_status
from chatgptrest.providers.registry import (
    PresetValidationError,
    ask_min_prompt_interval_seconds,
    ask_rate_limit_key,
    is_web_ask_kind,
    validate_ask_preset,
)


DONEISH_STATUSES: set[JobStatus] = {
    JobStatus.COMPLETED,
    JobStatus.ERROR,
    JobStatus.CANCELED,
    JobStatus.BLOCKED,
    JobStatus.COOLDOWN,
    JobStatus.NEEDS_FOLLOWUP,
}

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _driver_readiness(cfg: AppConfig) -> dict[str, Any]:
    raw_url = str(cfg.driver_url or cfg.chatgpt_mcp_url or "").strip()
    parsed = parse_host_port_from_url(raw_url, default_port=18701)
    if parsed is None:
        return {
            "ok": False,
            "driver_url": raw_url or None,
            "error": "invalid_driver_url",
        }
    host, port = parsed
    probe_host = "127.0.0.1" if host == "0.0.0.0" else host
    ok = port_open(probe_host, port, timeout_seconds=0.2)
    return {
        "ok": bool(ok),
        "driver_url": raw_url,
        "probe_host": probe_host,
        "probe_port": int(port),
    }


def _truncate_header(value: str | None, *, max_chars: int) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if len(raw) <= max(1, int(max_chars)):
        return raw
    return raw[: max(1, int(max_chars))] + "…"


def _inherit_parent_followup_web_ask_params(
    conn: sqlite3.Connection,
    *,
    kind: str,
    params_obj: dict[str, Any],
    parent_job_id: str | None,
) -> dict[str, Any]:
    params = dict(params_obj or {})
    if not parent_job_id or not is_web_ask_kind(kind):
        return params
    if "deep_research" in params:
        return params
    row = conn.execute(
        "SELECT kind, params_json FROM jobs WHERE job_id = ?",
        (str(parent_job_id),),
    ).fetchone()
    if row is None:
        return params
    parent_kind = str(row["kind"] or "").strip()
    if parent_kind != kind:
        return params
    try:
        parent_params = json.loads(str(row["params_json"] or "{}"))
    except Exception:
        parent_params = {}
    if isinstance(parent_params, dict) and bool(parent_params.get("deep_research") or False):
        params["deep_research"] = True
    return params


def _canonicalize_common_input(kind: str, input_obj: dict[str, Any]) -> dict[str, Any]:
    """
    Canonicalize fields that would otherwise create "semantic duplicates" that differ only by representation.

    Today the main culprit is `input.file_paths` being passed as relative vs absolute paths, which:
    - can create idempotency collisions (same key, different payload hash),
    - can also silently point to a different file depending on server working directory.

    Policy:
    - absolute paths are accepted as-is (after resolve).
    - relative paths are interpreted relative to this repo root (`ChatgptREST/`).
    - non-existent paths are rejected early (HTTP 400).
    """
    kind = str(kind or "").strip()
    # Best-effort: normalize common CLI-escaping artifact where "\n" is passed literally
    # (e.g. via bash quoting) instead of becoming a real newline. This helps idempotency and
    # prevents "semantic duplicates" that only differ by representation.
    q = input_obj.get("question")
    if isinstance(q, str) and "\\n" in q and "\n" not in q:
        out = dict(input_obj)
        out["question"] = q.replace("\\n", "\n")
        input_obj = out

    p = input_obj.get("prompt")
    if isinstance(p, str) and "\\n" in p and "\n" not in p:
        out = dict(input_obj)
        out["prompt"] = p.replace("\\n", "\n")
        input_obj = out

    file_paths = input_obj.get("file_paths")
    if file_paths is None:
        return input_obj
    if not isinstance(file_paths, list):
        raise HTTPException(status_code=400, detail="input.file_paths must be a list of strings")

    # Restrict file_paths to repo root and /tmp only (P2: narrowed from any path).
    _allowed_roots = [_REPO_ROOT, Path("/tmp")]

    normalized_entries = normalize_file_path_entries(str(raw) for raw in file_paths)
    out: list[str] = []
    for raw in normalized_entries:
        if not isinstance(raw, str) or not raw.strip():
            raise HTTPException(status_code=400, detail="input.file_paths must contain non-empty strings")
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (_REPO_ROOT / p).resolve()
        else:
            p = p.resolve()
        if not p.exists():
            raise HTTPException(
                status_code=400,
                detail=f"input.file_paths not found: {p.as_posix()} (pass an absolute path, or a path relative to ChatgptREST repo root)",
            )
        if not p.is_file():
            raise HTTPException(status_code=400, detail=f"input.file_paths must be files (not dirs): {p.as_posix()}")
        # Path restriction: must be under an allowed root
        if not any(p.is_relative_to(root) for root in _allowed_roots):
            raise HTTPException(
                status_code=403,
                detail=f"input.file_paths outside allowed directory: {p.as_posix()}",
            )
        out.append(p.as_posix())

    out_obj = dict(input_obj)
    out_obj["file_paths"] = out
    return out_obj


def _validate_chatgpt_web_ask_preset(params_obj: Any) -> None:
    try:
        validate_ask_preset(kind="chatgpt_web.ask", params_obj=params_obj)
    except PresetValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail)


def _validate_gemini_web_ask_preset(params_obj: Any) -> None:
    try:
        validate_ask_preset(kind="gemini_web.ask", params_obj=params_obj)
    except PresetValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail)


def _validate_qwen_web_ask_preset(params_obj: Any) -> None:
    try:
        validate_ask_preset(kind="qwen_web.ask", params_obj=params_obj)
    except PresetValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.detail)


def _enforce_kind_runtime_availability(*, kind: str) -> None:
    raw = str(kind or "").strip().lower()
    if raw.startswith("qwen_web.") and not _env_get_bool("CHATGPTREST_QWEN_ENABLED"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "provider_disabled",
                "detail": f"{kind} is disabled on this host",
                "hint": "Enable CHATGPTREST_QWEN_ENABLED=1 before submitting qwen_web jobs.",
            },
        )


def _request_attribution(request: Request) -> dict[str, Any]:
    """
    Record minimal, safe request metadata for /cancel attribution.

    We intentionally do NOT persist sensitive headers (Authorization/Cookie/etc).
    """
    out: dict[str, Any] = {
        "transport": "http",
        "received_at": float(time.time()),
        "server": {"hostname": socket.gethostname(), "pid": int(os.getpid())},
    }
    if request.client is not None:
        out["client"] = {"host": get_client_ip(request), "port": request.client.port}

    headers = request.headers
    h: dict[str, Any] = {}
    ua = _truncate_header(headers.get("user-agent"), max_chars=200)
    if ua:
        h["user_agent"] = ua

    x_client_name = _truncate_header(headers.get("x-client-name"), max_chars=200)
    if x_client_name:
        h["x_client_name"] = x_client_name

    x_client_instance = _truncate_header(headers.get("x-client-instance"), max_chars=200)
    if x_client_instance:
        h["x_client_instance"] = x_client_instance

    x_request_id = _truncate_header(headers.get("x-request-id"), max_chars=200)
    if x_request_id:
        h["x_request_id"] = x_request_id

    x_cancel_reason = _truncate_header(_normalize_reason_text(headers.get("x-cancel-reason")), max_chars=200)
    if x_cancel_reason:
        h["x_cancel_reason"] = x_cancel_reason

    if h:
        out["headers"] = h
    return out


def _require_ops_token_for_repair_kind(*, cfg: AppConfig, request: Request, kind: str) -> None:
    if not str(kind or "").strip().lower().startswith("repair."):
        return
    if not _truthy_env("CHATGPTREST_REQUIRE_OPS_TOKEN_FOR_REPAIR_KINDS", True):
        return

    ops_token = str(cfg.ops_token or "").strip()
    if not ops_token:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "repair_kind_ops_token_not_configured",
                "detail": "repair.* job submission requires CHATGPTREST_OPS_TOKEN to be configured",
                "hint": "Set CHATGPTREST_OPS_TOKEN and submit repair.* jobs with Authorization: Bearer <ops token>.",
            },
        )

    auth = str(request.headers.get("authorization") or "").strip()
    provided = auth.split(" ", 1)[1].strip() if auth.lower().startswith("bearer ") else ""
    if provided and hmac.compare_digest(provided, ops_token):
        return

    raise HTTPException(
        status_code=403,
        detail={
            "error": "repair_kind_requires_ops_token",
            "detail": "repair.* job submission requires Authorization: Bearer <ops token>",
            "hint": "Use the ops token for repair.* kinds; generic API tokens are not sufficient.",
        },
    )


def _estimate_wait(conn, *, cfg: AppConfig, job: Any) -> tuple[int | None, int | None, int | None]:
    kind = str(getattr(job, "kind", "") or "").strip()
    interval = ask_min_prompt_interval_seconds(cfg=cfg, kind=kind)
    rate_limit_key = ask_rate_limit_key(kind)
    if interval is None or rate_limit_key is None:
        return None, None, None
    phase = str(getattr(job, "phase", "") or "").strip().lower()
    if phase and phase != "send":
        return None, None, None
    if interval <= 0:
        return None, None, None

    row = conn.execute("SELECT last_ts FROM rate_limits WHERE k = ?", (rate_limit_key,)).fetchone()
    last_ts = float(row["last_ts"]) if row is not None and row["last_ts"] is not None else 0.0
    now = time.time()
    wait_to_next = max(0.0, last_ts + float(interval) - now)

    created_at = float(getattr(job, "created_at", 0.0) or 0.0)
    ahead = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM jobs
        WHERE kind = ?
          AND COALESCE(phase, 'send') = 'send'
          AND status IN (?,?,?)
          AND created_at < ?
        """,
        (
            kind,
            JobStatus.QUEUED.value,
            JobStatus.COOLDOWN.value,
            JobStatus.IN_PROGRESS.value,
            created_at,
        ),
    ).fetchone()
    queue_position = int(ahead["n"] or 0) if ahead is not None else 0
    estimated_wait_seconds = int(round(wait_to_next + float(queue_position) * float(interval)))
    return queue_position, max(0, estimated_wait_seconds), interval


def _action_hint_for_job(job: Any) -> str | None:
    status = str(getattr(job, "status", "") or "").strip().lower()
    phase = str(getattr(job, "phase", "") or "").strip().lower() or None
    return _action_hint_for_status(status=status, phase=phase)


def _job_event_summary(conn: sqlite3.Connection | None, *, job_id: str) -> dict[str, Any]:
    if conn is None:
        return {}
    rows = conn.execute(
        """
        SELECT id, ts, type
        FROM job_events
        WHERE job_id = ?
        ORDER BY id DESC
        LIMIT 64
        """,
        (job_id,),
    ).fetchall()
    if not rows:
        return {}

    summary: dict[str, Any] = {
        "last_event_type": str(rows[0]["type"] or "").strip() or None,
        "last_event_at": (float(rows[0]["ts"]) if rows[0]["ts"] is not None else None),
    }
    for row in rows:
        event_type = str(row["type"] or "").strip()
        event_ts = float(row["ts"]) if row["ts"] is not None else None
        if event_type == "prompt_sent" and "prompt_sent_at" not in summary:
            summary["prompt_sent_at"] = event_ts
        elif event_type == "assistant_answer_ready" and "assistant_answer_ready_at" not in summary:
            summary["assistant_answer_ready_at"] = event_ts
    return summary


def _completion_quality_for_job(job: Any, *, event_summary: dict[str, Any]) -> str | None:
    if getattr(job, "status", None) != JobStatus.COMPLETED:
        return None
    last_event_type = str(event_summary.get("last_event_type") or "").strip().lower()
    if last_event_type == "completion_guard_completed_under_min_chars":
        return "completed_under_min_chars"
    kind = str(getattr(job, "kind", "") or "").strip().lower()
    answer_chars = getattr(job, "answer_chars", None)
    if not is_web_ask_kind(kind):
        return "final"
    if not isinstance(answer_chars, int) or answer_chars <= 0:
        return "final"

    # ── Content-based quality check for short answers ────────────────
    # When answer is in the suspect range (< 800 chars), load the text
    # and run heuristic classification to detect meta-commentary.
    if answer_chars < 800:
        answer_text = ""
        answer_path = getattr(job, "answer_path", None)
        if answer_path:
            try:
                from chatgptrest.core.conversation_exports import classify_answer_quality
                full = (_REPO_ROOT / str(answer_path)).resolve()
                if full.is_file():
                    answer_text = full.read_text(encoding="utf-8", errors="replace")[:2000]
                quality = classify_answer_quality(answer_text, answer_chars=answer_chars)
                if quality != "final":
                    return quality
            except Exception:
                pass  # fall through to legacy check

    # Legacy fallback: hard threshold
    if isinstance(answer_chars, int) and answer_chars < 400:
        return "suspect_short_answer"
    return "final"


def _phase_detail_for_job(job: Any, *, event_summary: dict[str, Any], completion_quality: str | None) -> str | None:
    status = str(getattr(job, "status", "") or "").strip().lower()
    phase = str(getattr(job, "phase", "") or "").strip().lower()
    if status == JobStatus.COMPLETED.value:
        if completion_quality and completion_quality != "final":
            if completion_quality.startswith("completed_"):
                return completion_quality
            return f"completed_{completion_quality}"
        return "completed"
    if phase == "send":
        if not event_summary.get("prompt_sent_at"):
            return "awaiting_prompt_send"
        if not event_summary.get("assistant_answer_ready_at"):
            return "awaiting_assistant_answer"
        return "awaiting_post_send_reconciliation"
    if phase == "wait":
        if event_summary.get("assistant_answer_ready_at"):
            return "awaiting_export_reconciliation"
        if event_summary.get("prompt_sent_at"):
            return "awaiting_assistant_answer"
        return "awaiting_wait_poll"
    return None


def _compute_recovery_status(job: Any, *, event_summary: dict[str, Any]) -> dict[str, Any]:
    """Compute recovery_status / recovery_detail / safe_next_action for a job.

    These fields give clients actionable insight into system health without
    requiring them to parse internal error types or event sequences.
    """
    status = str(getattr(job, "status", "") or "").strip().lower()
    last_error_type = str(getattr(job, "last_error_type", "") or "").strip().lower()
    last_error = str(getattr(job, "last_error", "") or "").strip()
    attempts = int(getattr(job, "attempts", 0) or 0)

    # Terminal success
    if status == "completed":
        return {
            "recovery_status": "healthy",
            "recovery_detail": None,
            "safe_next_action": None,
        }

    # In progress — normal
    if status in ("queued", "in_progress"):
        if attempts > 1:
            return {
                "recovery_status": "recovering",
                "recovery_detail": f"Retry attempt {attempts}, previous attempt failed",
                "safe_next_action": "wait",
            }
        return {
            "recovery_status": "healthy",
            "recovery_detail": None,
            "safe_next_action": "wait",
        }

    # Cooldown — transient, will auto-recover
    if status == "cooldown":
        retry_after = None
        if getattr(job, "not_before", None) and job.not_before > time.time():
            retry_after = int(job.not_before - time.time())
        detail = f"Rate limited, auto-retry in {retry_after}s" if retry_after else "Rate limited, auto-retry pending"
        return {
            "recovery_status": "recovering",
            "recovery_detail": detail,
            "safe_next_action": "wait",
        }

    # Needs followup — may auto-recover or need human
    if status == "needs_followup":
        # Provider auth/region gates usually require a human to restore the session.
        followup_signal = f"{last_error_type} {last_error}".lower()
        if any(token in followup_signal for token in ("login", "loggedin", "captcha", "region")):
            return {
                "recovery_status": "needs_human",
                "recovery_detail": f"Provider issue: {last_error[:120]}",
                "safe_next_action": "escalate",
            }
        return {
            "recovery_status": "recovering",
            "recovery_detail": f"Follow-up needed: {last_error[:120]}" if last_error else "Follow-up action pending",
            "safe_next_action": "wait",
        }

    # Blocked — usually chrome/driver issue
    if status == "blocked":
        if "chrome" in last_error_type or "target" in last_error_type or "closed" in last_error_type:
            return {
                "recovery_status": "recovering",
                "recovery_detail": "Browser recovered, retry pending",
                "safe_next_action": "wait",
            }
        return {
            "recovery_status": "needs_human",
            "recovery_detail": f"Blocked: {last_error[:120]}" if last_error else "Blocked by system issue",
            "safe_next_action": "escalate",
        }

    # Error — terminal failure
    if status == "error":
        if attempts > 2:
            return {
                "recovery_status": "needs_human",
                "recovery_detail": f"Failed after {attempts} attempts: {last_error[:100]}" if last_error else f"Failed after {attempts} attempts",
                "safe_next_action": "escalate",
            }
        return {
            "recovery_status": "needs_human",
            "recovery_detail": f"Error: {last_error[:120]}" if last_error else "Job failed",
            "safe_next_action": "retry",
        }

    # Canceled
    if status == "canceled":
        return {
            "recovery_status": "healthy",
            "recovery_detail": "Job was canceled",
            "safe_next_action": None,
        }

    return {
        "recovery_status": "healthy",
        "recovery_detail": None,
        "safe_next_action": None,
    }

def _action_hint_for_job_view(job: Any, *, phase_detail: str | None, completion_quality: str | None) -> str | None:
    status = str(getattr(job, "status", "") or "").strip().lower()
    phase = str(getattr(job, "phase", "") or "").strip().lower() or None
    if status == JobStatus.COMPLETED.value and completion_quality and completion_quality != "final":
        return "review_completed_answer"
    if status == JobStatus.IN_PROGRESS.value and phase_detail == "awaiting_prompt_send":
        return "wait_for_prompt_send"
    if status == JobStatus.IN_PROGRESS.value and phase_detail == "awaiting_assistant_answer":
        return "wait_for_assistant_answer"
    if status == JobStatus.IN_PROGRESS.value and phase_detail == "awaiting_export_reconciliation":
        return "wait_for_export_reconciliation"
    return _action_hint_for_status(status=status, phase=phase)


def _job_view(
    cfg: AppConfig,
    job: Any,
    *,
    conn: sqlite3.Connection | None = None,
    queue_position: int | None = None,
    estimated_wait_seconds: int | None = None,
    min_interval_seconds: int | None = None,
) -> JobView:
    preview = job_artifacts.read_text_preview(
        artifacts_dir=cfg.artifacts_dir,
        path=job.answer_path,
        max_chars=cfg.preview_chars,
    )
    event_summary = _job_event_summary(conn, job_id=str(job.job_id))
    completion_quality = _completion_quality_for_job(job, event_summary=event_summary)
    phase_detail = _phase_detail_for_job(job, event_summary=event_summary, completion_quality=completion_quality)
    recovery = _compute_recovery_status(job, event_summary=event_summary)
    reason_visible = job.status in {
        JobStatus.ERROR,
        JobStatus.BLOCKED,
        JobStatus.COOLDOWN,
        JobStatus.NEEDS_FOLLOWUP,
        JobStatus.CANCELED,
    }
    return JobView(
        job_id=job.job_id,
        kind=(job.kind or None),
        parent_job_id=(job.parent_job_id or None),
        phase=(getattr(job, "phase", None) or None),
        phase_detail=phase_detail,
        status=job.status.value,
        path=job.answer_path,
        preview=preview,
        answer_chars=(job.answer_chars if job.answer_chars is not None else None),
        conversation_url=(job.conversation_url or None),
        conversation_export_format=(job.conversation_export_format or None),
        conversation_export_path=(job.conversation_export_path or None),
        conversation_export_sha256=(job.conversation_export_sha256 or None),
        conversation_export_chars=(job.conversation_export_chars if job.conversation_export_chars is not None else None),
        created_at=job.created_at,
        updated_at=job.updated_at,
        not_before=job.not_before or None,
        attempts=(job.attempts if getattr(job, "attempts", None) is not None else None),
        max_attempts=(job.max_attempts if getattr(job, "max_attempts", None) is not None else None),
        retry_after_seconds=(max(0, int(job.not_before - time.time())) if job.not_before and job.not_before > time.time() else None),
        queue_position=queue_position,
        estimated_wait_seconds=estimated_wait_seconds,
        min_prompt_interval_seconds=min_interval_seconds,
        action_hint=_action_hint_for_job_view(job, phase_detail=phase_detail, completion_quality=completion_quality),
        completion_quality=completion_quality,
        last_event_type=(event_summary.get("last_event_type") or None),
        last_event_at=(event_summary.get("last_event_at") if event_summary.get("last_event_at") is not None else None),
        prompt_sent_at=(event_summary.get("prompt_sent_at") if event_summary.get("prompt_sent_at") is not None else None),
        assistant_answer_ready_at=(
            event_summary.get("assistant_answer_ready_at")
            if event_summary.get("assistant_answer_ready_at") is not None
            else None
        ),
        cancel_requested_at=job.cancel_requested_at,
        reason_type=(job.last_error_type if reason_visible else None),
        reason=(job.last_error if reason_visible else None),
        recovery_status=recovery["recovery_status"],
        recovery_detail=recovery["recovery_detail"],
        safe_next_action=recovery["safe_next_action"],
        error=(job.last_error if job.status == JobStatus.ERROR else None),
    )


def make_router(cfg: AppConfig) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/jobs", response_model=JobView)
    def create_job_route(
        req: JobCreateRequest,
        request: Request,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ) -> JobView:
        _enforce_client_name_allowlist(request)
        _enforce_write_trace_headers(request, operation="create_job")
        kind = str(req.kind or "").strip()
        _enforce_kind_runtime_availability(kind=kind)
        _require_ops_token_for_repair_kind(cfg=cfg, request=request, kind=kind)
        input_obj: dict[str, Any] = dict(req.input or {})
        params_obj: dict[str, Any] = dict(req.params or {})
        if is_web_ask_kind(kind) or kind in ("gemini_web.generate_image", "gemini_web.extract_answer"):
            input_obj = _canonicalize_common_input(kind, input_obj)
        if is_web_ask_kind(kind):
            try:
                validate_ask_preset(kind=kind, params_obj=params_obj)
            except PresetValidationError as exc:
                raise HTTPException(status_code=400, detail=exc.detail)
        parent_job_id = None
        try:
            raw = input_obj.get("parent_job_id")
            if isinstance(raw, str) and raw.strip():
                parent_job_id = raw.strip()
        except Exception:
            parent_job_id = None
        allow_queue = False
        try:
            allow_queue = bool(params_obj.get("allow_queue") or False)
        except Exception:
            allow_queue = False

        if kind == "gemini_web.ask":
            raw_repo = (input_obj or {}).get("github_repo")
            if raw_repo is not None and not isinstance(raw_repo, str):
                raise HTTPException(status_code=400, detail="input.github_repo must be a string")
            if isinstance(raw_repo, str) and raw_repo.strip():
                enable_import_code = False
                try:
                    enable_import_code = bool(params_obj.get("enable_import_code") or False)
                except Exception:
                    enable_import_code = False
                if not enable_import_code:
                    raise HTTPException(
                        status_code=400,
                        detail="gemini_web.ask input.github_repo requires params.enable_import_code=true",
                    )

        if _truthy_env("CHATGPTREST_ENFORCE_PROMPT_SUBMISSION_POLICY", True):
            try:
                enforce_prompt_submission_policy(
                    kind=kind,
                    input_obj=input_obj,
                    params_obj=params_obj,
                    client_obj=(req.client if isinstance(req.client, dict) else None),
                )
            except PromptPolicyViolation as exc:
                raise HTTPException(status_code=400, detail=exc.detail) from exc
        _enforce_direct_live_chatgpt_submission(
            request,
            kind=kind,
            params_obj=params_obj,
            client_obj=(req.client if isinstance(req.client, dict) else None),
        )
        enforce_single_flight = _truthy_env("CHATGPTREST_CONVERSATION_SINGLE_FLIGHT", True)
        requested_by = _request_attribution(request)

        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                params_obj = _inherit_parent_followup_web_ask_params(
                    conn,
                    kind=kind,
                    params_obj=params_obj,
                    parent_job_id=parent_job_id,
                )
                job = create_job(
                    conn,
                    artifacts_dir=cfg.artifacts_dir,
                    idempotency_key=idempotency_key,
                    kind=kind,
                    input=input_obj,
                    params=params_obj,
                    max_attempts=cfg.max_attempts,
                    parent_job_id=parent_job_id,
                    client=(dict(req.client) if isinstance(req.client, dict) else None),
                    requested_by=requested_by,
                    allow_queue=allow_queue,
                    enforce_conversation_single_flight=enforce_single_flight,
                )
                queue_pos, est_wait, min_interval = _estimate_wait(conn, cfg=cfg, job=job)
                conn.commit()
        except ConversationBusy as exc:
            # Prevent multiple overlapping user messages in the same ChatGPT conversation
            # (wind-control risk). Caller should wait/cancel the active job, or explicitly
            # opt into queuing by setting `params.allow_queue=true`.
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "conversation_busy",
                    "active_job_id": exc.active_job_id,
                    "active_status": exc.active_status,
                    "active_phase": exc.active_phase,
                    "active_updated_at": exc.active_updated_at,
                    "conversation_url": exc.conversation_url,
                    "retry_after_seconds": max(5, int(cfg.min_prompt_interval_seconds or 30)),
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except IdempotencyCollision as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "idempotency_collision",
                    "message": str(exc),
                    "idempotency_key": getattr(exc, "idempotency_key", None),
                    "existing_job_id": getattr(exc, "existing_job_id", None),
                    "existing_request_hash": getattr(exc, "existing_hash", None),
                    "request_hash": getattr(exc, "request_hash", None),
                    "hint": "Common cause: request fields differ only by representation (e.g. file_paths absolute vs relative).",
                },
            )
        with connect(cfg.db_path) as conn:
            return _job_view(
                cfg,
                job,
                conn=conn,
                queue_position=queue_pos,
                estimated_wait_seconds=est_wait,
                min_interval_seconds=min_interval,
            )

    @router.get("/v1/jobs/{job_id}", response_model=JobView)
    def get_job_route(job_id: str) -> JobView:
        with connect(cfg.db_path) as conn:
            job = get_job(conn, job_id=job_id)
            if job is not None:
                queue_pos, est_wait, min_interval = _estimate_wait(conn, cfg=cfg, job=job)
            else:
                queue_pos, est_wait, min_interval = None, None, None
            if job is None:
                raise HTTPException(status_code=404, detail="job not found")
            job_artifacts.reconcile_job_artifacts(artifacts_dir=cfg.artifacts_dir, job=job)
            return _job_view(
                cfg,
                job,
                conn=conn,
                queue_position=queue_pos,
                estimated_wait_seconds=est_wait,
                min_interval_seconds=min_interval,
            )

    @router.get("/v1/jobs/{job_id}/result", response_model=JobView)
    def get_result_route(job_id: str) -> JobView:
        return get_job_route(job_id)

    @router.post("/v1/jobs/{job_id}/cancel", response_model=JobView)
    def cancel_route(job_id: str, request: Request) -> JobView:
        _enforce_client_name_allowlist(request)
        _enforce_cancel_client_name_allowlist(request)
        _enforce_write_trace_headers(request, operation="cancel_job")
        cancel_reason = _extract_cancel_reason(request)
        requested_by = _request_attribution(request)
        if cancel_reason:
            requested_by["cancel_reason"] = cancel_reason
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                job = request_cancel(
                    conn,
                    artifacts_dir=cfg.artifacts_dir,
                    job_id=job_id,
                    requested_by=requested_by,
                    reason=cancel_reason,
                )
                queue_pos, est_wait, min_interval = _estimate_wait(conn, cfg=cfg, job=job)
                conn.commit()
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found")
        with connect(cfg.db_path) as conn:
            return _job_view(
                cfg,
                job,
                conn=conn,
                queue_position=queue_pos,
                estimated_wait_seconds=est_wait,
                min_interval_seconds=min_interval,
            )

    @router.get("/v1/jobs/{job_id}/wait", response_model=JobView)
    async def wait_route(
        job_id: str,
        timeout_seconds: int = 60,
        poll_seconds: float = 1.0,
        auto_wait_cooldown: bool = False,
    ) -> JobView:
        deadline = time.time() + max(0.0, float(timeout_seconds))
        poll = max(0.2, float(poll_seconds))
        doneish = DONEISH_STATUSES if not auto_wait_cooldown else (DONEISH_STATUSES - {JobStatus.COOLDOWN})
        with connect(cfg.db_path) as conn:
            while True:
                job = get_job(conn, job_id=job_id)
                if job is None:
                    raise HTTPException(status_code=404, detail="job not found")
                job_artifacts.reconcile_job_artifacts(artifacts_dir=cfg.artifacts_dir, job=job)
                queue_pos, est_wait, min_interval = _estimate_wait(conn, cfg=cfg, job=job)
                if job.status in doneish:
                    return _job_view(
                        cfg,
                        job,
                        conn=conn,
                        queue_position=queue_pos,
                        estimated_wait_seconds=est_wait,
                        min_interval_seconds=min_interval,
                    )
                now = time.time()
                if now >= deadline:
                    return _job_view(
                        cfg,
                        job,
                        conn=conn,
                        queue_position=queue_pos,
                        estimated_wait_seconds=est_wait,
                        min_interval_seconds=min_interval,
                    )
                if auto_wait_cooldown and job.status == JobStatus.COOLDOWN and job.not_before and job.not_before > now:
                    sleep_for = min(float(job.not_before - now), float(deadline - now), 30.0)
                    await asyncio.sleep(max(0.2, sleep_for))
                else:
                    await asyncio.sleep(poll)

    @router.get("/v1/jobs/{job_id}/events", response_model=JobEvents)
    def events_route(job_id: str, after_id: int = 0, limit: int = 200) -> JobEvents:
        after_id = max(0, int(after_id))
        limit = max(1, min(1000, int(limit)))
        with connect(cfg.db_path) as conn:
            exists = conn.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail="job not found")
            rows = conn.execute(
                """
                SELECT id, job_id, ts, type, payload_json
                FROM job_events
                WHERE job_id = ?
                  AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (job_id, after_id, limit),
            ).fetchall()
        events: list[JobEvent] = []
        for r in rows:
            payload = None
            raw = r["payload_json"]
            if raw is not None:
                try:
                    payload = json.loads(str(raw))
                    if not isinstance(payload, dict):
                        payload = {"_raw": str(raw)}
                except Exception:
                    payload = {"_raw": str(raw)}
            events.append(
                JobEvent(
                    id=int(r["id"]),
                    job_id=str(r["job_id"]),
                    ts=float(r["ts"]),
                    type=str(r["type"]),
                    payload=payload,
                )
            )
        next_after = int(events[-1].id) if events else after_id
        return JobEvents(job_id=job_id, after_id=after_id, next_after_id=next_after, events=events)

    @router.get("/v1/jobs/{job_id}/answer", response_model=AnswerChunk)
    def answer_chunk_route(job_id: str, offset: int = 0, max_chars: int = 8000) -> AnswerChunk:
        with connect(cfg.db_path) as conn:
            job = get_job(conn, job_id=job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        if job.status != JobStatus.COMPLETED or not job.answer_path:
            retry_after = (
                max(0, int(job.not_before - time.time()))
                if job.not_before and job.not_before > time.time()
                else None
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "answer not ready",
                    "status": job.status.value,
                    "retry_after_seconds": retry_after,
                },
            )
        try:
            chunk, next_offset, done, used_offset = job_artifacts.read_utf8_chunk_by_bytes(
                artifacts_dir=cfg.artifacts_dir,
                path=job.answer_path,
                offset=int(offset),
                max_bytes=int(max_chars),
            )
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail="answer artifact missing")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return AnswerChunk(
            job_id=job_id,
            offset=max(0, int(used_offset)),
            returned_chars=len(chunk),
            next_offset=next_offset,
            done=bool(done),
            chunk=chunk,
        )

    @router.get("/v1/jobs/{job_id}/conversation", response_model=ConversationChunk)
    def conversation_chunk_route(job_id: str, offset: int = 0, max_chars: int = 8000) -> ConversationChunk:
        with connect(cfg.db_path) as conn:
            job = get_job(conn, job_id=job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        path = str(job.conversation_export_path or "").strip()
        if not path:
            retry_after = (
                max(0, int(job.not_before - time.time()))
                if job.not_before and job.not_before > time.time()
                else None
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "conversation export not ready",
                    "status": job.status.value,
                    "retry_after_seconds": retry_after,
                },
            )
        try:
            chunk, next_offset, done, used_offset = job_artifacts.read_utf8_chunk_by_bytes(
                artifacts_dir=cfg.artifacts_dir,
                path=path,
                offset=int(offset),
                max_bytes=int(max_chars),
            )
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail="conversation export artifact missing")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return ConversationChunk(
            job_id=job_id,
            offset=max(0, int(used_offset)),
            returned_chars=len(chunk),
            next_offset=next_offset,
            done=bool(done),
            chunk=chunk,
        )

    @router.get("/v1/jobs/{job_id}/stream")
    async def stream_route(job_id: str, poll_seconds: float = 1.0) -> Any:
        """SSE endpoint: stream job status + events in real-time until terminal."""
        from sse_starlette.sse import EventSourceResponse

        poll = max(0.5, min(5.0, float(poll_seconds)))

        async def _event_generator():
            last_event_id = 0
            last_status = ""
            try:
                while True:
                    with connect(cfg.db_path) as conn:
                        job = get_job(conn, job_id=job_id)
                        if job is None:
                            yield {"event": "error", "data": json.dumps({"error": "job_not_found"})}
                            return

                        status = job.status.value
                        phase = str(getattr(job, "phase", "") or "").strip() or None

                        # Emit status change
                        if status != last_status:
                            event_summary = _job_event_summary(conn, job_id=job_id)
                            completion_quality = _completion_quality_for_job(job, event_summary=event_summary)
                            phase_detail = _phase_detail_for_job(
                                job, event_summary=event_summary, completion_quality=completion_quality,
                            )
                            recovery = _compute_recovery_status(job, event_summary=event_summary)
                            yield {
                                "event": "status",
                                "data": json.dumps({
                                    "job_id": job_id,
                                    "status": status,
                                    "phase": phase,
                                    "phase_detail": phase_detail,
                                    "action_hint": _action_hint_for_job_view(
                                        job, phase_detail=phase_detail, completion_quality=completion_quality,
                                    ),
                                    "completion_quality": completion_quality,
                                    "recovery_status": recovery["recovery_status"],
                                    "recovery_detail": recovery["recovery_detail"],
                                    "safe_next_action": recovery["safe_next_action"],
                                }),
                            }
                            last_status = status

                        # Emit new events
                        rows = conn.execute(
                            """
                            SELECT id, ts, type, payload_json
                            FROM job_events
                            WHERE job_id = ? AND id > ?
                            ORDER BY id ASC
                            LIMIT 50
                            """,
                            (job_id, last_event_id),
                        ).fetchall()
                        for r in rows:
                            payload = None
                            raw = r["payload_json"]
                            if raw is not None:
                                try:
                                    payload = json.loads(str(raw))
                                except Exception:
                                    payload = {"_raw": str(raw)[:500]}
                            yield {
                                "event": "job_event",
                                "data": json.dumps({
                                    "id": int(r["id"]),
                                    "ts": float(r["ts"]),
                                    "type": str(r["type"]),
                                    "payload": payload,
                                }),
                            }
                            last_event_id = int(r["id"])

                        # Terminate on terminal status
                        if job.status in DONEISH_STATUSES:
                            yield {"event": "done", "data": json.dumps({"status": status, "job_id": job_id})}
                            return

                    await asyncio.sleep(poll)
            except asyncio.CancelledError:
                return

        return EventSourceResponse(_event_generator())

    @router.get("/healthz")
    def healthz() -> dict[str, Any]:
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("SELECT 1")
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={"ok": False, "status": "error", "error_type": type(exc).__name__, "error": str(exc)[:500]},
            )
        return {"ok": True, "status": "ok"}

    @router.get("/livez")
    def livez() -> dict[str, Any]:
        return {"ok": True, "status": "live"}

    @router.get("/readyz")
    def readyz(request: Request) -> dict[str, Any]:
        checks: dict[str, Any] = {}
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("SELECT 1")
            checks["db"] = {"ok": True}
        except Exception as exc:
            checks["db"] = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:500]}

        checks["driver"] = _driver_readiness(cfg)
        startup_manifest = getattr(getattr(request, "app", None), "state", None)
        manifest = getattr(startup_manifest, "startup_manifest", None)
        router_errors = []
        route_count = 0
        if isinstance(manifest, dict):
            router_errors = list(manifest.get("router_load_errors") or [])
            route_count = int(manifest.get("route_count") or 0)
        checks["startup"] = {
            "ok": not bool(router_errors),
            "status": "ready" if not router_errors else "router_load_failed",
            "route_count": route_count,
            "router_load_errors": router_errors,
        }
        ready = (
            bool(checks["db"].get("ok"))
            and bool(checks["driver"].get("ok"))
            and bool(checks["startup"].get("ok"))
        )
        if not ready:
            raise HTTPException(status_code=503, detail={"ok": False, "status": "not_ready", "checks": checks})
        return {"ok": True, "status": "ready", "checks": checks}

    @router.get("/health")
    def health() -> dict[str, Any]:
        return healthz()

    @router.get("/v1/health")
    def v1_health() -> dict[str, Any]:
        return healthz()

    return router
