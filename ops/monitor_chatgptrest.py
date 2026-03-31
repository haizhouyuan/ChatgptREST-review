#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _tail_last_jsonl(path: Path, *, max_bytes: int = 32_768) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
    except Exception:
        return None
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            size = min(int(max_bytes), end)
            f.seek(max(0, end - size))
            raw = f.read()
    except Exception:
        return None
    lines = raw.decode("utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        s = (line or "").strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            continue
        return obj if isinstance(obj, dict) else {"_raw": s}
    return None


@dataclass
class MonitorState:
    last_event_id: int = 0
    last_summary_ts: float = 0.0
    last_blocked_state_ts: float = 0.0
    last_mihomo_ts: float = 0.0
    recent_event_counts: dict[str, int] = field(default_factory=dict)
    recent_cancel_by_client: dict[str, int] = field(default_factory=dict)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _fetch_events(conn: sqlite3.Connection, after_id: int, *, batch_size: int = 5000) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT id, job_id, ts, type, payload_json FROM job_events WHERE id > ? ORDER BY id ASC LIMIT ?", (after_id, batch_size)).fetchall())


def _jobs_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status ORDER BY n DESC").fetchall()
    return {str(r["status"]): int(r["n"]) for r in rows}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Monitor ChatgptREST job events and write structured logs (JSONL).")
    ap.add_argument("--db", default=os.environ.get("CHATGPTREST_DB_PATH") or "state/jobdb.sqlite3")
    ap.add_argument("--out", default="", help="Output jsonl (default: artifacts/monitor/<ts>.jsonl)")
    ap.add_argument("--duration-seconds", type=int, default=0, help="0 = run forever (until SIGINT).")
    ap.add_argument("--poll-seconds", type=float, default=2.0)
    ap.add_argument("--summary-every-seconds", type=int, default=60)
    default_blocked = os.environ.get("CHATGPT_BLOCKED_STATE_FILE") or os.environ.get("CHATGPTREST_BLOCKED_STATE_FILE")
    if not default_blocked:
        repo_root = Path(__file__).resolve().parents[1]
        state_driver = (repo_root / "state" / "driver" / "chatgpt_blocked_state.json").resolve()
        if state_driver.parent.exists():
            default_blocked = str(state_driver)
        else:
            default_blocked = str((repo_root / ".run/chatgpt_blocked_state.json").resolve())
    ap.add_argument(
        "--chatgptmcp-state-file",
        default=default_blocked,
        help="Optional: read chatgptMCP blocked_state file for correlation.",
    )
    ap.add_argument("--blocked-state-every-seconds", type=int, default=120)
    ap.add_argument(
        "--mihomo-delay-log-dir",
        default=os.environ.get("MIHOMO_DELAY_LOG_DIR") or "artifacts/monitor/mihomo_delay",
        help="Directory containing mihomo_delay_YYYYMMDD.jsonl (default: artifacts/monitor/mihomo_delay).",
    )
    ap.add_argument("--mihomo-delay-every-seconds", type=int, default=300)
    args = ap.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    db_path = Path(str(args.db)).expanduser()
    if not db_path.is_absolute():
        db_path = (repo_root / db_path).resolve(strict=False)
    if not db_path.exists():
        raise SystemExit(f"db not found: {db_path}")

    out_path_raw = str(args.out).strip()
    if out_path_raw:
        out_path = Path(out_path_raw).expanduser()
        if not out_path.is_absolute():
            out_path = (repo_root / out_path).resolve(strict=False)
    else:
        out_path = (repo_root / "artifacts" / "monitor" / f"monitor_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}Z.jsonl").resolve(strict=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    chatgptmcp_state_path = Path(str(args.chatgptmcp_state_file)).expanduser()
    legacy_state_path = (repo_root / "../chatgptMCP/.run/chatgpt_blocked_state.json").resolve()
    mihomo_delay_dir = Path(str(args.mihomo_delay_log_dir)).expanduser()
    if not mihomo_delay_dir.is_absolute():
        mihomo_delay_dir = (repo_root / mihomo_delay_dir).resolve(strict=False)

    state = MonitorState()
    started = time.time()
    deadline = None if int(args.duration_seconds) <= 0 else (started + float(max(1, int(args.duration_seconds))))

    # ---- resume from previous run -------------------------------------------
    # Without this, every fresh start replays ALL historical events from event 0
    # which can be 700K+ events / 230MB+, causing timer-triggered runs to timeout.
    # Strategy: read the last event_id from the output file (if appending) or
    # from the most recent sibling JSONL in the same directory.
    resume_sources: list[Path] = []
    if out_path.exists() and out_path.stat().st_size > 0:
        resume_sources.append(out_path)
    else:
        # Look for the most recent sibling JSONL in the same directory
        try:
            siblings = sorted(
                (p for p in out_path.parent.glob("monitor_12h_*.jsonl") if p.stat().st_size > 0),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if siblings:
                resume_sources.append(siblings[0])
        except Exception:
            pass
    for src in resume_sources:
        last_rec = _tail_last_jsonl(src)
        if last_rec and isinstance(last_rec, dict):
            eid = last_rec.get("event_id")
            if eid is not None:
                state.last_event_id = int(eid)
                break
    # ---- end resume ---------------------------------------------------------

    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now_iso(), "type": "monitor_started", "db": str(db_path),
                             "resumed_from_event_id": state.last_event_id}, ensure_ascii=False) + "\n")
        f.flush()

        while deadline is None or time.time() < deadline:
            time.sleep(max(0.2, float(args.poll_seconds)))
            try:
                conn = _connect(db_path)
            except Exception as exc:
                f.write(json.dumps({"ts": _now_iso(), "type": "db_connect_error", "error": str(exc)}, ensure_ascii=False) + "\n")
                f.flush()
                continue
            try:
                events = _fetch_events(conn, state.last_event_id)
                for row in events:
                    payload_raw = row["payload_json"]
                    payload = None
                    if payload_raw:
                        try:
                            payload = json.loads(str(payload_raw))
                        except Exception:
                            payload = {"_raw": str(payload_raw)}
                    line = {
                        "ts": _now_iso(),
                        "type": "job_event",
                        "event_id": int(row["id"]),
                        "job_id": str(row["job_id"]),
                        "event_ts": float(row["ts"]),
                        "event_type": str(row["type"]),
                        "payload": payload,
                    }
                    f.write(json.dumps(line, ensure_ascii=False) + "\n")
                    state.last_event_id = int(row["id"])
                    et = str(row["type"])
                    state.recent_event_counts[et] = int(state.recent_event_counts.get(et, 0)) + 1
                    if et == "cancel_requested" and isinstance(payload, dict):
                        by = payload.get("by")
                        headers = by.get("headers") if isinstance(by, dict) else None
                        x_client_name = str((headers or {}).get("x_client_name") or "").strip().lower()
                        if x_client_name:
                            state.recent_cancel_by_client[x_client_name] = int(
                                state.recent_cancel_by_client.get(x_client_name, 0)
                            ) + 1

                now = time.time()
                if now - state.last_summary_ts >= float(max(5, int(args.summary_every_seconds))):
                    summary = _jobs_summary(conn)
                    payload = {
                        "ts": _now_iso(),
                        "type": "jobs_summary",
                        "summary": summary,
                        "recent_event_counts": dict(sorted(state.recent_event_counts.items())),
                    }
                    if state.recent_cancel_by_client:
                        payload["recent_cancel_by_client"] = dict(sorted(state.recent_cancel_by_client.items()))
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                    state.last_summary_ts = now
                    state.recent_event_counts = {}
                    state.recent_cancel_by_client = {}

                if now - state.last_blocked_state_ts >= float(max(10, int(args.blocked_state_every_seconds))):
                    bs = _read_json(chatgptmcp_state_path) if chatgptmcp_state_path.exists() else None
                    if bs is None and legacy_state_path.exists():
                        bs = _read_json(legacy_state_path)
                    if bs is not None:
                        blocked_until = float(bs.get("blocked_until") or 0.0)
                        blocked = bool(blocked_until and blocked_until > time.time())
                        f.write(
                            json.dumps(
                                {
                                    "ts": _now_iso(),
                                    "type": "chatgptmcp_blocked_state",
                                    "blocked": blocked,
                                    "blocked_until": blocked_until,
                                    "reason": bs.get("reason"),
                                    "phase": bs.get("phase"),
                                    "url": bs.get("url"),
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                    state.last_blocked_state_ts = now

                if now - state.last_mihomo_ts >= float(max(30, int(args.mihomo_delay_every_seconds))):
                    day = datetime.now(UTC).strftime("%Y%m%d")
                    path = mihomo_delay_dir / f"mihomo_delay_{day}.jsonl"
                    rec = _tail_last_jsonl(path)
                    if rec is not None:
                        f.write(json.dumps({"ts": _now_iso(), "type": "mihomo_delay_last", "path": str(path), "record": rec}, ensure_ascii=False) + "\n")
                    state.last_mihomo_ts = now

                f.flush()
            finally:
                conn.close()

        if deadline is not None:
            f.write(json.dumps({"ts": _now_iso(), "type": "monitor_finished"}, ensure_ascii=False) + "\n")
            f.flush()

    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
