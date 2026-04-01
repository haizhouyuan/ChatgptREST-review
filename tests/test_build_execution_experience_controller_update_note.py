from __future__ import annotations

from pathlib import Path

from ops.build_execution_experience_controller_update_note import build_note


def test_build_note_includes_progress_delta_and_steps(tmp_path: Path) -> None:
    result = build_note(
        output_path=tmp_path / "controller_update_note.md",
        controller_packet={
            "output_path": "/tmp/controller_packet.json",
            "summary": {
                "recommended_action": "collect_missing_reviews",
                "reason": "review coverage is incomplete",
                "total_candidates": 4,
                "backlog_candidates": 2,
                "followup_candidates": 1,
                "validation_available": True,
            },
            "paths": {
                "review_brief": "/tmp/review_brief.md",
                "review_reply_draft": "/tmp/review_reply_draft.md",
            },
        },
        controller_action_plan={
            "output_path": "/tmp/controller_action_plan.json",
            "steps": [
                "send the current review pack and reviewer manifest to the remaining reviewers",
                "wait for missing review outputs to land",
            ],
            "artifacts": ["/tmp/reviewer_manifest.json"],
        },
        progress_delta={
            "output_path": "/tmp/progress_delta.json",
            "status": {
                "progress_signal": "improved",
                "recommended_action_changed": False,
                "action_severity_delta": -1,
            },
            "delta": {
                "totals": {
                    "reviewed_candidates": 2,
                    "backlog_candidates": -2,
                },
                "validation_state": {
                    "total_validation_issues": -1,
                },
                "attention_flag_changes": {
                    "invalid_review_outputs": {"previous": True, "current": False},
                },
            },
        },
    )

    text = (tmp_path / "controller_update_note.md").read_text(encoding="utf-8")
    assert result["progress_signal"] == "improved"
    assert "## Progress Delta" in text
    assert "- progress_signal: improved" in text
    assert "- reviewed_candidates_delta: 2" in text
    assert "/tmp/progress_delta.json" in text
    assert "/tmp/reviewer_manifest.json" in text


def test_build_note_handles_missing_progress_delta(tmp_path: Path) -> None:
    build_note(
        output_path=tmp_path / "controller_update_note.md",
        controller_packet={
            "summary": {
                "recommended_action": "park",
                "reason": "no immediate review-plane action is pending",
            },
            "paths": {},
        },
        controller_action_plan={"steps": []},
        progress_delta=None,
    )

    text = (tmp_path / "controller_update_note.md").read_text(encoding="utf-8")
    assert "- available: False" in text
    assert "- progress_signal: -" in text
