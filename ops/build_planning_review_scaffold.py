#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.evomap.knowledge.planning_review_plane import default_db_path
from ops.build_planning_review_priority_bundle import build_priority_queue


FIELDNAMES = [
    "doc_id",
    "title",
    "raw_ref",
    "family_id",
    "review_domain",
    "source_bucket",
    "document_role",
    "priority_score",
    "priority_reason",
    "suggested_bucket",
    "final_bucket",
    "reviewer",
    "review_notes",
]


def build_scaffold(*, db_path: str | Path, output_tsv: str | Path, limit: int = 100) -> dict[str, Any]:
    report = build_priority_queue(db_path=db_path, limit=limit)
    out = Path(output_tsv)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = [
        {
            "doc_id": row["doc_id"],
            "title": row["title"],
            "raw_ref": row["raw_ref"],
            "family_id": row["family_id"],
            "review_domain": row["review_domain"],
            "source_bucket": row["source_bucket"],
            "document_role": row["document_role"],
            "priority_score": row["priority_score"],
            "priority_reason": row["priority_reason"],
            "suggested_bucket": "",
            "final_bucket": "",
            "reviewer": "",
            "review_notes": "",
        }
        for row in report["rows"]
    ]

    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "ok": True,
        "db_path": str(db_path),
        "output_tsv": str(out),
        "selected_docs": len(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a TSV review scaffold for the planning priority review queue.")
    parser.add_argument("--db", default=default_db_path())
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    result = build_scaffold(db_path=args.db, output_tsv=args.output_tsv, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
