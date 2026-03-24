from __future__ import annotations

from pathlib import Path

from ops.build_execution_experience_review_reply_draft import build_draft


def test_build_draft_recommends_fixing_invalid_outputs_first(tmp_path: Path) -> None:
    result = build_draft(
        output_path=tmp_path / "review_reply_draft.md",
        governance_snapshot={
            "output_path": "/tmp/governance_snapshot.json",
            "totals": {
                "total_candidates": 12,
                "reviewed_candidates": 8,
                "backlog_candidates": 4,
                "followup_candidates": 3,
            },
            "validation_state": {
                "available": True,
                "structurally_valid": False,
                "complete": False,
            },
            "attention_flags": {
                "invalid_review_outputs": True,
                "reviewer_coverage_gaps": True,
                "backlog_open": True,
                "followup_work_present": True,
            },
        },
        review_brief_path="/tmp/review_brief.md",
        attention_manifest_path="/tmp/attention_manifest.json",
    )

    text = (tmp_path / "review_reply_draft.md").read_text(encoding="utf-8")
    assert result["recommended_action"] == "fix_review_outputs"
    assert "Recommended next step:" in text
    assert "action=fix_review_outputs" in text
    assert "/tmp/review_brief.md" in text

