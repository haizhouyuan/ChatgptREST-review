from __future__ import annotations

from pathlib import Path

import chatgptrest.eval.scoped_stack_readiness_gate as mod


def test_run_scoped_stack_readiness_gate_uses_latest_reports(tmp_path: Path, monkeypatch) -> None:
    phase19 = tmp_path / "phase19"
    phase20 = tmp_path / "phase20"
    phase21 = tmp_path / "phase21"
    phase22 = tmp_path / "phase22"
    for directory in (phase19, phase20, phase21, phase22):
        directory.mkdir()
    (phase19 / "report_v1.json").write_text('{"overall_passed": true, "num_failed": 0}', encoding="utf-8")
    (phase20 / "report_v1.json").write_text('{"num_failed": 0, "num_checks": 3}', encoding="utf-8")
    (phase21 / "report_v1.json").write_text('{"num_failed": 1, "num_checks": 3}', encoding="utf-8")
    (phase21 / "report_v2.json").write_text('{"num_failed": 0, "num_checks": 3}', encoding="utf-8")
    (phase22 / "report_v1.json").write_text('{"num_failed": 0, "num_checks": 5}', encoding="utf-8")

    monkeypatch.setattr(mod, "PHASE19_DIR", phase19)
    monkeypatch.setattr(mod, "PHASE20_DIR", phase20)
    monkeypatch.setattr(mod, "PHASE21_DIR", phase21)
    monkeypatch.setattr(mod, "PHASE22_DIR", phase22)

    report = mod.run_scoped_stack_readiness_gate()

    assert report.overall_passed is True
    assert report.num_failed == 0
    check = next(item for item in report.checks if item.name == "phase21_api_provider_delivery_gate")
    assert check.details["report"].endswith("report_v2.json")


def test_scoped_stack_readiness_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.ScopedStackReadinessGateReport(
        overall_passed=True,
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[mod.ScopedStackReadinessCheck(name="phase19", passed=True, details={"num_failed": 0})],
        scope_boundary=["scoped stack only"],
    )

    json_path, md_path = mod.write_scoped_stack_readiness_gate_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    assert "Scoped Stack Readiness Gate Report" in md_path.read_text(encoding="utf-8")
