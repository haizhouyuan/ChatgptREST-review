"""Scoped release gate for the current public ChatgptREST surface."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PHASE15_REPORT = Path("docs/dev_log/artifacts/phase15_public_surface_launch_gate_20260322/report_v1.json")
PHASE16_REPORT = Path("docs/dev_log/artifacts/phase16_public_auth_trace_gate_20260322/report_v1.json")


@dataclass
class ScopedReleaseGateCheck:
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
class ScopedPublicReleaseGateReport:
    overall_passed: bool
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[ScopedReleaseGateCheck]
    scope_boundary: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_passed": self.overall_passed,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
            "scope_boundary": list(self.scope_boundary),
        }


def run_scoped_public_release_gate() -> ScopedPublicReleaseGateReport:
    phase15 = _read_json(PHASE15_REPORT)
    phase16 = _read_json(PHASE16_REPORT)
    checks = [
        _build_check(
            name="phase15_public_surface_launch_gate",
            details={
                "report": str(PHASE15_REPORT),
                "overall_passed": bool(phase15.get("overall_passed") or False),
                "num_failed": int(phase15.get("num_failed") or 0),
            },
            expectations={"overall_passed": True, "num_failed": 0},
        ),
        _build_check(
            name="phase16_public_auth_trace_gate",
            details={
                "report": str(PHASE16_REPORT),
                "num_failed": int(phase16.get("num_failed") or 0),
                "num_checks": int(phase16.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return ScopedPublicReleaseGateReport(
        overall_passed=num_passed == len(checks),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
        scope_boundary=[
            "public /v3/agent/turn path in scoped planning/research coverage",
            "public agent MCP transport usability",
            "strict Pro smoke/trivial blocking",
            "auth + allowlist + trace-header enforcement for public agent writes",
            "not a full-stack execution delivery proof",
            "not an OpenClaw dynamic replay proof",
            "not a heavy execution lane approval",
        ],
    )


def render_scoped_public_release_gate_markdown(report: ScopedPublicReleaseGateReport) -> str:
    lines = [
        "# Scoped Public Release Gate Report",
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
    lines.append("")
    lines.append("## Scope Boundary")
    lines.append("")
    for item in report.scope_boundary:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_scoped_public_release_gate_report(
    report: ScopedPublicReleaseGateReport,
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_scoped_public_release_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_check(*, name: str, details: dict[str, Any], expectations: dict[str, Any]) -> ScopedReleaseGateCheck:
    mismatches: dict[str, dict[str, Any]] = {}
    for field_name, expected in expectations.items():
        actual = details.get(field_name)
        if actual != expected:
            mismatches[field_name] = {"expected": expected, "actual": actual}
    return ScopedReleaseGateCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")

