"""Aggregate scoped provider-execution readiness gate."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE23_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "phase23_scoped_stack_readiness_gate_20260322"
PHASE24_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "phase24_direct_provider_execution_gate_20260323"
PHASE25_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "phase25_admin_mcp_provider_compatibility_gate_20260323"


@dataclass
class ScopedProviderExecutionReadinessCheck:
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
class ScopedProviderExecutionReadinessGateReport:
    overall_passed: bool
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[ScopedProviderExecutionReadinessCheck]
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


def run_scoped_provider_execution_readiness_gate() -> ScopedProviderExecutionReadinessGateReport:
    phase23_path = _latest_report_json(PHASE23_DIR)
    phase24_path = _latest_report_json(PHASE24_DIR)
    phase25_path = _latest_report_json(PHASE25_DIR)
    phase23 = _read_json(phase23_path)
    phase24 = _read_json(phase24_path)
    phase25 = _read_json(phase25_path)
    checks = [
        _build_check(
            name="phase23_scoped_stack_readiness_gate",
            details={
                "report": str(phase23_path),
                "overall_passed": bool(phase23.get("overall_passed") or False),
                "num_failed": int(phase23.get("num_failed") or 0),
            },
            expectations={"overall_passed": True, "num_failed": 0},
        ),
        _build_check(
            name="phase24_direct_provider_execution_gate",
            details={
                "report": str(phase24_path),
                "num_failed": int(phase24.get("num_failed") or 0),
                "num_checks": int(phase24.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
        _build_check(
            name="phase25_admin_mcp_provider_compatibility_gate",
            details={
                "report": str(phase25_path),
                "num_failed": int(phase25.get("num_failed") or 0),
                "num_checks": int(phase25.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return ScopedProviderExecutionReadinessGateReport(
        overall_passed=num_passed == len(checks),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
        scope_boundary=[
            "phase23 scoped stack readiness remains green",
            "allowed low-level generic provider execution path is proven via direct gemini_web.ask",
            "legacy admin MCP low-level provider wrapper remains dynamically replayable",
            "not a proof that direct chatgpt_web.ask should be used as a normal live path",
            "not a qwen or full generic-provider matrix",
            "not a heavy execution lane approval",
            "not a full-stack deployment proof",
        ],
    )


def render_scoped_provider_execution_readiness_gate_markdown(report: ScopedProviderExecutionReadinessGateReport) -> str:
    lines = [
        "# Scoped Provider Execution Readiness Gate Report",
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


def write_scoped_provider_execution_readiness_gate_report(
    report: ScopedProviderExecutionReadinessGateReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_scoped_provider_execution_readiness_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_check(*, name: str, details: dict[str, Any], expectations: dict[str, Any]) -> ScopedProviderExecutionReadinessCheck:
    mismatches: dict[str, dict[str, Any]] = {}
    for field_name, expected in expectations.items():
        actual = details.get(field_name)
        if actual != expected:
            mismatches[field_name] = {"expected": expected, "actual": actual}
    return ScopedProviderExecutionReadinessCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _latest_report_json(directory: Path) -> Path:
    pattern = re.compile(r"report_v(\d+)\.json$")
    candidates: list[tuple[int, Path]] = []
    for path in directory.glob("report_v*.json"):
        match = pattern.match(path.name)
        if match:
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
