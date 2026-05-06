from __future__ import annotations

from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from ops.run_evomap_feedback_event_smoke import run_feedback_smoke


def test_run_feedback_smoke_records_feedback(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()

    summary = run_feedback_smoke(
        knowledge_db_path=str(db_path),
        output_root=tmp_path / "artifacts",
        query="feedback smoke query",
    )

    assert summary["ok"] is True
    assert summary["answer_feedback_delta"] == 1
    assert summary["query_event_delta"] == 1
    assert summary["latest_feedback"]["feedback_type"] == "corrected"
    assert summary["negative_artifact_score"] < 0.5
    assert summary["positive_artifact_score"] > 0.5

