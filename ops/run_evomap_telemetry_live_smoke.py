#!/usr/bin/env python3
"""Run a live telemetry -> EvoMap smoke check against the local runtime."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def build_payload(
    *,
    trace_id: str,
    session_id: str,
    event_id: str,
    task_ref: str,
    source: str,
    agent_name: str,
    artifact_path: str,
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "session_key": session_id,
        "events": [
            {
                "type": "team.run.completed",
                "source": source,
                "domain": "execution",
                "event_id": event_id,
                "task_ref": task_ref,
                "repo_name": "ChatgptREST",
                "repo_path": "/vol1/1000/projects/ChatgptREST",
                "repo_branch": "master",
                "agent_name": agent_name,
                "provider": "openai",
                "model": "gpt-5",
                "data": {
                    "status": "completed",
                    "summary": "live telemetry P0 smoke",
                    "artifact_path": artifact_path,
                },
            }
        ],
    }


def post_telemetry(
    *,
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    max_attempts: int = 2,
    retry_sleep_seconds: float = 1.0,
) -> dict[str, Any]:
    attempts = max(1, int(max_attempts))
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/v2/telemetry/ingest",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt >= attempts:
                raise
            time.sleep(max(0.0, float(retry_sleep_seconds)))
    assert last_exc is not None
    raise last_exc


def matching_activity_atoms(db_path: str, *, event_id: str) -> list[dict[str, str]]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT a.atom_id, e.source_ext
            FROM atoms a
            JOIN episodes e ON e.episode_id = a.episode_id
            WHERE a.canonical_question = 'activity: team.run.completed'
              AND e.source_ext LIKE ?
            ORDER BY a.atom_id DESC
            """,
            (f"%{event_id}%",),
        ).fetchall()
        matches: list[dict[str, str]] = []
        for atom_id, source_ext in rows:
            source = json.loads(source_ext or "{}")
            if source.get("event_id") == event_id or source.get("upstream_event_id") == event_id:
                matches.append(
                    {
                        "atom_id": atom_id,
                        "event_id": str(source.get("event_id") or ""),
                        "upstream_event_id": str(source.get("upstream_event_id") or ""),
                    }
                )
        return matches
    finally:
        conn.close()


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        raise SystemExit(f"missing API key in env var {args.api_key_env}")

    payload = build_payload(
        trace_id=args.trace_id,
        session_id=args.session_id,
        event_id=args.event_id,
        task_ref=args.task_ref,
        source=args.source,
        agent_name=args.agent_name,
        artifact_path=args.artifact_path,
    )

    before = matching_activity_atoms(args.db_path, event_id=args.event_id)
    responses: list[dict[str, Any]] = []
    for _ in range(args.replay_count):
        responses.append(
            post_telemetry(
                base_url=args.base_url,
                api_key=api_key,
                payload=payload,
                timeout_seconds=args.http_timeout_seconds,
                max_attempts=args.max_attempts,
                retry_sleep_seconds=args.retry_sleep_seconds,
            )
        )
        time.sleep(args.settle_seconds)

    deadline = time.time() + max(args.visibility_timeout_seconds, 0.0)
    after = matching_activity_atoms(args.db_path, event_id=args.event_id)
    dedup_ok = len(after) == 1 if args.expect_dedup else len(after) >= 1
    while not dedup_ok and time.time() < deadline:
        time.sleep(args.poll_interval_seconds)
        after = matching_activity_atoms(args.db_path, event_id=args.event_id)
        dedup_ok = len(after) == 1 if args.expect_dedup else len(after) >= 1
    report = {
        "ok": dedup_ok,
        "base_url": args.base_url,
        "db_path": args.db_path,
        "trace_id": args.trace_id,
        "session_id": args.session_id,
        "event_id": args.event_id,
        "replay_count": args.replay_count,
        "responses": responses,
        "before_match_count": len(before),
        "after_match_count": len(after),
        "matching_atoms": after,
        "dedup_ok": dedup_ok,
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18711")
    parser.add_argument("--db-path", default="data/evomap_knowledge.db")
    parser.add_argument("--api-key-env", default="OPENMIND_API_KEY")
    parser.add_argument("--trace-id", default="tr-evomap-telemetry-live-smoke")
    parser.add_argument("--session-id", default="sess-evomap-telemetry-live-smoke")
    parser.add_argument("--event-id", default=f"telemetry-live-{int(time.time())}")
    parser.add_argument("--task-ref", default="telemetry-p0/live-smoke")
    parser.add_argument("--source", default="codex")
    parser.add_argument("--agent-name", default="codex")
    parser.add_argument(
        "--artifact-path",
        default="docs/dev_log/2026-03-11_evomap_live_smoke_results.md",
    )
    parser.add_argument("--replay-count", type=int, default=2)
    parser.add_argument("--settle-seconds", type=float, default=0.2)
    parser.add_argument("--http-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--visibility-timeout-seconds", type=float, default=35.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=0.5)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--retry-sleep-seconds", type=float, default=1.0)
    parser.add_argument("--expect-dedup", action="store_true")
    parser.add_argument("--report-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_smoke(args)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        report = {
            "ok": False,
            "http_status": exc.code,
            "error": body,
            "event_id": args.event_id,
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        report = {
            "ok": False,
            "error": str(exc),
            "error_type": type(exc).__name__,
            "event_id": args.event_id,
        }
    if args.report_json:
        Path(args.report_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
