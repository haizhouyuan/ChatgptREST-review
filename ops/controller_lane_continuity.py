#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "state" / "controller_lanes.sqlite3"
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "controller_lanes"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "config" / "controller_lanes.json"
ACTIVE_STATES = {"idle", "working"}
TERMINAL_STATES = {"completed", "failed", "needs_gate", "paused"}


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS lanes (
            lane_id TEXT PRIMARY KEY,
            purpose TEXT NOT NULL,
            lane_kind TEXT NOT NULL,
            cwd TEXT NOT NULL,
            desired_state TEXT NOT NULL,
            run_state TEXT NOT NULL,
            session_key TEXT NOT NULL DEFAULT '',
            stale_after_seconds INTEGER NOT NULL DEFAULT 900,
            restart_cooldown_seconds INTEGER NOT NULL DEFAULT 300,
            heartbeat_at REAL,
            pid INTEGER,
            launch_cmd TEXT NOT NULL DEFAULT '',
            resume_cmd TEXT NOT NULL DEFAULT '',
            last_summary TEXT NOT NULL DEFAULT '',
            last_artifact_path TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '',
            checkpoint_pending INTEGER NOT NULL DEFAULT 0,
            restart_count INTEGER NOT NULL DEFAULT 0,
            last_launch_at REAL,
            last_exit_code INTEGER,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS lane_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lane_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL
        );
        """
    )
    return conn


def _record_event(conn: sqlite3.Connection, lane_id: str, event_type: str, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO lane_events (lane_id, event_type, payload_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (lane_id, event_type, json.dumps(payload, ensure_ascii=False, sort_keys=True), time.time()),
    )


def _pid_alive(pid: int | None) -> bool:
    if pid is None or int(pid) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def _json_output(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def upsert_lane(
    *,
    db_path: Path,
    lane_id: str,
    purpose: str,
    lane_kind: str,
    cwd: str,
    desired_state: str,
    run_state: str,
    session_key: str,
    stale_after_seconds: int,
    restart_cooldown_seconds: int,
    launch_cmd: str,
    resume_cmd: str,
) -> dict[str, Any]:
    now = time.time()
    conn = _connect(db_path)
    try:
        existing = conn.execute("SELECT * FROM lanes WHERE lane_id = ?", (lane_id,)).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO lanes (
                    lane_id, purpose, lane_kind, cwd, desired_state, run_state, session_key,
                    stale_after_seconds, restart_cooldown_seconds, launch_cmd, resume_cmd,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lane_id,
                    purpose,
                    lane_kind,
                    cwd,
                    desired_state,
                    run_state,
                    session_key,
                    int(stale_after_seconds),
                    int(restart_cooldown_seconds),
                    launch_cmd,
                    resume_cmd,
                    now,
                    now,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE lanes
                SET purpose = ?, lane_kind = ?, cwd = ?, desired_state = ?, run_state = ?, session_key = ?,
                    stale_after_seconds = ?, restart_cooldown_seconds = ?, launch_cmd = ?, resume_cmd = ?,
                    updated_at = ?
                WHERE lane_id = ?
                """,
                (
                    purpose,
                    lane_kind,
                    cwd,
                    desired_state,
                    run_state,
                    session_key,
                    int(stale_after_seconds),
                    int(restart_cooldown_seconds),
                    launch_cmd,
                    resume_cmd,
                    now,
                    lane_id,
                ),
            )
        _record_event(
            conn,
            lane_id,
            "lane.upserted",
            {
                "purpose": purpose,
                "lane_kind": lane_kind,
                "cwd": cwd,
                "desired_state": desired_state,
                "run_state": run_state,
            },
        )
        conn.commit()
    finally:
        conn.close()
    return lane_status(db_path=db_path, lane_id=lane_id)


def sync_manifest(*, db_path: Path, manifest_path: Path) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    lanes = payload.get("lanes")
    if not isinstance(lanes, list):
        raise ValueError(f"manifest missing lanes list: {manifest_path}")
    synced: list[dict[str, Any]] = []
    for item in lanes:
        if not isinstance(item, dict):
            raise ValueError(f"manifest lane entry must be object: {item!r}")
        lane_id = str(item.get("lane_id") or "").strip()
        purpose = str(item.get("purpose") or "").strip()
        lane_kind = str(item.get("lane_kind") or "").strip()
        cwd = str(item.get("cwd") or "").strip()
        if not lane_id or not purpose or not lane_kind or not cwd:
            raise ValueError(f"manifest lane missing required fields: {item!r}")
        synced.append(
            upsert_lane(
                db_path=db_path,
                lane_id=lane_id,
                purpose=purpose,
                lane_kind=lane_kind,
                cwd=cwd,
                desired_state=str(item.get("desired_state") or "observed"),
                run_state=str(item.get("run_state") or "idle"),
                session_key=str(item.get("session_key") or ""),
                stale_after_seconds=int(item.get("stale_after_seconds") or 900),
                restart_cooldown_seconds=int(item.get("restart_cooldown_seconds") or 300),
                launch_cmd=str(item.get("launch_cmd") or ""),
                resume_cmd=str(item.get("resume_cmd") or ""),
            )
        )
    return {
        "ok": True,
        "manifest_path": str(manifest_path),
        "synced_count": len(synced),
        "lane_ids": [item["lane_id"] for item in synced],
    }


