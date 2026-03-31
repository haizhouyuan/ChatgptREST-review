#!/usr/bin/env python3
"""Compare live ingest and archive extractor execution-extension parity."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from chatgptrest.evomap.activity_ingest import ActivityIngestService
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.extractors.activity_extractor import ActivityExtractor


def _archive_closeout() -> dict[str, Any]:
    return {
        "event_type": "agent.task.closeout",
        "ts": "2026-03-11T18:00:00+08:00",
        "source": "workflow/closeout",
        "trace_id": "trace-parity-1",
        "task_ref": "issue-115:parity",
        "repo": {
            "path": "/vol1/1000/projects/ChatgptREST",
            "name": "ChatgptREST",
            "branch": "master",
            "head": "abc123def4567890",
        },
        "agent": {"name": "main", "source": "controller_lane_wrapper"},
        "lane_id": "main",
        "role_id": "devops",
        "adapter_id": "controller_lane_wrapper",
        "profile_id": "mainline_runtime",
        "executor_kind": "codex.controller",
        "closeout": {
            "status": "completed",
            "summary": "Parity smoke closeout.",
        },
    }


def _live_payload() -> dict[str, Any]:
    return {
        "event_type": "team.run.completed",
        "source": "controller_lane_wrapper",
        "trace_id": "trace-parity-1",
        "session_id": "session-parity-1",
        "event_id": "run-parity-1:completed",
        "upstream_event_id": "run-parity-1:completed",
        "run_id": "run-parity-1",
        "task_ref": "issue-115:parity",
        "repo_name": "ChatgptREST",
        "repo_path": "/vol1/1000/projects/ChatgptREST",
        "agent_name": "main",
        "agent_source": "controller_lane_wrapper",
        "provider": "openai",
        "model": "gpt-5",
        "lane_id": "main",
        "role_id": "devops",
        "adapter_id": "controller_lane_wrapper",
        "profile_id": "mainline_runtime",
        "executor_kind": "codex.controller",
    }


def _projection(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "task_ref",
        "trace_id",
        "lane_id",
        "role_id",
        "adapter_id",
        "profile_id",
        "executor_kind",
    )
    return {key: payload.get(key) for key in keys if payload.get(key) not in (None, "")}


def run_smoke() -> dict[str, Any]:
    archive_event = _archive_closeout()
    live_payload = _live_payload()
    expected = _projection(live_payload)

    with tempfile.TemporaryDirectory(prefix="execution-parity-") as tmpdir:
        tmp = Path(tmpdir)
        archive_path = tmp / "agent_activity_events_2026-03-11.jsonl"
        archive_path.write_text(json.dumps(archive_event, ensure_ascii=False) + "\n", encoding="utf-8")

        archive_db = KnowledgeDB(str(tmp / "archive.db"))
        archive_db.init_schema()
        try:
            archive_stats = ActivityExtractor(archive_db, event_dirs=[str(tmp)]).extract_all()
            archive_conn = archive_db.connect()
            archive_row = archive_conn.execute(
                """
                SELECT applicability
                FROM atoms
                WHERE canonical_question LIKE 'task result:%'
                LIMIT 1
                """
            ).fetchone()
            archive_applicability = json.loads(archive_row[0] or "{}")
        finally:
            archive_db.close()

        live_db = KnowledgeDB(str(tmp / "live.db"))
        live_db.init_schema()
        try:
            service = ActivityIngestService(db=live_db, observer=None)
            result = service.ingest_activity_event(live_payload)
            live_conn = live_db.connect()
            live_row = live_conn.execute(
                """
                SELECT applicability
                FROM atoms
                WHERE canonical_question = 'activity: team.run.completed'
                LIMIT 1
                """
            ).fetchone()
            live_applicability = json.loads(live_row[0] or "{}")
        finally:
            live_db.close()

    return {
        "ok": archive_stats.atoms_created == 1 and result.ok is True,
        "expected": expected,
        "plane_local": {
            "archive_source": archive_event["source"],
            "live_source": live_payload["source"],
        },
        "archive_applicability": archive_applicability,
        "live_applicability": live_applicability,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_smoke()
    if args.report_json:
        out = Path(args.report_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
