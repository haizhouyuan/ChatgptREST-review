from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Document
from ops.build_planning_review_scaffold import build_scaffold


def test_build_scaffold_writes_priority_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    meta = {
        "planning_review": {
            "document_role": "service_candidate",
            "source_bucket": "planning_latest_output",
            "review_domain": "business_104",
            "family_id": "b104_latest_outputs",
            "is_latest_output": True,
        }
    }
    db.put_document(
        Document(
            doc_id="doc_keep",
            source="planning",
            project="planning",
            raw_ref="/vol1/1000/projects/planning/机器人代工业务规划/104/99_最新产物/执行计划.md",
            title="执行计划",
            meta_json=json.dumps(meta, ensure_ascii=False),
        )
    )
    db.commit()
    db.close()

    out = tmp_path / "scaffold.tsv"
    result = build_scaffold(db_path=db_path, output_tsv=out, limit=20)

    assert result["ok"] is True
    assert result["selected_docs"] == 1
    text = out.read_text(encoding="utf-8")
    assert "doc_keep" in text
    assert "suggested_bucket" in text


def test_build_scaffold_is_deterministic(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    meta = {
        "planning_review": {
            "document_role": "service_candidate",
            "source_bucket": "planning_latest_output",
            "review_domain": "business_104",
            "family_id": "b104_latest_outputs",
            "is_latest_output": True,
        }
    }
    db.put_document(
        Document(
            doc_id="doc_keep",
            source="planning",
            project="planning",
            raw_ref="/vol1/1000/projects/planning/机器人代工业务规划/104/99_最新产物/执行计划.md",
            title="执行计划",
            meta_json=json.dumps(meta, ensure_ascii=False),
        )
    )
    db.commit()
    db.close()

    out1 = tmp_path / "scaffold1.tsv"
    out2 = tmp_path / "scaffold2.tsv"
    build_scaffold(db_path=db_path, output_tsv=out1, limit=20)
    build_scaffold(db_path=db_path, output_tsv=out2, limit=20)

    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")
