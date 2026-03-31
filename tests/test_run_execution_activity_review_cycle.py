from __future__ import annotations

import csv
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.compose_execution_activity_review_decisions import FIELDNAMES
from ops.run_execution_activity_review_cycle import run_cycle


def _write_decisions(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_run_cycle_writes_expected_artifacts(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
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
            episode_type="team.run.completed",
            title="team.run.completed",
            summary="team.run.completed",
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
            canonical_question="activity: team.run.completed",
            status="candidate",
            promotion_status="staged",
            promotion_reason="activity_ingest",
            applicability=json.dumps(
                {"task_ref": "issue-114", "trace_id": "trace-114"},
                ensure_ascii=False,
                sort_keys=True,
            ),
            valid_from=1.0,
        )
    )
    db.commit()
    db.close()

    output_root = tmp_path / "cycle"
    summary = run_cycle(db_path=db_path, output_root=output_root)

    out = Path(summary["output_dir"])
    assert summary["selected_atoms"] == 1
    assert (out / "state_audit.json").exists()
    assert (out / "review_queue.json").exists()
    assert (out / "lineage" / "lineage_family_registry.tsv").exists()
    assert (out / "summary.json").exists()
    assert (out / "bundle" / "review_queue.json").exists()
    assert (out / "bundle" / "review_decisions_template.tsv").exists()
    assert summary["lineage_families"] == 1
    assert summary["merged_decisions_path"] == ""


def test_run_cycle_merges_decisions_and_exports_experience_candidates(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
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
            applicability=json.dumps(
                {"task_ref": "issue-115", "trace_id": "trace-115"},
                ensure_ascii=False,
                sort_keys=True,
            ),
            valid_from=1.0,
        )
    )
    db.commit()
    db.close()

    baseline_root = tmp_path / "cycle"
    first = run_cycle(db_path=db_path, output_root=baseline_root)
    first_dir = Path(first["output_dir"])
    baseline_decisions = first_dir / "execution_review_decisions_v1.tsv"
    _write_decisions(
        baseline_decisions,
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
                "final_bucket": "review_only",
                "lineage_action": "keep_lineage",
                "experience_kind": "",
                "experience_title": "",
                "experience_summary": "",
                "reviewer": "reviewer-a",
                "review_notes": "hold",
            }
        ],
    )

    delta = tmp_path / "delta.tsv"
    _write_decisions(
        delta,
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
                "experience_title": "",
                "experience_summary": "",
                "reviewer": "reviewer-b",
                "review_notes": "promote to lesson candidate",
            }
        ],
    )

    second = run_cycle(db_path=db_path, output_root=baseline_root, review_decisions_path=delta)
    merged = Path(second["merged_decisions_path"])

    assert merged.exists()
    assert merged.name == "execution_review_decisions_v2.tsv"
    assert second["experience_summary"]["experience_candidates"] == 1
    assert Path(second["experience_summary"]["summary_path"]).exists()
