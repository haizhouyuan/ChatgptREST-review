"""Live validation for the public-agent effects and delivery surface."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import urllib.parse
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.eval.public_agent_live_cutover_validation import (
    DEFAULT_API_BASE_URL,
    DEFAULT_PUBLIC_AGENT_MCP_BASE_URL,
    DEFAULT_SAMPLE_GOAL_HINT,
    DEFAULT_SAMPLE_MESSAGE,
    _agent_session_http as _shared_agent_session_http,
    _agent_turn_http as _shared_agent_turn_http,
    _api_key as _shared_api_key,
    _http_json as _shared_http_json,
    _mcp_turn as _shared_mcp_turn,
    _service_snapshot as _shared_service_snapshot,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER_SCRIPT = _REPO_ROOT / "skills-src" / "chatgptrest-call" / "scripts" / "chatgptrest_call.py"
_DEFAULT_WORKSPACE_ACTION = "deliver_report_to_docs"


@dataclass
class PublicAgentEffectsDeliveryCheck:
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
class PublicAgentEffectsDeliveryReport:
    api_base_url: str
    mcp_base_url: str
    sample_message: str
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[PublicAgentEffectsDeliveryCheck]
    scope_boundary: str = (
        "live public-agent lifecycle/effects/delivery projection proof only; "
        "not external provider completion proof and not heavy execution approval"
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


def run_public_agent_effects_delivery_validation(
    *,
    api_base_url: str = DEFAULT_API_BASE_URL,
    mcp_base_url: str = DEFAULT_PUBLIC_AGENT_MCP_BASE_URL,
    sample_message: str = DEFAULT_SAMPLE_MESSAGE,
    goal_hint: str = DEFAULT_SAMPLE_GOAL_HINT,
) -> PublicAgentEffectsDeliveryReport:
    api_service = _shared_service_snapshot("chatgptrest-api.service")
    mcp_service = _shared_service_snapshot("chatgptrest-mcp.service")

    raw_session_id = f"effects-raw-{uuid.uuid4().hex[:12]}"
    raw_response = _shared_agent_turn_http(
        api_base_url=api_base_url,
        session_id=raw_session_id,
        message=sample_message,
        goal_hint=goal_hint,
        delivery_mode="sync",
    )

    mcp_response = _shared_mcp_turn(
        mcp_base_url=mcp_base_url,
        message=sample_message,
        goal_hint=goal_hint,
    )

    wrapper_stdout, wrapper_summary = _wrapper_turn_with_summary(
        message=sample_message,
        goal_hint=goal_hint,
    )

    patch_session_id = f"effects-patch-{uuid.uuid4().hex[:12]}"
    _shared_agent_turn_http(
        api_base_url=api_base_url,
        session_id=patch_session_id,
        message=sample_message,
        goal_hint=goal_hint,
        delivery_mode="sync",
    )
    deferred_accept = _shared_agent_turn_http(
        api_base_url=api_base_url,
        session_id=patch_session_id,
        message=sample_message,
        goal_hint=goal_hint,
        delivery_mode="deferred",
        contract_patch={
            "decision_to_support": "支持候选人是否进入下一轮的决定",
            "audience": "招聘经理",
        },
    )
    patched_session = _shared_agent_session_http(api_base_url=api_base_url, session_id=patch_session_id)
    cancelled_session = _cancel_session_http(api_base_url=api_base_url, session_id=patch_session_id)

    workspace_response = _workspace_clarify_http(api_base_url=api_base_url)

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
        _clarify_surface_check(name="raw_api_clarify_lifecycle_delivery", response=raw_response),
        _clarify_surface_check(name="public_mcp_clarify_lifecycle_delivery", response=mcp_response),
        _wrapper_summary_check(stdout_response=wrapper_stdout, summary=wrapper_summary),
        _build_check(
            name="same_session_deferred_accept_surface",
            details={
                "status": str(deferred_accept.get("status") or ""),
                "accepted": bool(deferred_accept.get("accepted")),
                "phase": str(_mapping(deferred_accept.get("lifecycle")).get("phase") or ""),
                "delivery_mode": str(_mapping(deferred_accept.get("delivery")).get("mode") or ""),
                "delivery_accepted": bool(_mapping(deferred_accept.get("delivery")).get("accepted")),
                "next_action_type": str(_mapping(deferred_accept.get("lifecycle")).get("next_action_type") or ""),
            },
            expectations={
                "status": "running",
                "accepted": True,
                "phase": "accepted",
                "delivery_mode": "deferred",
                "delivery_accepted": True,
                "next_action_type": "check_status",
            },
        ),
        _build_check(
            name="patched_session_progress_surface",
            details={
                "status": str(patched_session.get("status") or ""),
                "route": str(patched_session.get("route") or ""),
                "phase": str(_mapping(patched_session.get("lifecycle")).get("phase") or ""),
                "delivery_mode": str(_mapping(patched_session.get("delivery")).get("mode") or ""),
                "contract_source": str(_mapping(patched_session.get("control_plane")).get("contract_source") or ""),
                "decision_to_support": str(_mapping(patched_session.get("task_intake")).get("decision_to_support") or ""),
            },
            expectations={
                "status": "running",
                "route": "planning",
                "phase": "progress",
                "delivery_mode": "deferred",
                "contract_source": "client",
            },
            required_fields=("decision_to_support",),
        ),
        _build_check(
            name="cancelled_session_surface",
            details={
                "status": str(cancelled_session.get("status") or ""),
                "phase": str(_mapping(cancelled_session.get("lifecycle")).get("phase") or ""),
                "session_terminal": bool(_mapping(cancelled_session.get("lifecycle")).get("session_terminal")),
                "delivery_terminal": bool(_mapping(cancelled_session.get("delivery")).get("terminal")),
                "message": str(cancelled_session.get("message") or ""),
            },
            expectations={
                "status": "cancelled",
                "phase": "cancelled",
                "session_terminal": True,
                "delivery_terminal": True,
                "message": "Session cancelled successfully",
            },
        ),
        _build_check(
            name="workspace_effect_surface",
            details={
                "status": str(workspace_response.get("status") or ""),
                "phase": str(_mapping(workspace_response.get("lifecycle")).get("phase") or ""),
                "action": str(_mapping(_mapping(workspace_response.get("effects")).get("workspace_action")).get("action") or ""),
                "workspace_status": str(
                    _mapping(_mapping(workspace_response.get("effects")).get("workspace_action")).get("status") or ""
                ),
                "missing_fields": list(_mapping(workspace_response.get("workspace_diagnostics")).get("missing_fields") or []),
            },
            expectations={
                "status": "needs_followup",
                "phase": "clarify_required",
                "action": _DEFAULT_WORKSPACE_ACTION,
                "workspace_status": "clarify_required",
                "missing_fields": ["body_markdown"],
            },
        ),
    ]

    num_passed = sum(1 for item in checks if item.passed)
    return PublicAgentEffectsDeliveryReport(
        api_base_url=str(api_base_url).rstrip("/"),
        mcp_base_url=str(mcp_base_url).rstrip("/"),
        sample_message=sample_message,
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
    )


def render_public_agent_effects_delivery_markdown(report: PublicAgentEffectsDeliveryReport) -> str:
    lines = [
        "# Public Agent Effects And Delivery Validation Report",
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


def write_public_agent_effects_delivery_report(
    report: PublicAgentEffectsDeliveryReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_public_agent_effects_delivery_markdown(report), encoding="utf-8")
    return json_path, md_path


def _clarify_surface_check(*, name: str, response: dict[str, Any]) -> PublicAgentEffectsDeliveryCheck:
    lifecycle = _mapping(response.get("lifecycle"))
    delivery = _mapping(response.get("delivery"))
    clarify = _mapping(response.get("clarify_diagnostics"))
    details = {
        "status": str(response.get("status") or ""),
        "phase": str(lifecycle.get("phase") or ""),
        "blocking": bool(lifecycle.get("blocking")),
        "delivery_mode": str(delivery.get("mode") or ""),
        "answer_ready": bool(delivery.get("answer_ready")),
        "has_task_intake": "task_intake" in response,
        "has_control_plane": "control_plane" in response,
        "has_clarify_diagnostics": "clarify_diagnostics" in response,
        "missing_fields_present": bool(list(clarify.get("missing_fields") or [])),
    }
    return _build_check(
        name=name,
        details=details,
        expectations={
            "status": "needs_followup",
            "phase": "clarify_required",
            "blocking": True,
            "delivery_mode": "sync",
            "answer_ready": True,
            "has_task_intake": True,
            "has_control_plane": True,
            "has_clarify_diagnostics": True,
            "missing_fields_present": True,
        },
    )


def _wrapper_summary_check(*, stdout_response: dict[str, Any], summary: dict[str, Any]) -> PublicAgentEffectsDeliveryCheck:
    details = {
        "stdout_status": str(stdout_response.get("status") or ""),
        "stdout_phase": str(_mapping(stdout_response.get("lifecycle")).get("phase") or ""),
        "summary_mode": str(summary.get("mode") or ""),
        "summary_session_id": str(summary.get("session_id") or ""),
        "summary_route": str(summary.get("route") or ""),
        "summary_phase": str(_mapping(summary.get("lifecycle")).get("phase") or ""),
        "summary_has_result": isinstance(summary.get("result"), dict),
        "summary_has_clarify_diagnostics": isinstance(_mapping(summary.get("result")).get("clarify_diagnostics"), dict),
    }
    return _build_check(
        name="wrapper_summary_projection",
        details=details,
        expectations={
            "stdout_status": "needs_followup",
            "stdout_phase": "clarify_required",
            "summary_mode": "agent_public_mcp",
            "summary_route": "clarify",
            "summary_phase": "clarify_required",
            "summary_has_result": True,
            "summary_has_clarify_diagnostics": True,
        },
        required_fields=("summary_session_id",),
    )


def _wrapper_turn_with_summary(*, message: str, goal_hint: str) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="public-agent-effects-") as tmp_dir:
        summary_path = Path(tmp_dir) / "summary.json"
        cmd = [
            str((_REPO_ROOT / ".venv" / "bin" / "python").resolve()),
            str(_WRAPPER_SCRIPT.resolve()),
            "--question",
            str(message),
            "--goal-hint",
            str(goal_hint),
            "--out-summary",
            str(summary_path),
        ]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(_REPO_ROOT)
        result = subprocess.run(cmd, cwd=str(_REPO_ROOT), env=env, capture_output=True, text=True, check=True)
        stdout_payload = json.loads(result.stdout)
        summary_payload: dict[str, Any] = {}
        if summary_path.exists():
            raw = summary_path.read_text(encoding="utf-8", errors="replace").strip()
            if raw:
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    summary_payload = loaded
        return stdout_payload, summary_payload


def _workspace_clarify_http(*, api_base_url: str) -> dict[str, Any]:
    return _shared_http_json(
        url=str(api_base_url).rstrip("/") + "/v3/agent/turn",
        method="POST",
        payload={
            "workspace_request": {
                "action": _DEFAULT_WORKSPACE_ACTION,
                "payload": {"title": "Daily report"},
            }
        },
    )


def _cancel_session_http(*, api_base_url: str, session_id: str) -> dict[str, Any]:
    return _shared_http_json(
        url=str(api_base_url).rstrip("/") + "/v3/agent/cancel",
        method="POST",
        payload={"session_id": session_id},
    )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _build_check(
    *,
    name: str,
    details: dict[str, Any],
    expectations: dict[str, Any],
    required_fields: tuple[str, ...] = (),
) -> PublicAgentEffectsDeliveryCheck:
    mismatches: dict[str, dict[str, Any]] = {}
    for field_name in required_fields:
        if not details.get(field_name):
            mismatches[field_name] = {"expected": "non-empty", "actual": details.get(field_name)}
    for field_name, expected in expectations.items():
        actual = details.get(field_name)
        if actual != expected:
            mismatches[field_name] = {"expected": expected, "actual": actual}
    return PublicAgentEffectsDeliveryCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _escape_pipe(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")
