#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def build_review_queue(*, db_path: str | Path, limit: int = 1000) -> dict[str, Any]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
              a.atom_id,
              a.atom_type,
              a.status,
              a.promotion_status,
              a.canonical_question,
              a.answer,
              a.valid_from,
              d.source,
              e.episode_type,
              json_extract(a.applicability, '$.task_ref') AS task_ref,
              json_extract(a.applicability, '$.trace_id') AS trace_id,
              json_extract(a.applicability, '$.lane_id') AS lane_id,
              json_extract(a.applicability, '$.role_id') AS role_id,
              json_extract(a.applicability, '$.adapter_id') AS adapter_id,
              json_extract(a.applicability, '$.profile_id') AS profile_id,
              json_extract(a.applicability, '$.executor_kind') AS executor_kind
            FROM atoms a
            JOIN episodes e ON e.episode_id = a.episode_id
            JOIN documents d ON d.doc_id = e.doc_id
            WHERE a.promotion_reason = 'activity_ingest'
              AND a.promotion_status = 'staged'
              AND COALESCE(a.canonical_question, '') != ''
              AND COALESCE(json_extract(a.applicability, '$.task_ref'), '') != ''
              AND COALESCE(json_extract(a.applicability, '$.trace_id'), '') != ''
            ORDER BY a.valid_from DESC, a.atom_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    queue_rows = [
        {
            "atom_id": str(row["atom_id"]),
            "source": str(row["source"] or ""),
            "episode_type": str(row["episode_type"] or ""),
            "atom_type": str(row["atom_type"] or ""),
            "status": str(row["status"] or ""),
            "promotion_status": str(row["promotion_status"] or ""),
            "task_ref": str(row["task_ref"] or ""),
            "trace_id": str(row["trace_id"] or ""),
            "lane_id": str(row["lane_id"] or ""),
            "role_id": str(row["role_id"] or ""),
            "adapter_id": str(row["adapter_id"] or ""),
            "profile_id": str(row["profile_id"] or ""),
            "executor_kind": str(row["executor_kind"] or ""),
            "canonical_question": str(row["canonical_question"] or ""),
            "answer_preview": str(row["answer"] or "")[:200],
            "valid_from": float(row["valid_from"] or 0.0),
        }
        for row in rows
    ]

    summary = {
        "db_path": str(db_path),
        "selected_atoms": len(queue_rows),
        "sources": {},
        "episode_types": {},
        "atom_types": {},
        "rows": queue_rows,
    }
    for key in ("source", "episode_type", "atom_type"):
        counts: dict[str, int] = {}
        for row in queue_rows:
            counts[row[key]] = counts.get(row[key], 0) + 1
        summary[f"{key}s" if not key.endswith("s") else key] = counts
    return summary


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "atom_id",
        "source",
        "episode_type",
        "atom_type",
        "status",
        "promotion_status",
        "task_ref",
        "trace_id",
        "lane_id",
        "role_id",
        "adapter_id",
        "profile_id",
        "executor_kind",
        "canonical_question",
        "answer_preview",
        "valid_from",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a narrow review queue from staged execution-activity atoms."
    )
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-tsv", default="")
    args = parser.parse_args()

    report = build_review_queue(db_path=args.db, limit=args.limit)
    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.output_tsv:
        _write_tsv(Path(args.output_tsv), report["rows"])
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
