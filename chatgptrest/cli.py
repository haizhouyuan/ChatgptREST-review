from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chatgptrest.providers.registry import PresetValidationError, validate_ask_preset


DEFAULT_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_PUBLIC_MCP_URL = "http://127.0.0.1:18712/mcp"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_SERVICES = [
    "chatgptrest-driver.service",
    "chatgptrest-api.service",
    "chatgptrest-worker-send.service",
    "chatgptrest-worker-wait.service",
    "chatgptrest-mcp.service",
]
OPTIONAL_SERVICES = [
    "chatgptrest-chrome.service",
    "chatgptrest-worker-repair.service",
    "chatgptrest-maint-daemon.service",
]


class CliError(RuntimeError):
    pass


class ApiError(CliError):
    def __init__(self, *, status: int, message: str, body_obj: Any | None = None, body_text: str | None = None) -> None:
        super().__init__(message)
        self.status = int(status)
        self.body_obj = body_obj
        self.body_text = body_text


@dataclass
class CliContext:
    base_url: str
    api: "ApiClient"
    output: str
    timeout_seconds: float
    repo_root: Path


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


def _decode_sse_json(raw: str) -> dict[str, Any]:
    for line in str(raw or "").splitlines():
        if line.startswith("data: "):
            payload = line[len("data: ") :].strip()
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed
    raise CliError(f"unable to decode SSE JSON payload: {raw!r}")


