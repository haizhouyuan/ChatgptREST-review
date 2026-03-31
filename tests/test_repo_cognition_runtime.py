from __future__ import annotations

import json
import subprocess

from chatgptrest.repo_cognition import runtime


def test_generate_runtime_snapshot_quick_has_stable_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime,
        "summarize_runtime_quick",
        lambda: {
            "mode": "quick",
            "source": "quick_summary",
            "services": [{"name": "public_mcp", "ok": True}],
            "databases": [{"name": "jobdb", "ok": True}],
            "public_mcp_ingress": {"ok": True, "agent_entry_url": "http://127.0.0.1:18712/mcp"},
            "maintenance_timers": None,
        },
    )

    snapshot = runtime.generate_runtime_snapshot("quick")

    assert snapshot["mode"] == "quick"
    assert snapshot["source"] == "quick_summary"
    assert isinstance(snapshot["services"], list)
    assert isinstance(snapshot["databases"], list)
    assert "timestamp" in snapshot
    assert snapshot["maintenance_timers"] is None


def test_generate_runtime_snapshot_deep_preserves_base_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime,
        "summarize_runtime_quick",
        lambda: {
            "mode": "quick",
            "source": "quick_summary",
            "services": [{"name": "public_mcp", "ok": True}],
            "databases": [{"name": "jobdb", "ok": True}],
            "public_mcp_ingress": {"ok": True, "agent_entry_url": "http://127.0.0.1:18712/mcp"},
            "maintenance_timers": None,
        },
    )

    deep_payload = {
        "ts": "2026-03-31T12:00:00Z",
        "all_ok": True,
        "checks": [
            {"check": "public_mcp_ingress_contract", "ok": True, "num_failed": 0, "failed_paths": []},
            {
                "check": "maintenance_timers",
                "ok": True,
                "details": [{"unit": "chatgptrest-health-probe.timer", "active": True}],
            },
        ],
    }

    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=["python"], returncode=0, stdout=json.dumps(deep_payload), stderr=""),
    )

    snapshot = runtime.generate_runtime_snapshot("deep")

    assert snapshot["mode"] == "deep"
    assert snapshot["source"] == "health_probe"
    assert snapshot["all_ok"] is True
    assert snapshot["services"][0]["name"] == "public_mcp"
    assert snapshot["databases"][0]["name"] == "jobdb"
    assert snapshot["maintenance_timers"] == [{"unit": "chatgptrest-health-probe.timer", "active": True}]
    assert snapshot["checks"][0]["check"] == "public_mcp_ingress_contract"
