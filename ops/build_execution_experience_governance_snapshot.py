#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_snapshot(
    *,
    output_path: str | Path,
    review_backlog: dict[str, Any],
    review_validation: dict[str, Any] | None,
    governance_queues: dict[str, Any],
    followup_manifest: dict[str, Any],
) -> dict[str, Any]:
    validation = review_validation if isinstance(review_validation, dict) else {}
    validation_available = bool(validation)
    unknown_items = int(validation.get("unknown_candidate_items", 0)) if validation_available else 0
    invalid_items = int(validation.get("invalid_decision_items", 0)) if validation_available else 0
    duplicate_items = int(validation.get("duplicate_candidate_items", 0)) if validation_available else 0
    followup_branches = followup_manifest.get("branches") if isinstance(followup_manifest, dict) else {}
    branch_counts = {
        branch: int(details.get("candidates", 0))
        for branch, details in sorted((followup_branches or {}).items())
        if isinstance(details, dict)
    }

    snapshot = {
        "ok": True,
        "inputs": {
            "candidates_path": str(review_backlog.get("candidates_path") or ""),
            "decisions_path": str(review_backlog.get("decisions_path") or ""),
            "reviewer_manifest_path": str(review_backlog.get("reviewer_manifest_path") or ""),
            "review_output_validation_path": str(validation.get("review_output_validation_path") or ""),
            "governance_queue_summary_path": str(governance_queues.get("summary_path") or ""),
            "followup_manifest_path": str(followup_manifest.get("output_path") or ""),
        },
        "totals": {
            "total_candidates": int(review_backlog.get("total_candidates", 0)),
            "reviewed_candidates": int(review_backlog.get("reviewed_candidates", 0)),
            "backlog_candidates": int(review_backlog.get("backlog_candidates", 0)),
            "stale_reviewed_candidates": int(review_backlog.get("stale_reviewed_candidates", 0)),
            "followup_candidates": int(followup_manifest.get("total_followup_candidates", 0)),
        },
        "review_state": {
            "expected_reviewers": list(review_backlog.get("expected_reviewers") or []),
            "under_reviewed_candidates": int(review_backlog.get("under_reviewed_candidates", 0)),
            "disputed_candidates": int(review_backlog.get("disputed_candidates", 0)),
            "deferred_candidates": int(review_backlog.get("deferred_candidates", 0)),
            "reviewed_by_decision": dict(review_backlog.get("reviewed_by_decision") or {}),
        },
        "validation_state": {
            "available": validation_available,
            "structurally_valid": validation.get("structurally_valid") if validation_available else None,
            "complete": validation.get("complete") if validation_available else None,
            "missing_reviewers": list(validation.get("missing_reviewers") or []),
            "unexpected_reviewers": list(validation.get("unexpected_reviewers") or []),
            "unknown_candidate_items": unknown_items,
            "invalid_decision_items": invalid_items,
            "duplicate_candidate_items": duplicate_items,
            "total_validation_issues": unknown_items + invalid_items + duplicate_items,
        },
        "queue_state": {
            "by_state": dict(governance_queues.get("by_state") or {}),
            "by_action": dict(governance_queues.get("by_action") or {}),
            "followup_by_branch": branch_counts,
        },
        "attention_flags": {
            "backlog_open": int(review_backlog.get("backlog_candidates", 0)) > 0,
            "stale_reviews_present": int(review_backlog.get("stale_reviewed_candidates", 0)) > 0,
            "reviewer_coverage_gaps": (
                int(review_backlog.get("under_reviewed_candidates", 0)) > 0
                or bool(validation.get("missing_reviewers"))
            ),
            "disputed_reviews_present": int(review_backlog.get("disputed_candidates", 0)) > 0,
            "invalid_review_outputs": (unknown_items + invalid_items + duplicate_items) > 0,
            "followup_work_present": int(followup_manifest.get("total_followup_candidates", 0)) > 0,
        },
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    snapshot["output_path"] = str(out)
    return snapshot


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a governance snapshot for execution experience review outputs.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--review-backlog", required=True)
    parser.add_argument("--governance-queue-summary", required=True)
    parser.add_argument("--followup-manifest", required=True)
    parser.add_argument("--review-output-validation", default="")
    args = parser.parse_args()

    review_backlog = _load_json(Path(args.review_backlog))
    review_validation = _load_json(Path(args.review_output_validation)) if args.review_output_validation else None
    governance_queues = _load_json(Path(args.governance_queue_summary))
    followup_manifest = _load_json(Path(args.followup_manifest))

    if review_validation:
        review_validation["review_output_validation_path"] = args.review_output_validation

    result = build_snapshot(
        output_path=args.output,
        review_backlog=review_backlog,
        review_validation=review_validation,
        governance_queues=governance_queues,
        followup_manifest=followup_manifest,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
