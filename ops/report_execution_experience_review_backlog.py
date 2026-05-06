#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _read_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError(f"Expected candidate list JSON at {path}")


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: int(counter[key]) for key in sorted(counter)}


def _load_expected_reviewers(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    reviewers = payload.get("reviewers") if isinstance(payload, dict) else None
    if not isinstance(reviewers, list):
        return []
    result: list[str] = []
    for item in reviewers:
        if not isinstance(item, dict):
            continue
        reviewer = str(item.get("reviewer") or "").strip()
        if reviewer:
            result.append(reviewer)
    return sorted(dict.fromkeys(result))


def _parse_reviewers(raw: str) -> list[dict[str, Any]]:
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def report_backlog(
    *,
    candidates_path: str | Path,
    decisions_path: str | Path | None = None,
    reviewer_manifest_path: str | Path | None = None,
    top_n: int = 12,
) -> dict[str, Any]:
    candidates = _read_candidates(Path(candidates_path))
    candidate_lookup = {str(row.get("candidate_id") or ""): row for row in candidates}
    candidate_ids = {candidate_id for candidate_id in candidate_lookup if candidate_id}

    decision_rows = _read_tsv(Path(decisions_path)) if decisions_path else []
    expected_reviewers = _load_expected_reviewers(Path(reviewer_manifest_path) if reviewer_manifest_path else None)
    expected_reviewer_count = len(expected_reviewers)

    active_decisions = [row for row in decision_rows if str(row.get("candidate_id") or "") in candidate_ids]
    stale_decisions = [row for row in decision_rows if str(row.get("candidate_id") or "") not in candidate_ids]
    reviewed_lookup = {str(row.get("candidate_id") or ""): row for row in active_decisions}

    reviewed_candidates = [candidate_lookup[candidate_id] for candidate_id in reviewed_lookup]
    backlog_candidates = [candidate for candidate_id, candidate in sorted(candidate_lookup.items()) if candidate_id not in reviewed_lookup]

    coverage_counter: Counter[str] = Counter()
    disputed_candidates = 0
    deferred_candidates = 0
    under_reviewed_candidates = 0
    sample_disputed_rows: list[dict[str, Any]] = []

    for candidate_id, candidate in sorted(candidate_lookup.items()):
        decision_row = reviewed_lookup.get(candidate_id, {})
        reviewer_payload = _parse_reviewers(str(decision_row.get("reviewers") or ""))
        review_count = len(reviewer_payload)
        coverage_counter[str(review_count)] += 1
        if expected_reviewer_count and review_count < expected_reviewer_count:
            under_reviewed_candidates += 1
        distinct_decisions = sorted(
            {
                str(item.get("decision") or "").strip()
                for item in reviewer_payload
                if str(item.get("decision") or "").strip()
            }
        )
        if len(distinct_decisions) > 1:
            disputed_candidates += 1
            if len(sample_disputed_rows) < int(top_n):
                sample_disputed_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "experience_kind": str(candidate.get("experience_kind") or ""),
                        "source": str(candidate.get("source") or ""),
                        "decision": str(decision_row.get("review_decision") or ""),
                        "distinct_reviewer_decisions": distinct_decisions,
                        "review_count": review_count,
                    }
                )
        if str(decision_row.get("review_decision") or "") == "defer":
            deferred_candidates += 1

    sample_backlog_rows = [
        {
            "candidate_id": str(row.get("candidate_id") or ""),
            "experience_kind": str(row.get("experience_kind") or ""),
            "source": str(row.get("source") or ""),
            "episode_type": str(row.get("episode_type") or ""),
            "lineage_status": str(row.get("lineage_status") or ""),
        }
        for row in sorted(
            backlog_candidates,
            key=lambda row: (
                str(row.get("experience_kind") or ""),
                str(row.get("source") or ""),
                str(row.get("candidate_id") or ""),
            ),
        )[: int(top_n)]
    ]

    return {
        "candidates_path": str(candidates_path),
        "decisions_path": str(decisions_path) if decisions_path else "",
        "reviewer_manifest_path": str(reviewer_manifest_path) if reviewer_manifest_path else "",
        "expected_reviewers": expected_reviewers,
        "total_candidates": len(candidates),
        "reviewed_candidates": len(reviewed_candidates),
        "backlog_candidates": len(backlog_candidates),
        "stale_reviewed_candidates": len(stale_decisions),
        "by_kind": _counter_to_dict(Counter(str(row.get("experience_kind") or "") for row in candidates)),
        "reviewed_by_kind": _counter_to_dict(Counter(str(row.get("experience_kind") or "") for row in reviewed_candidates)),
        "backlog_by_kind": _counter_to_dict(Counter(str(row.get("experience_kind") or "") for row in backlog_candidates)),
        "reviewed_by_decision": _counter_to_dict(
            Counter(str(row.get("review_decision") or "") for row in active_decisions if str(row.get("review_decision") or ""))
        ),
        "coverage_by_review_count": _counter_to_dict(coverage_counter),
        "under_reviewed_candidates": under_reviewed_candidates if expected_reviewer_count else 0,
        "disputed_candidates": disputed_candidates,
        "deferred_candidates": deferred_candidates,
        "sample_backlog_candidates": sample_backlog_rows,
        "sample_disputed_candidates": sample_disputed_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report backlog and governance state for execution experience review candidates.")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--decisions", default="")
    parser.add_argument("--reviewer-manifest", default="")
    parser.add_argument("--top-n", type=int, default=12)
    args = parser.parse_args()

    summary = report_backlog(
        candidates_path=args.candidates,
        decisions_path=Path(args.decisions) if args.decisions else None,
        reviewer_manifest_path=Path(args.reviewer_manifest) if args.reviewer_manifest else None,
        top_n=args.top_n,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
