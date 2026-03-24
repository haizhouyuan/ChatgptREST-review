from __future__ import annotations

from pathlib import Path

from chatgptrest.eval.scoped_public_release_gate import (
    ScopedPublicReleaseGateReport,
    ScopedReleaseGateCheck,
    render_scoped_public_release_gate_markdown,
    run_scoped_public_release_gate,
    write_scoped_public_release_gate_report,
)


def test_phase17_scoped_public_release_gate_passes() -> None:
    report = run_scoped_public_release_gate()

    assert report.num_checks == 2
    assert report.num_failed == 0
    assert report.overall_passed is True


def test_scoped_public_release_gate_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = ScopedPublicReleaseGateReport(
        overall_passed=True,
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[ScopedReleaseGateCheck(name="phase15_public_surface_launch_gate", passed=True, details={"overall_passed": True})],
        scope_boundary=["not a full-stack execution delivery proof"],
    )

    json_path, md_path = write_scoped_public_release_gate_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = render_scoped_public_release_gate_markdown(report)
    assert "Scoped Public Release Gate Report" in markdown
    assert "## Scope Boundary" in markdown
