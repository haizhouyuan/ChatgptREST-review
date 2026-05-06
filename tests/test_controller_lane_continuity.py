from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import time
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[1] / "ops" / "controller_lane_continuity.py"
_SPEC = importlib.util.spec_from_file_location("controller_lane_continuity", _MODULE_PATH)
assert _SPEC and _SPEC.loader
ctl = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = ctl
_SPEC.loader.exec_module(ctl)


def _db(tmp_path: Path) -> Path:
    return tmp_path / "controller_lanes.sqlite3"


def test_upsert_lane_and_status_roundtrip(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    payload = ctl.upsert_lane(
        db_path=db_path,
        lane_id="scout",
        purpose="read-only scout",
        lane_kind="codex",
        cwd=str(tmp_path),
        desired_state="running",
        run_state="idle",
        session_key="lane:scout",
        stale_after_seconds=600,
        restart_cooldown_seconds=60,
        launch_cmd="echo launch",
        resume_cmd="echo resume",
    )

    assert payload["lane_id"] == "scout"
    assert payload["purpose"] == "read-only scout"
    assert payload["run_state"] == "idle"
    assert payload["launch_cmd"] == "echo launch"
    assert payload["resume_cmd"] == "echo resume"
    assert payload["stale"] is True


def test_heartbeat_updates_pid_and_summary(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    ctl.upsert_lane(
        db_path=db_path,
        lane_id="worker",
        purpose="bounded worker",
        lane_kind="codex",
        cwd=str(tmp_path),
        desired_state="running",
        run_state="idle",
        session_key="lane:worker",
        stale_after_seconds=600,
        restart_cooldown_seconds=60,
        launch_cmd="echo launch",
        resume_cmd="echo resume",
    )

    payload = ctl.heartbeat_lane(
        db_path=db_path,
        lane_id="worker",
        pid=1234,
        summary="indexing tests",
        run_state="working",
    )

    assert payload["pid"] == 1234
    assert payload["run_state"] == "working"
    assert payload["last_summary"] == "indexing tests"


def test_report_completed_prevents_restart(tmp_path: Path, monkeypatch) -> None:
    db_path = _db(tmp_path)
    artifacts_dir = tmp_path / "artifacts"
    ctl.upsert_lane(
        db_path=db_path,
        lane_id="verifier",
        purpose="test verifier",
        lane_kind="codex",
        cwd=str(tmp_path),
        desired_state="running",
        run_state="idle",
        session_key="lane:verifier",
        stale_after_seconds=1,
        restart_cooldown_seconds=0,
        launch_cmd="echo launch",
        resume_cmd="echo resume",
    )
    ctl.report_lane(
        db_path=db_path,
        lane_id="verifier",
        run_state="completed",
        summary="done",
        artifact_path=str(tmp_path / "result.md"),
        error="",
        checkpoint_pending=False,
        exit_code=0,
    )

    spawned: list[str] = []
    monkeypatch.setattr(ctl, "_spawn_detached", lambda **kwargs: spawned.append(kwargs["cmd"]) or 9999)

    result = ctl.sweep_lanes(db_path=db_path, artifacts_dir=artifacts_dir, restart=True)
    assert result["restarted"] == []
    assert spawned == []


def test_sweep_restarts_idle_lane_with_launch_command(tmp_path: Path, monkeypatch) -> None:
    db_path = _db(tmp_path)
    artifacts_dir = tmp_path / "artifacts"
    ctl.upsert_lane(
        db_path=db_path,
        lane_id="scout",
        purpose="read-only scout",
        lane_kind="codex",
        cwd=str(tmp_path),
        desired_state="running",
        run_state="idle",
        session_key="lane:scout",
        stale_after_seconds=600,
        restart_cooldown_seconds=0,
        launch_cmd="echo launch-scout",
        resume_cmd="echo resume-scout",
    )

    spawned: list[str] = []
    monkeypatch.setattr(ctl, "_spawn_detached", lambda **kwargs: spawned.append(kwargs["cmd"]) or 4321)

    result = ctl.sweep_lanes(db_path=db_path, artifacts_dir=artifacts_dir, restart=True)

    assert result["restarted"] == ["scout"]
    assert spawned == ["echo launch-scout"]
    lane = ctl.lane_status(db_path=db_path, lane_id="scout")
    assert lane["pid"] == 4321
    assert lane["restart_count"] == 1


def test_sweep_uses_resume_command_after_first_restart(tmp_path: Path, monkeypatch) -> None:
    db_path = _db(tmp_path)
    artifacts_dir = tmp_path / "artifacts"
    ctl.upsert_lane(
        db_path=db_path,
        lane_id="worker",
        purpose="bounded worker",
        lane_kind="codex",
        cwd=str(tmp_path),
        desired_state="running",
        run_state="working",
        session_key="lane:worker",
        stale_after_seconds=1,
        restart_cooldown_seconds=0,
        launch_cmd="echo launch-worker",
        resume_cmd="echo resume-worker",
    )

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        UPDATE lanes
        SET restart_count = 1, heartbeat_at = ?, pid = ?, last_launch_at = ?
        WHERE lane_id = 'worker'
        """,
        (time.time() - 500, 999999, time.time() - 500),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(ctl, "_pid_alive", lambda _pid: False)
    spawned: list[str] = []
    monkeypatch.setattr(ctl, "_spawn_detached", lambda **kwargs: spawned.append(kwargs["cmd"]) or 5555)

    result = ctl.sweep_lanes(db_path=db_path, artifacts_dir=artifacts_dir, restart=True)
    assert result["restarted"] == ["worker"]
    assert spawned == ["echo resume-worker"]


def test_draft_digest_highlights_attention(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    ctl.upsert_lane(
        db_path=db_path,
        lane_id="main",
        purpose="controller",
        lane_kind="codex",
        cwd=str(tmp_path),
        desired_state="running",
        run_state="needs_gate",
        session_key="lane:main",
        stale_after_seconds=600,
        restart_cooldown_seconds=60,
        launch_cmd="",
        resume_cmd="",
    )
    ctl.report_lane(
        db_path=db_path,
        lane_id="main",
        run_state="needs_gate",
        summary="needs human approval",
        artifact_path="",
        error="",
        checkpoint_pending=True,
        exit_code=None,
    )

    digest = ctl.build_digest(db_path=db_path)
    assert "main: needs_gate" in digest
    assert "checkpoint" in digest
    assert "needs human approval" in digest


def test_sync_manifest_upserts_multiple_observed_lanes(tmp_path: Path) -> None:
    db_path = _db(tmp_path)
    manifest_path = tmp_path / "controller_lanes.json"
    manifest_path.write_text(
        json.dumps(
            {
                "lanes": [
                    {
                        "lane_id": "main",
                        "purpose": "primary controller",
                        "lane_kind": "codex",
                        "cwd": str(tmp_path),
                        "desired_state": "observed",
                        "run_state": "working",
                    },
                    {
                        "lane_id": "verifier",
                        "purpose": "tests and smoke validation",
                        "lane_kind": "codex",
                        "cwd": str(tmp_path),
                        "desired_state": "observed",
                        "run_state": "idle",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = ctl.sync_manifest(db_path=db_path, manifest_path=manifest_path)

    assert payload["ok"] is True
    assert payload["synced_count"] == 2
    assert payload["lane_ids"] == ["main", "verifier"]
    lanes = ctl.list_lanes(db_path=db_path)
    assert [lane["lane_id"] for lane in lanes] == ["main", "verifier"]
    assert all(lane["desired_state"] == "observed" for lane in lanes)
    assert all(lane["stale"] is False for lane in lanes)
