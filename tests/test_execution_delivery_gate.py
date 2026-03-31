from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.execution_delivery_gate import (
    render_execution_delivery_gate_markdown,
    run_execution_delivery_gate,
    write_execution_delivery_gate_report,
)


def test_phase18_execution_delivery_gate_passes() -> None:
    report = run_execution_delivery_gate()

    assert report.num_checks == 5
    assert report.num_failed == 0
    assert report.overall_passed is True


def test_phase18_consult_delivery_check_requires_completed_session_projection() -> None:
    report = run_execution_delivery_gate()

    consult_check = next(item for item in report.checks if item.name == "consult_delivery_completion")
    assert consult_check.passed is True
    assert consult_check.details["response_status"] == "completed"
    assert consult_check.details["session_status"] == "completed"


def test_execution_delivery_gate_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = run_execution_delivery_gate()

    json_path, md_path = write_execution_delivery_gate_report(report, out_dir=tmp_path, basename="report_v9")

    assert json_path.exists()
    assert md_path.exists()
    assert json_path.name == "report_v9.json"
    assert md_path.name == "report_v9.md"
    markdown = render_execution_delivery_gate_markdown(report)
    assert "Execution Delivery Gate Report" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown
