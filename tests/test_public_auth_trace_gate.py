from __future__ import annotations

from pathlib import Path

import chatgptrest.eval.public_auth_trace_gate as mod


def test_phase16_public_auth_trace_gate_passes() -> None:
    report = mod.run_public_auth_trace_gate()

    assert report.num_checks == 4
    assert report.num_failed == 0


def test_public_auth_trace_gate_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.PublicAuthTraceGateReport(
        base_url="http://127.0.0.1:18711",
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[mod.PublicAuthTraceCheck(name="no_auth_rejected", passed=True, details={"http_status": 401})],
    )

    json_path, md_path = mod.write_public_auth_trace_gate_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = mod.render_public_auth_trace_gate_markdown(report)
    assert "Public Auth Trace Gate Report" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown
