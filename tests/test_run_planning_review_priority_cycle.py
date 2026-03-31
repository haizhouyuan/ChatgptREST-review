from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, PromotionStatus
from ops.run_planning_review_priority_cycle import run_cycle


def _write_allowlist(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
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
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "doc_id": "doc_reviewed",
                "title": "已审文档",
                "raw_ref": "/reviewed.md",
                "family_id": "budget_outputs",
                "review_domain": "budget",
                "source_bucket": "planning_budget",
                "avg_quality": "0.8",
                "final_bucket": "service_candidate",
                "service_readiness": "high",
                "reviewers": "[]",
            }
        )


def _put_doc(
    db: KnowledgeDB,
    doc_id: str,
    *,
    role: str,
    bucket: str,
    domain: str,
    family_id: str,
    latest: bool,
    reviewed: bool,
    title: str,
) -> None:
    meta = {
        "planning_review": {
            "document_role": role,
            "source_bucket": bucket,
            "review_domain": domain,
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
            raw_ref=f"/vol1/1000/projects/planning/{doc_id}.md",
            title=title,
            meta_json=json.dumps(meta, ensure_ascii=False),
        )
    )
    db.put_episode(
        Episode(
            episode_id=f"ep_{doc_id}",
            doc_id=doc_id,
            episode_type="md_section",
            title=title,
            summary=title,
            start_ref=f"/{doc_id}.md",
            end_ref=f"/{doc_id}.md",
            time_start=1.0,
            time_end=1.0,
        )
    )
    promotion_status = PromotionStatus.ACTIVE.value if reviewed else PromotionStatus.STAGED.value
    promotion_reason = "planning_bootstrap_review_verified_fast_path" if reviewed else ""
    db.put_atom(
        Atom(
            atom_id=f"at_{doc_id}",
            episode_id=f"ep_{doc_id}",
            atom_type="procedure",
            question=title,
            answer="answer",
            canonical_question=title,
            quality_auto=0.82,
            promotion_status=promotion_status,
            promotion_reason=promotion_reason,
            valid_from=1.0,
        )
    )


def test_run_cycle_writes_expected_artifacts(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    _put_doc(
        db,
        "doc_reviewed",
        role="service_candidate",
        bucket="planning_budget",
        domain="budget",
        family_id="budget_outputs",
        latest=True,
        reviewed=True,
        title="已审文档",
    )
    _put_doc(
        db,
        "doc_backlog",
        role="service_candidate",
        bucket="planning_latest_output",
        domain="business_104",
        family_id="b104_latest_outputs",
        latest=True,
        reviewed=False,
        title="执行计划",
    )
    db.commit()
    db.close()

    allowlist = tmp_path / "allowlist.tsv"
    _write_allowlist(allowlist)

    summary = run_cycle(
        db_path=db_path,
        output_root=tmp_path / "cycle",
        allowlist_path=allowlist,
        limit=20,
    )

    out = Path(summary["output_dir"])
    assert summary["selected_docs"] == 1
    assert summary["backlog_docs"] == 1
    assert (out / "state_audit.json").exists()
    assert (out / "backlog_audit.json").exists()
    assert (out / "consistency_audit.json").exists()
    assert (out / "review_queue.json").exists()
    assert (out / "summary.json").exists()
    assert summary["consistency_ok"] is True
    assert (out / "bundle" / "review_queue.json").exists()
    assert (out / "bundle" / "review_decisions_template.tsv").exists()


def test_run_cycle_can_fail_fast_on_consistency_drift(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    _put_doc(
        db,
        "doc_missing",
        role="service_candidate",
        bucket="planning_latest_output",
        domain="business_104",
        family_id="b104_latest_outputs",
        latest=True,
        reviewed=True,
        title="漂移文档",
    )
    db.commit()
    db.close()

    allowlist = tmp_path / "allowlist.tsv"
    _write_allowlist(allowlist)

    with pytest.raises(RuntimeError, match="consistency drift"):
        run_cycle(
            db_path=db_path,
            output_root=tmp_path / "cycle",
            allowlist_path=allowlist,
            limit=20,
            require_consistent=True,
        )
