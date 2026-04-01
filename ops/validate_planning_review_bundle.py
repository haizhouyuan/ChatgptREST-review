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


REQUIRED_FILES = [
    "review_queue.json",
    "review_queue.tsv",
    "summary.json",
    "README.md",
    "review_decisions_template.tsv",
]

QUEUE_FIELDS = [
    "doc_id",
    "title",
    "raw_ref",
    "family_id",
    "review_domain",
    "source_bucket",
    "document_role",
    "is_latest_output",
    "priority_score",
    "priority_reason",
]

SCAFFOLD_FIELDS = [
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


def _read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return fieldnames, rows


def validate_bundle(*, bundle_dir: str | Path) -> dict[str, Any]:
    bundle = Path(bundle_dir)
    missing = [name for name in REQUIRED_FILES if not (bundle / name).exists()]
    if missing:
        return {
            "ok": False,
            "bundle_dir": str(bundle),
            "missing_files": missing,
            "checks": {"required_files_ok": False},
        }

    queue_json = json.loads((bundle / "review_queue.json").read_text(encoding="utf-8"))
    summary = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
    queue_fields, queue_rows = _read_tsv(bundle / "review_queue.tsv")
    scaffold_fields, scaffold_rows = _read_tsv(bundle / "review_decisions_template.tsv")

    queue_doc_ids_json = [str(row["doc_id"]) for row in queue_json.get("rows", [])]
    queue_doc_ids_tsv = [str(row["doc_id"]) for row in queue_rows]
    scaffold_doc_ids = [str(row["doc_id"]) for row in scaffold_rows]

    checks = {
        "required_files_ok": True,
        "queue_fields_ok": queue_fields == QUEUE_FIELDS,
        "scaffold_fields_ok": scaffold_fields == SCAFFOLD_FIELDS,
        "queue_json_count_matches_summary_ok": int(queue_json.get("selected_docs", 0)) == int(summary.get("selected_docs", 0)),
        "queue_tsv_count_matches_summary_ok": len(queue_rows) == int(summary.get("selected_docs", 0)),
        "scaffold_count_matches_summary_ok": len(scaffold_rows) == int(summary.get("selected_docs", 0)),
        "queue_json_tsv_doc_ids_match_ok": queue_doc_ids_json == queue_doc_ids_tsv,
        "queue_tsv_scaffold_doc_ids_match_ok": queue_doc_ids_tsv == scaffold_doc_ids,
    }

    return {
        "ok": all(checks.values()),
        "bundle_dir": str(bundle),
        "missing_files": [],
        "selected_docs": int(summary.get("selected_docs", 0)),
        "candidate_pool_docs": int(summary.get("candidate_pool_docs", 0)),
        "checks": checks,
        "queue_doc_ids": queue_doc_ids_tsv[:10],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate planning review priority bundle artifacts and internal consistency.")
    parser.add_argument("--bundle-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(validate_bundle(bundle_dir=args.bundle_dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
