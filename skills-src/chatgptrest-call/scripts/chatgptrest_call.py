#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import fcntl
import http.client
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.integrations.mcp_http_client import (
    McpHttpSession,
    mcp_http_initialize_handshake,
    mcp_http_jsonrpc_call,
)

DEFAULT_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_PUBLIC_MCP_URL = "http://127.0.0.1:18712/mcp"


def _default_chatgptrest_root() -> Path:
    override = str(os.environ.get("CHATGPTREST_ROOT") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT


def _default_interval_state_file(root: Path) -> Path:
    override = str(os.environ.get("CHATGPTREST_CALL_INTERVAL_STATE_FILE") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (root / "state" / "skill" / "chatgptrest_call_interval.json").resolve()


def _default_chatgpt_review_lane_lock_file(root: Path) -> Path:
    override = str(os.environ.get("CHATGPTREST_CALL_CHATGPT_REVIEW_LOCK_FILE") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (root / "state" / "skill" / "chatgptrest_call_chatgpt_review.lock").resolve()


DEFAULT_CHATGPTREST_ROOT = str(_default_chatgptrest_root())
DEFAULT_INTERVAL_STATE_FILE = str(_default_interval_state_file(Path(DEFAULT_CHATGPTREST_ROOT)))
DEFAULT_CHATGPT_REVIEW_LANE_LOCK_FILE = str(
    _default_chatgpt_review_lane_lock_file(Path(DEFAULT_CHATGPTREST_ROOT))
)
DEFAULT_RUNTIME_ENV_FILES = (
    str((Path.home() / ".config" / "chatgptrest" / "chatgptrest.env").resolve(strict=False)),
    "/vol1/maint/MAIN/secrets/credentials.env",
)
DEFAULT_MAINT_LEGACY_CLIENT_NAME = "chatgptrestctl-maint"
DEFAULT_AGENT_SURFACE = "automation-kernel-v1"
DEFAULT_AGENT_TIMEOUT_SECONDS = 300
DEFAULT_AGENT_REQUEST_TIMEOUT_SECONDS = 330.0
DEFAULT_LEGACY_REQUEST_TIMEOUT_SECONDS = 180.0
DEFAULT_MCP_PROTOCOL_VERSION = "2025-03-26"
DEFAULT_MCP_CLIENT_NAME = "chatgptrest-call"
DEFAULT_MCP_CLIENT_VERSION = "1.0"
DEFAULT_CHATGPT_REVIEW_LANE_LOCK_TIMEOUT_SECONDS = 7200.0
DEFAULT_CHATGPT_PRO_AGENT_TIMEOUT_SECONDS = 3600
DEFAULT_CHATGPT_DEEP_RESEARCH_AGENT_TIMEOUT_SECONDS = 7200
# Cloudflare / verification_pending cooldown loops on the shared ChatGPT review lane can
# legitimately require multiple same-session resumes before the browser surface is usable again.
# Keep the default budget high enough to outlast transient challenge windows without forcing
# operators to hand-tune every wrapped review invocation.
DEFAULT_AGENT_SAME_SESSION_REPAIR_MAX_ATTEMPTS = 8
_AGENT_BACKGROUND_GOAL_HINTS = {
    "code_review",
    "consult",
    "gemini_deep_research",
    "gemini_research",
    "image",
    "report",
    "research",
}
_AUTOMATION_TERMINAL_STATUSES = {
    "blocked",
    "canceled",
    "cancelled",
    "completed",
    "failed",
    "needs_followup",
    "needs_input",
}
_AUTOMATION_ALLOWED_PROVIDERS = {"chatgpt", "gemini"}


def _runtime_env_file_candidates() -> list[Path]:
    override = str(os.environ.get("CHATGPTREST_CALL_ENV_FILES") or "").strip()
    raw_items = override.split(os.pathsep) if override else list(DEFAULT_RUNTIME_ENV_FILES)
    out: list[Path] = []
    seen: set[str] = set()
    for raw in raw_items:
        item = str(raw or "").strip()
        if not item:
            continue
        path = Path(item).expanduser().resolve(strict=False)
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _parse_env_file(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    if not path.exists():
        return payload
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = str(key or "").strip()
        if not normalized_key:
            continue
        normalized_value = str(value or "").strip()
        if normalized_value:
            try:
                tokens = shlex.split(normalized_value, comments=False, posix=True)
                if len(tokens) == 1:
                    normalized_value = tokens[0]
            except Exception:
                pass
        payload[normalized_key] = normalized_value
    return payload


def _autoload_runtime_env() -> dict[str, Any]:
    loaded: dict[str, list[str]] = {}
    for path in _runtime_env_file_candidates():
        file_payload = _parse_env_file(path)
        if not file_payload:
            continue
        loaded_keys: list[str] = []
        for key, value in file_payload.items():
            if str(os.environ.get(key) or "").strip():
                continue
            os.environ[key] = value
            loaded_keys.append(key)
        if loaded_keys:
            loaded[str(path)] = sorted(loaded_keys)
    return {
        "files": sorted(loaded.keys()),
        "loaded_keys_by_file": loaded,
    }


def _json_dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


def _write_summary_file(path_str: str, payload: dict[str, Any]) -> None:
    path = Path(str(path_str)).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(payload), encoding="utf-8")


def _build_agent_summary(result: dict[str, Any]) -> dict[str, Any]:
    provenance = dict(result.get("provenance") or {})
    next_action = dict(result.get("next_action") or {})
    summary: dict[str, Any] = {
        "ok": bool(result.get("ok")),
        "mode": "agent_public_mcp",
        "session_id": str(result.get("session_id") or ""),
        "run_id": str(result.get("run_id") or ""),
        "status": str(result.get("status") or ""),
        "route": str(provenance.get("route") or result.get("route") or ""),
        "next_action_type": str(next_action.get("type") or ""),
        "result": dict(result),
    }
    if isinstance(provenance.get("provider_selection"), dict):
        summary["provider_selection"] = dict(provenance.get("provider_selection") or {})
    if isinstance(result.get("lifecycle"), dict):
        summary["lifecycle"] = dict(result.get("lifecycle") or {})
    if isinstance(result.get("delivery"), dict):
        summary["delivery"] = dict(result.get("delivery") or {})
    if isinstance(result.get("effects"), dict):
        summary["effects"] = dict(result.get("effects") or {})
    for key in (
        "accepted_for_background",
        "wait_tool",
        "wait_transport_recovered",
        "wait_transport_retry_count",
        "wait_transport_resolution",
        "transport_recovered",
        "auto_resumed",
        "same_session_repair_attempts",
        "answer_state",
        "authoritative_job_id",
        "authoritative_answer_path",
        "answer_provenance",
        "canonical_answer",
        "answer_fetch",
    ):
        if key in result:
            summary[key] = result.get(key)
    return summary


def _build_automation_summary(result: dict[str, Any]) -> dict[str, Any]:
    provider = str(result.get("provider") or "").strip()
    kind = str(result.get("kind") or "").strip()
    job_id = str(result.get("job_id") or result.get("authoritative_job_id") or "").strip()
    summary: dict[str, Any] = {
        "ok": bool(result.get("ok")),
        "mode": "automation_public_mcp",
        "surface": "automation-kernel-v1",
        "job_id": job_id,
        "status": str(result.get("status") or ""),
        "provider": provider,
        "kind": kind,
        "action_hint": str(result.get("action_hint") or ""),
        "result": dict(result),
    }
    for key in (
        "answer_state",
        "answer",
        "canonical_answer",
        "answer_fetch",
        "background_wait",
        "authoritative_job_id",
        "authoritative_answer_path",
        "answer_provenance",
    ):
        if key in result:
            summary[key] = result.get(key)
    return summary


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _load_driver_blocked_state(chatgptrest_root: Path) -> dict[str, Any]:
    candidates: list[Path] = []
    env_path = str(os.environ.get("CHATGPT_BLOCKED_STATE_FILE") or "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.append((chatgptrest_root / "state" / "driver" / "chatgpt_blocked_state.json").resolve(strict=False))

    seen: set[str] = set()
    for candidate in candidates:
        state_path = candidate.resolve(strict=False)
        key = str(state_path)
        if key in seen:
            continue
        seen.add(key)
        if not state_path.exists():
            continue
        payload = _load_json_file(state_path)
        if payload:
            payload.setdefault("path", str(state_path))
            return payload
    return {}


def _chatgpt_review_lane_enabled(args: argparse.Namespace, *, legacy_preset: str) -> bool:
    if not bool(getattr(args, "serialize_chatgpt_review_lane", True)):
        return False
    provider = str(getattr(args, "provider", "") or "").strip().lower()
    if provider != "chatgpt":
        return False
    if not _is_pro_preset(legacy_preset):
        return False
    goal_hint = str(getattr(args, "goal_hint", "") or "").strip().lower()
    if goal_hint not in {"code_review", "report", "research"}:
        return False
    return bool(str(getattr(args, "github_repo", "") or "").strip() or list(getattr(args, "file_path", []) or []))


@contextlib.contextmanager
def _provider_lane_lock(
    *,
    enabled: bool,
    lock_path: Path,
    timeout_seconds: float,
    metadata: dict[str, Any] | None = None,
):
    if not enabled:
        yield None
        return
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    handle = lock_path.open("a+", encoding="utf-8")
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if timeout_seconds > 0 and (time.time() - start) >= timeout_seconds:
                    raise RuntimeError(
                        "timed out waiting for ChatGPT review lane lock",
                        {"lock_path": str(lock_path), "timeout_seconds": float(timeout_seconds)},
                    )
                time.sleep(1.0)
        if metadata:
            handle.seek(0)
            handle.truncate()
            handle.write(_json_dump({"pid": os.getpid(), **dict(metadata)}))
            handle.flush()
        yield {"lock_path": str(lock_path), "waited_seconds": round(time.time() - start, 3)}
    finally:
        try:
            if acquired:
                handle.seek(0)
                handle.truncate()
                handle.flush()
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _retry_after_seconds_from_blocked_state(*, state: dict[str, Any], cap_seconds: int) -> int:
    if not state:
        return 0
    if str(state.get("reason") or "").strip().lower() != "verification_pending":
        return 0
    blocked_until = float(state.get("blocked_until") or 0.0)
    remaining = max(0, int(round(blocked_until - time.time())))
    return max(0, min(int(cap_seconds), remaining))


def _repair_next_delay_seconds(
    *,
    result: dict[str, Any],
    blocked_state: dict[str, Any],
    cap_seconds: int,
) -> int:
    next_action = dict(result.get("next_action") or {})
    raw_retry_after = next_action.get("retry_after_seconds")
    try:
        retry_after = int(float(raw_retry_after)) if raw_retry_after is not None else 0
    except Exception:
        retry_after = 0
    blocked_retry_after = _retry_after_seconds_from_blocked_state(state=blocked_state, cap_seconds=cap_seconds)
    wait_seconds = max(retry_after, blocked_retry_after)
    return max(0, min(int(cap_seconds), wait_seconds))


def _same_session_repair_next_action(result: dict[str, Any]) -> dict[str, Any]:
    next_action = result.get("next_action")
    return dict(next_action or {}) if isinstance(next_action, dict) else {}


def _same_session_repair_error_type(result: dict[str, Any]) -> str:
    return str(_same_session_repair_next_action(result).get("error_type") or "").strip().lower()


def _same_session_repair_job_id(result: dict[str, Any]) -> str:
    next_action = _same_session_repair_next_action(result)
    return str(
        next_action.get("job_id")
        or result.get("authoritative_job_id")
        or result.get("job_id")
        or ""
    ).strip()


def _same_session_repair_conversation_url(result: dict[str, Any]) -> str:
    for value in (
        result.get("conversation_url"),
        (result.get("delivery") or {}).get("conversation_url") if isinstance(result.get("delivery"), dict) else "",
    ):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _ops_bearer_token() -> str:
    return str(os.environ.get("CHATGPTREST_OPS_TOKEN") or "").strip()


def _http_json_request(
    url: str,
    *,
    method: str,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    req = urllib.request.Request(
        str(url),
        data=(json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None),
        method=str(method).upper(),
        headers=dict(headers or {}),
    )
    try:
        with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} calling {method.upper()} {url}: {text}") from exc
    body = str(raw or "").strip()
    if not body:
        return {}
    parsed = json.loads(body)
    return dict(parsed) if isinstance(parsed, dict) else {}


def _submit_repair_autofix_job(
    *,
    base_url: str,
    ops_token: str,
    session_id: str,
    target_job_id: str,
    symptom: str,
    conversation_url: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    bucket = int(time.time() // 900.0)
    idempotency_key = f"same-session-repair-autofix:{session_id}:{target_job_id}:{bucket}"
    payload: dict[str, Any] = {
        "kind": "repair.autofix",
        "input": {
            "job_id": str(target_job_id),
            "symptom": str(symptom or "").strip() or "same_session_repair WebRetryBudgetExceeded",
        },
        "params": {
            "timeout_seconds": max(30, min(int(timeout_seconds), 600)),
            "max_risk": "low",
            "allow_actions": ["capture_ui", "clear_blocked", "refresh"],
            "apply_actions": True,
        },
    }
    if str(conversation_url or "").strip():
        payload["input"]["conversation_url"] = str(conversation_url).strip()
    return _http_json_request(
        f"{str(base_url).rstrip('/')}/v1/jobs",
        method="POST",
        timeout_seconds=max(10.0, min(float(timeout_seconds), 60.0)),
        headers={
            "Authorization": f"Bearer {ops_token}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            "X-Client-Name": DEFAULT_MAINT_LEGACY_CLIENT_NAME,
            "X-Client-Instance": "chatgptrest-call:auto-repair",
            "X-Request-Id": f"chatgptrest-call-repair-{uuid.uuid4().hex[:16]}",
        },
        payload=payload,
    )


def _wait_for_repair_autofix_terminal(
    *,
    base_url: str,
    ops_token: str,
    repair_job_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.time() + max(5.0, float(timeout_seconds))
    last: dict[str, Any] = {}
    while time.time() <= deadline:
        last = _http_json_request(
            f"{str(base_url).rstrip('/')}/v1/jobs/{urllib.parse.quote(str(repair_job_id))}",
            method="GET",
            timeout_seconds=min(30.0, max(5.0, float(timeout_seconds))),
            headers={
                "Authorization": f"Bearer {ops_token}",
                "X-Client-Name": DEFAULT_MAINT_LEGACY_CLIENT_NAME,
                "X-Client-Instance": "chatgptrest-call:auto-repair",
                "X-Request-Id": f"chatgptrest-call-repair-status-{uuid.uuid4().hex[:16]}",
            },
        )
        status = str(last.get("status") or "").strip().lower()
        if status not in {"queued", "pending", "running", "in_progress"}:
            return last
        time.sleep(2.0)
    return last


def _maybe_run_same_session_runtime_repair(
    *,
    args: argparse.Namespace,
    result: dict[str, Any],
    session_id: str,
    request_timeout_seconds: float,
) -> dict[str, Any]:
    error_type = _same_session_repair_error_type(result)
    if error_type != "webretrybudgetexceeded":
        return {"attempted": False, "skipped": True, "reason": f"unsupported_error_type:{error_type or 'unknown'}"}
    ops_token = _ops_bearer_token()
    if not ops_token:
        return {"attempted": False, "skipped": True, "reason": "missing_ops_token"}
    target_job_id = _same_session_repair_job_id(result)
    if not target_job_id:
        return {"attempted": False, "skipped": True, "reason": "missing_target_job_id"}
    conversation_url = _same_session_repair_conversation_url(result)
    symptom = (
        "advisor-agent same_session_repair after WebRetryBudgetExceeded; "
        "preserve same conversation and do low-risk runtime recovery only"
    )
    submit = _submit_repair_autofix_job(
        base_url=str(args.base_url),
        ops_token=ops_token,
        session_id=str(session_id),
        target_job_id=target_job_id,
        symptom=symptom,
        conversation_url=conversation_url,
        timeout_seconds=min(max(float(request_timeout_seconds), 30.0), 180.0),
    )
    repair_job_id = str(submit.get("job_id") or "").strip()
    if not repair_job_id:
        return {
            "attempted": True,
            "submitted": False,
            "skipped": True,
            "reason": "missing_repair_job_id",
            "submit_result": submit,
        }
    terminal = _wait_for_repair_autofix_terminal(
        base_url=str(args.base_url),
        ops_token=ops_token,
        repair_job_id=repair_job_id,
        timeout_seconds=min(max(float(request_timeout_seconds), 30.0), 180.0),
    )
    return {
        "attempted": True,
        "submitted": True,
        "repair_job_id": repair_job_id,
        "repair_status": str(terminal.get("status") or "").strip().lower(),
        "completed": str(terminal.get("status") or "").strip().lower() == "completed",
        "terminal_result": terminal,
    }


def _should_auto_same_session_repair(
    *,
    args: argparse.Namespace,
    result: dict[str, Any],
    legacy_preset: str,
    blocked_state: dict[str, Any],
    repair_attempts: int,
) -> bool:
    if repair_attempts >= int(
        getattr(args, "same_session_repair_max_attempts", DEFAULT_AGENT_SAME_SESSION_REPAIR_MAX_ATTEMPTS)
    ):
        return False
    if not _chatgpt_review_lane_enabled(args, legacy_preset=legacy_preset):
        return False
    if str(result.get("status") or "").strip().lower() != "needs_followup":
        return False
    lifecycle = dict(result.get("lifecycle") or {})
    if not bool(lifecycle.get("same_session_patch_allowed")):
        return False
    next_action = dict(result.get("next_action") or {})
    if str(next_action.get("type") or "").strip().lower() != "same_session_repair":
        return False
    error_type = str(next_action.get("error_type") or "").strip().lower()
    if error_type not in {"", "blocked", "runtimeerror", "webretrybudgetexceeded"}:
        return False
    if error_type == "runtimeerror" and str(blocked_state.get("reason") or "").strip().lower() != "verification_pending":
        return False
    if error_type == "webretrybudgetexceeded" and not _same_session_repair_job_id(result):
        return False
    if error_type == "webretrybudgetexceeded":
        return True
    if _repair_next_delay_seconds(result=result, blocked_state=blocked_state, cap_seconds=300) > 0:
        return True
    return str(blocked_state.get("reason") or "").strip().lower() == "verification_pending"


def _agent_runtime_payload(
    *,
    session_id: str,
    agent_timeout_seconds: int,
    request_timeout_seconds: float,
    delivery_mode: str,
    submission_stage: str,
    submission_started: bool,
    mcp_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session_id": str(session_id or ""),
        "agent_timeout_seconds": int(agent_timeout_seconds),
        "request_timeout_seconds": float(request_timeout_seconds),
        "delivery_mode": str(delivery_mode or ""),
        "submission_stage": str(submission_stage or ""),
        "submission_started": bool(submission_started),
    }
    if isinstance(mcp_session, dict) and mcp_session:
        payload["mcp_session"] = dict(mcp_session)
    return payload


def _write_agent_summary_snapshot(
    path_str: str,
    *,
    result: dict[str, Any] | None = None,
    runtime: dict[str, Any],
) -> None:
    if isinstance(result, dict):
        summary = _build_agent_summary(result)
    else:
        submission_stage = str(runtime.get("submission_stage") or "").strip()
        submission_started = bool(runtime.get("submission_started"))
        summary_status = "submitting"
        lifecycle_phase = "bootstrap"
        next_action_type = ""
        if submission_stage in {"initialize_mcp", "initialized"} and not submission_started:
            summary_status = "initialized"
        elif submission_started:
            summary_status = "submitted"
            lifecycle_phase = "progress"
            next_action_type = "await_turn_response"
        summary = {
            "ok": True,
            "mode": "agent_public_mcp",
            "session_id": str(runtime.get("session_id") or ""),
            "run_id": "",
            "status": summary_status,
            "route": "",
            "next_action_type": next_action_type,
            "delivery": {
                "accepted": False,
                "answer_chars": 0,
                "answer_ready": False,
                "artifact_count": 0,
                "format": "markdown",
                "mode": str(runtime.get("delivery_mode") or "sync"),
                "stream_url": "",
                "terminal": False,
                "watchable": False,
            },
            "lifecycle": {
                "phase": lifecycle_phase,
                "status": summary_status,
                "turn_terminal": False,
                "session_terminal": False,
                "blocking": False,
                "resumable": True,
                "same_session_patch_allowed": False,
                "next_action_type": next_action_type,
                "stream_supported": False,
            },
            "result": {
                "ok": True,
                "session_id": str(runtime.get("session_id") or ""),
                "status": summary_status,
            },
        }
    summary["requested_runtime"] = dict(runtime)
    _write_summary_file(path_str, summary)


def _write_automation_summary_snapshot(
    path_str: str,
    *,
    result: dict[str, Any] | None = None,
    runtime: dict[str, Any],
) -> None:
    if isinstance(result, dict):
        summary = _build_automation_summary(result)
    else:
        summary = {
            "ok": True,
            "mode": "automation_public_mcp",
            "surface": "automation-kernel-v1",
            "job_id": str(runtime.get("job_id") or ""),
            "status": str(runtime.get("status") or "submitting"),
            "provider": str(runtime.get("provider") or ""),
            "kind": str(runtime.get("kind") or ""),
            "action_hint": str(runtime.get("action_hint") or ""),
            "result": {
                "ok": True,
                "job_id": str(runtime.get("job_id") or ""),
                "status": str(runtime.get("status") or "submitting"),
            },
        }
    summary["requested_runtime"] = dict(runtime)
    _write_summary_file(path_str, summary)


def _run_json_command(cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> dict[str, Any]:
    proc_env = None
    if env:
        proc_env = dict(os.environ)
        proc_env.update({str(k): str(v) for k, v in env.items()})
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=proc_env,
        cwd=(str(cwd) if cwd is not None else None),
    )
    if proc.returncode != 0:
        err_text = (proc.stderr or "").strip()
        err_obj: Any
        try:
            err_obj = json.loads(err_text) if err_text else None
        except Exception:
            err_obj = err_text or (proc.stdout or "").strip() or None
        raise RuntimeError(f"command failed rc={proc.returncode}", err_obj)

    out_text = (proc.stdout or "").strip()
    if not out_text:
        raise RuntimeError("command returned empty stdout", None)
    try:
        data = json.loads(out_text)
    except Exception as exc:
        raise RuntimeError(f"invalid JSON stdout: {exc}", out_text) from exc
    if not isinstance(data, dict):
        raise RuntimeError("command JSON stdout must be an object", data)
    return data


def _mcp_headers(session: dict[str, Any] | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if isinstance(session, dict):
        session_id = str(session.get("session_id") or "").strip()
        protocol_version = str(session.get("protocol_version") or "").strip()
        if session_id:
            headers["mcp-session-id"] = session_id
        if protocol_version:
            headers["mcp-protocol-version"] = protocol_version
    return headers


def _mcp_http_session(session: dict[str, Any], *, mcp_url: str) -> McpHttpSession:
    return McpHttpSession(
        url=str(mcp_url),
        session_id=str(session.get("session_id") or "").strip() or None,
        protocol_version=str(session.get("protocol_version") or "").strip() or DEFAULT_MCP_PROTOCOL_VERSION,
    )


def _run_mcp_tool(
    *,
    mcp_url: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: float,
    request_id: int = 1,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(session, dict):
        raise RuntimeError("missing MCP session for tool call")
    payload = mcp_http_jsonrpc_call(
        _mcp_http_session(session, mcp_url=mcp_url),
        method="tools/call",
        params={"name": str(tool_name), "arguments": dict(arguments)},
        timeout_sec=float(timeout_seconds),
    )
    return _decode_tool_result(payload)


def _partial_text_from_incomplete_read(exc: http.client.IncompleteRead) -> str:
    partial = exc.partial
    if isinstance(partial, bytes):
        return partial.decode("utf-8", errors="replace")
    return str(partial or "")


def _jsonrpc_call(
    url: str,
    *,
    request_id: int,
    method: str,
    params: dict[str, Any],
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    req = urllib.request.Request(
        str(url),
        data=json.dumps(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
            ensure_ascii=False,
        ).encode("utf-8"),
        method="POST",
        headers=dict(headers or _mcp_headers()),
    )
    try:
        with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
            response_headers = {str(k): str(v) for k, v in resp.headers.items()}
            try:
                raw = resp.read().decode("utf-8", errors="replace")
            except http.client.IncompleteRead as exc:
                raw = _partial_text_from_incomplete_read(exc)
                try:
                    parsed = _decode_jsonrpc_body(raw)
                except Exception:
                    raise
                return parsed, response_headers
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} calling MCP {method}: {text}") from exc
    parsed = _decode_jsonrpc_body(raw)
    if "error" in parsed:
        raise RuntimeError(f"MCP {method} returned error", parsed.get("error"))
    return parsed, response_headers


def _decode_jsonrpc_body(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        raise RuntimeError("empty MCP response body")
    try:
        parsed = json.loads(text)
    except Exception:
        return _decode_sse_json(text)
    if isinstance(parsed, dict):
        return parsed
    return _decode_sse_json(text)


def _initialize_mcp_session(*, mcp_url: str, timeout_seconds: float) -> dict[str, Any]:
    handshake = mcp_http_initialize_handshake(
        mcp_url,
        client_name=DEFAULT_MCP_CLIENT_NAME,
        client_version=DEFAULT_MCP_CLIENT_VERSION,
        protocol_version=DEFAULT_MCP_PROTOCOL_VERSION,
        timeout_sec=max(5.0, min(float(timeout_seconds), 30.0)),
    )
    return {
        "protocol_version": str(handshake.session.protocol_version or DEFAULT_MCP_PROTOCOL_VERSION),
        "session_id": str(handshake.session.session_id or "").strip(),
    }


def _decode_sse_json(raw: str) -> dict[str, Any]:
    latest: dict[str, Any] | None = None
    for line in str(raw or "").splitlines():
        if line.startswith("data: "):
            payload = line[len("data: ") :].strip()
            if not payload or payload == "[DONE]":
                continue
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                latest = parsed
    if latest is not None:
        return latest
    raise RuntimeError(f"unable to decode SSE JSON payload: {raw!r}")


def _json_fragment_from_text(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _non_json_tool_text_detail(text: str) -> dict[str, Any]:
    raw_text = str(text or "").strip()
    lower = raw_text.lower()
    detail: dict[str, Any] = {
        "raw_text_preview": raw_text[:1200],
    }
    status_match = re.search(r"\bHTTP\s+(\d{3})\b", raw_text, flags=re.IGNORECASE)
    if status_match:
        detail["http_status"] = int(status_match.group(1))
    if "chatgpt_frontend_rate_limit_active" in raw_text:
        detail["error"] = "chatgpt_frontend_rate_limit_active"
    if "frontend_rate_limit" in raw_text:
        detail["reason"] = "frontend_rate_limit"
    retry_match = re.search(r'"?retry_after_seconds"?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)', raw_text)
    if retry_match:
        detail["retry_after_seconds"] = float(retry_match.group(1))
    parsed = _json_fragment_from_text(raw_text)
    if parsed is not None:
        detail["parsed_error"] = parsed
        nested = parsed.get("detail") if isinstance(parsed.get("detail"), dict) else parsed
        if isinstance(nested, dict):
            for key in ("error", "reason", "retry_after_seconds", "seconds_until_exp"):
                if key in nested and key not in detail:
                    detail[key] = nested.get(key)
    if "429" in lower and "http_status" not in detail:
        detail["http_status"] = 429
    return detail


def _decode_tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("invalid MCP tool result payload", payload)
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    for item in list(result.get("content") or []):
        if not isinstance(item, dict) or str(item.get("type") or "") != "text":
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "MCP tool returned non-JSON text response",
                _non_json_tool_text_detail(text),
            ) from exc
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError("unable to decode MCP tool response", payload)


def _runtime_error_detail(exc: BaseException) -> dict[str, Any] | None:
    args = getattr(exc, "args", ())
    if len(args) > 1 and isinstance(args[1], dict):
        return dict(args[1])
    return None


def _non_empty(v: str) -> str:
    s = str(v or "").strip()
    if not s:
        raise argparse.ArgumentTypeError("value must be non-empty")
    return s


def _default_preset(provider: str) -> str:
    if provider == "chatgpt":
        return "pro_extended"
    if provider == "gemini":
        return "pro"
    if provider == "qwen":
        return "auto"
    return "auto"


def _kind_for_provider(provider: str) -> str:
    if provider == "chatgpt":
        return "chatgpt_web.ask"
    if provider == "gemini":
        return "gemini_web.ask"
    if provider == "qwen":
        return "qwen_web.ask"
    raise ValueError(f"unsupported provider: {provider}")


_PRO_PRESETS = frozenset(
    {
        "pro_extended",
        "thinking_extended",
        "thinking_heavy",
        "deep_research",
        "pro",
    }
)


def _is_pro_preset(preset: str) -> bool:
    p = str(preset or "").strip().lower()
    if p in {"research", "deep-research", "deepresearch"}:
        return True
    return p in _PRO_PRESETS


def _is_trivial_prompt(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return True
    normalized = re.sub(r"\s+", "", s).lower()
    trivial_exact = {
        "ok",
        "yes",
        "no",
        "ping",
        "test",
        "hello",
        "你好",
        "测试",
        "请回复ok",
        "回复ok",
    }
    if normalized in trivial_exact:
        return True
    if re.fullmatch(r"[a-zA-Z]{1,4}", s):
        return True
    if re.fullmatch(r"[0-9]{1,4}", s):
        return True
    if re.fullmatch(r"(请)?回复\s*ok[.!?。！？]?", s, flags=re.IGNORECASE):
        return True
    return False


def _load_interval_state(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {}


def _looks_like_conversation_not_ready(err: Any) -> bool:
    if isinstance(err, dict):
        status = err.get("status")
        if int(status or 0) == 409:
            return True
        body = err.get("body")
        if isinstance(body, dict):
            detail = body.get("detail")
            if isinstance(detail, dict):
                text = json.dumps(detail, ensure_ascii=False).lower()
                if "conversation export not ready" in text:
                    return True
    text = str(err or "").lower()
    return "conversation export not ready" in text


def _save_interval_state(path: Path, *, ts: float, provider: str, preset: str, idempotency_key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_send_ts": float(ts),
        "provider": str(provider),
        "preset": str(preset),
        "idempotency_key": str(idempotency_key),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _enforce_min_interval(
    *,
    path: Path,
    min_interval_seconds: float,
    provider: str,
    preset: str,
    idempotency_key: str,
) -> dict[str, Any]:
    state = _load_interval_state(path)
    now = time.time()
    last_ts = float(state.get("last_send_ts") or 0.0)
    wait_seconds = max(0.0, (last_ts + float(min_interval_seconds)) - now)
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    sent_at = time.time()
    _save_interval_state(path, ts=sent_at, provider=provider, preset=preset, idempotency_key=idempotency_key)
    return {
        "state_file": str(path),
        "min_interval_seconds": float(min_interval_seconds),
        "last_send_ts": last_ts,
        "waited_seconds": round(wait_seconds, 3),
        "sent_at": sent_at,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Agent-first ChatgptREST call wrapper (JSON out).")
    p.add_argument("--chatgptrest-root", default=DEFAULT_CHATGPTREST_ROOT)
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--public-mcp-url", default=DEFAULT_PUBLIC_MCP_URL)
    p.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=0.0,
        help="Transport timeout for the MCP/HTTP call. In agent mode this auto-derives from the total run budget unless explicitly set.",
    )

    p.add_argument(
        "--agent",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use public MCP mode (default: true). Canonical surface is automation-kernel-v1; set --no-agent together with --maintenance-legacy-jobs only for controlled legacy maintenance",
    )
    p.add_argument(
        "--maintenance-legacy-jobs",
        action="store_true",
        help="Acknowledge that legacy provider-first jobs mode is maintenance-only and must not be used by coding agents as a default path",
    )
    p.add_argument(
        "--provider",
        choices=["chatgpt", "gemini", "qwen"],
        default="chatgpt",
        help="Provider for automation-kernel-v1 (chatgpt or gemini recommended); legacy mode also honors it",
    )
    p.add_argument(
        "--preset",
        default="",
        help="Preset for automation-kernel-v1; defaults per provider when omitted",
    )
    p.add_argument("--question", default="")
    p.add_argument("--idempotency-key", default="")
    p.add_argument(
        "--purpose",
        choices=["prod", "smoke"],
        default="prod",
        help="prod: real task; smoke: health/sanity check",
    )
    p.add_argument(
        "--allow-pro-smoke",
        action="store_true",
        help="Allow smoke tests to run on ChatGPT Pro presets",
    )
    p.add_argument(
        "--allow-trivial-pro",
        action="store_true",
        help="Allow very short/trivial prompts on Pro (not recommended)",
    )

    p.add_argument("--conversation-url", default="")
    p.add_argument("--parent-job-id", default="")
    p.add_argument("--file-path", action="append", default=[])
    p.add_argument("--github-repo", default="")

    p.add_argument("--session-id", default="", help="Session ID for agent continuity")
    p.add_argument(
        "--agent-surface",
        default=DEFAULT_AGENT_SURFACE,
        help="Public MCP contract surface to target (automation-kernel-v1 only)",
    )
    p.add_argument("--project-id", default="", help="Deprecated compatibility arg; rejected on automation-kernel-v1")
    p.add_argument("--role-id", default="", help="Deprecated compatibility arg; rejected on automation-kernel-v1")
    p.add_argument("--user-id", default="", help="Deprecated compatibility arg; rejected on automation-kernel-v1")
    p.add_argument("--trace-id", default="", help="Trace ID for request tracing")
    p.add_argument("--goal-hint", default="", help="Goal hint for agent (code_review, research, image, report, repair)")
    p.add_argument("--depth", default="standard", choices=["light", "standard", "deep", "heavy", "thinking_heavy"], help="Agent execution depth")
    p.add_argument(
        "--execution-profile",
        default="",
        help="Deprecated compatibility arg; rejected on automation-kernel-v1",
    )
    p.add_argument("--task-intake-json", default="{}", help="Canonical task_intake JSON object")
    p.add_argument("--task-intake-file", default="", help="Path to canonical task_intake JSON object file")
    p.add_argument("--workspace-request-json", default="{}", help="Workspace request JSON object")
    p.add_argument("--workspace-request-file", default="", help="Path to workspace request JSON object file")
    p.add_argument("--contract-patch-json", default="{}", help="Contract patch JSON object")
    p.add_argument("--contract-patch-file", default="", help="Path to contract patch JSON object file")
    p.add_argument("--preflight-json", default="{}", help="Automation preflight checklist JSON object")
    p.add_argument("--preflight-file", default="", help="Path to automation preflight checklist JSON object file")
    p.add_argument("--provider-selection-json", default="{}", help="Provider selection rationale JSON object")
    p.add_argument("--provider-selection-file", default="", help="Path to provider selection rationale JSON object file")
    p.add_argument("--client-context-json", default="{}", help="Client context JSON object for downstream push hooks")
    p.add_argument("--client-context-file", default="", help="Path to client context JSON object file")
    p.add_argument(
        "--delivery-preference",
        default="push_only",
        choices=["push_only", "push_plus_cache"],
        help="Canonical automation delivery mode; push_only is the default and foreground wait is not used by this wrapper",
    )

    p.add_argument("--deep-research", action="store_true")
    p.add_argument("--web-search", action="store_true")
    p.add_argument("--agent-mode", action="store_true")
    p.add_argument("--allow-queue", action="store_true")
    p.add_argument("--enable-import-code", action="store_true")
    p.add_argument("--drive-name-fallback", action="store_true")

    p.add_argument("--job-timeout-seconds", dest="timeout_seconds", type=int, default=0)
    p.add_argument("--timeout-seconds", dest="timeout_seconds", type=int, default=0, help=argparse.SUPPRESS)
    p.add_argument("--send-timeout-seconds", type=int, default=0)
    p.add_argument("--wait-timeout-seconds", type=int, default=0)
    p.add_argument("--max-wait-seconds", type=int, default=0)
    p.add_argument("--min-chars", type=int, default=0)
    p.add_argument("--answer-format", choices=["markdown", "text"], default="markdown")

    p.add_argument("--run-wait-timeout-seconds", type=float, default=900.0)
    p.add_argument("--run-poll-seconds", type=float, default=1.0)
    p.add_argument("--run-auto-wait-cooldown", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--skip-answer", action="store_true")
    p.add_argument("--answer-max-chars", type=int, default=8000)

    p.add_argument("--out-answer", default="")
    p.add_argument("--out-conversation", default="")
    p.add_argument("--conversation-max-chars", type=int, default=8000)
    p.add_argument("--conversation-retries", type=int, default=3)
    p.add_argument("--conversation-retry-sleep-seconds", type=float, default=3.0)
    p.add_argument("--out-summary", default="")
    p.add_argument(
        "--enforce-min-interval",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enforce minimal interval before sending ChatGPT Pro requests",
    )
    p.add_argument("--min-send-interval-seconds", type=float, default=61.0)
    p.add_argument("--interval-state-file", default=DEFAULT_INTERVAL_STATE_FILE)
    p.add_argument(
        "--serialize-chatgpt-review-lane",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Serialize ChatGPT Pro review-style agent calls on the shared CDP lane",
    )
    p.add_argument("--chatgpt-review-lane-lock-file", default=DEFAULT_CHATGPT_REVIEW_LANE_LOCK_FILE)
    p.add_argument("--chatgpt-review-lane-lock-timeout-seconds", type=float, default=DEFAULT_CHATGPT_REVIEW_LANE_LOCK_TIMEOUT_SECONDS)
    p.add_argument("--same-session-repair-max-attempts", type=int, default=DEFAULT_AGENT_SAME_SESSION_REPAIR_MAX_ATTEMPTS)
    return p


def _python_bin(chatgptrest_root: Path) -> Path:
    venv_python = (chatgptrest_root / ".venv" / "bin" / "python").resolve()
    if venv_python.exists():
        return venv_python
    return Path(sys.executable).resolve()


def _build_base_cli(python_bin: Path, base_url: str, request_timeout_seconds: float) -> list[str]:
    return [
        str(python_bin),
        "-m",
        "chatgptrest.cli",
        "--base-url",
        str(base_url),
        "--timeout-seconds",
        str(float(request_timeout_seconds)),
        "--output",
        "json",
    ]


def _append_if(cmd: list[str], key: str, value: str) -> None:
    if str(value or "").strip():
        cmd.extend([key, str(value).strip()])


def _append_int_if_positive(cmd: list[str], key: str, value: int) -> None:
    if int(value) > 0:
        cmd.extend([key, str(int(value))])


def _resolved_root(path_like: Any) -> Path:
    return Path(str(path_like)).expanduser().resolve(strict=False)


def _resolve_agent_timeout_seconds(args: argparse.Namespace) -> int:
    if int(args.timeout_seconds or 0) > 0:
        return int(args.timeout_seconds)
    provider = str(getattr(args, "provider", "") or "").strip().lower()
    preset = str(getattr(args, "preset", "") or "").strip() or _default_preset(provider)
    if provider == "chatgpt" and _is_pro_preset(preset):
        if bool(getattr(args, "deep_research", False)):
            return DEFAULT_CHATGPT_DEEP_RESEARCH_AGENT_TIMEOUT_SECONDS
        return DEFAULT_CHATGPT_PRO_AGENT_TIMEOUT_SECONDS
    return DEFAULT_AGENT_TIMEOUT_SECONDS


def _resolve_request_timeout_seconds(*, args: argparse.Namespace, agent_mode: bool) -> float:
    explicit = float(args.request_timeout_seconds or 0.0)
    if explicit > 0:
        return explicit
    if agent_mode:
        return max(DEFAULT_AGENT_REQUEST_TIMEOUT_SECONDS, float(_resolve_agent_timeout_seconds(args)) + 30.0)
    return max(DEFAULT_LEGACY_REQUEST_TIMEOUT_SECONDS, float(args.run_wait_timeout_seconds or 0.0) + 30.0)


def _agent_legacy_only_overrides(args: argparse.Namespace) -> list[str]:
    flags: list[str] = []
    if float(args.run_wait_timeout_seconds or 0.0) != 900.0:
        flags.append("--run-wait-timeout-seconds")
    if float(args.run_poll_seconds or 0.0) != 1.0:
        flags.append("--run-poll-seconds")
    if bool(args.run_auto_wait_cooldown) is False:
        flags.append("--no-run-auto-wait-cooldown")
    if bool(args.skip_answer):
        flags.append("--skip-answer")
    if str(args.out_answer or "").strip():
        flags.append("--out-answer/--out")
    if str(args.out_conversation or "").strip():
        flags.append("--out-conversation")
    if int(args.conversation_retries or 0) != 3:
        flags.append("--conversation-retries")
    if float(args.conversation_retry_sleep_seconds or 0.0) != 3.0:
        flags.append("--conversation-retry-sleep-seconds")
    return flags


def _agent_tool_names(surface: str) -> dict[str, str]:
    normalized = str(surface or "").strip().lower() or DEFAULT_AGENT_SURFACE
    if normalized != "automation-kernel-v1":
        raise RuntimeError(
            "public compatibility surfaces were removed from the shared MCP",
            {
                "requested_surface": normalized,
                "supported_surface": "automation-kernel-v1",
                "hint": "Use the automation kernel only. Task-intake, workspace routing, coding/advisor facade, and broad task understanding now belong in Hermes or the caller-side workflow.",
            },
        )
    return {
        "turn": "automation_ask",
        "events": "automation_job_events",
        "status": "automation_job_status",
        "answer": "automation_result",
        "cancel": "automation_job_cancel",
    }


def _agent_surface_was_explicit(argv: list[str] | None) -> bool:
    raw = list(argv or [])
    return "--agent-surface" in raw


def _looks_like_broad_review_intent(question: str) -> bool:
    text = str(question or "").strip().lower()
    if not text:
        return False
    needles = (
        "review repo",
        "review this repo",
        "code review",
        "审查",
        "评审",
        "代码评审",
    )
    return any(needle in text for needle in needles)


def _resolve_agent_surface(
    *,
    args: argparse.Namespace,
    question: str,
    task_intake_obj: dict[str, Any],
    workspace_request_obj: dict[str, Any],
    contract_patch_obj: dict[str, Any],
    explicit_surface: bool,
) -> str:
    requested = str(getattr(args, "agent_surface", DEFAULT_AGENT_SURFACE) or DEFAULT_AGENT_SURFACE).strip().lower()
    if explicit_surface:
        return requested or DEFAULT_AGENT_SURFACE
    return DEFAULT_AGENT_SURFACE


def _agent_surface_requires_question(surface: str) -> bool:
    return True


def _validate_automation_surface_args(
    *,
    args: argparse.Namespace,
    question: str,
    task_intake_obj: dict[str, Any],
    workspace_request_obj: dict[str, Any],
    contract_patch_obj: dict[str, Any],
) -> None:
    if not question:
        raise RuntimeError(
            "automation-kernel-v1 requires --question",
            {"hint": "Provide --question. Broad task-intake/workspace routing is no longer part of the shared public MCP."},
        )
    if task_intake_obj:
        raise RuntimeError(
            "automation-kernel-v1 does not accept task_intake",
            {"hint": "Move task_intake semantics to Hermes or the caller-side workflow; public MCP only accepts explicit automation asks."},
        )
    if workspace_request_obj:
        raise RuntimeError(
            "automation-kernel-v1 does not accept workspace_request",
            {"hint": "Move workspace_request handling to Hermes or the caller-side workflow; public MCP only accepts explicit automation asks."},
        )
    if contract_patch_obj:
        raise RuntimeError(
            "automation-kernel-v1 does not accept contract_patch",
            {"hint": "Move contract patching to Hermes or the caller-side workflow; public MCP only accepts explicit automation asks."},
        )
    if str(args.project_id or "").strip():
        raise RuntimeError(
            "automation-kernel-v1 does not accept --project-id",
            {"hint": "coding-agent-v1 was removed from the shared public MCP. Use automation-kernel-v1 only."},
        )
    if str(args.role_id or "").strip():
        raise RuntimeError(
            "automation-kernel-v1 does not accept --role-id",
            {"hint": "Role-bound turns no longer belong to the shared public MCP. Resolve them in Hermes or the caller workflow before submitting automation."},
        )
    if str(args.user_id or "").strip():
        raise RuntimeError(
            "automation-kernel-v1 does not accept --user-id",
            {"hint": "User-bound turns no longer belong to the shared public MCP. Resolve them in Hermes or the caller workflow before submitting automation."},
        )
    depth = str(args.depth or "").strip().lower()
    if depth and depth not in {"", "standard", "thinking_heavy"}:
        raise RuntimeError(
            "automation-kernel-v1 does not accept non-default --depth",
            {"hint": "Choose provider/preset explicitly instead of using advisor-style depth routing."},
        )
    if str(args.execution_profile or "").strip():
        raise RuntimeError(
            "automation-kernel-v1 does not accept --execution-profile",
            {"hint": "Choose --provider/--preset/--deep-research explicitly on automation-kernel-v1; routing profiles are no longer part of the shared public MCP."},
        )
    provider = str(args.provider or "").strip().lower()
    if provider not in _AUTOMATION_ALLOWED_PROVIDERS:
        raise RuntimeError(
            "unsupported provider for automation-kernel-v1",
            {
                "provider": provider,
                "allowed": sorted(_AUTOMATION_ALLOWED_PROVIDERS),
                "hint": "Use chatgpt or gemini on automation-kernel-v1; other providers stay on explicit maintenance lanes.",
            },
        )


def _validate_agent_mode_args(args: argparse.Namespace) -> tuple[int, float]:
    legacy_only = _agent_legacy_only_overrides(args)
    if legacy_only:
        joined = ", ".join(legacy_only)
        raise RuntimeError(
            "agent mode does not support legacy jobs wait/export flags",
            {
                "unsupported_flags": legacy_only,
                "message": f"The following flags only apply to --no-agent legacy jobs mode: {joined}",
                "hint": "Use --job-timeout-seconds/--timeout-seconds as the total agent run budget and let --request-timeout-seconds auto-derive, or switch to --no-agent --maintenance-legacy-jobs for the legacy jobs surface.",
            },
        )
    agent_timeout_seconds = _resolve_agent_timeout_seconds(args)
    request_timeout_seconds = _resolve_request_timeout_seconds(args=args, agent_mode=True)
    explicit_request_timeout = float(args.request_timeout_seconds or 0.0)
    if explicit_request_timeout > 0 and explicit_request_timeout < float(agent_timeout_seconds):
        raise RuntimeError(
            "agent transport timeout is shorter than the requested run budget",
            {
                "request_timeout_seconds": explicit_request_timeout,
                "agent_timeout_seconds": agent_timeout_seconds,
                "hint": "Omit --request-timeout-seconds for auto-derive, or set it >= the agent run budget.",
            },
        )
    return agent_timeout_seconds, request_timeout_seconds


def _runtime_payload(*, chatgptrest_root: Path, python_bin: Path, command: list[str] | None = None, request_timeout_seconds: float = 0.0) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "chatgptrest_root": str(chatgptrest_root),
        "python_bin": str(python_bin),
    }
    if request_timeout_seconds > 0:
        payload["request_timeout_seconds"] = float(request_timeout_seconds)
    if command is not None:
        payload["command"] = list(command)
    return payload


def _looks_like_transport_timeout(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout, urllib.error.URLError, http.client.RemoteDisconnected, http.client.IncompleteRead)):
        return True
    text = str(exc or "").lower()
    return any(
        marker in text
        for marker in (
            "timed out",
            "read timed out",
            "gateway timeout",
            "http 504",
            "remote end closed connection",
            "remote disconnected",
            "sse stream timeout",
            "incomplete read",
        )
    )


def _iter_exception_chain(exc: BaseException) -> list[BaseException]:
    out: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        out.append(current)
        seen.add(id(current))
        current = current.__cause__ or (
            None if getattr(current, "__suppress_context__", False) else current.__context__
        )
    return out


def _still_running_possible_after_failure(exc: BaseException) -> bool:
    return any(_looks_like_transport_timeout(candidate) for candidate in _iter_exception_chain(exc))


def _looks_like_wait_transport_recoverable(exc: BaseException) -> bool:
    if _looks_like_transport_timeout(exc):
        return True
    text = str(exc or "").lower()
    return any(
        marker in text
        for marker in (
            "unable to decode sse json payload",
            "incomplete mcp response",
            ": ping - ",
        )
    )


def _session_terminal_status(status: str) -> bool:
    return str(status or "").strip().lower() in {
        "completed",
        "failed",
        "cancelled",
        "canceled",
        "needs_followup",
        "needs_input",
    }


def _run_agent_wait_with_recovery(
    *,
    mcp_url: str,
    session_id: str,
    agent_timeout_seconds: int,
    request_timeout_seconds: float,
    request_id: int,
    wait_tool_name: str,
    status_tool_name: str,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deadline = time.time() + max(0.0, float(agent_timeout_seconds))
    attempts = 0
    last_exc: BaseException | None = None
    last_status: dict[str, Any] | None = None
    last_status_exc: BaseException | None = None

    def _refresh_mcp_session(reason: str) -> dict[str, Any] | None:
        if not isinstance(session, dict):
            return None
        refreshed = _initialize_mcp_session(
            mcp_url=str(mcp_url),
            timeout_seconds=max(5.0, min(float(request_timeout_seconds), 30.0)),
        )
        session.clear()
        session.update(refreshed)
        session["refreshed_after"] = str(reason)
        return dict(session)

    while True:
        remaining = max(1, int(round(deadline - time.time())))
        attempts += 1
        try:
            result = _run_mcp_tool(
                mcp_url=str(mcp_url),
                tool_name=str(wait_tool_name),
                arguments={
                    "session_id": str(session_id),
                    "timeout_seconds": remaining,
                },
                timeout_seconds=max(float(request_timeout_seconds), float(remaining) + 30.0),
                request_id=request_id + attempts - 1,
                session=session,
            )
            if attempts > 1:
                result.setdefault("wait_transport_recovered", True)
                result.setdefault("wait_transport_retry_count", attempts - 1)
            return result
        except Exception as exc:
            last_exc = exc
            if not _looks_like_wait_transport_recoverable(exc):
                raise
            try:
                status_result = _run_mcp_tool(
                    mcp_url=str(mcp_url),
                    tool_name=str(status_tool_name),
                    arguments={"session_id": str(session_id)},
                    timeout_seconds=max(5.0, min(float(request_timeout_seconds), 30.0)),
                    request_id=request_id + 100 + attempts,
                    session=session,
                )
            except Exception as status_exc:
                last_status_exc = status_exc
                if not _looks_like_wait_transport_recoverable(status_exc):
                    raise
            else:
                if isinstance(status_result, dict):
                    last_status = dict(status_result)
                    last_status.setdefault("wait_transport_recovered", True)
                    last_status.setdefault("wait_transport_retry_count", attempts)
                    if _session_terminal_status(str(last_status.get("status") or "")):
                        last_status.setdefault("wait_transport_resolution", "status_after_wait_transport_failure")
                        return last_status
            if attempts < 3 and time.time() < deadline:
                try:
                    _refresh_mcp_session("wait_transport_failure")
                except Exception as refresh_exc:
                    if not _looks_like_wait_transport_recoverable(refresh_exc):
                        raise
                    last_status_exc = refresh_exc
            if time.time() >= deadline or attempts >= 3:
                break
            time.sleep(min(2.0, 0.5 * attempts))
    detail = {
        "session_id": str(session_id),
        "attempts": attempts,
        "status_after_failure": dict(last_status or {}),
        "status_error": (
            {
                "error_type": type(last_status_exc).__name__ or "RuntimeError",
                "message": str(last_status_exc.args[0]) if getattr(last_status_exc, "args", ()) else str(last_status_exc),
            }
            if last_status_exc is not None
            else None
        ),
        "wait_tool_name": str(wait_tool_name),
        "status_tool_name": str(status_tool_name),
    }
    raise RuntimeError(f"{wait_tool_name} transport recovery exhausted", detail) from last_exc


def _agent_prefers_background_delivery(args: argparse.Namespace) -> bool:
    goal_hint = str(args.goal_hint or "").strip().lower()
    if goal_hint in _AGENT_BACKGROUND_GOAL_HINTS:
        return True
    if str(args.github_repo or "").strip():
        return True
    if bool(args.file_path):
        return True
    if bool(args.enable_import_code):
        return True
    if str(args.execution_profile or "").strip().lower() in {"thinking_heavy", "deep_research", "report_grade"}:
        return True
    return str(args.depth or "").strip().lower() in {"deep", "heavy", "thinking_heavy"}


def _merge_turn_wait_result(turn_result: dict[str, Any], wait_result: dict[str, Any]) -> dict[str, Any]:
    merged = dict(wait_result)
    handoff = {
        "delivery_mode_requested": turn_result.get("delivery_mode_requested"),
        "delivery_mode_effective": turn_result.get("delivery_mode_effective"),
        "accepted_for_background": turn_result.get("accepted_for_background"),
        "why_sync_was_not_possible": turn_result.get("why_sync_was_not_possible"),
        "recommended_client_action": turn_result.get("recommended_client_action"),
        "wait_tool": turn_result.get("wait_tool"),
        "turn_accept": {
            "accepted": bool(turn_result.get("accepted")),
            "status": str(turn_result.get("status") or ""),
            "delivery": dict(turn_result.get("delivery") or {}),
        },
    }
    for key, value in handoff.items():
        if key not in merged and value not in (None, "", {}):
            merged[key] = value
    return merged


def _maybe_fetch_agent_canonical_answer(
    *,
    result: dict[str, Any],
    mcp_url: str,
    session: dict[str, Any] | None,
    request_timeout_seconds: float,
    request_id: int,
    answer_tool_name: str,
) -> dict[str, Any]:
    answer_state = str(result.get("answer_state") or "").strip().lower()
    authoritative_job_id = str(result.get("authoritative_job_id") or "").strip()
    authoritative_answer_path = str(result.get("authoritative_answer_path") or "").strip()
    session_id = str(result.get("session_id") or "").strip()
    if (
        answer_state != "final"
        or not session_id
        or not (authoritative_job_id or authoritative_answer_path)
    ):
        return result
    answer_result = _run_mcp_tool(
        mcp_url=str(mcp_url),
        tool_name=str(answer_tool_name),
        arguments={
            "session_id": session_id,
            "offset": 0,
            "max_chars": 80000,
        },
        timeout_seconds=max(30.0, float(request_timeout_seconds)),
        request_id=request_id,
        session=session,
    )
    if not isinstance(answer_result, dict) or not answer_result.get("ok"):
        return result
    canonical_answer = str(answer_result.get("answer") or "")
    if not canonical_answer:
        return result
    merged = dict(result)
    merged["canonical_answer"] = canonical_answer
    merged["answer_fetch"] = {
        "source": str(answer_result.get("source") or ""),
        "answer_chars": int(answer_result.get("answer_chars") or len(canonical_answer)),
        "has_more": bool(answer_result.get("has_more")),
    }
    if len(canonical_answer) > len(str(merged.get("last_answer") or "")):
        merged["last_answer"] = canonical_answer
    if len(canonical_answer) > len(str(merged.get("answer") or "")):
        merged["answer"] = canonical_answer
    return merged


def _automation_terminal_status(status: str) -> bool:
    return str(status or "").strip().lower() in _AUTOMATION_TERMINAL_STATUSES


def _validate_automation_prompt_policy(
    *,
    provider: str,
    preset: str,
    purpose: str,
    question: str,
    allow_pro_smoke: bool,
    allow_trivial_pro: bool,
) -> None:
    if purpose == "smoke" and _is_pro_preset(preset) and not allow_pro_smoke:
        raise RuntimeError(
            f"smoke test on Pro preset is blocked for provider={provider}; use non-Pro preset or pass --allow-pro-smoke",
            {"provider": provider, "preset": preset},
        )
    if provider == "chatgpt" and _is_pro_preset(preset) and _is_trivial_prompt(question) and not allow_trivial_pro:
        raise RuntimeError(
            "trivial prompt on ChatGPT Pro is blocked; provide a non-trivial prompt or pass --allow-trivial-pro",
            {"provider": provider, "preset": preset},
        )


def _looks_over_closed_prompt(question: str) -> bool:
    text = str(question or "").strip()
    if not text:
        return True
    if len(text) <= 10 and text.endswith(("?", "？", "吗")):
        return True
    lowered = text.lower()
    if len(text.split()) <= 6 and lowered.startswith(("is ", "are ", "can ", "should ", "do ", "does ")):
        return True
    return False


def _looks_like_output_defined(question: str) -> bool:
    text = str(question or "").strip()
    if not text:
        return False
    signals = (
        "总结",
        "评审",
        "分析",
        "给出",
        "生成",
        "撰写",
        "判断",
        "建议",
        "结论",
        "memo",
        "review",
        "analyze",
        "summary",
    )
    lowered = text.lower()
    return any(signal in text or signal in lowered for signal in signals)


def _build_default_automation_preflight(
    *,
    args: argparse.Namespace,
    question: str,
    preset: str,
    purpose: str,
) -> dict[str, Any]:
    followup_requested = bool(str(args.parent_job_id or "").strip() or str(args.conversation_url or "").strip())
    return {
        "task_goal_clear": bool(question) and not _is_trivial_prompt(question),
        "expected_output_defined": _looks_like_output_defined(question) or bool(str(args.goal_hint or "").strip()),
        "attachments_complete": True,
        "followup_context_present": True if not followup_requested else True,
        "provider_justified": True,
        "premium_justified": (not _is_pro_preset(preset)) or (purpose != "smoke" and not _is_trivial_prompt(question)),
        "question_not_trivial": not _is_trivial_prompt(question),
        "question_not_over_closed": not _looks_over_closed_prompt(question),
        "known_gaps": [],
        "generated_by": "chatgptrest_call_wrapper",
    }


def _build_default_provider_selection(
    *,
    args: argparse.Namespace,
    provider: str,
    preset: str,
) -> dict[str, Any]:
    reason_parts: list[str] = []
    if str(args.goal_hint or "").strip():
        reason_parts.append(f"goal_hint={str(args.goal_hint).strip()}")
    if bool(args.deep_research):
        reason_parts.append("explicit_deep_research")
    if bool(args.file_path):
        reason_parts.append(f"attachments={len(list(args.file_path or []))}")
    if not reason_parts:
        reason_parts.append("explicit_provider_and_preset")
    return {
        "requested_provider": provider,
        "requested_preset": preset,
        "reason": "; ".join(reason_parts),
        "alternatives_considered": [],
        "generated_by": "chatgptrest_call_wrapper",
    }


def _normalize_local_file_paths(paths: list[str] | tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    for raw in paths or []:
        text = str(raw or "").strip()
        if not text:
            continue
        path = Path(text).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path)
        normalized.append(path.resolve(strict=False).as_posix())
    return normalized


def _merge_automation_turn_wait_result(turn_result: dict[str, Any], wait_result: dict[str, Any]) -> dict[str, Any]:
    merged = dict(turn_result or {})
    merged.update(dict(wait_result or {}))
    for key in ("job_id", "provider", "kind", "action_hint", "background_wait", "estimated_wait_seconds"):
        if key not in merged and key in turn_result:
            merged[key] = turn_result.get(key)
    return merged


def _run_automation_turn(
    *,
    args: argparse.Namespace,
    question: str,
    request_timeout_seconds: float,
    agent_timeout_seconds: int,
    tool_names: dict[str, str],
    preflight_obj: dict[str, Any],
    provider_selection_obj: dict[str, Any],
    client_context_obj: dict[str, Any],
) -> int:
    provider = str(args.provider or "").strip().lower()
    preset = str(args.preset or "").strip() or _default_preset(provider)
    purpose = str(args.purpose or "prod").strip().lower()
    normalized_file_paths = _normalize_local_file_paths(list(args.file_path or []))
    args.file_path = normalized_file_paths
    idempotency_key = str(args.idempotency_key or "").strip() or (
        f"skill-{provider}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    )
    _validate_automation_prompt_policy(
        provider=provider,
        preset=preset,
        purpose=purpose,
        question=question,
        allow_pro_smoke=bool(args.allow_pro_smoke),
        allow_trivial_pro=bool(args.allow_trivial_pro),
    )

    interval_enforced: dict[str, Any] | None = None
    if provider == "chatgpt" and _is_pro_preset(preset) and bool(args.enforce_min_interval):
        interval_path = Path(str(args.interval_state_file)).expanduser()
        interval_enforced = _enforce_min_interval(
            path=interval_path,
            min_interval_seconds=max(0.0, float(args.min_send_interval_seconds)),
            provider=provider,
            preset=preset,
            idempotency_key=idempotency_key,
        )

    deep_research_value: bool | None = True if bool(args.deep_research) else None
    out_summary = str(args.out_summary or "").strip()
    runtime: dict[str, Any] = {
        "job_id": "",
        "status": "submitting",
        "provider": provider,
        "kind": _kind_for_provider(provider),
        "request_timeout_seconds": float(request_timeout_seconds),
        "agent_timeout_seconds": int(agent_timeout_seconds),
        "idempotency_key": idempotency_key,
        "file_paths": list(normalized_file_paths),
    }
    if out_summary:
        _write_automation_summary_snapshot(out_summary, runtime=runtime)

    mcp_session = _initialize_mcp_session(
        mcp_url=str(args.public_mcp_url),
        timeout_seconds=request_timeout_seconds,
    )
    lock_enabled = _chatgpt_review_lane_enabled(args, legacy_preset=preset)
    lock_path = Path(str(args.chatgpt_review_lane_lock_file)).expanduser().resolve()

    try:
        with _provider_lane_lock(
            enabled=lock_enabled,
            lock_path=lock_path,
            timeout_seconds=float(args.chatgpt_review_lane_lock_timeout_seconds or 0.0),
            metadata={
                "provider": provider,
                "preset": preset,
                "goal_hint": str(args.goal_hint or ""),
                "trace_id": str(args.trace_id or ""),
            },
        ):
            turn_result = _run_mcp_tool(
                mcp_url=str(args.public_mcp_url),
                tool_name=tool_names["turn"],
                arguments={
                    "idempotency_key": idempotency_key,
                    "question": question,
                    "provider": provider,
                    "preset": preset,
                    "parent_job_id": str(args.parent_job_id or "").strip(),
                    "conversation_url": str(args.conversation_url or "").strip(),
                    "file_paths": list(args.file_path or []),
                    "deep_research": deep_research_value,
                    "timeout_seconds": int(agent_timeout_seconds),
                    "max_wait_seconds": max(int(agent_timeout_seconds), 1800 if bool(args.deep_research) else int(agent_timeout_seconds)),
                    "min_chars": (int(args.min_chars) if int(args.min_chars or 0) > 0 else None),
                    "preflight": dict(preflight_obj),
                    "provider_selection": dict(provider_selection_obj),
                    "client_context": dict(client_context_obj),
                    "delivery_preference": str(args.delivery_preference or "push_only"),
                    "auto_wait": True,
                    "notify_done": True,
                },
                timeout_seconds=request_timeout_seconds,
                request_id=3,
                session=mcp_session,
            )
            result = dict(turn_result or {})
            job_id = str(result.get("job_id") or "").strip()
            runtime["job_id"] = job_id
            runtime["status"] = str(result.get("status") or "submitted")
            runtime["action_hint"] = str(result.get("action_hint") or "")
            if out_summary:
                _write_automation_summary_snapshot(out_summary, result=result, runtime=runtime)
        runtime["status"] = str(result.get("status") or runtime["status"])
        if out_summary:
            _write_automation_summary_snapshot(out_summary, result=result, runtime=runtime)
    except Exception as exc:
        detail = _runtime_error_detail(exc)
        err = {
            "ok": False,
            "error_type": type(exc).__name__,
            "message": str(getattr(exc, "args", [""])[0]) if getattr(exc, "args", ()) else str(exc),
            "surface": "automation-kernel-v1",
            "job_id": str(runtime.get("job_id") or ""),
            "provider": provider,
            "preset": preset,
            "idempotency_key": idempotency_key,
            "resolved_runtime": {
                "request_timeout_seconds": float(request_timeout_seconds),
                "agent_timeout_seconds": int(agent_timeout_seconds),
                "interval_enforced": interval_enforced,
            },
        }
        if detail is not None:
            err["detail"] = detail
        if out_summary:
            _write_summary_file(out_summary, err)
        print(_json_dump(err), file=sys.stderr)
        return 2

    if interval_enforced:
        result.setdefault("interval_enforced", interval_enforced)
    print(_json_dump(result))
    return 0


def _parse_json_obj(*, raw: str | None, path: str | None, field_name: str) -> dict[str, Any]:
    obj: Any = {}
    if raw and str(raw).strip():
        try:
            obj = json.loads(str(raw))
        except Exception as exc:
            raise RuntimeError(f"invalid JSON in {field_name}: {exc}") from exc
    if path and str(path).strip():
        file_path = Path(str(path)).expanduser()
        try:
            obj = json.loads(file_path.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            raise RuntimeError(f"failed to load JSON file for {field_name}: {file_path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise RuntimeError(f"{field_name} must be a JSON object")
    return dict(obj)


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(raw_argv)
    setattr(args, "_agent_surface_explicit", _agent_surface_was_explicit(raw_argv))
    runtime_env = _autoload_runtime_env()
    setattr(args, "_runtime_env_summary", runtime_env)

    root = _resolved_root(args.chatgptrest_root)
    python_bin = _python_bin(root)
    if not python_bin.exists():
        payload = {
            "ok": False,
            "error_type": "CliError",
            "message": f"python binary not found: {python_bin}",
            "resolved_runtime": {
                **_runtime_payload(chatgptrest_root=root, python_bin=python_bin),
                "runtime_env": runtime_env,
            },
        }
        print(_json_dump(payload), file=sys.stderr)
        return 2

    use_agent = bool(args.agent)

    if use_agent:
        if bool(args.maintenance_legacy_jobs):
            payload = {
                "ok": False,
                "error_type": "PolicyError",
                "message": "--maintenance-legacy-jobs only applies together with --no-agent",
                "resolved_runtime": {
                    **_runtime_payload(chatgptrest_root=root, python_bin=python_bin),
                    "runtime_env": runtime_env,
                },
            }
            print(_json_dump(payload), file=sys.stderr)
            return 2
        try:
            return _run_agent_turn(python_bin, args)
        except RuntimeError as exc:
            payload = {
                "ok": False,
                "error_type": "RuntimeError",
                "message": str(exc.args[0]) if exc.args else str(exc),
                "detail": (exc.args[1] if len(exc.args) > 1 else None),
                "resolved_runtime": {
                    **_runtime_payload(chatgptrest_root=root, python_bin=python_bin),
                    "runtime_env": runtime_env,
                },
            }
            print(_json_dump(payload), file=sys.stderr)
            return 2
    else:
        if not bool(args.maintenance_legacy_jobs):
            payload = {
                "ok": False,
                "error_type": "PolicyError",
                "message": "legacy provider-first mode is maintenance-only; use public automation-kernel-v1 MCP by default, or pass --maintenance-legacy-jobs for audited maintenance work",
                "resolved_runtime": {
                    **_runtime_payload(chatgptrest_root=root, python_bin=python_bin),
                    "runtime_env": runtime_env,
                },
            }
            print(_json_dump(payload), file=sys.stderr)
            return 2
        return _run_legacy_jobs(python_bin, args)


def _run_agent_turn(python_bin: Path, args: argparse.Namespace) -> int:
    question = str(args.question or "").strip()
    task_intake_obj = _parse_json_obj(
        raw=getattr(args, "task_intake_json", "{}"),
        path=getattr(args, "task_intake_file", ""),
        field_name="task_intake",
    )
    contract_patch_obj = _parse_json_obj(
        raw=getattr(args, "contract_patch_json", "{}"),
        path=getattr(args, "contract_patch_file", ""),
        field_name="contract_patch",
    )
    workspace_request_obj = _parse_json_obj(
        raw=getattr(args, "workspace_request_json", "{}"),
        path=getattr(args, "workspace_request_file", ""),
        field_name="workspace_request",
    )
    preflight_obj = _parse_json_obj(
        raw=getattr(args, "preflight_json", "{}"),
        path=getattr(args, "preflight_file", ""),
        field_name="preflight",
    )
    provider_selection_obj = _parse_json_obj(
        raw=getattr(args, "provider_selection_json", "{}"),
        path=getattr(args, "provider_selection_file", ""),
        field_name="provider_selection",
    )
    client_context_obj = _parse_json_obj(
        raw=getattr(args, "client_context_json", "{}"),
        path=getattr(args, "client_context_file", ""),
        field_name="client_context",
    )
    if not question:
        raise RuntimeError(
            "agent mode on automation-kernel-v1 requires --question",
            {
                "hint": "Broad task-intake, workspace routing, and contract patch flows no longer belong to the shared public MCP. Resolve them in Hermes or the caller workflow before submitting automation.",
            },
        )
    agent_surface = _resolve_agent_surface(
        args=args,
        question=question,
        task_intake_obj=task_intake_obj,
        workspace_request_obj=workspace_request_obj,
        contract_patch_obj=contract_patch_obj,
        explicit_surface=bool(getattr(args, "_agent_surface_explicit", False)),
    )
    tool_names = _agent_tool_names(agent_surface)
    _validate_automation_surface_args(
        args=args,
        question=question,
        task_intake_obj=task_intake_obj,
        workspace_request_obj=workspace_request_obj,
        contract_patch_obj=contract_patch_obj,
    )
    agent_timeout_seconds, request_timeout_seconds = _validate_agent_mode_args(args)
    provider = str(args.provider or "").strip().lower()
    preset = str(args.preset or "").strip() or _default_preset(provider)
    purpose = str(args.purpose or "prod").strip().lower()
    if not preflight_obj:
        preflight_obj = _build_default_automation_preflight(
            args=args,
            question=question,
            preset=preset,
            purpose=purpose,
        )
    if not provider_selection_obj:
        provider_selection_obj = _build_default_provider_selection(
            args=args,
            provider=provider,
            preset=preset,
        )
    return _run_automation_turn(
        args=args,
        question=question,
        request_timeout_seconds=request_timeout_seconds,
        agent_timeout_seconds=agent_timeout_seconds,
        tool_names=tool_names,
        preflight_obj=preflight_obj,
        provider_selection_obj=provider_selection_obj,
        client_context_obj=client_context_obj,
    )


def _run_legacy_jobs(python_bin: Path, args: argparse.Namespace) -> int:
    legacy_env = {"CHATGPTREST_CLIENT_NAME": DEFAULT_MAINT_LEGACY_CLIENT_NAME}
    root = _resolved_root(args.chatgptrest_root)
    runtime_env = dict(getattr(args, "_runtime_env_summary", {}) or {})
    provider = str(args.provider)
    kind = _kind_for_provider(provider)
    preset = str(args.preset or "").strip() or _default_preset(provider)
    purpose = str(args.purpose or "prod").strip().lower()
    request_timeout_seconds = _resolve_request_timeout_seconds(args=args, agent_mode=False)
    idempotency_key = str(args.idempotency_key or "").strip() or (
        f"skill-{provider}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    )
    question = str(args.question or "").strip()
    if not question:
        err = {
            "ok": False,
            "error_type": "CliError",
            "message": "legacy jobs mode requires --question",
        }
        print(_json_dump(err), file=sys.stderr)
        return 2

    if purpose == "smoke" and _is_pro_preset(preset) and not bool(args.allow_pro_smoke):
        err = {
            "ok": False,
            "error_type": "PolicyError",
            "message": f"smoke test on Pro preset is blocked for provider={provider}; use non-Pro preset or pass --allow-pro-smoke",
        }
        print(_json_dump(err), file=sys.stderr)
        return 2
    if provider == "chatgpt" and _is_pro_preset(preset) and _is_trivial_prompt(question) and not bool(args.allow_trivial_pro):
        err = {
            "ok": False,
            "error_type": "PolicyError",
            "message": "trivial prompt on ChatGPT Pro is blocked; provide a non-trivial prompt or pass --allow-trivial-pro",
        }
        print(_json_dump(err), file=sys.stderr)
        return 2

    interval_enforced: dict[str, Any] | None = None
    if provider == "chatgpt" and _is_pro_preset(preset) and bool(args.enforce_min_interval):
        interval_path = Path(str(args.interval_state_file)).expanduser()
        interval_enforced = _enforce_min_interval(
            path=interval_path,
            min_interval_seconds=max(0.0, float(args.min_send_interval_seconds)),
            provider=provider,
            preset=preset,
            idempotency_key=idempotency_key,
        )

    cmd = _build_base_cli(python_bin, str(args.base_url), request_timeout_seconds)
    cmd.extend([
        "jobs",
        "run",
        "--kind",
        kind,
        "--idempotency-key",
        idempotency_key,
        "--question",
        question,
        "--preset",
        preset,
        "--purpose",
        purpose,
        "--run-wait-timeout-seconds",
        str(float(args.run_wait_timeout_seconds)),
        "--run-poll-seconds",
        str(float(args.run_poll_seconds)),
        "--answer-format",
        str(args.answer_format),
        "--answer-max-chars",
        str(int(args.answer_max_chars)),
    ])

    _append_if(cmd, "--conversation-url", str(args.conversation_url))
    _append_if(cmd, "--parent-job-id", str(args.parent_job_id))
    _append_if(cmd, "--github-repo", str(args.github_repo))
    for p in (args.file_path or []):
        _append_if(cmd, "--file-path", str(p))

    if bool(args.deep_research):
        cmd.append("--deep-research")
    if bool(args.web_search):
        cmd.append("--web-search")
    if bool(args.agent_mode):
        cmd.append("--agent-mode")
    if bool(args.allow_queue):
        cmd.append("--allow-queue")
    if bool(args.enable_import_code):
        cmd.append("--enable-import-code")
    if bool(args.drive_name_fallback):
        cmd.append("--drive-name-fallback")

    _append_int_if_positive(cmd, "--job-timeout-seconds", int(args.timeout_seconds))
    _append_int_if_positive(cmd, "--send-timeout-seconds", int(args.send_timeout_seconds))
    _append_int_if_positive(cmd, "--wait-timeout-seconds", int(args.wait_timeout_seconds))
    _append_int_if_positive(cmd, "--max-wait-seconds", int(args.max_wait_seconds))
    _append_int_if_positive(cmd, "--min-chars", int(args.min_chars))

    if bool(args.skip_answer):
        cmd.append("--skip-answer")
    if bool(args.run_auto_wait_cooldown) is False:
        cmd.append("--no-run-auto-wait-cooldown")
    if str(args.out_answer or "").strip():
        cmd.extend(["--out", str(args.out_answer).strip()])

    try:
        run_obj = _run_json_command(cmd, env=legacy_env, cwd=root)
        submit = run_obj.get("submit") if isinstance(run_obj, dict) else None
        job = run_obj.get("job") if isinstance(run_obj, dict) else None
        answer = run_obj.get("answer") if isinstance(run_obj, dict) else None

        job_id = ""
        if isinstance(job, dict) and job.get("job_id"):
            job_id = str(job.get("job_id"))
        elif isinstance(submit, dict) and submit.get("job_id"):
            job_id = str(submit.get("job_id"))

        conversation_obj: dict[str, Any] | None = None
        if str(args.out_conversation or "").strip() and job_id:
            conv_cmd = _build_base_cli(python_bin, str(args.base_url), request_timeout_seconds)
            conv_cmd.extend(
                [
                    "jobs",
                    "conversation",
                    job_id,
                    "--all",
                    "--max-chars",
                    str(int(args.conversation_max_chars)),
                    "--out",
                    str(args.out_conversation).strip(),
                ]
            )
            conversation_attempts = max(1, int(args.conversation_retries) + 1)
            last_conv_error: RuntimeError | None = None
            for attempt in range(1, conversation_attempts + 1):
                try:
                    conversation_obj = _run_json_command(conv_cmd, env=legacy_env, cwd=root)
                    if isinstance(conversation_obj, dict):
                        conversation_obj.setdefault("attempts", attempt)
                    break
                except RuntimeError as exc:
                    last_conv_error = exc
                    detail = exc.args[1] if len(exc.args) > 1 else str(exc)
                    if attempt >= conversation_attempts or not _looks_like_conversation_not_ready(detail):
                        raise
                    time.sleep(max(0.0, float(args.conversation_retry_sleep_seconds)))
            if conversation_obj is None and last_conv_error is not None:
                raise last_conv_error

        summary: dict[str, Any] = {
            "ok": True,
            "mode": "legacy_jobs_maintenance",
            "client_name": DEFAULT_MAINT_LEGACY_CLIENT_NAME,
            "provider": provider,
            "kind": kind,
            "preset": preset,
            "purpose": purpose,
            "idempotency_key": idempotency_key,
            "job_id": job_id,
            "status": (job.get("status") if isinstance(job, dict) else None),
            "conversation_url": (job.get("conversation_url") if isinstance(job, dict) else None),
            "result": run_obj,
            "resolved_runtime": _runtime_payload(
                chatgptrest_root=root,
                python_bin=python_bin,
                command=cmd,
                request_timeout_seconds=request_timeout_seconds,
            )
            | {"runtime_env": runtime_env},
        }
        if interval_enforced is not None:
            summary["interval_enforced"] = interval_enforced
        if isinstance(answer, dict):
            summary["answer_chars"] = int(answer.get("returned_chars") or len(str(answer.get("chunk") or "")))
            if str(args.out_answer or "").strip():
                summary["out_answer"] = str(args.out_answer).strip()
        if conversation_obj is not None:
            summary["conversation"] = conversation_obj
            summary["out_conversation"] = str(args.out_conversation).strip()

        out_summary = str(args.out_summary or "").strip()
        if out_summary:
            _write_summary_file(out_summary, summary)

        print(_json_dump(summary))
        return 0
    except RuntimeError as exc:
        err = {
            "ok": False,
            "error_type": "RuntimeError",
            "message": str(exc.args[0]) if exc.args else str(exc),
            "detail": (exc.args[1] if len(exc.args) > 1 else None),
            "resolved_runtime": _runtime_payload(
                chatgptrest_root=root,
                python_bin=python_bin,
                command=cmd if "cmd" in locals() else None,
                request_timeout_seconds=request_timeout_seconds,
            )
            | {"runtime_env": runtime_env},
        }
        print(_json_dump(err), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
