from __future__ import annotations

import csv
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.compose_execution_activity_review_decisions import FIELDNAMES as ACTIVITY_FIELDNAMES
from ops.run_execution_experience_review_cycle import run_cycle


def _write_execution_decisions(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ACTIVITY_FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _seed_db(path: Path) -> None:
    db = KnowledgeDB(str(path))
    db.init_schema()
    db.put_document(
        Document(
            doc_id="doc_exec",
            source="agent_activity",
            project="ChatgptREST",
            raw_ref="/tmp/doc_exec.json",
            title="doc_exec",
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_exec",
            doc_id="doc_exec",
            episode_type="workflow.completed",
            title="workflow.completed",
            summary="workflow.completed",
            start_ref="doc_exec:1",
            end_ref="doc_exec:1",
            time_start=1.0,
            time_end=1.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_exec",
            episode_id="ep_exec",
            atom_type="lesson",
            question="at_exec",
            answer="execution review cycle complete",
            canonical_question="activity: workflow.completed",
            status="candidate",
            promotion_status="staged",
            promotion_reason="activity_ingest",
            applicability=json.dumps({"task_ref": "issue-115", "trace_id": "trace-115"}, ensure_ascii=False, sort_keys=True),
            valid_from=1.0,
        )
    )
    db.commit()
    db.close()


def test_run_cycle_refresh_only_emits_manifest(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    decisions = tmp_path / "execution_review_decisions_v1.tsv"
    _write_execution_decisions(
        decisions,
        [
                {
                    "atom_id": "at_exec",
                    "lineage_family_id": "fam_exec",
                    "lineage_status": "complete",
                    "source": "agent_activity",
                    "episode_type": "workflow.completed",
                    "atom_type": "lesson",
                    "task_ref": "issue-115",
                    "trace_id": "trace-115",
                    "canonical_question": "activity: workflow.completed",
                    "suggested_bucket": "lesson",
                    "final_bucket": "lesson",
                    "lineage_action": "keep_lineage",
                    "experience_kind": "lesson",
                    "experience_title": "workflow lesson",
                    "experience_summary": "Reusable workflow lesson",
                    "reviewer": "reviewer-a",
                    "review_notes": "keep",
            }
        ],
    )

    payload = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "experience_cycle",
        activity_review_root=tmp_path / "activity_cycle",
        decisions_path=decisions,
        review_json_paths=[],
        base_experience_decisions_path=None,
        limit=50,
    )

    assert payload["mode"] == "refresh_only"
    assert payload["candidate_export"]["experience_candidates"] == 1
    manifest = payload["reviewer_manifest"]
    assert Path(manifest["manifest_path"]).exists()
    reviewers = {item["reviewer"] for item in manifest["reviewers"]}
    assert reviewers == {"gemini_no_mcp", "claudeminmax", "codex_auth_only"}
    assert payload["review_backlog"]["backlog_candidates"] == 1
    assert payload["review_backlog"]["reviewed_candidates"] == 0
    assert Path(payload["review_backlog_path"]).exists()
    assert Path(payload["review_decision_scaffold_path"]).exists()
    assert payload["review_decision_scaffold"]["by_governance_state"] == {"review_pending": 1}
    assert Path(payload["governance_queue_summary_path"]).exists()
    assert payload["governance_queues"]["by_state"] == {"review_pending": 1}
    assert Path(payload["revision_worklist_path"]).exists()
    assert payload["revision_worklist"]["total_revise_candidates"] == 0
    assert Path(payload["acceptance_pack_manifest_path"]).exists()
    assert payload["acceptance_pack"]["accepted_candidates"] == 0
    assert Path(payload["deferred_revisit_queue_path"]).exists()
    assert payload["deferred_revisit_queue"]["total_deferred_candidates"] == 0
    assert Path(payload["rejected_archive_queue_path"]).exists()
    assert payload["rejected_archive_queue"]["total_rejected_candidates"] == 0
    assert Path(payload["followup_manifest_path"]).exists()
    assert payload["followup_manifest"]["total_followup_candidates"] == 0
    assert Path(payload["governance_snapshot_path"]).exists()
    assert payload["governance_snapshot"]["validation_state"]["available"] is False
    assert payload["governance_snapshot"]["attention_flags"]["backlog_open"] is True
    assert Path(payload["attention_manifest_path"]).exists()
    assert payload["attention_manifest"]["review"]["validation_available"] is False
    assert payload["attention_manifest"]["followup"]["total_candidates"] == 0
    assert Path(payload["review_brief_path"]).exists()
    assert "## Totals" in Path(payload["review_brief_path"]).read_text(encoding="utf-8")
    assert Path(payload["review_reply_draft_path"]).exists()
    assert payload["review_reply_draft"]["recommended_action"] == "collect_missing_reviews"
    assert Path(payload["controller_packet_path"]).exists()
    assert payload["controller_packet"]["summary"]["recommended_action"] == "collect_missing_reviews"
    assert Path(payload["controller_action_plan_path"]).exists()
    assert payload["controller_action_plan"]["recommended_action"] == "collect_missing_reviews"
    assert payload["progress_delta"] is None
    assert payload["progress_delta_path"] == ""
    assert Path(payload["controller_update_note_path"]).exists()
    assert "## Progress Delta" in Path(payload["controller_update_note_path"]).read_text(encoding="utf-8")
    assert Path(payload["controller_rollup_manifest_path"]).exists()
    assert payload["controller_rollup_manifest"]["availability"]["progress_delta"] is False
    assert Path(payload["controller_reply_packet_path"]).exists()
    assert payload["controller_reply_packet"]["decision"]["manual_send_required"] is True


def test_run_cycle_refresh_only_emits_revision_worklist_from_existing_decisions(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    decisions = tmp_path / "execution_review_decisions_v1.tsv"
    _write_execution_decisions(
        decisions,
        [
            {
                "atom_id": "at_exec",
                "lineage_family_id": "fam_exec",
                "lineage_status": "complete",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "atom_type": "lesson",
                "task_ref": "issue-115",
                "trace_id": "trace-115",
                "canonical_question": "activity: workflow.completed",
                "suggested_bucket": "lesson",
                "final_bucket": "lesson",
                "lineage_action": "keep_lineage",
                "experience_kind": "lesson",
                "experience_title": "workflow lesson",
                "experience_summary": "Reusable workflow lesson",
                "reviewer": "reviewer-a",
                "review_notes": "keep",
            }
        ],
    )
    experience_decisions = tmp_path / "execution_experience_review_decisions_v1.tsv"
    with experience_decisions.open("w", encoding="utf-8", newline="") as fh:
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
                "candidate_id": "execxp_at_exec",
                "atom_id": "at_exec",
                "lineage_family_id": "fam_exec",
                "lineage_status": "complete",
                "task_ref": "issue-115",
                "trace_id": "trace-115",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "experience_kind": "lesson",
                "title": "workflow lesson",
                "summary": "Tighten wording before accept",
                "review_decision": "revise",
                "groundedness": "medium",
                "time_sensitivity": "versioned",
                "reviewers": "[]",
            }
        )

    payload = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "experience_cycle",
        activity_review_root=tmp_path / "activity_cycle",
        decisions_path=decisions,
        review_json_paths=[],
        base_experience_decisions_path=experience_decisions,
        limit=50,
    )

    assert payload["review_backlog"]["reviewed_candidates"] == 1
    assert payload["review_decision_scaffold"]["by_governance_action"] == {"collect_missing_reviews": 1}
    assert payload["revision_worklist"]["total_revise_candidates"] == 1
    assert Path(payload["revision_worklist_path"]).exists()
    assert payload["acceptance_pack"]["accepted_candidates"] == 0
    assert payload["deferred_revisit_queue"]["total_deferred_candidates"] == 0
    assert payload["rejected_archive_queue"]["total_rejected_candidates"] == 0
    assert payload["followup_manifest"]["branches"]["revise"]["candidates"] == 1
    assert Path(payload["governance_snapshot_path"]).exists()
    assert payload["governance_snapshot"]["queue_state"]["followup_by_branch"]["revise"] == 1
    assert Path(payload["attention_manifest_path"]).exists()
    assert payload["attention_manifest"]["followup"]["routes"]["revise"]["candidates"] == 1
    assert Path(payload["review_brief_path"]).exists()
    assert "revise" in Path(payload["review_brief_path"]).read_text(encoding="utf-8")
    assert Path(payload["review_reply_draft_path"]).exists()
    assert payload["review_reply_draft"]["recommended_action"] == "collect_missing_reviews"
    assert Path(payload["controller_packet_path"]).exists()
    assert payload["controller_packet"]["followup"]["total_candidates"] == 1
    assert Path(payload["controller_action_plan_path"]).exists()
    assert payload["controller_action_plan"]["recommended_action"] == "collect_missing_reviews"
    assert payload["progress_delta"] is None
    assert payload["progress_delta_path"] == ""
    assert Path(payload["controller_update_note_path"]).exists()
    assert Path(payload["controller_rollup_manifest_path"]).exists()
    assert Path(payload["controller_reply_packet_path"]).exists()


