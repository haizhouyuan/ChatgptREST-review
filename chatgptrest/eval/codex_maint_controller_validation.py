"""Validation pack for the lane-backed Codex maintenance controller."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYTEST = _REPO_ROOT / ".venv" / "bin" / "pytest"


@dataclass
class CodexMaintControllerCheck:
    name: str
    command: list[str]
    passed: bool
    returncode: int
    stdout: str
    stderr: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": list(self.command),
            "passed": self.passed,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "description": self.description,
        }


@dataclass
class CodexMaintControllerValidationReport:
    repo_root: str
    scope_boundary: str
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[CodexMaintControllerCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_root": self.repo_root,
            "scope_boundary": self.scope_boundary,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [check.to_dict() for check in self.checks],
        }


def _default_checks() -> list[tuple[str, str, list[str]]]:
    return [
        (
            "py_compile_controller_targets",
            "Compile the canonical lane controller, maint daemon bridge, attach adapter, and covered tests.",
            [
                "python3",
                "-m",
                "py_compile",
                "chatgptrest/executors/sre.py",
                "chatgptrest/ops_shared/maint_memory.py",
                "ops/maint_daemon.py",
                "ops/codex_maint_attach.py",
                "tests/test_sre_fix_request.py",
                "tests/test_maint_daemon_codex_sre.py",
                "tests/test_maint_bootstrap_memory.py",
                "tests/test_codex_maint_attach.py",
                "tests/test_maint_daemon_auto_repair_check.py",
            ],
        ),
        (
            "canonical_lane_taskpack_projection",
            "Prove the canonical lane writes controller metadata and taskpack views without creating a second truth source.",
            [
                str(_PYTEST),
                "-q",
                "tests/test_sre_fix_request.py::test_sre_fix_request_writes_controller_taskpack_projection",
            ],
        ),
        (
            "controller_decision_override_runtime_fix",
            "Prove controller decision overrides stay inside the canonical lane and route to repair.autofix without invoking Codex.",
            [
                str(_PYTEST),
                "-q",
                "tests/test_sre_fix_request.py::test_sre_fix_request_decision_override_routes_runtime_fix_without_codex",
            ],
        ),
        (
            "incident_codex_artifacts_are_mirror_pointer_only",
            "Prove maint incident analyze writes mirror/pointer artifacts back to the incident tree while canonical truth stays on the lane.",
            [
                str(_PYTEST),
                "-q",
                "tests/test_maint_daemon_codex_sre.py::test_run_codex_sre_analyze_incident_writes_lane_pointer_and_mirror_payload",
            ],
        ),
        (
            "maint_fallback_and_runtime_fix_reuse_canonical_lane",
            "Prove maint fallback and runtime autofix escalation both route through the canonical lane and reuse canonical decisions.",
            [
                str(_PYTEST),
                "-q",
                "tests/test_maint_daemon_codex_sre.py::test_route_repair_autofix_fallback_via_controller_writes_lane_pointer",
                "tests/test_maint_daemon_codex_sre.py::test_route_incident_runtime_fix_via_controller_reuses_canonical_decision",
            ],
        ),
        (
            "recurring_action_memory_preferences",
            "Prove recurring Codex action preferences can be read from global memory and injected into escalation context.",
            [
                str(_PYTEST),
                "-q",
                "tests/test_maint_bootstrap_memory.py::test_load_maintagent_action_preferences_prefers_recent_matching_actions",
            ],
        ),
        (
            "operator_attach_adapter",
            "Prove operator attach resolves canonical lane state, including incident-side source_lane pointers.",
            [
                str(_PYTEST),
                "-q",
                "tests/test_codex_maint_attach.py",
            ],
        ),
        (
            "repair_autofix_guardrails_regression",
            "Prove legacy repair.autofix guardrails stay idempotent while the canonical controller routes downstream jobs.",
            [
                str(_PYTEST),
                "-q",
                "tests/test_maint_daemon_auto_repair_check.py::test_maint_daemon_ensure_repair_autofix_job_is_idempotent",
                "tests/test_maint_daemon_auto_repair_check.py::test_maint_daemon_attach_repair_autofix_artifacts",
            ],
        ),
    ]


def _run_check_command(command: list[str], *, cwd: Path) -> tuple[int, str, str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def run_codex_maint_controller_validation(*, repo_root: str | Path | None = None) -> CodexMaintControllerValidationReport:
    root = Path(repo_root) if repo_root is not None else _REPO_ROOT
    checks: list[CodexMaintControllerCheck] = []
    for name, description, command in _default_checks():
        returncode, stdout, stderr = _run_check_command(command, cwd=root)
        checks.append(
            CodexMaintControllerCheck(
                name=name,
                command=command,
                passed=returncode == 0,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
                description=description,
            )
        )
    num_passed = sum(1 for item in checks if item.passed)
    return CodexMaintControllerValidationReport(
        repo_root=str(root),
        scope_boundary=(
            "lane-backed Codex maintenance control plane proof only; "
            "not a live provider or tmux/TUI rollout proof"
        ),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
    )


def render_codex_maint_controller_validation_markdown(report: CodexMaintControllerValidationReport) -> str:
    lines = [
        "# Codex Maint Controller Validation Report",
        "",
        f"- repo_root: {report.repo_root}",
        f"- checks: {report.num_checks}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        f"- scope_boundary: {report.scope_boundary}",
        "",
        "| Check | Pass | Command | Description |",
        "|---|---:|---|---|",
    ]
    for check in report.checks:
        lines.append(
            "| {name} | {passed} | {command} | {description} |".format(
                name=_escape_pipe(check.name),
                passed="yes" if check.passed else "no",
                command=_escape_pipe(" ".join(check.command)),
                description=_escape_pipe(check.description),
            )
        )
    lines.append("")
    for check in report.checks:
        lines.append(f"## {check.name}")
        lines.append("")
        lines.append(f"- passed: {'yes' if check.passed else 'no'}")
        lines.append(f"- returncode: {check.returncode}")
        lines.append(f"- command: `{ ' '.join(check.command) }`")
        if check.stdout:
            lines.append("")
            lines.append("```text")
            lines.append(check.stdout)
            lines.append("```")
        if check.stderr:
            lines.append("")
            lines.append("```text")
            lines.append(check.stderr)
            lines.append("```")
        lines.append("")
    return "\n".join(lines)


def write_codex_maint_controller_validation_report(
    report: CodexMaintControllerValidationReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    json_path = target_dir / f"{basename}.json"
    md_path = target_dir / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_codex_maint_controller_validation_markdown(report), encoding="utf-8")
    return json_path, md_path


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|")
