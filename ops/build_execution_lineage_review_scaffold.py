#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDNAMES = [
    "atom_id",
    "task_ref",
    "trace_id",
    "source",
    "episode_type",
    "lineage_class",
    "extension_count",
    "correlation_group_size",
    "candidate_fill_fields",
    "remediation_action",
    "suggested_decision_bucket",
    "final_decision_bucket",
    "approved_fill_fields",
    "final_remediation_action",
    "reviewer",
    "review_notes",
    "canonical_question",
]


def build_scaffold(*, input_json: str | Path, output_tsv: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(input_json).read_text(encoding="utf-8"))
    rows = payload.get("rows", [])

    scaffold_rows = [
        {
            "atom_id": str(row.get("atom_id") or ""),
            "task_ref": str(row.get("task_ref") or ""),
            "trace_id": str(row.get("trace_id") or ""),
            "source": str(row.get("source") or ""),
            "episode_type": str(row.get("episode_type") or ""),
            "lineage_class": str(row.get("lineage_class") or ""),
            "extension_count": int(row.get("extension_count") or 0),
            "correlation_group_size": int(row.get("correlation_group_size") or 0),
            "candidate_fill_fields": str(row.get("candidate_fill_fields") or ""),
            "remediation_action": str(row.get("remediation_action") or ""),
            "suggested_decision_bucket": str(row.get("decision_bucket") or ""),
            "final_decision_bucket": "",
            "approved_fill_fields": "",
            "final_remediation_action": "",
            "reviewer": "",
            "review_notes": "",
            "canonical_question": str(row.get("canonical_question") or ""),
        }
        for row in rows
    ]

    out = Path(output_tsv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(scaffold_rows)

    return {
        "ok": True,
        "input_json": str(input_json),
        "output_tsv": str(out),
        "selected_rows": len(scaffold_rows),
        "suggested_review_ready": sum(1 for row in scaffold_rows if row["suggested_decision_bucket"] == "review_ready"),
        "suggested_remediation_candidate": sum(
            1 for row in scaffold_rows if row["suggested_decision_bucket"] == "remediation_candidate"
        ),
        "suggested_manual_review_required": sum(
            1 for row in scaffold_rows if row["suggested_decision_bucket"] == "manual_review_required"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a ready-to-fill lineage review scaffold from execution review decision input."
    )
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--output-tsv", required=True)
    args = parser.parse_args()

    result = build_scaffold(input_json=args.input_json, output_tsv=args.output_tsv)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
