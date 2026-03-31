"""Live public-agent cutover proof for the contract-first control plane."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_API_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_PUBLIC_AGENT_MCP_BASE_URL = "http://127.0.0.1:18712"
DEFAULT_SAMPLE_MESSAGE = "请总结面试纪要"
DEFAULT_SAMPLE_GOAL_HINT = "planning"
DEFAULT_PATCH = {
    "decision_to_support": "支持候选人是否进入下一轮的决定",
    "audience": "招聘经理",
}
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = Path.home() / ".config" / "chatgptrest" / "chatgptrest.env"
_WRAPPER_SCRIPT = _REPO_ROOT / "skills-src" / "chatgptrest-call" / "scripts" / "chatgptrest_call.py"


@dataclass
class PublicAgentLiveCutoverCheck:
    name: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "details": dict(self.details),
            "mismatches": dict(self.mismatches),
        }


@dataclass
class PublicAgentLiveCutoverReport:
    api_base_url: str
    mcp_base_url: str
    sample_message: str
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[PublicAgentLiveCutoverCheck]
    scope_boundary: str = (
        "live /v3/agent/turn plus public MCP field projection and same-session contract_patch proof only; "
        "not external provider completion proof"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_base_url": self.api_base_url,
            "mcp_base_url": self.mcp_base_url,
            "sample_message": self.sample_message,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
            "scope_boundary": self.scope_boundary,
        }


def run_public_agent_live_cutover_validation(
    *,
    api_base_url: str = DEFAULT_API_BASE_URL,
    mcp_base_url: str = DEFAULT_PUBLIC_AGENT_MCP_BASE_URL,
    sample_message: str = DEFAULT_SAMPLE_MESSAGE,
    goal_hint: str = DEFAULT_SAMPLE_GOAL_HINT,
) -> PublicAgentLiveCutoverReport:
    api_service = _service_snapshot("chatgptrest-api.service")
    mcp_service = _service_snapshot("chatgptrest-mcp.service")

    raw_session_id = f"live-cutover-api-{uuid.uuid4().hex[:12]}"
    raw_response = _agent_turn_http(
        api_base_url=api_base_url,
        session_id=raw_session_id,
        message=sample_message,
        goal_hint=goal_hint,
        delivery_mode="sync",
    )

    mcp_response = _mcp_turn(
        mcp_base_url=mcp_base_url,
        message=sample_message,
        goal_hint=goal_hint,
    )

    wrapper_response = _wrapper_turn(
        message=sample_message,
        goal_hint=goal_hint,
    )

    patch_session_id = f"live-cutover-patch-{uuid.uuid4().hex[:12]}"
    first_patch_response = _agent_turn_http(
        api_base_url=api_base_url,
        session_id=patch_session_id,
        message=sample_message,
        goal_hint=goal_hint,
        delivery_mode="sync",
    )
    second_patch_response = _agent_turn_http(
        api_base_url=api_base_url,
        session_id=patch_session_id,
        message=sample_message,
        goal_hint=goal_hint,
        delivery_mode="deferred",
        contract_patch=dict(DEFAULT_PATCH),
    )
    patched_session = _agent_session_http(api_base_url=api_base_url, session_id=patch_session_id)
    _cancel_session_http(api_base_url=api_base_url, session_id=patch_session_id)

    checks = [
        _build_check(
            name="api_service_running",
            details={
                "active_state": api_service.get("ActiveState"),
                "sub_state": api_service.get("SubState"),
                "start_timestamp": api_service.get("ExecMainStartTimestamp"),
            },
            expectations={"active_state": "active", "sub_state": "running"},
            required_fields=("start_timestamp",),
        ),
        _build_check(
            name="mcp_service_running",
            details={
                "active_state": mcp_service.get("ActiveState"),
                "sub_state": mcp_service.get("SubState"),
                "start_timestamp": mcp_service.get("ExecMainStartTimestamp"),
            },
            expectations={"active_state": "active", "sub_state": "running"},
            required_fields=("start_timestamp",),
        ),
        _projection_check(name="raw_api_clarify_projection", response=raw_response),
        _projection_check(name="public_mcp_clarify_projection", response=mcp_response),
        _projection_check(name="wrapper_clarify_projection", response=wrapper_response),
        _build_check(
            name="same_session_contract_patch_deferred",
            details={
                "first_status": str(first_patch_response.get("status") or ""),
                "first_route": str(_mapping(first_patch_response.get("provenance")).get("route") or ""),
                "second_status": str(second_patch_response.get("status") or ""),
                "second_next_action_type": str(_mapping(second_patch_response.get("next_action")).get("type") or ""),
                "second_delivery_mode": str(_mapping(second_patch_response.get("delivery")).get("mode") or ""),
                "second_has_task_intake": "task_intake" in second_patch_response,
                "second_has_control_plane": "control_plane" in second_patch_response,
            },
            expectations={
                "first_status": "needs_followup",
                "first_route": "clarify",
                "second_status": "running",
                "second_next_action_type": "check_status",
                "second_delivery_mode": "deferred",
                "second_has_task_intake": True,
                "second_has_control_plane": True,
            },
        ),
        _build_check(
            name="patched_session_projection",
            details={
                "status": str(patched_session.get("status") or ""),
                "route": str(patched_session.get("route") or ""),
                "contract_source": str(_mapping(patched_session.get("control_plane")).get("contract_source") or ""),
                "contract_completeness": float(_mapping(patched_session.get("control_plane")).get("contract_completeness") or 0.0),
                "decision_to_support": str(_mapping(patched_session.get("task_intake")).get("decision_to_support") or ""),
                "audience": str(_mapping(patched_session.get("task_intake")).get("audience") or ""),
                "has_task_intake": "task_intake" in patched_session,
                "has_control_plane": "control_plane" in patched_session,
            },
            expectations={
                "status": "running",
                "route": "planning",
                "contract_source": "client",
                "contract_completeness": 1.0,
                "has_task_intake": True,
                "has_control_plane": True,
            },
            required_fields=("decision_to_support", "audience"),
        ),
    ]

    num_passed = sum(1 for item in checks if item.passed)
    return PublicAgentLiveCutoverReport(
        api_base_url=str(api_base_url).rstrip("/"),
        mcp_base_url=str(mcp_base_url).rstrip("/"),
        sample_message=sample_message,
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
    )


def render_public_agent_live_cutover_markdown(report: PublicAgentLiveCutoverReport) -> str:
    lines = [
        "# Public Agent Live Cutover Validation Report",
        "",
        f"- api_base_url: {report.api_base_url}",
        f"- mcp_base_url: {report.mcp_base_url}",
        f"- sample_message: {report.sample_message}",
        f"- checks: {report.num_checks}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        f"- scope_boundary: {report.scope_boundary}",
        "",
        "| Check | Pass | Key Details | Mismatch |",
        "|---|---:|---|---|",
    ]
    for result in report.checks:
        details = ", ".join(f"{k}={v}" for k, v in result.details.items())
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in result.mismatches.items()
        )
        lines.append(
            "| {name} | {passed} | {details} | {mismatch} |".format(
                name=_escape_pipe(result.name),
                passed="yes" if result.passed else "no",
                details=_escape_pipe(details or "-"),
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    return "\n".join(lines) + "\n"


def write_public_agent_live_cutover_report(
    report: PublicAgentLiveCutoverReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_public_agent_live_cutover_markdown(report), encoding="utf-8")
    return json_path, md_path


def _projection_check(*, name: str, response: dict[str, Any]) -> PublicAgentLiveCutoverCheck:
    provenance = _mapping(response.get("provenance"))
    next_action = _mapping(response.get("next_action"))
    control_plane = _mapping(response.get("control_plane"))
    details = {
        "status": str(response.get("status") or ""),
        "route": str(provenance.get("route") or ""),
        "has_task_intake": "task_intake" in response,
        "has_control_plane": "control_plane" in response,
        "has_clarify_diagnostics": "clarify_diagnostics" in response,
        "next_action_has_clarify_diagnostics": isinstance(next_action.get("clarify_diagnostics"), dict),
        "contract_source": str(control_plane.get("contract_source") or ""),
    }
    return _build_check(
        name=name,
        details=details,
        expectations={
            "status": "needs_followup",
            "route": "clarify",
            "has_task_intake": True,
            "has_control_plane": True,
            "has_clarify_diagnostics": True,
            "next_action_has_clarify_diagnostics": True,
        },
    )


def _service_snapshot(unit: str) -> dict[str, str]:
    cmd = [
        "systemctl",
        "--user",
        "show",
        unit,
        "-p",
        "ActiveState",
        "-p",
        "SubState",
        "-p",
        "ExecMainStartTimestamp",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    payload: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key] = value.strip()
    return payload


def _agent_turn_http(
    *,
    api_base_url: str,
    session_id: str,
    message: str,
    goal_hint: str,
    delivery_mode: str,
    contract_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message": message,
        "goal_hint": goal_hint,
        "delivery_mode": delivery_mode,
        "session_id": session_id,
        "client": {"name": "mcp-agent", "instance": "public-mcp"},
    }
    if contract_patch:
        payload["contract_patch"] = dict(contract_patch)
    return _http_json(
        url=str(api_base_url).rstrip("/") + "/v3/agent/turn",
        method="POST",
        payload=payload,
    )


def _agent_session_http(*, api_base_url: str, session_id: str) -> dict[str, Any]:
    session_url = str(api_base_url).rstrip("/") + f"/v3/agent/session/{urllib.parse.quote(session_id, safe='')}"
    return _http_json(url=session_url, method="GET")


def _cancel_session_http(*, api_base_url: str, session_id: str) -> None:
    try:
        _http_json(
            url=str(api_base_url).rstrip("/") + "/v3/agent/cancel",
            method="POST",
            payload={"session_id": session_id},
        )
    except Exception:
        return


def _mcp_turn(*, mcp_base_url: str, message: str, goal_hint: str) -> dict[str, Any]:
    payload = _jsonrpc_call(
        str(mcp_base_url).rstrip("/") + "/mcp",
        request_id=3,
        method="tools/call",
        params={
            "name": "advisor_agent_turn",
            "arguments": {
                "message": message,
                "goal_hint": goal_hint,
                "timeout_seconds": 30,
                "auto_watch": True,
                "notify_done": False,
            },
        },
        timeout_seconds=90.0,
    )
    return _decode_tool_call_result(payload)


def _wrapper_turn(*, message: str, goal_hint: str) -> dict[str, Any]:
    cmd = [
        str((_REPO_ROOT / ".venv" / "bin" / "python").resolve()),
        str(_WRAPPER_SCRIPT.resolve()),
        "--question",
        str(message),
        "--goal-hint",
        str(goal_hint),
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_REPO_ROOT)
    result = subprocess.run(cmd, cwd=str(_REPO_ROOT), env=env, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def _http_json(*, url: str, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = _agent_http_headers()
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=120.0) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method.upper()} {url} failed with {exc.code}: {raw}") from exc
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _agent_http_headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "X-Api-Key": _api_key(),
        "X-Client-Name": "chatgptrest-mcp",
        "X-Client-Instance": "public-mcp",
        "X-Request-ID": f"live-cutover-{uuid.uuid4().hex[:12]}",
    }


def _api_key() -> str:
    envfile_values: dict[str, str] = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            if key in {"OPENMIND_API_KEY", "CHATGPTREST_API_TOKEN"} and value.strip():
                envfile_values[key] = value.strip()
    if envfile_values.get("OPENMIND_API_KEY"):
        return envfile_values["OPENMIND_API_KEY"]
    if envfile_values.get("CHATGPTREST_API_TOKEN"):
        return envfile_values["CHATGPTREST_API_TOKEN"]
    for key in ("OPENMIND_API_KEY", "CHATGPTREST_API_TOKEN"):
        value = str(os.environ.get(key, "")).strip()
        if value:
            return value
    raise RuntimeError("OPENMIND_API_KEY or CHATGPTREST_API_TOKEN is required for live public-agent validation")


def _jsonrpc_call(
    url: str,
    *,
    request_id: int,
    method: str,
    params: dict[str, Any],
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}, ensure_ascii=False).encode(
            "utf-8"
        ),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    try:
        with urllib.request.urlopen(request, timeout=float(timeout_seconds)) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MCP {method} failed with HTTP {exc.code}: {raw}") from exc
    lines = [line for line in raw.splitlines() if line.strip()]
    for line in reversed(lines):
        payload = line
        if payload.startswith("data:"):
            payload = payload[5:].strip()
        if not payload:
            continue
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError(f"MCP {method} returned no JSON payload: {raw}")


def _decode_tool_call_result(payload: dict[str, Any]) -> dict[str, Any]:
    result = _mapping(payload.get("result"))
    structured = _mapping(result.get("structuredContent"))
    if structured:
        return structured
    content = list(result.get("content") or [])
    for item in content:
        mapped = _mapping(item)
        if mapped.get("type") != "text":
            continue
        text = str(mapped.get("text") or "").strip()
        if not text:
            continue
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    return {}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _build_check(
    *,
    name: str,
    details: dict[str, Any],
    expectations: dict[str, Any],
    required_fields: tuple[str, ...] = (),
) -> PublicAgentLiveCutoverCheck:
    mismatches: dict[str, dict[str, Any]] = {}
    for field_name in required_fields:
        if not details.get(field_name):
            mismatches[field_name] = {"expected": "non-empty", "actual": details.get(field_name)}
    for field_name, expected in expectations.items():
        actual = details.get(field_name)
        if actual != expected:
            mismatches[field_name] = {"expected": expected, "actual": actual}
    return PublicAgentLiveCutoverCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _escape_pipe(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")
