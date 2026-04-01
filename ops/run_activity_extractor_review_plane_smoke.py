#!/usr/bin/env python3
"""Run a local review-plane smoke for ActivityExtractor."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.extractors.activity_extractor import ActivityExtractor


def _sample_closeout() -> dict[str, Any]:
    return {
        "event_type": "agent.task.closeout",
        "ts": "2026-03-11T12:00:00+08:00",
        "source": "workflow/closeout",
        "trace_id": "trace-review-plane-closeout",
        "task_ref": "issue-114:activity-review-plane",
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
            "summary": "Validated activity review-plane extraction smoke.",
        },
    }


def _sample_commit() -> dict[str, Any]:
    return {
        "event_type": "agent.git.commit",
        "ts": "2026-03-11T12:02:00+08:00",
        "source": "workflow/git-hook",
        "trace_id": "trace-review-plane-commit",
        "task_ref": "issue-114:activity-review-plane",
        "repo": {
            "path": "/vol1/1000/projects/ChatgptREST",
            "name": "ChatgptREST",
            "branch": "master",
            "head": "def456abc7891234",
        },
        "agent": {"name": "main", "source": "controller_lane_wrapper"},
        "lane_id": "main",
        "role_id": "devops",
        "adapter_id": "controller_lane_wrapper",
        "profile_id": "mainline_runtime",
        "executor_kind": "codex.controller",
        "commit": {
            "commit": "def456abc7891234beef",
            "subject": "test: validate activity extractor review plane smoke",
            "files_changed": 2,
            "touched_paths_preview": [
                "ops/run_activity_extractor_review_plane_smoke.py",
                "tests/test_activity_extractor_review_plane_smoke.py",
            ],
        },
    }


def run_smoke() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="activity-review-plane-") as tmpdir:
        tmp = Path(tmpdir)
        jsonl_path = tmp / "agent_activity_events_2026-03-11.jsonl"
        db_path = tmp / "evomap_review_plane.db"

        events = [_sample_closeout(), _sample_commit()]
        with jsonl_path.open("w", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")

        db = KnowledgeDB(db_path=str(db_path))
        db.connect()
        db.init_schema()
        try:
            stats = ActivityExtractor(db, event_dirs=[str(tmp)]).extract_all()

            conn = db.connect()
            atom_rows = conn.execute(
                """
                SELECT canonical_question, promotion_status, status, applicability
                FROM atoms
                ORDER BY canonical_question
                """
            ).fetchall()
            episode_rows = conn.execute(
                """
                SELECT episode_type, source_ext
                FROM episodes
                ORDER BY episode_type
                """
            ).fetchall()
        finally:
            db.close()

    atom_details = [
        {
            "canonical_question": str(row[0]),
            "promotion_status": str(row[1]),
            "status": str(row[2]),
            "applicability": json.loads(row[3] or "{}"),
        }
        for row in atom_rows
    ]
    episode_details = [
        {
            "episode_type": str(row[0]),
            "source_ext": json.loads(row[1] or "{}"),
        }
        for row in episode_rows
    ]
    return {
        "ok": stats.atoms_created == 2 and len(atom_details) == 2,
        "stats": {
            "files_processed": stats.files_processed,
            "events_read": stats.events_read,
            "atoms_created": stats.atoms_created,
            "atoms_skipped": stats.atoms_skipped,
            "duplicates": stats.duplicates,
        },
        "atoms": atom_details,
        "episodes": episode_details,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_smoke()
    if args.report_json:
        path = Path(args.report_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