def test_run_cycle_refresh_only_emits_progress_delta_when_previous_cycle_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    decisions = tmp_path / "execution_review_decisions_v1.tsv"
    _write_execution_decisions(
        decisions,
        [
            {
                "atom_id": "at_exec",
                "lineage_family_id": "fam_exec",
                "lineage_status": "complete",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "atom_type": "lesson",
                "task_ref": "issue-115",
                "trace_id": "trace-115",
                "canonical_question": "activity: workflow.completed",
                "suggested_bucket": "lesson",
                "final_bucket": "lesson",
                "lineage_action": "keep_lineage",
                "experience_kind": "lesson",
                "experience_title": "workflow lesson",
                "experience_summary": "Reusable workflow lesson",
                "reviewer": "reviewer-a",
                "review_notes": "keep",
            }
        ],
    )

    first = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "experience_cycle",
        activity_review_root=tmp_path / "activity_cycle",
        decisions_path=decisions,
        review_json_paths=[],
        base_experience_decisions_path=None,
        limit=50,
    )
    second = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "experience_cycle",
        activity_review_root=tmp_path / "activity_cycle",
        decisions_path=decisions,
        review_json_paths=[],
        base_experience_decisions_path=None,
        limit=50,
    )

    assert first["progress_delta"] is None
    assert Path(second["progress_delta_path"]).exists()
    assert second["progress_delta"]["status"]["progress_signal"] == "unchanged"
    assert second["progress_delta"]["status"]["recommended_action_changed"] is False
    assert Path(second["controller_update_note_path"]).exists()
    assert "- progress_signal: unchanged" in Path(second["controller_update_note_path"]).read_text(encoding="utf-8")
    assert Path(second["controller_rollup_manifest_path"]).exists()
    assert second["controller_rollup_manifest"]["summary"]["progress_signal"] == "unchanged"
    assert Path(second["controller_reply_packet_path"]).exists()
    assert second["controller_reply_packet"]["decision"]["reply_kind"] == "missing_review_request"


