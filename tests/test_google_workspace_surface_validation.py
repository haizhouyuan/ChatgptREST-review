from __future__ import annotations

from pathlib import Path

import pytest

import chatgptrest.eval.google_workspace_surface_validation as mod


def test_google_workspace_surface_validation_report_passes_with_green_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mod,
        "_workspace_auth_state_check",
        lambda: mod.GoogleWorkspaceSurfaceCheckResult(
            name="workspace_auth_state",
            passed=True,
            details={
                "ok": True,
                "enabled_services": ["drive", "docs", "gmail", "sheets"],
                "credentials_path": "/tmp/google_credentials.json",
                "token_path": "/tmp/google_token.json",
                "credentials_exists": True,
                "token_exists": True,
            },
        ),
    )
    monkeypatch.setattr(
        mod,
        "_rclone_remote_check",
        lambda: mod.GoogleWorkspaceSurfaceCheckResult(
            name="rclone_remote_present",
            passed=True,
            details={"remotes": ["gdrive:"]},
        ),
    )

    report = mod.run_google_workspace_surface_validation()

    assert report.num_checks == 11
    assert report.num_failed == 0
    assert [item.name for item in report.results] == [
        "capability_audit",
        "rclone_remote_present",
        "workspace_auth_state",
        "public_agent_workspace_clarify",
        "public_agent_workspace_same_session_patch",
        "workspace_service_docs_gmail_chain",
        "workspace_service_drive_chain",
        "workspace_service_sheets_chain",
        "report_graph_workspace_outbox_contract",
        "cli_workspace_request_northbound",
        "skill_wrapper_workspace_request_northbound",
    ]


def test_workspace_auth_state_check_reports_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod.WorkspaceService,
        "auth_state",
        lambda self: {
            "ok": False,
            "enabled_services": ["drive", "docs", "gmail", "sheets"],
            "credentials_path": "/tmp/google_credentials.json",
            "token_path": "/tmp/google_token.json",
        },
    )
    monkeypatch.setattr(Path, "exists", lambda self: True)

    result = mod._workspace_auth_state_check()

    assert result.passed is False
    assert result.mismatches["ok"]["expected"] is True
    assert result.details["credentials_exists"] is True
    assert result.details["token_exists"] is True


def test_google_workspace_surface_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.GoogleWorkspaceSurfaceValidationReport(
        num_checks=1,
        num_passed=1,
        num_failed=0,
        results=[
            mod.GoogleWorkspaceSurfaceCheckResult(
                name="capability_audit",
                passed=True,
                details={"setup_script_declares_required_apis": True},
            )
        ],
    )

    json_path, md_path = mod.write_google_workspace_surface_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = mod.render_google_workspace_surface_report_markdown(report)
    assert "Google Workspace Surface Validation Report" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown


def test_cli_workspace_request_check_uses_public_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    import chatgptrest.cli as cli_mod

    captured: list[dict[str, object]] = []

    def fake_public_mcp_tool(
        *,
        mcp_url: str,
        tool_name: str,
        arguments: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured.append(
            {
                "mcp_url": mcp_url,
                "tool_name": tool_name,
                "arguments": dict(arguments),
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"ok": True, "status": "completed", "session_id": "sess-cli-ws"}

    result = mod._cli_workspace_request_check(public_mcp_tool_impl=fake_public_mcp_tool)

    assert result.passed is True
    assert captured
    assert captured[0]["tool_name"] == "advisor_agent_turn"
    assert captured[0]["arguments"]["workspace_request"]["action"] == "deliver_report_to_docs"
