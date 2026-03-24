#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: int(counter[key]) for key in sorted(counter)}


def report_backlog(*, input_tsv: str | Path, top_n: int = 12) -> dict[str, Any]:
    path = Path(input_tsv)
    rows = _read_tsv(path)

    reviewed_rows = [row for row in rows if str(row.get("final_decision_bucket") or "")]
    backlog_rows = [row for row in rows if not str(row.get("final_decision_bucket") or "")]

    suggested_by_bucket = Counter(str(row.get("suggested_decision_bucket") or "") for row in rows)
    final_by_bucket = Counter(str(row.get("final_decision_bucket") or "") for row in reviewed_rows)
    backlog_by_suggested_bucket = Counter(str(row.get("suggested_decision_bucket") or "") for row in backlog_rows)
    backlog_by_remediation_action = Counter(str(row.get("remediation_action") or "") for row in backlog_rows)
    backlog_by_lineage_class = Counter(str(row.get("lineage_class") or "") for row in backlog_rows)

    backlog_with_candidate_fill = [row for row in backlog_rows if str(row.get("candidate_fill_fields") or "")]
    sample_backlog_rows = sorted(
        backlog_rows,
        key=lambda row: (
            str(row.get("task_ref") or ""),
            str(row.get("trace_id") or ""),
            str(row.get("atom_id") or ""),
        ),
    )[: int(top_n)]

    return {
        "input_tsv": str(path),
        "total_rows": len(rows),
        "reviewed_rows": len(reviewed_rows),
        "backlog_rows": len(backlog_rows),
        "suggested_by_bucket": _counter_to_dict(suggested_by_bucket),
        "final_by_bucket": _counter_to_dict(final_by_bucket),
        "backlog_by_suggested_bucket": _counter_to_dict(backlog_by_suggested_bucket),
        "backlog_by_remediation_action": _counter_to_dict(backlog_by_remediation_action),
        "backlog_by_lineage_class": _counter_to_dict(backlog_by_lineage_class),
        "backlog_rows_with_candidate_fill_fields": len(backlog_with_candidate_fill),
        "sample_backlog_rows": [
            {
                "atom_id": str(row.get("atom_id") or ""),
                "task_ref": str(row.get("task_ref") or ""),
                "trace_id": str(row.get("trace_id") or ""),
                "suggested_decision_bucket": str(row.get("suggested_decision_bucket") or ""),
                "remediation_action": str(row.get("remediation_action") or ""),
                "candidate_fill_fields": str(row.get("candidate_fill_fields") or ""),
                "lineage_class": str(row.get("lineage_class") or ""),
            }
            for row in sample_backlog_rows
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report backlog state for an execution lineage review scaffold/decision TSV.")
    parser.add_argument("--input-tsv", required=True)
    parser.add_argument("--top-n", type=int, default=12)
    args = parser.parse_args()

    print(json.dumps(report_backlog(input_tsv=args.input_tsv, top_n=args.top_n), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
