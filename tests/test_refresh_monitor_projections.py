from __future__ import annotations

from pathlib import Path

from ops import refresh_monitor_projections


def test_refresh_monitor_projections_runs_issue_views_and_guardian(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    class _Proc:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def _fake_run(cmd, cwd, capture_output, text, check):
        calls.append(list(cmd))
        name = Path(str(cmd[1])).name
        if name == "export_issue_views.py":
            return _Proc(0, stdout="issue views ok\n")
        if name == "openclaw_guardian_run.py":
            return _Proc(0, stdout='{"ok": true}\n')
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(refresh_monitor_projections.subprocess, "run", _fake_run)

    rc = refresh_monitor_projections.main(
        [
            "--python-bin",
            "/tmp/python",
            "--db-path",
            str(tmp_path / "jobdb.sqlite3"),
            "--json-out",
            str(tmp_path / "latest.json"),
            "--md-out",
            str(tmp_path / "latest.md"),
            "--history-json-out",
            str(tmp_path / "history.json"),
            "--history-md-out",
            str(tmp_path / "history.md"),
            "--guardian-report-out",
            str(tmp_path / "guardian.json"),
        ]
    )

    assert rc == 0
    assert len(calls) == 2
    assert Path(calls[0][1]).name == "export_issue_views.py"
    assert "--json-out" in calls[0]
    assert Path(calls[1][1]).name == "openclaw_guardian_run.py"
    assert "--projection-only" in calls[1]
    assert "--report-out" in calls[1]


def test_refresh_monitor_projections_returns_nonzero_on_child_failure(monkeypatch, tmp_path: Path) -> None:
    class _Proc:
        def __init__(self, returncode: int) -> None:
            self.returncode = returncode
            self.stdout = ""
            self.stderr = ""

    def _fake_run(cmd, cwd, capture_output, text, check):
        name = Path(str(cmd[1])).name
        if name == "export_issue_views.py":
            return _Proc(1)
        return _Proc(0)

    monkeypatch.setattr(refresh_monitor_projections.subprocess, "run", _fake_run)

    rc = refresh_monitor_projections.main(
        [
            "--python-bin",
            "/tmp/python",
            "--db-path",
            str(tmp_path / "jobdb.sqlite3"),
            "--skip-guardian",
        ]
    )

    assert rc == 2
