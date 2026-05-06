from __future__ import annotations

import csv
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.compose_execution_activity_review_decisions import FIELDNAMES
from ops.export_execution_experience_candidates import export_candidates


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_export_candidates_writes_review_backed_experience_rows(tmp_path: Path) -> None:
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

    decisions = tmp_path / "execution_review_decisions_v1.tsv"
    _write_rows(
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
                "experience_title": "",
                "experience_summary": "",
                "reviewer": "reviewer-a",
                "review_notes": "keep",
            }
        ],
    )

    result = export_candidates(db_path=db_path, decisions_path=decisions, output_dir=tmp_path / "experience")

    assert result["experience_candidates"] == 1
    summary = json.loads((tmp_path / "experience" / "summary.json").read_text(encoding="utf-8"))
    candidates = json.loads((tmp_path / "experience" / "experience_candidates.json").read_text(encoding="utf-8"))
    assert summary["by_kind"] == {"lesson": 1}
    assert candidates[0]["title"] == "activity: workflow.completed"
    assert candidates[0]["summary"].startswith("execution review cycle complete")
