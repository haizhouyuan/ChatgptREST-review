from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any

from chatgptrest.core import artifacts
from chatgptrest.core.db import insert_event
from chatgptrest.core.idempotency import IdempotencyCollision, begin, hash_request
from chatgptrest.core.issue_autoreport import (
    AUTO_ISSUE_SOURCE,
    auto_issue_fingerprint,
    issue_autoreport_statuses,
    issue_project_from_client_json,
    issue_severity_for_status,
    ws_single,
)
from chatgptrest.core.pause import get_pause_state, pause_filter_allows_job
from chatgptrest.core.state_machine import JobStatus, can_transition, is_terminal
from chatgptrest.providers.registry import is_web_ask_kind, provider_spec_for_kind, web_ask_kinds


def _now() -> float:
    return time.time()


def _truthy_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    raw = raw.strip().lower()
    if not raw:
        return bool(default)
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return int(default)
    raw = raw.strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _retryable_send_attempts_cap() -> int:
    # Cap for extending max_attempts on retryable *send-phase* failures for ask jobs.
    # This helps jobs survive transient infra/network incidents without requiring client resubmission,
    # while still providing an upper bound to prevent infinite send-side loops.
    return max(1, _env_int("CHATGPTREST_RETRYABLE_SEND_ATTEMPTS_CAP", 20))


def _retryable_send_max_extensions() -> int:
    # Cap for how many times a single send-stage job is allowed to auto-extend max_attempts.
    # Prevents endless loops where the same retryable error recurs and max_attempts keeps growing.
    return max(0, _env_int("CHATGPTREST_RETRYABLE_SEND_MAX_EXTENSIONS", 1))


