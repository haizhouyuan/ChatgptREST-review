from __future__ import annotations

import csv
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.build_execution_activity_review_scaffold import build_scaffold


def test_build_scaffold_writes_review_template(tmp_path: Path) -> None:
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
            answer="completed a telemetry parity check",
            canonical_question="activity: workflow.completed",
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

    output_tsv = tmp_path / "review_scaffold.tsv"
    result = build_scaffold(db_path=db_path, output_tsv=output_tsv)

    assert result["ok"] is True
    assert result["selected_atoms"] == 1
    assert result["lineage_families"] == 1
    with output_tsv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    assert rows[0]["atom_id"] == "at_exec"
    assert rows[0]["lineage_family_id"] != ""
    assert rows[0]["lineage_status"] == "complete"
    assert rows[0]["canonical_question"] == "activity: workflow.completed"
    assert rows[0]["suggested_bucket"] == "lesson"
    assert rows[0]["final_bucket"] == ""
