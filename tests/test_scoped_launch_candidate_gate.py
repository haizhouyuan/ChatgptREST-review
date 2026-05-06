from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.eval.scoped_launch_candidate_gate import (
    _resolve_existing_report_path,
    render_scoped_launch_candidate_gate_markdown,
    run_scoped_launch_candidate_gate,
    write_scoped_launch_candidate_gate_report,
)


def test_phase19_scoped_launch_candidate_gate_passes_with_green_inputs(tmp_path: Path) -> None:
    phase17 = tmp_path / "phase17.json"
    phase18 = tmp_path / "phase18.json"
    phase17.write_text(json.dumps({"overall_passed": True, "num_failed": 0}), encoding="utf-8")
    phase18.write_text(json.dumps({"overall_passed": True, "num_failed": 0}), encoding="utf-8")

    report = run_scoped_launch_candidate_gate(phase17_report_path=phase17, phase18_report_path=phase18)

    assert report.num_checks == 2
    assert report.num_failed == 0
    assert report.overall_passed is True


def test_scoped_launch_candidate_gate_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    phase17 = tmp_path / "phase17.json"
    phase18 = tmp_path / "phase18.json"
    phase17.write_text(json.dumps({"overall_passed": True, "num_failed": 0}), encoding="utf-8")
    phase18.write_text(json.dumps({"overall_passed": True, "num_failed": 0}), encoding="utf-8")
    report = run_scoped_launch_candidate_gate(phase17_report_path=phase17, phase18_report_path=phase18)

    json_path, md_path = write_scoped_launch_candidate_gate_report(report, out_dir=tmp_path / "out", basename="report_v9")

    assert json_path.exists()
    assert md_path.exists()
    assert json_path.name == "report_v9.json"
    assert md_path.name == "report_v9.md"
    markdown = render_scoped_launch_candidate_gate_markdown(report)
    assert "Scoped Launch Candidate Gate Report" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown


def test_scoped_launch_candidate_gate_prefers_latest_existing_input_report(tmp_path: Path) -> None:
    v1 = tmp_path / "report_v1.json"
    v2 = tmp_path / "report_v2.json"
    v1.write_text("{}", encoding="utf-8")
    v2.write_text("{}", encoding="utf-8")

    chosen = _resolve_existing_report_path((tmp_path / "report_v3.json", v2, v1))

    assert chosen == v2