def _mcp_jsonrpc_call(
    url: str,
    *,
    request_id: int,
    method: str,
    params: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    req = urllib.request.Request(
        str(url),
        data=json.dumps(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
            ensure_ascii=False,
        ).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise CliError(f"HTTP {exc.code} calling MCP {method}: {text}") from exc
    except urllib.error.URLError as exc:
        raise CliError(f"failed to call MCP {method}: {exc}") from exc
    except TimeoutError as exc:
        raise CliError(f"MCP {method} timed out after {timeout_seconds}s") from exc
    parsed = _decode_sse_json(raw)
    if "error" in parsed:
        raise CliError(f"MCP {method} returned error: {parsed.get('error')}")
    return parsed


def _decode_mcp_tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result")
    if not isinstance(result, dict):
        raise CliError(f"invalid MCP tool result payload: {payload!r}")
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
    raise CliError(f"unable to decode MCP tool response: {payload!r}")


def _call_public_mcp_tool(
    *,
    mcp_url: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    payload = _mcp_jsonrpc_call(
        mcp_url,
        request_id=1,
        method="tools/call",
        params={"name": str(tool_name), "arguments": dict(arguments)},
        timeout_seconds=float(timeout_seconds),
    )
    return _decode_mcp_tool_result(payload)


def _is_timeout_like_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return ("timed out" in text) or ("timeout" in text)


def _parse_json_obj(*, raw: str | None, path: str | None, field_name: str) -> dict[str, Any]:
    obj: Any = {}
    if raw and raw.strip():
        try:
            obj = json.loads(raw)
        except Exception as exc:
            raise CliError(f"invalid JSON in {field_name}: {exc}") from exc
    if path and str(path).strip():
        p = Path(path).expanduser()
        try:
            obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            raise CliError(f"failed to load JSON file for {field_name}: {p}: {exc}") from exc
    if not isinstance(obj, dict):
        raise CliError(f"{field_name} must be a JSON object")
    return dict(obj)


def _merge_non_none(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for k, v in src.items():
        if v is not None:
            dst[k] = v
    return dst


def _as_bool(v: Any) -> bool:
    return bool(v)


def _sanitize_header_token(value: str | None, *, fallback: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raw = fallback
    out: list[str] = []
    for ch in raw:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("-")
    clean = "".join(out).strip("-_.")
    return clean or fallback


def _default_client_name() -> str:
    raw = (os.environ.get("CHATGPTREST_CLIENT_NAME") or "").strip()
    return _sanitize_header_token(raw, fallback="chatgptrestctl")


def _default_client_instance() -> str:
    raw = (os.environ.get("CHATGPTREST_CLIENT_INSTANCE") or "").strip()
    if raw:
        return _sanitize_header_token(raw, fallback="chatgptrestctl")
    host = _sanitize_header_token(socket.gethostname(), fallback="localhost")
    return f"{host}-pid{os.getpid()}"


def _new_request_id(*, client_name: str) -> str:
    prefix_raw = (os.environ.get("CHATGPTREST_REQUEST_ID_PREFIX") or "").strip() or client_name
    prefix = _sanitize_header_token(prefix_raw, fallback="chatgptrestctl")
    ts_ms = int(time.time() * 1000.0)
    return f"{prefix}-{os.getpid()}-{ts_ms:x}-{uuid.uuid4().hex[:8]}"


def _default_cancel_reason() -> str:
    raw = (os.environ.get("CHATGPTREST_CANCEL_REASON_DEFAULT") or "").strip()
    if raw:
        return " ".join(raw.replace("\r", " ").replace("\n", " ").split())[:200]
    return "chatgptrestctl_manual_cancel"


def _format_pretty(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        if "job_id" in obj and "status" in obj:
            parts = [f"job_id={obj['job_id']}  status={obj['status']}"]
            for k in ("phase", "kind", "attempts", "reason", "error", "conversation_url", "preview"):
                v = obj.get(k)
                if v is not None and str(v).strip():
                    parts.append(f"{k}={v}")
            return "  ".join(parts)
        if "jobs" in obj and isinstance(obj.get("jobs"), list):
            lines = [f"{'JOB_ID':34s} {'STATUS':15s} {'KIND':25s} {'PHASE':6s} {'REASON'}"]
            for j in obj["jobs"]:
                lines.append(
                    f"{j.get('job_id','?'):34s} {j.get('status','?'):15s} "
                    f"{j.get('kind','?'):25s} {str(j.get('phase') or '-'):6s} "
                    f"{str(j.get('reason') or '-')[:40]}"
                )
            return "\n".join(lines)
        if "jobs_by_status" in obj and "pause" in obj:
            pause = obj.get("pause") or {}
            counts = obj.get("jobs_by_status") or {}
            parts = [f"pause={pause.get('active', False)} ({pause.get('mode', '-')})"]
            for st, cnt in sorted(counts.items()):
                parts.append(f"{st}={cnt}")
            parts.append(f"incidents={obj.get('active_incidents', 0)}")
            return "  ".join(parts)
        if "incidents" in obj and isinstance(obj.get("incidents"), list):
            lines = [f"{'INCIDENT_ID':34s} {'SEV':4s} {'STATUS':12s} {'COUNT':>5s} {'SIGNATURE'}"]
            for inc in obj["incidents"]:
                lines.append(
                    f"{inc.get('incident_id','?'):34s} {inc.get('severity','?'):4s} "
                    f"{inc.get('status','?'):12s} {str(inc.get('count',0)):>5s} "
                    f"{str(inc.get('signature',''))[:50]}"
                )
            return "\n".join(lines)
    return _json_dumps(obj)


def _print(ctx: CliContext, obj: Any) -> None:
    if ctx.output == "json":
        print(_json_dumps(obj))
        return
    if isinstance(obj, str):
        print(obj)
        return
    print(_format_pretty(obj))


def _validate_kind_preset(*, kind: str, params_obj: dict[str, Any]) -> None:
    try:
        validate_ask_preset(kind=str(kind), params_obj=params_obj)
    except PresetValidationError as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            msg = str(detail.get("detail") or detail.get("error") or "invalid preset")
            supported = detail.get("supported")
            if isinstance(supported, list) and supported:
                msg = f"{msg}; supported: {', '.join(str(x) for x in supported)}"
            raise CliError(msg) from exc
        raise CliError(str(detail or exc)) from exc


def _read_chunk_stream(api: "ApiClient", *, path: str, offset: int, max_chars: int) -> dict[str, Any]:
    current_offset = max(0, int(offset))
    chunks: list[str] = []
    last_obj: dict[str, Any] = {}
    while True:
        obj = api.request(
            "GET",
            path,
            query={"offset": str(current_offset), "max_chars": str(max_chars)},
        )
        if not isinstance(obj, dict):
            raise CliError(f"invalid chunk response from {path}: expected object")
        chunk = str(obj.get("chunk") or "")
        chunks.append(chunk)
        last_obj = obj
        done = bool(obj.get("done"))
        next_offset = obj.get("next_offset")
        if done or next_offset is None:
            break
        try:
            current_offset = int(next_offset)
        except Exception:
            break

    out = dict(last_obj)
    out["chunk"] = "".join(chunks)
    out["offset"] = int(offset)
    out["fetched_all"] = True
    out["chunks"] = len(chunks)
    return out


def _http_json_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: Any | None,
    timeout_seconds: float,
) -> tuple[int, dict[str, Any] | list[Any] | str | None, str]:
    data = None
    req_headers = dict(headers)
    if json_body is not None:
        req_headers["Content-Type"] = "application/json"
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status = int(getattr(resp, "status", 200))
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw = str(exc)
        obj: Any = None
        try:
            obj = json.loads(raw) if raw.strip() else None
        except Exception:
            obj = None
        message = f"HTTP {exc.code} {exc.reason}: {raw[:400]}"
        raise ApiError(status=int(exc.code), message=message, body_obj=obj, body_text=raw) from exc
    except urllib.error.URLError as exc:
        raise CliError(f"request failed: {type(exc).__name__}: {exc}") from exc
    except TimeoutError as exc:
        raise CliError(
            f"request timed out: {exc}. For long-poll endpoints, increase --request-timeout-seconds."
        ) from exc
    except socket.timeout as exc:
        raise CliError(
            f"request timed out: {exc}. For long-poll endpoints, increase --request-timeout-seconds."
        ) from exc

    parsed: Any = None
    if raw.strip():
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
    return status, parsed, raw


class ApiClient:
    def __init__(self, *, base_url: str, api_token: str | None, ops_token: str | None, timeout_seconds: float) -> None:
        self.base_url = str(base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_token = str(api_token or "").strip() or None
        self.ops_token = str(ops_token or "").strip() or None
        self.timeout_seconds = max(0.1, float(timeout_seconds))

    def _token_for_path(self, path: str) -> str | None:
        if path.startswith("/v1/ops/") and self.ops_token:
            return self.ops_token
        return self.api_token

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        json_body: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        rel_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{rel_path}"
        if query:
            q = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None}, doseq=True)
            if q:
                url = f"{url}?{q}"
        client_name = _default_client_name()
        req_headers = {
            "Accept": "application/json",
            "X-Client-Name": client_name,
            "X-Client-Instance": _default_client_instance(),
            "X-Request-ID": _new_request_id(client_name=client_name),
        }
        if headers:
            req_headers.update(headers)
        token = self._token_for_path(rel_path)
        if token:
            req_headers["Authorization"] = f"Bearer {token}"
        _status, parsed, _raw = _http_json_request(
            method=method,
            url=url,
            headers=req_headers,
            json_body=json_body,
            timeout_seconds=self.timeout_seconds,
        )
        return parsed


def _wait_job_with_client_timeout_fallback(
    *,
    ctx: CliContext,
    job_id: str,
    query: dict[str, str],
) -> dict[str, Any] | Any:
    wait_path = f"/v1/jobs/{urllib.parse.quote(str(job_id))}/wait"
    try:
        return ctx.api.request("GET", wait_path, query=query)
    except CliError as exc:
        if not _is_timeout_like_error(exc):
            raise
        try:
            snap = ctx.api.request("GET", f"/v1/jobs/{urllib.parse.quote(str(job_id))}")
        except Exception:
            snap = None
        if isinstance(snap, dict):
            out = dict(snap)
            out["client_wait_timed_out"] = True
            out["client_wait_timeout_error"] = str(exc)
            return out
        return {
            "ok": False,
            "job_id": str(job_id),
            "status": "timeout",
            "client_wait_timed_out": True,
            "client_wait_timeout_error": str(exc),
        }


def _cmd_jobs_submit(ctx: CliContext, args: argparse.Namespace) -> int:
    payload, headers = _build_submit_request(args)
    obj = ctx.api.request("POST", "/v1/jobs", json_body=payload, headers=headers)
    _print(ctx, obj)
    return 0


def _build_submit_request(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, str]]:
    input_obj = _parse_json_obj(raw=args.input_json, path=args.input_file, field_name="input")
    params_obj = _parse_json_obj(raw=args.params_json, path=args.params_file, field_name="params")
    client_obj = _parse_json_obj(raw=args.client_json, path=args.client_file, field_name="client")

    if args.question and not input_obj.get("question"):
        input_obj["question"] = str(args.question)
    if args.prompt and not input_obj.get("prompt"):
        input_obj["prompt"] = str(args.prompt)
    if args.conversation_url and not input_obj.get("conversation_url"):
        input_obj["conversation_url"] = str(args.conversation_url)
    if args.parent_job_id and not input_obj.get("parent_job_id"):
        input_obj["parent_job_id"] = str(args.parent_job_id)
    if args.github_repo and not input_obj.get("github_repo"):
        input_obj["github_repo"] = str(args.github_repo)
    if args.file_path:
        input_obj["file_paths"] = [str(x) for x in args.file_path]

    _merge_non_none(
        params_obj,
        {
            "preset": args.preset,
            "timeout_seconds": args.timeout_seconds,
            "send_timeout_seconds": args.send_timeout_seconds,
            "wait_timeout_seconds": args.wait_timeout_seconds,
            "max_wait_seconds": args.max_wait_seconds,
            "min_chars": args.min_chars,
            "answer_format": args.answer_format,
            "purpose": args.purpose,
            "allow_queue": args.allow_queue,
            "deep_research": args.deep_research,
            "web_search": args.web_search,
            "agent_mode": args.agent_mode,
            "enable_import_code": args.enable_import_code,
            "drive_name_fallback": args.drive_name_fallback,
        },
    )

    kind = str(args.kind)
    _validate_kind_preset(kind=kind, params_obj=params_obj)

    payload: dict[str, Any] = {"kind": kind, "input": input_obj, "params": params_obj}
    if client_obj:
        payload["client"] = client_obj
    elif args.client_name or args.client_project:
        payload["client"] = {
            "name": (str(args.client_name) if args.client_name else None),
            "project": (str(args.client_project) if args.client_project else None),
        }

    headers = {}
    idem = str(args.idempotency_key or "").strip()
    if not idem:
        idem = f"chatgptrestctl-{uuid.uuid4().hex}"
        print(f"[auto-generated idempotency-key: {idem}]", file=sys.stderr)
    headers["Idempotency-Key"] = idem
    return payload, headers


def _cmd_jobs_get(ctx: CliContext, args: argparse.Namespace) -> int:
    obj = ctx.api.request("GET", f"/v1/jobs/{urllib.parse.quote(str(args.job_id))}")
    _print(ctx, obj)
    return 0


def _cmd_jobs_wait(ctx: CliContext, args: argparse.Namespace) -> int:
    query = {
        "timeout_seconds": str(args.timeout_seconds),
        "poll_seconds": str(args.poll_seconds),
    }
    if args.auto_wait_cooldown is not None:
        query["auto_wait_cooldown"] = "1" if args.auto_wait_cooldown else "0"
    obj = _wait_job_with_client_timeout_fallback(
        ctx=ctx,
        job_id=str(args.job_id),
        query=query,
    )
    _print(ctx, obj)
    return 0


def _cmd_jobs_cancel(ctx: CliContext, args: argparse.Namespace) -> int:
    reason = str(args.reason or "").strip() or _default_cancel_reason()
    reason = " ".join(reason.replace("\r", " ").replace("\n", " ").split())[:200]
    obj = ctx.api.request(
        "POST",
        f"/v1/jobs/{urllib.parse.quote(str(args.job_id))}/cancel",
        headers={"X-Cancel-Reason": reason},
    )
    _print(ctx, obj)
    return 0


def _cmd_jobs_events(ctx: CliContext, args: argparse.Namespace) -> int:
    after_id = int(args.after_id)
    while True:
        obj = ctx.api.request(
            "GET",
            f"/v1/jobs/{urllib.parse.quote(str(args.job_id))}/events",
            query={"after_id": str(after_id), "limit": str(args.limit)},
        )
        _print(ctx, obj)
        if not bool(getattr(args, "follow", False)):
            break
        if not isinstance(obj, dict):
            break
        events = obj.get("events") or []
        next_after_id = obj.get("next_after_id")
        if isinstance(next_after_id, int) and next_after_id > after_id and events:
            after_id = next_after_id
            continue
        time.sleep(2.0)
    return 0


def _write_output_file(path: str | None, text: str) -> None:
    if not path:
        return
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _cmd_jobs_answer(ctx: CliContext, args: argparse.Namespace) -> int:
    path = f"/v1/jobs/{urllib.parse.quote(str(args.job_id))}/answer"
    if args.all:
        obj = _read_chunk_stream(
            ctx.api,
            path=path,
            offset=args.offset,
            max_chars=args.max_chars,
        )
    else:
        obj = ctx.api.request(
            "GET",
            path,
            query={"offset": str(args.offset), "max_chars": str(args.max_chars)},
        )
    if not isinstance(obj, dict):
        _print(ctx, obj)
        return 0
    chunk = str(obj.get("chunk") or "")
    _write_output_file(args.out, chunk)
    if args.only_text:
        print(chunk)
        return 0
    _print(ctx, obj)
    return 0


def _cmd_jobs_conversation(ctx: CliContext, args: argparse.Namespace) -> int:
    path = f"/v1/jobs/{urllib.parse.quote(str(args.job_id))}/conversation"
    if args.all:
        obj = _read_chunk_stream(
            ctx.api,
            path=path,
            offset=args.offset,
            max_chars=args.max_chars,
        )
    else:
        obj = ctx.api.request(
            "GET",
            path,
            query={"offset": str(args.offset), "max_chars": str(args.max_chars)},
        )
    if not isinstance(obj, dict):
        _print(ctx, obj)
        return 0
    chunk = str(obj.get("chunk") or "")
    _write_output_file(args.out, chunk)
    if args.only_text:
        print(chunk)
        return 0
    _print(ctx, obj)
    return 0


def _cmd_jobs_run(ctx: CliContext, args: argparse.Namespace) -> int:
    expect_job_id = str(args.expect_job_id or "").strip()
    created: dict[str, Any]
    if expect_job_id:
        job_id = expect_job_id
        created = {
            "ok": True,
            "job_id": job_id,
            "status": "submit_skipped",
            "reason": "expect_job_id",
        }
    else:
        if not str(args.kind or "").strip():
            raise CliError("--kind is required unless --expect-job-id is set")
        payload, headers = _build_submit_request(args)
        created_obj = ctx.api.request("POST", "/v1/jobs", json_body=payload, headers=headers)
        if not isinstance(created_obj, dict) or not created_obj.get("job_id"):
            raise CliError("submit did not return a valid job_id")
        job_id = str(created_obj.get("job_id") or "").strip()
        if not job_id:
            raise CliError("submit returned empty job_id")
        created = dict(created_obj)

    wait_obj = _wait_job_with_client_timeout_fallback(
        ctx=ctx,
        job_id=str(job_id),
        query={
            "timeout_seconds": str(args.run_wait_timeout_seconds),
            "poll_seconds": str(args.run_poll_seconds),
            "auto_wait_cooldown": ("1" if _as_bool(args.run_auto_wait_cooldown) else "0"),
        },
    )
    if not isinstance(wait_obj, dict):
        _print(ctx, {"submit": created, "job_id": job_id, "wait": wait_obj})
        return 0

    status = str(wait_obj.get("status") or "")
    result: dict[str, Any] = {"submit": created, "job": wait_obj}
    if bool(wait_obj.get("client_wait_timed_out")) and bool(getattr(args, "cancel_on_client_timeout", False)):
        reason = str(getattr(args, "cancel_on_client_timeout_reason", "") or "").strip() or "client_wait_timeout"
        reason = " ".join(reason.replace("\r", " ").replace("\n", " ").split())[:200]
        try:
            cancel_obj = ctx.api.request(
                "POST",
                f"/v1/jobs/{urllib.parse.quote(job_id)}/cancel",
                headers={"X-Cancel-Reason": reason},
            )
            result["cancel"] = cancel_obj
        except Exception as exc:
            result["cancel_error"] = {"error_type": type(exc).__name__, "reason": str(exc)}

    if status == "completed" and not args.skip_answer:
        answer_obj = _read_chunk_stream(
            ctx.api,
            path=f"/v1/jobs/{urllib.parse.quote(job_id)}/answer",
            offset=0,
            max_chars=max(128, int(args.answer_max_chars)),
        )
        result["answer"] = answer_obj
        if isinstance(answer_obj, dict):
            chunk = str(answer_obj.get("chunk") or "")
            _write_output_file(args.out, chunk)
            if args.only_text:
                print(chunk)
                return 0
    _print(ctx, result)
    return 0


def _cmd_advisor_advise(ctx: CliContext, args: argparse.Namespace) -> int:
    context_obj = _parse_json_obj(raw=args.context_json, path=args.context_file, field_name="context")
    agent_options_obj = _parse_json_obj(
        raw=args.agent_options_json,
        path=args.agent_options_file,
        field_name="agent_options",
    )
    payload: dict[str, Any] = {
        "raw_question": str(args.raw_question),
        "context": context_obj,
        "force": bool(args.force),
        "execute": bool(args.execute),
    }
    if agent_options_obj:
        payload["agent_options"] = agent_options_obj
    obj = ctx.api.request("POST", "/v1/advisor/advise", json_body=payload)
    _print(ctx, obj)
    return 0


def _cmd_agent_turn(ctx: CliContext, args: argparse.Namespace) -> int:
    context_obj = _parse_json_obj(raw=args.context_json, path=args.context_file, field_name="context")
    task_intake_obj = _parse_json_obj(raw=args.task_intake_json, path=args.task_intake_file, field_name="task_intake")
    workspace_request_obj = _parse_json_obj(
        raw=args.workspace_request_json,
        path=args.workspace_request_file,
        field_name="workspace_request",
    )
    contract_patch_obj = _parse_json_obj(
        raw=args.contract_patch_json,
        path=args.contract_patch_file,
        field_name="contract_patch",
    )
    payload: dict[str, Any] = {
        "message": str(args.message),
    }
    if args.session_id:
        payload["session_id"] = str(args.session_id)
    if args.goal_hint:
        payload["goal_hint"] = str(args.goal_hint)
    if args.depth:
        payload["depth"] = str(args.depth)
    if getattr(args, "execution_profile", ""):
        payload["execution_profile"] = str(args.execution_profile)
    if task_intake_obj:
        payload["task_intake"] = task_intake_obj
    if workspace_request_obj:
        payload["workspace_request"] = workspace_request_obj
    if contract_patch_obj:
        payload["contract_patch"] = contract_patch_obj
    if args.timeout_seconds:
        payload["timeout_seconds"] = int(args.timeout_seconds)
    if context_obj:
        payload["context"] = context_obj
    if args.file_path:
        payload["attachments"] = list(args.file_path)
    if args.role_id:
        payload["role_id"] = str(args.role_id)
    if args.user_id:
        payload["user_id"] = str(args.user_id)
    if args.trace_id:
        payload["trace_id"] = str(args.trace_id)
    if bool(getattr(args, "agent_direct_rest", False)):
        obj = ctx.api.request(
            "POST",
            "/v3/agent/turn",
            json_body=payload,
            headers={"X-Client-Name": "chatgptrestctl-maint"},
        )
    else:
        http_timeout_seconds = max(float(ctx.timeout_seconds), float(payload.get("timeout_seconds") or 0) + 30.0)
        obj = _call_public_mcp_tool(
            mcp_url=str(args.public_mcp_url),
            tool_name="advisor_agent_turn",
            arguments=payload,
            timeout_seconds=http_timeout_seconds,
        )
    _print(ctx, obj)
    return 0


def _cmd_agent_status(ctx: CliContext, args: argparse.Namespace) -> int:
    if bool(getattr(args, "agent_direct_rest", False)):
        obj = ctx.api.request(
            "GET",
            f"/v3/agent/session/{args.session_id}",
            headers={"X-Client-Name": "chatgptrestctl-maint"},
        )
    else:
        obj = _call_public_mcp_tool(
            mcp_url=str(args.public_mcp_url),
            tool_name="advisor_agent_status",
            arguments={"session_id": str(args.session_id)},
            timeout_seconds=float(ctx.timeout_seconds),
        )
    _print(ctx, obj)
    return 0


def _cmd_agent_cancel(ctx: CliContext, args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {
        "session_id": str(args.session_id),
    }
    if bool(getattr(args, "agent_direct_rest", False)):
        obj = ctx.api.request(
            "POST",
            "/v3/agent/cancel",
            json_body=payload,
            headers={"X-Client-Name": "chatgptrestctl-maint"},
        )
    else:
        obj = _call_public_mcp_tool(
            mcp_url=str(args.public_mcp_url),
            tool_name="advisor_agent_cancel",
            arguments=payload,
            timeout_seconds=float(ctx.timeout_seconds),
        )
    _print(ctx, obj)
    return 0


def _cmd_issues_list(ctx: CliContext, args: argparse.Namespace) -> int:
    query: dict[str, str] = {"limit": str(args.limit)}
    for name in (
        "project",
        "kind",
        "source",
        "status",
        "severity",
        "fingerprint_hash",
        "fingerprint_text",
        "before_issue_id",
    ):
        value = getattr(args, name)
        if value is not None and str(value).strip():
            query[name] = str(value)
    if args.since_ts is not None:
        query["since_ts"] = str(args.since_ts)
    if args.until_ts is not None:
        query["until_ts"] = str(args.until_ts)
    if args.before_ts is not None:
        query["before_ts"] = str(args.before_ts)
    obj = ctx.api.request("GET", "/v1/issues", query=query)
    _print(ctx, obj)
    return 0


def _cmd_issues_get(ctx: CliContext, args: argparse.Namespace) -> int:
    obj = ctx.api.request("GET", f"/v1/issues/{urllib.parse.quote(str(args.issue_id))}")
    _print(ctx, obj)
    return 0


def _cmd_issues_report(ctx: CliContext, args: argparse.Namespace) -> int:
    metadata_obj = _parse_json_obj(raw=args.metadata_json, path=args.metadata_file, field_name="metadata")
    if bool(getattr(args, "allow_resolved_job", False)):
        metadata_obj["allow_resolved_job"] = True
    payload = {
        "project": str(args.project),
        "title": str(args.title),
        "severity": args.severity,
        "kind": args.kind,
        "symptom": args.symptom,
        "raw_error": args.raw_error,
        "job_id": args.job_id,
        "conversation_url": args.conversation_url,
        "artifacts_path": args.artifacts_path,
        "source": args.source,
        "fingerprint": args.fingerprint,
        "tags": [str(x) for x in (args.tag or [])],
        "metadata": (metadata_obj if metadata_obj else None),
    }
    obj = ctx.api.request("POST", "/v1/issues/report", json_body=payload)
    _print(ctx, obj)
    return 0


def _cmd_issues_events(ctx: CliContext, args: argparse.Namespace) -> int:
    obj = ctx.api.request(
        "GET",
        f"/v1/issues/{urllib.parse.quote(str(args.issue_id))}/events",
        query={"after_id": str(args.after_id), "limit": str(args.limit)},
    )
    _print(ctx, obj)
    return 0


def _cmd_issues_status(ctx: CliContext, args: argparse.Namespace) -> int:
    metadata_obj = _parse_json_obj(raw=args.metadata_json, path=args.metadata_file, field_name="metadata")
    payload = {
        "status": str(args.status),
        "note": args.note,
        "actor": args.actor,
        "linked_job_id": args.linked_job_id,
        "metadata": (metadata_obj if metadata_obj else None),
    }
    obj = ctx.api.request("POST", f"/v1/issues/{urllib.parse.quote(str(args.issue_id))}/status", json_body=payload)
    _print(ctx, obj)
    return 0


def _cmd_issues_evidence(ctx: CliContext, args: argparse.Namespace) -> int:
    metadata_obj = _parse_json_obj(raw=args.metadata_json, path=args.metadata_file, field_name="metadata")
    payload = {
        "job_id": args.job_id,
        "conversation_url": args.conversation_url,
        "artifacts_path": args.artifacts_path,
        "note": args.note,
        "source": args.source,
        "metadata": (metadata_obj if metadata_obj else None),
    }
    obj = ctx.api.request("POST", f"/v1/issues/{urllib.parse.quote(str(args.issue_id))}/evidence", json_body=payload)
    _print(ctx, obj)
    return 0


def _cmd_ops_health(ctx: CliContext, _args: argparse.Namespace) -> int:
    obj = ctx.api.request("GET", "/healthz")
    _print(ctx, obj)
    return 0


def _cmd_ops_status(ctx: CliContext, _args: argparse.Namespace) -> int:
    obj = ctx.api.request("GET", "/v1/ops/status")
    _print(ctx, obj)
    return 0


def _cmd_ops_pause_get(ctx: CliContext, _args: argparse.Namespace) -> int:
    obj = ctx.api.request("GET", "/v1/ops/pause")
    _print(ctx, obj)
    return 0


def _cmd_ops_pause_set(ctx: CliContext, args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {"mode": args.mode}
    if args.duration_seconds is not None:
        payload["duration_seconds"] = int(args.duration_seconds)
    if args.until_ts is not None:
        payload["until_ts"] = float(args.until_ts)
    if args.reason is not None:
        payload["reason"] = str(args.reason)
    obj = ctx.api.request("POST", "/v1/ops/pause", json_body=payload)
    _print(ctx, obj)
    return 0


def _cmd_ops_jobs(ctx: CliContext, args: argparse.Namespace) -> int:
    query = {"limit": str(args.limit)}
    for key in ("status", "kind_prefix", "phase", "before_ts", "before_job_id"):
        v = getattr(args, key)
        if v is not None and str(v).strip():
            query[key] = str(v)
    obj = ctx.api.request("GET", "/v1/ops/jobs", query=query)
    _print(ctx, obj)
    return 0


def _cmd_ops_events(ctx: CliContext, args: argparse.Namespace) -> int:
    obj = ctx.api.request(
        "GET",
        "/v1/ops/events",
        query={"after_id": str(args.after_id), "limit": str(args.limit)},
    )
    _print(ctx, obj)
    return 0


def _cmd_ops_incidents(ctx: CliContext, args: argparse.Namespace) -> int:
    query = {"limit": str(args.limit)}
    for key in ("status", "severity", "before_ts", "before_incident_id"):
        v = getattr(args, key)
        if v is not None and str(v).strip():
            query[key] = str(v)
    obj = ctx.api.request("GET", "/v1/ops/incidents", query=query)
    _print(ctx, obj)
    return 0


def _cmd_ops_incident_get(ctx: CliContext, args: argparse.Namespace) -> int:
    obj = ctx.api.request("GET", f"/v1/ops/incidents/{urllib.parse.quote(str(args.incident_id))}")
    _print(ctx, obj)
    return 0


def _cmd_ops_incident_actions(ctx: CliContext, args: argparse.Namespace) -> int:
    obj = ctx.api.request(
        "GET",
        f"/v1/ops/incidents/{urllib.parse.quote(str(args.incident_id))}/actions",
        query={"limit": str(args.limit)},
    )
    _print(ctx, obj)
    return 0


def _cmd_ops_idempotency(ctx: CliContext, args: argparse.Namespace) -> int:
    obj = ctx.api.request("GET", f"/v1/ops/idempotency/{urllib.parse.quote(str(args.idempotency_key))}")
    _print(ctx, obj)
    return 0


def _run_shell(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise CliError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc


def _service_names(args: argparse.Namespace) -> list[str]:
    names = [str(x) for x in (args.service or []) if str(x).strip()]
    if names:
        return names
    merged = list(DEFAULT_SERVICES)
    if _as_bool(getattr(args, "include_optional", False)):
        merged.extend(OPTIONAL_SERVICES)
    return merged


def _cmd_service_status(ctx: CliContext, args: argparse.Namespace) -> int:
    services = _service_names(args)
    proc = _run_shell(["systemctl", "--user", "--no-pager", "--full", "status", *services], check=False)
    out = {
        "ok": (proc.returncode == 0),
        "cmd": proc.args,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "services": services,
    }
    _print(ctx, out)
    return 0 if proc.returncode == 0 else 2


def _cmd_service_action(ctx: CliContext, args: argparse.Namespace) -> int:
    services = _service_names(args)
    action = str(args.action)
    proc = _run_shell(["systemctl", "--user", action, *services], check=False)
    out = {
        "ok": (proc.returncode == 0),
        "action": action,
        "services": services,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    _print(ctx, out)
    return 0 if proc.returncode == 0 else 2


def _viewer_bind_host(repo_root: Path) -> str:
    p = repo_root / ".run" / "viewer" / "novnc_bind_host.txt"
    try:
        raw = p.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        raw = ""
    return raw or "127.0.0.1"


def _port_open(host: str, port: int, *, timeout: float = 0.2) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, int(port))) == 0
    except Exception:
        return False
    finally:
        s.close()


def _cdp_port_from_url(raw_url: str | None) -> int | None:
    raw = str(raw_url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"http://{raw}"
    try:
        parsed = urllib.parse.urlparse(raw)
        if parsed.port is None:
            return None
        return int(parsed.port)
    except Exception:
        return None


def _doctor_cdp_ports() -> list[int]:
    ports: list[int] = []

    def _append(port: int | None) -> None:
        if port is None:
            return
        if int(port) <= 0:
            return
        if int(port) not in ports:
            ports.append(int(port))

    _append(_cdp_port_from_url(os.environ.get("CHATGPT_CDP_URL")))
    raw_debug = str(os.environ.get("CHROME_DEBUG_PORT") or "").strip()
    _append(int(raw_debug) if raw_debug.isdigit() else None)
    _append(9222)
    _append(9226)
    return ports


def _http_ok(url: str, *, timeout: float) -> tuple[bool, int | None]:
    req = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, int(getattr(resp, "status", 200))
    except urllib.error.HTTPError as exc:
        return False, int(exc.code)
    except Exception:
        return False, None


def _viewer_status(repo_root: Path, *, timeout_seconds: float, novnc_port: int, vnc_port: int) -> dict[str, Any]:
    bind_host = _viewer_bind_host(repo_root)
    probe_host = "127.0.0.1" if bind_host in {"0.0.0.0", "::"} else bind_host
    url = f"http://{bind_host}:{novnc_port}/vnc.html"
    probe_url = f"http://{probe_host}:{novnc_port}/vnc.html"
    novnc_listening = _port_open(probe_host, novnc_port, timeout=0.2)
    vnc_listening = _port_open("127.0.0.1", vnc_port, timeout=0.2)
    http_ok, status_code = _http_ok(probe_url, timeout=timeout_seconds)
    chrome_proc = _run_shell(
        [
            "pgrep",
            "-af",
            "chrome.*--user-data-dir=/vol1/1000/projects/ChatgptREST/secrets/chrome-profile-viewer",
        ],
        check=False,
    )
    return {
        "ok": bool(novnc_listening and vnc_listening and http_ok),
        "bind_host": bind_host,
        "probe_host": probe_host,
        "novnc_port": int(novnc_port),
        "vnc_port": int(vnc_port),
        "novnc_url": url,
        "novnc_probe_url": probe_url,
        "novnc_listening": bool(novnc_listening),
        "vnc_listening": bool(vnc_listening),
        "novnc_http_ok": bool(http_ok),
        "novnc_http_status": status_code,
        "viewer_chrome_running": (chrome_proc.returncode == 0),
    }


def _run_repo_script(repo_root: Path, script_rel: str, *, extra_args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    script = repo_root / script_rel
    if not script.exists():
        raise CliError(f"script not found: {script}")
    cmd = ["bash", str(script), *(extra_args or [])]
    return _run_shell(cmd, check=False)


def _cmd_viewer_status(ctx: CliContext, args: argparse.Namespace) -> int:
    out = _viewer_status(
        ctx.repo_root,
        timeout_seconds=ctx.timeout_seconds,
        novnc_port=int(args.novnc_port),
        vnc_port=int(args.vnc_port),
    )
    _print(ctx, out)
    return 0 if out.get("ok") else 2


def _cmd_viewer_url(ctx: CliContext, args: argparse.Namespace) -> int:
    bind_host = _viewer_bind_host(ctx.repo_root)
    novnc_port = int(args.novnc_port)
    url = f"http://{bind_host}:{novnc_port}/vnc.html"
    out = {"novnc_url": url, "bind_host": bind_host, "novnc_port": novnc_port}
    if bind_host in {"0.0.0.0", "::"}:
        out["local_url"] = f"http://127.0.0.1:{novnc_port}/vnc.html"
        ts = _run_shell(["tailscale", "ip", "-4"], check=False)
        ts_ip = str(ts.stdout or "").strip().splitlines()
        if ts.returncode == 0 and ts_ip:
            out["tailscale_url"] = f"http://{ts_ip[0]}:{novnc_port}/vnc.html"
    if ctx.output == "json":
        _print(ctx, out)
    else:
        print(out.get("tailscale_url") or out.get("local_url") or out["novnc_url"])
    return 0


def _cmd_viewer_start(ctx: CliContext, _args: argparse.Namespace) -> int:
    proc = _run_repo_script(ctx.repo_root, "ops/viewer_start.sh")
    out = {"ok": (proc.returncode == 0), "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    _print(ctx, out)
    return 0 if proc.returncode == 0 else 2


def _cmd_viewer_stop(ctx: CliContext, _args: argparse.Namespace) -> int:
    proc = _run_repo_script(ctx.repo_root, "ops/viewer_stop.sh")
    out = {"ok": (proc.returncode == 0), "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    _print(ctx, out)
    return 0 if proc.returncode == 0 else 2


def _cmd_viewer_restart(ctx: CliContext, args: argparse.Namespace) -> int:
    extra = ["--full"] if _as_bool(args.full) else ["--chrome-only"]
    proc = _run_repo_script(ctx.repo_root, "ops/viewer_restart.sh", extra_args=extra)
    out = {
        "ok": (proc.returncode == 0),
        "mode": ("full" if _as_bool(args.full) else "chrome-only"),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    _print(ctx, out)
    return 0 if proc.returncode == 0 else 2


def _cmd_doctor(ctx: CliContext, args: argparse.Namespace) -> int:
    report: dict[str, Any] = {"ok": True}

    health_ok = False
    try:
        health = ctx.api.request("GET", "/healthz")
        report["healthz"] = health
        health_ok = True
    except Exception as exc:
        report["healthz"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    report["ok"] = report["ok"] and health_ok

    ops_ok = False
    try:
        ops_status = ctx.api.request("GET", "/v1/ops/status")
        report["ops_status"] = ops_status
        ops_ok = isinstance(ops_status, dict) and bool(ops_status.get("ok", True))
    except Exception as exc:
        report["ops_status"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    report["ok"] = report["ok"] and ops_ok

    services = _service_names(args)
    svc_proc = _run_shell(["systemctl", "--user", "is-active", *services], check=False)
    report["services"] = {
        "services": services,
        "ok": (svc_proc.returncode == 0),
        "stdout": svc_proc.stdout,
        "stderr": svc_proc.stderr,
        "returncode": svc_proc.returncode,
    }
    report["ok"] = report["ok"] and bool(report["services"]["ok"])

    required_ports = [18711, 18701, 18712]
    cdp_ports = _doctor_cdp_ports()

    port_checks = {}
    for p in required_ports + cdp_ports:
        port_checks[str(p)] = _port_open("127.0.0.1", p, timeout=0.2)
    report["ports"] = port_checks
    required_ok = all(bool(port_checks.get(str(p))) for p in required_ports)
    cdp_ok = any(bool(port_checks.get(str(p))) for p in cdp_ports)
    report["required_ports_ok"] = bool(required_ok)
    report["cdp_ports"] = cdp_ports
    report["cdp_ok"] = bool(cdp_ok)
    report["ok"] = report["ok"] and bool(required_ok) and bool(cdp_ok)

    viewer = _viewer_status(
        ctx.repo_root,
        timeout_seconds=ctx.timeout_seconds,
        novnc_port=int(args.viewer_novnc_port),
        vnc_port=int(args.viewer_vnc_port),
    )
    report["viewer"] = viewer
    if _as_bool(args.require_viewer):
        report["ok"] = report["ok"] and bool(viewer.get("ok"))

    _print(ctx, report)
    return 0 if bool(report.get("ok")) else 2


def _cmd_version(ctx: CliContext, _args: argparse.Namespace) -> int:
    out: dict[str, Any] = {
        "cli": {"name": "chatgptrestctl", "module": "chatgptrest.cli"},
        "server": {},
    }
    try:
        ops = ctx.api.request("GET", "/v1/ops/status")
        if isinstance(ops, dict):
            out["server"] = {
                "build": ops.get("build"),
                "ok": ops.get("ok"),
            }
        else:
            out["server"] = {"raw": ops}
    except Exception as exc:
        out["server"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    _print(ctx, out)
    return 0


def _add_common_job_submit_flags(p: argparse.ArgumentParser, *, require_kind: bool = True, require_idem: bool = True) -> None:
    p.add_argument("--kind", required=require_kind, help="job kind, e.g. chatgpt_web.ask")
    p.add_argument("--idempotency-key", required=require_idem, default=None, help="Idempotency-Key header")
    p.add_argument("--input-json", default="{}", help="input JSON object")
    p.add_argument("--input-file", default=None, help="path to input JSON object file")
    p.add_argument("--params-json", default="{}", help="params JSON object")
    p.add_argument("--params-file", default=None, help="path to params JSON object file")
    p.add_argument("--client-json", default="{}", help="client JSON object")
    p.add_argument("--client-file", default=None, help="path to client JSON object file")
    p.add_argument("--client-name", default=None, help="client.name convenience field")
    p.add_argument("--client-project", default=None, help="client.project convenience field")

    p.add_argument("--question", default=None, help="input.question convenience field")
    p.add_argument("--prompt", default=None, help="input.prompt convenience field")
    p.add_argument("--conversation-url", default=None, help="input.conversation_url")
    p.add_argument("--parent-job-id", default=None, help="input.parent_job_id")
    p.add_argument("--file-path", action="append", default=None, help="input.file_paths[]; repeatable")
    p.add_argument("--github-repo", default=None, help="input.github_repo")

    p.add_argument("--preset", default=None, help="params.preset")
    p.add_argument("--job-timeout-seconds", dest="timeout_seconds", type=int, default=None, help="params.timeout_seconds")
    p.add_argument("--timeout-seconds", dest="timeout_seconds", type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument("--send-timeout-seconds", type=int, default=None, help="params.send_timeout_seconds")
    p.add_argument("--wait-timeout-seconds", type=int, default=None, help="params.wait_timeout_seconds")
    p.add_argument("--max-wait-seconds", type=int, default=None, help="params.max_wait_seconds")
    p.add_argument("--min-chars", type=int, default=None, help="params.min_chars")
    p.add_argument("--answer-format", default=None, help="params.answer_format")
    p.add_argument("--purpose", default=None, help="params.purpose (e.g. prod|smoke)")
    p.add_argument("--allow-queue", action=argparse.BooleanOptionalAction, default=None, help="params.allow_queue")
    p.add_argument("--deep-research", action=argparse.BooleanOptionalAction, default=None, help="params.deep_research")
    p.add_argument("--web-search", action=argparse.BooleanOptionalAction, default=None, help="params.web_search")
    p.add_argument("--agent-mode", action=argparse.BooleanOptionalAction, default=None, help="params.agent_mode")
    p.add_argument(
        "--enable-import-code",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="params.enable_import_code",
    )
    p.add_argument(
        "--drive-name-fallback",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="params.drive_name_fallback",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="chatgptrestctl",
        description="Operational CLI for ChatgptREST (jobs/advisor/issues/ops/services/viewer/doctor).",
    )
    p.add_argument("--base-url", default=os.environ.get("CHATGPTREST_BASE_URL", DEFAULT_BASE_URL))
    p.add_argument(
        "--public-mcp-url",
        default=os.environ.get("CHATGPTREST_PUBLIC_MCP_URL", DEFAULT_PUBLIC_MCP_URL),
        help="public advisor-agent MCP URL (default northbound surface for coding agents)",
    )
    p.add_argument("--api-token", default=os.environ.get("CHATGPTREST_API_TOKEN", ""))
    p.add_argument("--ops-token", default=os.environ.get("CHATGPTREST_OPS_TOKEN", os.environ.get("CHATGPTREST_ADMIN_TOKEN", "")))
    p.add_argument(
        "--request-timeout-seconds",
        dest="request_timeout_seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    p.add_argument("--timeout-seconds", dest="request_timeout_seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS, help=argparse.SUPPRESS)
    p.add_argument("--output", choices=["pretty", "json"], default="json")
    p.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]), help="repo root for local scripts")

    sub = p.add_subparsers(dest="group", required=True)

    jobs = sub.add_parser("jobs", help="job operations")
    jobs_sub = jobs.add_subparsers(dest="jobs_cmd", required=True)

    jobs_submit = jobs_sub.add_parser("submit", help="POST /v1/jobs")
    _add_common_job_submit_flags(jobs_submit, require_idem=False)
    jobs_submit.set_defaults(func=_cmd_jobs_submit)

    jobs_get = jobs_sub.add_parser("get", help="GET /v1/jobs/{job_id}")
    jobs_get.add_argument("job_id")
    jobs_get.set_defaults(func=_cmd_jobs_get)

    jobs_wait = jobs_sub.add_parser("wait", help="GET /v1/jobs/{job_id}/wait")
    jobs_wait.add_argument("job_id")
    jobs_wait.add_argument("--timeout-seconds", type=float, default=300.0)
    jobs_wait.add_argument("--poll-seconds", type=float, default=1.0)
    jobs_wait.add_argument("--auto-wait-cooldown", action=argparse.BooleanOptionalAction, default=None)
    jobs_wait.set_defaults(func=_cmd_jobs_wait)

    jobs_cancel = jobs_sub.add_parser("cancel", help="POST /v1/jobs/{job_id}/cancel")
    jobs_cancel.add_argument("job_id")
    jobs_cancel.add_argument("--reason", default="", help="Cancel reason (sent as X-Cancel-Reason header).")
    jobs_cancel.set_defaults(func=_cmd_jobs_cancel)

    jobs_events = jobs_sub.add_parser("events", help="GET /v1/jobs/{job_id}/events")
    jobs_events.add_argument("job_id")
    jobs_events.add_argument("--after-id", type=int, default=0)
    jobs_events.add_argument("--limit", type=int, default=200)
    jobs_events.add_argument("--follow", action="store_true", help="continuously poll for new events")
    jobs_events.set_defaults(func=_cmd_jobs_events)

    jobs_answer = jobs_sub.add_parser("answer", help="GET /v1/jobs/{job_id}/answer")
    jobs_answer.add_argument("job_id")
    jobs_answer.add_argument("--offset", type=int, default=0)
    jobs_answer.add_argument("--max-chars", type=int, default=4000)
    jobs_answer.add_argument("--all", action="store_true", help="fetch all chunks")
    jobs_answer.add_argument("--out", default=None, help="write combined chunk text to file")
    jobs_answer.add_argument("--only-text", action="store_true", help="print chunk text only")
    jobs_answer.set_defaults(func=_cmd_jobs_answer)

    jobs_conv = jobs_sub.add_parser("conversation", help="GET /v1/jobs/{job_id}/conversation")
    jobs_conv.add_argument("job_id")
    jobs_conv.add_argument("--offset", type=int, default=0)
    jobs_conv.add_argument("--max-chars", type=int, default=4000)
    jobs_conv.add_argument("--all", action="store_true", help="fetch all chunks")
    jobs_conv.add_argument("--out", default=None, help="write combined chunk text to file")
    jobs_conv.add_argument("--only-text", action="store_true", help="print chunk text only")
    jobs_conv.set_defaults(func=_cmd_jobs_conversation)

    jobs_run = jobs_sub.add_parser("run", help="submit + wait + (optionally) fetch answer")
    _add_common_job_submit_flags(jobs_run, require_kind=False, require_idem=False)
    jobs_run.add_argument("--run-wait-timeout-seconds", type=float, default=900.0)
    jobs_run.add_argument("--run-poll-seconds", type=float, default=1.0)
    jobs_run.add_argument("--run-auto-wait-cooldown", action=argparse.BooleanOptionalAction, default=True)
    jobs_run.add_argument("--skip-answer", action="store_true")
    jobs_run.add_argument("--answer-max-chars", type=int, default=8000)
    jobs_run.add_argument("--out", default=None, help="write final answer text to file")
    jobs_run.add_argument("--only-text", action="store_true")
    jobs_run.add_argument(
        "--expect-job-id",
        default=None,
        help="skip submit and wait/fetch this existing job_id",
    )
    jobs_run.add_argument(
        "--cancel-on-client-timeout",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="when local wait request times out, auto-call /cancel for the same job",
    )
    jobs_run.add_argument(
        "--cancel-on-client-timeout-reason",
        default="client_wait_timeout",
        help="X-Cancel-Reason used when --cancel-on-client-timeout is enabled",
    )
    jobs_run.set_defaults(func=_cmd_jobs_run)

    jobs_list = jobs_sub.add_parser("list", help="GET /v1/ops/jobs (convenience alias)")
    jobs_list.add_argument("--status", default=None)
    jobs_list.add_argument("--kind-prefix", default=None)
    jobs_list.add_argument("--phase", default=None)
    jobs_list.add_argument("--before-ts", type=float, default=None)
    jobs_list.add_argument("--before-job-id", default=None)
    jobs_list.add_argument("--limit", type=int, default=20)
    jobs_list.set_defaults(func=_cmd_ops_jobs)

    advisor = sub.add_parser("advisor", help="advisor wrapper v1 operations")
    advisor_sub = advisor.add_subparsers(dest="advisor_cmd", required=True)

    advisor_advise = advisor_sub.add_parser("advise", help="POST /v1/advisor/advise")
    advisor_advise.add_argument("--raw-question", required=True, help="advisor input question")
    advisor_advise.add_argument("--context-json", default="{}", help="context JSON object")
    advisor_advise.add_argument("--context-file", default=None, help="path to context JSON object file")
    advisor_advise.add_argument("--force", action=argparse.BooleanOptionalAction, default=False)
    advisor_advise.add_argument("--execute", action=argparse.BooleanOptionalAction, default=False)
    advisor_advise.add_argument("--agent-options-json", default="{}", help="agent_options JSON object")
    advisor_advise.add_argument("--agent-options-file", default=None, help="path to agent_options JSON object file")
    advisor_advise.set_defaults(func=_cmd_advisor_advise)

    agent = sub.add_parser("agent", help="public agent facade operations (v3)")
    agent_sub = agent.add_subparsers(dest="agent_cmd", required=True)

    agent_turn = agent_sub.add_parser("turn", help="POST /v3/agent/turn - execute agent turn")
    agent_turn.add_argument("--message", default="", help="user message (optional when workspace_request is provided)")
    agent_turn.add_argument("--session-id", default="", help="session ID for continuity")
    agent_turn.add_argument("--goal-hint", default="", help="goal hint (code_review, research, image, report, repair)")
    agent_turn.add_argument("--depth", default="standard", help="depth (light, standard, deep, heavy)")
    agent_turn.add_argument(
        "--execution-profile",
        default="",
        help="optional execution profile override (thinking_heavy, deep_research, report_grade)",
    )
    agent_turn.add_argument("--task-intake-json", default="{}", help="canonical task_intake JSON object")
    agent_turn.add_argument("--task-intake-file", default=None, help="path to task_intake JSON object file")
    agent_turn.add_argument("--workspace-request-json", default="{}", help="workspace_request JSON object")
    agent_turn.add_argument("--workspace-request-file", default=None, help="path to workspace_request JSON object file")
    agent_turn.add_argument("--contract-patch-json", default="{}", help="contract_patch JSON object")
    agent_turn.add_argument("--contract-patch-file", default=None, help="path to contract_patch JSON object file")
    agent_turn.add_argument("--timeout-seconds", type=int, default=300, help="execution timeout")
    agent_turn.add_argument("--context-json", default="{}", help="context JSON object")
    agent_turn.add_argument("--context-file", default=None, help="path to context JSON object file")
    agent_turn.add_argument("--file-path", action="append", default=[], help="file paths to attach (can be repeated)")
    agent_turn.add_argument("--role-id", default="", help="role ID for context binding")
    agent_turn.add_argument("--user-id", default="", help="user ID")
    agent_turn.add_argument("--trace-id", default="", help="trace ID for tracking")
    agent_turn.add_argument(
        "--agent-direct-rest",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="maintenance/debug override: call /v3/agent/turn directly instead of public MCP",
    )
    agent_turn.set_defaults(func=_cmd_agent_turn)

    agent_status = agent_sub.add_parser("status", help="GET /v3/agent/session/{session_id}")
    agent_status.add_argument("session_id", help="session ID to query")
    agent_status.add_argument(
        "--agent-direct-rest",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="maintenance/debug override: call /v3/agent/session/{session_id} directly instead of public MCP",
    )
    agent_status.set_defaults(func=_cmd_agent_status)

    agent_cancel = agent_sub.add_parser("cancel", help="POST /v3/agent/cancel")
    agent_cancel.add_argument("session_id", help="session ID to cancel")
    agent_cancel.add_argument(
        "--agent-direct-rest",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="maintenance/debug override: call /v3/agent/cancel directly instead of public MCP",
    )
    agent_cancel.set_defaults(func=_cmd_agent_cancel)

    issues = sub.add_parser("issues", help="issue ledger operations")
    issues_sub = issues.add_subparsers(dest="issues_cmd", required=True)

    issues_list = issues_sub.add_parser("list", help="GET /v1/issues")
    issues_list.add_argument("--project", default=None)
    issues_list.add_argument("--kind", default=None)
    issues_list.add_argument("--source", default=None)
    issues_list.add_argument("--status", default=None)
    issues_list.add_argument("--severity", default=None)
    issues_list.add_argument("--fingerprint-hash", default=None)
    issues_list.add_argument("--fingerprint-text", default=None)
    issues_list.add_argument("--since-ts", type=float, default=None)
    issues_list.add_argument("--until-ts", type=float, default=None)
    issues_list.add_argument("--before-ts", type=float, default=None)
    issues_list.add_argument("--before-issue-id", default=None)
    issues_list.add_argument("--limit", type=int, default=200)
    issues_list.set_defaults(func=_cmd_issues_list)

    issues_get = issues_sub.add_parser("get", help="GET /v1/issues/{issue_id}")
    issues_get.add_argument("issue_id")
    issues_get.set_defaults(func=_cmd_issues_get)

    issues_report = issues_sub.add_parser("report", help="POST /v1/issues/report")
    issues_report.add_argument("--project", required=True)
    issues_report.add_argument("--title", required=True)
    issues_report.add_argument("--severity", default=None)
    issues_report.add_argument("--kind", default=None)
    issues_report.add_argument("--symptom", default=None)
    issues_report.add_argument("--raw-error", default=None)
    issues_report.add_argument("--job-id", default=None)
    issues_report.add_argument("--conversation-url", default=None)
    issues_report.add_argument("--artifacts-path", default=None)
    issues_report.add_argument("--source", default=None)
    issues_report.add_argument("--fingerprint", default=None)
    issues_report.add_argument(
        "--allow-resolved-job",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="allow reporting even when referenced job is already completed (postmortem)",
    )
    issues_report.add_argument("--tag", action="append", default=[])
    issues_report.add_argument("--metadata-json", default="{}")
    issues_report.add_argument("--metadata-file", default=None)
    issues_report.set_defaults(func=_cmd_issues_report)

    issues_events = issues_sub.add_parser("events", help="GET /v1/issues/{issue_id}/events")
    issues_events.add_argument("issue_id")
    issues_events.add_argument("--after-id", type=int, default=0)
    issues_events.add_argument("--limit", type=int, default=200)
    issues_events.set_defaults(func=_cmd_issues_events)

    issues_status = issues_sub.add_parser("status", help="POST /v1/issues/{issue_id}/status")
    issues_status.add_argument("issue_id")
    issues_status.add_argument("--status", required=True, choices=["open", "in_progress", "mitigated", "closed"])
    issues_status.add_argument("--note", default=None)
    issues_status.add_argument("--actor", default=None)
    issues_status.add_argument("--linked-job-id", default=None)
    issues_status.add_argument("--metadata-json", default="{}")
    issues_status.add_argument("--metadata-file", default=None)
    issues_status.set_defaults(func=_cmd_issues_status)

    issues_evidence = issues_sub.add_parser("evidence", help="POST /v1/issues/{issue_id}/evidence")
    issues_evidence.add_argument("issue_id")
    issues_evidence.add_argument("--job-id", default=None)
    issues_evidence.add_argument("--conversation-url", default=None)
    issues_evidence.add_argument("--artifacts-path", default=None)
    issues_evidence.add_argument("--note", default=None)
    issues_evidence.add_argument("--source", default=None)
    issues_evidence.add_argument("--metadata-json", default="{}")
    issues_evidence.add_argument("--metadata-file", default=None)
    issues_evidence.set_defaults(func=_cmd_issues_evidence)

    ops = sub.add_parser("ops", help="ops endpoints")
    ops_sub = ops.add_subparsers(dest="ops_cmd", required=True)

    ops_health = ops_sub.add_parser("health", help="GET /healthz")
    ops_health.set_defaults(func=_cmd_ops_health)

    ops_status = ops_sub.add_parser("status", help="GET /v1/ops/status")
    ops_status.set_defaults(func=_cmd_ops_status)

    ops_pause = ops_sub.add_parser("pause", help="GET/POST /v1/ops/pause")
    ops_pause_sub = ops_pause.add_subparsers(dest="ops_pause_cmd", required=True)
    ops_pause_get = ops_pause_sub.add_parser("get")
    ops_pause_get.set_defaults(func=_cmd_ops_pause_get)
    ops_pause_set = ops_pause_sub.add_parser("set")
    ops_pause_set.add_argument("--mode", required=True, choices=["none", "send", "all"])
    ops_pause_set.add_argument("--duration-seconds", type=int, default=None)
    ops_pause_set.add_argument("--until-ts", type=float, default=None)
    ops_pause_set.add_argument("--reason", default=None)
    ops_pause_set.set_defaults(func=_cmd_ops_pause_set)

    ops_jobs = ops_sub.add_parser("jobs", help="GET /v1/ops/jobs")
    ops_jobs.add_argument("--status", default=None)
    ops_jobs.add_argument("--kind-prefix", default=None)
    ops_jobs.add_argument("--phase", default=None)
    ops_jobs.add_argument("--before-ts", default=None)
    ops_jobs.add_argument("--before-job-id", default=None)
    ops_jobs.add_argument("--limit", type=int, default=50)
    ops_jobs.set_defaults(func=_cmd_ops_jobs)

    ops_events = ops_sub.add_parser("events", help="GET /v1/ops/events")
    ops_events.add_argument("--after-id", type=int, default=0)
    ops_events.add_argument("--limit", type=int, default=200)
    ops_events.set_defaults(func=_cmd_ops_events)

    ops_incidents = ops_sub.add_parser("incidents", help="GET /v1/ops/incidents")
    ops_incidents.add_argument("--status", default=None)
    ops_incidents.add_argument("--severity", default=None)
    ops_incidents.add_argument("--before-ts", default=None)
    ops_incidents.add_argument("--before-incident-id", default=None)
    ops_incidents.add_argument("--limit", type=int, default=50)
    ops_incidents.set_defaults(func=_cmd_ops_incidents)

    ops_incident_get = ops_sub.add_parser("incident-get", help="GET /v1/ops/incidents/{incident_id}")
    ops_incident_get.add_argument("incident_id")
    ops_incident_get.set_defaults(func=_cmd_ops_incident_get)

    ops_incident_actions = ops_sub.add_parser("incident-actions", help="GET /v1/ops/incidents/{incident_id}/actions")
    ops_incident_actions.add_argument("incident_id")
    ops_incident_actions.add_argument("--limit", type=int, default=50)
    ops_incident_actions.set_defaults(func=_cmd_ops_incident_actions)

    ops_idem = ops_sub.add_parser("idempotency", help="GET /v1/ops/idempotency/{idempotency_key}")
    ops_idem.add_argument("idempotency_key")
    ops_idem.set_defaults(func=_cmd_ops_idempotency)

    service = sub.add_parser("service", help="systemd service operations")
    service_sub = service.add_subparsers(dest="service_cmd", required=True)

    service_status = service_sub.add_parser("status", help="systemctl --user status")
    service_status.add_argument("--service", action="append", default=None, help="repeatable")
    service_status.add_argument("--include-optional", action="store_true")
    service_status.set_defaults(func=_cmd_service_status)

    for action in ("start", "stop", "restart"):
        sp = service_sub.add_parser(action, help=f"systemctl --user {action}")
        sp.add_argument("--service", action="append", default=None, help="repeatable")
        sp.add_argument("--include-optional", action="store_true")
        sp.set_defaults(func=_cmd_service_action, action=action)

    viewer = sub.add_parser("viewer", help="viewer/noVNC operations")
    viewer_sub = viewer.add_subparsers(dest="viewer_cmd", required=True)

    viewer_status = viewer_sub.add_parser("status")
    viewer_status.add_argument("--novnc-port", type=int, default=6082)
    viewer_status.add_argument("--vnc-port", type=int, default=5902)
    viewer_status.set_defaults(func=_cmd_viewer_status)

    viewer_url = viewer_sub.add_parser("url")
    viewer_url.add_argument("--novnc-port", type=int, default=6082)
    viewer_url.set_defaults(func=_cmd_viewer_url)

    viewer_start = viewer_sub.add_parser("start")
    viewer_start.set_defaults(func=_cmd_viewer_start)

    viewer_stop = viewer_sub.add_parser("stop")
    viewer_stop.set_defaults(func=_cmd_viewer_stop)

    viewer_restart = viewer_sub.add_parser("restart")
    viewer_restart.add_argument("--full", action="store_true", help="use --full; default is --chrome-only")
    viewer_restart.set_defaults(func=_cmd_viewer_restart)

    doctor = sub.add_parser("doctor", help="end-to-end operational diagnostics")
    doctor.add_argument("--service", action="append", default=None, help="repeatable")
    doctor.add_argument("--include-optional", action="store_true")
    doctor.add_argument("--viewer-novnc-port", type=int, default=6082)
    doctor.add_argument("--viewer-vnc-port", type=int, default=5902)
    doctor.add_argument("--require-viewer", action="store_true", help="fail doctor when viewer is unhealthy")
    doctor.set_defaults(func=_cmd_doctor)

    version = sub.add_parser("version", help="show CLI + server build version")
    version.set_defaults(func=_cmd_version)

    return p


def _ctx_from_args(args: argparse.Namespace) -> CliContext:
    repo_root = Path(str(args.repo_root)).expanduser()
    api = ApiClient(
        base_url=str(args.base_url),
        api_token=str(args.api_token or ""),
        ops_token=str(args.ops_token or ""),
        timeout_seconds=float(args.request_timeout_seconds),
    )
    return CliContext(
        base_url=str(args.base_url),
        api=api,
        output=str(args.output),
        timeout_seconds=float(args.request_timeout_seconds),
        repo_root=repo_root,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ctx = _ctx_from_args(args)
    fn = getattr(args, "func", None)
    if fn is None:
        parser.print_help()
        return 2
    try:
        return int(fn(ctx, args))
    except ApiError as exc:
        payload = {
            "ok": False,
            "error_type": "ApiError",
            "status": int(exc.status),
            "message": str(exc),
            "body": exc.body_obj if exc.body_obj is not None else exc.body_text,
        }
        if ctx.output == "json":
            print(_json_dumps(payload), file=sys.stderr)
        else:
            print(_json_dumps(payload), file=sys.stderr)
        return 3
    except CliError as exc:
        payload = {"ok": False, "error_type": "CliError", "message": str(exc)}
        if ctx.output == "json":
            print(_json_dumps(payload), file=sys.stderr)
        else:
            print(_json_dumps(payload), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('{"ok":false,"error_type":"KeyboardInterrupt","message":"interrupted"}', file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
