from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Sequence

from chatgptrest.core.chatgpt_web_hold import get_chatgpt_web_hold
from chatgptrest.core.db import connect
from chatgptrest.core.pause import get_pause_state
from ops import manual_pro_watch_guard as guard


class _Runner:
    def __init__(self, *, active_units: set[str] | None = None) -> None:
        self.active_units = active_units or set()
        self.commands: list[list[str]] = []

    def __call__(self, cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
        argv = list(cmd)
        self.commands.append(argv)
        if argv[:3] == ["systemctl", "--user", "is-active"]:
            statuses = ["active" if unit in self.active_units else "inactive" for unit in argv[3:]]
            return subprocess.CompletedProcess(argv, 0 if any(s == "active" for s in statuses) else 3, "\n".join(statuses) + "\n", "")
        if argv[:3] == ["systemctl", "--user", "stop"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:4] == ["systemctl", "--user", "mask", "--runtime"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:3] == ["systemctl", "--user", "unmask"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, "", "")


def _config(tmp_path: Path, *, scan_existing_mcp_calls: bool = False) -> guard.GuardConfig:
    return guard.GuardConfig(
        db_path=tmp_path / "jobdb.sqlite3",
        mcp_calls_log=tmp_path / "mcp_calls.jsonl",
        blocked_state_file=tmp_path / "driver" / "chatgpt_blocked_state.json",
        systemd_allow_file=tmp_path / "run" / "chatgptrest_manual_pro_watch_allow_web_automation",
        run_dir=tmp_path / "guard-run",
        poll_seconds=0.01,
        duration_seconds=-1,
        frontend_hold_seconds=600,
        scan_existing_mcp_calls=scan_existing_mcp_calls,
    )


def test_guard_seeds_manual_pro_hold_and_worker_pause(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    cfg.systemd_allow_file.parent.mkdir(parents=True)
    cfg.systemd_allow_file.touch()
    runner = _Runner()

    code = guard.run_guard(cfg, runner=runner)

    assert code == 0
    blocked = json.loads(cfg.blocked_state_file.read_text(encoding="utf-8"))
    assert blocked["reason"] == "manual_pro_session"
    assert blocked["source"] == "manual_pro_watch_guard"

    with connect(cfg.db_path) as conn:
        hold = get_chatgpt_web_hold(conn)
        pause = get_pause_state(conn)
    assert hold is not None
    assert hold.reason == "manual_pro_session"
    assert hold.source == "manual_pro_watch_guard"
    assert pause.mode == "all"
    assert pause.reason == "auto_blocked:manual_pro_watch_guard"
    assert pause.until_ts > 0
    assert not cfg.systemd_allow_file.exists()
    assert ["systemctl", "--user", "mask", "--runtime", *guard.DEFAULT_PROTECTED_UNITS] in runner.commands


def test_release_requires_explicit_confirmation(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    guard.run_guard(cfg, runner=_Runner())

    runner = _Runner()
    result = guard.release_manual_pro_hold(cfg, release_reason="manual window ended", runner=runner)

    assert result["released"] is True
    assert result["db_hold_cleared"] is True
    assert result["blocked_state_file_removed"] is True
    assert result["systemd_allow_file"]["restored"] is True
    assert result["systemd_unmask"]["unmasked"] is True
    assert cfg.systemd_allow_file.exists()
    assert ["systemctl", "--user", "unmask", *guard.DEFAULT_PROTECTED_UNITS] in runner.commands
    with connect(cfg.db_path) as conn:
        assert get_chatgpt_web_hold(conn) is None
        pause = get_pause_state(conn)
    assert pause.mode == "none"


def test_guard_removes_recreated_systemd_allow_file_on_violation(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    cfg.systemd_allow_file.parent.mkdir(parents=True)
    cfg.systemd_allow_file.touch()
    runner = _Runner(active_units={"chatgptrest-driver.service"})

    code = guard.run_guard(cfg, runner=runner)

    assert code == 2
    assert not cfg.systemd_allow_file.exists()
    alerts = (cfg.run_dir / "alerts.jsonl").read_text(encoding="utf-8")
    assert "remove_systemd_allow_file" in alerts
    assert "mask_protected_units" in alerts


def test_guard_stops_protected_units_on_violation(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    runner = _Runner(active_units={"chatgptrest-driver.service"})

    code = guard.run_guard(cfg, runner=runner)

    assert code == 2
    assert ["systemctl", "--user", "stop", *guard.DEFAULT_PROTECTED_UNITS] in runner.commands
    alerts = (cfg.run_dir / "alerts.jsonl").read_text(encoding="utf-8")
    assert "protected_unit_active" in alerts


def test_guard_detects_chatgpt_web_calls_in_mcp_log(tmp_path: Path) -> None:
    cfg = _config(tmp_path, scan_existing_mcp_calls=True)
    cfg.mcp_calls_log.write_text(
        json.dumps({"tool": "chatgpt_web_ask", "status": "completed"}) + "\n",
        encoding="utf-8",
    )
    runner = _Runner()

    code = guard.run_guard(cfg, runner=runner)

    assert code == 2
    alerts = (cfg.run_dir / "alerts.jsonl").read_text(encoding="utf-8")
    assert "chatgpt_web_tool_call_observed" in alerts


def test_guard_detects_active_chatgpt_web_jobs_without_phase_detail_column(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with connect(cfg.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO jobs (
              job_id, kind, input_json, params_json, status,
              created_at, updated_at, not_before, phase
            ) VALUES (
              'job-chatgpt-active', 'chatgpt_web.ask', '{}', '{}', 'queued',
              1.0, 2.0, 0.0, 'send'
            )
            """
        )
        conn.commit()
    runner = _Runner()

    code = guard.run_guard(cfg, runner=runner)

    assert code == 2
    samples = (cfg.run_dir / "samples.jsonl").read_text(encoding="utf-8")
    assert "active_chatgpt_web_jobs" in samples
    assert "job-chatgpt-active" in samples


def test_old_mcp_log_is_ignored_by_default(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    cfg.mcp_calls_log.write_text(
        json.dumps({"tool": "chatgpt_web_ask", "status": "completed"}) + "\n",
        encoding="utf-8",
    )
    runner = _Runner()

    code = guard.run_guard(cfg, runner=runner)

    assert code == 0


def test_default_systemd_allow_file_is_persistent_repo_state() -> None:
    assert "/run/user/" not in str(guard.DEFAULT_SYSTEMD_ALLOW_FILE)
    assert str(guard.DEFAULT_SYSTEMD_ALLOW_FILE).endswith(
        "state/driver/chatgptrest_manual_pro_watch_allow_web_automation"
    )