def test_run_cycle_merge_materializes_reviewed_candidates(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    decisions = tmp_path / "execution_review_decisions_v1.tsv"
    _write_execution_decisions(
        decisions,
        [
                {
                    "atom_id": "at_exec",
                    "lineage_family_id": "fam_exec",
                    "lineage_status": "complete",
                    "source": "agent_activity",
                    "episode_type": "workflow.completed",
                    "atom_type": "lesson",
                    "task_ref": "issue-115",
                    "trace_id": "trace-115",
                    "canonical_question": "activity: workflow.completed",
                    "suggested_bucket": "lesson",
                    "final_bucket": "lesson",
                    "lineage_action": "keep_lineage",
                    "experience_kind": "lesson",
                    "experience_title": "workflow lesson",
                    "experience_summary": "Reusable workflow lesson",
                    "reviewer": "reviewer-a",
                    "review_notes": "keep",
            }
        ],
    )
    first = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "experience_cycle",
        activity_review_root=tmp_path / "activity_cycle",
        decisions_path=decisions,
        review_json_paths=[],
        base_experience_decisions_path=None,
        limit=50,
    )
    manifest_dir = Path(first["reviewer_manifest"]["review_output_dir"])
    review_output = manifest_dir / "gemini_no_mcp.json"
    review_output.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "candidate_id": "execxp_at_exec",
                        "decision": "accept",
                        "experience_kind": "lesson",
                        "title": "workflow lesson",
                        "summary": "Reusable workflow lesson",
                        "groundedness": "high",
                        "time_sensitivity": "evergreen",
                        "note": "keep",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    second = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "experience_cycle",
        activity_review_root=tmp_path / "activity_cycle",
        decisions_path=decisions,
        review_json_paths=[review_output],
        base_experience_decisions_path=None,
        limit=50,
    )

    assert second["mode"] == "refresh_merge_only"
    assert Path(second["full_output"]).exists()
    assert Path(second["review_output_validation_path"]).exists()
    assert second["compose_summary"]["accepted_candidates"] == 1
    assert second["reviewed_candidates"]["accepted_candidates"] == 1
    assert second["review_backlog"]["reviewed_candidates"] == 1
    assert second["review_backlog"]["backlog_candidates"] == 0
    assert second["review_output_validation"]["structurally_valid"] is True
    assert second["review_output_validation"]["complete"] is False
    assert Path(second["review_decision_scaffold_path"]).exists()
    assert second["review_decision_scaffold"]["by_governance_state"] == {"under_reviewed": 1}
    assert second["review_decision_scaffold"]["by_governance_action"] == {"collect_missing_reviews": 1}
    assert Path(second["governance_queue_summary_path"]).exists()
    assert second["governance_queues"]["by_state"] == {"under_reviewed": 1}
    assert Path(second["revision_worklist_path"]).exists()
    assert second["revision_worklist"]["total_revise_candidates"] == 0
    assert Path(second["acceptance_pack_manifest_path"]).exists()
    assert second["acceptance_pack"]["accepted_candidates"] == 1
    assert Path(second["deferred_revisit_queue_path"]).exists()
    assert second["deferred_revisit_queue"]["total_deferred_candidates"] == 0
    assert Path(second["rejected_archive_queue_path"]).exists()
    assert second["rejected_archive_queue"]["total_rejected_candidates"] == 0
    assert Path(second["followup_manifest_path"]).exists()
    assert second["followup_manifest"]["branches"]["accept"]["candidates"] == 1
    assert Path(second["governance_snapshot_path"]).exists()
    assert second["governance_snapshot"]["validation_state"]["available"] is True
    assert second["governance_snapshot"]["queue_state"]["followup_by_branch"]["accept"] == 1
    assert second["governance_snapshot"]["attention_flags"]["followup_work_present"] is True
    assert Path(second["attention_manifest_path"]).exists()
    assert second["attention_manifest"]["review"]["validation_available"] is True
    assert second["attention_manifest"]["followup"]["routes"]["accept"]["candidates"] == 1
    assert Path(second["review_brief_path"]).exists()
    assert "structurally_valid: True" in Path(second["review_brief_path"]).read_text(encoding="utf-8")
    assert Path(second["review_reply_draft_path"]).exists()
    assert second["review_reply_draft"]["recommended_action"] == "collect_missing_reviews"
    assert Path(second["controller_packet_path"]).exists()
    assert second["controller_packet"]["summary"]["recommended_action"] == "collect_missing_reviews"
    assert Path(second["controller_action_plan_path"]).exists()
    assert second["controller_action_plan"]["recommended_action"] == "collect_missing_reviews"
    assert Path(second["progress_delta_path"]).exists()
    assert second["progress_delta"]["delta"]["totals"]["reviewed_candidates"] == 1
    assert second["progress_delta"]["delta"]["totals"]["backlog_candidates"] == -1
    assert second["progress_delta"]["status"]["progress_signal"] == "improved"
    assert Path(second["controller_update_note_path"]).exists()
    assert "- progress_signal: improved" in Path(second["controller_update_note_path"]).read_text(encoding="utf-8")
    assert Path(second["controller_rollup_manifest_path"]).exists()
    assert second["controller_rollup_manifest"]["summary"]["progress_signal"] == "improved"
    assert Path(second["controller_reply_packet_path"]).exists()
    assert "progress_signal=improved" in second["controller_reply_packet"]["reply"]["comment_markdown"]


