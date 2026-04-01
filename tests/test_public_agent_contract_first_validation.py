from __future__ import annotations

from pathlib import Path

import chatgptrest.eval.public_agent_contract_first_validation as mod


def test_public_agent_contract_first_validation_report_passes() -> None:
    report = mod.run_public_agent_contract_first_validation()

    assert report.num_checks == 6
    assert report.num_failed == 0
    assert [item.name for item in report.results] == [
        "canonical_task_intake_northbound",
        "clarify_machine_readable_diagnostics",
        "same_session_contract_patch_resume",
        "session_projection_retains_control_plane",
        "message_contract_parser_fallback",
        "northbound_observability_projection",
    ]


def test_public_agent_contract_first_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.PublicAgentContractFirstValidationReport(
        num_checks=1,
        num_passed=1,
        num_failed=0,
        results=[
            mod.PublicAgentContractFirstCheckResult(
                name="canonical_task_intake_northbound",
                passed=True,
                details={"status": "completed"},
            )
        ],
    )

    json_path, md_path = mod.write_public_agent_contract_first_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = mod.render_public_agent_contract_first_report_markdown(report)
    assert "Public Agent Contract-First Validation Report" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown
