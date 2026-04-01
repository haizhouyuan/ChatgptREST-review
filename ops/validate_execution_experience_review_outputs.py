#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from chatgptrest.evomap.knowledge.review_experiment import load_review_json
from ops.execution_experience_review_reviewer_identity import load_expected_reviewers, resolve_reviewer_name


VALID_DECISIONS = {"accept", "revise", "reject", "defer"}


def _read_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError(f"Expected candidate list JSON at {path}")


def _extract_review_payload(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(payload, list):
        return {"items": payload}
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload

    for key in ("response", "text", "output", "message", "result"):
        raw = payload.get(key) if isinstance(payload, dict) else None
        if not raw or not isinstance(raw, str):
            continue
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```$", "", text)
        try:
            nested = json.loads(text)
            if isinstance(nested, dict) and isinstance(nested.get("items"), list):
                return nested
            if isinstance(nested, list):
                return {"items": nested}
        except Exception:
            pass
        decoder = json.JSONDecoder()
        for idx, ch in enumerate(text):
            if ch not in "{[":
                continue
            try:
                nested, _ = decoder.raw_decode(text[idx:])
            except Exception:
                continue
            if isinstance(nested, dict) and isinstance(nested.get("items"), list):
                return nested
            if isinstance(nested, list):
                return {"items": nested}
    return payload if isinstance(payload, dict) else {"items": []}


def validate_review_outputs(
    *,
    candidates_path: str | Path,
    review_json_paths: list[Path],
    reviewer_manifest_path: str | Path | None = None,
    top_n: int = 12,
) -> dict[str, Any]:
    candidates = _read_candidates(Path(candidates_path))
    candidate_ids = {str(row.get("candidate_id") or "") for row in candidates if str(row.get("candidate_id") or "")}
    expected_reviewers = load_expected_reviewers(Path(reviewer_manifest_path) if reviewer_manifest_path else None)

    per_reviewer: list[dict[str, Any]] = []
    coverage: defaultdict[str, set[str]] = defaultdict(set)
    unknown_items: list[dict[str, Any]] = []
    invalid_decisions: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    provided_reviewers: list[str] = []
    total_items = 0

    for path in review_json_paths:
        payload = _extract_review_payload(load_review_json(path))
        reviewer = resolve_reviewer_name(path, payload, expected_reviewers)
        provided_reviewers.append(reviewer)
        items = payload.get("items")
        if not isinstance(items, list):
            items = []
        seen_candidate_ids: set[str] = set()
        reviewer_unknown = 0
        reviewer_invalid = 0
        reviewer_duplicates = 0

        for item in items:
            if not isinstance(item, dict):
                continue
            total_items += 1
            candidate_id = str(item.get("candidate_id") or "").strip()
            decision = str(item.get("decision") or "").strip().lower()

            if not candidate_id or candidate_id not in candidate_ids:
                reviewer_unknown += 1
                if len(unknown_items) < int(top_n):
                    unknown_items.append(
                        {
                            "reviewer": reviewer,
                            "candidate_id": candidate_id,
                            "decision": decision,
                        }
                    )
                continue

            if decision not in VALID_DECISIONS:
                reviewer_invalid += 1
                if len(invalid_decisions) < int(top_n):
                    invalid_decisions.append(
                        {
                            "reviewer": reviewer,
                            "candidate_id": candidate_id,
                            "decision": decision,
                        }
                    )
                continue

            if candidate_id in seen_candidate_ids:
                reviewer_duplicates += 1
                if len(duplicate_rows) < int(top_n):
                    duplicate_rows.append(
                        {
                            "reviewer": reviewer,
                            "candidate_id": candidate_id,
                        }
                    )
                continue

            seen_candidate_ids.add(candidate_id)
            coverage[candidate_id].add(reviewer)

        per_reviewer.append(
            {
                "reviewer": reviewer,
                "path": str(path),
                "items": len([item for item in items if isinstance(item, dict)]),
                "unknown_candidate_items": reviewer_unknown,
                "invalid_decision_items": reviewer_invalid,
                "duplicate_candidate_items": reviewer_duplicates,
                "valid_candidate_items": len(seen_candidate_ids),
            }
        )

    provided_unique = sorted(dict.fromkeys(provided_reviewers))
    expected_set = set(expected_reviewers)
    provided_set = set(provided_unique)
    coverage_by_review_count = Counter(str(len(reviewers)) for reviewers in coverage.values())
    untouched_candidates = len(candidate_ids - set(coverage))
    if untouched_candidates:
        coverage_by_review_count["0"] += untouched_candidates

    structurally_valid = not unknown_items and not invalid_decisions and not duplicate_rows
    complete = bool(expected_reviewers) and not (expected_set - provided_set)

    return {
        "candidates_path": str(candidates_path),
        "reviewer_manifest_path": str(reviewer_manifest_path) if reviewer_manifest_path else "",
        "review_outputs": [str(path) for path in review_json_paths],
        "expected_reviewers": expected_reviewers,
        "provided_reviewers": provided_unique,
        "missing_reviewers": sorted(expected_set - provided_set),
        "unexpected_reviewers": sorted(provided_set - expected_set) if expected_reviewers else [],
        "total_candidates": len(candidate_ids),
        "total_review_items": total_items,
        "coverage_by_review_count": {key: int(coverage_by_review_count[key]) for key in sorted(coverage_by_review_count)},
        "structurally_valid": structurally_valid,
        "complete": complete,
        "unknown_candidate_items": sum(item["unknown_candidate_items"] for item in per_reviewer),
        "invalid_decision_items": sum(item["invalid_decision_items"] for item in per_reviewer),
        "duplicate_candidate_items": sum(item["duplicate_candidate_items"] for item in per_reviewer),
        "per_reviewer": per_reviewer,
        "sample_unknown_candidate_items": unknown_items,
        "sample_invalid_decision_items": invalid_decisions,
        "sample_duplicate_candidate_items": duplicate_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate execution experience reviewer JSON outputs against the current candidate pack.")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--review-json", action="append", default=[])
    parser.add_argument("--reviewer-manifest", default="")
    parser.add_argument("--top-n", type=int, default=12)
    args = parser.parse_args()

    summary = validate_review_outputs(
        candidates_path=args.candidates,
        review_json_paths=[Path(path) for path in args.review_json],
        reviewer_manifest_path=Path(args.reviewer_manifest) if args.reviewer_manifest else None,
        top_n=args.top_n,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
