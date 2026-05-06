from __future__ import annotations

import csv
import json
from pathlib import Path

from ops.build_execution_experience_review_decision_scaffold import build_scaffold


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def test_build_scaffold_marks_pending_candidates_without_decisions(tmp_path: Path) -> None:
    candidates = tmp_path / "experience_candidates.json"
    candidates.write_text(
        json.dumps(
            [
                {
                    "candidate_id": "execxp_a",
                    "atom_id": "at_a",
                    "lineage_family_id": "fam_a",
                    "lineage_status": "complete",
                    "source": "agent_activity",
                    "episode_type": "workflow.completed",
                    "experience_kind": "lesson",
                    "title": "workflow lesson",
                    "summary": "Reusable workflow lesson",
                }
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
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "review_decision_scaffold.tsv"

    summary = build_scaffold(candidates_path=candidates, reviewer_manifest_path=manifest, output_tsv=output)
    rows = _read_rows(output)

    assert summary["total_candidates"] == 1
    assert summary["by_governance_state"] == {"review_pending": 1}
    assert summary["by_governance_action"] == {"collect_reviews": 1}
    assert rows[0]["candidate_id"] == "execxp_a"
    assert rows[0]["provided_reviewers"] == ""
    assert rows[0]["missing_reviewers"] == "claudeminmax,gemini_no_mcp"
    assert rows[0]["suggested_governance_state"] == "review_pending"
    assert rows[0]["suggested_governance_action"] == "collect_reviews"


def test_build_scaffold_marks_decision_ready_candidates_from_complete_reviews(tmp_path: Path) -> None:
    candidates = tmp_path / "experience_candidates.json"
    candidates.write_text(
        json.dumps(
            [{"candidate_id": "execxp_a", "atom_id": "at_a", "experience_kind": "lesson", "title": "workflow lesson"}],
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
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    decisions = tmp_path / "execution_experience_review_decisions_v1.tsv"
    with decisions.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "candidate_id",
                "atom_id",
                "lineage_family_id",
                "lineage_status",
                "task_ref",
                "trace_id",
                "source",
                "episode_type",
                "experience_kind",
                "title",
                "summary",
                "review_decision",
                "groundedness",
                "time_sensitivity",
                "reviewers",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "candidate_id": "execxp_a",
                "atom_id": "at_a",
                "lineage_family_id": "fam_a",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-115",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "experience_kind": "lesson",
                "title": "workflow lesson",
                "summary": "Reusable workflow lesson",
                "review_decision": "accept",
                "groundedness": "high",
                "time_sensitivity": "evergreen",
                "reviewers": json.dumps(
                    [
                        {"reviewer": "gemini_no_mcp", "decision": "accept"},
                        {"reviewer": "claudeminmax", "decision": "accept"},
                    ],
                    ensure_ascii=False,
                ),
            }
        )
    output = tmp_path / "review_decision_scaffold.tsv"

    summary = build_scaffold(
        candidates_path=candidates,
        decisions_path=decisions,
        reviewer_manifest_path=manifest,
        output_tsv=output,
    )
    rows = _read_rows(output)

    assert summary["decision_ready_candidates"] == 1
    assert summary["by_governance_state"] == {"decision_ready": 1}
    assert summary["by_governance_action"] == {"accept_candidate": 1}
    assert rows[0]["review_decision"] == "accept"
    assert rows[0]["provided_reviewers"] == "claudeminmax,gemini_no_mcp"
    assert rows[0]["missing_reviewers"] == ""
    assert rows[0]["suggested_governance_state"] == "decision_ready"
    assert rows[0]["suggested_governance_action"] == "accept_candidate"
