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

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from ops.build_execution_activity_lineage_registry import build_lineage_registry
from ops.export_execution_activity_review_queue import build_review_queue


FIELDNAMES = [
    "atom_id",
    "lineage_family_id",
    "lineage_status",
    "lineage_action",
    "family_atom_count",
    "family_trace_count",
    "source",
    "episode_type",
    "atom_type",
    "task_ref",
    "trace_id",
    "canonical_question",
    "answer_preview",
    "suggested_bucket",
    "final_bucket",
    "experience_kind",
    "experience_title",
    "experience_summary",
    "reviewer",
    "review_notes",
]


def build_scaffold(*, db_path: str | Path, output_tsv: str | Path, limit: int = 1000) -> dict[str, Any]:
    report = build_review_queue(db_path=db_path, limit=limit)
    lineage = build_lineage_registry(db_path=db_path, limit=limit)
    family_lookup = {
        row["lineage_family_id"]: row
        for row in lineage["families"]
    }
    atom_lookup = {
        row["atom_id"]: row
        for row in lineage["atoms"]
    }
    out = Path(output_tsv)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = [
        {
            "atom_id": row["atom_id"],
            "lineage_family_id": atom_lookup.get(row["atom_id"], {}).get("lineage_family_id", ""),
            "lineage_status": atom_lookup.get(row["atom_id"], {}).get("lineage_status", ""),
            "lineage_action": atom_lookup.get(row["atom_id"], {}).get("lineage_action", ""),
            "family_atom_count": family_lookup.get(atom_lookup.get(row["atom_id"], {}).get("lineage_family_id", ""), {}).get(
                "atom_count", 0
            ),
            "family_trace_count": family_lookup.get(atom_lookup.get(row["atom_id"], {}).get("lineage_family_id", ""), {}).get(
                "trace_count", 0
            ),
            "source": row["source"],
            "episode_type": row["episode_type"],
            "atom_type": row["atom_type"],
            "task_ref": row["task_ref"],
            "trace_id": row["trace_id"],
            "canonical_question": row["canonical_question"],
            "answer_preview": row["answer_preview"],
            "suggested_bucket": atom_lookup.get(row["atom_id"], {}).get("suggested_bucket", ""),
            "final_bucket": "",
            "experience_kind": "",
            "experience_title": "",
            "experience_summary": "",
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
        "selected_atoms": len(rows),
        "lineage_families": lineage["summary"]["lineage_families"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a TSV review scaffold for the lineage-ready execution activity queue."
    )
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    result = build_scaffold(db_path=args.db, output_tsv=args.output_tsv, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
