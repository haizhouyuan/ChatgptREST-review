from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from ops import run_convergence_validation as module


def test_build_wave_plan_includes_optional_waves() -> None:
    plan = module.build_wave_plan(
        pytest_bin="/tmp/pytest",
        python_bin="/tmp/python",
        include_wave4=True,
        include_wave5=True,
        include_live=True,
        include_fault=True,
        include_soak=True,
    )

    waves = [item["wave"] for item in plan]

    assert waves[:4] == ["wave0", "wave1", "wave2", "wave3"]
    assert "wave4" in waves
    assert "wave5" in waves
    assert "wave6" in waves
    assert "wave7" in waves
    assert "wave8" in waves
    assert "wave8_soak" in waves
    live_wave = next(item for item in plan if item["wave"] == "wave6")
    wave5 = next(item for item in plan if item["wave"] == "wave5")
    wave7 = next(item for item in plan if item["wave"] == "wave7")
    wave8 = next(item for item in plan if item["wave"] == "wave8")
    wave8_soak = next(item for item in plan if item["wave"] == "wave8_soak")
    assert live_wave["command"] == ["/tmp/python", str(module.REPO_ROOT / "ops" / "run_convergence_live_matrix.py")]
    assert wave5["command"][-5:] == [
        "tests/test_business_flow_advise.py",
        "tests/test_business_flow_deep_research.py",
        "tests/test_business_flow_openclaw.py",
        "tests/test_business_flow_multi_turn.py",
        "tests/test_business_flow_planning_lane.py",
    ]
    assert wave7["command"][-6:-3] == [
        "tests/test_restart_recovery.py",
        "tests/test_db_corruption_recovery.py",
        "tests/test_network_partition.py",
    ]
    assert wave8["command"][-2:] == [
        "tests/test_shadow_mode.py",
        "tests/test_canary_routing.py",
    ]
    assert wave8_soak["command"][:2] == [
        "/tmp/python",
        str(module.REPO_ROOT / "ops" / "run_convergence_soak.py"),
    ]


def test_default_pytest_bin_prefers_python_sibling(tmp_path: Path) -> None:
    fake_python = tmp_path / "venv" / "bin" / "python"
    fake_pytest = fake_python.with_name("pytest")
    fake_pytest.parent.mkdir(parents=True, exist_ok=True)
    fake_python.write_text("", encoding="utf-8")
    fake_pytest.write_text("", encoding="utf-8")

    resolved = module._default_pytest_bin(python_bin=str(fake_python))

    assert resolved == str(fake_pytest)


def test_run_validation_writes_bundle(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_run_command(cmd: list[str], *, cwd: Path = module.REPO_ROOT, env=None):
        commands.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(
        module,
        "_collect_startup_manifest",
        lambda: {
            "status": "ready",
            "routers": [{"name": "advisor_v3", "loaded": True, "core": True}],
            "router_load_errors": [],
            "route_inventory": [{"path": "/healthz", "name": "healthz", "methods": ["GET"]}],
            "route_count": 1,
        },
    )

    result = module.run_validation(
        output_dir=tmp_path / "bundle",
        pytest_bin="/tmp/pytest",
        python_bin="/tmp/python",
        include_wave4=True,
        include_wave5=True,
        include_live=True,
        include_fault=True,
        include_soak=True,
    )

    assert result["ok"] is True
    assert commands[0][:3] == ["/tmp/python", "-m", "py_compile"]
    assert "ops/run_convergence_live_matrix.py" in commands[0]
    assert "ops/run_convergence_soak.py" in commands[0]
    assert any("tests/test_api_startup_smoke.py" in command for command in commands[1:])
    assert any("tests/test_business_flow_advise.py" in command for command in commands[1:])
    assert any(
        any("ops/run_convergence_live_matrix.py" in part for part in command)
        for command in commands[1:]
    )
    assert any("tests/test_restart_recovery.py" in command for command in commands[1:])
    assert any("tests/test_shadow_mode.py" in command for command in commands[1:])
    assert any(
        any("ops/run_convergence_soak.py" in part for part in command)
        for command in commands[1:]
    )
    assert (tmp_path / "bundle" / "startup_manifest.json").exists()
    assert (tmp_path / "bundle" / "summary.json").exists()
    assert (tmp_path / "bundle" / "README.md").exists()

    summary = json.loads((tmp_path / "bundle" / "summary.json").read_text(encoding="utf-8"))
    assert summary["compile"]["ok"] is True
    assert any(wave["wave"] == "wave4" for wave in summary["waves"])
    assert any(wave["wave"] == "wave5" for wave in summary["waves"])
    assert any(wave["wave"] == "wave6" for wave in summary["waves"])
    assert any(wave["wave"] == "wave7" for wave in summary["waves"])
    assert any(wave["wave"] == "wave8" for wave in summary["waves"])
    assert any(wave["wave"] == "wave8_soak" for wave in summary["waves"])


def test_main_returns_nonzero_when_required_wave_fails(monkeypatch, tmp_path: Path) -> None:
    args = argparse.Namespace(
        output_dir=str(tmp_path / "bundle"),
        pytest_bin="/tmp/pytest",
        python_bin="/tmp/python",
        include_wave4=False,
        include_wave5=False,
        include_live=False,
        include_fault=False,
        include_soak=False,
    )
    monkeypatch.setattr(module, "parse_args", lambda: args)
    monkeypatch.setattr(
        module,
        "run_validation",
        lambda **kwargs: {"ok": False, "output_dir": kwargs["output_dir"]},
    )

    assert module.main() == 1
