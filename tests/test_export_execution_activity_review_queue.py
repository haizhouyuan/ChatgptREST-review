from __future__ import annotations

from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.export_execution_activity_review_queue import build_review_queue


def _put_atom(
    db: KnowledgeDB,
    *,
    atom_id: str,
    source: str,
    episode_type: str,
    canonical_question: str,
    task_ref: str,
    trace_id: str,
) -> None:
    doc_id = f"doc_{atom_id}"
    episode_id = f"ep_{atom_id}"
    db.put_document(
        Document(
            doc_id=doc_id,
            source=source,
            project="ChatgptREST",
            raw_ref=f"/tmp/{doc_id}.json",
            title=doc_id,
        )
    )
    db.put_episode(
        Episode(
            episode_id=episode_id,
            doc_id=doc_id,
            episode_type=episode_type,
            title=episode_type,
            summary=episode_type,
            start_ref=f"{doc_id}:1",
            end_ref=f"{doc_id}:1",
            time_start=1.0,
            time_end=1.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id=atom_id,
            episode_id=episode_id,
            atom_type="lesson",
            question=atom_id,
            answer="answer",
            canonical_question=canonical_question,
            status="candidate",
            promotion_status="staged",
            promotion_reason="activity_ingest",
            applicability=(
                "{"
                f"\"task_ref\":\"{task_ref}\","
                f"\"trace_id\":\"{trace_id}\","
                "\"lane_id\":\"main\","
                "\"role_id\":\"devops\","
                "\"adapter_id\":\"controller_lane_wrapper\","
                "\"profile_id\":\"mainline_runtime\","
                "\"executor_kind\":\"codex.controller\""
                "}"
            ),
            valid_from=1.0,
        )
    )


def test_build_review_queue_selects_only_lineage_ready_atoms(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()

    _put_atom(
        db,
        atom_id="at_keep",
        source="agent_activity",
        episode_type="team.run.completed",
        canonical_question="task result: issue-114",
        task_ref="issue-114",
        trace_id="trace-114",
    )
    _put_atom(
        db,
        atom_id="at_missing_trace",
        source="agent_activity",
        episode_type="workflow.completed",
        canonical_question="task result: issue-115",
        task_ref="issue-115",
        trace_id="",
    )
    _put_atom(
        db,
        atom_id="at_missing_question",
        source="agent_activity",
        episode_type="tool.completed",
        canonical_question="",
        task_ref="issue-116",
        trace_id="trace-116",
    )
    db.commit()
    db.close()

    report = build_review_queue(db_path=db_path)

    assert report["selected_atoms"] == 1
    assert report["sources"] == {"agent_activity": 1}
    assert report["episode_types"] == {"team.run.completed": 1}
    assert report["atom_types"] == {"lesson": 1}
    assert report["rows"][0]["atom_id"] == "at_keep"
    assert report["rows"][0]["task_ref"] == "issue-114"
    assert report["rows"][0]["trace_id"] == "trace-114"
