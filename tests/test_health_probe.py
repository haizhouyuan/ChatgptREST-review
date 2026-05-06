from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
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
    monkeypatch.setattr(mod, "_check_earlyoom_recent_kills", lambda: {"check": "earlyoom_recent_kills", "ok": True})
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


def test_main_marks_snapshot_failed_when_dashboard_surface_is_unhealthy(monkeypatch, tmp_path: Path, capsys) -> None:
    mod = _load_module()
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    def _fake_check_http(label, url, timeout=5):  # noqa: ARG001
        if label == "dashboard_8787":
            return {"check": label, "ok": False, "status": 404}
        return {"check": label, "ok": True}

    monkeypatch.setattr(mod, "_check_http", _fake_check_http)
    monkeypatch.setattr(mod, "_check_db", lambda label, db_path: {"check": label, "ok": True})  # noqa: ARG005
    monkeypatch.setattr(mod, "_check_stuck_jobs", lambda db_path, threshold_seconds=3600: {"check": "stuck_jobs", "ok": True})  # noqa: ARG005
    monkeypatch.setattr(mod, "_check_kb", lambda kb_path: {"check": "kb_fts", "ok": True})  # noqa: ARG005
    monkeypatch.setattr(mod, "_check_memory", lambda mem_path: {"check": "memory", "ok": True})  # noqa: ARG005
    monkeypatch.setattr(mod, "_check_earlyoom_recent_kills", lambda: {"check": "earlyoom_recent_kills", "ok": True})
    monkeypatch.setattr(
        mod,
        "_check_public_mcp_ingress_contract",
        lambda: {
            "check": "public_mcp_ingress_contract",
            "ok": True,
            "num_failed": 0,
            "failed_paths": [],
            "failed_reasons": [],
            "fix_hint": None,
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
    assert checks["dashboard_8787"]["ok"] is False


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


def test_resolve_openmind_db_path_honors_kb_search_env(monkeypatch, tmp_path: Path) -> None:
    mod = _load_module()
    configured = tmp_path / "configured" / "kb_search.db"
    configured.parent.mkdir()
    configured.write_bytes(b"not-empty")
    fallback_home = tmp_path / "fallback-home"
    (fallback_home / ".openmind").mkdir(parents=True)
    (fallback_home / ".openmind" / "kb_search.db").write_bytes(b"not-empty")

    monkeypatch.setenv("OPENMIND_KB_SEARCH_DB", str(configured))
    monkeypatch.setenv("HOME", str(tmp_path / "isolated-home"))
    monkeypatch.setattr(mod, "_passwd_home", lambda: str(fallback_home))

    assert mod._resolve_openmind_db_path(("OPENMIND_KB_SEARCH_DB", "OPENMIND_KB_PATH"), "kb_search.db") == str(configured)


def test_resolve_openmind_db_path_falls_back_to_passwd_home(monkeypatch, tmp_path: Path) -> None:
    mod = _load_module()
    isolated_home = tmp_path / "codex-home"
    real_home = tmp_path / "login-home"
    live_db = real_home / ".openmind" / "memory.db"
    live_db.parent.mkdir(parents=True)
    live_db.write_bytes(b"not-empty")

    monkeypatch.delenv("OPENMIND_MEMORY_DB", raising=False)
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setattr(mod, "_passwd_home", lambda: str(real_home))

    assert mod._resolve_openmind_db_path(("OPENMIND_MEMORY_DB",), "memory.db") == str(live_db)


def test_check_earlyoom_recent_kills_flags_recent_log_block(tmp_path: Path) -> None:
    mod = _load_module()
    log_path = tmp_path / "earlyoom.log"
    log_path.write_text(
        "\n".join([
            "==== 2026-04-28T22:21:34+08:00 pid=1445795 uid=1000 name=python ====",
            "-- free -h --",
            "Mem: 30Gi 27Gi 1.4Gi 234Mi 3.0Gi 3.7Gi",
            "",
        ]),
        encoding="utf-8",
    )
    now = datetime.fromisoformat("2026-04-28T22:22:00+08:00").timestamp()

    result = mod._check_earlyoom_recent_kills(str(log_path), now=now, window_seconds=900)

    assert result["ok"] is False
    assert result["recent_count"] == 1
    assert result["details"][0]["pid"] == "1445795"


def test_check_earlyoom_recent_kills_ignores_old_log_block(tmp_path: Path) -> None:
    mod = _load_module()
    log_path = tmp_path / "earlyoom.log"
    log_path.write_text(
        "==== 2026-04-28T22:00:00+08:00 pid=123 uid=1000 name=python ====\n",
        encoding="utf-8",
    )
    now = datetime.fromisoformat("2026-04-28T22:30:00+08:00").timestamp()

    result = mod._check_earlyoom_recent_kills(str(log_path), now=now, window_seconds=900)

    assert result["ok"] is True
    assert result["recent_count"] == 0


def test_read_tail_falls_back_to_sudo_on_permission_error(monkeypatch) -> None:
    mod = _load_module()

    class _BlockedPath:
        def stat(self):
            raise PermissionError("blocked")

        def __str__(self) -> str:
            return "/var/log/earlyoom/earlyoom_kills_2026-04-29.log"

    class _Completed:
        returncode = 0
        stdout = "sudo-tail"
        stderr = ""

    def _fake_run(cmd, **kwargs):  # noqa: ARG001
        assert cmd[:4] == ["sudo", "-n", "tail", "-c"]
        return _Completed()

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    assert mod._read_tail(_BlockedPath()) == "sudo-tail"
