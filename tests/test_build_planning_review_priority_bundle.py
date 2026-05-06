from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Document
from ops.build_planning_review_priority_bundle import build_bundle, build_priority_queue


def _put_doc(
    db: KnowledgeDB,
    doc_id: str,
    *,
    title: str,
    raw_ref: str,
    role: str,
    source_bucket: str,
    review_domain: str,
    family_id: str,
    latest: bool,
    reviewed: bool,
) -> None:
    meta = {
        "planning_review": {
            "document_role": role,
            "source_bucket": source_bucket,
            "review_domain": review_domain,
            "family_id": family_id,
            "is_latest_output": latest,
        }
    }
    if reviewed:
        meta["planning_review"]["decision"] = {"final_bucket": "service_candidate"}
    db.put_document(
        Document(
            doc_id=doc_id,
            source="planning",
            project="planning",
            raw_ref=raw_ref,
            title=title,
            meta_json=json.dumps(meta, ensure_ascii=False),
        )
    )


def test_build_bundle_selects_high_signal_backlog_docs(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    _put_doc(
        db,
        "doc_keep",
        title="执行计划",
        raw_ref="/vol1/1000/projects/planning/机器人代工业务规划/104/99_最新产物/执行计划.md",
        role="service_candidate",
        source_bucket="planning_latest_output",
        review_domain="business_104",
        family_id="b104_latest_outputs",
        latest=True,
        reviewed=False,
    )
    _put_doc(
        db,
        "doc_drop_readme",
        title="README",
        raw_ref="/vol1/1000/projects/planning/机器人代工业务规划/104/99_最新产物/README.md",
        role="service_candidate",
        source_bucket="planning_latest_output",
        review_domain="business_104",
        family_id="b104_latest_outputs",
        latest=True,
        reviewed=False,
    )
    _put_doc(
        db,
        "doc_reviewed",
        title="已审文档",
        raw_ref="/vol1/1000/projects/planning/预算/预算概览.md",
        role="service_candidate",
        source_bucket="planning_budget",
        review_domain="budget",
        family_id="budget_outputs",
        latest=True,
        reviewed=True,
    )
    _put_doc(
        db,
        "doc_archive_only",
        title="REQUEST_R1",
        raw_ref="/vol1/1000/projects/planning/减速器开发/_review_pack/REQUEST_R1.md",
        role="archive_only",
        source_bucket="planning_review_pack",
        review_domain="reducer",
        family_id="peek_review",
        latest=False,
        reviewed=False,
    )
    db.commit()
    db.close()

    out = tmp_path / "bundle"
    result = build_bundle(db_path=db_path, output_dir=out, limit=20)

    assert result["ok"] is True
    assert result["selected_docs"] == 1
    assert (out / "review_queue.json").exists()
    assert (out / "review_queue.tsv").exists()
    assert (out / "summary.json").exists()
    assert (out / "README.md").exists()
    assert "doc_keep" in (out / "README.md").read_text(encoding="utf-8")


def test_build_priority_queue_is_deterministic(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    _put_doc(
        db,
        "doc_alpha",
        title="执行计划A",
        raw_ref="/vol1/1000/projects/planning/机器人代工业务规划/104/99_最新产物/执行计划A.md",
        role="service_candidate",
        source_bucket="planning_latest_output",
        review_domain="business_104",
        family_id="b104_latest_outputs",
        latest=True,
        reviewed=False,
    )
    _put_doc(
        db,
        "doc_beta",
        title="执行计划B",
        raw_ref="/vol1/1000/projects/planning/业务PPT/outputs/执行计划B.md",
        role="review_plane",
        source_bucket="planning_outputs",
        review_domain="governance",
        family_id="ppt_outputs",
        latest=False,
        reviewed=False,
    )
    db.commit()
    db.close()

    first = build_priority_queue(db_path=db_path, limit=20)
    second = build_priority_queue(db_path=db_path, limit=20)

    assert first["selected_docs"] == second["selected_docs"]
    assert first["candidate_pool_docs"] == second["candidate_pool_docs"]
    assert first["rows"] == second["rows"]
