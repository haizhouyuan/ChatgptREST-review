from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.eval import codex_maint_controller_validation as validation


def test_codex_maint_controller_validation_uses_expected_checks(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], *, cwd: Path):  # noqa: ANN001
        calls.append(command)
        return 0, "ok", ""

    monkeypatch.setattr(validation, "_run_check_command", fake_run)

    report = validation.run_codex_maint_controller_validation(repo_root=tmp_path)

    assert report.num_checks == 8
    assert report.num_passed == 8
    assert report.num_failed == 0
    assert calls[0][0:3] == ["python3", "-m", "py_compile"]
    assert any(check.name == "incident_codex_artifacts_are_mirror_pointer_only" for check in report.checks)
    assert any(check.name == "operator_attach_adapter" for check in report.checks)


def test_codex_maint_controller_validation_report_writer(tmp_path: Path) -> None:
    report = validation.CodexMaintControllerValidationReport(
        repo_root="/repo",
        scope_boundary="scope",
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[
            validation.CodexMaintControllerCheck(
                name="sample",
                command=["pytest", "-q", "tests/test_sample.py"],
                passed=True,
                returncode=0,
                stdout="1 passed",
                stderr="",
                description="sample description",
            )
        ],
    )

    json_path, md_path = validation.write_codex_maint_controller_validation_report(report, out_dir=tmp_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["num_passed"] == 1
    text = md_path.read_text(encoding="utf-8")
    assert "Codex Maint Controller Validation Report" in text
    assert "sample description" in text
