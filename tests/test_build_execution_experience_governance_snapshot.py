from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_governance_snapshot import build_snapshot


def test_build_snapshot_collects_governance_flags_and_counts(tmp_path: Path) -> None:
    result = build_snapshot(
        output_path=tmp_path / "governance_snapshot.json",
        review_backlog={
            "candidates_path": "/tmp/candidates.json",
            "decisions_path": "/tmp/decisions.tsv",
            "reviewer_manifest_path": "/tmp/reviewer_manifest.json",
            "total_candidates": 12,
            "reviewed_candidates": 8,
            "backlog_candidates": 4,
            "stale_reviewed_candidates": 1,
            "expected_reviewers": ["gemini_no_mcp", "claudeminmax"],
            "under_reviewed_candidates": 2,
            "disputed_candidates": 1,
            "deferred_candidates": 1,
            "reviewed_by_decision": {"accept": 5, "revise": 2, "defer": 1},
        },
        review_validation={
            "review_output_validation_path": "/tmp/review_output_validation_summary.json",
            "structurally_valid": False,
            "complete": False,
            "missing_reviewers": ["claudeminmax"],
            "unexpected_reviewers": ["rogue"],
            "unknown_candidate_items": 1,
            "invalid_decision_items": 2,
            "duplicate_candidate_items": 1,
        },
        governance_queues={
            "summary_path": "/tmp/governance_queues/summary.json",
            "by_state": {"under_reviewed": 2, "review_pending": 4},
            "by_action": {"collect_missing_reviews": 2, "review_now": 4},
        },
        followup_manifest={
            "output_path": "/tmp/followup_manifest.json",
            "total_followup_candidates": 4,
            "branches": {
                "accept": {"candidates": 1},
                "revise": {"candidates": 2},
                "defer": {"candidates": 1},
                "reject": {"candidates": 0},
            },
        },
    )

    assert result["totals"]["followup_candidates"] == 4
    assert result["validation_state"]["total_validation_issues"] == 4
    assert result["queue_state"]["followup_by_branch"] == {"accept": 1, "defer": 1, "reject": 0, "revise": 2}
    assert result["attention_flags"]["backlog_open"] is True
    assert result["attention_flags"]["reviewer_coverage_gaps"] is True
    assert result["attention_flags"]["invalid_review_outputs"] is True

    written = json.loads((tmp_path / "governance_snapshot.json").read_text(encoding="utf-8"))
    assert written["review_state"]["reviewed_by_decision"] == {"accept": 5, "revise": 2, "defer": 1}