def test_run_cycle_can_fail_fast_on_incomplete_reviews(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    decisions = tmp_path / "execution_review_decisions_v1.tsv"
    _write_execution_decisions(
        decisions,
        [
            {
                "atom_id": "at_exec",
                "lineage_family_id": "fam_exec",
                "lineage_status": "complete",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "atom_type": "lesson",
                "task_ref": "issue-115",
                "trace_id": "trace-115",
                "canonical_question": "activity: workflow.completed",
                "suggested_bucket": "lesson",
                "final_bucket": "lesson",
                "lineage_action": "keep_lineage",
                "experience_kind": "lesson",
                "experience_title": "workflow lesson",
                "experience_summary": "Reusable workflow lesson",
                "reviewer": "reviewer-a",
                "review_notes": "keep",
            }
        ],
    )
    first = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "experience_cycle",
        activity_review_root=tmp_path / "activity_cycle",
        decisions_path=decisions,
        review_json_paths=[],
        base_experience_decisions_path=None,
        limit=50,
    )
    manifest_dir = Path(first["reviewer_manifest"]["review_output_dir"])
    review_output = manifest_dir / "gemini_no_mcp.json"
    review_output.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "candidate_id": "execxp_at_exec",
                        "decision": "accept",
                        "experience_kind": "lesson",
                        "title": "workflow lesson",
                        "summary": "Reusable workflow lesson",
                        "groundedness": "high",
                        "time_sensitivity": "evergreen",
                        "note": "keep",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    try:
        run_cycle(
            db_path=db_path,
            output_root=tmp_path / "experience_cycle",
            activity_review_root=tmp_path / "activity_cycle",
            decisions_path=decisions,
            review_json_paths=[review_output],
            base_experience_decisions_path=None,
            limit=50,
            require_complete_reviews=True,
        )
    except RuntimeError as exc:
        assert "review outputs incomplete" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for incomplete reviews")

    latest = sorted((tmp_path / "experience_cycle").iterdir())[-1]
    summary = json.loads((latest / "cycle_summary.json").read_text(encoding="utf-8"))
    assert summary["ok"] is False
    assert summary["mode"] == "validation_failed"
    assert summary["validation_errors"]
    assert Path(summary["governance_snapshot_path"]).exists()
    assert summary["governance_snapshot"]["validation_state"]["complete"] is False
    assert Path(summary["attention_manifest_path"]).exists()
    assert summary["attention_manifest"]["review"]["validation_complete"] is False
    assert Path(summary["review_brief_path"]).exists()
    assert "complete: False" in Path(summary["review_brief_path"]).read_text(encoding="utf-8")
    assert Path(summary["review_reply_draft_path"]).exists()
    assert summary["review_reply_draft"]["recommended_action"] == "collect_missing_reviews"
    assert Path(summary["controller_packet_path"]).exists()
    assert summary["controller_packet"]["summary"]["recommended_action"] == "collect_missing_reviews"
    assert Path(summary["controller_action_plan_path"]).exists()
    assert summary["controller_action_plan"]["recommended_action"] == "collect_missing_reviews"
    assert Path(summary["progress_delta_path"]).exists()
    assert summary["progress_delta"]["status"]["progress_signal"] == "unchanged"
    assert Path(summary["controller_update_note_path"]).exists()
    assert Path(summary["controller_rollup_manifest_path"]).exists()
    assert Path(summary["controller_reply_packet_path"]).exists()


