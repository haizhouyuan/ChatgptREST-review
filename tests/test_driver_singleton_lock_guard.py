from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from chatgptrest.executors import repair as repair_mod
from chatgptrest.ops_shared import infra as infra_mod


def _load_maint_daemon_module():
    path = (Path(__file__).resolve().parents[1] / "ops" / "maint_daemon.py").resolve()
    spec = importlib.util.spec_from_file_location("chatgptrest_test_maint_daemon", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


md = _load_maint_daemon_module()


def test_maint_start_driver_if_down_skips_script_fallback_when_systemd_loaded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def _fake_run_cmd(cmd: list[str], *, cwd=None, timeout_seconds=60):  # noqa: ANN001
        calls.append(list(cmd))
        if cmd[:5] == [
            "systemctl",
            "--user",
            "show",
            "chatgptrest-driver.service",
            "--property=LoadState",
        ]:
            return True, "loaded"
        if cmd[:4] == ["systemctl", "--user", "reset-failed", "chatgptrest-driver.service"]:
            return True, ""
        if cmd[:4] == ["systemctl", "--user", "restart", "chatgptrest-driver.service"]:
            return False, "restart failed"
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(md, "systemd_unit_load_state", lambda *args, **kwargs: "loaded")
    monkeypatch.setattr(md, "run_cmd", _fake_run_cmd)
    monkeypatch.setattr(md, "port_open", lambda *args, **kwargs: False)

    ok, details = md._start_driver_if_down(
        driver_root=tmp_path,
        driver_url="http://127.0.0.1:18701/mcp",
        cdp_url="http://127.0.0.1:9222",
        log_file=tmp_path / "driver.log",
    )

    assert ok is False
    assert details.get("systemd_load_state") == "loaded"
    assert details.get("script_fallback_skipped") is True
    assert "singleton-lock" in str(details.get("error") or "")
    assert ["systemctl", "--user", "stop", "chatgptrest-driver.service"] not in calls


def test_repair_systemd_unit_load_state_parsing(monkeypatch) -> None:
    monkeypatch.setattr(infra_mod, "run_cmd", lambda *args, **kwargs: (True, "loaded\n"))
    assert repair_mod._systemd_unit_load_state("chatgptrest-driver.service") == "loaded"

    monkeypatch.setattr(infra_mod, "run_cmd", lambda *args, **kwargs: (False, "failed"))
    assert repair_mod._systemd_unit_load_state("chatgptrest-driver.service") is None