def _retryable_send_extensions_used(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    error_type: str | None = None,
) -> int:
    rows = conn.execute(
        "SELECT payload_json FROM job_events WHERE job_id = ? AND type = ? ORDER BY id ASC",
        (job_id, "max_attempts_extended"),
    ).fetchall()
    wanted = str(error_type or "").strip().lower()
    used = 0
    for row in rows:
        payload_raw = row["payload_json"] if row is not None else None
        try:
            payload = json.loads(str(payload_raw or "{}"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        phase = str(payload.get("phase") or "").strip().lower()
        if phase == "wait":
            continue
        if wanted:
            ev_err = str(payload.get("error_type") or "").strip().lower()
            if ev_err != wanted:
                continue
        used += 1
    return int(used)


def _looks_like_sticky_upload_surface_closed(error_type: str | None, error: str | None) -> bool:
    et = str(error_type or "").strip().lower()
    msg = str(error or "").strip().lower()
    if "targetclosed" not in et and "target page, context or browser has been closed" not in msg:
        return False
    if "set_input_files" in msg:
        return True
    if "input[type='file']" in msg or 'input[type="file"]' in msg:
        return True
    return False


def _looks_like_qwen_cdp_unavailable(error_type: str | None, error: str | None) -> bool:
    et = str(error_type or "").strip().lower()
    msg = str(error or "").strip().lower()
    if "qwen cdp connect failed" in msg:
        return True
    if "qwen_cdp_url" in msg and "cdp connect failed" in msg:
        return True
    if "qwen chrome" in msg and "cdp" in msg:
        return True
    if "qwen" in msg and "connect_over_cdp" in msg:
        return True
    return et in {"infraerror", "runtimeerror"} and "cdp connect failed" in msg and "qwen" in msg


DEFAULT_PHASE = "send"

_CHATGPT_CONVERSATION_ID_RE = re.compile(r"/c/([0-9a-f-]{36})", re.I)
_GEMINI_CONVERSATION_ID_RE = re.compile(r"/app/([0-9a-zA-Z_-]{8,})")
_QWEN_CONVERSATION_ID_RE = re.compile(r"/chat/([0-9a-f]{32})", re.I)
_CHATGPT_URL_HOST_RE = re.compile(r"(?:^|[/.])chatgpt\.com\b|(?:^|[/.])chat\.openai\.com\b", re.I)
_GEMINI_URL_HOST_RE = re.compile(r"(?:^|[/.])gemini\.google\.com\b", re.I)
_QWEN_URL_HOST_RE = re.compile(r"(?:^|[/.])qianwen\.com\b", re.I)
_GEMINI_BASE_APP_URL_RE = re.compile(r"^https?://gemini\.google\.com/app/?(?:\?.*)?$", re.I)
_CHATGPT_BASE_APP_URL_RE = re.compile(r"^https?://(?:chatgpt\.com|chat\.openai\.com)/?(?:\?.*)?$", re.I)
_WEB_ASK_KIND_SQL = ", ".join([f"'{k}'" for k in sorted(web_ask_kinds())])

# Whitelist of column names allowed in transition() updates dict.
# Prevents SQL injection via f-string column interpolation.
_TRANSITION_UPDATE_WHITELIST: frozenset[str] = frozenset({
    "phase",
    "not_before",
    "cancel_requested_at",
    "last_error_type",
    "last_error",
    "max_attempts",
    "lease_owner",
    "lease_expires_at",
    "lease_token",
    "updated_at",
    "conversation_url",
    "conversation_id",
    "conversation_export_format",
    "conversation_export_path",
    "conversation_export_sha256",
    "conversation_export_chars",
    "answer_format",
    "answer_path",
    "answer_sha256",
    "answer_chars",
})


def _gemini_is_base_app_url(url: str) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    if _GEMINI_CONVERSATION_ID_RE.search(raw):
        return False
    return bool(_GEMINI_BASE_APP_URL_RE.match(raw))


def _chatgpt_is_base_app_url(url: str) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    if _CHATGPT_CONVERSATION_ID_RE.search(raw):
        return False
    return bool(_CHATGPT_BASE_APP_URL_RE.match(raw))


def _gemini_is_thread_url(url: str) -> bool:
    return bool(_GEMINI_CONVERSATION_ID_RE.search(str(url or "").strip()))


def _conversation_id(url: str) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    m = _CHATGPT_CONVERSATION_ID_RE.search(raw)
    if m:
        return str(m.group(1)).lower()
    m = _GEMINI_CONVERSATION_ID_RE.search(raw)
    if m:
        return str(m.group(1)).lower()
    m = _QWEN_CONVERSATION_ID_RE.search(raw)
    if m:
        return str(m.group(1)).lower()
    # Only thread URLs have a meaningful "conversation". Treat other ChatGPT/Gemini/Qwen pages (including
    # https://chatgpt.com/ or https://www.qianwen.com/) as not having a conversation_id, otherwise the base URL becomes
    # a global single-flight key that can block unrelated jobs.
    if _CHATGPT_URL_HOST_RE.search(raw) or _GEMINI_URL_HOST_RE.search(raw) or _QWEN_URL_HOST_RE.search(raw):
        return None
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:32]


def _conversation_platform(url: str | None) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    if _GEMINI_URL_HOST_RE.search(raw):
        return "gemini"
    if _QWEN_URL_HOST_RE.search(raw):
        return "qwen"
    if _CHATGPT_URL_HOST_RE.search(raw):
        return "chatgpt"
    return None


def _validate_conversation_url_for_kind(*, kind: str, conversation_url: str | None) -> None:
    url = str(conversation_url or "").strip()
    if not url:
        return
    platform = _conversation_platform(url)
    k = str(kind or "").strip()
    spec = provider_spec_for_kind(k)
    provider = spec.provider_id if spec is not None else None
    if platform == "gemini" and provider == "chatgpt":
        raise ValueError(
            f"conversation_url host looks like Gemini ({url}); cannot use kind={k}. "
            "Use kind=gemini_web.ask (or chatgptrest_gemini_ask_submit)."
        )
    if platform == "chatgpt" and provider == "gemini":
        raise ValueError(
            f"conversation_url host looks like ChatGPT ({url}); cannot use kind={k}. "
            "Use kind=chatgpt_web.ask (or chatgptrest_chatgpt_ask_submit)."
        )
    if platform == "qwen" and provider in {"chatgpt", "gemini"}:
        raise ValueError(
            f"conversation_url host looks like Qwen ({url}); cannot use kind={k}. "
            "Use kind=qwen_web.ask (or chatgptrest_qwen_ask_submit)."
        )
    if platform in {"chatgpt", "gemini"} and provider == "qwen":
        raise ValueError(
            f"conversation_url host is not Qwen ({url}); cannot use kind={k}. "
            "Use kind=qwen_web.ask with a qianwen.com thread URL."
        )


def _normalize_phase(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw == "wait":
        return "wait"
    return DEFAULT_PHASE


def _normalize_error_fields(error_type: str | None, error: str | None) -> tuple[str, str]:
    et = str(error_type or "RuntimeError")
    msg = str(error or "")
    if not msg.strip():
        msg = f"<{et}: empty error>"
    return et, msg


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    kind: str
    phase: str
    status: JobStatus
    created_at: float
    updated_at: float
    not_before: float
    attempts: int
    max_attempts: int
    cancel_requested_at: float | None
    lease_owner: str | None
    lease_expires_at: float | None
    lease_token: str | None
    client_json: str | None
    parent_job_id: str | None
    conversation_url: str | None
    conversation_id: str | None
    conversation_export_format: str | None
    conversation_export_path: str | None
    conversation_export_sha256: str | None
    conversation_export_chars: int | None
    answer_format: str | None
    answer_path: str | None
    answer_sha256: str | None
    answer_chars: int | None
    last_error_type: str | None
    last_error: str | None


class LeaseLost(RuntimeError):
    pass


class AlreadyFinished(RuntimeError):
    pass


class ConversationBusy(RuntimeError):
    def __init__(
        self,
        *,
        conversation_url: str | None,
        active_job_id: str,
        active_status: str,
        active_phase: str | None = None,
        active_updated_at: float | None = None,
        reason: str | None = None,
    ) -> None:
        msg = reason or "conversation busy"
        super().__init__(msg)
        self.conversation_url = str(conversation_url or "").strip() or None
        self.active_job_id = str(active_job_id)
        self.active_status = str(active_status)
        self.active_phase = (str(active_phase).strip() if active_phase is not None else None) or None
        self.active_updated_at = (float(active_updated_at) if active_updated_at is not None else None)


def _row_to_job(row: sqlite3.Row) -> JobRecord:
    return JobRecord(
        job_id=str(row["job_id"]),
        kind=str(row["kind"]),
        phase=_normalize_phase(row["phase"] if "phase" in row.keys() else None),
        status=JobStatus(str(row["status"])),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        not_before=float(row["not_before"] or 0.0),
        attempts=int(row["attempts"] or 0),
        max_attempts=int(row["max_attempts"] or 0),
        cancel_requested_at=(float(row["cancel_requested_at"]) if row["cancel_requested_at"] is not None else None),
        lease_owner=(str(row["lease_owner"]) if row["lease_owner"] is not None else None),
        lease_expires_at=(float(row["lease_expires_at"]) if row["lease_expires_at"] is not None else None),
        lease_token=(str(row["lease_token"]) if row["lease_token"] is not None else None),
        client_json=(str(row["client_json"]) if "client_json" in row.keys() and row["client_json"] is not None else None),
        parent_job_id=(str(row["parent_job_id"]) if row["parent_job_id"] is not None else None),
        conversation_url=(str(row["conversation_url"]) if row["conversation_url"] is not None else None),
        conversation_id=(str(row["conversation_id"]) if "conversation_id" in row.keys() and row["conversation_id"] is not None else None),
        conversation_export_format=(str(row["conversation_export_format"]) if row["conversation_export_format"] is not None else None),
        conversation_export_path=(str(row["conversation_export_path"]) if row["conversation_export_path"] is not None else None),
        conversation_export_sha256=(str(row["conversation_export_sha256"]) if row["conversation_export_sha256"] is not None else None),
        conversation_export_chars=(int(row["conversation_export_chars"]) if row["conversation_export_chars"] is not None else None),
        answer_format=(str(row["answer_format"]) if row["answer_format"] is not None else None),
        answer_path=(str(row["answer_path"]) if row["answer_path"] is not None else None),
        answer_sha256=(str(row["answer_sha256"]) if row["answer_sha256"] is not None else None),
        answer_chars=(int(row["answer_chars"]) if row["answer_chars"] is not None else None),
        last_error_type=(str(row["last_error_type"]) if row["last_error_type"] is not None else None),
        last_error=(str(row["last_error"]) if row["last_error"] is not None else None),
    )


def get_job(conn: sqlite3.Connection, *, job_id: str) -> JobRecord | None:
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    return _row_to_job(row)


def create_job(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    idempotency_key: str,
    kind: str,
    input: dict[str, Any],
    params: dict[str, Any],
    max_attempts: int,
    parent_job_id: str | None = None,
    client: dict[str, Any] | None = None,
    requested_by: dict[str, Any] | None = None,
    allow_queue: bool = False,
    enforce_conversation_single_flight: bool = True,
) -> JobRecord:
    job_id = uuid.uuid4().hex

    req_hash = hash_request({"kind": kind, "input": input, "params": params})
    try:
        outcome = begin(conn, idempotency_key=idempotency_key, request_hash=req_hash, job_id=job_id)
    except IdempotencyCollision:
        raise

    if not outcome.created:
        existing = get_job(conn, job_id=outcome.job_id)
        if existing is None:
            raise RuntimeError("idempotency record points to missing job")
        return existing

    # Resolve/normalize follow-up conversation details early so we can:
    # - apply "single conversation single-flight" guardrails (avoid duplicate user messages),
    # - persist conversation_url on the job row for observability and worker scheduling.
    input = dict(input or {})
    conversation_url = str(input.get("conversation_url") or "").strip()
    conversation_id = _conversation_id(conversation_url) if conversation_url else None
    if parent_job_id and not conversation_url:
        parent_row = conn.execute(
            "SELECT kind, status, conversation_url FROM jobs WHERE job_id = ?",
            (str(parent_job_id),),
        ).fetchone()
        if parent_row is None:
            # Fail early: without a valid parent job, the worker cannot safely continue a thread.
            conn.execute("DELETE FROM idempotency WHERE idempotency_key = ?", (idempotency_key,))
            raise ValueError(f"parent_job_id not found: {parent_job_id}")
        parent_kind = str(parent_row["kind"] or "").strip()
        parent_status = str(parent_row["status"] or "").strip().lower()
        parent_conversation_url = str(parent_row["conversation_url"] or "").strip()
        if (
            is_web_ask_kind(kind)
            and is_web_ask_kind(parent_kind)
            and parent_kind != kind
        ):
            conn.execute("DELETE FROM idempotency WHERE idempotency_key = ?", (idempotency_key,))
            raise ValueError(
                f"parent_job_id kind mismatch: parent={parent_kind} child={kind}. "
                "Follow-ups must stay within the same provider."
            )
        if (
            is_web_ask_kind(kind)
            and parent_kind == kind
            and enforce_conversation_single_flight
            and (not allow_queue)
            and parent_status in {JobStatus.QUEUED.value, JobStatus.IN_PROGRESS.value}
        ):
            conn.execute("DELETE FROM idempotency WHERE idempotency_key = ?", (idempotency_key,))
            raise ConversationBusy(
                conversation_url=parent_conversation_url or None,
                active_job_id=str(parent_job_id),
                active_status=parent_status,
                active_phase=None,
                active_updated_at=None,
                reason="parent job still running; do not enqueue follow-up yet",
            )
        if parent_conversation_url:
            conversation_url = parent_conversation_url
            conversation_id = _conversation_id(conversation_url) if conversation_url else None
            input["conversation_url"] = conversation_url

    try:
        _validate_conversation_url_for_kind(kind=kind, conversation_url=conversation_url)
    except ValueError:
        conn.execute("DELETE FROM idempotency WHERE idempotency_key = ?", (idempotency_key,))
        raise

    if is_web_ask_kind(kind) and enforce_conversation_single_flight and (not allow_queue):
        # If this is a follow-up into an existing conversation, prevent accidental rapid-fire
        # user messages by enforcing single-flight at the conversation level.
        key = conversation_id or None
        if key:
            active = conn.execute(
                """
                SELECT job_id, status, phase, updated_at
                FROM jobs
                WHERE kind = ?
                  AND conversation_id = ?
                  AND status IN (?,?)
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (
                    kind,
                    key,
                    JobStatus.QUEUED.value,
                    JobStatus.IN_PROGRESS.value,
                ),
            ).fetchone()
        else:
            active = None

        if active is not None:
            conn.execute("DELETE FROM idempotency WHERE idempotency_key = ?", (idempotency_key,))
            raise ConversationBusy(
                conversation_url=conversation_url or None,
                active_job_id=str(active["job_id"]),
                active_status=str(active["status"] or ""),
                active_phase=(str(active["phase"]) if active["phase"] is not None else None),
                active_updated_at=(float(active["updated_at"]) if active["updated_at"] is not None else None),
                reason="conversation already has an active ask job; wait/cancel or set params.allow_queue=true",
            )

    now = _now()
    conn.execute(
        """
        INSERT INTO jobs(
          job_id, kind, input_json, params_json, client_json, phase, status,
          created_at, updated_at, not_before, max_attempts, parent_job_id,
          conversation_url, conversation_id
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            job_id,
            kind,
            json.dumps(input, ensure_ascii=False),
            json.dumps(params, ensure_ascii=False),
            (json.dumps(client, ensure_ascii=False) if isinstance(client, dict) else None),
            DEFAULT_PHASE,
            JobStatus.QUEUED.value,
            now,
            now,
            0.0,
            int(max_attempts),
            parent_job_id,
            (conversation_url or None),
            (conversation_id or None),
        ),
    )

    pause = get_pause_state(conn)
    if not pause_filter_allows_job(pause=pause, phase=DEFAULT_PHASE, kind=kind, now=now):
        conn.execute(
            "UPDATE jobs SET not_before = MAX(not_before, ?) WHERE job_id = ?",
            (float(pause.until_ts), str(job_id)),
        )
        insert_event(
            conn,
            job_id=job_id,
            type="job_deferred_by_pause",
            payload={
                "mode": str(pause.mode),
                "until_ts": float(pause.until_ts),
                "reason": (pause.reason or None),
            },
        )

    payload: dict[str, Any] = {"kind": kind, "input": input, "params": params}
    if isinstance(client, dict) and client:
        payload["client"] = client
    if isinstance(requested_by, dict) and requested_by:
        payload["requested_by"] = requested_by
    insert_event(conn, job_id=job_id, type="job_created", payload=payload)
    try:
        artifacts.write_request(artifacts_dir, job_id, payload)
    except Exception as exc:
        insert_event(
            conn,
            job_id=job_id,
            type="artifact_write_failed",
            payload={"op": "write_request", "error_type": type(exc).__name__, "error": str(exc)},
        )
    try:
        artifacts.append_event(artifacts_dir, job_id, type="job_created", payload=payload)
    except Exception:
        pass
    return get_job(conn, job_id=job_id)  # type: ignore[return-value]


def transition(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    job_id: str,
    dst: JobStatus,
    updates: dict[str, Any] | None = None,
    expected_lease_owner: str | None = None,
    expected_lease_token: str | None = None,
    require_lease_not_expired: bool = False,
) -> JobRecord:
    job = get_job(conn, job_id=job_id)
    if job is None:
        raise KeyError(job_id)
    src = job.status
    verdict = can_transition(src, dst)
    if not verdict.ok:
        raise RuntimeError(verdict.error or "invalid transition")
    sets: list[str] = ["status = ?", "updated_at = ?"]
    params: list[Any] = [dst.value, _now()]
    updates = dict(updates or {})
    for k, v in updates.items():
        if k not in _TRANSITION_UPDATE_WHITELIST:
            raise ValueError(f"transition() update key not allowed: {k!r}")
        sets.append(f"{k} = ?")
        params.append(v)
    where: list[str] = ["job_id = ?", "status = ?"]
    where_params: list[Any] = [job_id, src.value]
    if expected_lease_owner is not None and expected_lease_token is not None:
        where.append("lease_owner = ?")
        where.append("lease_token = ?")
        where_params.extend([expected_lease_owner, expected_lease_token])
    if require_lease_not_expired:
        where.append("(lease_expires_at IS NULL OR lease_expires_at >= ?)")
        where_params.append(_now())

    changed = conn.execute(
        f"UPDATE jobs SET {', '.join(sets)} WHERE {' AND '.join(where)}",
        tuple(params + where_params),
    ).rowcount
    if not changed:
        if expected_lease_owner is not None or expected_lease_token is not None or require_lease_not_expired:
            raise LeaseLost("lease lost (job was reclaimed or lease expired)")
        raise RuntimeError("failed to transition job (concurrent update?)")
    insert_event(conn, job_id=job_id, type="status_changed", payload={"from": src.value, "to": dst.value})
    artifacts.append_event(artifacts_dir, job_id, type="status_changed", payload={"from": src.value, "to": dst.value})
    if updates and "phase" in updates:
        new_phase = _normalize_phase(updates.get("phase"))
        old_phase = _normalize_phase(job.phase)
        if new_phase != old_phase:
            insert_event(conn, job_id=job_id, type="phase_changed", payload={"from": old_phase, "to": new_phase})
            artifacts.append_event(artifacts_dir, job_id, type="phase_changed", payload={"from": old_phase, "to": new_phase})
    return get_job(conn, job_id=job_id)  # type: ignore[return-value]


def request_cancel(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    job_id: str,
    requested_by: dict[str, Any] | None = None,
    reason: str | None = None,
) -> JobRecord:
    job = get_job(conn, job_id=job_id)
    if job is None:
        raise KeyError(job_id)
    now = _now()
    payload: dict[str, Any] = {"ts": now}
    if requested_by is not None:
        payload["by"] = requested_by
    reason_text = str(reason or "").strip()
    if reason_text:
        payload["reason"] = reason_text

    def _write_canceled_result_payload(canceled_job: JobRecord) -> None:
        artifacts.write_result(
            artifacts_dir,
            job_id,
            {
                "ok": False,
                "job_id": job_id,
                "status": canceled_job.status.value,
                "phase": canceled_job.phase,
                "conversation_url": canceled_job.conversation_url,
                "conversation_id": canceled_job.conversation_id,
                "canceled": True,
                "reason": (reason_text or None),
            },
        )

    def _try_cancel_wait_phase_immediately(current_job: JobRecord) -> JobRecord | None:
        if current_job.status != JobStatus.IN_PROGRESS or _normalize_phase(current_job.phase) != "wait":
            return None
        reason_message = (f"cancel requested: {reason_text}" if reason_text else "cancel requested")
        lease_owner = str(current_job.lease_owner or "").strip()
        lease_token = str(current_job.lease_token or "").strip()
        lease_active = bool(
            lease_owner
            and lease_token
            and (
                current_job.lease_expires_at is None
                or float(current_job.lease_expires_at) >= now
            )
        )
        if lease_active:
            return store_canceled_result(
                conn,
                artifacts_dir=artifacts_dir,
                job_id=job_id,
                worker_id=lease_owner,
                lease_token=lease_token,
                reason=reason_message,
            )
        canceled_job = transition(
            conn,
            artifacts_dir=artifacts_dir,
            job_id=job_id,
            dst=JobStatus.CANCELED,
            updates={
                "cancel_requested_at": now,
                "last_error_type": "Canceled",
                "last_error": reason_message,
                "lease_owner": None,
                "lease_expires_at": None,
                "lease_token": None,
            },
        )
        _write_canceled_result_payload(canceled_job)
        return canceled_job

    if job.status == JobStatus.QUEUED:
        canceled = transition(
            conn,
            artifacts_dir=artifacts_dir,
            job_id=job_id,
            dst=JobStatus.CANCELED,
            updates={
                "cancel_requested_at": now,
                "last_error_type": "Canceled",
                "last_error": (f"cancel requested: {reason_text}" if reason_text else "cancel requested"),
            },
        )
        insert_event(conn, job_id=job_id, type="cancel_requested", payload=payload)
        artifacts.append_event(artifacts_dir, job_id, type="cancel_requested", payload=payload)
        _write_canceled_result_payload(canceled)
        return canceled
    if is_terminal(job.status):
        return job
    immediate_wait_cancel = _try_cancel_wait_phase_immediately(job)
    if immediate_wait_cancel is not None:
        insert_event(conn, job_id=job_id, type="cancel_requested", payload=payload)
        artifacts.append_event(artifacts_dir, job_id, type="cancel_requested", payload=payload)
        return immediate_wait_cancel
    conn.execute(
        "UPDATE jobs SET cancel_requested_at = ?, updated_at = ? WHERE job_id = ?",
        (now, now, job_id),
    )
    insert_event(conn, job_id=job_id, type="cancel_requested", payload=payload)
    artifacts.append_event(artifacts_dir, job_id, type="cancel_requested", payload=payload)
    return get_job(conn, job_id=job_id)  # type: ignore[return-value]


def _build_claim_where(
    *,
    now: float,
    kind_prefix: str | None,
    kind_like: str | None,
    phase_filter: str | None,
    pause_active: int,
    pause_all: int,
) -> tuple[str, list[Any]]:
    """Build the WHERE clause shared by claim_next_job SELECT and UPDATE.

    Returns ``(sql_fragment, params)`` — single source of truth to prevent
    the two copies from diverging.
    """
    sql = f"""
        not_before <= ?
        AND (? IS NULL OR kind LIKE ?)
        AND (? IS NULL OR COALESCE(phase, ?) = ?)
        AND (
          ? = 0
          OR (? = 1 AND kind LIKE 'repair.%')
          OR (? = 0 AND (COALESCE(phase, ?) = 'wait' OR kind LIKE 'repair.%'))
        )
        AND (
          COALESCE(phase, ?) = 'wait'
          OR status = ?
          OR attempts < max_attempts
        )
        AND (
          COALESCE(phase, ?) = 'wait'
          OR kind NOT IN ({_WEB_ASK_KIND_SQL})
          OR conversation_id IS NULL
          OR NOT EXISTS (
            SELECT 1
            FROM jobs j2
            WHERE j2.kind = jobs.kind
              AND j2.status = ?
              AND j2.conversation_id = jobs.conversation_id
              AND j2.job_id != jobs.job_id
          )
        )
        AND (
          status IN (?,?)
          OR (status = ? AND (lease_expires_at IS NULL OR lease_expires_at < ?))
        )
    """
    params: list[Any] = [
        now,
        kind_prefix,
        kind_like,
        phase_filter,
        DEFAULT_PHASE,
        phase_filter,
        pause_active,
        pause_all,
        pause_all,
        DEFAULT_PHASE,
        DEFAULT_PHASE,
        JobStatus.IN_PROGRESS.value,
        DEFAULT_PHASE,
        JobStatus.IN_PROGRESS.value,
        JobStatus.QUEUED.value,
        JobStatus.COOLDOWN.value,
        JobStatus.IN_PROGRESS.value,
        now,
    ]
    return sql, params


def _build_claim_order_by(*, phase_filter: str | None) -> str:
    """Bias wait workers toward jobs that can make forward progress now.

    Gemini deep-research wait jobs with a stable thread URL are the most
    latency-sensitive path we currently see in production. Keep this narrow:
    only wait workers get the priority ordering; send/all workers retain the
    historical FIFO order.
    """

    if phase_filter != "wait":
        return "not_before ASC, created_at ASC"
    return """
        CASE
          WHEN kind = 'gemini_web.ask'
           AND conversation_id IS NOT NULL
           AND COALESCE(CAST(json_extract(params_json, '$.deep_research') AS INTEGER), 0) = 1
            THEN 0
          WHEN conversation_id IS NOT NULL
            THEN 1
          ELSE 2
        END ASC,
        not_before ASC,
        created_at ASC
    """


def claim_next_job(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    worker_id: str,
    lease_ttl_seconds: int,
    phase: str | None = None,
    kind_prefix: str | None = None,
) -> JobRecord | None:
    now = _now()
    lease_expires_at = now + float(lease_ttl_seconds)
    lease_token = uuid.uuid4().hex
    phase_filter = _normalize_phase(phase) if phase else None
    kind_prefix = str(kind_prefix or "").strip() or None
    kind_like = f"{kind_prefix}%" if kind_prefix else None
    pause = get_pause_state(conn)
    pause_active = int(pause.is_active(now=now))
    pause_all = int(pause_active and pause.mode == "all")
    # NOTE: The `attempts` counter is meant to cap "send side-effects" retries.
    # Wait-phase polls should not consume attempts, otherwise two-phase scheduling
    # can deadlock jobs in `in_progress` once attempts reaches max_attempts.
    where_sql, where_params = _build_claim_where(
        now=now,
        kind_prefix=kind_prefix,
        kind_like=kind_like,
        phase_filter=phase_filter,
        pause_active=pause_active,
        pause_all=pause_all,
    )
    order_by_sql = _build_claim_order_by(phase_filter=phase_filter)
    row = conn.execute(
        f"""
        SELECT job_id, status
        FROM jobs
        WHERE {where_sql}
        ORDER BY {order_by_sql}
        LIMIT 1
        """,
        tuple(where_params),
    ).fetchone()
    if row is None:
        return None
    job_id = str(row["job_id"])
    reclaimed = str(row["status"] or "") == JobStatus.IN_PROGRESS.value
    # Attempt atomic claim — reuse the same WHERE to guarantee consistency.
    changed = conn.execute(
        f"""
        UPDATE jobs
        SET status = ?,
            updated_at = ?,
            lease_owner = ?,
            lease_expires_at = ?,
            lease_token = ?,
            attempts = attempts + CASE WHEN COALESCE(phase, ?) = 'wait' OR status = ? THEN 0 ELSE 1 END
        WHERE job_id = ?
          AND {where_sql}
        """,
        (
            JobStatus.IN_PROGRESS.value,
            now,
            worker_id,
            lease_expires_at,
            lease_token,
            DEFAULT_PHASE,
            JobStatus.IN_PROGRESS.value,
            job_id,
            *where_params,
        ),
    ).rowcount
    if not changed:
        return None
    payload = {
        "worker_id": worker_id,
        "lease_expires_at": lease_expires_at,
        "lease_token": lease_token,
        "reclaimed": reclaimed,
    }
    insert_event(conn, job_id=job_id, type="claimed", payload=payload)
    artifacts.append_event(artifacts_dir, job_id, type="claimed", payload=payload)
    return get_job(conn, job_id=job_id)


def renew_lease(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    job_id: str,
    worker_id: str,
    lease_token: str,
    lease_ttl_seconds: int,
) -> bool:
    now = _now()
    lease_expires_at = now + float(lease_ttl_seconds)
    changed = conn.execute(
        """
        UPDATE jobs
        SET lease_expires_at = ?, updated_at = ?
        WHERE job_id = ?
          AND status = ?
          AND lease_owner = ?
          AND lease_token = ?
          AND (lease_expires_at IS NULL OR lease_expires_at >= ?)
        """,
        (
            lease_expires_at,
            now,
            job_id,
            JobStatus.IN_PROGRESS.value,
            worker_id,
            lease_token,
            now,
        ),
    ).rowcount
    if not changed:
        return False
    payload = {"worker_id": worker_id, "lease_expires_at": lease_expires_at, "lease_token": lease_token}
    insert_event(conn, job_id=job_id, type="lease_renewed", payload=payload)
    artifacts.append_event(artifacts_dir, job_id, type="lease_renewed", payload=payload)
    return True


def set_conversation_url(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    job_id: str,
    worker_id: str,
    lease_token: str,
    conversation_url: str,
) -> JobRecord:
    job = get_job(conn, job_id=job_id)
    if job is None:
        raise KeyError(job_id)
    url = str(conversation_url or "").strip()
    if not url:
        raise ValueError("conversation_url is empty")
    new_id = _conversation_id(url)
    existing_url = str(job.conversation_url or "").strip()
    if existing_url:
        existing_id = _conversation_id(existing_url)
        if existing_url == url:
            return job
        if existing_id and new_id and existing_id == new_id:
            return job
        can_rebind_gemini_thread = (
            str(job.kind or "").strip().lower() == "gemini_web.ask"
            and _gemini_is_thread_url(existing_url)
            and _gemini_is_thread_url(url)
        )
        # Upgrade: base app URL → specific conversation thread URL (either Gemini or ChatGPT).
        can_upgrade = (
            (_gemini_is_base_app_url(existing_url) and bool(_GEMINI_CONVERSATION_ID_RE.search(url)))
            or (_chatgpt_is_base_app_url(existing_url) and bool(_CHATGPT_CONVERSATION_ID_RE.search(url)))
        )
        if can_rebind_gemini_thread:
            now = _now()
            changed = conn.execute(
                """
                UPDATE jobs
                SET conversation_url = ?,
                    conversation_id = ?,
                    updated_at = ?
                WHERE job_id = ?
                  AND status = ?
                  AND lease_owner = ?
                  AND lease_token = ?
                  AND (lease_expires_at IS NULL OR lease_expires_at >= ?)
                """,
                (
                    url,
                    new_id,
                    now,
                    job_id,
                    JobStatus.IN_PROGRESS.value,
                    worker_id,
                    lease_token,
                    now,
                ),
            ).rowcount
            if not changed:
                raise LeaseLost("lease lost (cannot rebind gemini conversation_url)")
            payload = {
                "existing_conversation_url": existing_url,
                "new_conversation_url": url,
                "worker_id": worker_id,
                "lease_token": lease_token,
            }
            insert_event(conn, job_id=job_id, type="conversation_url_rebound", payload=payload)
            artifacts.append_event(artifacts_dir, job_id, type="conversation_url_rebound", payload=payload)
            return get_job(conn, job_id=job_id)  # type: ignore[return-value]
        if can_upgrade:
            now = _now()
            changed = conn.execute(
                """
                UPDATE jobs
                SET conversation_url = ?,
                    conversation_id = ?,
                    updated_at = ?
                WHERE job_id = ?
                  AND status = ?
                  AND lease_owner = ?
                  AND lease_token = ?
                  AND (lease_expires_at IS NULL OR lease_expires_at >= ?)
                """,
                (
                    url,
                    new_id,
                    now,
                    job_id,
                    JobStatus.IN_PROGRESS.value,
                    worker_id,
                    lease_token,
                    now,
                ),
            ).rowcount
            if not changed:
                raise LeaseLost("lease lost (cannot upgrade conversation_url)")
            payload = {
                "existing_conversation_url": existing_url,
                "new_conversation_url": url,
                "worker_id": worker_id,
                "lease_token": lease_token,
            }
            insert_event(conn, job_id=job_id, type="conversation_url_upgraded", payload=payload)
            artifacts.append_event(artifacts_dir, job_id, type="conversation_url_upgraded", payload=payload)
            return get_job(conn, job_id=job_id)  # type: ignore[return-value]
        payload = {
            "existing_conversation_url": existing_url,
            "new_conversation_url": url,
            "worker_id": worker_id,
            "lease_token": lease_token,
        }
        insert_event(conn, job_id=job_id, type="conversation_url_conflict", payload=payload)
        artifacts.append_event(artifacts_dir, job_id, type="conversation_url_conflict", payload=payload)
        return job
    now = _now()
    changed = conn.execute(
        """
        UPDATE jobs
        SET conversation_url = ?,
            conversation_id = ?,
            updated_at = ?
        WHERE job_id = ?
          AND status = ?
          AND lease_owner = ?
          AND lease_token = ?
          AND (lease_expires_at IS NULL OR lease_expires_at >= ?)
        """,
        (
            url,
            new_id,
            now,
            job_id,
            JobStatus.IN_PROGRESS.value,
            worker_id,
            lease_token,
            now,
        ),
    ).rowcount
    if not changed:
        raise LeaseLost("lease lost (cannot set conversation_url)")
    payload = {"conversation_url": url, "conversation_id": new_id, "worker_id": worker_id, "lease_token": lease_token}
    insert_event(conn, job_id=job_id, type="conversation_url_set", payload=payload)
    artifacts.append_event(artifacts_dir, job_id, type="conversation_url_set", payload=payload)
    return get_job(conn, job_id=job_id)  # type: ignore[return-value]


def store_conversation_export_result(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    job_id: str,
    conversation_export_path: str,
    conversation_export_sha256: str | None,
    conversation_export_chars: int | None,
    conversation_export_format: str = "json",
) -> JobRecord:
    job = get_job(conn, job_id=job_id)
    if job is None:
        raise KeyError(job_id)

    path = str(conversation_export_path or "").strip()
    if not path:
        raise ValueError("conversation_export_path is empty")

    sha = str(conversation_export_sha256 or "").strip() or None
    chars = int(conversation_export_chars or 0)
    fmt = str(conversation_export_format or "json").strip().lower() or "json"

    if sha and job.conversation_export_sha256 == sha and job.conversation_export_path == path:
        return job

    now = _now()
    conn.execute(
        """
        UPDATE jobs
        SET conversation_export_format = ?,
            conversation_export_path = ?,
            conversation_export_sha256 = ?,
            conversation_export_chars = ?,
            updated_at = ?
        WHERE job_id = ?
        """,
        (fmt, path, sha, chars, now, job_id),
    )
    payload = {
        "conversation_export_format": fmt,
        "conversation_export_path": path,
        "conversation_export_sha256": sha,
        "conversation_export_chars": chars,
    }
    insert_event(conn, job_id=job_id, type="conversation_exported", payload=payload)
    artifacts.append_event(artifacts_dir, job_id, type="conversation_exported", payload=payload)
    return get_job(conn, job_id=job_id)  # type: ignore[return-value]


def store_answer_result(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    job_id: str,
    worker_id: str,
    lease_token: str,
    answer: str,
    answer_format: str,
) -> JobRecord:
    job = get_job(conn, job_id=job_id)
    if job is None:
        raise KeyError(job_id)

    meta, _ = artifacts.compute_answer_meta(job_id=job_id, answer=answer, answer_format=answer_format)
    if job.status == JobStatus.COMPLETED:
        if job.answer_sha256 and job.answer_sha256 == meta.answer_sha256:
            return job
        raise AlreadyFinished("job already completed with different result")
    if is_terminal(job.status):
        raise AlreadyFinished(f"job already finished: {job.status.value}")
    if job.status != JobStatus.IN_PROGRESS:
        raise RuntimeError(f"job not in progress: {job.status.value}")

    meta, stage_path = artifacts.write_answer_staged(
        artifacts_dir,
        job_id,
        lease_token=lease_token,
        answer=answer,
        answer_format=answer_format,
    )

    result_payload = {
        "ok": True,
        "job_id": job_id,
        "status": JobStatus.COMPLETED.value,
        "phase": job.phase,
        "conversation_url": job.conversation_url,
        "conversation_id": job.conversation_id,
        "path": meta.answer_path,
        "answer_sha256": meta.answer_sha256,
        "answer_chars": meta.answer_chars,
        "answer_format": meta.answer_format,
    }
    result_stage_path = artifacts.write_result_staged(
        artifacts_dir,
        job_id,
        lease_token=lease_token,
        payload=result_payload,
    )
    canonical_path = artifacts.resolve_artifact_path(artifacts_dir, meta.answer_path)
    result_path = artifacts.job_dir(artifacts_dir, job_id) / "result.json"

    updates = {
        "answer_path": meta.answer_path,
        "answer_sha256": meta.answer_sha256,
        "answer_chars": meta.answer_chars,
        "answer_format": meta.answer_format,
        "last_error_type": None,
        "last_error": None,
    }
    try:
        finalized = transition(
            conn,
            artifacts_dir=artifacts_dir,
            job_id=job_id,
            dst=JobStatus.COMPLETED,
            updates=updates,
            expected_lease_owner=worker_id,
            expected_lease_token=lease_token,
            require_lease_not_expired=True,
        )
    except Exception:
        for path in (stage_path, result_stage_path):
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass

        raise

    published_paths: list[Any] = []
    try:
        stage_path.replace(canonical_path)
        published_paths.append(canonical_path)
        result_stage_path.replace(result_path)
        published_paths.append(result_path)
    except Exception:
        for path in (stage_path, result_stage_path):
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass
        for path in published_paths:
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass
        raise
    return finalized


def store_error_result(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    job_id: str,
    worker_id: str,
    lease_token: str,
    error_type: str,
    error: str,
    status: JobStatus = JobStatus.ERROR,
) -> JobRecord:
    job = get_job(conn, job_id=job_id)
    if job is None:
        raise KeyError(job_id)
    normalized_error_type, normalized_error = _normalize_error_fields(error_type, error)
    if job.status == status and job.last_error_type == normalized_error_type and job.last_error == normalized_error:
        return job
    if is_terminal(job.status):
        raise AlreadyFinished(f"job already finished: {job.status.value}")
    if job.status != JobStatus.IN_PROGRESS:
        raise RuntimeError(f"job not in progress: {job.status.value}")

    if status != JobStatus.ERROR and status not in {JobStatus.BLOCKED, JobStatus.COOLDOWN, JobStatus.NEEDS_FOLLOWUP}:
        raise ValueError(f"invalid error result status: {status.value}")

    updates = {
        "last_error_type": normalized_error_type,
        "last_error": normalized_error,
    }
    new_job = transition(
        conn,
        artifacts_dir=artifacts_dir,
        job_id=job_id,
        dst=status,
        updates=updates,
        expected_lease_owner=worker_id,
        expected_lease_token=lease_token,
        require_lease_not_expired=True,
    )
    artifacts.write_result(
        artifacts_dir,
        job_id,
        {
            "ok": False,
            "job_id": job_id,
            "status": new_job.status.value,
            "phase": new_job.phase,
            "conversation_url": new_job.conversation_url,
            "conversation_id": new_job.conversation_id,
            "error_type": normalized_error_type,
            "error": normalized_error,
        },
    )

    # ── Auto-report terminal errors to Issue Ledger ──────────────────────
    if status == JobStatus.ERROR:
        try:
            from chatgptrest.core import client_issues as _ci

            status_n = status.value
            if not _truthy_env("CHATGPTREST_ISSUE_AUTOREPORT_ENABLED", True):
                return new_job
            if status_n not in issue_autoreport_statuses(os.environ.get("CHATGPTREST_ISSUE_AUTOREPORT_STATUSES")):
                return new_job
            kind_n = ws_single(job.kind, max_chars=200) or "job_error"
            error_type_n = ws_single(normalized_error_type, max_chars=120) or "RuntimeError"
            error_n = str(normalized_error or "")
            default_project = ws_single(os.environ.get("CHATGPTREST_ISSUE_DEFAULT_PROJECT") or "chatgptrest", max_chars=200) or "chatgptrest"
            issue, created, info = _ci.report_issue(
                conn,
                project=issue_project_from_client_json(job.client_json, default_project=default_project),
                title=f"{kind_n} {status_n}: {error_type_n}",
                kind=kind_n,
                severity=issue_severity_for_status(status=status_n, error_type=error_type_n, error=error_n),
                symptom=f"{error_type_n}: {ws_single(error_n, max_chars=1000)}",
                raw_error=error_n,
                job_id=job_id,
                conversation_url=job.conversation_url,
                artifacts_path=f"jobs/{job_id}",
                source=AUTO_ISSUE_SOURCE,
                tags=["auto_report", "worker", status_n],
                metadata={
                    "status": status_n,
                    "error_type": error_type_n,
                    "attempts": int(getattr(job, "attempts", 0) or 0),
                    "max_attempts": int(getattr(job, "max_attempts", 0) or 0),
                    "phase": ws_single(getattr(job, "phase", ""), max_chars=20) or None,
                    "kind": kind_n,
                },
                fingerprint=auto_issue_fingerprint(
                    kind=kind_n,
                    status=status_n,
                    error_type=error_type_n,
                    error=error_n,
                ),
            )
            insert_event(
                conn,
                job_id=job_id,
                type="issue_auto_reported",
                payload={
                    "issue_id": issue.issue_id,
                    "created": bool(created),
                    "reopened": bool(info.get("reopened")),
                    "status": status_n,
                    "error_type": error_type_n,
                    "kind": kind_n,
                    "fingerprint_hash": issue.fingerprint_hash,
                },
            )
        except Exception:
            import logging
            logging.getLogger("chatgptrest.core.job_store").debug(
                "auto issue report failed for job %s", job_id, exc_info=True,
            )

    return new_job


def store_retryable_result(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    job_id: str,
    worker_id: str,
    lease_token: str,
    status: JobStatus,
    not_before: float,
    error_type: str,
    error: str,
    phase: str | None = None,
) -> JobRecord:
    if status not in {JobStatus.BLOCKED, JobStatus.COOLDOWN, JobStatus.NEEDS_FOLLOWUP}:
        raise ValueError(f"invalid retryable status: {status.value}")
    job = get_job(conn, job_id=job_id)
    if job is None:
        raise KeyError(job_id)
    effective_phase = _normalize_phase(phase) if phase is not None else _normalize_phase(job.phase)
    normalized_error_type, normalized_error = _normalize_error_fields(error_type, error)
    extended_max_attempts: int | None = None
    extension_guard_reason: str | None = None
    if effective_phase != "wait" and job.max_attempts > 0 and job.attempts >= job.max_attempts:
        # For ask jobs, retryable states like BLOCKED/COOLDOWN can legitimately occur before any
        # prompt send side-effects (e.g. CDP down, Drive upload not ready). Allow limited automatic
        # extension so the same job can recover to completed without requiring a new submission.
        if (
            is_web_ask_kind(job.kind)
            and _truthy_env("CHATGPTREST_RETRYABLE_SEND_EXTEND_MAX_ATTEMPTS", True)
        ):
            if _looks_like_sticky_upload_surface_closed(normalized_error_type, normalized_error):
                extension_guard_reason = "sticky_upload_surface_closed"
            else:
                cap = _retryable_send_attempts_cap()
                used = _retryable_send_extensions_used(
                    conn,
                    job_id=job_id,
                    error_type=normalized_error_type,
                )
                used_cap = _retryable_send_max_extensions()
                if used_cap >= 0 and used >= used_cap:
                    extension_guard_reason = f"retryable_extension_limit_reached:{used}/{used_cap}"
                elif job.max_attempts >= cap:
                    extension_guard_reason = f"retryable_attempts_cap_reached:{job.max_attempts}/{cap}"
                else:
                    extended_max_attempts = min(cap, max(int(job.max_attempts) + 1, int(job.attempts) + 1))
        if extended_max_attempts is None:
            if extension_guard_reason:
                payload = {
                    "status": status.value,
                    "phase": effective_phase,
                    "attempts": int(job.attempts),
                    "max_attempts": int(job.max_attempts),
                    "error_type": normalized_error_type,
                    "guard_reason": extension_guard_reason,
                }
                insert_event(conn, job_id=job_id, type="max_attempts_extension_skipped", payload=payload)
                artifacts.append_event(artifacts_dir, job_id, type="max_attempts_extension_skipped", payload=payload)
            msg = (
                f"Reached max_attempts={job.max_attempts} while retrying ({status.value}): "
                f"{normalized_error_type}: {normalized_error}"
            )
            if extension_guard_reason:
                msg = f"{msg} [guard={extension_guard_reason}]"
            terminal_status = JobStatus.ERROR
            terminal_error_type = "MaxAttemptsExceeded"
            if str(job.kind or "").strip().lower() == "qwen_web.ask" and _looks_like_qwen_cdp_unavailable(
                normalized_error_type,
                normalized_error,
            ):
                terminal_status = JobStatus.NEEDS_FOLLOWUP
                terminal_error_type = "QwenCdpUnavailable"
            return store_error_result(
                conn,
                artifacts_dir=artifacts_dir,
                job_id=job_id,
                worker_id=worker_id,
                lease_token=lease_token,
                error_type=terminal_error_type,
                error=msg,
                status=terminal_status,
            )
    if (
        job.status == status
        and job.not_before == not_before
        and job.last_error_type == normalized_error_type
        and job.last_error == normalized_error
    ):
        return job
    if is_terminal(job.status):
        raise AlreadyFinished(f"job already finished: {job.status.value}")
    if job.status != JobStatus.IN_PROGRESS:
        raise RuntimeError(f"job not in progress: {job.status.value}")

    updates = {
        "not_before": float(not_before),
        "last_error_type": normalized_error_type,
        "last_error": normalized_error,
    }
    if extended_max_attempts is not None and int(extended_max_attempts) > int(job.max_attempts):
        updates["max_attempts"] = int(extended_max_attempts)
    if phase is not None:
        updates["phase"] = _normalize_phase(phase)
    new_job = transition(
        conn,
        artifacts_dir=artifacts_dir,
        job_id=job_id,
        dst=status,
        updates=updates,
        expected_lease_owner=worker_id,
        expected_lease_token=lease_token,
        require_lease_not_expired=True,
    )
    if extended_max_attempts is not None and int(extended_max_attempts) > int(job.max_attempts):
        payload = {
            "previous_max_attempts": int(job.max_attempts),
            "new_max_attempts": int(extended_max_attempts),
            "attempts": int(job.attempts),
            "status": status.value,
            "phase": effective_phase,
            "error_type": normalized_error_type,
        }
        insert_event(conn, job_id=job_id, type="max_attempts_extended", payload=payload)
        artifacts.append_event(artifacts_dir, job_id, type="max_attempts_extended", payload=payload)
    artifacts.write_result(
        artifacts_dir,
        job_id,
        {
            "ok": False,
            "job_id": job_id,
            "status": new_job.status.value,
            "phase": new_job.phase,
            "conversation_url": new_job.conversation_url,
            "conversation_id": new_job.conversation_id,
            "not_before": float(not_before),
            "retryable": True,
            "error_type": normalized_error_type,
            "error": normalized_error,
        },
    )
    return new_job


def release_for_wait(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    job_id: str,
    worker_id: str,
    lease_token: str,
    not_before: float,
) -> JobRecord:
    job = get_job(conn, job_id=job_id)
    if job is None:
        raise KeyError(job_id)
    if is_terminal(job.status):
        raise AlreadyFinished(f"job already finished: {job.status.value}")
    if job.status != JobStatus.IN_PROGRESS:
        raise RuntimeError(f"job not in progress: {job.status.value}")

    now = _now()
    updates = {
        "phase": _normalize_phase("wait"),
        "not_before": float(not_before),
        "lease_owner": None,
        "lease_expires_at": None,
        "lease_token": None,
        "updated_at": now,
    }

    changed = conn.execute(
        """
        UPDATE jobs
        SET phase = ?, not_before = ?, lease_owner = ?, lease_expires_at = ?, lease_token = ?, updated_at = ?
        WHERE job_id = ?
          AND status = ?
          AND lease_owner = ?
          AND lease_token = ?
          AND (lease_expires_at IS NULL OR lease_expires_at >= ?)
        """,
        (
            updates["phase"],
            updates["not_before"],
            updates["lease_owner"],
            updates["lease_expires_at"],
            updates["lease_token"],
            updates["updated_at"],
            job_id,
            JobStatus.IN_PROGRESS.value,
            worker_id,
            lease_token,
            now,
        ),
    ).rowcount
    if not changed:
        raise LeaseLost("lease lost (cannot release for wait)")

    old_phase = _normalize_phase(job.phase)
    if old_phase != "wait":
        insert_event(conn, job_id=job_id, type="phase_changed", payload={"from": old_phase, "to": "wait"})
        artifacts.append_event(artifacts_dir, job_id, type="phase_changed", payload={"from": old_phase, "to": "wait"})
    insert_event(conn, job_id=job_id, type="wait_requeued", payload={"not_before": float(not_before)})
    artifacts.append_event(artifacts_dir, job_id, type="wait_requeued", payload={"not_before": float(not_before)})
    return get_job(conn, job_id=job_id)  # type: ignore[return-value]


def store_canceled_result(
    conn: sqlite3.Connection,
    *,
    artifacts_dir: Any,
    job_id: str,
    worker_id: str,
    lease_token: str,
    reason: str | None = None,
) -> JobRecord:
    job = get_job(conn, job_id=job_id)
    if job is None:
        raise KeyError(job_id)
    if job.status == JobStatus.CANCELED:
        return job
    if is_terminal(job.status):
        raise AlreadyFinished(f"job already finished: {job.status.value}")
    if job.status != JobStatus.IN_PROGRESS:
        raise RuntimeError(f"job not in progress: {job.status.value}")

    updates = {
        "cancel_requested_at": float(job.cancel_requested_at or _now()),
        "last_error_type": ("Canceled" if reason else None),
        "last_error": (str(reason or "") if reason else None),
    }
    new_job = transition(
        conn,
        artifacts_dir=artifacts_dir,
        job_id=job_id,
        dst=JobStatus.CANCELED,
        updates=updates,
        expected_lease_owner=worker_id,
        expected_lease_token=lease_token,
        require_lease_not_expired=True,
    )
    artifacts.write_result(
        artifacts_dir,
        job_id,
        {
            "ok": False,
            "job_id": job_id,
            "status": new_job.status.value,
            "phase": new_job.phase,
            "conversation_url": new_job.conversation_url,
            "conversation_id": new_job.conversation_id,
            "canceled": True,
            "reason": (str(reason) if reason else None),
        },
    )
    return new_job