def test_run_cycle_can_fail_fast_on_invalid_reviews(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    decisions = tmp_path / "execution_review_decisions_v1.tsv"
    _write_execution_decisions(
        decisions,
        [
            {
                "atom_id": "at_exec",
                "lineage_family_id": "fam_exec",
                "lineage_status": "complete",
                "source": "agent_activity",
                "episode_type": "workflow.completed",
                "atom_type": "lesson",
                "task_ref": "issue-115",
                "trace_id": "trace-115",
                "canonical_question": "activity: workflow.completed",
                "suggested_bucket": "lesson",
                "final_bucket": "lesson",
                "lineage_action": "keep_lineage",
                "experience_kind": "lesson",
                "experience_title": "workflow lesson",
                "experience_summary": "Reusable workflow lesson",
                "reviewer": "reviewer-a",
                "review_notes": "keep",
            }
        ],
    )
    first = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "experience_cycle",
        activity_review_root=tmp_path / "activity_cycle",
        decisions_path=decisions,
        review_json_paths=[],
        base_experience_decisions_path=None,
        limit=50,
    )
    manifest_dir = Path(first["reviewer_manifest"]["review_output_dir"])
    review_output = manifest_dir / "gemini_no_mcp.json"
    review_output.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "candidate_id": "execxp_at_exec",
                        "decision": "maybe",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    try:
        run_cycle(
            db_path=db_path,
            output_root=tmp_path / "experience_cycle",
            activity_review_root=tmp_path / "activity_cycle",
            decisions_path=decisions,
            review_json_paths=[review_output],
            base_experience_decisions_path=None,
            limit=50,
            require_valid_reviews=True,
        )
    except RuntimeError as exc:
        assert "structural validation" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for invalid reviews")

    latest = sorted((tmp_path / "experience_cycle").iterdir())[-1]
    summary = json.loads((latest / "cycle_summary.json").read_text(encoding="utf-8"))
    assert summary["ok"] is False
    assert summary["mode"] == "validation_failed"
    assert summary["review_output_validation"]["invalid_decision_items"] == 1
    assert Path(summary["governance_snapshot_path"]).exists()
    assert summary["governance_snapshot"]["attention_flags"]["invalid_review_outputs"] is True
    assert Path(summary["attention_manifest_path"]).exists()
    assert summary["attention_manifest"]["review"]["validation_structurally_valid"] is False
    assert Path(summary["review_brief_path"]).exists()
    assert "total_validation_issues: 1" in Path(summary["review_brief_path"]).read_text(encoding="utf-8")
    assert Path(summary["review_reply_draft_path"]).exists()
    assert summary["review_reply_draft"]["recommended_action"] == "fix_review_outputs"
    assert Path(summary["controller_packet_path"]).exists()
    assert summary["controller_packet"]["summary"]["recommended_action"] == "fix_review_outputs"
    assert Path(summary["controller_action_plan_path"]).exists()
    assert summary["controller_action_plan"]["recommended_action"] == "fix_review_outputs"
    assert Path(summary["progress_delta_path"]).exists()
    assert summary["progress_delta"]["status"]["recommended_action_changed"] is True
    assert summary["progress_delta"]["status"]["progress_signal"] == "regressed"
    assert Path(summary["controller_update_note_path"]).exists()
    assert "- progress_signal: regressed" in Path(summary["controller_update_note_path"]).read_text(encoding="utf-8")
    assert Path(summary["controller_rollup_manifest_path"]).exists()
    assert summary["controller_rollup_manifest"]["summary"]["progress_signal"] == "regressed"
    assert Path(summary["controller_reply_packet_path"]).exists()
    assert summary["controller_reply_packet"]["decision"]["reply_kind"] == "review_repair_request"
