from __future__ import annotations

from pathlib import Path

from ops.render_execution_experience_review_brief import render_brief


def test_render_brief_writes_human_readable_sections(tmp_path: Path) -> None:
    result = render_brief(
        output_path=tmp_path / "review_brief.md",
        governance_snapshot={
            "totals": {
                "total_candidates": 12,
                "reviewed_candidates": 8,
                "backlog_candidates": 4,
                "followup_candidates": 3,
            },
            "review_state": {
                "disputed_candidates": 1,
                "under_reviewed_candidates": 2,
            },
            "validation_state": {
                "available": True,
                "structurally_valid": False,
                "complete": False,
                "missing_reviewers": ["claudeminmax"],
                "total_validation_issues": 2,
            },
            "queue_state": {
                "by_state": {"under_reviewed": 2},
                "by_action": {"collect_missing_reviews": 2},
                "followup_by_branch": {"accept": 1, "revise": 2},
            },
            "attention_flags": {
                "backlog_open": True,
                "reviewer_coverage_gaps": True,
                "invalid_review_outputs": True,
                "followup_work_present": True,
            },
        },
        attention_manifest={
            "review": {
                "pack_path": "/tmp/review_pack/pack.json",
                "review_backlog_path": "/tmp/review_backlog_summary.json",
                "review_decision_scaffold_path": "/tmp/review_decision_scaffold.tsv",
                "review_output_validation_path": "/tmp/review_output_validation_summary.json",
                "reviewer_manifest_path": "/tmp/reviewer_manifest.json",
            },
            "governance": {
                "summary_path": "/tmp/governance_queues/summary.json",
            },
            "followup": {
                "total_candidates": 3,
            },
        },
    )

    text = (tmp_path / "review_brief.md").read_text(encoding="utf-8")
    assert result["sections"] == ["totals", "validation", "governance", "followup", "flags", "routes"]
    assert "# Execution Experience Review Brief" in text
    assert "## Totals" in text
    assert "- total_candidates: 12" in text
    assert "## Routes" in text
    assert "/tmp/reviewer_manifest.json" in text

