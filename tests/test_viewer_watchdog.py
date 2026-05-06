from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _load_module():
    path = Path(__file__).resolve().parents[1] / "ops" / "viewer_watchdog.py"
    spec = importlib.util.spec_from_file_location("viewer_watchdog", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def watchdog():
    return _load_module()


def _mk_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "ops").mkdir(parents=True)
    (repo / "ops" / "viewer_restart.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (repo / ".run" / "viewer").mkdir(parents=True)
    return repo


def test_pick_restart_mode_prefers_full_when_novnc_path_down(watchdog) -> None:
    mode = watchdog._pick_restart_mode(
        {
            "ok": False,
            "novnc_listening": False,
            "vnc_listening": True,
            "novnc_http_ok": True,
            "viewer_chrome_running": True,
        }
    )
    assert mode == "--full"


def test_pick_restart_mode_prefers_full_on_gpu_exit15_burst(watchdog) -> None:
    mode = watchdog._pick_restart_mode(
        {
            "ok": False,
            "novnc_listening": True,
            "vnc_listening": True,
            "novnc_http_ok": True,
            "viewer_chrome_running": True,
            "gpu_exit15_unhealthy": True,
        }
    )
    assert mode == "--full"


def test_main_check_mode_unhealthy_returns_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    watchdog,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _mk_repo(tmp_path)

    monkeypatch.setattr(
        watchdog,
        "_collect_viewer_status",
        lambda **kwargs: {
            "novnc_listening": True,
            "vnc_listening": True,
            "novnc_http_ok": True,
            "viewer_chrome_running": False,
        },
    )

    rc = watchdog.main(["--check", "--repo-root", str(repo)])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["message"] == "viewer unhealthy (check-only)"
    assert out["actions"] == []
    assert out["before_health"]["viewer_chrome_running"] is False


def test_main_heal_chrome_only_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    watchdog,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _mk_repo(tmp_path)
    calls: list[list[str]] = []
    status_idx = {"n": 0}

    def _fake_collect_viewer_status(**kwargs):  # noqa: ANN001
        status_idx["n"] += 1
        if status_idx["n"] == 1:
            return {
                "novnc_listening": True,
                "vnc_listening": True,
                "novnc_http_ok": True,
                "viewer_chrome_running": False,
            }
        return {
            "novnc_listening": True,
            "vnc_listening": True,
            "novnc_http_ok": True,
            "viewer_chrome_running": True,
        }

    def _fake_run(cmd: list[str], timeout_seconds: float = 30.0):  # noqa: ARG001
        calls.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(watchdog, "_collect_viewer_status", _fake_collect_viewer_status)
    monkeypatch.setattr(watchdog, "_run", _fake_run)

    rc = watchdog.main(["--repo-root", str(repo), "--sleep-after-restart-seconds", "0"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["message"] == "viewer healed"
    assert calls
    assert calls[0][:2] == ["bash", str(repo / "ops" / "viewer_restart.sh")]
    assert calls[0][2] == "--chrome-only"


def test_main_heal_full_when_novnc_down(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    watchdog,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _mk_repo(tmp_path)
    calls: list[list[str]] = []
    status_idx = {"n": 0}

    def _fake_collect_viewer_status(**kwargs):  # noqa: ANN001
        status_idx["n"] += 1
        if status_idx["n"] == 1:
            return {
                "novnc_listening": False,
                "vnc_listening": True,
                "novnc_http_ok": False,
                "viewer_chrome_running": True,
            }
        return {
            "novnc_listening": True,
            "vnc_listening": True,
            "novnc_http_ok": True,
            "viewer_chrome_running": True,
        }

    def _fake_run(cmd: list[str], timeout_seconds: float = 30.0):  # noqa: ARG001
        calls.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(watchdog, "_collect_viewer_status", _fake_collect_viewer_status)
    monkeypatch.setattr(watchdog, "_run", _fake_run)

    rc = watchdog.main(["--repo-root", str(repo), "--sleep-after-restart-seconds", "0"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["message"] == "viewer healed"
    assert calls
    assert calls[0][2] == "--full"


def test_main_heal_full_on_gpu_exit15_burst(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    watchdog,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _mk_repo(tmp_path)
    # Healthy ports/process, but log indicates repeated GPU exit_code=15.
    (repo / ".run" / "viewer" / "chrome.log").write_text(
        "\n".join(
            [
                "x",
                "GPU process exited unexpectedly: exit_code=15",
                "y",
                "GPU process exited unexpectedly: exit_code=15",
                "z",
                "GPU process exited unexpectedly: exit_code=15",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    monkeypatch.setattr(
        watchdog,
        "_collect_viewer_status",
        lambda **kwargs: {  # noqa: ARG005
            "novnc_listening": True,
            "vnc_listening": True,
            "novnc_http_ok": True,
            "viewer_chrome_running": True,
        },
    )
    monkeypatch.setattr(
        watchdog,
        "_run",
        lambda cmd, timeout_seconds=30.0: (  # noqa: ARG005
            calls.append(list(cmd)) or subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok\n", stderr="")
        ),
    )

    rc = watchdog.main(
        [
            "--repo-root",
            str(repo),
            "--sleep-after-restart-seconds",
            "0",
            "--gpu-exit15-threshold",
            "3",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["before_health"]["gpu_exit15_unhealthy"] is True
    assert out["chrome_diag"]["gpu_exit15_count_recent"] == 3
    assert calls
    assert calls[0][2] == "--full"


def test_collect_viewer_status_uses_local_probe_for_wildcard_bind(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    watchdog,
) -> None:
    repo = _mk_repo(tmp_path)
    run_dir = repo / ".run" / "viewer"
    (run_dir / "novnc_bind_host.txt").write_text("0.0.0.0\n", encoding="utf-8")
    calls: list[tuple[str, int]] = []

    def _fake_port_open(host: str, port: int, *, timeout_seconds: float = 1.5):  # noqa: ARG001
        calls.append((host, int(port)))
        return True

    monkeypatch.setattr(watchdog, "_pid_alive", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(watchdog, "_port_open", _fake_port_open)
    monkeypatch.setattr(watchdog, "_http_ok", lambda url, timeout_seconds=2.0: "127.0.0.1" in url)  # noqa: ARG005

    status = watchdog._collect_viewer_status(repo_root=repo)
    assert status["viewer_novnc_bind_host"] == "0.0.0.0"
    assert status["viewer_novnc_probe_host"] == "127.0.0.1"
    assert ("127.0.0.1", 6082) in calls
    assert status["novnc_http_ok"] is True
