"""Aggregate launch-candidate gate for the current scoped public release."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PHASE17_REPORT_CANDIDATES = (
    Path("docs/dev_log/artifacts/phase17_scoped_public_release_gate_20260322/report_v3.json"),
    Path("docs/dev_log/artifacts/phase17_scoped_public_release_gate_20260322/report_v2.json"),
    Path("docs/dev_log/artifacts/phase17_scoped_public_release_gate_20260322/report_v1.json"),
)
PHASE18_REPORT_CANDIDATES = (
    Path("docs/dev_log/artifacts/phase18_execution_delivery_gate_20260322/report_v3.json"),
    Path("docs/dev_log/artifacts/phase18_execution_delivery_gate_20260322/report_v2.json"),
    Path("docs/dev_log/artifacts/phase18_execution_delivery_gate_20260322/report_v1.json"),
)


@dataclass
class ScopedLaunchCandidateCheck:
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
class ScopedLaunchCandidateGateReport:
    overall_passed: bool
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[ScopedLaunchCandidateCheck]
    scope_boundary: str = (
        "scoped public release plus public-facade execution delivery only; "
        "not external provider replay, not OpenClaw dynamic replay, not heavy execution approval"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_passed": self.overall_passed,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
            "scope_boundary": self.scope_boundary,
        }


def run_scoped_launch_candidate_gate(
    *,
    phase17_report_path: str | Path | None = None,
    phase18_report_path: str | Path | None = None,
) -> ScopedLaunchCandidateGateReport:
    if phase17_report_path is None:
        phase17_report_path = _resolve_existing_report_path(PHASE17_REPORT_CANDIDATES)
    if phase18_report_path is None:
        phase18_report_path = _resolve_existing_report_path(PHASE18_REPORT_CANDIDATES)
    phase17 = _read_json(Path(phase17_report_path))
    phase18 = _read_json(Path(phase18_report_path))

    checks = [
        _build_check(
            name="phase17_scoped_public_release_gate",
            details={
                "report": str(phase17_report_path),
                "overall_passed": bool(phase17.get("overall_passed") or False),
                "num_failed": int(phase17.get("num_failed") or 0),
            },
            expectations={"overall_passed": True, "num_failed": 0},
        ),
        _build_check(
            name="phase18_execution_delivery_gate",
            details={
                "report": str(phase18_report_path),
                "overall_passed": bool(phase18.get("overall_passed") or False),
                "num_failed": int(phase18.get("num_failed") or 0),
            },
            expectations={"overall_passed": True, "num_failed": 0},
        ),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return ScopedLaunchCandidateGateReport(
        overall_passed=num_passed == len(checks),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
    )


def render_scoped_launch_candidate_gate_markdown(report: ScopedLaunchCandidateGateReport) -> str:
    lines = [
        "# Scoped Launch Candidate Gate Report",
        "",
        f"- overall_passed: {str(report.overall_passed).lower()}",
        f"- checks: {report.num_checks}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        f"- scope_boundary: {report.scope_boundary}",
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


def write_scoped_launch_candidate_gate_report(
    report: ScopedLaunchCandidateGateReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_scoped_launch_candidate_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_check(*, name: str, details: dict[str, Any], expectations: dict[str, Any]) -> ScopedLaunchCandidateCheck:
    mismatches: dict[str, dict[str, Any]] = {}
    for field_name, expected in expectations.items():
        actual = details.get(field_name)
        if actual != expected:
            mismatches[field_name] = {"expected": expected, "actual": actual}
    return ScopedLaunchCandidateCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _resolve_existing_report_path(candidates: tuple[Path, ...]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")
