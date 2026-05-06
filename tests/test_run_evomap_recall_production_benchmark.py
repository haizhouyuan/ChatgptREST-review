from __future__ import annotations

import json
import time
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode, PromotionStatus
from ops.run_evomap_recall_production_benchmark import _score_hits, load_cases, run_benchmark


def _seed(db_path: Path) -> None:
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    doc = Document(
        doc_id="doc_planning_green",
        source="planning",
        project="planning",
        raw_ref="/planning/两轮车车身业务/green.md",
        title="绿源拜访会议纪要",
        meta_json=json.dumps({"planning_review": {"source_bucket": "planning_controlled"}}, ensure_ascii=False),
    )
    episode = Episode(
        episode_id="ep_planning_green",
        doc_id=doc.doc_id,
        episode_type="md_section",
        title=doc.title,
    )
    db.put_document(doc)
    db.put_episode(episode)
    db.put_atom(
        Atom(
            atom_id="green_candidate",
            episode_id=episode.episode_id,
            atom_type="procedure",
            question="绿源拜访会议纪要是什么？",
            answer="绿源来访前要准备公司背景和会面议题。",
            canonical_question="绿源拜访会议纪要",
            quality_auto=0.9,
            groundedness=0.8,
            promotion_status=PromotionStatus.CANDIDATE.value,
            scope_project="planning",
            valid_from=time.time(),
        )
    )
    db.commit()


def test_run_benchmark_reports_recall_gain_and_confidence(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge.db"
    vector_path = tmp_path / "vectors.db"
    _seed(db_path)

    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "green-visit",
                    "case_family": "positive",
                    "query": "绿源来访准备",
                    "project_id": "planning",
                    "expected_keywords": ["绿源", "来访", "拜访", "准备"],
                    "entity_terms": ["绿源"],
                    "expected_posture": "answer",
                    "expected_recall_grade": "bridge",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "query": "绿源来访准备",
                        "hits": [
                            {
                                "question": "通用项目总结是什么？",
                                "answer_excerpt": "generic answer",
                                "source_ref": "/planning/generic.md",
                                "scope_project": "planning",
                            }
                        ],
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = run_benchmark(
        db_path=str(db_path),
        vector_db_path=str(vector_path),
        cases_path=str(cases_path),
        baseline_summary_path=str(baseline_path),
        output_root=str(tmp_path / "artifacts"),
        result_limit=3,
    )

    assert summary["current"]["aggregate"]["top3_hit_rate"] > summary["baseline"]["aggregate"]["top3_hit_rate"]
    assert summary["current"]["aggregate"]["background_reexplanation_risk_rate"] == 0.0
    assert summary["current"]["cases"][0]["confidence_posture"] == "answer"
    assert summary["current"]["cases"][0]["recall_grade"] == "bridge"
    assert summary["current"]["cases"][0]["entity_exact_hit_count"] >= 1
    assert summary["current"]["aggregate"]["expected_posture_match_rate"] == 1.0
    assert summary["current"]["aggregate"]["expected_recall_grade_match_rate"] == 1.0
    assert Path(summary["artifacts"]["summary_json"]).exists()
    assert Path(summary["artifacts"]["report_md"]).exists()


def test_load_cases_supports_v2_fields(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "entity-boundary",
                    "case_family": "boundary",
                    "query": "绿源公司整体情况和产品线",
                    "project_id": "planning",
                    "expected_keywords": ["绿源", "产品线"],
                    "entity_terms": ["绿源"],
                    "expected_posture": "clarify",
                    "expected_recall_grade": "bridge",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rows = load_cases(cases_path)

    assert rows[0]["case_family"] == "boundary"
    assert rows[0]["entity_terms"] == ["绿源"]
    assert rows[0]["expected_posture"] == "clarify"
    assert rows[0]["expected_recall_grade"] == "bridge"


def test_score_hits_marks_dossier_bridge_only_case_as_clarify() -> None:
    row = _score_hits(
        {
            "case_id": "green-profile",
            "query": "绿源公司整体情况和产品线",
            "project_id": "planning",
            "expected_keywords": ["绿源", "产品线", "业务"],
            "entity_terms": ["绿源"],
        },
        [
            {
                "question": "绿源会前准备材料是什么？",
                "answer_excerpt": "绿源关注点包括换色能力、平台复用和标准化轮型。",
                "source_ref": "/planning/green.md",
                "scope_project": "planning",
            }
        ],
    )

    assert row["recall_grade"] == "bridge"
    assert row["confidence_posture"] == "clarify"


def test_score_hits_marks_generic_visit_bridge_case_as_clarify() -> None:
    row = _score_hits(
        {
            "case_id": "vendor-visit",
            "query": "供应商来访准备",
            "project_id": "planning",
            "expected_keywords": ["供应商", "来访", "准备"],
            "entity_terms": [],
        },
        [
            {
                "question": "来访准备包是什么？",
                "answer_excerpt": "准备物料、交流议程和产线参观点位。",
                "source_ref": "/planning/vendor.md",
                "scope_project": "planning",
            }
        ],
    )

    assert row["recall_grade"] == "bridge"
    assert row["confidence_posture"] == "clarify"