def heartbeat_lane(
    *,
    db_path: Path,
    lane_id: str,
    pid: int | None,
    summary: str,
    run_state: str | None,
) -> dict[str, Any]:
    now = time.time()
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM lanes WHERE lane_id = ?", (lane_id,)).fetchone()
        if row is None:
            raise KeyError(f"lane not found: {lane_id}")
        next_state = run_state if run_state else str(row["run_state"] or "working")
        next_pid = int(pid) if pid is not None else row["pid"]
        conn.execute(
            """
            UPDATE lanes
            SET heartbeat_at = ?, pid = ?, run_state = ?, last_summary = ?, updated_at = ?
            WHERE lane_id = ?
            """,
            (now, next_pid, next_state, summary or str(row["last_summary"] or ""), now, lane_id),
        )
        _record_event(
            conn,
            lane_id,
            "lane.heartbeat",
            {"pid": next_pid, "run_state": next_state, "summary": summary or ""},
        )
        conn.commit()
    finally:
        conn.close()
    return lane_status(db_path=db_path, lane_id=lane_id)


def report_lane(
    *,
    db_path: Path,
    lane_id: str,
    run_state: str,
    summary: str,
    artifact_path: str,
    error: str,
    checkpoint_pending: bool,
    exit_code: int | None,
) -> dict[str, Any]:
    now = time.time()
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM lanes WHERE lane_id = ?", (lane_id,)).fetchone()
        if row is None:
            raise KeyError(f"lane not found: {lane_id}")
        conn.execute(
            """
            UPDATE lanes
            SET run_state = ?, last_summary = ?, last_artifact_path = ?, last_error = ?,
                checkpoint_pending = ?, last_exit_code = ?, updated_at = ?
            WHERE lane_id = ?
            """,
            (
                run_state,
                summary or str(row["last_summary"] or ""),
                artifact_path or str(row["last_artifact_path"] or ""),
                error or "",
                1 if checkpoint_pending else 0,
                exit_code,
                now,
                lane_id,
            ),
        )
        _record_event(
            conn,
            lane_id,
            "lane.reported",
            {
                "run_state": run_state,
                "summary": summary or "",
                "artifact_path": artifact_path or "",
                "checkpoint_pending": bool(checkpoint_pending),
                "exit_code": exit_code,
            },
        )
        conn.commit()
    finally:
        conn.close()
    return lane_status(db_path=db_path, lane_id=lane_id)


def _row_to_status(row: sqlite3.Row) -> dict[str, Any]:
    now = time.time()
    heartbeat_at = float(row["heartbeat_at"]) if row["heartbeat_at"] is not None else None
    last_launch_at = float(row["last_launch_at"]) if row["last_launch_at"] is not None else None
    pid = int(row["pid"]) if row["pid"] is not None else None
    pid_alive = _pid_alive(pid)
    heartbeat_age = (now - heartbeat_at) if heartbeat_at is not None else None
    run_state = str(row["run_state"] or "")
    desired_state = str(row["desired_state"] or "")
    cooldown_until = (
        (last_launch_at + float(row["restart_cooldown_seconds"]))
        if last_launch_at is not None
        else None
    )
    stale = bool(
        desired_state == "running"
        and run_state in ACTIVE_STATES
        and (
            heartbeat_age is None
            or heartbeat_age > float(row["stale_after_seconds"])
            or (pid is not None and not pid_alive)
        )
    )
    return {
        "lane_id": str(row["lane_id"]),
        "purpose": str(row["purpose"]),
        "lane_kind": str(row["lane_kind"]),
        "cwd": str(row["cwd"]),
        "desired_state": desired_state,
        "run_state": run_state,
        "session_key": str(row["session_key"] or ""),
        "stale_after_seconds": int(row["stale_after_seconds"]),
        "restart_cooldown_seconds": int(row["restart_cooldown_seconds"]),
        "heartbeat_at": heartbeat_at,
        "heartbeat_age_seconds": (round(heartbeat_age, 3) if heartbeat_age is not None else None),
        "pid": pid,
        "pid_alive": pid_alive,
        "checkpoint_pending": bool(row["checkpoint_pending"]),
        "restart_count": int(row["restart_count"]),
        "last_launch_at": last_launch_at,
        "cooldown_until": cooldown_until,
        "launch_cmd": str(row["launch_cmd"] or ""),
        "resume_cmd": str(row["resume_cmd"] or ""),
        "last_summary": str(row["last_summary"] or ""),
        "last_artifact_path": str(row["last_artifact_path"] or ""),
        "last_error": str(row["last_error"] or ""),
        "last_exit_code": (int(row["last_exit_code"]) if row["last_exit_code"] is not None else None),
        "created_at": float(row["created_at"]),
        "updated_at": float(row["updated_at"]),
        "stale": stale,
        "needs_attention": bool(stale or row["checkpoint_pending"] or run_state in {"failed", "needs_gate"}),
    }


def list_lanes(*, db_path: Path) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM lanes ORDER BY lane_id").fetchall()
        return [_row_to_status(row) for row in rows]
    finally:
        conn.close()


def lane_status(*, db_path: Path, lane_id: str) -> dict[str, Any]:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM lanes WHERE lane_id = ?", (lane_id,)).fetchone()
        if row is None:
            raise KeyError(f"lane not found: {lane_id}")
        return _row_to_status(row)
    finally:
        conn.close()


def _spawn_detached(*, cmd: str, cwd: str, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(log_path, "ab")
    proc = subprocess.Popen(
        ["bash", "-lc", cmd],
        cwd=str(Path(cwd).expanduser()),
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        text=False,
    )
    return int(proc.pid)


def sweep_lanes(*, db_path: Path, artifacts_dir: Path, restart: bool) -> dict[str, Any]:
    now = time.time()
    conn = _connect(db_path)
    summary: list[dict[str, Any]] = []
    restarted: list[str] = []
    try:
        rows = conn.execute("SELECT * FROM lanes ORDER BY lane_id").fetchall()
        for row in rows:
            status = _row_to_status(row)
            action = "noop"
            reason = ""
            if status["stale"]:
                reason = "stale"
            elif (
                status["desired_state"] == "running"
                and status["run_state"] == "idle"
                and not status["checkpoint_pending"]
                and status["heartbeat_at"] is None
            ):
                reason = "never_started"

            can_restart = bool(
                restart
                and reason
                and not status["checkpoint_pending"]
                and status["run_state"] in ACTIVE_STATES
                and (
                    status["cooldown_until"] is None or float(status["cooldown_until"]) <= now
                )
            )

            if can_restart:
                cmd = status["resume_cmd"] if status["restart_count"] > 0 and status["resume_cmd"] else status["launch_cmd"]
                if cmd:
                    log_path = artifacts_dir / status["lane_id"] / f"launch_{int(now)}.log"
                    pid = _spawn_detached(cmd=cmd, cwd=status["cwd"], log_path=log_path)
                    conn.execute(
                        """
                        UPDATE lanes
                        SET pid = ?, heartbeat_at = ?, last_launch_at = ?, restart_count = restart_count + 1,
                            updated_at = ?, run_state = CASE WHEN run_state = 'idle' THEN 'working' ELSE run_state END
                        WHERE lane_id = ?
                        """,
                        (pid, now, now, now, status["lane_id"]),
                    )
                    _record_event(
                        conn,
                        status["lane_id"],
                        "lane.relaunched",
                        {"reason": reason, "pid": pid, "cmd": cmd, "log_path": str(log_path)},
                    )
                    action = "restarted"
                    restarted.append(status["lane_id"])
                    status["pid"] = pid
                    status["pid_alive"] = True
                else:
                    action = "restart_skipped"
                    _record_event(
                        conn,
                        status["lane_id"],
                        "lane.restart_skipped",
                        {"reason": "missing_command", "stale_reason": reason},
                    )
            elif reason:
                action = "attention"
                _record_event(
                    conn,
                    status["lane_id"],
                    "lane.attention",
                    {"reason": reason, "checkpoint_pending": status["checkpoint_pending"]},
                )

            summary.append(
                {
                    "lane_id": status["lane_id"],
                    "run_state": status["run_state"],
                    "stale": status["stale"],
                    "checkpoint_pending": status["checkpoint_pending"],
                    "action": action,
                    "reason": reason,
                }
            )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "restart_enabled": bool(restart), "restarted": restarted, "lanes": summary}


def build_digest(*, db_path: Path) -> str:
    lanes = list_lanes(db_path=db_path)
    if not lanes:
        return "No registered controller lanes."
    lines: list[str] = []
    for lane in lanes:
        flags: list[str] = []
        if lane["stale"]:
            flags.append("stale")
        if lane["checkpoint_pending"]:
            flags.append("checkpoint")
        if lane["run_state"] == "failed":
            flags.append("failed")
        suffix = f" [{' '.join(flags)}]" if flags else ""
        summary = str(lane["last_summary"] or "").strip() or "no summary"
        lines.append(f"- {lane['lane_id']}: {lane['run_state']}{suffix} — {summary}")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Controller-centric lane continuity registry and sweep tool.")
    p.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    p.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_DIR))
    sub = p.add_subparsers(dest="cmd", required=True)

    upsert = sub.add_parser("upsert-lane")
    upsert.add_argument("--lane-id", required=True)
    upsert.add_argument("--purpose", required=True)
    upsert.add_argument("--lane-kind", required=True)
    upsert.add_argument("--cwd", required=True)
    upsert.add_argument("--desired-state", default="running")
    upsert.add_argument("--run-state", default="idle")
    upsert.add_argument("--session-key", default="")
    upsert.add_argument("--stale-after-seconds", type=int, default=900)
    upsert.add_argument("--restart-cooldown-seconds", type=int, default=300)
    upsert.add_argument("--launch-cmd", default="")
    upsert.add_argument("--resume-cmd", default="")

    heartbeat = sub.add_parser("heartbeat")
    heartbeat.add_argument("--lane-id", required=True)
    heartbeat.add_argument("--pid", type=int, default=None)
    heartbeat.add_argument("--summary", default="")
    heartbeat.add_argument("--run-state", default=None)

    report = sub.add_parser("report")
    report.add_argument("--lane-id", required=True)
    report.add_argument("--run-state", required=True)
    report.add_argument("--summary", default="")
    report.add_argument("--artifact-path", default="")
    report.add_argument("--error", default="")
    report.add_argument("--checkpoint-pending", action="store_true")
    report.add_argument("--exit-code", type=int, default=None)

    status = sub.add_parser("status")
    status.add_argument("--lane-id", default="")

    sub.add_parser("digest")

    sync_manifest_cmd = sub.add_parser("sync-manifest")
    sync_manifest_cmd.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST_PATH))

    sweep = sub.add_parser("sweep")
    sweep.add_argument("--restart", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    db_path = Path(args.db_path).expanduser()
    artifacts_dir = Path(args.artifacts_dir).expanduser()

    if args.cmd == "upsert-lane":
        payload = upsert_lane(
            db_path=db_path,
            lane_id=args.lane_id,
            purpose=args.purpose,
            lane_kind=args.lane_kind,
            cwd=args.cwd,
            desired_state=args.desired_state,
            run_state=args.run_state,
            session_key=args.session_key,
            stale_after_seconds=args.stale_after_seconds,
            restart_cooldown_seconds=args.restart_cooldown_seconds,
            launch_cmd=args.launch_cmd,
            resume_cmd=args.resume_cmd,
        )
        return _json_output(payload)

    if args.cmd == "heartbeat":
        payload = heartbeat_lane(
            db_path=db_path,
            lane_id=args.lane_id,
            pid=args.pid,
            summary=args.summary,
            run_state=args.run_state,
        )
        return _json_output(payload)

    if args.cmd == "report":
        payload = report_lane(
            db_path=db_path,
            lane_id=args.lane_id,
            run_state=args.run_state,
            summary=args.summary,
            artifact_path=args.artifact_path,
            error=args.error,
            checkpoint_pending=bool(args.checkpoint_pending),
            exit_code=args.exit_code,
        )
        return _json_output(payload)

    if args.cmd == "status":
        if args.lane_id:
            return _json_output(lane_status(db_path=db_path, lane_id=args.lane_id))
        return _json_output({"lanes": list_lanes(db_path=db_path)})

    if args.cmd == "digest":
        print(build_digest(db_path=db_path))
        return 0

    if args.cmd == "sync-manifest":
        manifest_path = Path(args.manifest_path).expanduser()
        return _json_output(sync_manifest(db_path=db_path, manifest_path=manifest_path))

    if args.cmd == "sweep":
        return _json_output(sweep_lanes(db_path=db_path, artifacts_dir=artifacts_dir, restart=bool(args.restart)))

    raise SystemExit(f"unsupported command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
