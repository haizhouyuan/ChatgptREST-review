from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _load_script():
    path = Path("scripts/chatgptrest_closeout.py").resolve()
    spec = importlib.util.spec_from_file_location("chatgptrest_closeout_test", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_closeout_blocks_when_doc_checker_fails(monkeypatch, capsys) -> None:
    mod = _load_script()
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        calls.append(list(cmd))
        if cmd[:3] == ["git", "rev-parse", "--verify"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="parent\n", stderr="")
        if cmd[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[0] == sys.executable and str(mod.CHECKER) in cmd:
            return subprocess.CompletedProcess(
                cmd,
                1,
                stdout=json.dumps(
                    {
                        "ok": False,
                        "validation": {"missing_updates": ["AGENTS.md"]},
                    }
                ),
                stderr="",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    rc = mod.main(["--agent", "codex", "--status", "completed", "--summary", "bootstrap fix", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["phase"] == "doc_obligations"
    assert payload["checker"]["validation"]["missing_updates"] == ["AGENTS.md"]
    assert not any(str(mod.UPSTREAM_CLOSEOUT) == cmd[0] for cmd in calls if cmd)


def test_closeout_forwards_after_checker_passes(monkeypatch, capsys) -> None:
    mod = _load_script()

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        if cmd[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=" M AGENTS.md\n", stderr="")
        if cmd[0] == sys.executable and str(mod.CHECKER) in cmd:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"ok": True, "validation": {"missing_updates": []}}),
                stderr="",
            )
        if cmd[0] == str(mod.UPSTREAM_CLOSEOUT):
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    rc = mod.main(
        [
            "--agent",
            "codex",
            "--status",
            "partial",
            "--summary",
            "paused",
            "--pending-reason",
            "review",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["diff_spec"] == "HEAD"
