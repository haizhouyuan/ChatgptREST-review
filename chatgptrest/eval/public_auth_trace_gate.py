"""Live auth, allowlist, and trace-header gate for public agent ingress."""

from __future__ import annotations

import json
import os
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_API_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_ENV_FILE = Path.home() / ".config" / "chatgptrest" / "chatgptrest.env"


@dataclass
class PublicAuthTraceCheck:
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
class PublicAuthTraceGateReport:
    base_url: str
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[PublicAuthTraceCheck]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
        }


def run_public_auth_trace_gate(*, base_url: str = DEFAULT_API_BASE_URL, env_file: Path = DEFAULT_ENV_FILE) -> PublicAuthTraceGateReport:
    tokens = _load_tokens(env_file)
    auth_header = _build_auth_header(tokens)

    no_auth = _post_turn(base_url=base_url, headers={})
    auth_only = _post_turn(base_url=base_url, headers=auth_header)
    auth_allowlisted_no_trace = _post_turn(
        base_url=base_url,
        headers={
            **auth_header,
            "X-Client-Name": "chatgptrestctl",
        },
    )
    auth_allowlisted_traced = _post_turn(
        base_url=base_url,
        headers={
            **auth_header,
            "X-Client-Name": "chatgptrestctl",
            "X-Client-Instance": "phase16-auth-trace-gate",
            "X-Request-ID": str(uuid.uuid4()),
        },
    )

    checks = [
        _build_check(
            name="no_auth_rejected",
            response=no_auth,
            expected_status=401,
            expected_error="Invalid or missing API key",
        ),
        _build_check(
            name="auth_without_allowlisted_client_rejected",
            response=auth_only,
            expected_status=403,
            expected_error="client_not_allowed",
        ),
        _build_check(
            name="auth_allowlisted_without_trace_rejected",
            response=auth_allowlisted_no_trace,
            expected_status=400,
            expected_error="missing_trace_headers",
        ),
        _build_check(
            name="auth_allowlisted_traced_request_accepted",
            response=auth_allowlisted_traced,
            expected_status=200,
            expected_route="clarify",
            expected_agent_status="needs_followup",
        ),
    ]

    num_passed = sum(1 for item in checks if item.passed)
    return PublicAuthTraceGateReport(
        base_url=str(base_url).rstrip("/"),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
    )


def render_public_auth_trace_gate_markdown(report: PublicAuthTraceGateReport) -> str:
    lines = [
        "# Public Auth Trace Gate Report",
        "",
        f"- base_url: {report.base_url}",
        f"- checks: {report.num_checks}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Check | Pass | Key Details | Mismatch |",
        "|---|---:|---|---|",
    ]
    for check in report.checks:
        details = ", ".join(f"{k}={v}" for k, v in check.details.items())
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
    return "\n".join(lines) + "\n"


def write_public_auth_trace_gate_report(
    report: PublicAuthTraceGateReport,
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_public_auth_trace_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_check(
    *,
    name: str,
    response: dict[str, Any],
    expected_status: int,
    expected_error: str | None = None,
    expected_route: str | None = None,
    expected_agent_status: str | None = None,
) -> PublicAuthTraceCheck:
    details = {
        "http_status": int(response.get("status_code") or 0),
        "error": str(response.get("error") or ""),
        "route": str(response.get("route") or ""),
        "agent_status": str(response.get("agent_status") or ""),
    }
    mismatches: dict[str, dict[str, Any]] = {}
    if details["http_status"] != expected_status:
        mismatches["http_status"] = {"expected": expected_status, "actual": details["http_status"]}
    if expected_error is not None and details["error"] != expected_error:
        mismatches["error"] = {"expected": expected_error, "actual": details["error"]}
    if expected_route is not None and details["route"] != expected_route:
        mismatches["route"] = {"expected": expected_route, "actual": details["route"]}
    if expected_agent_status is not None and details["agent_status"] != expected_agent_status:
        mismatches["agent_status"] = {"expected": expected_agent_status, "actual": details["agent_status"]}
    return PublicAuthTraceCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _load_tokens(env_file: Path) -> dict[str, str]:
    values = {
        "OPENMIND_API_KEY": os.environ.get("OPENMIND_API_KEY", "").strip(),
        "CHATGPTREST_API_TOKEN": os.environ.get("CHATGPTREST_API_TOKEN", "").strip(),
    }
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key_n = key.strip()
            if key_n not in values or values[key_n]:
                continue
            values[key_n] = value.strip().strip('"').strip("'")
    return values


def _build_auth_header(tokens: dict[str, str]) -> dict[str, str]:
    if tokens.get("OPENMIND_API_KEY"):
        return {"X-Api-Key": tokens["OPENMIND_API_KEY"]}
    if tokens.get("CHATGPTREST_API_TOKEN"):
        return {"Authorization": f"Bearer {tokens['CHATGPTREST_API_TOKEN']}"}
    raise RuntimeError("no local auth token available for public auth trace gate")


def _post_turn(*, base_url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(
        str(base_url).rstrip("/") + "/v3/agent/turn",
        data=json.dumps({"message": "请总结面试纪要", "goal_hint": "planning"}, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status_code = resp.status
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    body = json.loads(text) if text.strip() else {}
    detail = body.get("detail") if isinstance(body, dict) else {}
    detail_map = detail if isinstance(detail, dict) else {}
    provenance = body.get("provenance") if isinstance(body, dict) else {}
    provenance_map = provenance if isinstance(provenance, dict) else {}
    return {
        "status_code": status_code,
        "error": detail_map.get("error") or (detail if isinstance(detail, str) else ""),
        "route": provenance_map.get("route") or body.get("route") if isinstance(body, dict) else "",
        "agent_status": body.get("status") if isinstance(body, dict) else "",
    }


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")

