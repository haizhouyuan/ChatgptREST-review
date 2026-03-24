#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
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


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def next_versioned_decision_name(base_path: Path | None) -> str:
    if base_path is None:
        return "execution_lineage_review_decisions_v1.tsv"
    match = re.search(r"_v(\d+)\.tsv$", base_path.name)
    if not match:
        return "execution_lineage_review_decisions_v1.tsv"
    return re.sub(r"_v\d+\.tsv$", f"_v{int(match.group(1)) + 1}.tsv", base_path.name)


def compose(*, base_path: Path | None, delta_path: Path, output_path: Path) -> dict[str, Any]:
    base_rows = _read_tsv(base_path) if base_path and base_path.exists() else []
    delta_rows = _read_tsv(delta_path)

    merged = {row["atom_id"]: dict(row) for row in base_rows}
    replaced = 0
    added = 0
    for row in delta_rows:
        normalized = {field: row.get(field, "") for field in FIELDNAMES}
        if normalized["atom_id"] in merged:
            replaced += 1
        else:
            added += 1
        merged[normalized["atom_id"]] = normalized

    ordered = sorted(
        merged.values(),
        key=lambda row: (
            row.get("task_ref", ""),
            row.get("trace_id", ""),
            row.get("atom_id", ""),
        ),
    )
    _write_tsv(output_path, ordered)

    summary = {
        "base_path": str(base_path) if base_path else "",
        "delta_path": str(delta_path),
        "output_path": str(output_path),
        "base_atoms": len(base_rows),
        "delta_atoms": len(delta_rows),
        "replaced_atoms": replaced,
        "added_atoms": added,
        "final_atoms": len(ordered),
        "by_final_decision_bucket": Counter(row.get("final_decision_bucket", "") for row in ordered),
        "by_final_remediation_action": Counter(row.get("final_remediation_action", "") for row in ordered),
    }
    output_path.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Overlay lineage review decision deltas onto a baseline lineage decision set."
    )
    parser.add_argument("--delta", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base", default="")
    args = parser.parse_args()

    summary = compose(base_path=Path(args.base) if args.base else None, delta_path=Path(args.delta), output_path=Path(args.output))
    print(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
