#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


FIELDNAMES = [
    "candidate_id",
    "atom_id",
    "lineage_family_id",
    "task_ref",
    "trace_id",
    "source",
    "episode_type",
    "experience_kind",
    "title",
    "summary",
    "groundedness",
    "time_sensitivity",
    "review_decision",
    "archive_bucket",
    "archive_owner",
    "archive_notes",
]


def _read_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError(f"Expected candidate list JSON at {path}")


def _read_tsv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def build_queue(
    *,
    candidates_path: str | Path,
    decisions_path: str | Path | None,
    output_tsv: str | Path,
) -> dict[str, Any]:
    candidates = {str(row.get("candidate_id") or ""): row for row in _read_candidates(Path(candidates_path))}
    decisions = _read_tsv(Path(decisions_path) if decisions_path else None)

    rows: list[dict[str, Any]] = []
    for decision in decisions:
        if str(decision.get("review_decision") or "").strip() != "reject":
            continue
        candidate_id = str(decision.get("candidate_id") or "").strip()
        candidate = candidates.get(candidate_id, {})
        rows.append(
            {
                "candidate_id": candidate_id,
                "atom_id": str(decision.get("atom_id") or candidate.get("atom_id") or ""),
                "lineage_family_id": str(decision.get("lineage_family_id") or candidate.get("lineage_family_id") or ""),
                "task_ref": str(decision.get("task_ref") or candidate.get("task_ref") or ""),
                "trace_id": str(decision.get("trace_id") or candidate.get("trace_id") or ""),
                "source": str(decision.get("source") or candidate.get("source") or ""),
                "episode_type": str(decision.get("episode_type") or candidate.get("episode_type") or ""),
                "experience_kind": str(decision.get("experience_kind") or candidate.get("experience_kind") or ""),
                "title": str(decision.get("title") or candidate.get("title") or ""),
                "summary": str(decision.get("summary") or candidate.get("summary") or ""),
                "groundedness": str(decision.get("groundedness") or ""),
                "time_sensitivity": str(decision.get("time_sensitivity") or ""),
                "review_decision": "reject",
                "archive_bucket": "",
                "archive_owner": "",
                "archive_notes": "",
            }
        )

    out = Path(output_tsv)
    _write_tsv(out, rows)
    summary = {
        "ok": True,
        "candidates_path": str(candidates_path),
        "decisions_path": str(decisions_path) if decisions_path else "",
        "output_tsv": str(out),
        "total_rejected_candidates": len(rows),
        "by_kind": {key: int(count) for key, count in sorted(Counter(row["experience_kind"] for row in rows).items())},
    }
    summary_path = out.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a reject-only archive queue from execution experience review decisions.")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--decisions", default="")
    args = parser.parse_args()

    result = build_queue(
        candidates_path=args.candidates,
        decisions_path=Path(args.decisions) if args.decisions else None,
        output_tsv=args.output_tsv,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
