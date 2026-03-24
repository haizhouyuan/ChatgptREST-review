"""Transport-level public agent MCP validation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_PUBLIC_AGENT_MCP_BASE_URL = "http://127.0.0.1:18712"
EXPECTED_PUBLIC_AGENT_MCP_TOOLS = (
    "advisor_agent_turn",
    "advisor_agent_cancel",
    "advisor_agent_status",
)


@dataclass
class PublicAgentMcpCheckResult:
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
class PublicAgentMcpValidationReport:
    base_url: str
    sample_message: str
    num_checks: int
    num_passed: int
    num_failed: int
    results: list[PublicAgentMcpCheckResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "sample_message": self.sample_message,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "results": [item.to_dict() for item in self.results],
        }


def run_public_agent_mcp_validation(
    *,
    base_url: str = DEFAULT_PUBLIC_AGENT_MCP_BASE_URL,
    sample_message: str = "请总结面试纪要",
) -> PublicAgentMcpValidationReport:
    mcp_url = str(base_url).rstrip("/") + "/mcp"

    initialize_payload = _jsonrpc_call(
        mcp_url,
        request_id=1,
        method="initialize",
        params={
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "phase13-public-agent-mcp-validation", "version": "1.0"},
        },
    )
    initialize_result = _mapping(initialize_payload.get("result"))
    server_info = _mapping(initialize_result.get("serverInfo"))

    tools_payload = _jsonrpc_call(mcp_url, request_id=2, method="tools/list", params={})
    tools_result = _mapping(tools_payload.get("result"))
    tools = list(tools_result.get("tools") or [])
    tool_names = [str(_mapping(tool).get("name") or "") for tool in tools]

    turn_payload = _jsonrpc_call(
        mcp_url,
        request_id=3,
        method="tools/call",
        params={
            "name": "advisor_agent_turn",
            "arguments": {
                "message": sample_message,
                "goal_hint": "planning",
                "timeout_seconds": 30,
                "auto_watch": True,
                "notify_done": False,
            },
        },
        timeout_seconds=90.0,
    )
    turn_result = _decode_tool_call_result(turn_payload)
    turn_provenance = _mapping(turn_result.get("provenance"))
    turn_next_action = _mapping(turn_result.get("next_action"))
    session_id = str(turn_result.get("session_id") or "")

    status_payload = _jsonrpc_call(
        mcp_url,
        request_id=4,
        method="tools/call",
        params={"name": "advisor_agent_status", "arguments": {"session_id": session_id}},
    )
    status_result = _decode_tool_call_result(status_payload)
    status_provenance = _mapping(status_result.get("provenance"))
    status_next_action = _mapping(status_result.get("next_action"))

    checks = [
        _build_check(
            name="initialize",
            details={
                "server_name": str(server_info.get("name") or ""),
                "server_version": str(server_info.get("version") or ""),
                "protocol_version": str(initialize_result.get("protocolVersion") or ""),
            },
            expectations={
                "server_name": "chatgptrest-agent-mcp",
                "protocol_version": "2025-03-26",
            },
        ),
        _build_check(
            name="tools_list",
            details={"tool_names": tool_names},
            expectations={"tool_names": list(EXPECTED_PUBLIC_AGENT_MCP_TOOLS)},
        ),
        _build_check(
            name="planning_clarify_turn",
            details={
                "session_id": session_id,
                "status": str(turn_result.get("status") or ""),
                "route": str(turn_provenance.get("route") or ""),
                "provider_path": list(turn_provenance.get("provider_path") or []),
                "next_action_type": str(turn_next_action.get("type") or ""),
                "output_shape": str(_mapping(turn_result.get("contract")).get("output_shape") or ""),
                "task_template": str(_mapping(turn_result.get("contract")).get("task_template") or ""),
            },
            expectations={
                "status": "needs_followup",
                "route": "clarify",
                "next_action_type": "await_user_clarification",
            },
            required_fields=("session_id",),
        ),
        _build_check(
            name="status_continuity",
            details={
                "session_id": str(status_result.get("session_id") or ""),
                "status": str(status_result.get("status") or ""),
                "route": str(status_result.get("route") or status_provenance.get("route") or ""),
                "next_action_type": str(status_next_action.get("type") or ""),
            },
            expectations={
                "session_id": session_id,
                "status": "needs_followup",
                "route": "clarify",
                "next_action_type": "await_user_clarification",
            },
        ),
    ]

    num_passed = sum(1 for item in checks if item.passed)
    return PublicAgentMcpValidationReport(
        base_url=str(base_url).rstrip("/"),
        sample_message=sample_message,
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        results=checks,
    )


def render_public_agent_mcp_report_markdown(report: PublicAgentMcpValidationReport) -> str:
    lines = [
        "# Public Agent MCP Validation Report",
        "",
        f"- base_url: {report.base_url}",
        f"- sample_message: {report.sample_message}",
        f"- checks: {report.num_checks}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Check | Pass | Key Details | Mismatch |",
        "|---|---:|---|---|",
    ]
    for result in report.results:
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


def write_public_agent_mcp_report(
    report: PublicAgentMcpValidationReport,
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_public_agent_mcp_report_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_check(
    *,
    name: str,
    details: dict[str, Any],
    expectations: dict[str, Any],
    required_fields: tuple[str, ...] = (),
) -> PublicAgentMcpCheckResult:
    mismatches: dict[str, dict[str, Any]] = {}
    for field_name in required_fields:
        if not details.get(field_name):
            mismatches[field_name] = {"expected": "non-empty", "actual": details.get(field_name)}
    for field_name, expected in expectations.items():
        actual = details.get(field_name)
        if actual != expected:
            mismatches[field_name] = {"expected": expected, "actual": actual}
    return PublicAgentMcpCheckResult(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _jsonrpc_call(
    url: str,
    *,
    request_id: int,
    method: str,
    params: dict[str, Any],
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}, ensure_ascii=False).encode(
            "utf-8"
        ),
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
        raise RuntimeError(f"HTTP {exc.code} calling MCP {method}: {text}") from exc
    return _decode_sse_json(raw)


def _decode_sse_json(raw: str) -> dict[str, Any]:
    for line in str(raw or "").splitlines():
        if line.startswith("data: "):
            payload = line[len("data: ") :].strip()
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed
    raise RuntimeError(f"unable to decode SSE JSON payload: {raw!r}")


def _decode_tool_call_result(payload: dict[str, Any]) -> dict[str, Any]:
    result = _mapping(payload.get("result"))
    structured = _mapping(result.get("structuredContent"))
    if structured:
        return structured
    for item in list(result.get("content") or []):
        entry = _mapping(item)
        if str(entry.get("type") or "") != "text":
            continue
        text = str(entry.get("text") or "").strip()
        if not text:
            continue
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError(f"unable to decode tool result payload: {payload!r}")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")

