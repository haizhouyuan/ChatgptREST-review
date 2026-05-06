"""Transport-level automation-only public MCP validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.integrations.mcp_http_client import (
    McpHttpClient,
    McpHttpError,
    McpHttpInitializeHandshake,
    mcp_http_initialize_handshake,
)


DEFAULT_PUBLIC_AGENT_MCP_BASE_URL = "http://127.0.0.1:18712"
DEFAULT_VALIDATION_CLIENT_NAME = "chatgptrest-public-agent-mcp-validation"
DEFAULT_VALIDATION_CLIENT_VERSION = "validation-v1"
EXPECTED_PUBLIC_AGENT_MCP_PROTOCOL_VERSION = "2025-06-18"
REQUIRED_PUBLIC_AGENT_MCP_TOOLS = (
    "automation_ask",
    "automation_result",
    "automation_job_create",
    "automation_job_status",
    "automation_job_answer",
    "automation_job_cancel",
    "automation_job_events",
    "automation_conversation_fetch",
    "automation_conversation_get",
    "automation_conversation_find",
    "automation_gemini_generate_image_submit",
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
    surface: str
    validation_class: str
    sample_message: str
    num_checks: int
    num_passed: int
    num_failed: int
    results: list[PublicAgentMcpCheckResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "surface": self.surface,
            "validation_class": self.validation_class,
            "sample_message": self.sample_message,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "results": [item.to_dict() for item in self.results],
        }


def run_public_agent_mcp_validation(
    *,
    base_url: str = DEFAULT_PUBLIC_AGENT_MCP_BASE_URL,
    sample_message: str = "请基于 docs/contract_v1.md 为维护者输出一段自动化提交变更摘要。",
) -> PublicAgentMcpValidationReport:
    mcp_url = str(base_url).rstrip("/") + "/mcp"
    initialize = _mcp_initialize_handshake(mcp_url)
    initialize_result = _mapping(initialize.result)
    server_info = _mapping(initialize_result.get("serverInfo"))
    client = _mcp_client(mcp_url)
    tools = list(_mcp_list_tools(client))
    tool_names = [str(_mapping(tool).get("name") or "") for tool in tools]

    submit_result = _mcp_call_tool(
        client,
        tool_name="automation_ask",
        tool_args={
            "idempotency_key": "public-agent-mcp-validation-automation-ask",
            "question": sample_message,
            "provider": "chatgpt",
            "preset": "auto",
            "requested_execution_lane": "web_standard",
            "premium_allowed": False,
            "task_object_contract": {
                "object_type": "document",
                "object_ref": "docs/contract_v1.md",
                "intended_reader": "maintainer",
                "task_purpose": "probe_validation",
                "evidence_boundary": "repository_docs_only",
            },
            "delivery_preference": "push_only",
            "preflight": {
                "task_goal_clear": True,
                "expected_output_defined": True,
                "attachments_complete": True,
                "question_not_trivial": True,
            },
            "provider_selection": {
                "requested_provider": "chatgpt",
                "requested_preset": "auto",
                "selection_source": "probe_validation",
                "reason": "验证 automation-kernel-v1 canonical receipt（probe-only, non-premium）",
            },
            "timeout_seconds": 30,
            "auto_wait": True,
            "notify_done": False,
        },
        timeout_seconds=90.0,
    )
    duplicate_handoff = _looks_like_duplicate_in_progress(submit_result)
    job_id = str(submit_result.get("job_id") or "")
    if duplicate_handoff:
        job_id = str(submit_result.get("existing_job_id") or job_id)
    status_result = _mcp_call_tool(
        client,
        tool_name="automation_job_status",
        tool_args={"job_id": job_id},
    )
    receipt = status_result if duplicate_handoff else submit_result
    next_action = _mapping(receipt.get("next_action"))
    submit_expectations = (
        {
            "duplicate_handoff": True,
            "status_allowed": True,
        }
        if duplicate_handoff
        else {
            "completion_mode": "push",
            "push_enabled": True,
            "front_action": "return_now",
            "next_action_kind": "await_push",
            "next_action_channel": "controller",
            "background_wait_started": True,
            "status_allowed": True,
        }
    )
    submit_required_fields = ("job_id",) if duplicate_handoff else ("job_id", "expected_wait_bucket")

    checks = [
        _build_check(
            name="initialize",
            details={
                "server_name": str(server_info.get("name") or ""),
                "server_version": str(server_info.get("version") or ""),
                "protocol_version": str(initialize_result.get("protocolVersion") or ""),
                "mcp_session_id": str(initialize.session.session_id or ""),
            },
            expectations={
                "server_name": "chatgptrest-agent-mcp",
                "protocol_version": EXPECTED_PUBLIC_AGENT_MCP_PROTOCOL_VERSION,
            },
            required_fields=("mcp_session_id",),
        ),
        _build_required_tool_subset_check(tool_names),
        _build_cancel_reason_schema_check(tools),
        _build_check(
            name="automation_submit_receipt",
            details={
                "job_id": job_id,
                "status": str(receipt.get("status") or ""),
                "completion_mode": str(receipt.get("completion_mode") or ""),
                "push_enabled": bool(receipt.get("push_enabled")),
                "front_action": str(receipt.get("front_action") or ""),
                "next_action_kind": str(next_action.get("kind") or ""),
                "next_action_channel": str(next_action.get("channel") or ""),
                "expected_wait_bucket": str(receipt.get("expected_wait_bucket") or ""),
                "expected_wait_seconds": int(receipt.get("expected_wait_seconds") or 0),
                "background_wait_started": bool(receipt.get("background_wait_started")),
                "status_allowed": str(receipt.get("status") or "") in {"queued", "in_progress", "running", "completed"},
                "duplicate_handoff": duplicate_handoff,
                "turn_source": "status_after_duplicate_handoff" if duplicate_handoff else "turn",
                "receipt_contract_checked": not duplicate_handoff,
            },
            expectations=submit_expectations,
            required_fields=submit_required_fields,
        ),
        _build_check(
            name="status_continuity",
            details={
                "job_id": str(status_result.get("job_id") or ""),
                "status": str(status_result.get("status") or ""),
                "job_id_matches_turn": str(status_result.get("job_id") or "") == job_id,
                "status_allowed": str(status_result.get("status") or "") in {"queued", "in_progress", "running", "completed"},
            },
            expectations={
                "job_id": job_id,
                "job_id_matches_turn": True,
                "status_allowed": True,
            },
        ),
    ]

    num_passed = sum(1 for item in checks if item.passed)
    return PublicAgentMcpValidationReport(
        base_url=str(base_url).rstrip("/"),
        surface="automation-kernel-v1",
        validation_class="probe",
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
        f"- surface: {report.surface}",
        f"- validation_class: {report.validation_class}",
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
    expectations: dict[str, Any] | None = None,
    required_fields: tuple[str, ...] = (),
) -> PublicAgentMcpCheckResult:
    expectations = dict(expectations or {})
    mismatches: dict[str, dict[str, Any]] = {}
    passed = True
    for field_name in required_fields:
        if not str(details.get(field_name) or "").strip():
            mismatches[field_name] = {"expected": "nonempty", "actual": details.get(field_name)}
            passed = False
    for field_name, expected_value in expectations.items():
        actual_value = details.get(field_name)
        if actual_value != expected_value:
            mismatches[field_name] = {"expected": expected_value, "actual": actual_value}
            passed = False
    return PublicAgentMcpCheckResult(name=name, passed=passed, details=details, mismatches=mismatches)


def _build_required_tool_subset_check(tool_names: list[str]) -> PublicAgentMcpCheckResult:
    missing = [name for name in REQUIRED_PUBLIC_AGENT_MCP_TOOLS if name not in tool_names]
    return PublicAgentMcpCheckResult(
        name="tools_list",
        passed=not missing,
        details={
            "required_subset": list(REQUIRED_PUBLIC_AGENT_MCP_TOOLS),
            "advertised_tools": list(tool_names),
        },
        mismatches={"missing_tools": {"expected": [], "actual": missing}} if missing else {},
    )


def _tool_input_schema(tool: dict[str, Any]) -> dict[str, Any]:
    for key in ("inputSchema", "parameters", "input_schema"):
        schema = tool.get(key)
        if isinstance(schema, dict):
            return schema
    return {}


def _build_cancel_reason_schema_check(tools: list[dict[str, Any]]) -> PublicAgentMcpCheckResult:
    cancel_tool = next(
        (
            _mapping(tool)
            for tool in tools
            if str(_mapping(tool).get("name") or "") == "automation_job_cancel"
        ),
        {},
    )
    schema = _tool_input_schema(cancel_tool)
    properties = _mapping(schema.get("properties"))
    has_reason = isinstance(properties.get("reason"), dict)
    return PublicAgentMcpCheckResult(
        name="automation_job_cancel_schema",
        passed=bool(cancel_tool) and has_reason,
        details={
            "tool_present": bool(cancel_tool),
            "properties": sorted(str(key) for key in properties.keys()),
            "reason_property": properties.get("reason") if has_reason else None,
        },
        mismatches=(
            {}
            if bool(cancel_tool) and has_reason
            else {"reason": {"expected": "present", "actual": "missing"}}
        ),
    )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|")


def _looks_like_duplicate_in_progress(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    error_text = str(payload.get("error") or "").strip().lower()
    reason = str(payload.get("reason") or "").strip().lower()
    recommended_action = str(payload.get("recommended_client_action") or "").strip().lower()
    existing_job_id = str(payload.get("existing_job_id") or "").strip()
    if not existing_job_id:
        return False
    return (
        error_text == "duplicate_public_agent_session_in_progress"
        or error_text == "low_level_ask_duplicate_recently_submitted"
        or reason == "duplicate_recent_low_level_ask"
        or recommended_action == "reuse_existing_job"
    )


def _mcp_initialize_handshake(url: str) -> McpHttpInitializeHandshake:
    return mcp_http_initialize_handshake(
        url,
        client_name=DEFAULT_VALIDATION_CLIENT_NAME,
        client_version=DEFAULT_VALIDATION_CLIENT_VERSION,
    )


def _mcp_client(url: str) -> McpHttpClient:
    return McpHttpClient(
        url=url,
        client_name=DEFAULT_VALIDATION_CLIENT_NAME,
        client_version=DEFAULT_VALIDATION_CLIENT_VERSION,
    )


def _mcp_list_tools(client: McpHttpClient) -> list[dict[str, Any]]:
    return list(client.list_tools())


def _mcp_call_tool(
    client: McpHttpClient,
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    try:
        payload = client.call_tool(tool_name=tool_name, tool_args=tool_args, timeout_sec=timeout_seconds)
    except McpHttpError as exc:
        parsed = _structured_tool_error_payload(exc)
        if parsed:
            return parsed
        raise
    return dict(payload) if isinstance(payload, dict) else {"ok": False, "payload": payload}


def _structured_tool_error_payload(exc: McpHttpError) -> dict[str, Any] | None:
    text = str(exc)
    marker = "Error executing tool "
    if marker not in text:
        return None
    json_start = text.find("{", text.find(marker))
    if json_start < 0:
        return None
    try:
        payload = json.loads(text[json_start:])
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    detail = payload.get("detail")
    if isinstance(detail, dict):
        out = dict(detail)
        out.setdefault("ok", False)
        out.setdefault("mcp_tool_error", True)
        return out
    payload.setdefault("ok", False)
    payload.setdefault("mcp_tool_error", True)
    return payload
