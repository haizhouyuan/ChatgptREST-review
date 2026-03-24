from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import re
import shutil
import socket
import sqlite3
import sys
import time
import traceback
import zipfile
from dataclasses import replace as _dc_replace
from pathlib import Path
from typing import Any

from chatgptrest.core.config import AppConfig, load_config
from chatgptrest.core import client_issues
from chatgptrest.core import env as _env_registry
from chatgptrest.core import mihomo_delay
from chatgptrest.core.attachment_contract import detect_missing_attachment_contract
from chatgptrest.core.repair_jobs import create_repair_autofix_job, source_job_uses_synthetic_or_trivial_prompt
from chatgptrest.core.rate_limit import try_reserve, try_reserve_fixed_window
from chatgptrest.core import artifacts
from chatgptrest.core.db import connect, insert_event
from chatgptrest.core.job_store import (
    AlreadyFinished,
    LeaseLost,
    claim_next_job,
    release_for_wait,
    renew_lease,
    set_conversation_url,
    store_conversation_export_result,
    store_answer_result,
    store_canceled_result,
    store_error_result,
    store_retryable_result,
)
from chatgptrest.core.state_machine import JobStatus
from chatgptrest.core.conversation_exports import (
    classify_answer_quality as _classify_answer_quality,
    conversation_export_is_dom_fallback as _conversation_export_is_dom_fallback,
    conversation_export_messages as _conversation_export_messages,
    extract_answer_from_conversation_export as _extract_answer_from_conversation_export,
    extract_answer_from_conversation_export_obj as _extract_answer_from_conversation_export_obj,
    normalize_dom_export_text as _normalize_dom_export_text,
    normalize_text as _normalize_text,
    render_conversation_export_markdown as _render_conversation_export_markdown,
    unwrap_response_envelope_text as _unwrap_response_envelope_text,
)
from chatgptrest.core.issue_autoreport import (
    AUTO_ISSUE_SOURCE,
    auto_issue_fingerprint as _auto_issue_fingerprint,
    error_signature_fragment as _shared_error_signature_fragment,
    issue_autoreport_statuses as _shared_issue_autoreport_statuses,
    issue_project_from_client_json as _shared_issue_project_from_client_json,
    issue_severity_for_status as _shared_issue_severity_for_status,
    ws_single as _shared_ws_single,
)
from chatgptrest.driver.api import ToolCaller
from chatgptrest.driver.factory import build_tool_caller, normalize_driver_mode
from chatgptrest.executors.base import ExecutorResult
from chatgptrest.executors.chatgpt_web_mcp import ChatGPTWebMcpExecutor
from chatgptrest.executors.factory import executor_for_job as _resolve_executor_for_job
from chatgptrest.executors.repair import RepairAutofixExecutor, RepairExecutor, RepairOpenPrExecutor
from chatgptrest.providers.registry import (
    ask_min_prompt_interval_seconds,
    ask_rate_limit_key,
    is_provider_web_kind,
    is_web_ask_kind,
    is_worker_autofix_kind,
    looks_like_thread_url as provider_looks_like_thread_url,
    provider_id_for_kind,
)


_DEEP_RESEARCH_ACK_RE = re.compile(
    r"("
    r"我将.*?(深入研究|深度研究)|"
    r"我将为你.*?(深入研究|深度研究)|"
    r"我将.*?(开始|开展|进行|马上|立即|立刻).*?(研究|调研|调查)|"
    r"我会.*?(开始|开展|进行|马上|立即|立刻).*?(研究|调研|调查)|"
    r"我正在.*?(准备|撰写|整理|生成).{0,80}(报告|正文|内容|交付|交付物|表格)|"
    r"我(将|会).{0,40}(一次性)?(输出|给出|提供|呈现|汇报).{0,80}(完整|最终|全文|正文|报告)|"
    r"(深研|深入研究|深度研究|深入调研|深度调研)|"
    r"我会在.*?研究完成后|"
    r"我会在研究完成后向你汇报|"
    r"研究完成后.*?我会|"
    r"我(已|已经)将.*?纳入研究|"
    r"(已|已经)将.*?纳入研究|"
    r"报告.*?(准备好|准备完成|完成|写好).{0,60}(后|之后).{0,60}(发给|发送|给你|提供|呈现|汇报|报告|请查收|查收)|"
    r"(稍后|稍等|请稍等|请耐心等待).{0,60}(请查收|查收|给你|发给你|发送给你|提供|呈现|汇报|报告)|"
    r"稍后请查收|"
    r"报告准备好后.{0,60}(请查收|给你|发给你|发送给你|提供|呈现)|"
    r"研究完成后我会.*?(呈现|提供|汇报|报告)|"
    r"研究完成后.{0,60}(将|会).{0,60}(一次性)?(输出|给出|提供|呈现|汇报|报告)|"
    r"我会.*?(第一时间|尽快).*?(呈现|提供|汇报|报告)|"
    r"完成后我会通知你|"
    r"期间你可以继续与我交流|"
    r"期间你可以.{0,60}(随时)?(继续)?(与我交流|和我交流)|"
    r"你可以.{0,60}(随时)?(继续)?(与我交流|和我交流|继续提问)|"
    r"(I( will|'ll) .*?(research|look into|investigate))|"
    r"(I'll .*?(research|look into|investigate))|"
    r"(I'll get back to you)|"
    r"(I will get back to you)"
    r")",
    re.I | re.S,
)


_INFRA_ERROR_RE = re.compile(
    r"("
    r"CDP connect failed|"
    r"connect_over_cdp|"
    r"BrowserType\.connect_over_cdp|"
    r"ws://127\.0\.0\.1:9222/|"
    r"Target page, context or browser has been closed|"
    r"BrowserContext\.new_page: Target page|"
    r"ECONNREFUSED|"
    r"Connection refused|"
    r"socket hang up"
    r")",
    re.I,
)

_UI_TRANSIENT_ERROR_RE = re.compile(
    r"("
    r"upload menu button not found|"
    r"upload menu item not found|"
    r"Gemini Tools button|"
    r"Cannot find Gemini Tools button|"
    r"Locator\.click: Timeout|"
    r"element is not enabled|"
    r"unable to load conversation|"
    r"无法加载对话"
    r")",
    re.I,
)

def _looks_like_thread_url(kind: str, url: str | None) -> bool:
    return provider_looks_like_thread_url(kind, url)


def _looks_like_infra_error(error_type: str, error: str) -> bool:
    et = str(error_type or "").strip().lower()
    if et in {"infraerror", "targetclosederror"}:
        return True
    return bool(_INFRA_ERROR_RE.search(str(error or "")))


def _looks_like_ui_transient_error(error_type: str, error: str) -> bool:
    et = str(error_type or "").strip().lower()
    if et in {"uitransienterror"}:
        return True
    if et in {"timeouterror"}:
        return True
    return bool(_UI_TRANSIENT_ERROR_RE.search(str(error or "")))


def _retry_after_seconds_for_error(*, error_type: str, error: str) -> float:
    if _looks_like_infra_error(error_type, error):
        base = float(_env_int("CHATGPTREST_INFRA_RETRY_AFTER_SECONDS", 120))
        return base + random.uniform(0.0, 3.0)
    if _looks_like_ui_transient_error(error_type, error):
        base = float(_env_int("CHATGPTREST_UI_RETRY_AFTER_SECONDS", 30))
        return base + random.uniform(0.0, 3.0)
    return 60.0 + random.uniform(0.0, 3.0)


def _retry_after_seconds_for_wait_phase_error(
    *,
    kind: str,
    conversation_url: str | None,
    error_type: str,
    error: str,
) -> float:
    default_wait = _retry_after_seconds_for_error(error_type=error_type, error=error)
    if not _looks_like_thread_url(str(kind or ""), conversation_url):
        return default_wait
    if _looks_like_infra_error(error_type, error):
        base = float(_env_int("CHATGPTREST_WAIT_INFRA_RETRY_AFTER_SECONDS", 20))
        return max(3.0, min(300.0, base)) + random.uniform(0.0, 1.5)
    if _looks_like_ui_transient_error(error_type, error):
        base = float(_env_int("CHATGPTREST_WAIT_UI_RETRY_AFTER_SECONDS", 12))
        return max(3.0, min(180.0, base)) + random.uniform(0.0, 1.5)
    return default_wait


def _wait_issue_family(*, kind: str, reason: str, has_thread_url: bool) -> str | None:
    provider = str(provider_id_for_kind(str(kind or "")) or "").strip().lower()
    if provider != "gemini":
        return None
    if reason == "missing_thread_url":
        return "gemini_no_thread_url"
    if reason == "no_progress" and has_thread_url:
        return "gemini_stable_thread_no_progress"
    return None


def _should_release_in_progress_web_job_to_wait(
    *,
    kind: str,
    conversation_url: str | None,
    meta: dict[str, Any],
) -> bool:
    if not is_web_ask_kind(kind):
        return False
    has_thread_url = _looks_like_thread_url(str(kind or ""), conversation_url)
    provider = str(provider_id_for_kind(str(kind or "")) or "").strip().lower()
    if provider == "gemini":
        return has_thread_url
    sent_marker = _debug_timeline_has_phase(meta, "sent") or _debug_timeline_has_phase(meta, "user_message_confirmed")
    return bool(sent_marker or has_thread_url)


def _coerce_retry_not_before(
    raw_not_before: Any,
    *,
    retry_after: Any | None,
    default_retry_after: float = 60.0,
    now: float | None = None,
) -> float:
    current = float(time.time() if now is None else now)
    fallback_after = float(default_retry_after)
    try:
        if retry_after is not None:
            fallback_after = max(0.0, float(retry_after))
    except Exception:
        fallback_after = float(default_retry_after)
    fallback = float(current + fallback_after)

    try:
        candidate = float(raw_not_before)
    except Exception:
        return fallback
    if not math.isfinite(candidate):
        return fallback
    # `not_before` is stored as wall-clock epoch seconds in SQLite. Values below this threshold
    # are almost certainly monotonic-clock bugs or other invalid timestamps and cause hot loops.
    if candidate < 1_000_000_000:
        return fallback
    return candidate


