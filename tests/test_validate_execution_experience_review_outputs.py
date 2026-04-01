from __future__ import annotations

import json
from pathlib import Path

from ops.validate_execution_experience_review_outputs import validate_review_outputs


def test_validate_review_outputs_reports_completeness_and_shape(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    candidates.write_text(
        json.dumps(
            [
                {"candidate_id": "execxp_a"},
                {"candidate_id": "execxp_b"},
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "reviewer_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "reviewers": [
                    {"reviewer": "gemini_no_mcp"},
                    {"reviewer": "claudeminmax"},
                    {"reviewer": "codex_auth_only"},
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    reviewer_a = tmp_path / "gemini_no_mcp.json"
    reviewer_a.write_text(
        json.dumps(
            {
                "items": [
                    {"candidate_id": "execxp_a", "decision": "accept"},
                    {"candidate_id": "execxp_b", "decision": "revise"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    reviewer_b = tmp_path / "claudeminmax.json"
    reviewer_b.write_text(
        json.dumps(
            {
                "items": [
                    {"candidate_id": "execxp_a", "decision": "reject"},
                    {"candidate_id": "execxp_unknown", "decision": "accept"},
                    {"candidate_id": "execxp_b", "decision": "maybe"},
                    {"candidate_id": "execxp_a", "decision": "accept"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = validate_review_outputs(
        candidates_path=candidates,
        review_json_paths=[reviewer_a, reviewer_b],
        reviewer_manifest_path=manifest,
        top_n=5,
    )

    assert summary["expected_reviewers"] == ["claudeminmax", "codex_auth_only", "gemini_no_mcp"]
    assert summary["provided_reviewers"] == ["claudeminmax", "gemini_no_mcp"]
    assert summary["missing_reviewers"] == ["codex_auth_only"]
    assert summary["coverage_by_review_count"] == {"1": 1, "2": 1}
    assert summary["structurally_valid"] is False
    assert summary["complete"] is False
    assert summary["unknown_candidate_items"] == 1
    assert summary["invalid_decision_items"] == 1
    assert summary["duplicate_candidate_items"] == 1
    assert summary["sample_unknown_candidate_items"][0]["candidate_id"] == "execxp_unknown"
    assert summary["sample_invalid_decision_items"][0]["decision"] == "maybe"
    assert summary["sample_duplicate_candidate_items"][0]["candidate_id"] == "execxp_a"


def test_validate_review_outputs_normalizes_reviewer_identity_from_payload(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    candidates.write_text(
        json.dumps([{"candidate_id": "execxp_a"}], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest = tmp_path / "reviewer_manifest.json"
    manifest.write_text(
        json.dumps(
            {"reviewers": [{"reviewer": "gemini_no_mcp"}]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    reviewer = tmp_path / "reviewer_temp_output.json"
    reviewer.write_text(
        json.dumps(
            {
                "reviewer": "gemini_no_mcp",
                "items": [{"candidate_id": "execxp_a", "decision": "accept"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = validate_review_outputs(
        candidates_path=candidates,
        review_json_paths=[reviewer],
        reviewer_manifest_path=manifest,
    )

    assert summary["provided_reviewers"] == ["gemini_no_mcp"]
    assert summary["missing_reviewers"] == []
    assert summary["unexpected_reviewers"] == []
    assert summary["complete"] is True
