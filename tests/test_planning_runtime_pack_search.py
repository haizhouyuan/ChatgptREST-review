from __future__ import annotations

import csv
import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.planning_runtime_pack_search import search_planning_runtime_pack
from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, Document, Episode, PromotionStatus, Stability


def _write_pack_bundle(base: Path) -> tuple[Path, Path]:
    bundle = base / "bundle"
    pack = base / "pack"
    bundle.mkdir(parents=True, exist_ok=True)
    pack.mkdir(parents=True, exist_ok=True)

    docs_fields = [
        "doc_id",
        "title",
        "raw_ref",
        "family_id",
        "review_domain",
        "source_bucket",
        "document_role",
        "final_bucket",
        "service_readiness",
        "is_latest_output",
        "updated_at",
        "updated_at_iso",
        "live_active_atoms",
        "live_candidate_atoms",
    ]
    with (pack / "docs.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=docs_fields, delimiter="\t")
        writer.writeheader()
        writer.writerow(
            {
                "doc_id": "doc_plan",
                "title": "机器人代工合同与商务底线",
                "raw_ref": "/planning/report.md",
                "family_id": "business_104",
                "review_domain": "business_104",
                "source_bucket": "planning_outputs",
                "document_role": "service_candidate",
                "final_bucket": "service_candidate",
                "service_readiness": "high",
                "is_latest_output": 1,
                "updated_at": 1,
                "updated_at_iso": "2026-03-11T00:00:00+00:00",
                "live_active_atoms": 1,
                "live_candidate_atoms": 1,
            }
        )

    atom_fields = [
        "doc_id",
        "atom_id",
        "episode_id",
        "atom_type",
        "promotion_status",
        "promotion_reason",
        "quality_auto",
        "value_auto",
        "question",
        "canonical_question",
    ]
    with (pack / "atoms.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=atom_fields, delimiter="\t")
        writer.writeheader()
        writer.writerow(
            {
                "doc_id": "doc_plan",
                "atom_id": "at_active",
                "episode_id": "ep_active",
                "atom_type": "decision",
                "promotion_status": "active",
                "promotion_reason": "planning_bootstrap_review_verified",
                "quality_auto": 0.9,
                "value_auto": 0.6,
                "question": "合同与商务底线怎么设",
                "canonical_question": "合同与商务底线怎么设",
            }
        )
        writer.writerow(
            {
                "doc_id": "doc_plan",
                "atom_id": "at_candidate",
                "episode_id": "ep_candidate",
                "atom_type": "decision",
                "promotion_status": "candidate",
                "promotion_reason": "planning_bootstrap_review_verified",
                "quality_auto": 0.9,
                "value_auto": 0.6,
                "question": "合同候选条款还有什么",
                "canonical_question": "合同候选条款还有什么",
            }
        )

    (pack / "retrieval_pack.json").write_text(
        json.dumps(
            {
                "pack_type": "planning_reviewed_runtime_pack_v1",
                "doc_ids": ["doc_plan"],
                "atom_ids": ["at_active", "at_candidate"],
                "review_domains": ["business_104"],
                "source_buckets": ["planning_outputs"],
                "opt_in_only": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (bundle / "release_bundle_manifest.json").write_text(
        json.dumps(
            {
                "pack_dir": str(pack),
                "ready_for_explicit_consumption": True,
                "scope": {"opt_in_only": True, "default_runtime_cutover": False},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return bundle, pack


def _seed_db(db_path: Path) -> None:
    db = KnowledgeDB(db_path=str(db_path))
    db.init_schema()
    db.put_document(
        Document(
            doc_id="doc_plan",
            source="planning",
            project="planning",
            raw_ref="/planning/report.md",
            title="机器人代工合同与商务底线",
            meta_json=json.dumps(
                {
                    "planning_review": {
                        "review_domain": "business_104",
                        "source_bucket": "planning_outputs",
                    }
                },
                ensure_ascii=False,
            ),
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_active",
            doc_id="doc_plan",
            episode_type="md_section",
            title="合同与商务底线",
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_candidate",
            doc_id="doc_plan",
            episode_type="md_section",
            title="候选条款",
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_active",
            episode_id="ep_active",
            atom_type="decision",
            question="合同与商务底线怎么设",
            answer="底线应包含付款节点、验收标准和违约退出条件。",
            canonical_question="合同与商务底线怎么设",
            status="reviewed",
            stability=Stability.VERSIONED.value,
            promotion_status=PromotionStatus.ACTIVE.value,
            quality_auto=0.92,
            groundedness=0.9,
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_candidate",
            episode_id="ep_candidate",
            atom_type="decision",
            question="合同候选条款还有什么",
            answer="候选条款仍需 review，不应直接进入 runtime。",
            canonical_question="合同候选条款还有什么",
            status="reviewed",
            stability=Stability.VERSIONED.value,
            promotion_status=PromotionStatus.CANDIDATE.value,
            quality_auto=0.92,
            groundedness=0.9,
        )
    )
    db.commit()


def test_search_planning_runtime_pack_returns_only_runtime_visible_atoms(tmp_path: Path, monkeypatch) -> None:
    bundle, _ = _write_pack_bundle(tmp_path)
    db_path = tmp_path / "evomap_knowledge.db"
    _seed_db(db_path)
    monkeypatch.setenv("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR", str(bundle))
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(db_path))

    hits = search_planning_runtime_pack("合同 商务 底线", top_k=5)

    assert len(hits) == 1
    assert hits[0]["artifact_id"] == "at_active"
    assert hits[0]["source"] == "planning_review_pack"
    assert hits[0]["planning_pack_meta"]["pack_version"] == "pack"


def test_search_planning_runtime_pack_requires_ready_bundle(tmp_path: Path, monkeypatch) -> None:
    bundle, pack = _write_pack_bundle(tmp_path)
    (bundle / "release_bundle_manifest.json").write_text(
        json.dumps(
            {
                "pack_dir": str(pack),
                "ready_for_explicit_consumption": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "evomap_knowledge.db"
    _seed_db(db_path)
    monkeypatch.setenv("CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR", str(bundle))
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", str(db_path))

    assert search_planning_runtime_pack("合同 商务 底线", top_k=5) == []
