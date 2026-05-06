#!/usr/bin/env python3
"""Run a live OpenClaw telemetry plugin -> EvoMap smoke check."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


def expected_task_ref(*, session_id: str, agent_id: str = "main", prefix: str = "openclaw") -> str:
    digest = hashlib.sha1(session_id.encode("utf-8")).hexdigest()
    return f"{prefix}:{agent_id}:{digest}"


def task_ref_candidates(*, session_ids: list[str], agent_id: str = "main", prefix: str = "openclaw") -> list[str]:
    seen: set[str] = set()
    refs: list[str] = []
    for session_id in session_ids:
        value = str(session_id or "").strip()
        if not value:
            continue
        ref = expected_task_ref(session_id=value, agent_id=agent_id, prefix=prefix)
        if ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
    return refs


def latest_openclaw_activity_rowid(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT COALESCE(MAX(a.rowid), 0)
            FROM atoms a
            JOIN episodes e ON e.episode_id = a.episode_id
            WHERE a.canonical_question IN ('activity: team.run.created', 'activity: workflow.completed', 'activity: workflow.failed')
            """
        ).fetchone()
        return int((row or [0])[0] or 0)
    finally:
        conn.close()


def matching_openclaw_activity_atoms(
    db_path: str,
    *,
    task_refs: list[str],
    session_ids: list[str],
    min_rowid: int = 0,
) -> list[dict[str, str]]:
    task_ref_set = {str(item).strip() for item in task_refs if str(item).strip()}
    session_id_set = {str(item).strip() for item in session_ids if str(item).strip()}
    if not task_ref_set and not session_id_set:
        return []
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT a.rowid, a.atom_id, a.canonical_question, e.source_ext
            FROM atoms a
            JOIN episodes e ON e.episode_id = a.episode_id
            WHERE a.canonical_question IN ('activity: team.run.created', 'activity: workflow.completed', 'activity: workflow.failed')
              AND a.rowid > ?
            ORDER BY a.atom_id ASC
            """,
            (min_rowid,),
        ).fetchall()
        matches: list[dict[str, str]] = []
        for rowid, atom_id, canonical_question, source_ext in rows:
            source = json.loads(source_ext or "{}")
            task_ref = str(source.get("task_ref") or "").strip()
            session_id = str(source.get("session_id") or "").strip()
            if task_ref_set and task_ref in task_ref_set:
                pass
            elif session_id_set and session_id in session_id_set:
                pass
            else:
                continue
            matches.append(
                {
                    "rowid": str(rowid),
                    "atom_id": str(atom_id),
                    "canonical_question": str(canonical_question),
                    "task_ref": task_ref,
                    "event_id": str(source.get("event_id") or ""),
                    "session_id": session_id,
                }
            )
        return matches
    finally:
        conn.close()


def latest_matching_run_start_rowid(
    db_path: str,
    *,
    task_refs: list[str],
    session_ids: list[str],
    max_rowid: int = 0,
) -> int:
    matches = matching_openclaw_activity_atoms(
        db_path,
        task_refs=task_refs,
        session_ids=session_ids,
        min_rowid=0,
    )
    created_rows = [
        int(item["rowid"])
        for item in matches
        if item["canonical_question"] == "activity: team.run.created"
        and int(item["rowid"]) <= int(max_rowid)
    ]
    return max(created_rows) if created_rows else 0


def evaluate_coverage(
    *,
    db_path: str,
    after: list[dict[str, str]],
    task_refs: list[str],
    session_ids: list[str],
    before_rowid: int,
    created_lookback_rows: int,
) -> dict[str, Any]:
    seen = {item["canonical_question"] for item in after}
    completion_seen = bool({"activity: workflow.completed", "activity: workflow.failed"} & seen)
    fresh_created_seen = "activity: team.run.created" in seen
    prior_created_rowid = latest_matching_run_start_rowid(
        db_path,
        task_refs=task_refs,
        session_ids=session_ids,
        max_rowid=before_rowid,
    )
    recent_threshold = max(0, int(before_rowid) - max(1, int(created_lookback_rows)))
    reused_recent_created = bool(
        completion_seen
        and not fresh_created_seen
        and prior_created_rowid >= recent_threshold
    )
    coverage_ok = bool(completion_seen and (fresh_created_seen or reused_recent_created))
    return {
        "coverage_ok": coverage_ok,
        "fresh_created_seen": fresh_created_seen,
        "completion_seen": completion_seen,
        "prior_created_rowid": prior_created_rowid,
        "created_reused_from_recent_history": reused_recent_created,
        "seen_questions": sorted(seen),
    }


def run_agent(*, openclaw_bin: str, session_id: str, expected_reply: str, timeout_seconds: int) -> dict[str, Any]:
    cmd = [
        openclaw_bin,
        "agent",
        "--agent",
        "main",
        "--session-id",
        session_id,
        "--message",
        (
            "You have the openmind_telemetry_flush tool available. "
            "You must call it exactly once before answering. "
            f"Then reply exactly {expected_reply}."
        ),
        "--json",
        "--timeout",
        str(timeout_seconds),
    ]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 20,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
        }


def extract_reply(stdout: str) -> str:
    payload = json.loads(stdout)
    payloads = ((payload.get("result") or {}).get("payloads")) or []
    if not payloads:
        return ""
    return str((payloads[0] or {}).get("text") or "")


def extract_session_candidates(stdout: str, *, requested_session_id: str) -> list[str]:
    candidates = [requested_session_id]
    try:
        payload = json.loads(stdout)
    except Exception:
        return candidates
    result = payload.get("result") or {}
    meta = result.get("meta") or {}
    agent_meta = meta.get("agentMeta") or {}
    system_prompt_report = meta.get("systemPromptReport") or {}
    for key in (agent_meta.get("sessionId"), system_prompt_report.get("sessionId"), system_prompt_report.get("sessionKey")):
        value = str(key or "").strip()
        if value and value not in candidates:
            candidates.append(value)
    return candidates


def poll_for_atoms(
    *,
    db_path: str,
    task_refs: list[str],
    session_ids: list[str],
    min_rowid: int,
    timeout_seconds: float,
    poll_seconds: float,
) -> list[dict[str, str]]:
    deadline = time.time() + timeout_seconds
    latest: list[dict[str, str]] = []
    while time.time() < deadline:
        latest = matching_openclaw_activity_atoms(
            db_path,
            task_refs=task_refs,
            session_ids=session_ids,
            min_rowid=min_rowid,
        )
        seen = {item["canonical_question"] for item in latest}
        if "activity: team.run.created" in seen and bool({"activity: workflow.completed", "activity: workflow.failed"} & seen):
            return latest
        time.sleep(poll_seconds)
    return latest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openclaw-bin", default="openclaw")
    parser.add_argument("--db-path", default="data/evomap_knowledge.db")
    parser.add_argument("--session-id", default=f"evomap-plugin-smoke-{uuid.uuid4().hex[:12]}")
    parser.add_argument("--task-ref-prefix", default="openclaw")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--poll-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--created-lookback-rows", type=int, default=25)
    parser.add_argument("--report-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = uuid.uuid4().hex[:12]
    expected_reply = f"OPENCLAW_TELEMETRY_OK {token}"
    before_rowid = latest_openclaw_activity_rowid(args.db_path)
    initial_session_ids = [args.session_id]
    initial_task_refs = task_ref_candidates(session_ids=initial_session_ids, prefix=args.task_ref_prefix)
    before = matching_openclaw_activity_atoms(
        args.db_path,
        task_refs=initial_task_refs,
        session_ids=initial_session_ids,
        min_rowid=before_rowid,
    )
    run = run_agent(
        openclaw_bin=args.openclaw_bin,
        session_id=args.session_id,
        expected_reply=expected_reply,
        timeout_seconds=args.timeout_seconds,
    )
    reply = extract_reply(run["stdout"]) if run["returncode"] == 0 and run["stdout"] else ""
    observed_session_ids = extract_session_candidates(run.get("stdout") or "", requested_session_id=args.session_id)
    observed_task_refs = task_ref_candidates(session_ids=observed_session_ids, prefix=args.task_ref_prefix)
    after = poll_for_atoms(
        db_path=args.db_path,
        task_refs=observed_task_refs,
        session_ids=observed_session_ids,
        min_rowid=before_rowid,
        timeout_seconds=args.poll_timeout_seconds,
        poll_seconds=args.poll_seconds,
    )
    coverage = evaluate_coverage(
        db_path=args.db_path,
        after=after,
        task_refs=observed_task_refs,
        session_ids=observed_session_ids,
        before_rowid=before_rowid,
        created_lookback_rows=args.created_lookback_rows,
    )
    coverage_ok = bool(coverage["coverage_ok"])
    agent_run_ok = run["returncode"] == 0 and reply.strip() == expected_reply
    report = {
        "ok": coverage_ok,
        "coverage_ok": coverage_ok,
        "agent_run_ok": agent_run_ok,
        "session_id": args.session_id,
        "session_ids_observed": observed_session_ids,
        "task_refs_observed": observed_task_refs,
        "expected_reply": expected_reply,
        "reply": reply,
        "before_match_count": len(before),
        "before_rowid": before_rowid,
        "after_match_count": len(after),
        "matching_atoms": after,
        **coverage,
        "run": run,
    }
    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
