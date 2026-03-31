from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    path = Path("ops/health_probe.py").resolve()
    spec = importlib.util.spec_from_file_location("chatgptrest_health_probe_test", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_check_public_mcp_ingress_contract_passes_when_alignment_snapshot_is_green(monkeypatch) -> None:
    mod = _load_module()

    class _Checker:
        @staticmethod
        def collect_alignment_report(*, apply_fix: bool = False):
            assert apply_fix is False
            return {
                "ok": True,
                "num_failed": 0,
                "checks": [
                    {"path": "/tmp/codex.toml", "ok": True, "reason": "ok"},
                ],
                "skill_wrapper": {"path": "/tmp/wrapper.py", "ok": True, "reason": "ok"},
            }

    monkeypatch.setattr(mod, "_load_sibling_module", lambda name: _Checker())
    result = mod._check_public_mcp_ingress_contract()
    assert result["ok"] is True
    assert result["num_failed"] == 0
    assert result["failed_paths"] == []
    assert result["failed_reasons"] == []


def test_check_public_mcp_ingress_contract_surfaces_failed_paths_and_reasons(monkeypatch) -> None:
    mod = _load_module()

    class _Checker:
        @staticmethod
        def collect_alignment_report(*, apply_fix: bool = False):
            assert apply_fix is False
            return {
                "ok": False,
                "num_failed": 2,
                "checks": [
                    {"path": "/tmp/antigravity.json", "ok": False, "reason": "legacy_serverURL_field"},
                ],
                "skill_wrapper": {"path": "/tmp/wrapper.py", "ok": False, "reason": "agent_mode_not_using_public_mcp"},
            }

    monkeypatch.setattr(mod, "_load_sibling_module", lambda name: _Checker())
    result = mod._check_public_mcp_ingress_contract()
    assert result["ok"] is False
    assert result["num_failed"] == 2
    assert result["failed_paths"] == ["/tmp/antigravity.json", "/tmp/wrapper.py"]
    assert result["failed_reasons"] == ["legacy_serverURL_field", "agent_mode_not_using_public_mcp"]


def test_check_maintenance_timers_passes_when_all_units_are_active(monkeypatch) -> None:
    mod = _load_module()

    def _fake_show(unit: str, *properties: str):  # noqa: ARG001
        return {"ActiveState": "active", "SubState": "waiting", "UnitFileState": "enabled"}

    monkeypatch.setattr(mod, "_systemctl_user_show", _fake_show)
    result = mod._check_maintenance_timers()
    assert result["ok"] is True
    assert result["failed_units"] == []
    assert len(result["details"]) == 3


def test_check_maintenance_timers_surfaces_inactive_units(monkeypatch) -> None:
    mod = _load_module()

    def _fake_show(unit: str, *properties: str):  # noqa: ARG001
        if unit == "chatgptrest-backlog-janitor.timer":
            return {"ActiveState": "inactive", "SubState": "dead", "UnitFileState": "enabled"}
        return {"ActiveState": "active", "SubState": "waiting", "UnitFileState": "enabled"}

    monkeypatch.setattr(mod, "_systemctl_user_show", _fake_show)
    result = mod._check_maintenance_timers()
    assert result["ok"] is False
    assert result["failed_units"] == ["chatgptrest-backlog-janitor.timer"]


def test_main_marks_snapshot_failed_when_public_mcp_ingress_contract_fails(monkeypatch, tmp_path: Path, capsys) -> None:
    mod = _load_module()
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_check_http", lambda label, url, timeout=5: {"check": label, "ok": True})  # noqa: ARG005
    monkeypatch.setattr(mod, "_check_db", lambda label, db_path: {"check": label, "ok": True})  # noqa: ARG005
    monkeypatch.setattr(mod, "_check_stuck_jobs", lambda db_path, threshold_seconds=3600: {"check": "stuck_jobs", "ok": True})  # noqa: ARG005
    monkeypatch.setattr(mod, "_check_kb", lambda kb_path: {"check": "kb_fts", "ok": True})  # noqa: ARG005
    monkeypatch.setattr(mod, "_check_memory", lambda mem_path: {"check": "memory", "ok": True})  # noqa: ARG005
    monkeypatch.setattr(
        mod,
        "_check_public_mcp_ingress_contract",
        lambda: {
            "check": "public_mcp_ingress_contract",
            "ok": False,
            "num_failed": 1,
            "failed_paths": ["/tmp/antigravity.json"],
            "failed_reasons": ["legacy_serverURL_field"],
            "fix_hint": "python3 ops/check_public_mcp_client_configs.py --fix",
        },
    )
    monkeypatch.setattr(
        mod,
        "_check_maintenance_timers",
        lambda: {
            "check": "maintenance_timers",
            "ok": True,
            "failed_units": [],
            "details": [],
        },
    )

    rc = mod.main(["--json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["all_ok"] is False
    checks = {item["check"]: item for item in payload["checks"]}
    assert checks["public_mcp_ingress_contract"]["ok"] is False
    latest = tmp_path / "artifacts" / "monitor" / "health_probe" / "latest.json"
    assert latest.exists()


def test_check_http_and_db_delegate_to_shared_helpers(monkeypatch) -> None:
    mod = _load_module()

    class _HealthChecks:
        @staticmethod
        def check_http(label: str, url: str, *, timeout: int = 5):
            return {"check": label, "url": url, "timeout": timeout, "ok": True}

        @staticmethod
        def check_db(label: str, db_path: str):
            return {"check": label, "path": db_path, "ok": True}

    monkeypatch.setattr(mod, "_load_sibling_module", lambda name: _HealthChecks())

    http_result = mod._check_http("api", "http://127.0.0.1:18711/healthz", timeout=3)
    db_result = mod._check_db("jobdb", "state/jobdb.sqlite3")

    assert http_result == {"check": "api", "url": "http://127.0.0.1:18711/healthz", "timeout": 3, "ok": True}
    assert db_result == {"check": "jobdb", "path": "state/jobdb.sqlite3", "ok": True}
