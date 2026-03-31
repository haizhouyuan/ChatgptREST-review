from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.pro_smoke_block_validation import (
    ProSmokeBlockCheckResult,
    ProSmokeBlockValidationReport,
    render_pro_smoke_block_report_markdown,
    run_pro_smoke_block_validation,
    write_pro_smoke_block_report,
)


def test_phase14_strict_pro_smoke_block_validation_passes() -> None:
    report = run_pro_smoke_block_validation()

    assert report.num_checks == 4
    assert report.num_failed == 0


def test_pro_smoke_block_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = ProSmokeBlockValidationReport(
        num_checks=1,
        num_passed=1,
        num_failed=0,
        results=[ProSmokeBlockCheckResult(name="active_docs_scrubbed", passed=True, details={"docs/contract_v1.md": "clean"})],
    )

    json_path, md_path = write_pro_smoke_block_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = render_pro_smoke_block_report_markdown(report)
    assert "Strict Pro Smoke Block Validation Report" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown
