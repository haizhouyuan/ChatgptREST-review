from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ops import run_convergence_soak as module


def test_run_soak_validation_writes_bounded_bundle(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_run_command(cmd: list[str], *, cwd: Path = module.REPO_ROOT):
        commands.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    result = module.run_soak_validation(
        output_dir=tmp_path / "bundle",
        python_bin="/tmp/python",
        duration_seconds=42,
    )

    assert result["ok"] is True
    assert commands[0] == [
        "/tmp/python",
        str(module.REPO_ROOT / "ops" / "monitor_chatgptrest.py"),
        "--duration-seconds",
        "42",
        "--out",
        str(tmp_path / "bundle" / "monitor.jsonl"),
    ]
    assert commands[1] == [
        "/tmp/python",
        str(module.REPO_ROOT / "ops" / "summarize_monitor_log.py"),
        "--in",
        str(tmp_path / "bundle" / "monitor.jsonl"),
        "--out",
        str(tmp_path / "bundle" / "summary.md"),
    ]
    summary = json.loads((tmp_path / "bundle" / "summary.json").read_text(encoding="utf-8"))
    assert summary["ok"] is True
    assert summary["duration_seconds"] == 42
    assert (tmp_path / "bundle" / "monitor.stdout.txt").exists()
    assert (tmp_path / "bundle" / "summarize.stdout.txt").exists()
