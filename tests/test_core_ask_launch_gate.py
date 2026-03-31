from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.eval.core_ask_launch_gate import (
    HealthCheckSpec,
    ReportCheckSpec,
    render_core_ask_launch_gate_markdown,
    run_core_ask_launch_gate,
    write_core_ask_launch_gate_report,
)


def test_core_ask_launch_gate_passes_with_green_reports_and_health(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"num_items": 3, "num_failed": 0}), encoding="utf-8")

    report = run_core_ask_launch_gate(
        report_specs=(ReportCheckSpec(name="phaseX", path=str(report_path), min_items=3),),
        health_specs=(HealthCheckSpec(name="health", url="http://example/health", expected_field="ok", expected_value=True),),
        exclusions=("excluded",),
        fetch_json=lambda url: (200, {"ok": True}),
    )

    assert report.overall_passed is True
    assert report.report_checks[0].passed is True
    assert report.health_checks[0].passed is True
    markdown = render_core_ask_launch_gate_markdown(report)
    assert "overall_passed: yes" in markdown
    assert "- excluded" in markdown


def test_core_ask_launch_gate_fails_when_health_or_reports_fail(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"num_items": 1, "num_failed": 1}), encoding="utf-8")

    report = run_core_ask_launch_gate(
        report_specs=(ReportCheckSpec(name="phaseX", path=str(report_path), min_items=1),),
        health_specs=(HealthCheckSpec(name="health", url="http://example/health", expected_field="status", expected_value="ok"),),
        exclusions=(),
        fetch_json=lambda url: (200, {"status": "degraded"}),
    )

    assert report.overall_passed is False
    assert report.report_checks[0].passed is False
    assert report.health_checks[0].passed is False


def test_core_ask_launch_gate_writer_emits_files(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"num_items": 2, "num_failed": 0}), encoding="utf-8")
    report = run_core_ask_launch_gate(
        report_specs=(ReportCheckSpec(name="phaseX", path=str(report_path), min_items=1),),
        health_specs=(HealthCheckSpec(name="health", url="http://example/health", expected_field="ok", expected_value=True),),
        exclusions=(),
        fetch_json=lambda url: (200, {"ok": True}),
    )

    json_path, md_path = write_core_ask_launch_gate_report(report, out_dir=tmp_path / "out")

    assert json_path.exists()
    assert md_path.exists()


def test_core_ask_launch_gate_supports_num_cases_threshold(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"num_items": 7, "num_cases": 28, "num_failed": 0}), encoding="utf-8")

    report = run_core_ask_launch_gate(
        report_specs=(ReportCheckSpec(name="phaseX", path=str(report_path), min_items=7, min_cases=28),),
        health_specs=(HealthCheckSpec(name="health", url="http://example/health", expected_field="ok", expected_value=True),),
        exclusions=(),
        fetch_json=lambda url: (200, {"ok": True}),
    )

    assert report.overall_passed is True
    assert report.report_checks[0].passed is True
