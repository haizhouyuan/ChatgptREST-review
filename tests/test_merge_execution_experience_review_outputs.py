from __future__ import annotations

import csv
import json
from pathlib import Path

from ops.compose_execution_experience_review_decisions import FIELDNAMES
from ops.merge_execution_experience_review_outputs import materialize_reviewed_candidates, merge_review_outputs


def _write_decisions(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_merge_review_outputs_and_materialize_reviewed_candidates(tmp_path: Path) -> None:
    candidates_path = tmp_path / "experience_candidates.json"
    candidates_path.write_text(
        json.dumps(
            [
                {
                    "candidate_id": "execxp_at_1",
                    "atom_id": "at_1",
                    "lineage_family_id": "fam_1",
                    "lineage_status": "complete",
                    "task_ref": "issue-115",
                    "trace_id": "trace-115",
                    "source": "agent_activity",
                    "episode_type": "workflow.completed",
                    "experience_kind": "lesson",
                    "title": "workflow lesson",
                    "summary": "A reusable workflow lesson.",
                    "review_notes": "from atom review",
                },
                {
                    "candidate_id": "execxp_at_2",
                    "atom_id": "at_2",
                    "lineage_family_id": "fam_2",
                    "lineage_status": "complete",
                    "task_ref": "issue-115",
                    "trace_id": "trace-116",
                    "source": "agent_activity",
                    "episode_type": "tool.completed",
                    "experience_kind": "procedure",
                    "title": "revision candidate",
                    "summary": "Needs controlled rewrite.",
                    "review_notes": "from atom review",
                },
            ],
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
                    {
                        "candidate_id": "execxp_at_1",
                        "decision": "accept",
                        "experience_kind": "lesson",
                        "title": "workflow lesson",
                        "summary": "Reusable lesson",
                        "groundedness": "high",
                        "time_sensitivity": "evergreen",
                        "note": "clear",
                    }
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
                    {
                        "candidate_id": "execxp_at_1",
                        "decision": "revise",
                        "experience_kind": "lesson",
                        "title": "workflow lesson",
                        "summary": "Reusable lesson",
                        "groundedness": "medium",
                        "time_sensitivity": "evergreen",
                        "note": "tighten wording",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    delta = tmp_path / "delta.tsv"
    summary = merge_review_outputs(
        candidates_path=candidates_path,
        review_json_paths=[reviewer_a, reviewer_b],
        output_path=delta,
    )

    assert summary["reviewed_candidates"] == 1
    decisions = list(csv.DictReader(delta.open("r", encoding="utf-8", newline=""), delimiter="\t"))
    assert decisions[0]["review_decision"] == "defer"

    _write_decisions(
        tmp_path / "full.tsv",
        [
            {
                "candidate_id": "execxp_at_1",
                "atom_id": "at_1",
                "lineage_family_id": "fam_1",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-115",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "experience_kind": "lesson",
                "title": "workflow lesson",
                "summary": "Reusable lesson",
                "review_decision": "accept",
                "groundedness": "high",
                "time_sensitivity": "evergreen",
                "reviewers": "[]",
            },
            {
                "candidate_id": "execxp_at_2",
                "atom_id": "at_2",
                "lineage_family_id": "fam_2",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-116",
                "source": "agent_activity",
                "episode_type": "tool.completed",
                "experience_kind": "procedure",
                "title": "revision candidate",
                "summary": "Needs controlled rewrite.",
                "review_decision": "revise",
                "groundedness": "medium",
                "time_sensitivity": "versioned",
                "reviewers": "[]",
            }
        ],
    )
    materialized = materialize_reviewed_candidates(
        candidates_path=candidates_path,
        decisions_path=tmp_path / "full.tsv",
        output_dir=tmp_path / "reviewed",
    )
    assert materialized["accepted_candidates"] == 2
    accepted = json.loads((tmp_path / "reviewed" / "accepted_review_candidates.json").read_text(encoding="utf-8"))
    assert {row["candidate_id"] for row in accepted} == {"execxp_at_1", "execxp_at_2"}
    accept_rows = json.loads((tmp_path / "reviewed" / "by_decision" / "accept.json").read_text(encoding="utf-8"))
    revise_rows = json.loads((tmp_path / "reviewed" / "by_decision" / "revise.json").read_text(encoding="utf-8"))
    assert accept_rows[0]["candidate_id"] == "execxp_at_1"
    assert revise_rows[0]["candidate_id"] == "execxp_at_2"
    assert set(materialized["decision_files"]) == {"accept", "revise"}


def test_merge_review_outputs_normalizes_reviewer_identity_from_manifest(tmp_path: Path) -> None:
    candidates_path = tmp_path / "experience_candidates.json"
    candidates_path.write_text(
        json.dumps(
            [
                {
                    "candidate_id": "execxp_at_1",
                    "atom_id": "at_1",
                    "lineage_family_id": "fam_1",
                    "lineage_status": "complete",
                    "task_ref": "issue-115",
                    "trace_id": "trace-115",
                    "source": "agent_activity",
                    "episode_type": "workflow.completed",
                    "experience_kind": "lesson",
                    "title": "workflow lesson",
                    "summary": "A reusable workflow lesson.",
                    "review_notes": "from atom review",
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
                "items": [
                    {
                        "candidate_id": "execxp_at_1",
                        "decision": "accept",
                        "experience_kind": "lesson",
                        "title": "workflow lesson",
                        "summary": "Reusable lesson",
                        "groundedness": "high",
                        "time_sensitivity": "evergreen",
                        "note": "clear",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    delta = tmp_path / "delta.tsv"
    merge_review_outputs(
        candidates_path=candidates_path,
        review_json_paths=[reviewer],
        output_path=delta,
        reviewer_manifest_path=manifest,
    )

    decisions = list(csv.DictReader(delta.open("r", encoding="utf-8", newline=""), delimiter="\t"))
    reviewers = json.loads(decisions[0]["reviewers"])
    assert reviewers[0]["reviewer"] == "gemini_no_mcp"
