from __future__ import annotations

from pathlib import Path

import pytest

import chatgptrest.eval.public_agent_live_cutover_validation as mod


def test_live_cutover_validation_report_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_service_snapshot(unit: str) -> dict[str, str]:
        return {
            "ActiveState": "active",
            "SubState": "running",
            "ExecMainStartTimestamp": f"Mon 2026-03-23 13:38:11 CST {unit}",
        }

    raw_response = {
        "ok": True,
        "session_id": "sess-raw",
        "status": "needs_followup",
        "task_intake": {"objective": "请总结面试纪要"},
        "control_plane": {"contract_source": "server_synthesized"},
        "clarify_diagnostics": {"missing_fields": ["decision_to_support", "audience"]},
        "next_action": {"type": "await_user_clarification", "clarify_diagnostics": {"missing_fields": ["audience"]}},
        "provenance": {"route": "clarify"},
    }
    mcp_response = {
        "ok": True,
        "session_id": "sess-mcp",
        "status": "needs_followup",
        "task_intake": {"objective": "请总结面试纪要"},
        "control_plane": {"contract_source": "server_synthesized"},
        "clarify_diagnostics": {"missing_fields": ["decision_to_support", "audience"]},
        "next_action": {"type": "await_user_clarification", "clarify_diagnostics": {"missing_fields": ["audience"]}},
        "provenance": {"route": "clarify"},
    }
    wrapper_response = {
        "ok": True,
        "session_id": "sess-wrap",
        "status": "needs_followup",
        "task_intake": {"objective": "请总结面试纪要"},
        "control_plane": {"contract_source": "server_synthesized"},
        "clarify_diagnostics": {"missing_fields": ["decision_to_support", "audience"]},
        "next_action": {"type": "await_user_clarification", "clarify_diagnostics": {"missing_fields": ["audience"]}},
        "provenance": {"route": "clarify"},
    }
    second_patch_response = {
        "ok": True,
        "session_id": "patch-session",
        "status": "running",
        "delivery": {"mode": "deferred"},
        "task_intake": {"audience": "招聘经理", "decision_to_support": "支持候选人是否进入下一轮的决定"},
        "control_plane": {"contract_source": "client"},
        "next_action": {"type": "check_status"},
        "provenance": {},
    }
    patched_session = {
        "session_id": "patch-session",
        "status": "running",
        "route": "planning",
        "task_intake": {
            "decision_to_support": "支持候选人是否进入下一轮的决定",
            "audience": "招聘经理",
        },
        "control_plane": {
            "contract_source": "client",
            "contract_completeness": 1.0,
        },
    }

    call_counter = {"turn": 0}

    def _fake_agent_turn_http(**kwargs):
        call_counter["turn"] += 1
        if call_counter["turn"] == 1:
            return raw_response
        if call_counter["turn"] == 2:
            return raw_response
        return second_patch_response

    monkeypatch.setattr(mod, "_service_snapshot", _fake_service_snapshot)
    monkeypatch.setattr(mod, "_agent_turn_http", _fake_agent_turn_http)
    monkeypatch.setattr(mod, "_mcp_turn", lambda **kwargs: mcp_response)
    monkeypatch.setattr(mod, "_wrapper_turn", lambda **kwargs: wrapper_response)
    monkeypatch.setattr(mod, "_agent_session_http", lambda **kwargs: patched_session)
    monkeypatch.setattr(mod, "_cancel_session_http", lambda **kwargs: None)

    report = mod.run_public_agent_live_cutover_validation()

    assert report.num_checks == 7
    assert report.num_failed == 0
    assert [item.name for item in report.checks] == [
        "api_service_running",
        "mcp_service_running",
        "raw_api_clarify_projection",
        "public_mcp_clarify_projection",
        "wrapper_clarify_projection",
        "same_session_contract_patch_deferred",
        "patched_session_projection",
    ]


def test_live_cutover_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.PublicAgentLiveCutoverReport(
        api_base_url="http://127.0.0.1:18711",
        mcp_base_url="http://127.0.0.1:18712",
        sample_message="请总结面试纪要",
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[
            mod.PublicAgentLiveCutoverCheck(
                name="api_service_running",
                passed=True,
                details={"active_state": "active"},
            )
        ],
    )

    json_path, md_path = mod.write_public_agent_live_cutover_report(report, out_dir=tmp_path, basename="report_v1")

    assert json_path.exists()
    assert md_path.exists()
    markdown = mod.render_public_agent_live_cutover_markdown(report)
    assert "Public Agent Live Cutover Validation Report" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown
