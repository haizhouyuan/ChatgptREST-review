from __future__ import annotations

import json
from pathlib import Path

from ops.build_execution_experience_attention_manifest import build_manifest


def test_build_manifest_collects_review_governance_and_followup_routes(tmp_path: Path) -> None:
    result = build_manifest(
        output_path=tmp_path / "attention_manifest.json",
        review_pack={
            "selected_candidates": 3,
            "pack_path": "/tmp/review_pack/pack.json",
        },
        reviewer_manifest={
            "manifest_path": "/tmp/reviewer_manifest.json",
            "review_output_dir": "/tmp/review_runs",
        },
        review_backlog={
            "backlog_candidates": 2,
        },
        review_backlog_path="/tmp/review_backlog_summary.json",
        review_decision_scaffold_path="/tmp/review_decision_scaffold.tsv",
        review_validation={
            "review_output_validation_path": "/tmp/review_output_validation_summary.json",
            "structurally_valid": True,
            "complete": False,
            "missing_reviewers": ["claudeminmax"],
            "unexpected_reviewers": [],
        },
        governance_queues={
            "summary_path": "/tmp/governance_queues/summary.json",
            "queue_files": {
                "under_reviewed": {
                    "rows": 2,
                    "json_path": "/tmp/governance_queues/under_reviewed.json",
                    "tsv_path": "/tmp/governance_queues/under_reviewed.tsv",
                }
            },
            "action_files": {
                "collect_missing_reviews": {
                    "rows": 2,
                    "json_path": "/tmp/governance_queues/by_action/collect_missing_reviews.json",
                    "tsv_path": "/tmp/governance_queues/by_action/collect_missing_reviews.tsv",
                }
            },
        },
        followup_manifest={
            "total_followup_candidates": 2,
            "branches": {
                "accept": {"candidates": 1, "manifest_path": "/tmp/accepted_pack/manifest.json"},
                "revise": {"candidates": 1, "worklist_path": "/tmp/revision_worklist.tsv"},
            },
        },
    )

    assert result["review"]["selected_candidates"] == 3
    assert result["review"]["validation_available"] is True
    assert result["governance"]["state_routes"]["under_reviewed"]["rows"] == 2
    assert result["followup"]["routes"]["accept"]["candidates"] == 1
    assert result["followup"]["total_candidates"] == 2

    written = json.loads((tmp_path / "attention_manifest.json").read_text(encoding="utf-8"))
    assert written["review"]["missing_reviewers"] == ["claudeminmax"]

