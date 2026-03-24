from __future__ import annotations

import csv
import json
from pathlib import Path

from ops.compose_execution_experience_review_decisions import FIELDNAMES
from ops.report_execution_experience_review_backlog import report_backlog


def _write_decisions(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_report_backlog_refresh_only_manifest_state(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    candidates.write_text(
        json.dumps(
            [
                {"candidate_id": "execxp_a", "experience_kind": "lesson", "source": "agent_activity", "episode_type": "workflow.completed", "lineage_status": "complete"},
                {"candidate_id": "execxp_b", "experience_kind": "procedure", "source": "agent_activity", "episode_type": "workflow.completed", "lineage_status": "complete"},
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

    summary = report_backlog(candidates_path=candidates, reviewer_manifest_path=manifest, top_n=3)

    assert summary["total_candidates"] == 2
    assert summary["reviewed_candidates"] == 0
    assert summary["backlog_candidates"] == 2
    assert summary["expected_reviewers"] == ["claudeminmax", "codex_auth_only", "gemini_no_mcp"]
    assert summary["coverage_by_review_count"] == {"0": 2}
    assert summary["under_reviewed_candidates"] == 2
    assert summary["backlog_by_kind"] == {"lesson": 1, "procedure": 1}


def test_report_backlog_tracks_disputes_and_stale_rows(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    candidates.write_text(
        json.dumps(
            [
                {"candidate_id": "execxp_a", "experience_kind": "lesson", "source": "agent_activity", "episode_type": "workflow.completed", "lineage_status": "complete"},
                {"candidate_id": "execxp_b", "experience_kind": "procedure", "source": "agent_activity", "episode_type": "workflow.completed", "lineage_status": "partial"},
                {"candidate_id": "execxp_c", "experience_kind": "correction", "source": "agent_activity", "episode_type": "workflow.completed", "lineage_status": "minimal"},
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

    decisions = tmp_path / "execution_experience_review_decisions_v1.tsv"
    _write_decisions(
        decisions,
        [
            {
                "candidate_id": "execxp_a",
                "atom_id": "at_a",
                "lineage_family_id": "fam_a",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-a",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "experience_kind": "lesson",
                "title": "Lesson A",
                "summary": "Summary A",
                "review_decision": "defer",
                "groundedness": "medium",
                "time_sensitivity": "versioned",
                "reviewers": json.dumps(
                    [
                        {"reviewer": "gemini_no_mcp", "decision": "accept"},
                        {"reviewer": "claudeminmax", "decision": "reject"},
                    ],
                    ensure_ascii=False,
                ),
            },
            {
                "candidate_id": "execxp_b",
                "atom_id": "at_b",
                "lineage_family_id": "fam_b",
                "lineage_status": "partial",
                "task_ref": "issue-115",
                "trace_id": "trace-b",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "experience_kind": "procedure",
                "title": "Procedure B",
                "summary": "Summary B",
                "review_decision": "accept",
                "groundedness": "high",
                "time_sensitivity": "evergreen",
                "reviewers": json.dumps(
                    [
                        {"reviewer": "gemini_no_mcp", "decision": "accept"},
                        {"reviewer": "claudeminmax", "decision": "accept"},
                        {"reviewer": "codex_auth_only", "decision": "accept"},
                    ],
                    ensure_ascii=False,
                ),
            },
            {
                "candidate_id": "execxp_old",
                "atom_id": "at_old",
                "lineage_family_id": "fam_old",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-old",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "experience_kind": "lesson",
                "title": "Old",
                "summary": "Old",
                "review_decision": "accept",
                "groundedness": "high",
                "time_sensitivity": "evergreen",
                "reviewers": "[]",
            },
        ],
    )

    summary = report_backlog(
        candidates_path=candidates,
        decisions_path=decisions,
        reviewer_manifest_path=manifest,
        top_n=3,
    )

    assert summary["total_candidates"] == 3
    assert summary["reviewed_candidates"] == 2
    assert summary["backlog_candidates"] == 1
    assert summary["stale_reviewed_candidates"] == 1
    assert summary["reviewed_by_decision"] == {"accept": 1, "defer": 1}
    assert summary["coverage_by_review_count"] == {"0": 1, "2": 1, "3": 1}
    assert summary["under_reviewed_candidates"] == 2
    assert summary["disputed_candidates"] == 1
    assert summary["deferred_candidates"] == 1
    assert summary["backlog_by_kind"] == {"correction": 1}
    assert summary["sample_backlog_candidates"][0]["candidate_id"] == "execxp_c"
    assert summary["sample_disputed_candidates"][0]["candidate_id"] == "execxp_a"
