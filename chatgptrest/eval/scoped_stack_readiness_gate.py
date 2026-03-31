"""Aggregate scoped readiness gate for the current public stack."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE19_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "phase19_scoped_launch_candidate_gate_20260322"
PHASE20_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "phase20_openclaw_dynamic_replay_gate_20260322"
PHASE21_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "phase21_api_provider_delivery_gate_20260322"
PHASE22_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "phase22_auth_hardening_secret_source_gate_20260322"


@dataclass
class ScopedStackReadinessCheck:
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
class ScopedStackReadinessGateReport:
    overall_passed: bool
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[ScopedStackReadinessCheck]
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


def run_scoped_stack_readiness_gate() -> ScopedStackReadinessGateReport:
    phase19_path = _latest_report_json(PHASE19_DIR)
    phase20_path = _latest_report_json(PHASE20_DIR)
    phase21_path = _latest_report_json(PHASE21_DIR)
    phase22_path = _latest_report_json(PHASE22_DIR)
    phase19 = _read_json(phase19_path)
    phase20 = _read_json(phase20_path)
    phase21 = _read_json(phase21_path)
    phase22 = _read_json(phase22_path)
    checks = [
        _build_check(
            name="phase19_scoped_launch_candidate_gate",
            details={
                "report": str(phase19_path),
                "overall_passed": bool(phase19.get("overall_passed") or False),
                "num_failed": int(phase19.get("num_failed") or 0),
            },
            expectations={"overall_passed": True, "num_failed": 0},
        ),
        _build_check(
            name="phase20_openclaw_dynamic_replay_gate",
            details={
                "report": str(phase20_path),
                "num_failed": int(phase20.get("num_failed") or 0),
                "num_checks": int(phase20.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
        _build_check(
            name="phase21_api_provider_delivery_gate",
            details={
                "report": str(phase21_path),
                "num_failed": int(phase21.get("num_failed") or 0),
                "num_checks": int(phase21.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
        _build_check(
            name="phase22_auth_hardening_secret_source_gate",
            details={
                "report": str(phase22_path),
                "num_failed": int(phase22.get("num_failed") or 0),
                "num_checks": int(phase22.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return ScopedStackReadinessGateReport(
        overall_passed=num_passed == len(checks),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
        scope_boundary=[
            "public surface + covered delivery chain",
            "dynamic OpenClaw plugin replay on the current public ingress",
            "correlated API-provider delivery evidence on the live advisor path",
            "auth-hardening + secret-source hygiene on the scoped public surface",
            "not a full-stack deployment proof",
            "not a generic web-provider or MCP-provider execution proof",
            "not a heavy execution lane approval",
        ],
    )


def render_scoped_stack_readiness_gate_markdown(report: ScopedStackReadinessGateReport) -> str:
    lines = [
        "# Scoped Stack Readiness Gate Report",
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


def write_scoped_stack_readiness_gate_report(
    report: ScopedStackReadinessGateReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_scoped_stack_readiness_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_check(*, name: str, details: dict[str, Any], expectations: dict[str, Any]) -> ScopedStackReadinessCheck:
    mismatches: dict[str, dict[str, Any]] = {}
    for field_name, expected in expectations.items():
        actual = details.get(field_name)
        if actual != expected:
            mismatches[field_name] = {"expected": expected, "actual": actual}
    return ScopedStackReadinessCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _latest_report_json(directory: Path) -> Path:
    pattern = re.compile(r"report_v(\d+)\.json$")
    candidates: list[tuple[int, Path]] = []
    for path in directory.glob("report_v*.json"):
        match = pattern.match(path.name)
        if not match:
            continue
        candidates.append((int(match.group(1)), path))
    if not candidates:
        raise FileNotFoundError(f"no report_v*.json found under {directory}")
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def _read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")
