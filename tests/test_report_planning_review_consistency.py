from __future__ import annotations

import csv
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, PromotionStatus
from ops.report_planning_review_consistency import report_consistency


def _write_allowlist(path: Path, doc_ids: list[str]) -> None:
    fieldnames = [
        "doc_id",
        "title",
        "raw_ref",
        "family_id",
        "review_domain",
        "source_bucket",
        "avg_quality",
        "final_bucket",
        "service_readiness",
        "reviewers",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for doc_id in doc_ids:
            writer.writerow(
                {
                    "doc_id": doc_id,
                    "title": doc_id,
                    "raw_ref": f"/vol1/1000/projects/planning/{doc_id}.md",
                    "family_id": "fam",
                    "review_domain": "business_104",
                    "source_bucket": "planning_latest_output",
                    "avg_quality": "0.81",
                    "final_bucket": "service_candidate",
                    "service_readiness": "high",
                    "reviewers": "[]",
                }
            )


def _put_doc(
    db: KnowledgeDB,
    doc_id: str,
    *,
    reviewed: bool,
    role: str,
    domain: str,
    source_bucket: str,
    latest: bool,
    promotion_status: str | None = None,
    promotion_reason: str = "",
) -> None:
    meta = {
        "planning_review": {
            "document_role": role,
            "review_domain": domain,
            "source_bucket": source_bucket,
            "family_id": "fam",
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
            raw_ref=f"/vol1/1000/projects/planning/{doc_id}.md",
            title=doc_id,
            meta_json=json.dumps(meta, ensure_ascii=False),
        )
    )
    db.put_episode(
        Episode(
            episode_id=f"ep_{doc_id}",
            doc_id=doc_id,
            episode_type="md_section",
            title=doc_id,
            summary=doc_id,
            start_ref=f"/{doc_id}.md",
            end_ref=f"/{doc_id}.md",
            time_start=1.0,
            time_end=1.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id=f"at_{doc_id}",
            episode_id=f"ep_{doc_id}",
            atom_type="procedure",
            question=doc_id,
            answer="answer",
            canonical_question=doc_id,
            quality_auto=0.82,
            promotion_status=promotion_status,
            promotion_reason=promotion_reason,
            valid_from=1.0,
        )
    )


def test_report_consistency_passes_for_consistent_review_slice(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    _put_doc(
        db,
        "doc_reviewed",
        reviewed=True,
        role="service_candidate",
        domain="business_104",
        source_bucket="planning_latest_output",
        latest=True,
        promotion_status=PromotionStatus.ACTIVE.value,
        promotion_reason="planning_bootstrap_review_verified_fast_path",
    )
    _put_doc(
        db,
        "doc_backlog",
        reviewed=False,
        role="review_plane",
        domain="governance",
        source_bucket="planning_outputs",
        latest=False,
        promotion_status=PromotionStatus.STAGED.value,
    )
    db.commit()
    db.close()

    allowlist = tmp_path / "allowlist.tsv"
    _write_allowlist(allowlist, ["doc_reviewed"])

    summary = report_consistency(db_path=db_path, allowlist_path=allowlist, top_n=12, limit=10)

    assert summary["ok"] is True
    assert summary["reviewed_docs"] == 1
    assert summary["backlog_docs"] == 1
    assert summary["candidate_pool_docs"] == 1
    assert summary["selected_docs"] == 1
    assert summary["live_active_atoms"] == 1
    assert all(summary["checks"].values())


def test_report_consistency_flags_allowlist_and_bootstrap_drift(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    _put_doc(
        db,
        "doc_missing",
        reviewed=True,
        role="service_candidate",
        domain="business_104",
        source_bucket="planning_latest_output",
        latest=True,
        promotion_status=PromotionStatus.STAGED.value,
    )
    _put_doc(
        db,
        "doc_stale",
        reviewed=True,
        role="service_candidate",
        domain="business_104",
        source_bucket="planning_latest_output",
        latest=True,
        promotion_status=PromotionStatus.ACTIVE.value,
        promotion_reason="planning_bootstrap_review_verified_fast_path",
    )
    db.commit()
    db.close()

    allowlist = tmp_path / "allowlist.tsv"
    _write_allowlist(allowlist, ["doc_missing"])

    summary = report_consistency(db_path=db_path, allowlist_path=allowlist, top_n=12, limit=10)

    assert summary["ok"] is False
    assert summary["checks"]["allowlist_live_coverage_ok"] is False
    assert summary["checks"]["bootstrap_allowlist_alignment_ok"] is False
