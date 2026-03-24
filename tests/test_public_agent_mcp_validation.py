from __future__ import annotations

from pathlib import Path

import pytest

import chatgptrest.eval.public_agent_mcp_validation as mod


def test_public_agent_mcp_validation_report_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        {
            "result": {
                "serverInfo": {"name": "chatgptrest-agent-mcp", "version": "1.26.0"},
                "protocolVersion": "2025-03-26",
            }
        },
        {
            "result": {
                "tools": [
                    {"name": "advisor_agent_turn"},
                    {"name": "advisor_agent_cancel"},
                    {"name": "advisor_agent_status"},
                ]
            }
        },
        {
            "result": {
                "structuredContent": {
                    "ok": True,
                    "session_id": "agent_sess_test",
                    "status": "needs_followup",
                    "provenance": {"route": "clarify", "provider_path": ["ask_strategist"]},
                    "next_action": {"type": "await_user_clarification"},
                    "contract": {"output_shape": "meeting_summary", "task_template": "implementation_planning"},
                }
            }
        },
        {
            "result": {
                "structuredContent": {
                    "ok": True,
                    "session_id": "agent_sess_test",
                    "status": "needs_followup",
                    "route": "clarify",
                    "provenance": {"route": "clarify"},
                    "next_action": {"type": "await_user_clarification"},
                }
            }
        },
    ]

    def _fake_jsonrpc_call(url: str, *, request_id: int, method: str, params: dict, timeout_seconds: float = 30.0):
        assert url == "http://127.0.0.1:18712/mcp"
        assert timeout_seconds > 0
        expected = responses.pop(0)
        return expected

    monkeypatch.setattr(mod, "_jsonrpc_call", _fake_jsonrpc_call)

    report = mod.run_public_agent_mcp_validation()

    assert report.num_checks == 4
    assert report.num_failed == 0
    assert [item.name for item in report.results] == [
        "initialize",
        "tools_list",
        "planning_clarify_turn",
        "status_continuity",
    ]


def test_public_agent_mcp_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.PublicAgentMcpValidationReport(
        base_url="http://127.0.0.1:18712",
        sample_message="请总结面试纪要",
        num_checks=1,
        num_passed=1,
        num_failed=0,
        results=[
            mod.PublicAgentMcpCheckResult(
                name="initialize",
                passed=True,
                details={"server_name": "chatgptrest-agent-mcp"},
            )
        ],
    )

    json_path, md_path = mod.write_public_agent_mcp_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    markdown = mod.render_public_agent_mcp_report_markdown(report)
    assert "Public Agent MCP Validation Report" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown
