from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Document
from ops.report_planning_review_backlog import report_backlog


def _put_doc(db: KnowledgeDB, doc_id: str, *, role: str, reviewed_bucket: str | None, domain: str, source_bucket: str, family_id: str, latest: bool) -> None:
    meta = {
        "planning_review": {
            "document_role": role,
            "review_domain": domain,
            "source_bucket": source_bucket,
            "family_id": family_id,
            "is_latest_output": latest,
        }
    }
    if reviewed_bucket is not None:
        meta["planning_review"]["decision"] = {"final_bucket": reviewed_bucket}
    db.put_document(
        Document(
            doc_id=doc_id,
            source="planning",
            project="planning",
            raw_ref=f"/vol1/1000/projects/planning/{doc_id}.md",
            title=doc_id,
            meta_json=json.dumps(meta, ensure_ascii=False),
        )
    )


def test_report_backlog_groups_review_backlog(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    _put_doc(
        db,
        "doc_reviewed",
        role="service_candidate",
        reviewed_bucket="service_candidate",
        domain="business_104",
        source_bucket="planning_latest_output",
        family_id="b104_exec",
        latest=True,
    )
    _put_doc(
        db,
        "doc_backlog_latest",
        role="service_candidate",
        reviewed_bucket=None,
        domain="business_104",
        source_bucket="planning_latest_output",
        family_id="b104_exec",
        latest=True,
    )
    _put_doc(
        db,
        "doc_backlog_review_pack",
        role="archive_only",
        reviewed_bucket=None,
        domain="reducer",
        source_bucket="planning_review_pack",
        family_id="peek_review",
        latest=False,
    )
    db.commit()
    db.close()

    summary = report_backlog(db_path=db_path, top_n=5)

    assert summary["total_docs"] == 3
    assert summary["role_tagged_docs"] == 3
    assert summary["reviewed_docs"] == 1
    assert summary["backlog_docs"] == 2
    assert summary["reviewed_by_bucket"]["service_candidate"] == 1
    assert summary["backlog_by_domain"]["business_104"] == 1
    assert summary["backlog_by_domain"]["reducer"] == 1
    assert summary["backlog_by_source_bucket"]["planning_latest_output"] == 1
    assert summary["backlog_by_source_bucket"]["planning_review_pack"] == 1
    assert summary["backlog_by_document_role"]["service_candidate"] == 1
    assert summary["backlog_by_document_role"]["archive_only"] == 1
    assert summary["latest_output_backlog_docs"] == 1
    assert summary["top_backlog_families"][0]["count"] >= 1
    assert summary["sample_latest_output_backlog"][0]["doc_id"] == "doc_backlog_latest"
