from __future__ import annotations

from pathlib import Path

import pytest

import chatgptrest.eval.public_agent_effects_delivery_validation as mod


def test_effects_delivery_validation_report_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_service_snapshot(unit: str) -> dict[str, str]:
        return {
            "ActiveState": "active",
            "SubState": "running",
            "ExecMainStartTimestamp": f"Mon 2026-03-23 13:38:11 CST {unit}",
        }

    clarify_response = {
        "ok": True,
        "session_id": "sess-clarify",
        "status": "needs_followup",
        "lifecycle": {"phase": "clarify_required", "blocking": True},
        "delivery": {"mode": "sync", "answer_ready": True},
        "task_intake": {"objective": "请总结面试纪要"},
        "control_plane": {"contract_source": "server_synthesized"},
        "clarify_diagnostics": {"missing_fields": ["decision_to_support", "audience"]},
    }
    deferred_accept = {
        "ok": True,
        "session_id": "patch-session",
        "status": "running",
        "accepted": True,
        "lifecycle": {"phase": "accepted", "next_action_type": "check_status"},
        "delivery": {"mode": "deferred", "accepted": True},
    }
    patched_session = {
        "ok": True,
        "session_id": "patch-session",
        "status": "running",
        "route": "planning",
        "lifecycle": {"phase": "progress"},
        "delivery": {"mode": "deferred"},
        "control_plane": {"contract_source": "client"},
        "task_intake": {"decision_to_support": "支持候选人是否进入下一轮的决定"},
    }
    cancelled = {
        "ok": True,
        "session_id": "patch-session",
        "status": "cancelled",
        "message": "Session cancelled successfully",
        "lifecycle": {"phase": "cancelled", "session_terminal": True},
        "delivery": {"terminal": True},
    }
    workspace = {
        "ok": True,
        "session_id": "ws-1",
        "status": "needs_followup",
        "lifecycle": {"phase": "clarify_required"},
        "effects": {"workspace_action": {"action": "deliver_report_to_docs", "status": "clarify_required"}},
        "workspace_diagnostics": {"missing_fields": ["body_markdown"]},
    }
    wrapper_stdout = {
        "ok": True,
        "session_id": "wrap-1",
        "status": "needs_followup",
        "lifecycle": {"phase": "clarify_required"},
    }
    wrapper_summary = {
        "mode": "agent_public_mcp",
        "session_id": "wrap-1",
        "route": "clarify",
        "lifecycle": {"phase": "clarify_required"},
        "result": {"clarify_diagnostics": {"missing_fields": ["audience"]}},
    }

    calls = {"turn": 0}

    def _fake_agent_turn_http(**kwargs):
        calls["turn"] += 1
        if calls["turn"] in {1, 2}:
            return clarify_response
        return deferred_accept

    monkeypatch.setattr(mod, "_shared_service_snapshot", _fake_service_snapshot)
    monkeypatch.setattr(mod, "_shared_agent_turn_http", _fake_agent_turn_http)
    monkeypatch.setattr(mod, "_shared_mcp_turn", lambda **kwargs: clarify_response)
    monkeypatch.setattr(mod, "_wrapper_turn_with_summary", lambda **kwargs: (wrapper_stdout, wrapper_summary))
    monkeypatch.setattr(mod, "_shared_agent_session_http", lambda **kwargs: patched_session)
    monkeypatch.setattr(mod, "_cancel_session_http", lambda **kwargs: cancelled)
    monkeypatch.setattr(mod, "_workspace_clarify_http", lambda **kwargs: workspace)

    report = mod.run_public_agent_effects_delivery_validation()

    assert report.num_checks == 9
    assert report.num_failed == 0
    assert [item.name for item in report.checks] == [
        "api_service_running",
        "mcp_service_running",
        "raw_api_clarify_lifecycle_delivery",
        "public_mcp_clarify_lifecycle_delivery",
        "wrapper_summary_projection",
        "same_session_deferred_accept_surface",
        "patched_session_progress_surface",
        "cancelled_session_surface",
        "workspace_effect_surface",
    ]


def test_effects_delivery_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.PublicAgentEffectsDeliveryReport(
        api_base_url="http://127.0.0.1:18711",
        mcp_base_url="http://127.0.0.1:18712",
        sample_message="请总结面试纪要",
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[
            mod.PublicAgentEffectsDeliveryCheck(
                name="api_service_running",
                passed=True,
                details={"active_state": "active"},
            )
        ],
    )

    json_path, md_path = mod.write_public_agent_effects_delivery_report(report, out_dir=tmp_path, basename="report_v1")

    assert json_path.exists()
    assert md_path.exists()
    markdown = mod.render_public_agent_effects_delivery_markdown(report)
    assert "Public Agent Effects And Delivery Validation Report" in markdown
    assert "| Check | Pass | Key Details | Mismatch |" in markdown
