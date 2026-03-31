"""Scoped live gate for API-provider delivery on the advisor surface."""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.eval.public_auth_trace_gate import _build_auth_header, _load_tokens


DEFAULT_API_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_ENV_FILE = Path.home() / ".config" / "chatgptrest" / "chatgptrest.env"
DEFAULT_EVENTS_DB = Path.home() / ".openmind" / "events.db"
DEFAULT_SAMPLE_MESSAGE = "QXJZ-9173 是什么概念？如果不知道就基于常识判断并明确说明。"


@dataclass
class ApiProviderDeliveryCheck:
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
class ApiProviderDeliveryGateReport:
    base_url: str
    trace_id: str
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[ApiProviderDeliveryCheck]
    scope_boundary: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "trace_id": self.trace_id,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
            "scope_boundary": list(self.scope_boundary),
        }


def run_api_provider_delivery_gate(
    *,
    base_url: str = DEFAULT_API_BASE_URL,
    env_file: Path = DEFAULT_ENV_FILE,
    events_db: Path = DEFAULT_EVENTS_DB,
) -> ApiProviderDeliveryGateReport:
    trace_id = f"phase21-api-provider-{uuid.uuid4().hex[:12]}"
    auth_header = _build_auth_header(_load_tokens(env_file))
    advise = _post_advise(base_url=base_url, auth_header=auth_header, trace_id=trace_id)
    trace_snapshot = _get_trace_snapshot(base_url=base_url, auth_header=auth_header, trace_id=trace_id)
    llm_events = _read_llm_events(events_db=events_db, trace_id=trace_id)
    checks = [
        _build_advise_delivery_check(advise),
        _build_trace_snapshot_check(trace_snapshot),
        _build_llm_event_correlation_check(llm_events=llm_events, trace_id=trace_id),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return ApiProviderDeliveryGateReport(
        base_url=str(base_url).rstrip("/"),
        trace_id=trace_id,
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
        scope_boundary=[
            "live /v2/advisor/advise request on the current 18711 advisor host",
            "correlated same-trace llm_connector completion evidence from EventBus",
            "covered API-provider quick-answer delivery only",
            "not a generic external-provider proof",
            "not a web-provider or MCP-provider proof",
            "not a full-stack deployment proof",
        ],
    )


def render_api_provider_delivery_gate_markdown(report: ApiProviderDeliveryGateReport) -> str:
    lines = [
        "# API Provider Delivery Gate Report",
        "",
        f"- base_url: {report.base_url}",
        f"- trace_id: {report.trace_id}",
        f"- checks: {report.num_checks}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Check | Pass | Key Details | Mismatch |",
        "|---|---:|---|---|",
    ]
    for check in report.checks:
        details = ", ".join(f"{key}={value}" for key, value in check.details.items())
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in check.mismatches.items()
        )
        lines.append(
            "| {name} | {passed} | {details} | {mismatch} |".format(
                name=_escape_pipe(check.name),
                passed="yes" if check.passed else "no",
                details=_escape_pipe(details or "-"),
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    lines.append("")
    lines.append("## Scope Boundary")
    lines.append("")
    for item in report.scope_boundary:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_api_provider_delivery_gate_report(
    report: ApiProviderDeliveryGateReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_api_provider_delivery_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_advise_delivery_check(response: dict[str, Any]) -> ApiProviderDeliveryCheck:
    body = response.get("body") if isinstance(response.get("body"), dict) else {}
    route_result = body.get("route_result") if isinstance(body, dict) else {}
    route_result = route_result if isinstance(route_result, dict) else {}
    details = {
        "http_status": int(response.get("status_code") or 0),
        "response_status": str(body.get("status") or ""),
        "selected_route": str(body.get("selected_route") or ""),
        "route_result_route": str(route_result.get("route") or ""),
        "controller_status": str(body.get("controller_status") or ""),
        "answer_nonempty": bool(str(body.get("answer") or "").strip()),
    }
    expectations = {
        "http_status": 200,
        "response_status": "completed",
        "selected_route": "hybrid",
        "route_result_route": "quick_ask",
        "controller_status": "DELIVERED",
        "answer_nonempty": True,
    }
    mismatches = {
        field_name: {"expected": expected, "actual": details[field_name]}
        for field_name, expected in expectations.items()
        if details[field_name] != expected
    }
    return ApiProviderDeliveryCheck(
        name="live_advise_delivery",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_trace_snapshot_check(snapshot: dict[str, Any]) -> ApiProviderDeliveryCheck:
    details = {
        "trace_status": str(snapshot.get("status") or ""),
        "selected_route": str(snapshot.get("selected_route") or ""),
        "route_result_route": str(((snapshot.get("route_result") or {}) if isinstance(snapshot.get("route_result"), dict) else {}).get("route") or ""),
        "answer_nonempty": bool(str(snapshot.get("answer") or "").strip()),
    }
    expectations = {
        "trace_status": "completed",
        "selected_route": "hybrid",
        "route_result_route": "quick_ask",
        "answer_nonempty": True,
    }
    mismatches = {
        field_name: {"expected": expected, "actual": details[field_name]}
        for field_name, expected in expectations.items()
        if details[field_name] != expected
    }
    return ApiProviderDeliveryCheck(
        name="persisted_trace_snapshot",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_llm_event_correlation_check(*, llm_events: list[dict[str, Any]], trace_id: str) -> ApiProviderDeliveryCheck:
    first_event = llm_events[0] if llm_events else {}
    first_data = first_event.get("data") if isinstance(first_event.get("data"), dict) else {}
    details = {
        "trace_id": trace_id,
        "event_count": len(llm_events),
        "first_source": str(first_event.get("source") or ""),
        "first_event_type": str(first_event.get("event_type") or ""),
        "first_model": str(first_data.get("model") or ""),
        "first_preset": str(first_data.get("preset") or ""),
    }
    mismatches: dict[str, dict[str, Any]] = {}
    if details["event_count"] < 1:
        mismatches["event_count"] = {"expected": ">=1", "actual": details["event_count"]}
    if details["first_source"] != "llm_connector":
        mismatches["first_source"] = {"expected": "llm_connector", "actual": details["first_source"]}
    if details["first_event_type"] != "llm.call_completed":
        mismatches["first_event_type"] = {"expected": "llm.call_completed", "actual": details["first_event_type"]}
    if not details["first_model"]:
        mismatches["first_model"] = {"expected": "non-empty", "actual": details["first_model"]}
    if details["first_preset"] != "default":
        mismatches["first_preset"] = {"expected": "default", "actual": details["first_preset"]}
    return ApiProviderDeliveryCheck(
        name="eventbus_llm_trace_correlation",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _post_advise(*, base_url: str, auth_header: dict[str, str], trace_id: str) -> dict[str, Any]:
    payload = {
        "message": DEFAULT_SAMPLE_MESSAGE,
        "trace_id": trace_id,
        "task_intake": {
            "spec_version": "task-intake-v2",
            "source": "rest",
            "ingress_lane": "advisor_advise_v2",
            "scenario": "general",
            "output_shape": "text_answer",
        },
    }
    request = urllib.request.Request(
        str(base_url).rstrip("/") + "/v2/advisor/advise",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **auth_header},
        method="POST",
    )
    return _request_json(request)


def _get_trace_snapshot(*, base_url: str, auth_header: dict[str, str], trace_id: str) -> dict[str, Any]:
    request = urllib.request.Request(
        str(base_url).rstrip("/") + f"/v2/advisor/trace/{trace_id}",
        headers=dict(auth_header),
        method="GET",
    )
    response = _request_json(request)
    body = response.get("body")
    return body if isinstance(body, dict) else {}


def _request_json(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            text = response.read().decode("utf-8", errors="replace")
            return {
                "status_code": response.status,
                "body": json.loads(text) if text else {},
            }
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text) if text else {}
        except json.JSONDecodeError:
            body = {"raw": text}
        return {"status_code": exc.code, "body": body}


def _read_llm_events(*, events_db: Path, trace_id: str) -> list[dict[str, Any]]:
    query = """
        SELECT source, event_type, trace_id, data
          FROM trace_events
         WHERE trace_id = ?
           AND source = 'llm_connector'
         ORDER BY timestamp ASC
    """
    with sqlite3.connect(events_db) as conn:
        rows = conn.execute(query, (trace_id,)).fetchall()
    result: list[dict[str, Any]] = []
    for source, event_type, row_trace_id, raw_data in rows:
        try:
            data = json.loads(raw_data or "{}")
        except json.JSONDecodeError:
            data = {"raw": raw_data}
        result.append(
            {
                "source": str(source or ""),
                "event_type": str(event_type or ""),
                "trace_id": str(row_trace_id or ""),
                "data": data if isinstance(data, dict) else {"value": data},
            }
        )
    return result


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")