def _looks_like_db_write_unavailable(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.OperationalError):
        msg = str(exc).lower()
        return (
            "readonly database" in msg
            or "attempt to write a readonly database" in msg
            or "disk is full" in msg
            or "database or disk is full" in msg
            or "unable to open database file" in msg
        )
    return False


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _write_db_panic_snapshot(*, cfg: AppConfig, worker_id: str, exc: BaseException, tb: str) -> None:
    db_path = Path(cfg.db_path).expanduser()
    db_dir = db_path.parent
    panic_dir = (db_dir / "panic").resolve(strict=False)

    def _safe_stat(p: Path) -> dict[str, Any]:
        try:
            st = p.stat()
            return {
                "path": str(p),
                "exists": True,
                "mode_octal": oct(int(st.st_mode) & 0o777),
                "uid": int(getattr(st, "st_uid", -1)),
                "gid": int(getattr(st, "st_gid", -1)),
                "size": int(getattr(st, "st_size", 0)),
                "mtime": float(getattr(st, "st_mtime", 0.0)),
            }
        except FileNotFoundError:
            return {"path": str(p), "exists": False}
        except Exception as e:
            return {"path": str(p), "exists": None, "error_type": type(e).__name__, "error": str(e)[:500]}

    disk = None
    try:
        du = shutil.disk_usage(str(db_dir))
        disk = {"total": int(du.total), "used": int(du.used), "free": int(du.free)}
    except Exception:
        disk = None

    payload = {
        "ts": time.time(),
        "worker_id": str(worker_id),
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback": tb,
        "db": {
            "db_path": str(db_path),
            "db_dir": str(db_dir),
            "disk_usage": disk,
            "db_file": _safe_stat(db_path),
            "wal_file": _safe_stat(db_path.with_suffix(db_path.suffix + "-wal")),
            "shm_file": _safe_stat(db_path.with_suffix(db_path.suffix + "-shm")),
            "dir": _safe_stat(db_dir),
        },
    }
    out_path = panic_dir / "db_write_unavailable.json"
    _atomic_write_text(out_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _db_write_autofix_enabled() -> bool:
    # Default off: chmod-ing state is an active action; enable only after observation.
    return _truthy_env("CHATGPTREST_DB_WRITE_AUTOFIX", False)


def _try_db_write_autofix(*, cfg: AppConfig, worker_id: str, exc: BaseException, tb: str) -> None:
    if not _db_write_autofix_enabled():
        return

    db_path = Path(cfg.db_path).expanduser()
    db_dir = db_path.parent
    panic_dir = (db_dir / "panic").resolve(strict=False)
    now = time.time()

    def _mode_octal(path: Path) -> str | None:
        try:
            return oct(int(path.stat().st_mode) & 0o777)
        except Exception:
            return None

    def _chmod_add_bits(path: Path, bits: int) -> dict[str, Any]:
        before = _mode_octal(path)
        ok = False
        err: str | None = None
        try:
            st = path.stat()
            mode = int(st.st_mode) & 0o777
            new_mode = mode | int(bits)
            if new_mode != mode:
                os.chmod(path, new_mode)
            ok = True
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        after = _mode_octal(path)
        return {
            "path": str(path),
            "bits_added_octal": oct(int(bits)),
            "before_mode_octal": before,
            "after_mode_octal": after,
            "ok": ok,
            "error": err,
        }

    actions: list[dict[str, Any]] = []
    # Ensure parent dir is traversable/writable by the worker user (journaling needs this).
    if db_dir.exists():
        actions.append(_chmod_add_bits(db_dir, 0o300))  # u+wx
    # Ensure DB + WAL/SHM are writable (best-effort).
    for p in [db_path, db_path.with_suffix(db_path.suffix + "-wal"), db_path.with_suffix(db_path.suffix + "-shm")]:
        if p.exists():
            actions.append(_chmod_add_bits(p, 0o200))  # u+w

    payload = {
        "ts": now,
        "worker_id": str(worker_id),
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback": tb,
        "db_path": str(db_path),
        "db_dir": str(db_dir),
        "actions": actions,
    }
    try:
        _atomic_write_text(panic_dir / "db_write_autofix.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except Exception:
        pass


def _count_ready_jobs_fast(*, cfg: AppConfig, phase: str, kind_prefix: str | None) -> int | None:
    """
    Best-effort backlog signal used to avoid long "human sleep" pauses while the queue has work.
    Returns:
      - int (>=0): count (capped) of ready jobs
      - None: unknown (db busy/unavailable)
    """
    db_path = Path(cfg.db_path).expanduser()
    now = float(time.time())
    phase = str(phase or "").strip() or "send"
    kind_prefix = str(kind_prefix or "").strip() or None
    kind_like = f"{kind_prefix}%" if kind_prefix else None
    try:
        with sqlite3.connect(str(db_path), timeout=1.0) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT COUNT(1) AS n
                FROM jobs
                WHERE not_before <= ?
                  AND status IN (?, ?)
                  AND COALESCE(phase, 'send') = ?
                  AND (? IS NULL OR kind LIKE ?)
                LIMIT 100
                """,
                (now, JobStatus.QUEUED.value, JobStatus.COOLDOWN.value, phase, kind_prefix, kind_like),
            ).fetchone()
            if row is None:
                return 0
            return min(100, int(row["n"] or 0))
    except Exception:
        return None


def _should_worker_auto_autofix(*, kind: str, status: str, error_type: str, error: str) -> bool:
    kind = str(kind or "").strip().lower()
    status = str(status or "").strip().lower()
    et = str(error_type or "").strip().lower()
    pro_regen_error_types = {"proinstantanswerneedsregenerate"}
    if not is_worker_autofix_kind(kind):
        return False
    if status not in {"cooldown", "blocked", "needs_followup"}:
        return False
    if et in {"inprogress"}:
        return False
    if status == "blocked":
        return True
    if status == "needs_followup":
        return et in {"waitnoprogresstimeout", "waitnothreadurltimeout"} or et in pro_regen_error_types
    return _looks_like_infra_error(error_type, error) or _looks_like_ui_transient_error(error_type, error)


def _worker_autofix_allow_actions(*, kind: str, status: str, error_type: str, error: str) -> list[str]:
    kind = str(kind or "").strip().lower()
    status = str(status or "").strip().lower()
    et = str(error_type or "").strip().lower()
    is_chatgpt = kind.startswith("chatgpt_web.")
    allowed: list[str] = ["capture_ui"]
    if status == "blocked":
        if is_chatgpt:
            allowed.append("clear_blocked")
        allowed.extend(["restart_driver", "restart_chrome"])
        return allowed
    if _looks_like_infra_error(error_type, error):
        allowed.extend(["restart_driver", "restart_chrome"])
        return allowed
    if _looks_like_ui_transient_error(error_type, error):
        if is_chatgpt:
            allowed.append("refresh")
        allowed.append("restart_driver")
        return allowed
    if status == "needs_followup":
        if et == "proinstantanswerneedsregenerate":
            if is_chatgpt:
                allowed.extend(["regenerate", "refresh"])
            allowed.append("restart_driver")
            return allowed
        # Wait-stage timeout usually means UI/driver drift while conversation is already in-flight.
        # Prefer no-prompt recovery first; allow driver restart as a guarded fallback.
        if is_chatgpt:
            allowed.append("refresh")
        allowed.append("restart_driver")
        return allowed
    return allowed


async def _maybe_submit_worker_autofix(
    *,
    cfg: AppConfig,
    job_id: str,
    kind: str,
    status: str,
    error_type: str,
    error: str,
    conversation_url: str | None,
) -> None:
    # Default off: centralize auto-heal decisions in maint_daemon to avoid double-remediation.
    if not _truthy_env("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX", False):
        return
    if not _should_worker_auto_autofix(kind=kind, status=status, error_type=error_type, error=error):
        return

    window_seconds = max(60, _env_int("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_WINDOW_SECONDS", 1800))
    bucket = int(time.time() // float(window_seconds))
    idem = f"worker:auto_codex_autofix:{job_id}:{bucket}"
    min_interval = max(0, _env_int("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MIN_INTERVAL_SECONDS", 300))
    conversation_cooldown = max(
        0,
        _env_int("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_CONVERSATION_COOLDOWN_SECONDS", 1800),
    )

    allow_actions = _worker_autofix_allow_actions(kind=kind, status=status, error_type=error_type, error=error)
    apply_actions = _truthy_env("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_APPLY_ACTIONS", True)
    max_risk = _env_registry.get_str("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MAX_RISK") or "low"
    timeout_seconds = max(30, _env_int("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_TIMEOUT_SECONDS", 600))
    model = _env_registry.get_str("CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MODEL") or None

    with connect(cfg.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        if source_job_uses_synthetic_or_trivial_prompt(conn, str(job_id)):
            payload = {"source_job_id": str(job_id), "reason": "synthetic_or_trivial_prompt"}
            insert_event(conn, job_id=str(job_id), type="auto_autofix_skipped_synthetic_source", payload=payload)
            conn.commit()
            artifacts.append_event(
                cfg.artifacts_dir,
                str(job_id),
                type="auto_autofix_skipped_synthetic_source",
                payload=payload,
            )
            return
        wait_s = try_reserve(conn, key="worker_auto_codex_autofix", min_interval_seconds=int(min_interval))
        if wait_s > 0:
            conn.rollback()
            return
        normalized_conversation_url = str(conversation_url or "").strip()
        if normalized_conversation_url and conversation_cooldown > 0:
            existing = conn.execute(
                """
                SELECT job_id
                  FROM jobs
                 WHERE kind = 'repair.autofix'
                   AND created_at >= ?
                   AND json_extract(input_json, '$.conversation_url') = ?
                   AND json_extract(client_json, '$.name') = 'worker_auto_codex_autofix'
                 ORDER BY created_at DESC
                 LIMIT 1
                """,
                (time.time() - float(conversation_cooldown), normalized_conversation_url),
            ).fetchone()
            if existing is not None:
                conn.rollback()
                return
        repair = create_repair_autofix_job(
            conn=conn,
            artifacts_dir=cfg.artifacts_dir,
            idempotency_key=idem,
            client_name="worker_auto_codex_autofix",
            job_id=str(job_id),
            symptom=f"{error_type}: {str(error or '')[:500]}",
            conversation_url=(normalized_conversation_url or None),
            timeout_seconds=int(timeout_seconds),
            model=model,
            max_risk=str(max_risk),
            allow_actions=allow_actions,
            apply_actions=bool(apply_actions),
            max_attempts=1,
            enforce_conversation_single_flight=False,
        )
        payload = {"repair_job_id": str(repair.job_id), "idempotency_key": idem, "status": str(status), "error_type": str(error_type)}
        insert_event(conn, job_id=str(job_id), type="auto_autofix_submitted", payload=payload)
        conn.commit()
    artifacts.append_event(cfg.artifacts_dir, str(job_id), type="auto_autofix_submitted", payload=payload)


def _deep_research_is_ack(text: str) -> bool:
    trimmed = (text or "").strip()
    if not trimmed:
        return False
    # Some Deep Research runs emit a JSON envelope (visible in the transcript/export) that wraps the
    # actual assistant text in a `response` field. Unwrap it before applying heuristics, otherwise
    # the envelope can inflate length and evade the ack guard.
    trimmed = _unwrap_response_envelope_text(trimmed)
    # For Deep Research, the conversation export / early UI may contain an initial short “acknowledgement”
    # message while the report is still being prepared. Treat these as in_progress and keep waiting.
    return len(trimmed) <= 1200 and bool(_DEEP_RESEARCH_ACK_RE.search(trimmed))


def _deep_research_export_should_finalize(text: str) -> bool:
    trimmed = str(text or "").strip()
    if not trimmed:
        return False
    # Some Deep Research runs emit a JSON envelope (visible in the transcript/export) that wraps the
    # actual assistant text in a `response` field. Unwrap it before applying heuristics.
    trimmed = _unwrap_response_envelope_text(trimmed)
    if _deep_research_is_ack(trimmed):
        return False

    # New Deep Research UI can emit an embedded-app "implicit_link" stub in the transcript/export,
    # e.g. `{"path": "/Deep Research App/implicit_link::connector_openai_deep_research/start", ...}`.
    # This is not the final report content, so do not finalize from export in this case.
    if len(trimmed) <= 2500 and ("implicit_link" in trimmed or "connector_openai_deep_research" in trimmed):
        if trimmed.startswith("{") and trimmed.endswith("}"):
            try:
                obj = json.loads(trimmed)
            except Exception:
                obj = None
            if isinstance(obj, dict):
                path = str(obj.get("path") or "")
                if "connector_openai_deep_research" in path or "Deep Research" in path:
                    return False
        if "connector_openai_deep_research" in trimmed:
            return False

    return True


_CONNECTOR_TOOL_CALL_STUB_MAX_CHARS = 4000
_CONNECTOR_TOOL_CALL_STUB_ALLOWED_KEYS = {"path", "args"}
_ADOBE_ACROBAT_TOOL_CALL_PATH_RE = re.compile(r"^/Adobe Acrobat/", re.I)
_TOOL_PAYLOAD_MAX_CHARS = 12000


def _export_answer_is_connector_tool_call_stub(text: str) -> tuple[bool, dict[str, Any]]:
    """
    Conversation exports can contain assistant "tool-call" stubs instead of real answer content,
    e.g. when ChatGPT routes a `.zip` attachment into an external connector flow (Adobe Acrobat)
    and pauses on an OAuth/login screen.

    We should never finalize jobs from these stubs.
    """
    trimmed = str(text or "").strip()
    if not trimmed or len(trimmed) > _CONNECTOR_TOOL_CALL_STUB_MAX_CHARS:
        return False, {}
    if not (trimmed.startswith("{") and trimmed.endswith("}")):
        return False, {}
    try:
        obj = json.loads(trimmed)
    except Exception:
        return False, {}
    if not isinstance(obj, dict):
        return False, {}

    keys = {str(k) for k in obj.keys()}
    if not _CONNECTOR_TOOL_CALL_STUB_ALLOWED_KEYS.issubset(keys):
        return False, {}

    path = str(obj.get("path") or "").strip()
    if not path:
        return False, {}
    if _ADOBE_ACROBAT_TOOL_CALL_PATH_RE.search(path):
        return True, {"connector": "Adobe Acrobat", "path": path, "keys": sorted(keys)}
    return False, {}


def _should_reconcile_export_answer(
    *,
    candidate: str,
    deep_research: bool,
) -> tuple[bool, dict[str, Any]]:
    trimmed = str(candidate or "").strip()
    if not trimmed:
        return False, {"reason": "empty_export_answer"}
    is_stub, stub_info = _export_answer_is_connector_tool_call_stub(trimmed)
    if is_stub:
        return False, {"reason": "connector_tool_call_stub", **(stub_info or {})}
    if deep_research and (not _deep_research_export_should_finalize(trimmed)):
        return False, {"reason": "deep_research_not_final"}
    quality = _classify_answer_quality(trimmed, answer_chars=len(trimmed))
    if quality in {"suspect_meta_commentary", "suspect_context_acquisition_failure"}:
        return False, {"reason": f"answer_quality_{quality}", "answer_quality": quality}
    if quality == "suspect_short_answer" and _markdown_structure_score(trimmed) == 0:
        return False, {"reason": f"answer_quality_{quality}", "answer_quality": quality}
    return True, {"reason": "ok"}


def _looks_like_tool_payload_answer(text: str) -> tuple[bool, dict[str, Any]]:
    trimmed = str(text or "").strip()
    if not trimmed:
        return False, {}
    if len(trimmed) > _TOOL_PAYLOAD_MAX_CHARS:
        return False, {}
    if not (trimmed.startswith("{") and trimmed.endswith("}")):
        return False, {}
    try:
        obj = json.loads(trimmed)
    except Exception:
        return False, {}
    if not isinstance(obj, dict):
        return False, {}
    keys = {str(k) for k in obj.keys()}
    has_search_query = isinstance(obj.get("search_query"), list)
    has_response_length = "response_length" in keys
    # Typical tool-payload shape emitted by model-side search helpers:
    # {"search_query": [...], "response_length": "..."}.
    if has_search_query and has_response_length:
        return True, {"reason": "search_query_payload", "keys": sorted(keys)}
    # ChatGPT Pro ZIP attachment tool-payload: {"queries": ["file-..."]}.
    # The model references uploaded files instead of producing an answer.
    has_queries = isinstance(obj.get("queries"), list)
    if has_queries and all(isinstance(q, str) for q in obj["queries"]):
        return True, {"reason": "queries_file_reference", "keys": sorted(keys)}
    return False, {}


_MARKDOWN_HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S")
_MARKDOWN_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\S")
_MARKDOWN_TABLE_ROW_RE = re.compile(r"^\s*\|?.*\|.*\|")
_MARKDOWN_CODE_FENCE_RE = re.compile(r"^\s*```")
_MARKDOWN_HR_RE = re.compile(r"^\s*---+\s*$")
_INTERNAL_EXPORT_MARKUP_RE = re.compile(r"(?:[^]+|【\d+†[^\]]+】)")


def _markdown_structure_score(text: str) -> int:
    s = str(text or "")
    if not s.strip():
        return 0
    score = 0
    for line in s.splitlines():
        if _MARKDOWN_HEADING_RE.match(line):
            score += 3
            continue
        if _MARKDOWN_TABLE_ROW_RE.match(line):
            score += 2
            continue
        if _MARKDOWN_LIST_RE.match(line):
            score += 1
            continue
        if _MARKDOWN_CODE_FENCE_RE.match(line):
            score += 2
            continue
        if _MARKDOWN_HR_RE.match(line):
            score += 1
            continue
    return score


def _contains_internal_export_markup(text: str) -> bool:
    return bool(_INTERNAL_EXPORT_MARKUP_RE.search(str(text or "")))


def _deep_research_should_override_answer_with_export(
    *,
    current_answer: str,
    export_answer: str,
    export_dom_fallback: bool,
) -> tuple[bool, dict[str, Any]]:
    """
    Deep Research answers are often authored as Markdown, but DOM-based extraction can lose the
    original syntax (`#` / `-` / `|`). When we have a non-DOM backend export, prefer it if it
    preserves significantly more markdown structure.
    """
    info: dict[str, Any] = {"export_dom_fallback": bool(export_dom_fallback)}
    cur = _unwrap_response_envelope_text(str(current_answer or ""))
    exp = _unwrap_response_envelope_text(str(export_answer or ""))
    if not exp.strip():
        info["reason"] = "missing_export_answer"
        return False, info
    if export_dom_fallback:
        info["reason"] = "export_dom_fallback"
        return False, info
    if _contains_internal_export_markup(exp) and not _contains_internal_export_markup(cur):
        info["reason"] = "export_contains_internal_markup"
        return False, info

    cur_score = _markdown_structure_score(cur)
    exp_score = _markdown_structure_score(exp)
    info.update(
        {
            "current_score": int(cur_score),
            "export_score": int(exp_score),
            "current_chars": len(cur.strip()),
            "export_chars": len(exp.strip()),
        }
    )

    # Require a meaningful delta; avoid churn on tiny differences.
    if exp_score >= (cur_score + 2) and exp_score >= 2:
        info["reason"] = "export_has_more_markdown_structure"
        return True, info
    if cur_score == 0 and exp_score >= 2:
        info["reason"] = "current_missing_markdown_structure"
        return True, info
    info["reason"] = "no_override"
    return False, info


def _should_downgrade_when_export_missing_reply(
    *,
    current_answer: str,
    min_chars_required: int,
) -> tuple[bool, dict[str, Any]]:
    """
    Conversation export can temporarily lag behind the visible DOM answer, producing a window that
    matches the user prompt but contains no assistant reply yet.

    Only treat this as a blocking condition when the current answer is empty/short enough to be
    suspicious; otherwise, proceed with the DOM answer and record a warning for observability.
    """
    trimmed = str(current_answer or "").strip()
    threshold = max(200, int(min_chars_required or 0))
    info: dict[str, Any] = {"threshold": threshold, "answer_chars": len(trimmed)}
    if not trimmed:
        info["reason"] = "empty_answer"
        return True, info
    if len(trimmed) < threshold:
        info["reason"] = "answer_below_threshold"
        return True, info
    info["reason"] = "answer_sufficient"
    return False, info


_MIN_CHARS_GUARD_NEAR_MISS_RATIO = 0.05
_MIN_CHARS_GUARD_NEAR_MISS_MAX_ABS = 200
_MIN_CHARS_GUARD_STALL_AFTER_DOWNGRADES = 2
_MIN_CHARS_GUARD_MAX_DOWNGRADES = 10
_MIN_CHARS_GUARD_MAX_AGE_SECONDS = 30 * 60
_MIN_CHARS_GUARD_DEEP_RESEARCH_STALL_MIN_SECONDS = 20 * 60
_MIN_CHARS_GUARD_THINKING_STALL_MIN_SECONDS = 10 * 60
_THINKING_PRESETS = frozenset({"pro_extended", "thinking_extended", "thinking_heavy"})
_MIN_CHARS_GUARD_RETRY_BASE_SECONDS = 60
_MIN_CHARS_GUARD_RETRY_JITTER_MAX_SECONDS = 3
_WAIT_NO_PROGRESS_DEFAULT_TIMEOUT_SECONDS = 2 * 60 * 60
_WAIT_NO_PROGRESS_DEEP_RESEARCH_TIMEOUT_SECONDS = 6 * 60 * 60
_WAIT_NO_PROGRESS_NO_THREAD_URL_TIMEOUT_SECONDS = 30 * 60
_WAIT_NO_PROGRESS_RETRY_AFTER_SECONDS = 10 * 60
_WAIT_NO_PROGRESS_NON_PROGRESS_EVENT_TYPES = frozenset(
    {
        "job_created",
        "claimed",
        "lease_renewed",
        "wait_requeued",
        # Status churn while retrying wait-phase errors should not count as progress.
        "status_changed",
        # Infra telemetry snapshots can fire on every cooldown loop and otherwise hide stalls.
        "mihomo_delay_snapshot",
        "model_observed",
        # Export polling noise: these events can occur repeatedly while no new assistant content
        # is produced, and should not reset the no-progress timeout anchor.
        "conversation_exported",
        "conversation_export_forced",
        "model_observed_export",
        # Per-poll observability only; emitting timing telemetry should not hide a stalled wait job.
        "worker_timing",
    }
)


def _min_chars_guard_slack(min_chars_required: int) -> int:
    if min_chars_required <= 0:
        return 0
    return min(_MIN_CHARS_GUARD_NEAR_MISS_MAX_ABS, int(min_chars_required * _MIN_CHARS_GUARD_NEAR_MISS_RATIO))


def _min_chars_guard_history(conn: Any, job_id: str) -> tuple[int, float | None, int]:
    count = 0
    first_ts: float | None = None
    max_answer_chars = 0
    rows = conn.execute(
        """
        SELECT ts, payload_json
        FROM job_events
        WHERE job_id = ?
          AND type = ?
        ORDER BY id ASC
        """,
        (job_id, "completion_guard_downgraded"),
    ).fetchall()
    for row in rows:
        raw_payload = row[1]
        if not raw_payload:
            continue
        try:
            payload = json.loads(str(raw_payload))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("reason") or "") != "answer_too_short_for_min_chars":
            continue
        count += 1
        if first_ts is None and isinstance(row[0], (int, float)):
            first_ts = float(row[0])
        answer_chars = payload.get("answer_chars")
        if isinstance(answer_chars, int) and answer_chars > max_answer_chars:
            max_answer_chars = answer_chars
    return count, first_ts, max_answer_chars


def _min_chars_guard_should_complete_under_min_chars(
    *,
    conn: Any,
    job_id: str,
    answer_chars: int,
    min_chars_required: int,
    deep_research: bool = False,
    thinking_preset: bool = False,
    semantically_final: bool = False,
    now_ts: float | None = None,
) -> tuple[bool, dict[str, Any]]:
    now = float(now_ts) if isinstance(now_ts, (int, float)) else time.time()
    answer_chars = max(0, int(answer_chars))
    min_chars_required = max(0, int(min_chars_required))
    slack = _min_chars_guard_slack(min_chars_required)
    missing = max(0, min_chars_required - answer_chars)
    previous_downgrades, first_downgrade_ts, previous_max_answer_chars = _min_chars_guard_history(conn, job_id)
    age_seconds = (float(now - first_downgrade_ts) if first_downgrade_ts is not None else 0.0)
    details = {
        "answer_chars": answer_chars,
        "min_chars_required": min_chars_required,
        "missing_chars": missing,
        "slack_chars": slack,
        "previous_downgrades": previous_downgrades,
        "previous_max_answer_chars": previous_max_answer_chars,
        "first_downgrade_ts": first_downgrade_ts,
        "age_seconds": round(float(age_seconds), 3),
    }

    if slack > 0 and missing <= slack:
        details["decision_reason"] = "near_miss"
        return True, details
    if semantically_final and (not deep_research) and (not thinking_preset):
        semantic_threshold = max(120, min(600, int(min_chars_required * 0.4)))
        details["semantic_threshold"] = semantic_threshold
        if answer_chars >= semantic_threshold:
            details["decision_reason"] = "semantic_final_short_answer"
            return True, details
    if previous_downgrades >= _MIN_CHARS_GUARD_STALL_AFTER_DOWNGRADES and answer_chars <= previous_max_answer_chars:
        if deep_research:
            # Deep Research can spend a long time "silent" (no incremental assistant text) while gathering sources.
            # Do not declare a stall based on a couple of short polls; wait for a larger time window.
            if first_downgrade_ts is not None and age_seconds >= _MIN_CHARS_GUARD_DEEP_RESEARCH_STALL_MIN_SECONDS:
                details["decision_reason"] = "stalled"
                return True, details
        elif thinking_preset:
            # Extended-thinking presets (pro_extended, thinking_extended, thinking_heavy) can spend
            # 5-10+ minutes producing multi-turn 'thoughts' content that is invisible to the export
            # API. Do not declare stall until the grace period has elapsed.
            if first_downgrade_ts is not None and age_seconds >= _MIN_CHARS_GUARD_THINKING_STALL_MIN_SECONDS:
                details["decision_reason"] = "stalled"
                return True, details
        else:
            details["decision_reason"] = "stalled"
            return True, details
    if previous_downgrades >= _MIN_CHARS_GUARD_MAX_DOWNGRADES or (
        first_downgrade_ts is not None and age_seconds >= _MIN_CHARS_GUARD_MAX_AGE_SECONDS
    ):
        details["decision_reason"] = "cap_exceeded"
        return True, details

    details["decision_reason"] = "waiting"
    return False, details


def _completion_guard_retry_after_seconds() -> float:
    return float(_MIN_CHARS_GUARD_RETRY_BASE_SECONDS + random.randint(0, _MIN_CHARS_GUARD_RETRY_JITTER_MAX_SECONDS))


def _wait_no_progress_guard_enabled() -> bool:
    return _truthy_env("CHATGPTREST_WAIT_NO_PROGRESS_GUARD", True)


def _wait_no_progress_timeout_seconds(*, deep_research: bool) -> float:
    if deep_research:
        raw = _env_int(
            "CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_DEEP_RESEARCH_SECONDS",
            _WAIT_NO_PROGRESS_DEEP_RESEARCH_TIMEOUT_SECONDS,
        )
    else:
        raw = _env_int("CHATGPTREST_WAIT_NO_PROGRESS_TIMEOUT_SECONDS", _WAIT_NO_PROGRESS_DEFAULT_TIMEOUT_SECONDS)
    return max(0.0, float(raw))


def _wait_no_progress_no_thread_timeout_seconds() -> float:
    raw = _env_int(
        "CHATGPTREST_WAIT_NO_THREAD_URL_TIMEOUT_SECONDS",
        _WAIT_NO_PROGRESS_NO_THREAD_URL_TIMEOUT_SECONDS,
    )
    return max(0.0, float(raw))


def _wait_no_progress_retry_after_seconds() -> float:
    raw = _env_int("CHATGPTREST_WAIT_NO_PROGRESS_RETRY_AFTER_SECONDS", _WAIT_NO_PROGRESS_RETRY_AFTER_SECONDS)
    return max(1.0, float(raw))


def _wait_no_progress_status() -> JobStatus:
    raw = _env_registry.get_str("CHATGPTREST_WAIT_NO_PROGRESS_STATUS").lower()
    if raw == JobStatus.ERROR.value:
        return JobStatus.ERROR
    if raw == JobStatus.COOLDOWN.value:
        return JobStatus.COOLDOWN
    if raw == JobStatus.BLOCKED.value:
        return JobStatus.BLOCKED
    return JobStatus.NEEDS_FOLLOWUP


def _safe_payload_obj(raw_payload: Any) -> dict[str, Any]:
    if raw_payload is None:
        return {}
    if isinstance(raw_payload, dict):
        return raw_payload
    if not isinstance(raw_payload, str):
        return {}
    s = raw_payload.strip()
    if not s:
        return {}
    try:
        obj = json.loads(s)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _wait_no_progress_event_is_progress(event_type: str, payload: dict[str, Any]) -> bool:
    et = str(event_type or "").strip().lower()
    if not et:
        return False
    if et in _WAIT_NO_PROGRESS_NON_PROGRESS_EVENT_TYPES:
        return False
    if et == "phase_changed":
        return str(payload.get("to") or "").strip().lower() == "wait"
    return True


def _wait_no_progress_last_progress_anchor(
    *,
    conn: Any,
    job_id: str,
    created_at: float,
) -> tuple[float, str]:
    fallback_ts = float(created_at)
    rows = conn.execute(
        """
        SELECT ts, type, payload_json
        FROM job_events
        WHERE job_id = ?
        ORDER BY id DESC
        LIMIT 512
        """,
        (job_id,),
    ).fetchall()
    for row in rows:
        ts = row[0]
        if not isinstance(ts, (int, float)):
            continue
        event_type = str(row[1] or "").strip().lower()
        payload = _safe_payload_obj(row[2])
        if not _wait_no_progress_event_is_progress(event_type, payload):
            continue
        return float(ts), event_type
    return fallback_ts, "job_created"


def _wait_no_progress_timeout_decision(
    *,
    conn: Any,
    job: Any,
    kind: str,
    params: dict[str, Any],
    conversation_url: str | None,
    now_ts: float | None = None,
) -> dict[str, Any] | None:
    if not _wait_no_progress_guard_enabled():
        return None
    now = float(now_ts) if isinstance(now_ts, (int, float)) else time.time()
    deep_research = bool((params or {}).get("deep_research"))
    timeout_seconds = _wait_no_progress_timeout_seconds(deep_research=deep_research)
    no_thread_timeout_seconds = _wait_no_progress_no_thread_timeout_seconds()
    if timeout_seconds <= 0 and no_thread_timeout_seconds <= 0:
        return None

    anchor_ts, anchor_source = _wait_no_progress_last_progress_anchor(
        conn=conn,
        job_id=str(job.job_id),
        created_at=float(getattr(job, "created_at", now)),
    )
    age_seconds = max(0.0, float(now - anchor_ts))
    effective_conversation_url = str(conversation_url or "").strip() or str(getattr(job, "conversation_url", "") or "").strip()
    has_thread_url = _looks_like_thread_url(kind, effective_conversation_url)

    reason = None
    effective_timeout_seconds = timeout_seconds
    if not has_thread_url and no_thread_timeout_seconds > 0 and age_seconds >= no_thread_timeout_seconds:
        reason = "missing_thread_url"
        effective_timeout_seconds = no_thread_timeout_seconds
    elif timeout_seconds > 0 and age_seconds >= timeout_seconds:
        reason = "no_progress"
        effective_timeout_seconds = timeout_seconds

    if not reason:
        return None

    status = _wait_no_progress_status()
    retry_after_seconds = _wait_no_progress_retry_after_seconds()
    error_type = "WaitNoThreadUrlTimeout" if reason == "missing_thread_url" else "WaitNoProgressTimeout"
    if reason == "missing_thread_url":
        error = (
            "wait phase timed out without stable conversation_url; "
            f"age={age_seconds:.0f}s threshold={effective_timeout_seconds:.0f}s"
        )
    else:
        error = f"wait phase made no progress; age={age_seconds:.0f}s threshold={effective_timeout_seconds:.0f}s"
    payload = {
        "reason": reason,
        "status": status.value,
        "kind": str(kind or ""),
        "deep_research": bool(deep_research),
        "age_seconds": round(float(age_seconds), 3),
        "timeout_seconds": round(float(effective_timeout_seconds), 3),
        "last_progress_ts": round(float(anchor_ts), 3),
        "last_progress_source": anchor_source,
        "has_thread_url": bool(has_thread_url),
        "conversation_url": (effective_conversation_url or None),
        "retry_after_seconds": round(float(retry_after_seconds), 3),
        "error_type": error_type,
    }
    issue_family = _wait_issue_family(kind=str(kind or ""), reason=reason, has_thread_url=bool(has_thread_url))
    if issue_family:
        payload["issue_family"] = issue_family
    return {
        "status": status,
        "error_type": error_type,
        "error": error,
        "not_before": float(now + retry_after_seconds),
        "phase": "wait",
        "payload": payload,
    }


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _write_json(path: Path, payload: dict) -> None:
    _atomic_write_json(path, payload)


def _debug_timeline_first_t(meta: dict[str, Any], phase: str) -> float | None:
    timeline = meta.get("debug_timeline")
    if not isinstance(timeline, list):
        return None
    wanted = str(phase or "").strip()
    if not wanted:
        return None
    for item in timeline:
        if not isinstance(item, dict):
            continue
        if str(item.get("phase") or "").strip() != wanted:
            continue
        t = item.get("t")
        if isinstance(t, (int, float)):
            return float(t)
    return None


def _debug_timeline_has_phase(meta: dict[str, Any], phase: str) -> bool:
    return _debug_timeline_first_t(meta, phase) is not None


def _resolve_local_artifact_path(*, cfg: AppConfig, raw_path: str) -> Path | None:
    raw = str(raw_path or "").strip()
    if not raw:
        return None

    p = Path(raw).expanduser()
    if p.is_absolute():
        return p if p.exists() else None

    try:
        artifacts_abs = cfg.artifacts_dir.resolve()
    except Exception:
        artifacts_abs = cfg.artifacts_dir
    repo_root = artifacts_abs.parent

    candidates = [
        repo_root / p,
        artifacts_abs / p,
    ]
    for c in candidates:
        try:
            if c.exists():
                return c.resolve()
        except Exception:
            continue
    return None


def _maybe_attach_debug_artifacts(
    *,
    cfg: AppConfig,
    db_path: Path,
    job_id: str,
    worker_id: str,
    lease_token: str,
    meta: dict[str, Any],
) -> None:
    raw = meta.get("debug_artifacts")
    if not isinstance(raw, dict) or not raw:
        return

    dst_dir = cfg.artifacts_dir / "jobs" / job_id / "debug"
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return

    # Avoid debug-artifact storms: on frequent timeouts, the driver may attach fresh
    # HTML/screenshot/text every poll slice. Throttle per job to keep disk usage bounded.
    max_per_job = _env_registry.get_int("CHATGPTREST_DEBUG_ARTIFACTS_MAX_PER_JOB")
    if max_per_job <= 0:
        return
    min_interval_seconds = max(0.0, float(_env_registry.get_int("CHATGPTREST_DEBUG_ARTIFACTS_MIN_INTERVAL_SECONDS")))

    now = time.time()
    state_path = dst_dir / ".debug_artifacts_state.json"
    captures = 0
    last_capture_ts = 0.0
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(state, dict):
                captures = int(state.get("captures") or 0)
                last_capture_ts = float(state.get("last_capture_ts") or 0.0)
        except Exception:
            captures = 0
            last_capture_ts = 0.0
    else:
        # Best-effort backfill from existing files (cap the scan).
        try:
            with os.scandir(dst_dir) as it:
                for ent in it:
                    if not ent.is_file():
                        continue
                    if not ent.name.endswith(".html"):
                        continue
                    captures += 1
                    try:
                        last_capture_ts = max(last_capture_ts, float(ent.stat().st_mtime))
                    except Exception:
                        pass
                    if captures >= max_per_job:
                        break
        except Exception:
            captures = 0
            last_capture_ts = 0.0

    if captures >= max_per_job:
        return
    if last_capture_ts > 0 and (now - float(last_capture_ts)) < float(min_interval_seconds):
        return

    copied: dict[str, str] = {}
    for k, v in raw.items():
        key = str(k or "").strip()
        if not key:
            continue
        if not isinstance(v, str) or not v.strip():
            continue
        src = _resolve_local_artifact_path(cfg=cfg, raw_path=v)
        if src is None:
            continue
        try:
            if not src.exists() or not src.is_file():
                continue
        except Exception:
            continue

        base = src.name
        dst = dst_dir / base
        if dst.exists():
            try:
                if dst.stat().st_size == src.stat().st_size:
                    rel = None
                    try:
                        rel = dst.resolve().relative_to(cfg.artifacts_dir.resolve()).as_posix()
                    except Exception:
                        rel = dst.as_posix()
                    copied[key] = rel
                    continue
            except Exception:
                pass
            dst = dst_dir / f"{src.stem}.{int(time.time())}_{random.randint(1000, 9999)}{src.suffix}"
        try:
            shutil.copy2(src, dst)
        except Exception:
            continue
        try:
            rel = dst.resolve().relative_to(cfg.artifacts_dir.resolve()).as_posix()
        except Exception:
            rel = dst.as_posix()
        copied[key] = rel

    if not copied:
        return

    try:
        state_path.write_text(
            json.dumps(
                {
                    "captures": int(captures) + 1,
                    "last_capture_ts": float(now),
                    "max_per_job": int(max_per_job),
                    "min_interval_seconds": float(min_interval_seconds),
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass

    meta["job_debug_artifacts"] = copied
    payload = {"debug": copied, "worker_id": worker_id, "lease_token": lease_token}
    try:
        with connect(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            insert_event(conn, job_id=job_id, type="debug_artifacts_attached", payload=payload)
            conn.commit()
    except Exception:
        pass
    try:
        artifacts.append_event(cfg.artifacts_dir, job_id, type="debug_artifacts_attached", payload=payload)
    except Exception:
        pass


def _maybe_attach_generated_images(
    *,
    cfg: AppConfig,
    db_path: Path,
    job_id: str,
    worker_id: str,
    lease_token: str,
    meta: dict[str, Any],
) -> None:
    raw = meta.get("images")
    if not isinstance(raw, list) or not raw:
        return

    dst_dir = cfg.artifacts_dir / "jobs" / job_id / "images"
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return

    attached: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        src_raw = str(item.get("path") or "").strip()
        if not src_raw:
            continue
        src = _resolve_local_artifact_path(cfg=cfg, raw_path=src_raw)
        if src is None:
            continue
        try:
            if not src.exists() or not src.is_file():
                continue
        except Exception:
            continue

        base = src.name
        dst = dst_dir / base
        if dst.exists():
            try:
                if dst.stat().st_size == src.stat().st_size:
                    try:
                        rel = dst.resolve().relative_to(cfg.artifacts_dir.resolve()).as_posix()
                    except Exception:
                        rel = dst.as_posix()
                    attached.append({**item, "path": rel})
                    continue
            except Exception:
                pass
            dst = dst_dir / f"{src.stem}.{int(time.time())}_{random.randint(1000, 9999)}{src.suffix}"

        try:
            shutil.copy2(src, dst)
        except Exception:
            continue

        try:
            rel = dst.resolve().relative_to(cfg.artifacts_dir.resolve()).as_posix()
        except Exception:
            rel = dst.as_posix()

        attached.append({**item, "path": rel})

    if not attached:
        return

    meta["job_images"] = attached
    payload = {"count": len(attached), "worker_id": worker_id, "lease_token": lease_token}
    try:
        with connect(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            insert_event(conn, job_id=job_id, type="images_attached", payload=payload)
            conn.commit()
    except Exception:
        pass
    try:
        artifacts.append_event(cfg.artifacts_dir, job_id, type="images_attached", payload=payload)
    except Exception:
        pass


def _format_job_images_markdown(*, job_id: str, meta: dict[str, Any]) -> str | None:
    raw = meta.get("job_images")
    if not isinstance(raw, list) or not raw:
        return None

    conversation_url = str(meta.get("conversation_url") or "").strip() or None
    lines: list[str] = []
    lines.append("# Generated images")
    lines.append("")
    lines.append(f"- job_id: `{job_id}`")
    if conversation_url:
        lines.append(f"- conversation_url: `{conversation_url}`")
    lines.append(f"- images: `{len(raw)}`")
    lines.append("")

    base = Path("jobs") / str(job_id)
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        rel_path = str(item.get("path") or "").strip()
        if not rel_path:
            continue
        try:
            embed_path = Path(rel_path).relative_to(base).as_posix()
        except Exception:
            embed_path = rel_path

        mime_type = str(item.get("mime_type") or "").strip()
        size_bytes = item.get("bytes")
        width = item.get("width")
        height = item.get("height")

        lines.append(f"## Image {idx}")
        lines.append(f"- path: `{rel_path}`")
        if mime_type:
            lines.append(f"- mime_type: `{mime_type}`")
        if isinstance(size_bytes, int):
            lines.append(f"- bytes: `{size_bytes}`")
        if width is not None and height is not None:
            lines.append(f"- size: `{width}x{height}`")
        lines.append("")
        lines.append(f"![image {idx}]({embed_path})")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _record_mihomo_delay_snapshot(*, cfg: AppConfig, job_id: str, status: str, reason: str | None) -> None:
    try:
        mh_cfg = mihomo_delay.load_mihomo_delay_config()
        records = mihomo_delay.snapshot_once(cfg=mh_cfg)
        log_path = mihomo_delay.daily_log_path(artifacts_dir=cfg.artifacts_dir)
        for rec in records:
            mihomo_delay.append_jsonl(log_path, rec)

        history: dict[str, Any] = {}
        for rec in records:
            if not bool(rec.get("ok")):
                continue
            group = str(rec.get("group") or "")
            selected = str(rec.get("selected") or "")
            if not group or not selected:
                continue
            stats = mihomo_delay.summarize_recent(log_path=log_path, group=group, selected=selected, max_records=50)
            if stats is not None:
                history[f"{group}:{selected}"] = stats

        payload: dict[str, Any] = {
            "status": str(status),
            "reason": (str(reason) if reason else None),
            "log_path": str(log_path),
            "records": records,
            "history": history,
        }

        try:
            artifacts.append_event(cfg.artifacts_dir, job_id, type="mihomo_delay_snapshot", payload=payload)
        except Exception:
            pass
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                insert_event(conn, job_id=job_id, type="mihomo_delay_snapshot", payload=payload)
                conn.commit()
        except Exception:
            pass
        try:
            _write_json(cfg.artifacts_dir / "jobs" / job_id / "mihomo_delay_snapshot.json", payload)
        except Exception:
            pass
    except Exception:
        return


def _truthy_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


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


def _issue_autoreport_enabled() -> bool:
    return _truthy_env("CHATGPTREST_ISSUE_AUTOREPORT_ENABLED", True)


def _issue_autoreport_statuses() -> set[str]:
    return _shared_issue_autoreport_statuses(_env_registry.get_str("CHATGPTREST_ISSUE_AUTOREPORT_STATUSES"))


def _ws_single(s: str, *, max_chars: int = 400) -> str:
    return _shared_ws_single(s, max_chars=max_chars)


def _error_signature_fragment(*, error_type: str, error: str) -> str:
    return _shared_error_signature_fragment(error_type=error_type, error=error)


def _issue_project_for_job(job: Any) -> str:
    default_project = _ws_single(_env_registry.get_str("CHATGPTREST_ISSUE_DEFAULT_PROJECT") or "chatgptrest", max_chars=200)
    return _shared_issue_project_from_client_json(getattr(job, "client_json", None), default_project=default_project)


def _issue_severity_for_status(*, status: str, error_type: str, error: str) -> str:
    return _shared_issue_severity_for_status(status=status, error_type=error_type, error=error)


def _maybe_auto_report_issue(
    *,
    cfg: AppConfig,
    job: Any,
    status: str,
    error_type: str,
    error: str,
    conversation_url: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> None:
    if not _issue_autoreport_enabled():
        return
    status_n = str(status or "").strip().lower()
    if status_n not in _issue_autoreport_statuses():
        return

    kind = _ws_single(getattr(job, "kind", ""), max_chars=200)
    if not kind:
        return

    job_id = _ws_single(getattr(job, "job_id", ""), max_chars=128)
    if not job_id:
        return

    error_type_n = _ws_single(error_type, max_chars=120) or "RuntimeError"
    error_n = str(error or "")
    if not error_n.strip():
        error_n = f"<{error_type_n}: empty error>"
    conv_url = _ws_single(conversation_url or getattr(job, "conversation_url", ""), max_chars=2000) or None

    # Keep one auto-report event per job to avoid noisy duplicates across retries/restarts.
    try:
        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            exists = conn.execute(
                "SELECT 1 FROM job_events WHERE job_id = ? AND type = ? LIMIT 1",
                (job_id, "issue_auto_reported"),
            ).fetchone()
            if exists is not None:
                conn.commit()
                return

            issue, created, info = client_issues.report_issue(
                conn,
                project=_issue_project_for_job(job),
                title=f"{kind} {status_n}: {error_type_n}",
                severity=_issue_severity_for_status(status=status_n, error_type=error_type_n, error=error_n),
                kind=kind,
                symptom=f"{error_type_n}: {_ws_single(error_n, max_chars=1000)}",
                raw_error=error_n,
                job_id=job_id,
                conversation_url=conv_url,
                artifacts_path=f"jobs/{job_id}",
                source=AUTO_ISSUE_SOURCE,
                tags=["auto_report", "worker", status_n],
                metadata={
                    "status": status_n,
                    "error_type": error_type_n,
                    "attempts": int(getattr(job, "attempts", 0) or 0),
                    "max_attempts": int(getattr(job, "max_attempts", 0) or 0),
                    "phase": _ws_single(getattr(job, "phase", ""), max_chars=20) or None,
                    "kind": kind,
                    **(dict(extra_metadata) if isinstance(extra_metadata, dict) else {}),
                },
                fingerprint=_auto_issue_fingerprint(
                    kind=kind,
                    status=status_n,
                    error_type=error_type_n,
                    error=error_n,
                ),
            )
            payload = {
                "issue_id": issue.issue_id,
                "created": bool(created),
                "reopened": bool(info.get("reopened")),
                "status": status_n,
                "error_type": error_type_n,
                "kind": kind,
                "fingerprint_hash": issue.fingerprint_hash,
            }
            insert_event(conn, job_id=job_id, type="issue_auto_reported", payload=payload)
            conn.commit()
        try:
            artifacts.append_event(cfg.artifacts_dir, job_id, type="issue_auto_reported", payload=payload)
        except Exception:
            pass
    except Exception:
        return


def _record_attachment_contract_signal_once(
    *,
    cfg: AppConfig,
    job_id: str,
    payload: dict[str, Any],
) -> None:
    try:
        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            exists = conn.execute(
                "SELECT 1 FROM job_events WHERE job_id = ? AND type = ? LIMIT 1",
                (str(job_id), "attachment_contract_missing_detected"),
            ).fetchone()
            if exists is not None:
                conn.commit()
                return
            insert_event(
                conn,
                job_id=str(job_id),
                type="attachment_contract_missing_detected",
                payload=dict(payload),
            )
            conn.commit()
        artifacts.append_event(
            cfg.artifacts_dir,
            str(job_id),
            type="attachment_contract_missing_detected",
            payload=dict(payload),
        )
    except Exception:
        return


_ZIP_BUNDLE_ALLOWED_SUFFIXES = {
    ".md",
    ".txt",
    ".patch",
    ".diff",
    ".log",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".py",
    ".pyi",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".sh",
    ".ps1",
    ".bat",
    ".sql",
    ".csv",
    ".tsv",
    ".xml",
    ".html",
    ".css",
}

_ZIP_CODE_FENCE_LANG = {
    ".md": "markdown",
    ".txt": "text",
    ".patch": "diff",
    ".diff": "diff",
    ".log": "text",
    ".json": "json",
    ".jsonl": "text",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "text",
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".sh": "bash",
    ".ps1": "powershell",
    ".bat": "bat",
    ".sql": "sql",
    ".csv": "text",
    ".tsv": "text",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
}


def _safe_zip_member_relpath(name: str) -> str | None:
    raw = str(name or "").replace("\\", "/").strip()
    if not raw:
        return None
    raw = raw.lstrip("/")
    parts = [p for p in raw.split("/") if p not in {"", "."}]
    if not parts:
        return None
    if any(p == ".." for p in parts):
        return None
    # Strip NUL/control chars that can break renderers.
    safe_parts: list[str] = []
    for part in parts:
        cleaned = "".join(ch if (ch >= " " and ch not in {"\u2028", "\u2029"}) else "_" for ch in part)
        cleaned = cleaned.replace("\x00", "_")
        safe_parts.append(cleaned or "_")
    return "/".join(safe_parts)


def _render_zip_bundle_section(
    *,
    zip_name: str,
    member_path: str,
    member_bytes: int,
    included_bytes: int,
    truncated: bool,
    suffix: str,
    text: str,
) -> str:
    lang = _ZIP_CODE_FENCE_LANG.get(str(suffix or "").lower(), "")
    trunc_note = "（已截断）" if truncated else ""
    header = (
        f"## {zip_name} :: {member_path}\n\n"
        f"- 原始大小：{member_bytes} bytes\n"
        f"- 收录：{included_bytes} bytes{trunc_note}\n\n"
    )
    fence = f"```{lang}\n{text.rstrip()}\n```\n\n"
    return header + fence


def _maybe_expand_zip_attachments_for_chatgpt(
    *,
    artifacts_dir: Path,
    job_id: str,
    file_paths: list[str],
) -> tuple[list[str], dict[str, Any] | None]:
    """
    Work around ChatGPT UI sometimes routing `.zip` uploads into external connector flows (e.g. Adobe Acrobat),
    which can require OAuth and yield a tool-call stub instead of the actual answer.

    Strategy: if `.zip` attachments are present, build 2 generated markdown files:
    - ZIP_BUNDLE.md: concatenated text-like contents from the zip(s)
    - ZIP_MANIFEST.md: included/skipped list (no absolute paths)
    Then replace `.zip` attachments with these generated files.
    """
    if not file_paths:
        return file_paths, None
    if not _truthy_env("CHATGPTREST_EXPAND_ZIP_ATTACHMENTS", False):
        return file_paths, None

    zip_paths: list[Path] = []
    passthrough: list[str] = []
    for raw in list(file_paths):
        p = str(raw or "").strip()
        if not p:
            continue
        if p.lower().endswith(".zip"):
            zip_paths.append(Path(p))
        else:
            passthrough.append(p)
    if not zip_paths:
        return file_paths, None

    max_members = max(1, _env_int("CHATGPTREST_ZIP_EXPAND_MAX_MEMBERS", 600))
    max_files = max(1, _env_int("CHATGPTREST_ZIP_BUNDLE_MAX_FILES", 250))
    per_file_max_bytes = max(8_000, _env_int("CHATGPTREST_ZIP_BUNDLE_PER_FILE_MAX_BYTES", 200_000))
    bundle_max_bytes = max(50_000, _env_int("CHATGPTREST_ZIP_BUNDLE_MAX_BYTES", 5_000_000))

    inputs_dir = artifacts_dir / "jobs" / job_id / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = inputs_dir / "ZIP_MANIFEST.md"
    bundle_path = inputs_dir / "ZIP_BUNDLE.md"
    state_path = inputs_dir / "zip_expand_state.json"

    zip_meta: list[dict[str, Any]] = []
    included: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    bundle_parts: list[str] = []
    bundle_bytes = 0
    member_seen = 0
    included_files = 0

    for zip_idx, zip_path in enumerate(zip_paths):
        zip_name = zip_path.name
        rec: dict[str, Any] = {"zip": zip_name, "zip_index": int(zip_idx)}
        try:
            st = zip_path.stat()
            rec["zip_size"] = int(st.st_size)
            rec["zip_mtime"] = float(st.st_mtime)
        except Exception:
            rec["zip_size"] = None
            rec["zip_mtime"] = None

        included_before = len(included)
        skipped_before = len(skipped)
        members_total = 0

        try:
            zf = zipfile.ZipFile(zip_path)
        except Exception as exc:
            rec["open_ok"] = False
            rec["open_error"] = f"{type(exc).__name__}: {exc}"
            zip_meta.append(rec)
            skipped.append(
                {
                    "zip": zip_name,
                    "member": None,
                    "reason": "zip_open_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        with zf:
            rec["open_ok"] = True
            for info in list(zf.infolist()):
                if member_seen >= max_members:
                    break
                member_seen += 1
                members_total += 1
                if getattr(info, "is_dir", None) and info.is_dir():
                    continue

                rel = _safe_zip_member_relpath(str(getattr(info, "filename", "") or ""))
                if rel is None:
                    skipped.append({"zip": zip_name, "member": str(getattr(info, "filename", "") or ""), "reason": "unsafe_path"})
                    continue

                suffix = Path(rel).suffix.lower()
                member_bytes = int(getattr(info, "file_size", 0) or 0)

                if suffix not in _ZIP_BUNDLE_ALLOWED_SUFFIXES:
                    skipped.append({"zip": zip_name, "member": rel, "bytes": member_bytes, "reason": "unsupported_suffix"})
                    continue
                if included_files >= max_files:
                    skipped.append({"zip": zip_name, "member": rel, "bytes": member_bytes, "reason": "max_files_cap"})
                    continue

                try:
                    with zf.open(info) as fp:
                        data = fp.read(int(per_file_max_bytes) + 1)
                except Exception as exc:
                    skipped.append(
                        {
                            "zip": zip_name,
                            "member": rel,
                            "bytes": member_bytes,
                            "reason": "read_failed",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    continue

                truncated = len(data) > int(per_file_max_bytes)
                if truncated:
                    data = data[: int(per_file_max_bytes)]
                if b"\x00" in data:
                    skipped.append({"zip": zip_name, "member": rel, "bytes": member_bytes, "reason": "binary_detected"})
                    continue

                text = data.decode("utf-8", errors="replace")
                section = _render_zip_bundle_section(
                    zip_name=zip_name,
                    member_path=rel,
                    member_bytes=member_bytes,
                    included_bytes=len(data),
                    truncated=bool(truncated),
                    suffix=suffix,
                    text=text,
                )
                section_bytes = len(section.encode("utf-8", errors="replace"))
                if (bundle_bytes + section_bytes) > int(bundle_max_bytes):
                    skipped.append({"zip": zip_name, "member": rel, "bytes": member_bytes, "reason": "bundle_size_cap"})
                    continue

                bundle_parts.append(section)
                bundle_bytes += int(section_bytes)
                included_files += 1
                included.append(
                    {
                        "zip": zip_name,
                        "member": rel,
                        "bytes": member_bytes,
                        "included_bytes": len(data),
                        "truncated": bool(truncated),
                    }
                )

        rec["members_total"] = int(members_total)
        rec["included_members"] = int(len(included) - included_before)
        rec["skipped_members"] = int(len(skipped) - skipped_before)
        zip_meta.append(rec)

    if not bundle_parts:
        # Nothing usable found; keep original .zip attachment(s) to preserve legacy behavior.
        return file_paths, {"ok": False, "reason": "zip_bundle_empty", "zip_names": [p.name for p in zip_paths]}

    bundle_header = (
        "# ZIP_BUNDLE（ChatgptREST 自动生成）\n\n"
        "说明：原始 `.zip` 附件已在上传前展开；下方按“zip 文件名 :: zip 内路径”的形式合并了文本内容。\n"
        "若某些文件未出现，请查看 `ZIP_MANIFEST.md` 的 skipped 列表（可能是二进制、后缀不支持、或超出大小上限）。\n\n"
    )
    bundle_payload = bundle_header + "".join(bundle_parts)
    bundle_path.write_text(bundle_payload, encoding="utf-8", errors="replace")

    # Manifest for the model (no absolute paths).
    lines: list[str] = []
    lines.append("# ZIP_MANIFEST（ChatgptREST 自动生成）")
    lines.append("")
    lines.append("说明：原始 `.zip` 附件已在上传前展开；文本内容已合并到附件 `ZIP_BUNDLE.md`。")
    lines.append("")
    lines.append("## Zips")
    for rec in zip_meta:
        lines.append(
            f"- {rec.get('zip')} (open_ok={rec.get('open_ok')}, members_total={rec.get('members_total')}, included={rec.get('included_members')}, skipped={rec.get('skipped_members')})"
        )
    lines.append("")
    lines.append("## Included（已合并进 ZIP_BUNDLE.md）")
    for item in included:
        lines.append(
            f"- {item.get('zip')} :: {item.get('member')} "
            f"(bytes={item.get('bytes')}, included_bytes={item.get('included_bytes')}, truncated={item.get('truncated')})"
        )
    lines.append("")
    lines.append("## Skipped（未合并）")
    for item in skipped:
        zip_name = item.get("zip")
        member = item.get("member")
        reason = item.get("reason")
        b = item.get("bytes")
        lines.append(f"- {zip_name} :: {member} (bytes={b}) reason={reason}")
    lines.append("")
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8", errors="replace")

    # State for debugging (includes absolute zip paths).
    state = {
        "ok": True,
        "job_id": job_id,
        "zip_paths": [str(p) for p in zip_paths],
        "bundle_path": bundle_path.as_posix(),
        "manifest_path": manifest_path.as_posix(),
        "bundle_bytes": int(bundle_bytes),
        "zip_meta": zip_meta,
        "included_items": included,
        "skipped_items": skipped,
        "limits": {
            "max_members": int(max_members),
            "max_files": int(max_files),
            "per_file_max_bytes": int(per_file_max_bytes),
            "bundle_max_bytes": int(bundle_max_bytes),
        },
    }
    try:
        _write_json(state_path, state)
    except Exception:
        pass

    new_paths = list(passthrough) + [manifest_path.as_posix(), bundle_path.as_posix()]
    info = {
        "ok": True,
        "zip_names": [p.name for p in zip_paths],
        "bundle_path": bundle_path.as_posix(),
        "manifest_path": manifest_path.as_posix(),
        "bundle_bytes": int(bundle_bytes),
        "included_files": int(len(included)),
        "skipped_files": int(len(skipped)),
    }
    return new_paths, info


def _normalize_job_phase(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return "wait" if raw == "wait" else "send"


def _normalize_worker_role(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"send", "wait"}:
        return raw
    return "all"


_ANSWER_ID_RE = re.compile(r"^[a-f0-9]{32}$")


async def _rehydrate_answer_from_answer_id(
    *,
    tool_caller: ToolCaller,
    answer_id: str,
    expected_chars: int | None,
    timeout_seconds: float = 20.0,
    max_total_chars: int = 2_000_000,
) -> str | None:
    """
    Fetch a previously persisted full answer blob from the driver (chatgpt_web_answer_get).

    This is used when an ask job timed out and returned `in_progress`, but the driver
    already persisted a longer answer that would otherwise be lost.
    """
    key = str(answer_id or "").strip().lower()
    if not _ANSWER_ID_RE.fullmatch(key):
        return None

    offset = 0
    chunks: list[str] = []
    total = 0
    deadline = time.time() + float(max(5.0, timeout_seconds))
    for _ in range(1000):
        if time.time() > deadline:
            break
        res = await asyncio.to_thread(
            tool_caller.call_tool,
            tool_name="chatgpt_web_answer_get",
            tool_args={"answer_id": key, "offset": int(offset), "max_chars": 20000},
            timeout_sec=30.0,
        )
        if not isinstance(res, dict) or not bool(res.get("ok")):
            return None
        chunk = str(res.get("chunk") or "")
        chunks.append(chunk)
        total += len(chunk)
        if total >= int(max_total_chars):
            break
        if bool(res.get("done")):
            break
        next_offset = res.get("next_offset")
        if not isinstance(next_offset, int) or next_offset <= offset:
            break
        offset = next_offset

    text = "".join(chunks)
    if not text.strip():
        return None
    if expected_chars is not None and expected_chars > 0 and len(text) < max(1, int(expected_chars) - 50):
        return None
    return text


def _extract_export_model_info_from_conversation_export_obj(*, obj: dict[str, Any]) -> dict[str, Any] | None:
    # Support both export formats:
    # - official-ish: {"mapping": {...}, "current_node": "..."}
    # - simplified: {"messages": [{"role": "...", "metadata": {...}}, ...]}
    mapping = obj.get("mapping")
    if isinstance(mapping, dict):
        cur = obj.get("current_node")
        if isinstance(cur, str) and cur:
            seen: set[str] = set()
            last_meta: dict[str, Any] | None = None
            while cur and cur not in seen:
                seen.add(cur)
                node = mapping.get(cur)
                if not isinstance(node, dict):
                    break
                msg = node.get("message")
                if isinstance(msg, dict):
                    author = msg.get("author")
                    role = author.get("role") if isinstance(author, dict) else None
                    if str(role or "").strip().lower() == "assistant":
                        meta = msg.get("metadata")
                        last_meta = meta if isinstance(meta, dict) else {}
                        break
                parent = node.get("parent")
                cur = parent if isinstance(parent, str) else ""

            if last_meta is None:
                return None

            finish_details = last_meta.get("finish_details")
            finish_type = finish_details.get("type") if isinstance(finish_details, dict) else None
            return {
                "export_conversation_id": obj.get("conversation_id"),
                "export_default_model_slug": obj.get("default_model_slug"),
                "export_last_assistant_model_slug": (last_meta.get("model_slug") or last_meta.get("default_model_slug")),
                "export_last_assistant_thinking_effort": (last_meta.get("thinking_effort") or last_meta.get("reasoning_effort")),
                "export_last_assistant_finish_type": finish_type,
                "export_last_assistant_is_complete": last_meta.get("is_complete"),
            }

    messages = obj.get("messages")
    if isinstance(messages, list):
        for m in reversed(messages):
            if not isinstance(m, dict):
                continue
            if str(m.get("role") or "").strip().lower() != "assistant":
                continue
            meta = m.get("metadata") if isinstance(m.get("metadata"), dict) else {}
            finish_details = meta.get("finish_details")
            finish_type = finish_details.get("type") if isinstance(finish_details, dict) else None
            return {
                "export_conversation_id": obj.get("conversation_id"),
                "export_default_model_slug": obj.get("default_model_slug"),
                "export_last_assistant_model_slug": (meta.get("model_slug") or meta.get("default_model_slug")),
                "export_last_assistant_thinking_effort": (meta.get("thinking_effort") or meta.get("reasoning_effort")),
                "export_last_assistant_finish_type": finish_type,
                "export_last_assistant_is_complete": meta.get("is_complete"),
            }
    return None


def _extract_export_model_info_from_conversation_export(*, export_path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(export_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    return _extract_export_model_info_from_conversation_export_obj(obj=obj)


def _should_prefer_conversation_answer(*, candidate: str, current: str) -> bool:
    cand = _normalize_text(candidate)
    cur = _normalize_text(current)
    if not cand:
        return False
    if cand == cur:
        return False
    if not cur:
        return True
    if _contains_internal_export_markup(cand) and not _contains_internal_export_markup(cur):
        return False

    # Prefer when candidate is strictly longer and contains the current text.
    if len(cand) >= (len(cur) + 200) and (cur in cand or cand.startswith(cur[:200])):
        return True

    # Heuristic: current looks truncated (dangling markdown marker) but candidate is longer.
    if len(cand) >= (len(cur) + 200):
        tail = cur[-8:]
        if tail.endswith(("*", "-", "```", "|")):
            return True
    return False


def _looks_like_rescue_followup(question: str) -> bool:
    """
    Heuristic: "rescue follow-up" prompts that try to unstick a stalled answer, e.g.
    "继续…上一次回答卡住了…不要再写代码…".

    Used as a guardrail to avoid duplicate user messages when the parent job is about to
    complete (race).
    """

    q = str(question or "").strip()
    if not q:
        return False

    # Common Chinese rescue patterns.
    if q.startswith(("继续", "请继续", "继续。", "上一次", "上次")):
        return True
    if "卡住" in q or "不要再运行任何代码" in q or "不要展示代码" in q:
        return True

    # English-ish rescue patterns (cheap to support).
    lower = q.lower()
    if lower.startswith(("continue", "please continue")):
        return True
    if "stuck" in lower or "final answer" in lower or "don't run" in lower:
        return True

    return False


async def _maybe_export_conversation(
    *,
    cfg: AppConfig,
    job_id: str,
    conversation_url: str | None,
    tool_caller: ToolCaller | None,
    force: bool = False,
    cache: dict[str, Any] | None = None,
) -> None:
    if not conversation_url or not str(conversation_url).strip():
        return
    # Opt-2: If we already exported successfully in this _run_once cycle and
    # this is not a force call, skip the duplicate MCP request entirely.
    if cache is not None and not force and cache.get("ok"):
        return
    # Only ChatGPT conversations support server-side export via `chatgpt_web_conversation_export`.
    # (Gemini uses a different URL shape like /app/<id> and has no export tool yet.)
    if "/c/" not in str(conversation_url):
        return
    if not _truthy_env("CHATGPTREST_SAVE_CONVERSATION_EXPORT", True):
        return
    if tool_caller is None:
        return

    # Export fallback is valuable (fixes "refresh to show answer"), but we must avoid
    # repeatedly hitting the UI/network on every wait slice. Keep this conservative.
    ok_cooldown_seconds = max(0, _env_int("CHATGPTREST_CONVERSATION_EXPORT_OK_COOLDOWN_SECONDS", 120))
    fail_backoff_base_seconds = max(1, _env_int("CHATGPTREST_CONVERSATION_EXPORT_FAIL_BACKOFF_BASE_SECONDS", 60))
    fail_backoff_max_seconds = max(
        fail_backoff_base_seconds,
        _env_int("CHATGPTREST_CONVERSATION_EXPORT_FAIL_BACKOFF_MAX_SECONDS", 600),
    )
    global_min_interval_seconds = max(0, _env_int("CHATGPTREST_CONVERSATION_EXPORT_GLOBAL_MIN_INTERVAL_SECONDS", 30))
    force_wait_max_seconds = max(0, min(30, _env_int("CHATGPTREST_CONVERSATION_EXPORT_FORCE_MAX_WAIT_SECONDS", 5)))

    export_state_path = cfg.artifacts_dir / "jobs" / job_id / "conversation_export_state.json"
    state = _read_json(export_state_path) or {}
    now = time.time()

    try:
        last_ok_at = float(state.get("last_ok_at") or 0.0)
    except Exception:
        last_ok_at = 0.0
    # "force" is only meant to bypass OK cooldown (for cases where an earlier successful export
    # likely captured only the user message). Never bypass failure backoff.
    if (not force) and ok_cooldown_seconds > 0 and last_ok_at > 0 and now < (last_ok_at + float(ok_cooldown_seconds)):
        return

    try:
        cooldown_until = float(state.get("cooldown_until") or 0.0)
    except Exception:
        cooldown_until = 0.0
    if cooldown_until > 0 and now < cooldown_until:
        return

    if global_min_interval_seconds > 0:
        def _record_skipped(*, wait_seconds: float, reason: str) -> None:
            payload = {
                "reason": str(reason or "global_throttle"),
                "wait_seconds": round(float(wait_seconds), 3),
                "min_interval_seconds": int(global_min_interval_seconds),
                "force": bool(force),
            }
            try:
                artifacts.append_event(cfg.artifacts_dir, job_id, type="conversation_export_skipped", payload=payload)
            except Exception:
                pass
            try:
                with connect(cfg.db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    insert_event(conn, job_id=job_id, type="conversation_export_skipped", payload=payload)
                    conn.commit()
            except Exception:
                pass

        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                wait_seconds = try_reserve(
                    conn,
                    key="chatgpt_web_conversation_export",
                    min_interval_seconds=int(global_min_interval_seconds),
                )
                conn.commit()
            if wait_seconds > 0:
                if force and force_wait_max_seconds > 0 and float(wait_seconds) <= float(force_wait_max_seconds):
                    await asyncio.sleep(float(wait_seconds))
                    with connect(cfg.db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        wait_seconds2 = try_reserve(
                            conn,
                            key="chatgpt_web_conversation_export",
                            min_interval_seconds=int(global_min_interval_seconds),
                        )
                        conn.commit()
                    if wait_seconds2 > 0:
                        if force:
                            _record_skipped(wait_seconds=float(wait_seconds2), reason="global_throttle_still_busy")
                        return
                else:
                    if force:
                        _record_skipped(wait_seconds=float(wait_seconds), reason="global_throttle")
                    return
        except Exception:
            # If we can't coordinate the throttle, proceed best-effort (export is non-critical).
            pass

    try:
        attempt_payload = dict(state)
        attempt_payload.setdefault("version", 1)
        attempt_payload["last_attempt_at"] = float(now)
        _write_json(export_state_path, attempt_payload)
    except Exception:
        pass

    export_res = None
    tool_args: dict[str, Any] = {"conversation_url": str(conversation_url).strip()}
    if normalize_driver_mode(cfg.driver_mode) in {"internal_mcp", "embedded"}:
        dst_path = cfg.artifacts_dir / "jobs" / job_id / "conversation.json"
        tool_args["dst_path"] = str(dst_path)
    for attempt in range(2):
        try:
            export_res = await asyncio.to_thread(
                tool_caller.call_tool,
                tool_name="chatgpt_web_conversation_export",
                tool_args=tool_args,
                timeout_sec=60.0,
            )
        except Exception as exc:
            if attempt == 0:
                await asyncio.sleep(2.0)
                continue
            try:
                prev = _read_json(export_state_path) or state
                fail_count = int(prev.get("consecutive_failures") or 0) + 1
                backoff = min(float(fail_backoff_max_seconds), float(fail_backoff_base_seconds) * (2.0 ** float(fail_count - 1)))
                payload = dict(prev)
                payload.setdefault("version", 1)
                payload["last_fail_at"] = float(time.time())
                payload["consecutive_failures"] = int(fail_count)
                payload["cooldown_until"] = float(time.time() + backoff)
                payload["last_error_type"] = type(exc).__name__
                payload["last_error"] = str(exc)[:800]
                _write_json(export_state_path, payload)
            except Exception:
                pass
            try:
                artifacts.append_event(
                    cfg.artifacts_dir,
                    job_id,
                    type="conversation_export_failed",
                    payload={"error_type": type(exc).__name__, "error": str(exc)},
                )
            except Exception:
                pass
            try:
                with connect(cfg.db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    insert_event(
                        conn,
                        job_id=job_id,
                        type="conversation_export_failed",
                        payload={"error_type": type(exc).__name__, "error": str(exc)},
                    )
                    conn.commit()
            except Exception:
                pass
            return

        if isinstance(export_res, dict) and (not bool(export_res.get("ok"))):
            status = str(export_res.get("status") or "").strip().lower()
            err = str(export_res.get("error") or "").strip().lower()
            retryable = status == "error" and ("conversation_not_found" in err or "http 404" in err)
            if attempt == 0 and retryable:
                await asyncio.sleep(2.0)
                continue
        break

    if not isinstance(export_res, dict) or not bool(export_res.get("ok")):
        try:
            prev = _read_json(export_state_path) or state
            fail_count = int(prev.get("consecutive_failures") or 0) + 1
            backoff = min(float(fail_backoff_max_seconds), float(fail_backoff_base_seconds) * (2.0 ** float(fail_count - 1)))
            payload = dict(prev)
            payload.setdefault("version", 1)
            payload["last_fail_at"] = float(time.time())
            payload["consecutive_failures"] = int(fail_count)
            payload["cooldown_until"] = float(time.time() + backoff)
            payload["last_error_type"] = "ConversationExportFailed"
            payload["last_error"] = json.dumps(export_res, ensure_ascii=False)[:800]
            _write_json(export_state_path, payload)
        except Exception:
            pass
        try:
            artifacts.append_event(
                cfg.artifacts_dir,
                job_id,
                type="conversation_export_failed",
                payload={"result": export_res},
            )
        except Exception:
            pass
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                insert_event(conn, job_id=job_id, type="conversation_export_failed", payload={"result": export_res})
                conn.commit()
        except Exception:
            pass
        return

    src = str(export_res.get("export_path") or "").strip()
    if not src:
        return
    src_path = Path(src)
    try:
        meta = artifacts.write_conversation_export_from_file(cfg.artifacts_dir, job_id, src_path=src_path)
    except Exception as exc:
        try:
            prev = _read_json(export_state_path) or state
            fail_count = int(prev.get("consecutive_failures") or 0) + 1
            backoff = min(float(fail_backoff_max_seconds), float(fail_backoff_base_seconds) * (2.0 ** float(fail_count - 1)))
            payload = dict(prev)
            payload.setdefault("version", 1)
            payload["last_fail_at"] = float(time.time())
            payload["consecutive_failures"] = int(fail_count)
            payload["cooldown_until"] = float(time.time() + backoff)
            payload["last_error_type"] = type(exc).__name__
            payload["last_error"] = str(exc)[:800]
            _write_json(export_state_path, payload)
        except Exception:
            pass
        try:
            artifacts.append_event(
                cfg.artifacts_dir,
                job_id,
                type="conversation_export_failed",
                payload={"error_type": type(exc).__name__, "error": str(exc), "export_path": src},
            )
        except Exception:
            pass
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                insert_event(
                    conn,
                    job_id=job_id,
                    type="conversation_export_failed",
                    payload={"error_type": type(exc).__name__, "error": str(exc), "export_path": src},
                )
                conn.commit()
        except Exception:
            pass
        return

    try:
        payload = dict(_read_json(export_state_path) or state)
        payload.setdefault("version", 1)
        payload["last_ok_at"] = float(time.time())
        payload["consecutive_failures"] = 0
        payload["cooldown_until"] = 0.0
        payload["last_error_type"] = None
        payload["last_error"] = None
        payload["last_export_chars"] = int(meta.conversation_export_chars)
        _write_json(export_state_path, payload)
    except Exception:
        pass

    try:
        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            store_conversation_export_result(
                conn,
                artifacts_dir=cfg.artifacts_dir,
                job_id=job_id,
                conversation_export_path=meta.conversation_export_path,
                conversation_export_sha256=meta.conversation_export_sha256,
                conversation_export_chars=meta.conversation_export_chars,
                conversation_export_format=meta.conversation_export_format,
            )
            conn.commit()
    except Exception:
        return

    # Update cache so subsequent non-force calls in the same _run_once reuse this result.
    if cache is not None:
        cache["ok"] = True
        cache["conversation_export_chars"] = int(meta.conversation_export_chars)

    # Best-effort: capture model/thinking metadata from the exported conversation JSON.
    try:
        export_file = cfg.artifacts_dir / str(meta.conversation_export_path)
        export_info = _extract_export_model_info_from_conversation_export(export_path=export_file)
    except Exception:
        export_info = None
    if export_info:
        payload = dict(export_info)
        payload.setdefault("source", "conversation_export")
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                exists = conn.execute(
                    "SELECT 1 FROM job_events WHERE job_id = ? AND type = ? LIMIT 1",
                    (job_id, "model_observed_export"),
                ).fetchone()
                if exists is None:
                    insert_event(conn, job_id=job_id, type="model_observed_export", payload=payload)
                conn.commit()
        except Exception:
            pass
        try:
            artifacts.append_event(cfg.artifacts_dir, job_id, type="model_observed_export", payload=payload)
        except Exception:
            pass


async def _throttle_sends(
    *,
    cfg: AppConfig,
    job_id: str,
    rate_limit_key: str,
    min_interval_seconds: int,
    stop_event: asyncio.Event | None = None,
) -> float:
    """
    Enforce a minimum spacing between "send prompt" actions.

    This is process- and DB-coordinated (SQLite transaction) so multiple workers
    won't accidentally burst-send prompts.
    """
    interval = int(min_interval_seconds or 0)
    if interval <= 0:
        return 0.0

    rate_limit_key = str(rate_limit_key or "").strip()
    if not rate_limit_key:
        return 0.0

    waited = 0.0
    while True:
        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            wait_seconds = try_reserve(conn, key=rate_limit_key, min_interval_seconds=interval)
            if wait_seconds > 0:
                insert_event(
                    conn,
                    job_id=job_id,
                    type="send_throttled",
                    payload={"wait_seconds": round(float(wait_seconds), 3), "min_interval_seconds": interval},
                )
            conn.commit()
        if wait_seconds <= 0:
            return waited

        if stop_event is not None and stop_event.is_set():
            return waited

        jitter = random.random() * min(0.5, wait_seconds * 0.2)
        sleep_for = float(wait_seconds + jitter)
        waited += sleep_for
        try:
            artifacts.append_event(
                cfg.artifacts_dir,
                job_id,
                type="send_throttled",
                payload={"wait_seconds": round(sleep_for, 3), "base_wait_seconds": round(float(wait_seconds), 3), "jitter_seconds": round(float(jitter), 3)},
            )
        except Exception:
            pass
        if stop_event is None:
            await asyncio.sleep(sleep_for)
        else:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=sleep_for)
                return waited
            except asyncio.TimeoutError:
                pass


async def _throttle_sends_fixed_window(
    *,
    cfg: AppConfig,
    job_id: str,
    rate_limit_key: str,
    window_seconds: int,
    max_per_window: int,
    stop_event: asyncio.Event | None = None,
) -> float:
    """
    Enforce a max-per-window rate limit for \"send prompt\" actions.

    This is process- and DB-coordinated (SQLite transaction) so multiple workers
    won't accidentally burst-send prompts.
    """
    win = int(window_seconds or 0)
    max_n = int(max_per_window or 0)
    if win <= 0 or max_n <= 0:
        return 0.0
    rate_limit_key = str(rate_limit_key or "").strip()
    if not rate_limit_key:
        return 0.0

    waited = 0.0
    while True:
        now = time.time()
        with connect(cfg.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            wait_seconds = try_reserve_fixed_window(
                conn,
                key=rate_limit_key,
                window_seconds=win,
                max_per_window=max_n,
                now=now,
            )
            if wait_seconds > 0:
                insert_event(
                    conn,
                    job_id=job_id,
                    type="send_throttled",
                    payload={
                        "wait_seconds": round(float(wait_seconds), 3),
                        "window_seconds": int(win),
                        "max_per_window": int(max_n),
                        "rate_limit_kind": "fixed_window",
                    },
                )
            conn.commit()
        if wait_seconds <= 0:
            return waited

        if stop_event is not None and stop_event.is_set():
            return waited

        jitter = random.random() * min(1.0, wait_seconds * 0.2)
        sleep_for = float(wait_seconds + jitter)
        waited += sleep_for
        try:
            artifacts.append_event(
                cfg.artifacts_dir,
                job_id,
                type="send_throttled",
                payload={
                    "wait_seconds": round(sleep_for, 3),
                    "base_wait_seconds": round(float(wait_seconds), 3),
                    "jitter_seconds": round(float(jitter), 3),
                    "window_seconds": int(win),
                    "max_per_window": int(max_n),
                    "rate_limit_kind": "fixed_window",
                },
            )
        except Exception:
            pass
        if stop_event is None:
            await asyncio.sleep(sleep_for)
        else:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=sleep_for)
                return waited
            except asyncio.TimeoutError:
                pass


async def _lease_heartbeat(
    *,
    stop_event: asyncio.Event,
    lease_lost_event: asyncio.Event,
    db_path: Path,
    artifacts_dir: Path,
    job_id: str,
    worker_id: str,
    lease_token: str,
    lease_ttl_seconds: int,
) -> None:
    interval = max(1.0, float(lease_ttl_seconds) / 3.0)
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            pass
        with connect(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            ok = renew_lease(
                conn,
                artifacts_dir=artifacts_dir,
                job_id=job_id,
                worker_id=worker_id,
                lease_token=lease_token,
                lease_ttl_seconds=lease_ttl_seconds,
            )
            conn.commit()
        if not ok:
            lease_lost_event.set()
            stop_event.set()
            return


async def _cancel_watch(
    *,
    stop_event: asyncio.Event,
    cancel_event: asyncio.Event,
    db_path: Path,
    job_id: str,
    poll_seconds: float = 0.5,
) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
            return
        except asyncio.TimeoutError:
            pass
        with connect(db_path) as conn:
            row = conn.execute("SELECT cancel_requested_at FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return
        if row["cancel_requested_at"] is not None:
            cancel_event.set()
            stop_event.set()
            return


def _executor_for_job(cfg: AppConfig, kind: str, *, tool_caller: ToolCaller | None = None):
    return _resolve_executor_for_job(cfg=cfg, kind=kind, tool_caller=tool_caller)


async def _run_once(
    *,
    cfg: AppConfig,
    worker_id: str,
    lease_ttl_seconds: int | None = None,
    role: str | None = None,
    kind_prefix: str | None = None,
) -> bool:
    db_path = cfg.db_path
    artifacts_dir = cfg.artifacts_dir
    lease_ttl_seconds = int(lease_ttl_seconds or cfg.lease_ttl_seconds)
    role = _normalize_worker_role(role)
    phase_filter = role if role in {"send", "wait"} else None
    kind_prefix = str(kind_prefix or "").strip() or None
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = claim_next_job(
            conn,
            artifacts_dir=artifacts_dir,
            worker_id=worker_id,
            lease_ttl_seconds=lease_ttl_seconds,
            phase=phase_filter,
            kind_prefix=kind_prefix,
        )
        conn.commit()
    if job is None:
        return False

    # ── Timing instrumentation ──────────────────────────────────────────────
    _t_claimed = time.time()
    _t_created = float(getattr(job, "created_at", 0.0) or 0.0)
    _queue_wait = _t_claimed - _t_created if _t_created > 0 else 0.0

    tool_caller = None
    tool_caller_init_error: str | None = None
    _export_cache: dict[str, Any] = {}
    if is_provider_web_kind(job.kind) or job.kind.startswith("repair."):
        try:
            tool_caller = build_tool_caller(
                mode=cfg.driver_mode,
                url=cfg.driver_url,
                client_name="chatgptrest",
                client_version="0.1.0",
            )
        except Exception as exc:
            if job.kind.startswith("repair."):
                tool_caller = None
                tool_caller_init_error = f"{type(exc).__name__}: {exc}"
            else:
                with connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    store_error_result(
                        conn,
                        artifacts_dir=artifacts_dir,
                        job_id=job.job_id,
                        worker_id=worker_id,
                        lease_token=str(job.lease_token or ""),
                        error_type=type(exc).__name__,
                        error=f"Failed to initialize driver backend: {exc}",
                        status=JobStatus.ERROR,
                    )
                    conn.commit()
                _maybe_auto_report_issue(
                    cfg=cfg,
                    job=job,
                    status=JobStatus.ERROR.value,
                    error_type=type(exc).__name__,
                    error=f"Failed to initialize driver backend: {exc}",
                    conversation_url=str(job.conversation_url or "").strip() or None,
                    extra_metadata={"stage": "tool_caller_init"},
                )
                return True
    executor = _executor_for_job(cfg, job.kind, tool_caller=tool_caller)
    if isinstance(executor, RepairExecutor) and tool_caller_init_error:
        executor = RepairExecutor(cfg=cfg, tool_caller=tool_caller, tool_caller_init_error=tool_caller_init_error)
    if isinstance(executor, RepairAutofixExecutor) and tool_caller_init_error:
        executor = RepairAutofixExecutor(cfg=cfg, tool_caller=tool_caller, tool_caller_init_error=tool_caller_init_error)
    if isinstance(executor, RepairOpenPrExecutor) and tool_caller_init_error:
        executor = RepairOpenPrExecutor(cfg=cfg, tool_caller=tool_caller, tool_caller_init_error=tool_caller_init_error)
    if executor is None:
        with connect(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            store_error_result(
                conn,
                artifacts_dir=artifacts_dir,
                job_id=job.job_id,
                worker_id=worker_id,
                lease_token=str(job.lease_token or ""),
                error_type="ValueError",
                error=f"Unknown job kind: {job.kind}",
                status=JobStatus.ERROR,
            )
            conn.commit()
        _maybe_auto_report_issue(
            cfg=cfg,
            job=job,
            status=JobStatus.ERROR.value,
            error_type="ValueError",
            error=f"Unknown job kind: {job.kind}",
            conversation_url=str(job.conversation_url or "").strip() or None,
            extra_metadata={"stage": "executor_lookup"},
        )
        return True

    lease_token = str(job.lease_token or "")
    # Load job input/params
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT input_json, params_json, cancel_requested_at FROM jobs WHERE job_id = ?",
            (job.job_id,),
        ).fetchone()
    if row is None:
        return True

    input_obj = json.loads(str(row["input_json"] or "{}"))
    params_obj = json.loads(str(row["params_json"] or "{}"))
    if not isinstance(input_obj, dict):
        input_obj = {}
    if not isinstance(params_obj, dict):
        params_obj = {}
    if job.conversation_url and isinstance(input_obj, dict):
        input_obj.setdefault("conversation_url", job.conversation_url)

    job_phase = _normalize_job_phase(getattr(job, "phase", None))
    exec_phase = "full"
    if is_web_ask_kind(job.kind):
        if role == "send":
            exec_phase = "send"
        elif role == "wait":
            exec_phase = "wait"
        else:
            exec_phase = "wait" if job_phase == "wait" else "full"

    # Follow-up: allow callers to reference a previous job instead of passing conversation_url.
    # This keeps client logic minimal: `input.parent_job_id=<job_id>` will continue in the same thread.
    parent_job_id = None
    if isinstance(input_obj, dict):
        raw_parent = input_obj.get("parent_job_id")
        if isinstance(raw_parent, str) and raw_parent.strip():
            parent_job_id = raw_parent.strip()
    if job.parent_job_id and not parent_job_id:
        parent_job_id = str(job.parent_job_id).strip() or None

    if (
        isinstance(input_obj, dict)
        and parent_job_id
        and not str(input_obj.get("conversation_url") or "").strip()
    ):
        with connect(db_path) as conn:
            parent_row = conn.execute(
                "SELECT conversation_url, status FROM jobs WHERE job_id = ?",
                (str(parent_job_id),),
            ).fetchone()
        parent_conversation_url = ""
        parent_status = ""
        if parent_row is not None:
            parent_conversation_url = str(parent_row["conversation_url"] or "").strip()
            parent_status = str(parent_row["status"] or "").strip().lower()

        if parent_conversation_url:
            input_obj["conversation_url"] = parent_conversation_url
            try:
                with connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    set_conversation_url(
                        conn,
                        artifacts_dir=artifacts_dir,
                        job_id=job.job_id,
                        worker_id=worker_id,
                        lease_token=lease_token,
                        conversation_url=parent_conversation_url,
                    )
                    insert_event(
                        conn,
                        job_id=job.job_id,
                        type="conversation_url_inherited",
                        payload={"parent_job_id": parent_job_id, "conversation_url": parent_conversation_url},
                    )
                    conn.commit()
                artifacts.append_event(
                    artifacts_dir,
                    job.job_id,
                    type="conversation_url_inherited",
                    payload={"parent_job_id": parent_job_id, "conversation_url": parent_conversation_url},
                )
            except LeaseLost:
                return True
            except Exception:
                pass
        elif parent_row is None:
            msg = f"parent_job_id not found: {parent_job_id}"
            with connect(db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                store_error_result(
                    conn,
                    artifacts_dir=artifacts_dir,
                    job_id=job.job_id,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    error_type="ValueError",
                    error=msg,
                    status=JobStatus.ERROR,
                )
                conn.commit()
            _maybe_auto_report_issue(
                cfg=cfg,
                job=job,
                status=JobStatus.ERROR.value,
                error_type="ValueError",
                error=msg,
                conversation_url=str(job.conversation_url or "").strip() or None,
                extra_metadata={"stage": "parent_conversation_inherit"},
            )
            return True
        else:
            payload = {
                "parent_job_id": parent_job_id,
                "parent_status": parent_status or None,
                "reason": "parent_conversation_url_missing",
            }
            try:
                with connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    insert_event(conn, job_id=job.job_id, type="conversation_url_inherit_skipped", payload=payload)
                    conn.commit()
                artifacts.append_event(artifacts_dir, job.job_id, type="conversation_url_inherit_skipped", payload=payload)
            except LeaseLost:
                return True
            except Exception:
                pass

    # Persist a caller-provided conversation_url early (helps observability and follow-up),
    # even if the executor later times out/in_progress.
    input_conversation_url = ""
    if isinstance(input_obj, dict):
        input_conversation_url = str(input_obj.get("conversation_url") or "").strip()
    if input_conversation_url:
        existing_url = ""
        try:
            with connect(db_path) as conn:
                existing_row = conn.execute(
                    "SELECT conversation_url FROM jobs WHERE job_id = ?",
                    (job.job_id,),
                ).fetchone()
            if existing_row is not None:
                existing_url = str(existing_row["conversation_url"] or "").strip()
        except Exception:
            existing_url = str(job.conversation_url or "").strip()
        if not existing_url:
            try:
                with connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    set_conversation_url(
                        conn,
                        artifacts_dir=artifacts_dir,
                        job_id=job.job_id,
                        worker_id=worker_id,
                        lease_token=lease_token,
                        conversation_url=input_conversation_url,
                    )
                    conn.commit()
            except LeaseLost:
                return True
            except Exception:
                pass
    if row["cancel_requested_at"] is not None:
        with connect(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            store_canceled_result(
                conn,
                artifacts_dir=artifacts_dir,
                job_id=job.job_id,
                worker_id=worker_id,
                lease_token=lease_token,
                reason="cancel requested",
            )
            conn.commit()
        return True

    attachment_contract_signal: dict[str, Any] | None = None
    if exec_phase != "wait":
        attachment_contract_signal = detect_missing_attachment_contract(
            kind=str(job.kind or ""),
            input_obj=input_obj,
            params_obj=params_obj,
        )
        if attachment_contract_signal:
            payload = dict(attachment_contract_signal)
            payload["phase"] = exec_phase
            payload["job_kind"] = str(job.kind or "")
            _record_attachment_contract_signal_once(
                cfg=cfg,
                job_id=job.job_id,
                payload=payload,
            )

    # Guardrail: prevent "rescue follow-up" races from creating duplicate user messages.
    #
    # If a follow-up like "继续…不要再写代码…" is submitted while the parent job is about to
    # complete, wait a tiny grace window and, if the parent completes, short-circuit this
    # follow-up to the parent's answer (no new prompt sent).
    if (
        job.kind == "chatgpt_web.ask"
        and exec_phase in {"send", "full"}
        and parent_job_id
        and _truthy_env("CHATGPTREST_RESCUE_FOLLOWUP_GUARD", True)
        and isinstance(input_obj, dict)
        and _looks_like_rescue_followup(str(input_obj.get("question") or ""))
    ):
        with connect(db_path) as conn:
            parent_row = conn.execute(
                "SELECT status, updated_at FROM jobs WHERE job_id = ?",
                (str(parent_job_id),),
            ).fetchone()
        initial_parent_status = str(parent_row["status"] or "").strip().lower() if parent_row is not None else ""
        initial_parent_updated_at = float(parent_row["updated_at"] or 0.0) if parent_row is not None else 0.0
        follow_created_at = float(getattr(job, "created_at", 0.0) or 0.0)
        # Guard two race windows:
        # 1) Parent is still in_progress (classic race).
        # 2) Parent already flipped to completed, but completion happened after this follow-up
        #    was created (startup timing race; still should short-circuit).
        guard_parent_race = initial_parent_status == JobStatus.IN_PROGRESS.value
        if (
            not guard_parent_race
            and initial_parent_status == JobStatus.COMPLETED.value
            and follow_created_at > 0.0
            and initial_parent_updated_at >= follow_created_at
        ):
            guard_parent_race = True
        # If parent completed well before this follow-up was created, treat it as an intentional
        # follow-up and do not short-circuit.
        if guard_parent_race:
            grace_seconds = max(0.0, float(_env_int("CHATGPTREST_RESCUE_FOLLOWUP_GRACE_SECONDS", 3)))
            poll_seconds = 0.25
            deadline = time.time() + grace_seconds
            while True:
                with connect(db_path) as conn:
                    parent_row = conn.execute(
                        "SELECT status, answer_path, answer_format, answer_sha256, answer_chars FROM jobs WHERE job_id = ?",
                        (str(parent_job_id),),
                    ).fetchone()
                if parent_row is not None and str(parent_row["status"] or "").strip().lower() == JobStatus.COMPLETED.value:
                    parent_answer_path = str(parent_row["answer_path"] or "").strip()
                    if parent_answer_path:
                        try:
                            parent_answer = artifacts.resolve_artifact_path(artifacts_dir, parent_answer_path).read_text(
                                encoding="utf-8",
                                errors="replace",
                            )
                        except Exception:
                            parent_answer = ""
                        if parent_answer.strip():
                            payload = {
                                "parent_job_id": parent_job_id,
                                "grace_seconds": grace_seconds,
                                "poll_seconds": poll_seconds,
                                "initial_parent_status": initial_parent_status,
                                "initial_parent_updated_at": initial_parent_updated_at,
                                "follow_created_at": follow_created_at,
                                "parent_answer_path": parent_answer_path,
                                "parent_answer_sha256": (str(parent_row["answer_sha256"] or "").strip() or None),
                                "parent_answer_chars": (
                                    int(parent_row["answer_chars"] or 0) if parent_row["answer_chars"] is not None else None
                                ),
                            }
                            try:
                                with connect(db_path) as conn:
                                    conn.execute("BEGIN IMMEDIATE")
                                    store_answer_result(
                                        conn,
                                        artifacts_dir=artifacts_dir,
                                        job_id=job.job_id,
                                        worker_id=worker_id,
                                        lease_token=lease_token,
                                        answer=parent_answer,
                                        answer_format=str(parent_row["answer_format"] or "text"),
                                    )
                                    insert_event(conn, job_id=job.job_id, type="rescue_followup_shortcircuited", payload=payload)
                                    conn.commit()
                                artifacts.append_event(
                                    artifacts_dir,
                                    job.job_id,
                                    type="rescue_followup_shortcircuited",
                                    payload=payload,
                                )
                                return True
                            except (LeaseLost, AlreadyFinished):
                                return True
                            except Exception:
                                # Fall back to normal execution if the short-circuit path fails.
                                pass
                if time.time() >= deadline:
                    break
                await asyncio.sleep(poll_seconds)

    stop_event = asyncio.Event()
    lease_lost_event = asyncio.Event()
    cancel_event = asyncio.Event()
    heartbeat_task = asyncio.create_task(
        _lease_heartbeat(
            stop_event=stop_event,
            lease_lost_event=lease_lost_event,
            db_path=db_path,
            artifacts_dir=artifacts_dir,
            job_id=job.job_id,
            worker_id=worker_id,
            lease_token=lease_token,
            lease_ttl_seconds=lease_ttl_seconds,
        )
    )
    cancel_watch_task = asyncio.create_task(_cancel_watch(stop_event=stop_event, cancel_event=cancel_event, db_path=db_path, job_id=job.job_id))

    # NOTE: _run_executor_step creates fresh wait-tasks per invocation to avoid
    # stale-done-task issues when the formatting step reuses the closure.
    send_throttle_waited_total = 0.0
    send_throttle_waited = send_throttle_waited_total
    conversation_url = ""
    result = None
    format_prompt = str(params_obj.get("format_prompt") or "").strip()
    format_preset = str(params_obj.get("format_preset") or "thinking_heavy").strip().lower() or "thinking_heavy"
    formatting_applied = False

    async def _run_executor_step(
        *,
        exec_job_id: str,
        step_input: dict[str, Any],
        step_params: dict[str, Any],
        throttle_send: bool,
    ) -> tuple[Any | None, str | None]:
        nonlocal send_throttle_waited
        if throttle_send:
            # Preflight before consuming the send throttle slot: if the driver reports a
            # stop-the-world blocked/cooldown state, avoid reserving (wasting) the interval.
            if job.kind == "chatgpt_web.ask" and isinstance(executor, ChatGPTWebMcpExecutor):
                try:
                    preflight = None
                    if tool_caller is not None:
                        preflight = await asyncio.to_thread(
                            tool_caller.call_tool,
                            tool_name="chatgpt_web_blocked_status",
                            tool_args={},
                            timeout_sec=15.0,
                        )
                    if isinstance(preflight, dict) and bool(preflight.get("blocked")):
                        wait_seconds = float(preflight.get("seconds_until_unblocked") or 0.0)
                        not_before = float(preflight.get("blocked_until") or (time.time() + wait_seconds))
                        reason = str(preflight.get("reason") or "").strip() or "blocked"
                        status = JobStatus.COOLDOWN.value if wait_seconds > 0 else JobStatus.BLOCKED.value
                        return (
                            ExecutorResult(
                                status=status,
                                answer=f"driver blocked: {reason}",
                                meta={
                                    "error_type": "Blocked",
                                    "error": f"driver blocked: {reason}",
                                    "retry_after_seconds": (wait_seconds if wait_seconds > 0 else None),
                                    "not_before": not_before,
                                    "preflight_blocked_status": preflight,
                                },
                            ),
                            None,
                        )
                except Exception:
                    pass
            if job.kind == "chatgpt_web.ask":
                rate_limit_key = "chatgpt_web_send"
            else:
                rate_limit_key = ask_rate_limit_key(job.kind)
            interval = ask_min_prompt_interval_seconds(cfg=cfg, kind=job.kind)
            if rate_limit_key is None:
                rate_limit_key = "chatgpt_web_send"
            interval = max(0, int(interval or 0))
            if job.kind == "chatgpt_web.ask":
                # Fixed-window caps to reduce risk of ChatGPT "unusual activity" cooldowns.
                if int(cfg.chatgpt_max_prompts_per_hour or 0) > 0:
                    send_throttle_waited += await _throttle_sends_fixed_window(
                        cfg=cfg,
                        job_id=job.job_id,
                        rate_limit_key="chatgpt_web_send:hour",
                        window_seconds=3600,
                        max_per_window=int(cfg.chatgpt_max_prompts_per_hour),
                        stop_event=stop_event,
                    )
                if int(cfg.chatgpt_max_prompts_per_day or 0) > 0:
                    send_throttle_waited += await _throttle_sends_fixed_window(
                        cfg=cfg,
                        job_id=job.job_id,
                        rate_limit_key="chatgpt_web_send:day",
                        window_seconds=86400,
                        max_per_window=int(cfg.chatgpt_max_prompts_per_day),
                        stop_event=stop_event,
                    )
            send_throttle_waited += await _throttle_sends(
                cfg=cfg,
                job_id=job.job_id,
                rate_limit_key=rate_limit_key,
                min_interval_seconds=interval,
                stop_event=stop_event,
            )
            if lease_lost_event.is_set():
                return None, "lease_lost"
            if cancel_event.is_set():
                return None, "canceled"

        # Create fresh wait-tasks per invocation so that a previously-done
        # event.wait() task (e.g. from the first executor step) does not cause
        # asyncio.wait to return immediately and mis-detect an abort.
        _ll_task = asyncio.create_task(lease_lost_event.wait())
        _cc_task = asyncio.create_task(cancel_event.wait())

        task = asyncio.create_task(executor.run(job_id=exec_job_id, kind=job.kind, input=step_input, params=step_params))
        done, _pending = await asyncio.wait({task, _ll_task, _cc_task}, return_when=asyncio.FIRST_COMPLETED)

        # Clean up the sentinel tasks we no longer need.
        _ll_task.cancel()
        _cc_task.cancel()

        if lease_lost_event.is_set():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            return None, "lease_lost"
        if cancel_event.is_set():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            return None, "canceled"

        try:
            return task.result(), None
        except Exception as exc:
            raw_error_type = type(exc).__name__
            raw_error = str(exc)
            wait_seconds = _retry_after_seconds_for_error(error_type=raw_error_type, error=raw_error)
            if exec_phase == "wait":
                wait_cu = ""
                if isinstance(step_input, dict):
                    wait_cu = str(step_input.get("conversation_url") or "").strip()
                wait_seconds = _retry_after_seconds_for_wait_phase_error(
                    kind=str(job.kind or ""),
                    conversation_url=(wait_cu or None),
                    error_type=raw_error_type,
                    error=raw_error,
                )
            classified_error_type = raw_error_type
            if _looks_like_infra_error(raw_error_type, raw_error):
                classified_error_type = "InfraError"
            elif _looks_like_ui_transient_error(raw_error_type, raw_error):
                classified_error_type = "UiTransientError"
            meta: dict[str, Any] = {
                "error_type": classified_error_type,
                "error": raw_error,
                "raw_error_type": raw_error_type,
                "retry_after_seconds": wait_seconds,
                "not_before": float(time.time() + wait_seconds),
            }
            if isinstance(step_input, dict):
                cu = str(step_input.get("conversation_url") or "").strip()
                if cu:
                    meta["conversation_url"] = cu
            return ExecutorResult(status=JobStatus.COOLDOWN.value, answer=str(exc), meta=meta), None

    try:
        primary_params = dict(params_obj)
        if is_web_ask_kind(job.kind):
            primary_params["phase"] = exec_phase
            if exec_phase == "wait" and int(getattr(cfg, "wait_slice_seconds", 0) or 0) > 0:
                slice_seconds = int(getattr(cfg, "wait_slice_seconds", 0) or 0)
                # Opt-1: adaptive wait slice — grow slice with each requeue cycle.
                growth = float(getattr(cfg, "wait_slice_growth_factor", 1.0) or 1.0)
                if growth > 1.0:
                    try:
                        with connect(db_path) as _conn_wq:
                            wait_requeue_count = _conn_wq.execute(
                                "SELECT COUNT(*) FROM job_events WHERE job_id = ? AND type = ?",
                                (job.job_id, "wait_requeued"),
                            ).fetchone()[0]
                    except Exception:
                        wait_requeue_count = 0
                    if wait_requeue_count > 0:
                        max_cap = int(primary_params.get("max_wait_seconds") or 1800)
                        slice_seconds = min(
                            int(slice_seconds * (growth ** wait_requeue_count)),
                            max(slice_seconds, max_cap),
                        )
                try:
                    cur_max = int(primary_params.get("max_wait_seconds") or slice_seconds)
                except Exception:
                    cur_max = slice_seconds
                try:
                    cur_wait_timeout = int(primary_params.get("wait_timeout_seconds") or slice_seconds)
                except Exception:
                    cur_wait_timeout = slice_seconds
                primary_params["max_wait_seconds"] = min(cur_max, slice_seconds)
                primary_params["wait_timeout_seconds"] = min(cur_wait_timeout, slice_seconds)

        exec_input = input_obj
        if (
            job.kind == "chatgpt_web.ask"
            and exec_phase in {"send", "full"}
            and isinstance(input_obj, dict)
            and isinstance(input_obj.get("file_paths"), list)
        ):
            raw_paths = [str(p) for p in list(input_obj.get("file_paths") or []) if isinstance(p, str) and str(p).strip()]
            if any(p.lower().endswith(".zip") for p in raw_paths):
                try:
                    new_paths, zip_info = _maybe_expand_zip_attachments_for_chatgpt(
                        artifacts_dir=artifacts_dir,
                        job_id=job.job_id,
                        file_paths=raw_paths,
                    )
                except Exception as exc:
                    new_paths, zip_info = raw_paths, {"ok": False, "reason": "zip_expand_exception", "error": f"{type(exc).__name__}: {exc}"}

                if isinstance(zip_info, dict):
                    ev_type = "zip_attachments_expanded" if bool(zip_info.get("ok")) else "zip_attachments_expand_failed"
                    try:
                        payload = dict(zip_info)
                        payload.setdefault("original_file_paths", [Path(p).name for p in raw_paths if p.lower().endswith(".zip")])
                        with connect(db_path) as conn:
                            conn.execute("BEGIN IMMEDIATE")
                            insert_event(conn, job_id=job.job_id, type=ev_type, payload=payload)
                            conn.commit()
                        artifacts.append_event(artifacts_dir, job.job_id, type=ev_type, payload=payload)
                    except Exception:
                        pass

                if isinstance(zip_info, dict) and bool(zip_info.get("ok")) and new_paths != raw_paths:
                    exec_input = dict(input_obj)
                    exec_input["file_paths"] = list(new_paths)
        _t_executor_start = time.time()
        primary, abort = await _run_executor_step(
            exec_job_id=job.job_id,
            step_input=exec_input,
            step_params=primary_params,
            throttle_send=(is_web_ask_kind(job.kind) and exec_phase in {"send", "full"}),
        )
        _t_executor_end = time.time()
        _executor_elapsed = _t_executor_end - _t_executor_start
        _throttle_elapsed = send_throttle_waited - send_throttle_waited_total
        # Emit timing event for observability
        _timing_payload = {
            "kind": job.kind,
            "phase": exec_phase,
            "provider": provider_id_for_kind(job.kind) or "unknown",
            "queue_wait_s": round(_queue_wait, 1),
            "init_s": round((_t_executor_start - _t_claimed) - _throttle_elapsed, 1),
            "throttle_s": round(_throttle_elapsed, 1),
            "executor_s": round(_executor_elapsed, 1),
            "total_s": round(time.time() - _t_claimed, 1),
            "abort": abort,
        }
        try:
            with connect(db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                insert_event(conn, job_id=job.job_id, type="worker_timing", payload=_timing_payload)
                conn.commit()
            artifacts.append_event(artifacts_dir, job.job_id, type="worker_timing", payload=_timing_payload)
        except Exception:
            pass
        print(
            f"worker_timing: job={job.job_id[:8]} kind={job.kind} phase={exec_phase}"
            f" queue={_queue_wait:.0f}s throttle={_throttle_elapsed:.0f}s"
            f" executor={_executor_elapsed:.0f}s total={time.time() - _t_claimed:.0f}s"
            f" abort={abort}",
            file=sys.stderr, flush=True,
        )
        if abort == "lease_lost":
            return True
        if abort == "canceled":
            with connect(db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                store_canceled_result(
                    conn,
                    artifacts_dir=artifacts_dir,
                    job_id=job.job_id,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    reason="cancel requested",
                )
                conn.commit()
            return True
        result = primary

        # Make per-job artifacts self-contained: copy any driver debug artifacts (png/html/txt)
        # into artifacts/jobs/<job_id>/debug/ so postmortems don't depend on external paths.
        try:
            meta_ref = getattr(result, "meta", None)
            if isinstance(meta_ref, dict):
                _maybe_attach_debug_artifacts(
                    cfg=cfg,
                    db_path=db_path,
                    job_id=job.job_id,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    meta=meta_ref,
                )
                _maybe_attach_generated_images(
                    cfg=cfg,
                    db_path=db_path,
                    job_id=job.job_id,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    meta=meta_ref,
                )
        except Exception:
            pass

        # Persist thinking trace if captured by the driver.
        try:
            meta_ref = getattr(result, "meta", None)
            if isinstance(meta_ref, dict):
                thinking_trace = meta_ref.get("thinking_trace")
                if thinking_trace and isinstance(thinking_trace, dict):
                    from chatgptrest.core.thinking_qa import persist_thinking_trace
                    artifacts_dir = cfg.artifacts_dir if hasattr(cfg, "artifacts_dir") else Path("artifacts")
                    trace_path = persist_thinking_trace(
                        job_id=job.job_id,
                        thinking_trace=thinking_trace,
                        artifacts_dir=artifacts_dir,
                    )
                    _emit_event(
                        db_path=db_path,
                        job_id=job.job_id,
                        worker_id=worker_id,
                        lease_token=lease_token,
                        kind="thinking_trace_captured",
                        payload={
                            "provider": thinking_trace.get("provider", "unknown"),
                            "total_steps": thinking_trace.get("total_steps", 0),
                            "total_content_chars": thinking_trace.get("total_content_chars", 0),
                            "path": str(trace_path),
                        },
                    )
        except Exception:
            pass

        try:
            meta = dict(getattr(result, "meta", None) or {})
            conversation_url = str(meta.get("conversation_url") or "").strip()
        except Exception:
            conversation_url = ""

        stable_conversation_url = conversation_url or str(job.conversation_url or "").strip()

        if conversation_url:
            try:
                with connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    set_conversation_url(
                        conn,
                        artifacts_dir=artifacts_dir,
                        job_id=job.job_id,
                        worker_id=worker_id,
                        lease_token=lease_token,
                        conversation_url=conversation_url,
                    )
                    conn.commit()
            except Exception:
                pass

        status_raw = str(getattr(result, "status", "") or "").strip().lower()
        if (
            job.kind == "chatgpt_web.ask"
            and status_raw == JobStatus.IN_PROGRESS.value
            and stable_conversation_url
            and exec_phase != "send"
        ):
            try:
                await _maybe_export_conversation(
                    cfg=cfg,
                    job_id=job.job_id,
                    conversation_url=stable_conversation_url,
                    tool_caller=tool_caller,
                    cache=_export_cache,
                )
            except Exception:
                pass
            export_path = artifacts_dir / "jobs" / job.job_id / "conversation.json"
            deep_research_requested = bool((params_obj or {}).get("deep_research"))
            thinking_preset_requested = str((params_obj or {}).get("preset") or "").strip().lower() in _THINKING_PRESETS
            export_obj: dict[str, Any] | None = None
            cand = None
            match_info: dict[str, Any] = {}
            export_dom_fallback = False
            if export_path.exists():
                try:
                    parsed = json.loads(export_path.read_text(encoding="utf-8", errors="replace"))
                    export_obj = parsed if isinstance(parsed, dict) else None
                except Exception:
                    export_obj = None

            if export_obj is not None:
                export_dom_fallback = _conversation_export_is_dom_fallback(export_obj)
                cand, match_info = _extract_answer_from_conversation_export_obj(
                    obj=export_obj,
                    question=str(input_obj.get("question") or ""),
                    deep_research=deep_research_requested,
                    allow_fallback_last_assistant=False,
                )

            is_stub, _stub_info = _export_answer_is_connector_tool_call_stub(cand or "")
            is_tool_payload, _tool_payload_info = _looks_like_tool_payload_answer(cand or "")
            # Preamble guard for thinking presets: Pro/thinking often emit a short
            # preamble (93-268 chars) before the real answer. We detect preamble by
            # combining short length AND preamble regex patterns. Length alone
            # would cause false positives on legitimate short answers.
            _PREAMBLE_GUARD_PRESETS_WORKER = {"thinking_extended", "pro_extended", "thinking_heavy"}
            _PREAMBLE_HEURISTIC_RE_WORKER = re.compile(
                r"(?:"
                r"let me (?:plan|think|analyze|outline|break|consider)"
                r"|i'?ll (?:start|begin) by"
                r"|here'?s my (?:plan|approach)"
                r"|step \d+:"
                r"|first,? let me"
                r"|让我先"
                r"|我先规划"
                r")",
                re.IGNORECASE,
            )
            _preset_raw = str((params_obj or {}).get("preset") or "").strip().lower()
            _is_preamble_by_length = (
                _preset_raw in _PREAMBLE_GUARD_PRESETS_WORKER
                and isinstance(cand, str)
                and len(cand.strip()) < 800
                and bool(_PREAMBLE_HEURISTIC_RE_WORKER.search(cand[:500]))
            )
            if (
                cand
                and cand.strip()
                and not is_stub
                and not is_tool_payload
                and not _is_preamble_by_length
                and (not deep_research_requested or _deep_research_export_should_finalize(cand))
            ):
                meta = dict(getattr(result, "meta", None) or {})
                meta["conversation_url"] = stable_conversation_url
                meta["export_path"] = export_path.as_posix()
                meta["export_dom_fallback"] = export_dom_fallback
                if match_info:
                    meta["export_match"] = match_info

                chosen = cand
                chosen_source = "conversation_export"

                # If the export is DOM-derived (often incomplete for long answers),
                # prefer the full answer blob persisted by the driver (answer_id) when available.
                if tool_caller is not None and bool(meta.get("answer_saved")):
                    answer_id = str(meta.get("answer_id") or "").strip().lower()
                    expected_chars = None
                    try:
                        raw_expected = meta.get("answer_chars")
                        if isinstance(raw_expected, int):
                            expected_chars = int(raw_expected)
                        elif isinstance(raw_expected, str) and raw_expected.isdigit():
                            expected_chars = int(raw_expected)
                    except Exception:
                        expected_chars = None

                    try:
                        rehydrated = await _rehydrate_answer_from_answer_id(
                            tool_caller=tool_caller,
                            answer_id=answer_id,
                            expected_chars=expected_chars,
                            timeout_seconds=20.0,
                        )
                    except Exception:
                        rehydrated = None

                    if rehydrated and export_dom_fallback and len(_normalize_text(rehydrated)) > (len(_normalize_text(cand)) + 50):
                        chosen = rehydrated
                        chosen_source = "answer_id"
                    elif rehydrated and _should_prefer_conversation_answer(candidate=rehydrated, current=cand):
                        chosen = rehydrated
                        chosen_source = "answer_id"

                try:
                    payload = {
                        "export_path": export_path.as_posix(),
                        "export_answer_chars": len(cand),
                        "export_dom_fallback": export_dom_fallback,
                        "chosen_source": chosen_source,
                        "chosen_answer_chars": len(chosen),
                        "status_before": status_raw,
                    }
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        ev_type = "answer_completed_from_export" if chosen_source == "conversation_export" else "answer_completed_from_answer_id"
                        insert_event(conn, job_id=job.job_id, type=ev_type, payload=payload)
                        conn.commit()
                    ev_type = "answer_completed_from_export" if chosen_source == "conversation_export" else "answer_completed_from_answer_id"
                    artifacts.append_event(artifacts_dir, job.job_id, type=ev_type, payload=payload)
                except Exception:
                    pass

                result = ExecutorResult(
                    status="completed",
                    answer=chosen,
                    answer_format=str(getattr(result, "answer_format", "") or "text"),
                    meta=meta,
                )
                status_raw = "completed"

        # Completion guardrails:
        # - Deep Research: don't treat short "I'll research / report later" acknowledgements as completed.
        # - min_chars: if the caller explicitly requested a minimum length, do not finalize shorter answers
        #   immediately, but also avoid an infinite wait/requeue loop (fail-open with warnings after stalls/caps).
        if job.kind == "chatgpt_web.ask" and status_raw == JobStatus.COMPLETED.value:
            deep_research_requested = bool((params_obj or {}).get("deep_research"))
            thinking_preset_requested = str((params_obj or {}).get("preset") or "").strip().lower() in _THINKING_PRESETS
            answer_text = str(getattr(result, "answer", "") or "")
            trimmed_answer = answer_text.strip()
            question_text = str(input_obj.get("question") or "")

            min_chars_required = 0
            try:
                min_chars_required = max(0, int((params_obj or {}).get("min_chars") or 0))
            except Exception:
                min_chars_required = 0

            downgrade_reason = None
            export_guard_info: dict[str, Any] | None = None
            tool_payload_info: dict[str, Any] | None = None

            # P0 guard: never finalize connector tool-call stubs (e.g. Adobe Acrobat OAuth flows).
            stub, stub_info = _export_answer_is_connector_tool_call_stub(trimmed_answer)
            if stub:
                try:
                    payload = {
                        "reason": "connector_tool_call_stub",
                        "answer_chars": len(trimmed_answer),
                        "deep_research": bool(deep_research_requested),
                        **(stub_info or {}),
                    }
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        exists = conn.execute(
                            "SELECT 1 FROM job_events WHERE job_id = ? AND type = ? LIMIT 1",
                            (job.job_id, "connector_tool_call_detected"),
                        ).fetchone()
                        if exists is None:
                            insert_event(conn, job_id=job.job_id, type="connector_tool_call_detected", payload=payload)
                        conn.commit()
                    artifacts.append_event(artifacts_dir, job.job_id, type="connector_tool_call_detected", payload=payload)
                except Exception:
                    pass

                meta = dict(getattr(result, "meta", None) or {})
                meta["error_type"] = "ConnectorLoginRequired"
                meta["error"] = (
                    "Detected a connector/tool login flow in the assistant output (tool-call stub) "
                    f"instead of answer content. Common cause: uploading .zip triggers Adobe Acrobat and requires OAuth. "
                    f"connector_path={str(stub_info.get('path') or '')!r}"
                )
                meta.setdefault("not_before", float(time.time()))
                # Keep the raw stub in meta for debugging (do not store as an answer artifact).
                meta.setdefault("connector_tool_call", dict(stub_info or {}))
                result = ExecutorResult(
                    status=JobStatus.BLOCKED.value,
                    answer=answer_text,
                    answer_format=str(getattr(result, "answer_format", "") or "text"),
                    meta=meta,
                )
                status_raw = JobStatus.BLOCKED.value

            # P0 guard: avoid finalizing a follow-up as "completed" when the conversation export
            # shows the matched user message but no assistant reply after it yet.
            if stable_conversation_url and tool_caller is not None and exec_phase != "send":
                try:
                    await _maybe_export_conversation(
                        cfg=cfg,
                        job_id=job.job_id,
                        conversation_url=stable_conversation_url,
                        tool_caller=tool_caller,
                        # Completion-time export: bypass OK cooldown (still respects failure backoff).
                        force=True,
                        cache=_export_cache,
                    )
                except Exception:
                    pass

            export_path = artifacts_dir / "jobs" / job.job_id / "conversation.json"
            export_obj: dict[str, Any] | None = None
            if export_path.exists():
                try:
                    raw_export = json.loads(export_path.read_text(encoding="utf-8", errors="replace"))
                    export_obj = raw_export if isinstance(raw_export, dict) else None
                except Exception:
                    export_obj = None

            if export_obj is not None:
                export_answer, export_info = _extract_answer_from_conversation_export_obj(
                    obj=export_obj,
                    question=question_text,
                    deep_research=deep_research_requested,
                    allow_fallback_last_assistant=False,
                )
                export_guard_info = dict(export_info or {})
                export_guard_info["export_path"] = export_path.as_posix()
                export_guard_info["export_answer_chars"] = (len(export_answer) if export_answer else 0)

                matched = bool(export_guard_info.get("matched"))
                export_answer_text = str(export_answer or "")

                if matched and not export_answer_text.strip():
                    # Common race: the DOM answer is present but the export endpoint lags and
                    # returns a window with the user message but no assistant reply. Retry a
                    # couple times *immediately* to avoid long requeue loops.
                    if stable_conversation_url and tool_caller is not None and exec_phase != "send":
                        try:
                            retries = _env_registry.get_int("CHATGPTREST_EXPORT_MISSING_REPLY_RETRIES") or 2
                        except Exception:
                            retries = 2
                        try:
                            sleep_s = float(
                                _env_registry.get_int("CHATGPTREST_EXPORT_MISSING_REPLY_RETRY_SLEEP_SECONDS") or 3
                            )
                        except Exception:
                            sleep_s = 3.0
                        retries = max(0, min(int(retries), 4))
                        sleep_s = max(0.5, min(float(sleep_s), 15.0))

                        for attempt in range(retries):
                            await asyncio.sleep(sleep_s)
                            try:
                                await _maybe_export_conversation(
                                    cfg=cfg,
                                    job_id=job.job_id,
                                    conversation_url=stable_conversation_url,
                                    tool_caller=tool_caller,
                                    force=True,
                                    cache=_export_cache,
                                )
                            except Exception:
                                pass

                            export_obj_retry: dict[str, Any] | None = None
                            if export_path.exists():
                                try:
                                    raw_export = json.loads(export_path.read_text(encoding="utf-8", errors="replace"))
                                    export_obj_retry = raw_export if isinstance(raw_export, dict) else None
                                except Exception:
                                    export_obj_retry = None
                            if export_obj_retry is None:
                                continue

                            export_answer_retry, export_info_retry = _extract_answer_from_conversation_export_obj(
                                obj=export_obj_retry,
                                question=question_text,
                                deep_research=deep_research_requested,
                                allow_fallback_last_assistant=False,
                            )
                            if export_info_retry:
                                export_guard_info = dict(export_info_retry)
                                export_guard_info["export_path"] = export_path.as_posix()
                                export_guard_info["export_answer_chars"] = (
                                    len(export_answer_retry) if export_answer_retry else 0
                                )
                                export_guard_info["completion_retry_attempts"] = int(attempt + 1)
                            export_answer_text = str(export_answer_retry or "")
                            if export_answer_text.strip():
                                export_answer = export_answer_text
                                export_obj = export_obj_retry
                                break

                matched = bool(export_guard_info.get("matched"))
                export_answer_text = str(export_answer or "")

                if matched and not export_answer_text.strip():
                    should_downgrade, warn_info = _should_downgrade_when_export_missing_reply(
                        current_answer=trimmed_answer,
                        min_chars_required=min_chars_required,
                    )
                    if should_downgrade:
                        downgrade_reason = "conversation_export_missing_reply"
                    else:
                        # Export lag is common on long threads / Deep Research embedded reports. Avoid
                        # requeue loops when we already have a substantial DOM answer.
                        meta = dict(getattr(result, "meta", None) or {})
                        meta.setdefault("export_path", export_path.as_posix())
                        meta.setdefault("export_answer_source", export_guard_info.get("answer_source"))
                        meta["export_missing_reply"] = {
                            "action": "ignored",
                            **(warn_info if isinstance(warn_info, dict) else {}),
                        }
                        result = ExecutorResult(
                            status=str(getattr(result, "status", "") or JobStatus.COMPLETED.value),
                            answer=answer_text,
                            answer_format=str(getattr(result, "answer_format", "") or "text"),
                            meta=meta,
                        )
                        try:
                            payload = {
                                "reason": "conversation_export_missing_reply_ignored",
                                "export_path": export_path.as_posix(),
                                **(warn_info if isinstance(warn_info, dict) else {}),
                            }
                            if export_guard_info:
                                payload["export_guard"] = {
                                    "match_kind": export_guard_info.get("match_kind"),
                                    "match_strength": export_guard_info.get("match_strength"),
                                    "matched_user_index": export_guard_info.get("matched_user_index"),
                                    "export_messages_len": export_guard_info.get("export_messages_len"),
                                    "export_last_role": export_guard_info.get("export_last_role"),
                                    "completion_retry_attempts": export_guard_info.get("completion_retry_attempts"),
                                }
                            with connect(db_path) as conn:
                                conn.execute("BEGIN IMMEDIATE")
                                insert_event(
                                    conn,
                                    job_id=job.job_id,
                                    type="conversation_export_missing_reply_ignored",
                                    payload=payload,
                                )
                                conn.commit()
                            artifacts.append_event(
                                artifacts_dir,
                                job.job_id,
                                type="conversation_export_missing_reply_ignored",
                                payload=payload,
                            )
                        except Exception:
                            pass
                elif matched and export_answer_text.strip():
                    export_dom_fallback = _conversation_export_is_dom_fallback(export_obj) if export_obj is not None else False
                    did_override = False

                    # Deep Research: prefer the backend export when it preserves substantially more Markdown
                    # structure than the driver-extracted (DOM) answer.
                    if (
                        (not stub)
                        and deep_research_requested
                        and str(getattr(result, "answer_format", "") or "").strip().lower() == "markdown"
                    ):
                        try:
                            should_override, override_info = _deep_research_should_override_answer_with_export(
                                current_answer=trimmed_answer,
                                export_answer=export_answer_text,
                                export_dom_fallback=export_dom_fallback,
                            )
                        except Exception:
                            should_override, override_info = False, {"reason": "override_check_error"}
                        if should_override:
                            meta = dict(getattr(result, "meta", None) or {})
                            meta["export_path"] = export_path.as_posix()
                            meta["export_answer_source"] = export_guard_info.get("answer_source")
                            meta["export_dom_fallback"] = export_dom_fallback
                            meta["export_answer_chars"] = len(str(export_answer))
                            meta["export_markdown_override"] = override_info
                            result = ExecutorResult(
                                status=JobStatus.COMPLETED.value,
                                answer=str(export_answer),
                                answer_format="markdown",
                                meta=meta,
                            )
                            answer_text = str(export_answer)
                            trimmed_answer = answer_text.strip()
                            did_override = True
                            try:
                                payload = {
                                    "reason": "deep_research_export_has_more_markdown_structure",
                                    "export_path": export_path.as_posix(),
                                    "export_dom_fallback": export_dom_fallback,
                                    "export_answer_chars": len(str(export_answer)),
                                    **(override_info if isinstance(override_info, dict) else {}),
                                }
                                with connect(db_path) as conn:
                                    conn.execute("BEGIN IMMEDIATE")
                                    insert_event(
                                        conn,
                                        job_id=job.job_id,
                                        type="answer_overridden_from_export",
                                        payload=payload,
                                    )
                                    conn.commit()
                                artifacts.append_event(
                                    artifacts_dir,
                                    job.job_id,
                                    type="answer_overridden_from_export",
                                    payload=payload,
                                )
                            except Exception:
                                pass

                    # If the driver answered with a previous assistant message (common follow-up mis-detection),
                    # overwrite it with the export-anchored reply for this question.
                    if did_override:
                        pass
                    else:
                        try:
                            matched_idx = export_guard_info.get("matched_user_index")
                            msgs = _conversation_export_messages(
                                export_obj,
                                include_roles={"user", "assistant"},
                                include_hidden=False,
                            )
                            raw_norm = _normalize_text(trimmed_answer)
                            matched_old = False
                            if isinstance(matched_idx, int) and matched_idx > 0 and raw_norm:
                                for m in msgs[:matched_idx]:
                                    if not isinstance(m, dict):
                                        continue
                                    if str(m.get("role") or "").strip().lower() != "assistant":
                                        continue
                                    prev_norm = _normalize_text(str(m.get("text") or ""))
                                    if not prev_norm:
                                        continue
                                    if raw_norm == prev_norm:
                                        matched_old = True
                                        break
                                    if len(raw_norm) >= 200 and raw_norm in prev_norm:
                                        matched_old = True
                                        break
                                    if len(prev_norm) >= 200 and prev_norm in raw_norm:
                                        matched_old = True
                                        break
                                    if _common_prefix_len(prev_norm, raw_norm, 400) >= 200:
                                        matched_old = True
                                        break
                            # Also detect when the driver echoed part of the question text
                            # (common in follow-up scenarios where the driver picks up the
                            # user prompt instead of the assistant reply).
                            if not matched_old and raw_norm and len(raw_norm) >= 20:
                                question_norm = _normalize_text(question_text)
                                if question_norm and raw_norm in question_norm:
                                    matched_old = True
                            if matched_old and (not stub):
                                meta = dict(getattr(result, "meta", None) or {})
                                meta["export_path"] = export_path.as_posix()
                                meta["export_answer_source"] = export_guard_info.get("answer_source")
                                meta["export_answer_chars"] = len(str(export_answer))
                                result = ExecutorResult(
                                    status=JobStatus.COMPLETED.value,
                                    answer=str(export_answer),
                                    answer_format=str(getattr(result, "answer_format", "") or "text"),
                                    meta=meta,
                                )
                                answer_text = str(export_answer)
                                trimmed_answer = answer_text.strip()
                                try:
                                    payload = {
                                        "reason": "driver_answer_looked_like_previous_assistant_turn",
                                        "export_path": export_path.as_posix(),
                                        "export_answer_chars": len(str(export_answer)),
                                        "matched_user_index": matched_idx,
                                    }
                                    with connect(db_path) as conn:
                                        conn.execute("BEGIN IMMEDIATE")
                                        insert_event(
                                            conn,
                                            job_id=job.job_id,
                                            type="answer_overridden_from_export",
                                            payload=payload,
                                        )
                                        conn.commit()
                                    artifacts.append_event(
                                        artifacts_dir,
                                        job.job_id,
                                        type="answer_overridden_from_export",
                                        payload=payload,
                                    )
                                except Exception:
                                    pass
                        except Exception:
                            pass

            if downgrade_reason is None and deep_research_requested and _deep_research_is_ack(trimmed_answer):
                downgrade_reason = "deep_research_ack"
            # Deep Research can surface an embedded-app "implicit_link" tool-call stub as the assistant
            # message. This is not the final report content; keep waiting instead of finalizing.
            if downgrade_reason is None and deep_research_requested and (not _deep_research_export_should_finalize(trimmed_answer)):
                downgrade_reason = "deep_research_not_final"
            if downgrade_reason is None:
                is_tool_payload, tool_payload_info = _looks_like_tool_payload_answer(trimmed_answer)
                if is_tool_payload:
                    downgrade_reason = "tool_payload_not_final"
            # P0 answer quality guard: use classify_answer_quality() as a blocking guard,
            # not just observability. Catches single-char bogus completions (#101),
            # preamble-only answers (P0 #1), and meta-commentary (P0 #2).
            if downgrade_reason is None:
                _aq_quality = _classify_answer_quality(
                    trimmed_answer,
                    answer_chars=len(trimmed_answer),
                )
                if _aq_quality != "final":
                    downgrade_reason = f"answer_quality_{_aq_quality}"
            if downgrade_reason is None and min_chars_required > 0 and len(trimmed_answer) < min_chars_required:
                should_complete, details = False, {}
                try:
                    with connect(db_path) as conn:
                        should_complete, details = _min_chars_guard_should_complete_under_min_chars(
                            conn=conn,
                            job_id=job.job_id,
                            answer_chars=len(trimmed_answer),
                            min_chars_required=min_chars_required,
                            deep_research=bool(deep_research_requested),
                            thinking_preset=bool(thinking_preset_requested),
                            semantically_final=(_aq_quality == "final"),
                        )
                except Exception:
                    should_complete, details = False, {}

                if should_complete and (not stub):
                    try:
                        payload = {
                            "reason": "answer_too_short_for_min_chars",
                            "action": "completed_under_min_chars",
                            **details,
                        }
                        with connect(db_path) as conn:
                            conn.execute("BEGIN IMMEDIATE")
                            insert_event(
                                conn,
                                job_id=job.job_id,
                                type="completion_guard_completed_under_min_chars",
                                payload=payload,
                            )
                            conn.commit()
                        artifacts.append_event(
                            artifacts_dir,
                            job.job_id,
                            type="completion_guard_completed_under_min_chars",
                            payload=payload,
                        )
                    except Exception:
                        pass

                    meta = dict(getattr(result, "meta", None) or {})
                    meta["completion_guard"] = {
                        "type": "min_chars",
                        "action": "completed_under_min_chars",
                        **details,
                    }
                    meta["min_chars_required"] = min_chars_required
                    meta["min_chars_met"] = False
                    result = ExecutorResult(
                        status=JobStatus.COMPLETED.value,
                        answer=answer_text,
                        answer_format=str(getattr(result, "answer_format", "") or "text"),
                        meta=meta,
                    )
                    status_raw = JobStatus.COMPLETED.value
                else:
                    downgrade_reason = "answer_too_short_for_min_chars"

            if downgrade_reason and (not stub):
                should_regenerate_same_turn = bool(
                    thinking_preset_requested
                    and conversation_url
                    and downgrade_reason
                    in {
                        "answer_quality_suspect_short_answer",
                        "answer_quality_suspect_meta_commentary",
                        "answer_quality_suspect_context_acquisition_failure",
                    }
                )
                try:
                    payload = {
                        "reason": downgrade_reason,
                        "answer_chars": len(trimmed_answer),
                        "min_chars_required": (min_chars_required if min_chars_required > 0 else None),
                        "deep_research": bool(deep_research_requested),
                        "answer_preview": trimmed_answer[:200],
                    }
                    if should_regenerate_same_turn:
                        payload["action"] = "needs_followup_regenerate"
                    if export_guard_info:
                        payload["export_guard"] = export_guard_info
                    if downgrade_reason == "tool_payload_not_final" and tool_payload_info:
                        payload["tool_payload"] = dict(tool_payload_info)
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        insert_event(conn, job_id=job.job_id, type="completion_guard_downgraded", payload=payload)
                        conn.commit()
                    artifacts.append_event(artifacts_dir, job.job_id, type="completion_guard_downgraded", payload=payload)
                except Exception:
                    pass

                meta = dict(getattr(result, "meta", None) or {})
                retry_after = _completion_guard_retry_after_seconds()
                if should_regenerate_same_turn:
                    retry_after = max(15, min(int(retry_after), 60))
                    meta["error_type"] = "ProInstantAnswerNeedsRegenerate"
                    meta["error"] = (
                        f"thinking preset produced a suspicious fast answer ({downgrade_reason}); "
                        "request regenerate on the same conversation"
                    )
                    meta["retry_after_seconds"] = retry_after
                    meta["not_before"] = float(time.time() + float(retry_after))
                    meta.setdefault("completion_guard", {})
                    try:
                        meta["completion_guard"] = dict(meta.get("completion_guard") or {})
                    except Exception:
                        meta["completion_guard"] = {}
                    meta["completion_guard"].update(
                        {
                            "type": "answer_quality",
                            "action": "needs_followup_regenerate",
                            "reason": downgrade_reason,
                        }
                    )
                    result = ExecutorResult(
                        status=JobStatus.NEEDS_FOLLOWUP.value,
                        answer=answer_text,
                        answer_format=str(getattr(result, "answer_format", "") or "text"),
                        meta=meta,
                    )
                    status_raw = JobStatus.NEEDS_FOLLOWUP.value
                else:
                    meta.setdefault("error_type", "InProgress")
                    if downgrade_reason == "deep_research_ack":
                        meta.setdefault("error", "deep research acknowledgement received; waiting for full report")
                    elif downgrade_reason == "deep_research_not_final":
                        meta.setdefault("error", "deep research stub observed (implicit_link/tool call); waiting for full report")
                    elif downgrade_reason == "conversation_export_missing_reply":
                        meta.setdefault(
                            "error",
                            "conversation export matched the user prompt but no assistant reply is present yet; waiting",
                        )
                    elif downgrade_reason == "tool_payload_not_final":
                        meta.setdefault(
                            "error",
                            "assistant output looks like a search/tool payload JSON instead of final answer text; waiting",
                        )
                    elif downgrade_reason and downgrade_reason.startswith("answer_quality_"):
                        meta.setdefault(
                            "error",
                            f"answer quality classified as {downgrade_reason} (len={len(trimmed_answer)}); waiting for final answer",
                        )
                    else:
                        meta.setdefault(
                            "error",
                            f"answer too short (len={len(trimmed_answer)}) for min_chars={min_chars_required}; waiting",
                        )
                    meta.setdefault("retry_after_seconds", retry_after)
                    meta.setdefault("not_before", float(time.time() + float(retry_after)))
                    result = ExecutorResult(
                        status=JobStatus.IN_PROGRESS.value,
                        answer=answer_text,
                        answer_format=str(getattr(result, "answer_format", "") or "text"),
                        meta=meta,
                    )
                    status_raw = JobStatus.IN_PROGRESS.value

        # Thinking-time quality guard markers (from executor/driver). This is a pure observability hook:
        # it does not send new prompts. Side-effectful repairs (refresh/regenerate) are handled inside
        # the driver/executor behind explicit guardrails.
        try:
            meta_ref = getattr(result, "meta", None)
            if isinstance(meta_ref, dict):
                tg = meta_ref.get("_thought_guard")
                if isinstance(tg, dict) and bool(tg.get("enabled")):
                    action = str(tg.get("action") or "").strip().lower()
                    event_type = "thought_guard_regenerated" if action == "regenerated" else "thought_guard_abnormal"
                    payload = {
                        "action": (action or None),
                        "thought_seconds": tg.get("thought_seconds"),
                        "min_seconds": tg.get("min_seconds"),
                        "thought_for_present": tg.get("thought_for_present"),
                        "reason": tg.get("reason"),
                        "skipping": tg.get("skipping"),
                        "answer_now_visible": tg.get("answer_now_visible"),
                        "require_thought_for": tg.get("require_thought_for"),
                        "trigger_too_short": tg.get("trigger_too_short"),
                        "trigger_skipping": tg.get("trigger_skipping"),
                        "trigger_answer_now": tg.get("trigger_answer_now"),
                        "missing_observation": tg.get("missing_observation"),
                    }
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        insert_event(conn, job_id=job.job_id, type=event_type, payload=payload)
                        conn.commit()
                    artifacts.append_event(artifacts_dir, job.job_id, type=event_type, payload=payload)
        except Exception:
            pass

        # Answer quality guard markers (sanitization / semantic risk).
        try:
            meta_ref = getattr(result, "meta", None)
            if isinstance(meta_ref, dict):
                aq = meta_ref.get("answer_quality_guard")
                if isinstance(aq, dict) and bool(aq.get("enabled")):
                    common_payload = {
                        "action": aq.get("action"),
                        "preset": aq.get("preset"),
                        "deep_research": aq.get("deep_research"),
                        "ui_noise_detected": aq.get("ui_noise_detected"),
                        "ui_noise_sanitized": aq.get("ui_noise_sanitized"),
                        "ui_noise_prefix_lines": aq.get("ui_noise_prefix_lines"),
                        "semantic_risk_next_owner_mixed": aq.get("semantic_risk_next_owner_mixed"),
                        "answer_chars_before": aq.get("answer_chars_before"),
                        "answer_chars_after": aq.get("answer_chars_after"),
                        "status_override": aq.get("status_override"),
                    }
                    if aq.get("ui_noise_prefix_preview"):
                        common_payload["ui_noise_prefix_preview"] = aq.get("ui_noise_prefix_preview")

                    event_types: list[str] = []
                    if bool(aq.get("ui_noise_sanitized")):
                        event_types.append("answer_quality_sanitized")
                    elif bool(aq.get("ui_noise_detected")):
                        event_types.append("answer_quality_detected")
                    if bool(aq.get("semantic_risk_next_owner_mixed")):
                        event_types.append("answer_semantic_risk_detected")

                    if event_types:
                        with connect(db_path) as conn:
                            conn.execute("BEGIN IMMEDIATE")
                            for event_type in event_types:
                                insert_event(conn, job_id=job.job_id, type=event_type, payload=common_payload)
                            conn.commit()
                        for event_type in event_types:
                            artifacts.append_event(artifacts_dir, job.job_id, type=event_type, payload=common_payload)
        except Exception:
            pass

        # Optional: format the answer in a follow-up turn using a different preset (best-effort).
        if (
            job.kind == "chatgpt_web.ask"
            and format_prompt
            and getattr(result, "status", None) == "completed"
            and conversation_url
        ):
            raw_meta = None
            try:
                raw_meta = artifacts.write_answer_raw(
                    artifacts_dir,
                    job.job_id,
                    answer=str(getattr(result, "answer", "") or ""),
                    answer_format=str(getattr(result, "answer_format", "text") or "text"),
                )
                payload = {
                    "format_preset": format_preset,
                    "raw_path": raw_meta.answer_path,
                    "raw_sha256": raw_meta.answer_sha256,
                    "raw_chars": raw_meta.answer_chars,
                    "raw_format": raw_meta.answer_format,
                    "format_prompt_chars": len(format_prompt),
                    "format_prompt_preview": format_prompt[:200],
                }
                with connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    insert_event(conn, job_id=job.job_id, type="formatting_raw_saved", payload=payload)
                    conn.commit()
                artifacts.append_event(artifacts_dir, job.job_id, type="formatting_raw_saved", payload=payload)
            except Exception:
                raw_meta = None

            fmt_input: dict[str, Any] = {"question": format_prompt, "conversation_url": conversation_url}
            fmt_params: dict[str, Any] = dict(params_obj)
            fmt_params["preset"] = format_preset
            fmt_params.setdefault("min_chars", 200)
            fmt_params.setdefault("answer_format", "markdown")
            fmt_params["deep_research"] = False
            fmt_params["web_search"] = False
            fmt_params["agent_mode"] = False
            fmt_params["phase"] = "full"

            try:
                with connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    insert_event(conn, job_id=job.job_id, type="formatting_started", payload={"preset": format_preset})
                    conn.commit()
                artifacts.append_event(artifacts_dir, job.job_id, type="formatting_started", payload={"preset": format_preset})
            except Exception:
                pass

            formatted, abort2 = await _run_executor_step(
                exec_job_id=f"{job.job_id}:format",
                step_input=fmt_input,
                step_params=fmt_params,
                throttle_send=True,
            )
            if abort2 == "lease_lost":
                return True
            if abort2 == "canceled":
                with connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    store_canceled_result(
                        conn,
                        artifacts_dir=artifacts_dir,
                        job_id=job.job_id,
                        worker_id=worker_id,
                        lease_token=lease_token,
                        reason="cancel requested",
                    )
                    conn.commit()
                return True

            if formatted is not None and getattr(formatted, "status", None) == "completed":
                result = formatted
                formatting_applied = True
                try:
                    meta2 = dict(getattr(result, "meta", None) or {})
                    conversation_url2 = str(meta2.get("conversation_url") or "").strip()
                    if conversation_url2:
                        conversation_url = conversation_url2
                        with connect(db_path) as conn:
                            conn.execute("BEGIN IMMEDIATE")
                            set_conversation_url(
                                conn,
                                artifacts_dir=artifacts_dir,
                                job_id=job.job_id,
                                worker_id=worker_id,
                                lease_token=lease_token,
                                conversation_url=conversation_url,
                            )
                            conn.commit()
                except Exception:
                    pass

                try:
                    payload = {
                        "preset": format_preset,
                        "answer_chars": len(str(getattr(result, "answer", "") or "")),
                        "answer_format": str(getattr(result, "answer_format", "") or ""),
                    }
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        insert_event(conn, job_id=job.job_id, type="formatting_completed", payload=payload)
                        conn.commit()
                    artifacts.append_event(artifacts_dir, job.job_id, type="formatting_completed", payload=payload)
                except Exception:
                    pass
            else:
                try:
                    payload = {
                        "preset": format_preset,
                        "status": (getattr(formatted, "status", None) if formatted is not None else None),
                        "error": (str(getattr(formatted, "answer", "") or "")[:500] if formatted is not None else None),
                    }
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        insert_event(conn, job_id=job.job_id, type="formatting_failed", payload=payload)
                        conn.commit()
                    artifacts.append_event(artifacts_dir, job.job_id, type="formatting_failed", payload=payload)
                except Exception:
                    pass

        # Persist run metadata for diagnostics (keep long answer out).
        try:
            meta_payload = dict(getattr(result, "meta", None) or {})
            meta_payload.pop("answer", None)
            meta_payload["job_id"] = job.job_id
            meta_payload["job_kind"] = job.kind
            meta_payload["worker_id"] = worker_id
            meta_payload["worker_role"] = role
            meta_payload["job_phase"] = job_phase
            meta_payload["exec_phase"] = exec_phase
            meta_payload["send_throttle_wait_seconds"] = round(float(send_throttle_waited), 3)
            meta_payload["formatting_applied"] = bool(formatting_applied)
            meta_payload["format_preset"] = (format_preset if format_prompt else None)
            meta_payload["format_prompt_chars"] = (len(format_prompt) if format_prompt else 0)

            if job.kind == "chatgpt_web.ask":
                export_path = artifacts_dir / "jobs" / job.job_id / "conversation.json"
                if export_path.exists():
                    export_info = _extract_export_model_info_from_conversation_export(export_path=export_path)
                    if export_info:
                        for k, v in export_info.items():
                            meta_payload.setdefault(k, v)

            # Lightweight "send-stage" markers for operators (easier than parsing run_meta.json).
            if job.kind == "chatgpt_web.ask":
                run_id = str(meta_payload.get("run_id") or "").strip() or None
                markers: list[tuple[str, dict[str, Any]]] = []
                if _debug_timeline_has_phase(meta_payload, "sent"):
                    markers.append(
                        (
                            "prompt_sent",
                            {"run_id": run_id, "t": _debug_timeline_first_t(meta_payload, "sent")},
                        )
                    )
                if _debug_timeline_has_phase(meta_payload, "duplicate_prompt_guard_skip_send"):
                    markers.append(
                        (
                            "prompt_send_skipped_duplicate",
                            {"run_id": run_id, "t": _debug_timeline_first_t(meta_payload, "duplicate_prompt_guard_skip_send")},
                        )
                    )
                if _debug_timeline_has_phase(meta_payload, "answer_ready"):
                    markers.append(
                        (
                            "assistant_answer_ready",
                            {"run_id": run_id, "t": _debug_timeline_first_t(meta_payload, "answer_ready")},
                        )
                    )
                if markers:
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        for ev_type, payload in markers:
                            exists = conn.execute(
                                "SELECT 1 FROM job_events WHERE job_id = ? AND type = ? LIMIT 1",
                                (job.job_id, ev_type),
                            ).fetchone()
                            if exists is None:
                                insert_event(conn, job_id=job.job_id, type=ev_type, payload=payload)
                        conn.commit()
                    for ev_type, payload in markers:
                        try:
                            artifacts.append_event(artifacts_dir, job.job_id, type=ev_type, payload=payload)
                        except Exception:
                            pass
                # Persist model/thinking signals once for easier monitoring.
                model_payload: dict[str, Any] = {}
                for k in (
                    "model_text",
                    "thinking_time",
                    "thinking_time_requested",
                    "export_conversation_id",
                    "export_default_model_slug",
                    "export_last_assistant_model_slug",
                    "export_last_assistant_thinking_effort",
                    "export_last_assistant_finish_type",
                    "export_last_assistant_is_complete",
                ):
                    if k in meta_payload:
                        model_payload[k] = meta_payload.get(k)
                if model_payload:
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        exists = conn.execute(
                            "SELECT 1 FROM job_events WHERE job_id = ? AND type = ? LIMIT 1",
                            (job.job_id, "model_observed"),
                        ).fetchone()
                        if exists is None:
                            insert_event(conn, job_id=job.job_id, type="model_observed", payload=model_payload)
                        conn.commit()
                    try:
                        artifacts.append_event(artifacts_dir, job.job_id, type="model_observed", payload=model_payload)
                    except Exception:
                        pass
                export_keys = {
                    "export_conversation_id",
                    "export_default_model_slug",
                    "export_last_assistant_model_slug",
                    "export_last_assistant_thinking_effort",
                    "export_last_assistant_finish_type",
                    "export_last_assistant_is_complete",
                }
                if any((k in model_payload and model_payload.get(k) is not None) for k in export_keys):
                    export_payload: dict[str, Any] = {k: model_payload.get(k) for k in export_keys if k in model_payload}
                    export_payload.setdefault("run_id", run_id)
                    export_payload.setdefault("model_text", model_payload.get("model_text"))
                    export_payload.setdefault("thinking_time", model_payload.get("thinking_time"))
                    export_payload.setdefault("thinking_time_requested", model_payload.get("thinking_time_requested"))
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        exists = conn.execute(
                            "SELECT 1 FROM job_events WHERE job_id = ? AND type = ? LIMIT 1",
                            (job.job_id, "model_observed_export"),
                        ).fetchone()
                        if exists is None:
                            insert_event(conn, job_id=job.job_id, type="model_observed_export", payload=export_payload)
                        conn.commit()
                    try:
                        artifacts.append_event(artifacts_dir, job.job_id, type="model_observed_export", payload=export_payload)
                    except Exception:
                        pass
                # Persist lightweight DOM risk-control observations (e.g. unusual activity banner) for monitoring.
                try:
                    dom_obs = meta_payload.get("dom_risk_observation")
                    if isinstance(dom_obs, dict) and dom_obs.get("signals"):
                        dom_payload: dict[str, Any] = dict(dom_obs)
                        dom_payload.setdefault("run_id", run_id)
                        with connect(db_path) as conn:
                            conn.execute("BEGIN IMMEDIATE")
                            exists = conn.execute(
                                "SELECT 1 FROM job_events WHERE job_id = ? AND type = ? LIMIT 1",
                                (job.job_id, "dom_risk_observed"),
                            ).fetchone()
                            if exists is None:
                                insert_event(conn, job_id=job.job_id, type="dom_risk_observed", payload=dom_payload)
                            conn.commit()
                        try:
                            artifacts.append_event(artifacts_dir, job.job_id, type="dom_risk_observed", payload=dom_payload)
                        except Exception:
                            pass
                except Exception:
                    pass

            artifacts.write_run_meta(artifacts_dir, job.job_id, meta_payload)
        except Exception:
            pass

        # Persist final job state + answer/result artifacts.
        if getattr(result, "status", None) == "completed":
            if job.kind == "chatgpt_web.conversation_export":
                meta_ref = getattr(result, "meta", None)
                meta = dict(meta_ref) if isinstance(meta_ref, dict) else {}
                src = str(meta.get("export_path") or "").strip()
                if not src:
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        try:
                            store_error_result(
                                conn,
                                artifacts_dir=artifacts_dir,
                                job_id=job.job_id,
                                worker_id=worker_id,
                                lease_token=lease_token,
                                error_type=str(meta.get("error_type") or "ConversationExportFailed"),
                                error="conversation export completed without export_path",
                                status=JobStatus.ERROR,
                            )
                            conn.commit()
                        except (LeaseLost, AlreadyFinished):
                            conn.rollback()
                    return True

                try:
                    export_meta = artifacts.write_conversation_export_from_file(
                        artifacts_dir,
                        job.job_id,
                        src_path=Path(src),
                    )
                except Exception as exc:
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        try:
                            store_error_result(
                                conn,
                                artifacts_dir=artifacts_dir,
                                job_id=job.job_id,
                                worker_id=worker_id,
                                lease_token=lease_token,
                                error_type=type(exc).__name__,
                                error=f"conversation export copy failed: {exc}",
                                status=JobStatus.ERROR,
                            )
                            conn.commit()
                        except (LeaseLost, AlreadyFinished):
                            conn.rollback()
                    return True

                try:
                    with connect(db_path) as conn:
                        conn.execute("BEGIN IMMEDIATE")
                        store_conversation_export_result(
                            conn,
                            artifacts_dir=artifacts_dir,
                            job_id=job.job_id,
                            conversation_export_path=export_meta.conversation_export_path,
                            conversation_export_sha256=export_meta.conversation_export_sha256,
                            conversation_export_chars=export_meta.conversation_export_chars,
                            conversation_export_format=export_meta.conversation_export_format,
                        )
                        conn.commit()
                except Exception:
                    pass

                export_path = artifacts_dir / "jobs" / job.job_id / "conversation.json"
                try:
                    export_info = _extract_export_model_info_from_conversation_export(export_path=export_path)
                except Exception:
                    export_info = None
                if export_info:
                    payload = dict(export_info)
                    payload.setdefault("source", "conversation_export")
                    try:
                        with connect(db_path) as conn:
                            conn.execute("BEGIN IMMEDIATE")
                            exists = conn.execute(
                                "SELECT 1 FROM job_events WHERE job_id = ? AND type = ? LIMIT 1",
                                (job.job_id, "model_observed_export"),
                            ).fetchone()
                            if exists is None:
                                insert_event(conn, job_id=job.job_id, type="model_observed_export", payload=payload)
                            conn.commit()
                    except Exception:
                        pass
                    try:
                        artifacts.append_event(artifacts_dir, job.job_id, type="model_observed_export", payload=payload)
                    except Exception:
                        pass
                try:
                    export_obj = json.loads(export_path.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    export_obj = {}
                markdown = _render_conversation_export_markdown(
                    export_obj=export_obj if isinstance(export_obj, dict) else {},
                    conversation_id=(str(job.conversation_id or "").strip() or None),
                    conversation_url=(str(job.conversation_url or "").strip() or None),
                )

                with connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        store_answer_result(
                            conn,
                            artifacts_dir=artifacts_dir,
                            job_id=job.job_id,
                            worker_id=worker_id,
                            lease_token=lease_token,
                            answer=markdown,
                            answer_format="markdown",
                        )
                        conn.commit()
                    except (LeaseLost, AlreadyFinished):
                        conn.rollback()
                        return True
            else:
                raw_answer = str(getattr(result, "answer", "") or "")
                answer = raw_answer

                # For image-generation jobs, synthesize a stable markdown answer from attached artifacts.
                if job.kind == "gemini_web.generate_image":
                    meta_ref = getattr(result, "meta", None)
                    meta = dict(meta_ref) if isinstance(meta_ref, dict) else {}
                    formatted = _format_job_images_markdown(job_id=job.job_id, meta=meta)
                    if formatted:
                        raw_answer = formatted
                        answer = formatted
                        result = ExecutorResult(status="completed", answer=formatted, answer_format="markdown", meta=meta)

                question_text = str(input_obj.get("question") or "")
                deep_research_requested = bool((params_obj or {}).get("deep_research"))
                try:
                    min_chars_requested = int((params_obj or {}).get("min_chars") or 0)
                except Exception:
                    min_chars_requested = 0
                export_path = artifacts_dir / "jobs" / job.job_id / "conversation.json"
                existing_export_answer = None
                if export_path.exists():
                    existing_export_answer = _extract_answer_from_conversation_export(
                        export_path=export_path,
                        question=question_text,
                        deep_research=deep_research_requested,
                        allow_fallback_last_assistant=False,
                    )

                # Best-effort: export conversation before finalizing the answer, so we can reconcile
                # truncated tool outputs (e.g. partial stream reads). If an earlier export already
                # contains an assistant reply, avoid forcing another export (reduce UI load).
                export_force_reason = None
                if not (existing_export_answer and existing_export_answer.strip()):
                    export_force_reason = "missing_export_answer"
                else:
                    try:
                        export_len = len(str(existing_export_answer or "").strip())
                        answer_len = len(str(raw_answer or "").strip())
                    except Exception:
                        export_len = 0
                        answer_len = 0
                    if answer_len > 0 and export_len > 0 and (export_len + 500) < answer_len:
                        export_force_reason = "export_answer_too_short_vs_answer"
                    elif deep_research_requested and min_chars_requested > 0 and (export_len + 500) < int(min_chars_requested):
                        export_force_reason = "export_answer_too_short_vs_min_chars"

                if export_force_reason:
                    try:
                        payload = {
                            "reason": str(export_force_reason),
                            "deep_research": bool(deep_research_requested),
                            "min_chars_requested": int(min_chars_requested),
                            "existing_export_answer_chars": (len(str(existing_export_answer or "").strip()) if existing_export_answer else 0),
                            "current_answer_chars": len(str(raw_answer or "").strip()),
                        }
                        with connect(db_path) as conn:
                            conn.execute("BEGIN IMMEDIATE")
                            insert_event(conn, job_id=job.job_id, type="conversation_export_forced", payload=payload)
                            conn.commit()
                        artifacts.append_event(artifacts_dir, job.job_id, type="conversation_export_forced", payload=payload)
                    except Exception:
                        pass
                    try:
                        await _maybe_export_conversation(
                            cfg=cfg,
                            job_id=job.job_id,
                            conversation_url=(conversation_url or str(job.conversation_url or "").strip()),
                            tool_caller=tool_caller,
                            # Bypass OK cooldown for the final export attempt (but still respect failure backoff).
                            force=True,
                            cache=_export_cache,
                        )
                    except Exception:
                        pass

                if export_path.exists():
                    try:
                        parsed = json.loads(export_path.read_text(encoding="utf-8", errors="replace"))
                        export_obj = parsed if isinstance(parsed, dict) else None
                    except Exception:
                        export_obj = None

                    cand = None
                    match_info: dict[str, Any] = {}
                    export_dom_fallback = False
                    if export_obj is not None:
                        export_dom_fallback = _conversation_export_is_dom_fallback(export_obj)
                        cand, match_info = _extract_answer_from_conversation_export_obj(
                            obj=export_obj,
                            question=question_text,
                            deep_research=deep_research_requested,
                            allow_fallback_last_assistant=False,
                        )

                    prefer_export = False
                    if cand and cand.strip():
                        cand_norm = _normalize_text(cand)
                        raw_norm = _normalize_text(raw_answer)
                        if _contains_internal_export_markup(cand) and not _contains_internal_export_markup(raw_answer):
                            prefer_export = False
                        elif export_dom_fallback:
                            prefer_export = _should_prefer_conversation_answer(candidate=cand, current=raw_answer)
                        else:
                            # Official export preserves the message's source (markdown) and is the preferred truth
                            # when it matches the current question window.
                            if (len(cand_norm) + 200) < len(raw_norm):
                                prefer_export = False
                            else:
                                prefer_export = cand_norm != raw_norm

                    if cand and prefer_export:
                        reconcile_ok, reconcile_info = _should_reconcile_export_answer(
                            candidate=str(cand),
                            deep_research=bool(deep_research_requested),
                        )
                        if not reconcile_ok:
                            try:
                                payload = {
                                    "reason": str((reconcile_info or {}).get("reason") or "reconcile_guard_blocked"),
                                    "export_path": export_path.as_posix(),
                                    "export_dom_fallback": export_dom_fallback,
                                    "export_answer_chars": len(str(cand)),
                                }
                                if match_info:
                                    payload["export_match"] = match_info
                                for key in ("connector", "path", "keys"):
                                    if isinstance(reconcile_info, dict) and reconcile_info.get(key) is not None:
                                        payload[key] = reconcile_info.get(key)
                                with connect(db_path) as conn:
                                    conn.execute("BEGIN IMMEDIATE")
                                    insert_event(
                                        conn,
                                        job_id=job.job_id,
                                        type="answer_reconcile_skipped_by_guard",
                                        payload=payload,
                                    )
                                    conn.commit()
                                artifacts.append_event(
                                    artifacts_dir,
                                    job.job_id,
                                    type="answer_reconcile_skipped_by_guard",
                                    payload=payload,
                                )
                            except Exception:
                                pass
                        else:
                            try:
                                raw_meta = artifacts.write_answer_raw(
                                    artifacts_dir,
                                    job.job_id,
                                    answer=raw_answer,
                                    answer_format=str(getattr(result, "answer_format", "text") or "text"),
                                )
                                payload = {
                                    "raw_path": raw_meta.answer_path,
                                    "raw_sha256": raw_meta.answer_sha256,
                                    "raw_chars": raw_meta.answer_chars,
                                    "raw_format": raw_meta.answer_format,
                                    "export_path": export_path.as_posix(),
                                    "export_dom_fallback": export_dom_fallback,
                                    "export_answer_chars": len(cand),
                                }
                                if match_info:
                                    payload["export_match"] = match_info
                                with connect(db_path) as conn:
                                    conn.execute("BEGIN IMMEDIATE")
                                    insert_event(conn, job_id=job.job_id, type="answer_reconciled_from_conversation", payload=payload)
                                    conn.commit()
                                artifacts.append_event(
                                    artifacts_dir,
                                    job.job_id,
                                    type="answer_reconciled_from_conversation",
                                    payload=payload,
                                )
                            except Exception:
                                pass
                            answer = cand

                with connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        store_answer_result(
                            conn,
                            artifacts_dir=artifacts_dir,
                            job_id=job.job_id,
                            worker_id=worker_id,
                            lease_token=lease_token,
                            answer=answer,
                            answer_format=str(getattr(result, "answer_format", "text") or "text"),
                        )
                        conn.commit()
                    except (LeaseLost, AlreadyFinished):
                        conn.rollback()
                        return True
        else:
            status_raw = str(getattr(result, "status", "") or "").strip().lower()
            meta = dict(getattr(result, "meta", None) or {})
            error_type = str(meta.get("error_type") or "RuntimeError")
            error = str(meta.get("error") or getattr(result, "answer", "") or "")
            if not error.strip():
                error = f"<{error_type}: empty error>"
            retry_phase = None
            auto_issue_family: str | None = None
            if is_web_ask_kind(job.kind):
                if _should_release_in_progress_web_job_to_wait(
                    kind=str(job.kind or ""),
                    conversation_url=conversation_url,
                    meta=meta,
                ):
                    retry_phase = "wait"

            if status_raw == JobStatus.IN_PROGRESS.value and is_web_ask_kind(job.kind):
                timeout_decision: dict[str, Any] | None = None
                if exec_phase == "wait":
                    try:
                        with connect(db_path) as conn:
                            timeout_decision = _wait_no_progress_timeout_decision(
                                conn=conn,
                                job=job,
                                kind=str(job.kind or ""),
                                params=params_obj,
                                conversation_url=(str(conversation_url or "").strip() or str(job.conversation_url or "").strip()),
                                now_ts=time.time(),
                            )
                    except Exception as exc:
                        timeout_decision = None
                        guard_err_payload = {
                            "phase": "wait",
                            "reason": "guard_eval_exception",
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:800],
                        }
                        try:
                            with connect(db_path) as conn:
                                conn.execute("BEGIN IMMEDIATE")
                                insert_event(
                                    conn,
                                    job_id=job.job_id,
                                    type="wait_no_progress_guard_eval_failed",
                                    payload=guard_err_payload,
                                )
                                conn.commit()
                        except Exception:
                            pass
                        try:
                            artifacts.append_event(
                                artifacts_dir,
                                job.job_id,
                                type="wait_no_progress_guard_eval_failed",
                                payload=guard_err_payload,
                            )
                        except Exception:
                            pass

                if timeout_decision is not None:
                    timeout_status = timeout_decision.get("status")
                    if not isinstance(timeout_status, JobStatus):
                        timeout_status = JobStatus.NEEDS_FOLLOWUP
                    timeout_error_type = str(timeout_decision.get("error_type") or "WaitNoProgressTimeout")
                    timeout_error = str(timeout_decision.get("error") or "wait phase timed out without progress")
                    timeout_not_before = float(timeout_decision.get("not_before") or time.time())
                    timeout_phase = str(timeout_decision.get("phase") or "wait")
                    timeout_payload = dict(timeout_decision.get("payload") or {})
                    auto_issue_family = str(timeout_payload.get("issue_family") or "").strip() or None

                    try:
                        with connect(db_path) as conn:
                            conn.execute("BEGIN IMMEDIATE")
                            insert_event(conn, job_id=job.job_id, type="wait_no_progress_timeout", payload=timeout_payload)
                            if timeout_status == JobStatus.ERROR:
                                store_error_result(
                                    conn,
                                    artifacts_dir=artifacts_dir,
                                    job_id=job.job_id,
                                    worker_id=worker_id,
                                    lease_token=lease_token,
                                    error_type=timeout_error_type,
                                    error=timeout_error,
                                    status=JobStatus.ERROR,
                                )
                            else:
                                store_retryable_result(
                                    conn,
                                    artifacts_dir=artifacts_dir,
                                    job_id=job.job_id,
                                    worker_id=worker_id,
                                    lease_token=lease_token,
                                    status=timeout_status,
                                    not_before=timeout_not_before,
                                    error_type=timeout_error_type,
                                    error=timeout_error,
                                    phase=timeout_phase,
                                )
                            conn.commit()
                        artifacts.append_event(
                            artifacts_dir,
                            job.job_id,
                            type="wait_no_progress_timeout",
                            payload=timeout_payload,
                        )
                        status_raw = timeout_status.value
                        error_type = timeout_error_type
                        error = timeout_error
                        retry_phase = timeout_phase
                    except LeaseLost:
                        return True
                else:
                    retry_after = meta.get("retry_after_seconds")
                    not_before = _coerce_retry_not_before(
                        meta.get("not_before"),
                        retry_after=retry_after,
                    )
                    should_release_for_wait = exec_phase == "wait" or retry_phase == "wait"
                    try:
                        with connect(db_path) as conn:
                            conn.execute("BEGIN IMMEDIATE")
                            if should_release_for_wait:
                                release_for_wait(
                                    conn,
                                    artifacts_dir=artifacts_dir,
                                    job_id=job.job_id,
                                    worker_id=worker_id,
                                    lease_token=lease_token,
                                    not_before=not_before,
                                )
                            else:
                                store_retryable_result(
                                    conn,
                                    artifacts_dir=artifacts_dir,
                                    job_id=job.job_id,
                                    worker_id=worker_id,
                                    lease_token=lease_token,
                                    status=JobStatus.COOLDOWN,
                                    not_before=not_before,
                                    error_type=error_type,
                                    error=error,
                                    phase="send",
                                )
                                status_raw = JobStatus.COOLDOWN.value
                                retry_phase = "send"
                            conn.commit()
                    except LeaseLost:
                        return True
            else:
                with connect(db_path) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        if status_raw == JobStatus.CANCELED.value:
                            store_canceled_result(
                                conn,
                                artifacts_dir=artifacts_dir,
                                job_id=job.job_id,
                                worker_id=worker_id,
                                lease_token=lease_token,
                                reason=(str(meta.get("reason")) if meta.get("reason") else None),
                            )
                        elif status_raw in {JobStatus.BLOCKED.value, JobStatus.COOLDOWN.value, JobStatus.NEEDS_FOLLOWUP.value}:
                            retry_after = meta.get("retry_after_seconds")
                            not_before = _coerce_retry_not_before(
                                meta.get("not_before"),
                                retry_after=retry_after,
                            )
                            store_retryable_result(
                                conn,
                                artifacts_dir=artifacts_dir,
                                job_id=job.job_id,
                                worker_id=worker_id,
                                lease_token=lease_token,
                                status=JobStatus(status_raw),
                                not_before=not_before,
                                error_type=error_type,
                                error=error,
                                phase=retry_phase,
                            )
                        elif status_raw == JobStatus.IN_PROGRESS.value:
                            retry_after = meta.get("retry_after_seconds")
                            not_before = float(time.time() + float(retry_after if retry_after is not None else 60))
                            store_retryable_result(
                                conn,
                                artifacts_dir=artifacts_dir,
                                job_id=job.job_id,
                                worker_id=worker_id,
                                lease_token=lease_token,
                                status=JobStatus.COOLDOWN,
                                not_before=not_before,
                                error_type="InProgress",
                                error="job still in progress; retry later",
                                phase=retry_phase,
                            )
                        else:
                            # Some driver/tool layers report infra/UI failures as `status=error` even though
                            # they are safe to retry (no prompt was sent, or idempotency prevents duplicates).
                            # Convert those into COOLDOWN so the same job can auto-recover to completed.
                            retryable_error = False
                            classified_error_type = error_type
                            if is_worker_autofix_kind(job.kind):
                                if _looks_like_infra_error(error_type, error):
                                    retryable_error = True
                                    classified_error_type = "InfraError"
                                elif _looks_like_ui_transient_error(error_type, error):
                                    retryable_error = True
                                    classified_error_type = "UiTransientError"

                            if retryable_error:
                                retry_after = meta.get("retry_after_seconds")
                                if retry_after is None:
                                    retry_after = _retry_after_seconds_for_error(error_type=error_type, error=error)
                                not_before = _coerce_retry_not_before(
                                    meta.get("not_before"),
                                    retry_after=retry_after,
                                )
                                store_retryable_result(
                                    conn,
                                    artifacts_dir=artifacts_dir,
                                    job_id=job.job_id,
                                    worker_id=worker_id,
                                    lease_token=lease_token,
                                    status=JobStatus.COOLDOWN,
                                    not_before=not_before,
                                    error_type=classified_error_type,
                                    error=error,
                                    phase=retry_phase,
                                )
                                status_raw = JobStatus.COOLDOWN.value
                            else:
                                store_error_result(
                                    conn,
                                    artifacts_dir=artifacts_dir,
                                    job_id=job.job_id,
                                    worker_id=worker_id,
                                    lease_token=lease_token,
                                    error_type=error_type,
                                    error=error,
                                    status=JobStatus.ERROR,
                                )
                        conn.commit()
                    except (LeaseLost, AlreadyFinished):
                        conn.rollback()
                        return True

            report_status = status_raw
            report_error_type = error_type
            report_error = error
            try:
                with connect(db_path) as conn:
                    final_row = conn.execute(
                        "SELECT status, last_error_type, last_error FROM jobs WHERE job_id = ?",
                        (job.job_id,),
                    ).fetchone()
                if final_row is not None:
                    status_db = str(final_row["status"] or "").strip().lower()
                    if status_db:
                        report_status = status_db
                    last_error_type_db = str(final_row["last_error_type"] or "").strip()
                    if last_error_type_db:
                        report_error_type = last_error_type_db
                    last_error_db = str(final_row["last_error"] or "").strip()
                    if last_error_db:
                        report_error = last_error_db
            except Exception:
                pass

            try:
                explicit_family_id = str(meta.get("family_id") or "").strip() or None
                explicit_family_label = str(meta.get("family_label") or "").strip() or None
                attachment_contract_meta = meta.get("attachment_contract")
                signal_family_id = (
                    str(attachment_contract_signal.get("family_id") or "").strip()
                    if isinstance(attachment_contract_signal, dict)
                    else ""
                ) or None
                signal_family_label = (
                    str(attachment_contract_signal.get("family_label") or "").strip()
                    if isinstance(attachment_contract_signal, dict)
                    else ""
                ) or None
                _maybe_auto_report_issue(
                    cfg=cfg,
                    job=job,
                    status=report_status,
                    error_type=report_error_type,
                    error=report_error,
                    conversation_url=(conversation_url or str(job.conversation_url or "").strip()),
                    extra_metadata={
                        "retry_phase": retry_phase,
                        "executor_status": str(getattr(result, "status", "") or "").strip().lower(),
                        **({"family_id": (explicit_family_id or auto_issue_family or signal_family_id)} if (explicit_family_id or auto_issue_family or signal_family_id) else {}),
                        **({"family_label": (explicit_family_label or signal_family_label)} if (explicit_family_label or signal_family_label) else {}),
                        **({"attachment_contract": attachment_contract_meta} if isinstance(attachment_contract_meta, dict) else {}),
                        **({"attachment_contract": attachment_contract_signal} if attachment_contract_signal and not isinstance(attachment_contract_meta, dict) else {}),
                        **({"wait_state": str(meta.get("wait_state") or "").strip()} if str(meta.get("wait_state") or "").strip() else {}),
                    },
                )
            except Exception:
                pass

            # Best-effort: when we hit blocked/cooldown, snapshot proxy delay so Cloudflare incidents
            # can be correlated with mihomo latency spikes.
            if status_raw in {JobStatus.BLOCKED.value, JobStatus.COOLDOWN.value, JobStatus.NEEDS_FOLLOWUP.value}:
                try:
                    await _maybe_submit_worker_autofix(
                        cfg=cfg,
                        job_id=job.job_id,
                        kind=str(job.kind or ""),
                        status=status_raw,
                        error_type=error_type,
                        error=error,
                        conversation_url=(conversation_url or str(job.conversation_url or "").strip()),
                    )
                except Exception:
                    pass
                try:
                    _record_mihomo_delay_snapshot(
                        cfg=cfg,
                        job_id=job.job_id,
                        status=status_raw,
                        reason=(str(meta.get("error")) if meta.get("error") else None),
                    )
                except Exception:
                    pass

            if status_raw in {JobStatus.NEEDS_FOLLOWUP.value, JobStatus.IN_PROGRESS.value}:
                try:
                    await _maybe_export_conversation(
                        cfg=cfg,
                        job_id=job.job_id,
                        conversation_url=(conversation_url or str(job.conversation_url or "").strip()),
                        tool_caller=tool_caller,
                        cache=_export_cache,
                    )
                except Exception:
                    pass
    finally:
        stop_event.set()
        await asyncio.gather(heartbeat_task, return_exceptions=True)
        await asyncio.gather(cancel_watch_task, return_exceptions=True)
    return True


async def main_async() -> int:
    import signal as _signal

    _drain_requested = False

    def _on_drain_signal(signum, frame):
        nonlocal _drain_requested
        _drain_requested = True
        sig_name = _signal.Signals(signum).name if hasattr(_signal, 'Signals') else str(signum)
        print(f"worker_drain: received {sig_name}, will exit after current job completes", file=sys.stderr, flush=True)

    # SIGTERM = graceful drain (finish current job, then exit)
    # SIGUSR1 = same, but explicit "hot reload" intent
    _signal.signal(_signal.SIGTERM, _on_drain_signal)
    try:
        _signal.signal(_signal.SIGUSR1, _on_drain_signal)
    except (OSError, AttributeError):
        pass  # SIGUSR1 not available on all platforms

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=None)
    parser.add_argument("--artifacts", default=None)
    parser.add_argument("--worker-id", default=None)
    parser.add_argument("--role", default=os.environ.get("CHATGPTREST_WORKER_ROLE") or "all")
    parser.add_argument("--kind-prefix", default=os.environ.get("CHATGPTREST_WORKER_KIND_PREFIX") or "")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-sec", type=float, default=0.5)
    args = parser.parse_args()

    cfg = load_config()
    if args.db:
        cfg = _dc_replace(cfg, db_path=Path(args.db).expanduser())
    if args.artifacts:
        cfg = _dc_replace(cfg, artifacts_dir=Path(args.artifacts).expanduser())
    worker_id = str(args.worker_id or f"{socket.gethostname()}:{os.getpid()}")
    role = _normalize_worker_role(args.role)
    kind_prefix = str(args.kind_prefix or "").strip() or None
    work_cycle_seconds = max(0, _env_int("CHATGPTREST_WORK_CYCLE_SECONDS", 7200))
    work_sleep_min_seconds = max(0, _env_int("CHATGPTREST_WORK_SLEEP_MIN_SECONDS", 900))
    work_sleep_max_seconds = max(work_sleep_min_seconds, _env_int("CHATGPTREST_WORK_SLEEP_MAX_SECONDS", 1800))
    work_cycle_active_seconds = 0.0
    # Only apply long sleep-cycle pauses to the "send" role to reduce risk-control exposure.
    # The "wait" role should stay responsive to finalize jobs promptly.
    sleep_cycle_enabled = role in {"send", "all"} and work_cycle_seconds > 0 and work_sleep_max_seconds > 0

    while True:
        # Check drain flag before picking up new work
        if _drain_requested:
            print("worker_drain: drain flag set, exiting gracefully", file=sys.stderr, flush=True)
            return 0

        loop_started = time.monotonic()
        sleep_override: float | None = None
        try:
            ran = await _run_once(
                cfg=cfg,
                worker_id=worker_id,
                lease_ttl_seconds=cfg.lease_ttl_seconds,
                role=role,
                kind_prefix=kind_prefix,
            )
        except Exception as exc:
            print(f"worker_loop_error: {type(exc).__name__}: {exc}", file=sys.stderr)
            tb = traceback.format_exc()
            print(tb, file=sys.stderr)
            ran = False
            if _looks_like_db_write_unavailable(exc):
                try:
                    _write_db_panic_snapshot(cfg=cfg, worker_id=worker_id, exc=exc, tb=tb)
                except Exception:
                    pass
                try:
                    _try_db_write_autofix(cfg=cfg, worker_id=worker_id, exc=exc, tb=tb)
                except Exception:
                    pass
                action = _env_registry.get_str("CHATGPTREST_WORKER_FATAL_DB_ACTION").lower() or "backoff"
                if action in {"exit", "die"}:
                    return 70
                backoff = max(5.0, float(_env_int("CHATGPTREST_WORKER_FATAL_DB_BACKOFF_SECONDS", 30)))
                sleep_override = backoff
        loop_elapsed = time.monotonic() - loop_started
        if ran and sleep_cycle_enabled:
            work_cycle_active_seconds += max(0.0, loop_elapsed)
            if work_cycle_active_seconds >= float(work_cycle_seconds):
                backlog = _count_ready_jobs_fast(cfg=cfg, phase="send", kind_prefix=kind_prefix)
                if backlog is None:
                    print("worker_sleep_cycle: backlog unknown; skipping sleep", file=sys.stderr)
                elif backlog > 0:
                    print(f"worker_sleep_cycle: backlog={backlog}; skipping sleep", file=sys.stderr)
                else:
                    sleep_for = random.uniform(float(work_sleep_min_seconds), float(work_sleep_max_seconds))
                    print(f"worker_sleep_cycle: sleeping {sleep_for:.1f}s after active work", file=sys.stderr)
                    await asyncio.sleep(sleep_for)
                work_cycle_active_seconds = 0.0
        if args.once:
            return 0
        if sleep_override is not None:
            await asyncio.sleep(float(sleep_override))
            continue
        if not ran:
            await asyncio.sleep(max(0.1, float(args.poll_sec)))


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
