#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


KEEP_BUCKETS = {"lesson", "procedure", "correction"}

FIELDNAMES = [
    "atom_id",
    "lineage_family_id",
    "lineage_status",
    "source",
    "episode_type",
    "atom_type",
    "task_ref",
    "trace_id",
    "canonical_question",
    "suggested_bucket",
    "final_bucket",
    "lineage_action",
    "experience_kind",
    "experience_title",
    "experience_summary",
    "reviewer",
    "review_notes",
]


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def next_versioned_decision_name(base_path: Path | None) -> str:
    if base_path is None:
        return "execution_review_decisions_v1.tsv"
    match = re.search(r"_v(\d+)\.tsv$", base_path.name)
    if not match:
        return "execution_review_decisions_v1.tsv"
    return re.sub(r"_v\d+\.tsv$", f"_v{int(match.group(1)) + 1}.tsv", base_path.name)


def compose(base_path: Path | None, delta_path: Path, output_path: Path) -> dict[str, Any]:
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
            row.get("lineage_family_id", ""),
            row.get("task_ref", ""),
            row.get("trace_id", ""),
            row.get("atom_id", ""),
        ),
    )
    _write_tsv(output_path, ordered, FIELDNAMES)

    allowlist_rows = [row for row in ordered if row.get("final_bucket", "") in KEEP_BUCKETS]
    allowlist_path = output_path.with_name(output_path.stem + "_allowlist.tsv")
    _write_tsv(allowlist_path, allowlist_rows, FIELDNAMES)

    summary = {
        "base_path": str(base_path) if base_path else "",
        "delta_path": str(delta_path),
        "output_path": str(output_path),
        "allowlist_path": str(allowlist_path),
        "base_atoms": len(base_rows),
        "delta_atoms": len(delta_rows),
        "replaced_atoms": replaced,
        "added_atoms": added,
        "final_atoms": len(ordered),
        "allowlist_atoms": len(allowlist_rows),
        "by_bucket": Counter(row.get("final_bucket", "") for row in ordered),
    }
    output_path.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Overlay execution review delta decisions onto a baseline decision set.")
    parser.add_argument("--delta", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base", default="")
    args = parser.parse_args()

    summary = compose(Path(args.base) if args.base else None, Path(args.delta), Path(args.output))
    print(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
