from __future__ import annotations

from pathlib import Path

from ops.build_execution_experience_progress_delta import build_delta


def test_build_delta_marks_improvement_and_action_deescalation(tmp_path: Path) -> None:
    output = tmp_path / "progress_delta.json"
    previous = {
        "output_path": str(tmp_path / "previous_governance_snapshot.json"),
        "totals": {
            "total_candidates": 5,
            "reviewed_candidates": 1,
            "backlog_candidates": 4,
            "stale_reviewed_candidates": 1,
            "followup_candidates": 2,
        },
        "review_state": {
            "under_reviewed_candidates": 3,
            "disputed_candidates": 1,
            "deferred_candidates": 1,
        },
        "validation_state": {
            "available": True,
            "complete": False,
            "structurally_valid": False,
            "unknown_candidate_items": 1,
            "invalid_decision_items": 1,
            "duplicate_candidate_items": 0,
            "total_validation_issues": 2,
        },
        "queue_state": {
            "by_state": {"review_pending": 4},
            "by_action": {"fix_review_outputs": 1, "collect_missing_reviews": 3},
            "followup_by_branch": {"accept": 1, "revise": 1},
        },
        "attention_flags": {
            "backlog_open": True,
            "invalid_review_outputs": True,
            "followup_work_present": True,
        },
    }
    current = {
        "output_path": str(tmp_path / "current_governance_snapshot.json"),
        "totals": {
            "total_candidates": 5,
            "reviewed_candidates": 3,
            "backlog_candidates": 2,
            "stale_reviewed_candidates": 0,
            "followup_candidates": 1,
        },
        "review_state": {
            "under_reviewed_candidates": 1,
            "disputed_candidates": 0,
            "deferred_candidates": 0,
        },
        "validation_state": {
            "available": True,
            "complete": True,
            "structurally_valid": True,
            "unknown_candidate_items": 0,
            "invalid_decision_items": 0,
            "duplicate_candidate_items": 0,
            "total_validation_issues": 0,
        },
        "queue_state": {
            "by_state": {"review_pending": 2, "review_ready": 3},
            "by_action": {"collect_missing_reviews": 2, "route_followups": 1},
            "followup_by_branch": {"accept": 1},
        },
        "attention_flags": {
            "backlog_open": True,
            "invalid_review_outputs": False,
            "followup_work_present": True,
        },
    }
    previous_plan = {
        "output_path": str(tmp_path / "previous_controller_action_plan.json"),
        "recommended_action": "fix_review_outputs",
        "reason": "validation failed",
    }
    current_plan = {
        "output_path": str(tmp_path / "current_controller_action_plan.json"),
        "recommended_action": "collect_missing_reviews",
        "reason": "waiting for reviewer coverage",
    }

    result = build_delta(
        output_path=output,
        previous_governance_snapshot=previous,
        current_governance_snapshot=current,
        previous_controller_action_plan=previous_plan,
        current_controller_action_plan=current_plan,
    )

    assert output.exists()
    assert result["delta"]["totals"]["reviewed_candidates"] == 2
    assert result["delta"]["totals"]["backlog_candidates"] == -2
    assert result["delta"]["validation_state"]["total_validation_issues"] == -2
    assert result["delta"]["attention_flag_changes"]["invalid_review_outputs"] == {
        "previous": True,
        "current": False,
    }
    assert result["status"]["recommended_action_changed"] is True
    assert result["status"]["action_severity_delta"] == -1
    assert result["status"]["progress_signal"] == "improved"


def test_build_delta_marks_regression_when_backlog_and_severity_increase(tmp_path: Path) -> None:
    result = build_delta(
        output_path=tmp_path / "progress_delta.json",
        previous_governance_snapshot={
            "totals": {"reviewed_candidates": 3, "backlog_candidates": 1, "followup_candidates": 0},
            "review_state": {"under_reviewed_candidates": 0, "disputed_candidates": 0, "deferred_candidates": 0},
            "validation_state": {"total_validation_issues": 0},
            "queue_state": {"by_state": {"review_ready": 3}, "by_action": {"route_followups": 1}, "followup_by_branch": {}},
            "attention_flags": {"backlog_open": False, "invalid_review_outputs": False},
        },
        current_governance_snapshot={
            "totals": {"reviewed_candidates": 2, "backlog_candidates": 2, "followup_candidates": 0},
            "review_state": {"under_reviewed_candidates": 1, "disputed_candidates": 0, "deferred_candidates": 0},
            "validation_state": {"total_validation_issues": 1},
            "queue_state": {"by_state": {"review_pending": 2}, "by_action": {"fix_review_outputs": 1}, "followup_by_branch": {}},
            "attention_flags": {"backlog_open": True, "invalid_review_outputs": True},
        },
        previous_controller_action_plan={"recommended_action": "route_followups", "reason": "ready"},
        current_controller_action_plan={"recommended_action": "fix_review_outputs", "reason": "validation regressed"},
    )

    assert result["delta"]["totals"]["reviewed_candidates"] == -1
    assert result["delta"]["totals"]["backlog_candidates"] == 1
    assert result["status"]["action_severity_delta"] == 3
    assert result["status"]["progress_signal"] == "regressed"
