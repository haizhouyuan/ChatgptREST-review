"""Launch gate for the current public ChatgptREST surface."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PHASE12_REPORT = Path("docs/dev_log/artifacts/phase12_core_ask_launch_gate_20260322/report_v1.json")
PHASE13_REPORT = Path("docs/dev_log/artifacts/phase13_public_agent_mcp_validation_20260322/report_v1.json")
PHASE14_REPORT = Path("docs/dev_log/artifacts/phase14_strict_pro_smoke_block_validation_20260322/report_v1.json")


@dataclass
class PublicSurfaceGateCheck:
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
class PublicSurfaceLaunchGateReport:
    overall_passed: bool
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[PublicSurfaceGateCheck]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_passed": self.overall_passed,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
        }


def run_public_surface_launch_gate() -> PublicSurfaceLaunchGateReport:
    phase12 = _read_json(PHASE12_REPORT)
    phase13 = _read_json(PHASE13_REPORT)
    phase14 = _read_json(PHASE14_REPORT)
    api_health = _http_json("http://127.0.0.1:18711/healthz")
    mcp_initialize = _mcp_initialize("http://127.0.0.1:18712/mcp")

    checks = [
        _build_check(
            name="phase12_core_ask_launch_gate",
            details={
                "report": str(PHASE12_REPORT),
                "overall_passed": bool(phase12.get("overall_passed") or False),
                "num_report_checks": len(list(phase12.get("report_checks") or [])),
            },
            expectations={"overall_passed": True},
        ),
        _build_check(
            name="phase13_public_agent_mcp_validation",
            details={
                "report": str(PHASE13_REPORT),
                "num_failed": int(phase13.get("num_failed") or 0),
                "num_checks": int(phase13.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
        _build_check(
            name="phase14_strict_pro_smoke_block_validation",
            details={
                "report": str(PHASE14_REPORT),
                "num_failed": int(phase14.get("num_failed") or 0),
                "num_checks": int(phase14.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
        _build_check(
            name="live_api_health",
            details={"ok": bool(api_health.get("ok") or False), "status": str(api_health.get("status") or "")},
            expectations={"ok": True, "status": "ok"},
        ),
        _build_check(
            name="live_public_mcp_initialize",
            details={
                "server_name": str(_mapping(mcp_initialize.get("serverInfo")).get("name") or ""),
                "protocol_version": str(mcp_initialize.get("protocolVersion") or ""),
            },
            expectations={"server_name": "chatgptrest-agent-mcp", "protocol_version": "2025-03-26"},
        ),
    ]

    num_passed = sum(1 for item in checks if item.passed)
    return PublicSurfaceLaunchGateReport(
        overall_passed=num_passed == len(checks),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
    )


def render_public_surface_launch_gate_markdown(report: PublicSurfaceLaunchGateReport) -> str:
    lines = [
        "# Public Surface Launch Gate Report",
        "",
        f"- overall_passed: {str(report.overall_passed).lower()}",
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


def write_public_surface_launch_gate_report(
    report: PublicSurfaceLaunchGateReport,
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_public_surface_launch_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_check(*, name: str, details: dict[str, Any], expectations: dict[str, Any]) -> PublicSurfaceGateCheck:
    mismatches: dict[str, dict[str, Any]] = {}
    for field_name, expected in expectations.items():
        actual = details.get(field_name)
        if actual != expected:
            mismatches[field_name] = {"expected": expected, "actual": actual}
    return PublicSurfaceGateCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _http_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as resp:
        parsed = json.loads(resp.read().decode("utf-8", errors="replace"))
    return parsed if isinstance(parsed, dict) else {}


def _mcp_initialize(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "phase15-public-surface-launch-gate", "version": "1.0"},
                },
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    for line in raw.splitlines():
        if line.startswith("data: "):
            parsed = json.loads(line[len("data: ") :].strip())
            return _mapping(parsed.get("result"))
    raise RuntimeError(f"unable to decode MCP initialize response: {raw!r}")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")

