#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


KEEP_BUCKETS = {"service_candidate", "lesson", "procedure", "correction"}


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def compose(base_path: Path, delta_path: Path, output_path: Path) -> dict[str, Any]:
    base_rows = _read_tsv(base_path)
    delta_rows = _read_tsv(delta_path)
    merged = {row["doc_id"]: dict(row) for row in base_rows}
    replaced = 0
    added = 0
    for row in delta_rows:
        if row["doc_id"] in merged:
            replaced += 1
        else:
            added += 1
        merged[row["doc_id"]] = dict(row)

    ordered = sorted(merged.values(), key=lambda row: (row.get("review_domain", ""), row["doc_id"]))
    fields = [
        "doc_id",
        "title",
        "raw_ref",
        "family_id",
        "review_domain",
        "source_bucket",
        "avg_quality",
        "final_bucket",
        "service_readiness",
        "reviewers",
    ]
    _write_tsv(output_path, ordered, fields)

    allowlist_rows = [row for row in ordered if row.get("final_bucket", "") in KEEP_BUCKETS]
    allowlist_path = output_path.with_name(output_path.stem + "_allowlist.tsv")
    _write_tsv(allowlist_path, allowlist_rows, fields)

    summary = {
        "base_path": str(base_path),
        "delta_path": str(delta_path),
        "output_path": str(output_path),
        "allowlist_path": str(allowlist_path),
        "base_docs": len(base_rows),
        "delta_docs": len(delta_rows),
        "replaced_docs": replaced,
        "added_docs": added,
        "final_docs": len(ordered),
        "allowlist_docs": len(allowlist_rows),
        "by_bucket": Counter(row.get("final_bucket", "") for row in ordered),
    }
    output_path.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Overlay planning review delta decisions onto a full baseline decision set.")
    parser.add_argument("--base", required=True)
    parser.add_argument("--delta", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    summary = compose(Path(args.base), Path(args.delta), Path(args.output))
    print(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
