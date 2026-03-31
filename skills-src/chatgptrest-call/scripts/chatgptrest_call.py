#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
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


DEFAULT_CHATGPTREST_ROOT = str(_default_chatgptrest_root())
DEFAULT_INTERVAL_STATE_FILE = str(_default_interval_state_file(Path(DEFAULT_CHATGPTREST_ROOT)))
DEFAULT_MAINT_LEGACY_CLIENT_NAME = "chatgptrestctl-maint"
DEFAULT_AGENT_TIMEOUT_SECONDS = 300
DEFAULT_AGENT_REQUEST_TIMEOUT_SECONDS = 330.0
DEFAULT_LEGACY_REQUEST_TIMEOUT_SECONDS = 180.0
DEFAULT_MCP_PROTOCOL_VERSION = "2025-03-26"
DEFAULT_MCP_CLIENT_NAME = "chatgptrest-call"
DEFAULT_MCP_CLIENT_VERSION = "1.0"
_AGENT_BACKGROUND_GOAL_HINTS = {
    "code_review",
    "consult",
    "gemini_deep_research",
    "gemini_research",
    "image",
    "report",
    "research",
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
    return summary


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


def _run_json_command(cmd: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    proc_env = None
    if env:
        proc_env = dict(os.environ)
        proc_env.update({str(k): str(v) for k, v in env.items()})
    proc = subprocess.run(cmd, capture_output=True, text=True, env=proc_env)
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


def _run_mcp_tool(
    *,
    mcp_url: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: float,
    request_id: int = 1,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload, _headers = _jsonrpc_call(
        mcp_url,
        request_id=request_id,
        method="tools/call",
        params={"name": str(tool_name), "arguments": dict(arguments)},
        timeout_seconds=timeout_seconds,
        headers=_mcp_headers(session),
    )
    return _decode_tool_result(payload)


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
            raw = resp.read().decode("utf-8", errors="replace")
            response_headers = {str(k): str(v) for k, v in resp.headers.items()}
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
    initialize_payload, response_headers = _jsonrpc_call(
        mcp_url,
        request_id=1,
        method="initialize",
        params={
            "protocolVersion": DEFAULT_MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": DEFAULT_MCP_CLIENT_NAME,
                "version": DEFAULT_MCP_CLIENT_VERSION,
            },
        },
        timeout_seconds=max(5.0, min(float(timeout_seconds), 30.0)),
        headers=_mcp_headers(),
    )
    result = dict(initialize_payload.get("result") or {})
    protocol_version = str(result.get("protocolVersion") or "").strip() or DEFAULT_MCP_PROTOCOL_VERSION
    session_id = ""
    for key, value in response_headers.items():
        if key.lower() == "mcp-session-id" and str(value or "").strip():
            session_id = str(value).strip()
            break
    session = {
        "protocol_version": protocol_version,
        "session_id": session_id,
    }
    try:
        _jsonrpc_call(
            mcp_url,
            request_id=2,
            method="notifications/initialized",
            params={},
            timeout_seconds=max(5.0, min(float(timeout_seconds), 30.0)),
            headers=_mcp_headers(session),
        )
    except Exception:
        pass
    return session


def _decode_sse_json(raw: str) -> dict[str, Any]:
    for line in str(raw or "").splitlines():
        if line.startswith("data: "):
            payload = line[len("data: ") :].strip()
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed
    raise RuntimeError(f"unable to decode SSE JSON payload: {raw!r}")


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
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError("unable to decode MCP tool response", payload)


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
        help="Use public advisor-agent MCP mode (default: true). Set --no-agent together with --maintenance-legacy-jobs only for controlled legacy maintenance",
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
        help="Provider (expert override, only in legacy mode)",
    )
    p.add_argument(
        "--preset",
        default="",
        help="Preset (expert override, only in legacy mode)",
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
    p.add_argument("--role-id", default="", help="Role ID for agent (expert override)")
    p.add_argument("--user-id", default="", help="User ID for agent context")
    p.add_argument("--trace-id", default="", help="Trace ID for request tracing")
    p.add_argument("--goal-hint", default="", help="Goal hint for agent (code_review, research, image, report, repair)")
    p.add_argument("--depth", default="standard", choices=["light", "standard", "deep", "heavy", "thinking_heavy"], help="Agent execution depth")
    p.add_argument(
        "--execution-profile",
        default="",
        help="Optional execution profile override (thinking_heavy, deep_research, report_grade)",
    )
    p.add_argument("--task-intake-json", default="{}", help="Canonical task_intake JSON object")
    p.add_argument("--task-intake-file", default="", help="Path to canonical task_intake JSON object file")
    p.add_argument("--workspace-request-json", default="{}", help="Workspace request JSON object")
    p.add_argument("--workspace-request-file", default="", help="Path to workspace request JSON object file")
    p.add_argument("--contract-patch-json", default="{}", help="Contract patch JSON object")
    p.add_argument("--contract-patch-file", default="", help="Path to contract patch JSON object file")

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
    return int(args.timeout_seconds) if int(args.timeout_seconds or 0) > 0 else DEFAULT_AGENT_TIMEOUT_SECONDS


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
    if isinstance(exc, (TimeoutError, socket.timeout, urllib.error.URLError, http.client.RemoteDisconnected)):
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
        )
    )


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
    args = build_parser().parse_args(argv)

    root = _resolved_root(args.chatgptrest_root)
    python_bin = _python_bin(root)
    if not python_bin.exists():
        payload = {
            "ok": False,
            "error_type": "CliError",
            "message": f"python binary not found: {python_bin}",
            "resolved_runtime": _runtime_payload(chatgptrest_root=root, python_bin=python_bin),
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
            }
            print(_json_dump(payload), file=sys.stderr)
            return 2
        return _run_agent_turn(python_bin, args)
    else:
        if not bool(args.maintenance_legacy_jobs):
            payload = {
                "ok": False,
                "error_type": "PolicyError",
                "message": "legacy provider-first mode is maintenance-only; use public advisor-agent MCP by default, or pass --maintenance-legacy-jobs for audited maintenance work",
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
    if not question and not task_intake_obj and not workspace_request_obj and not contract_patch_obj:
        raise RuntimeError(
            "agent mode requires --question, --task-intake-json/--task-intake-file, "
            "--workspace-request-json/--workspace-request-file, or --contract-patch-json/--contract-patch-file"
        )
    session_id = str(args.session_id or "").strip() or f"agent_sess_{uuid.uuid4().hex[:16]}"
    delivery_mode = "deferred" if _agent_prefers_background_delivery(args) else "sync"
    submission_stage = "preflight"
    submission_started = False
    mcp_session: dict[str, Any] | None = None

    try:
        agent_timeout_seconds, request_timeout_seconds = _validate_agent_mode_args(args)
        agent_context: dict[str, Any] = {}
        if args.github_repo:
            agent_context["github_repo"] = str(args.github_repo)
        if args.conversation_url:
            agent_context["conversation_url"] = str(args.conversation_url)
        if args.parent_job_id:
            agent_context["parent_job_id"] = str(args.parent_job_id)
        if args.provider:
            agent_context["legacy_provider"] = str(args.provider)
        legacy_preset = str(args.preset or "").strip() or _default_preset(str(args.provider))
        if legacy_preset:
            agent_context["legacy_preset"] = legacy_preset
        if bool(args.deep_research):
            agent_context["legacy_deep_research"] = True
        if bool(args.web_search):
            agent_context["legacy_web_search"] = True
        if bool(args.enable_import_code):
            agent_context["enable_import_code"] = True
        if bool(args.drive_name_fallback):
            agent_context["drive_name_fallback"] = True
        if bool(args.agent_mode):
            agent_context["legacy_agent_mode"] = True
        if bool(args.allow_queue):
            agent_context["allow_queue"] = True
        if agent_context:
            task_intake_obj = dict(task_intake_obj or {})
            task_intake_context = dict(task_intake_obj.get("context") or {})
            task_intake_context.update(agent_context)
            task_intake_obj["context"] = task_intake_context

        tool_args: dict[str, Any] = {
            "message": question,
            "timeout_seconds": agent_timeout_seconds,
            "session_id": session_id,
            "delivery_mode": delivery_mode,
        }
        if args.goal_hint:
            tool_args["goal_hint"] = str(args.goal_hint)
        if args.depth:
            tool_args["depth"] = str(args.depth)
        if args.execution_profile:
            tool_args["execution_profile"] = str(args.execution_profile)
        if task_intake_obj:
            tool_args["task_intake"] = task_intake_obj
        if workspace_request_obj:
            tool_args["workspace_request"] = workspace_request_obj
        if contract_patch_obj:
            tool_args["contract_patch"] = contract_patch_obj
        if args.file_path:
            tool_args["attachments"] = [str(fp) for fp in args.file_path]
        if hasattr(args, "role_id") and args.role_id:
            tool_args["role_id"] = str(args.role_id)
        if hasattr(args, "user_id") and args.user_id:
            tool_args["user_id"] = str(args.user_id)
        if hasattr(args, "trace_id") and args.trace_id:
            tool_args["trace_id"] = str(args.trace_id)

        runtime = _agent_runtime_payload(
            session_id=session_id,
            agent_timeout_seconds=agent_timeout_seconds,
            request_timeout_seconds=request_timeout_seconds,
            delivery_mode=delivery_mode,
            submission_stage="submitting",
            submission_started=False,
        )
        out_summary = str(args.out_summary or "").strip()
        if out_summary:
            _write_agent_summary_snapshot(out_summary, runtime=runtime)

        submission_stage = "initialize_mcp"
        mcp_session = _initialize_mcp_session(
            mcp_url=str(args.public_mcp_url),
            timeout_seconds=request_timeout_seconds,
        )
        runtime = _agent_runtime_payload(
            session_id=session_id,
            agent_timeout_seconds=agent_timeout_seconds,
            request_timeout_seconds=request_timeout_seconds,
            delivery_mode=delivery_mode,
            submission_stage="initialized",
            submission_started=False,
            mcp_session=mcp_session,
        )
        if out_summary:
            _write_agent_summary_snapshot(out_summary, runtime=runtime)

        submission_stage = "submit_turn"
        submission_started = True
        runtime = _agent_runtime_payload(
            session_id=session_id,
            agent_timeout_seconds=agent_timeout_seconds,
            request_timeout_seconds=request_timeout_seconds,
            delivery_mode=delivery_mode,
            submission_stage=submission_stage,
            submission_started=submission_started,
            mcp_session=mcp_session,
        )
        if out_summary:
            _write_agent_summary_snapshot(out_summary, runtime=runtime)
        result = _run_mcp_tool(
            mcp_url=str(args.public_mcp_url),
            tool_name="advisor_agent_turn",
            arguments=tool_args,
            timeout_seconds=request_timeout_seconds,
            request_id=3,
            session=mcp_session,
        )
        runtime = _agent_runtime_payload(
            session_id=session_id,
            agent_timeout_seconds=agent_timeout_seconds,
            request_timeout_seconds=request_timeout_seconds,
            delivery_mode=delivery_mode,
            submission_stage="submitted",
            submission_started=True,
            mcp_session=mcp_session,
        )
        if out_summary:
            _write_agent_summary_snapshot(out_summary, result=result, runtime=runtime)

        delivery = dict(result.get("delivery") or {})
        should_wait = (
            delivery_mode == "deferred"
            and bool(result.get("ok"))
            and str(result.get("status") or "").strip().lower() not in {"completed", "failed", "cancelled", "needs_followup", "needs_input"}
            and (
                bool(result.get("accepted"))
                or str(delivery.get("mode") or "").strip().lower() == "deferred"
                or bool(result.get("accepted_for_background"))
            )
        )
        if should_wait:
            submission_stage = "wait"
            wait_result = _run_mcp_tool(
                mcp_url=str(args.public_mcp_url),
                tool_name="advisor_agent_wait",
                arguments={
                    "session_id": str(result.get("session_id") or session_id),
                    "timeout_seconds": agent_timeout_seconds,
                },
                timeout_seconds=max(request_timeout_seconds, float(agent_timeout_seconds) + 30.0),
                request_id=4,
                session=mcp_session,
            )
            result = _merge_turn_wait_result(result, wait_result)
            runtime = _agent_runtime_payload(
                session_id=str(result.get("session_id") or session_id),
                agent_timeout_seconds=agent_timeout_seconds,
                request_timeout_seconds=max(request_timeout_seconds, float(agent_timeout_seconds) + 30.0),
                delivery_mode=delivery_mode,
                submission_stage="wait_completed",
                submission_started=True,
                mcp_session=mcp_session,
            )
            if out_summary:
                _write_agent_summary_snapshot(out_summary, result=result, runtime=runtime)

        print(_json_dump(result))
        return 0
    except Exception as exc:
        agent_timeout_seconds = _resolve_agent_timeout_seconds(args)
        request_timeout_seconds = _resolve_request_timeout_seconds(args=args, agent_mode=True)
        detail = exc.args[1] if len(getattr(exc, "args", ())) > 1 else None
        still_running_possible = submission_started and _looks_like_transport_timeout(exc)
        err = {
            "ok": False,
            "error_type": type(exc).__name__ or "RuntimeError",
            "message": str(exc.args[0]) if getattr(exc, "args", ()) else str(exc),
            "detail": detail,
            "mode": "agent_public_mcp",
            "session_id": session_id,
            "requested_runtime": _agent_runtime_payload(
                session_id=session_id,
                agent_timeout_seconds=agent_timeout_seconds,
                request_timeout_seconds=request_timeout_seconds,
                delivery_mode=delivery_mode,
                submission_stage=submission_stage,
                submission_started=submission_started,
                mcp_session=mcp_session,
            ),
            "still_running_possible": still_running_possible,
            "submission_started": submission_started,
            "failure_stage": submission_stage,
            "recovery_hint": (
                "Use advisor_agent_status/advisor_agent_wait with this session_id instead of resubmitting a new turn."
                if still_running_possible
                else "The request did not start remotely; inspect the local validation/transport error and retry after fixing it."
            ),
        }
        out_summary = str(args.out_summary or "").strip()
        if out_summary:
            _write_summary_file(out_summary, err)
        print(_json_dump(err), file=sys.stderr)
        return 2


def _run_legacy_jobs(python_bin: Path, args: argparse.Namespace) -> int:
    legacy_env = {"CHATGPTREST_CLIENT_NAME": DEFAULT_MAINT_LEGACY_CLIENT_NAME}
    root = _resolved_root(args.chatgptrest_root)
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
        run_obj = _run_json_command(cmd, env=legacy_env)
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
                    conversation_obj = _run_json_command(conv_cmd, env=legacy_env)
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
            ),
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
            ),
        }
        print(_json_dump(err), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
