from __future__ import annotations

from pathlib import Path

import chatgptrest.eval.public_surface_launch_gate as mod


def test_phase15_public_surface_launch_gate_passes() -> None:
    report = mod.run_public_surface_launch_gate()

    assert report.num_checks == 5
    assert report.num_failed == 0
    assert report.overall_passed is True


def test_public_surface_launch_gate_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.PublicSurfaceLaunchGateReport(
        overall_passed=True,
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[mod.PublicSurfaceGateCheck(name="phase12_core_ask_launch_gate", passed=True, details={"overall_passed": True})],
    )

    json_path, md_path = mod.write_public_surface_launch_gate_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = mod.render_public_surface_launch_gate_markdown(report)
    assert "Public Surface Launch Gate Report" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown
