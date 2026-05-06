#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.chatgpt_web_hold import clear_chatgpt_web_hold, set_chatgpt_web_hold
from chatgptrest.core.db import connect
from chatgptrest.core.pause import clear_pause_state, set_pause_state


DEFAULT_PROTECTED_UNITS = (
    "chatgptrest-driver.service",
    "chatgptrest-worker-send.service",
    "chatgptrest-worker-wait.service",
)
DEFAULT_SYSTEMD_ALLOW_FILE = REPO_ROOT / "state" / "driver" / "chatgptrest_manual_pro_watch_allow_web_automation"
ACTIVE_UNIT_STATES = {"active", "activating", "reloading"}
ACTIVE_JOB_STATUSES = ("queued", "in_progress")
CHATGPT_WEB_HOLD_REASONS = {"frontend_rate_limit", "manual_pro_session"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp_dir_name(now: float | None = None) -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now or time.time()))


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()


def _resolve_path(raw: str | Path) -> Path:
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve(strict=False)
    return path


@dataclass(frozen=True)
class GuardConfig:
    db_path: Path
    mcp_calls_log: Path
    blocked_state_file: Path
    systemd_allow_file: Path
    run_dir: Path
    protected_units: tuple[str, ...] = DEFAULT_PROTECTED_UNITS
    poll_seconds: float = 5.0
    duration_seconds: float = 0.0
    frontend_hold_seconds: float = 10800.0
    source: str = "manual_pro_watch_guard"
    operator_note: str = (
        "Manual Pro watch guard is active. ChatGPT Web automation must stay disabled "
        "until the operator explicitly ends the watch."
    )
    enforce: bool = True
    stop_units: bool = True
    mask_units: bool = True
    scan_existing_mcp_calls: bool = False
    fail_on_violation: bool = True


@dataclass
class GuardState:
    mcp_offset: int = 0
    started_at: float = field(default_factory=time.time)
    violation_count: int = 0
    frontend_hold_written: bool = False


@dataclass(frozen=True)
class Violation:
    kind: str
    severity: str
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity, "detail": self.detail}


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _default_runner(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def initial_mcp_offset(path: Path, *, scan_existing: bool) -> int:
    if scan_existing:
        return 0
    try:
        return int(path.stat().st_size)
    except FileNotFoundError:
        return 0
    except OSError:
        return 0


def read_new_mcp_call_records(path: Path, *, offset: int) -> tuple[list[dict[str, Any]], int]:
    try:
        size = int(path.stat().st_size)
    except FileNotFoundError:
        return [], 0
    except OSError:
        return [], offset
    if size < offset:
        offset = 0
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            raw = handle.read()
            next_offset = int(handle.tell())
    except OSError:
        return [], offset
    records: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except Exception:
            obj = {"_raw": text}
        if isinstance(obj, dict):
            records.append(obj)
    return records, next_offset


def is_chatgpt_web_call(record: dict[str, Any]) -> bool:
    tool = str(record.get("tool") or "").strip()
    if tool.startswith("chatgpt_web_"):
        return True
    raw = str(record.get("_raw") or "")
    return '"chatgpt_web_' in raw or "chatgpt_web_" in raw


def active_chatgpt_web_jobs(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    connection = sqlite3.connect(str(db_path), timeout=10.0)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT job_id, kind, status, phase, conversation_url, updated_at
            FROM jobs
            WHERE status IN (?, ?)
              AND kind LIKE 'chatgpt_web.%'
            ORDER BY updated_at DESC
            LIMIT 50
            """,
            ACTIVE_JOB_STATUSES,
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def systemd_unit_states(units: Sequence[str], *, runner: Runner = _default_runner) -> dict[str, str]:
    if not units:
        return {}
    result = runner(["systemctl", "--user", "is-active", *units])
    lines = [line.strip() for line in (result.stdout or "").splitlines()]
    states: dict[str, str] = {}
    for index, unit in enumerate(units):
        states[str(unit)] = lines[index] if index < len(lines) and lines[index] else "unknown"
    return states


def write_frontend_hold(config: GuardConfig, *, now: float | None = None) -> dict[str, Any]:
    now_ts = float(now if now is not None else time.time())
    blocked_until = now_ts + float(max(60.0, config.frontend_hold_seconds))
    existing = _read_json(config.blocked_state_file)
    if isinstance(existing, dict):
        existing_reason = str(existing.get("reason") or "").strip()
        existing_until = float(existing.get("blocked_until") or 0.0)
        if existing_reason in CHATGPT_WEB_HOLD_REASONS and existing_until >= blocked_until:
            return {
                "written": False,
                "path": str(config.blocked_state_file),
                "reason": existing_reason,
                "blocked_until": existing_until,
                "source": existing.get("source"),
            }
    payload: dict[str, Any] = {
        "reason": "manual_pro_session",
        "blocked_until": blocked_until,
        "set_at": now_ts,
        "cooldown_seconds": float(max(60.0, config.frontend_hold_seconds)),
        "source": config.source,
        "operator_note": config.operator_note,
    }
    if existing:
        payload["previous_state"] = existing
    _json_dump(config.blocked_state_file, payload)
    return {
        "written": True,
        "path": str(config.blocked_state_file),
        "reason": payload["reason"],
        "blocked_until": blocked_until,
        "source": config.source,
    }


def set_worker_pause_for_manual_pro(config: GuardConfig, *, blocked_until: float) -> dict[str, Any]:
    reason = f"auto_blocked:{config.source}"
    with connect(config.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        pause = set_pause_state(
            conn,
            mode="all",
            until_ts=float(blocked_until),
            reason=reason,
        )
        conn.commit()
    return {
        "mode": pause.mode,
        "until_ts": float(pause.until_ts),
        "reason": pause.reason,
    }


def set_db_hold_for_manual_pro(config: GuardConfig, *, blocked_until: float) -> dict[str, Any]:
    with connect(config.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        hold = set_chatgpt_web_hold(
            conn,
            reason="manual_pro_session",
            until_ts=float(blocked_until),
            source=config.source,
            note=config.operator_note,
        )
        conn.commit()
    return hold.to_detail()


def remove_systemd_allow_file(config: GuardConfig) -> dict[str, Any]:
    removed = False
    existed = False
    try:
        existed = config.systemd_allow_file.exists()
        if existed:
            config.systemd_allow_file.unlink()
            removed = True
    except FileNotFoundError:
        existed = False
    return {
        "path": str(config.systemd_allow_file),
        "existed": existed,
        "removed": removed,
    }


def restore_systemd_allow_file(config: GuardConfig) -> dict[str, Any]:
    config.systemd_allow_file.parent.mkdir(parents=True, exist_ok=True)
    config.systemd_allow_file.touch(exist_ok=True)
    return {
        "path": str(config.systemd_allow_file),
        "restored": True,
    }


def mask_protected_units(
    config: GuardConfig,
    *,
    runner: Runner = _default_runner,
) -> dict[str, Any]:
    if not config.protected_units:
        return {"masked": False, "units": []}
    result = runner(["systemctl", "--user", "mask", "--runtime", *config.protected_units])
    return {
        "masked": result.returncode == 0,
        "units": list(config.protected_units),
        "returncode": int(result.returncode),
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
    }


def unmask_protected_units(
    config: GuardConfig,
    *,
    runner: Runner = _default_runner,
) -> dict[str, Any]:
    if not config.protected_units:
        return {"unmasked": False, "units": []}
    result = runner(["systemctl", "--user", "unmask", *config.protected_units])
    return {
        "unmasked": result.returncode == 0,
        "units": list(config.protected_units),
        "returncode": int(result.returncode),
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
    }


def release_manual_pro_hold(
    config: GuardConfig,
    *,
    release_reason: str,
    runner: Runner = _default_runner,
) -> dict[str, Any]:
    with connect(config.db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        clear_chatgpt_web_hold(conn)
        pause = clear_pause_state(conn)
        conn.commit()
    removed_state_file = False
    try:
        config.blocked_state_file.unlink()
        removed_state_file = True
    except FileNotFoundError:
        removed_state_file = False
    systemd_allow = restore_systemd_allow_file(config)
    unmask = unmask_protected_units(config, runner=runner) if config.mask_units else {"unmasked": False, "units": []}
    return {
        "released": True,
        "release_reason": str(release_reason or "").strip(),
        "db_hold_cleared": True,
        "pause": {
            "mode": pause.mode,
            "until_ts": float(pause.until_ts),
            "reason": pause.reason,
        },
        "blocked_state_file": str(config.blocked_state_file),
        "blocked_state_file_removed": removed_state_file,
        "systemd_allow_file": systemd_allow,
        "systemd_unmask": unmask,
    }


def collect_violations(
    config: GuardConfig,
    state: GuardState,
    *,
    runner: Runner = _default_runner,
) -> tuple[list[Violation], dict[str, Any]]:
    records, next_offset = read_new_mcp_call_records(config.mcp_calls_log, offset=state.mcp_offset)
    state.mcp_offset = next_offset
    chatgpt_calls = [record for record in records if is_chatgpt_web_call(record)]
    unit_states = systemd_unit_states(config.protected_units, runner=runner)
    active_units = {
        unit: status
        for unit, status in unit_states.items()
        if str(status).strip().lower() in ACTIVE_UNIT_STATES
    }
    active_jobs = active_chatgpt_web_jobs(config.db_path)
    systemd_allow_file_present = config.systemd_allow_file.exists()

    violations: list[Violation] = []
    if config.enforce and systemd_allow_file_present:
        violations.append(
            Violation(
                kind="systemd_allow_file_present",
                severity="P0",
                detail={"path": str(config.systemd_allow_file)},
            )
        )
    if active_units:
        violations.append(
            Violation(
                kind="protected_unit_active",
                severity="P0",
                detail={"units": active_units},
            )
        )
    if chatgpt_calls:
        violations.append(
            Violation(
                kind="chatgpt_web_tool_call_observed",
                severity="P0",
                detail={"calls": chatgpt_calls[-20:]},
            )
        )
    if active_jobs:
        violations.append(
            Violation(
                kind="active_chatgpt_web_jobs",
                severity="P1",
                detail={"jobs": active_jobs},
            )
        )

    sample = {
        "ts": _utc_now_iso(),
        "mcp_offset": state.mcp_offset,
        "unit_states": unit_states,
        "systemd_allow_file_present": systemd_allow_file_present,
        "systemd_allow_file": str(config.systemd_allow_file),
        "chatgpt_web_calls": chatgpt_calls[-20:],
        "active_chatgpt_web_jobs": active_jobs,
        "violations": [violation.to_dict() for violation in violations],
    }
    return violations, sample


def remediate(
    config: GuardConfig,
    violations: Sequence[Violation],
    *,
    runner: Runner = _default_runner,
) -> dict[str, Any]:
    action: dict[str, Any] = {
        "ts": _utc_now_iso(),
        "enforce": bool(config.enforce),
        "violations": [violation.to_dict() for violation in violations],
        "actions": [],
    }
    hold = write_frontend_hold(config)
    action["actions"].append({"type": "write_frontend_hold", "result": hold})
    db_hold = set_db_hold_for_manual_pro(config, blocked_until=float(hold.get("blocked_until") or time.time()))
    action["actions"].append({"type": "set_db_chatgpt_web_hold", "result": db_hold})
    pause = set_worker_pause_for_manual_pro(config, blocked_until=float(hold.get("blocked_until") or time.time()))
    action["actions"].append({"type": "set_worker_pause", "result": pause})
    if config.enforce:
        allow_file = remove_systemd_allow_file(config)
        action["actions"].append({"type": "remove_systemd_allow_file", "result": allow_file})
    if config.enforce and config.mask_units and config.protected_units:
        mask = mask_protected_units(config, runner=runner)
        action["actions"].append({"type": "mask_protected_units", "result": mask})
    if config.enforce and config.stop_units and config.protected_units:
        result = runner(["systemctl", "--user", "stop", *config.protected_units])
        action["actions"].append(
            {
                "type": "systemctl_stop",
                "units": list(config.protected_units),
                "returncode": int(result.returncode),
                "stdout": (result.stdout or "").strip(),
                "stderr": (result.stderr or "").strip(),
            }
        )
    elif not config.enforce:
        action["actions"].append({"type": "dry_run_no_stop"})
    return action


def run_guard(config: GuardConfig, *, runner: Runner = _default_runner) -> int:
    config.run_dir.mkdir(parents=True, exist_ok=True)
    alerts_path = config.run_dir / "alerts.jsonl"
    samples_path = config.run_dir / "samples.jsonl"
    summary_path = config.run_dir / "summary.json"
    state = GuardState(
        mcp_offset=initial_mcp_offset(config.mcp_calls_log, scan_existing=config.scan_existing_mcp_calls)
    )
    started_record = {
        "ts": _utc_now_iso(),
        "type": "manual_pro_watch_guard_started",
        "config": {
            "db_path": str(config.db_path),
            "mcp_calls_log": str(config.mcp_calls_log),
            "blocked_state_file": str(config.blocked_state_file),
            "systemd_allow_file": str(config.systemd_allow_file),
            "protected_units": list(config.protected_units),
            "poll_seconds": config.poll_seconds,
            "duration_seconds": config.duration_seconds,
            "frontend_hold_seconds": config.frontend_hold_seconds,
            "enforce": config.enforce,
            "stop_units": config.stop_units,
            "mask_units": config.mask_units,
            "scan_existing_mcp_calls": config.scan_existing_mcp_calls,
        },
    }
    _append_jsonl(alerts_path, started_record)
    if config.enforce:
        allow_file = remove_systemd_allow_file(config)
        _append_jsonl(alerts_path, {"ts": _utc_now_iso(), "type": "systemd_allow_file_removed", "result": allow_file})
        if config.mask_units and config.protected_units:
            mask = mask_protected_units(config, runner=runner)
            _append_jsonl(alerts_path, {"ts": _utc_now_iso(), "type": "protected_units_masked", "result": mask})
    if config.frontend_hold_seconds > 0:
        hold = write_frontend_hold(config)
        state.frontend_hold_written = True
        _append_jsonl(alerts_path, {"ts": _utc_now_iso(), "type": "frontend_hold_seeded", "result": hold})
        db_hold = set_db_hold_for_manual_pro(config, blocked_until=float(hold.get("blocked_until") or time.time()))
        _append_jsonl(alerts_path, {"ts": _utc_now_iso(), "type": "db_chatgpt_web_hold_seeded", "result": db_hold})
        pause = set_worker_pause_for_manual_pro(config, blocked_until=float(hold.get("blocked_until") or time.time()))
        _append_jsonl(alerts_path, {"ts": _utc_now_iso(), "type": "worker_pause_seeded", "result": pause})

    deadline = None
    if config.duration_seconds > 0:
        deadline = state.started_at + float(config.duration_seconds)

    sample_count = 0
    try:
        while deadline is None or time.time() < deadline:
            violations, sample = collect_violations(config, state, runner=runner)
            sample_count += 1
            sample["sample_no"] = sample_count
            _append_jsonl(samples_path, sample)
            if violations:
                state.violation_count += len(violations)
                action = remediate(config, violations, runner=runner)
                _append_jsonl(alerts_path, {"ts": _utc_now_iso(), "type": "manual_pro_watch_violation", "action": action})
            if config.duration_seconds < 0:
                break
            if deadline is not None and time.time() >= deadline:
                break
            time.sleep(max(0.5, float(config.poll_seconds)))
    finally:
        summary = {
            "started_at": datetime.fromtimestamp(state.started_at, tz=timezone.utc).isoformat(),
            "ended_at": _utc_now_iso(),
            "samples": sample_count,
            "violation_count": state.violation_count,
            "alerts_path": str(alerts_path),
            "samples_path": str(samples_path),
            "frontend_hold_written": state.frontend_hold_written,
        }
        _json_dump(summary_path, summary)
        _append_jsonl(alerts_path, {"ts": _utc_now_iso(), "type": "manual_pro_watch_guard_finished", "summary": summary})

    if config.fail_on_violation and state.violation_count > 0:
        return 2
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed guard for manual ChatGPT Pro usage windows."
    )
    parser.add_argument("--db", default=os.environ.get("CHATGPTREST_DB_PATH") or "state/jobdb.sqlite3")
    parser.add_argument("--mcp-calls-log", default=os.environ.get("MCP_CALL_LOG") or "artifacts/mcp_calls.jsonl")
    parser.add_argument(
        "--blocked-state-file",
        default=(
            os.environ.get("CHATGPTREST_CHATGPT_FRONTEND_BLOCK_STATE_FILE")
            or os.environ.get("CHATGPT_BLOCKED_STATE_FILE")
            or "state/driver/chatgpt_blocked_state.json"
        ),
    )
    parser.add_argument(
        "--systemd-allow-file",
        default=os.environ.get("CHATGPTREST_MANUAL_PRO_WATCH_ALLOW_FILE") or str(DEFAULT_SYSTEMD_ALLOW_FILE),
        help="Persistent allow file used by systemd ConditionPathExists for ChatGPT Web units.",
    )
    parser.add_argument("--out-dir", default="artifacts/monitor/manual_pro_watch_guard")
    parser.add_argument("--run-dir", default="", help="Exact output directory; overrides --out-dir timestamp subdir.")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--duration-seconds", type=float, default=0.0, help="0 runs until interrupted; -1 runs once.")
    parser.add_argument("--frontend-hold-seconds", type=float, default=10800.0)
    parser.add_argument("--source", default="manual_pro_watch_guard")
    parser.add_argument("--operator-note", default=GuardConfig.operator_note)
    parser.add_argument("--unit", action="append", default=[], help="Protected user systemd unit; repeatable.")
    parser.add_argument("--dry-run", action="store_true", help="Write evidence and frontend hold, but do not stop units.")
    parser.add_argument("--no-stop-units", action="store_true")
    parser.add_argument("--no-mask-units", action="store_true")
    parser.add_argument("--scan-existing-mcp-calls", action="store_true")
    parser.add_argument("--no-fail-on-violation", action="store_true")
    parser.add_argument("--release", action="store_true", help="Clear the durable manual Pro hold and worker pause.")
    parser.add_argument("--release-reason", default="", help="Required with --release.")
    parser.add_argument(
        "--confirm-release-manual-pro-session",
        action="store_true",
        help="Required with --release to avoid accidental hold removal.",
    )
    return parser


def config_from_args(args: argparse.Namespace) -> GuardConfig:
    run_dir_raw = str(args.run_dir or "").strip()
    if run_dir_raw:
        run_dir = _resolve_path(run_dir_raw)
    else:
        run_dir = _resolve_path(args.out_dir) / _timestamp_dir_name()
    units = tuple(str(unit).strip() for unit in (args.unit or []) if str(unit).strip())
    if not units:
        units = DEFAULT_PROTECTED_UNITS
    return GuardConfig(
        db_path=_resolve_path(args.db),
        mcp_calls_log=_resolve_path(args.mcp_calls_log),
        blocked_state_file=_resolve_path(args.blocked_state_file),
        systemd_allow_file=_resolve_path(args.systemd_allow_file),
        run_dir=run_dir,
        protected_units=units,
        poll_seconds=float(args.poll_seconds),
        duration_seconds=float(args.duration_seconds),
        frontend_hold_seconds=float(args.frontend_hold_seconds),
        source=str(args.source or "manual_pro_watch_guard"),
        operator_note=str(args.operator_note or GuardConfig.operator_note),
        enforce=not bool(args.dry_run),
        stop_units=not bool(args.no_stop_units),
        mask_units=not bool(args.no_mask_units),
        scan_existing_mcp_calls=bool(args.scan_existing_mcp_calls),
        fail_on_violation=not bool(args.no_fail_on_violation),
    )


def main(argv: list[str]) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config = config_from_args(args)
    if bool(args.release):
        reason = str(args.release_reason or "").strip()
        if not reason or not bool(args.confirm_release_manual_pro_session):
            parser.error("--release requires --release-reason and --confirm-release-manual-pro-session")
        result = release_manual_pro_hold(config, release_reason=reason)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    code = run_guard(config)
    print(str(config.run_dir))
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
