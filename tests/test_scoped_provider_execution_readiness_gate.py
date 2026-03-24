from __future__ import annotations

from pathlib import Path

import chatgptrest.eval.scoped_provider_execution_readiness_gate as mod


def test_run_scoped_provider_execution_readiness_gate_uses_latest_reports(tmp_path: Path, monkeypatch) -> None:
    phase23 = tmp_path / "phase23"
    phase24 = tmp_path / "phase24"
    phase25 = tmp_path / "phase25"
    for directory in (phase23, phase24, phase25):
        directory.mkdir()
    (phase23 / "report_v1.json").write_text('{"overall_passed": true, "num_failed": 0}', encoding="utf-8")
    (phase24 / "report_v1.json").write_text('{"num_failed": 1, "num_checks": 3}', encoding="utf-8")
    (phase24 / "report_v2.json").write_text('{"num_failed": 0, "num_checks": 3}', encoding="utf-8")
    (phase25 / "report_v1.json").write_text('{"num_failed": 0, "num_checks": 5}', encoding="utf-8")

    monkeypatch.setattr(mod, "PHASE23_DIR", phase23)
    monkeypatch.setattr(mod, "PHASE24_DIR", phase24)
    monkeypatch.setattr(mod, "PHASE25_DIR", phase25)

    report = mod.run_scoped_provider_execution_readiness_gate()

    assert report.overall_passed is True
    assert report.num_failed == 0
    check = next(item for item in report.checks if item.name == "phase24_direct_provider_execution_gate")
    assert check.details["report"].endswith("report_v2.json")


def test_scoped_provider_execution_readiness_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.ScopedProviderExecutionReadinessGateReport(
        overall_passed=True,
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[mod.ScopedProviderExecutionReadinessCheck(name="phase24", passed=True, details={"num_failed": 0})],
        scope_boundary=["scoped provider execution only"],
    )

    json_path, md_path = mod.write_scoped_provider_execution_readiness_gate_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    assert "Scoped Provider Execution Readiness Gate Report" in md_path.read_text(encoding="utf-8")
