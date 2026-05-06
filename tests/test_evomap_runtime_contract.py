from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from chatgptrest.api import routes_consult
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.retrieval import (
    RetrievalConfig,
    RetrievalSurface,
    retrieve,
    runtime_retrieval_config,
)
from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, PromotionStatus, Stability


def _put_atom(
    db: KnowledgeDB,
    *,
    atom_id: str,
    question: str = "How to deploy the service?",
    answer: str,
    status: str = AtomStatus.SCORED.value,
    promotion_status: str = PromotionStatus.ACTIVE.value,
    stability: str = Stability.VERSIONED.value,
    quality_auto: float = 0.8,
    groundedness: float = 0.8,
    scope_project: str = "",
    doc_project: str = "",
    raw_ref: str = "",
    source_bucket: str = "",
) -> None:
    doc_id = f"doc_{atom_id}"
    episode_id = f"ep_{atom_id}"
    if raw_ref or doc_project or source_bucket:
        from chatgptrest.evomap.knowledge.schema import Document, Episode

        meta_json = "{}"
        if source_bucket:
            meta_json = json.dumps(
                {"planning_review": {"source_bucket": source_bucket}},
                ensure_ascii=False,
            )
        db.put_document(
            Document(
                doc_id=doc_id,
                source="planning" if doc_project == "planning" else "chat",
                project=doc_project,
                raw_ref=raw_ref or f"/tmp/{atom_id}.md",
                title=question[:80] or atom_id,
                meta_json=meta_json,
            )
        )
        db.put_episode(Episode(episode_id=episode_id, doc_id=doc_id, episode_type="md_section", title=question[:80]))
    db.put_atom(
        Atom(
            atom_id=atom_id,
            episode_id=episode_id,
            question=question,
            answer=answer,
            atom_type="procedure",
            status=status,
            promotion_status=promotion_status,
            stability=stability,
            quality_auto=quality_auto,
            groundedness=groundedness,
            valid_from=time.time(),
            scope_project=scope_project,
        )
    )


def test_retrieve_exposes_only_active_runtime_promotion_state() -> None:
    db = KnowledgeDB(db_path=":memory:")
    db.init_schema()

    _put_atom(
        db,
        atom_id="active_ok",
        answer="Use docker compose up to deploy the service safely.",
        promotion_status=PromotionStatus.ACTIVE.value,
    )
    _put_atom(
        db,
        atom_id="staged_ok",
        answer="Staged guidance: deploy the service with smoke checks first.",
        promotion_status=PromotionStatus.STAGED.value,
    )
    _put_atom(
        db,
        atom_id="candidate_hidden",
        answer="Candidate-only guidance should not appear in runtime retrieval.",
        promotion_status=PromotionStatus.CANDIDATE.value,
    )

    results = retrieve(
        db,
        "deploy service guidance",
        config=RetrievalConfig(
            result_limit=10,
            allowed_promotion_status=(PromotionStatus.ACTIVE.value,),
        ),
    )

    atom_ids = {result.atom.atom_id for result in results}
    assert "active_ok" in atom_ids
    assert "staged_ok" not in atom_ids
    assert "candidate_hidden" not in atom_ids


def test_runtime_retrieval_policy_is_path_scoped() -> None:
    user_cfg = runtime_retrieval_config(surface=RetrievalSurface.USER_HOT_PATH)
    planning_cfg = runtime_retrieval_config(surface=RetrievalSurface.PLANNING_EXPLICIT_PATH)
    diagnostic_cfg = runtime_retrieval_config(surface=RetrievalSurface.DIAGNOSTIC_PATH)
    shadow_cfg = runtime_retrieval_config(surface=RetrievalSurface.SHADOW_EXPERIMENT_PATH)
    review_cfg = runtime_retrieval_config(surface=RetrievalSurface.PROMOTION_REVIEW_PATH)

    assert user_cfg.allowed_promotion_status == (PromotionStatus.ACTIVE.value,)
    assert planning_cfg.allowed_promotion_status == (
        PromotionStatus.ACTIVE.value,
        PromotionStatus.CANDIDATE.value,
        PromotionStatus.STAGED.value,
    )
    assert planning_cfg.planning_fallback_max_results == 3
    assert planning_cfg.planning_fallback_min_quality == 0.7
    assert diagnostic_cfg.allowed_promotion_status == (
        PromotionStatus.ACTIVE.value,
        PromotionStatus.STAGED.value,
    )
    assert shadow_cfg.allowed_promotion_status == diagnostic_cfg.allowed_promotion_status
    assert review_cfg.allowed_promotion_status == (
        PromotionStatus.ACTIVE.value,
        PromotionStatus.STAGED.value,
        PromotionStatus.CANDIDATE.value,
    )


def test_retrieve_excludes_superseded_atoms_even_when_they_match() -> None:
    db = KnowledgeDB(db_path=":memory:")
    db.init_schema()

    _put_atom(
        db,
        atom_id="active_current",
        answer="Current deploy guidance uses a canary rollout and smoke checks.",
        promotion_status=PromotionStatus.ACTIVE.value,
        stability=Stability.VERSIONED.value,
    )
    _put_atom(
        db,
        atom_id="active_superseded",
        answer="Old deploy guidance matched the same query but is superseded.",
        promotion_status=PromotionStatus.ACTIVE.value,
        stability=Stability.SUPERSEDED.value,
    )

    results = retrieve(
        db,
        "deploy guidance smoke checks",
        config=RetrievalConfig(result_limit=10),
    )

    atom_ids = {result.atom.atom_id for result in results}
    assert "active_current" in atom_ids
    assert "active_superseded" not in atom_ids


def test_consult_evomap_search_inherits_runtime_visibility_gate(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap_knowledge.db"
    db = KnowledgeDB(db_path=str(db_path))
    db.init_schema()

    _put_atom(
        db,
        atom_id="consult_active",
        answer="Active deploy answer surfaced through consult helper.",
        promotion_status=PromotionStatus.ACTIVE.value,
    )
    _put_atom(
        db,
        atom_id="consult_candidate",
        answer="Candidate answer should stay hidden from consult helper.",
        promotion_status=PromotionStatus.CANDIDATE.value,
    )
    db.commit()

    with patch.object(routes_consult, "_find_evomap_knowledge_db", return_value=str(db_path)):
        hits = routes_consult._evomap_search("deploy answer", top_k=10)

    hit_ids = {item["artifact_id"] for item in hits}
    assert "consult_active" in hit_ids
    assert "consult_candidate" not in hit_ids
    assert all(item["source"] == "evomap" for item in hits)


def test_consult_evomap_search_excludes_low_groundedness_atoms(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap_knowledge.db"
    db = KnowledgeDB(db_path=str(db_path))
    db.init_schema()

    _put_atom(
        db,
        atom_id="consult_grounded",
        answer="Grounded answer can appear in consult helper results.",
        promotion_status=PromotionStatus.ACTIVE.value,
        groundedness=0.9,
    )
    _put_atom(
        db,
        atom_id="consult_low_grounded",
        answer="Low groundedness answer should stay hidden from consult helper.",
        promotion_status=PromotionStatus.ACTIVE.value,
        groundedness=0.1,
    )
    db.commit()

    with patch.object(routes_consult, "_find_evomap_knowledge_db", return_value=str(db_path)):
        hits = routes_consult._evomap_search("consult helper grounded answer", top_k=10)

    hit_ids = {item["artifact_id"] for item in hits}
    assert "consult_grounded" in hit_ids
    assert "consult_low_grounded" not in hit_ids


def test_planning_explicit_surface_only_backfills_guarded_candidate_and_staged_atoms() -> None:
    db = KnowledgeDB(db_path=":memory:")
    db.init_schema()

    _put_atom(
        db,
        atom_id="plan_active",
        question="合同底线怎么设",
        answer="付款节点、验收标准和退出机制都要写死。",
        promotion_status=PromotionStatus.ACTIVE.value,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/planning/outputs/contract.md",
        source_bucket="planning_outputs",
    )
    _put_atom(
        db,
        atom_id="plan_candidate_ok",
        question="商务条款需要准备什么",
        answer="准备价格区间、付款节奏和违约场景。",
        promotion_status=PromotionStatus.CANDIDATE.value,
        quality_auto=0.82,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/planning/outputs/business.md",
        source_bucket="planning_outputs",
    )
    _put_atom(
        db,
        atom_id="plan_staged_ok",
        question="合作前要确认哪些边界",
        answer="确认产线窗口、质量门和保密边界。",
        promotion_status=PromotionStatus.STAGED.value,
        quality_auto=0.79,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/planning/99_最新产物/visit.md",
        source_bucket="planning_latest_output",
    )
    _put_atom(
        db,
        atom_id="plan_candidate_bad_bucket",
        question="AIOS 材料怎么处理",
        answer="这个 bucket 不应该进入 explicit fallback。",
        promotion_status=PromotionStatus.CANDIDATE.value,
        quality_auto=0.95,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/planning/aios/noisy.md",
        source_bucket="planning_aios",
    )
    _put_atom(
        db,
        atom_id="plan_staged_low_quality",
        question="低质量 staged 条目",
        answer="这个 staged 条目不该进 fallback。",
        promotion_status=PromotionStatus.STAGED.value,
        quality_auto=0.45,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/planning/outputs/low-quality.md",
        source_bucket="planning_outputs",
    )

    results = retrieve(
        db,
        "合同 准备 边界",
        config=runtime_retrieval_config(
            surface=RetrievalSurface.PLANNING_EXPLICIT_PATH,
            project_id="planning",
            result_limit=5,
        ),
    )

    layers = {item.atom.atom_id: item.retrieval_layer for item in results}
    ids = [item.atom.atom_id for item in results]
    assert "plan_active" in ids
    assert "plan_candidate_ok" in ids
    assert "plan_staged_ok" in ids
    assert "plan_candidate_bad_bucket" not in ids
    assert "plan_staged_low_quality" not in ids
    assert layers["plan_active"] == "promoted_active"
    assert layers["plan_candidate_ok"] == "candidate_fallback"
    assert layers["plan_staged_ok"] == "staged_fallback"
    assert sum(1 for item in results if item.retrieval_layer.endswith("fallback")) <= 3


def test_planning_explicit_surface_can_return_vector_only_hit(monkeypatch) -> None:
    db = KnowledgeDB(db_path=":memory:")
    db.init_schema()
    _put_atom(
        db,
        atom_id="vector_only_plan",
        question="供料与指定件边界是什么",
        answer="需要提前冻结供料件、指定件和责任边界。",
        promotion_status=PromotionStatus.ACTIVE.value,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/planning/outputs/supply.md",
        source_bucket="planning_outputs",
    )

    from chatgptrest.evomap.knowledge import retrieval as retrieval_mod

    monkeypatch.setattr(
        retrieval_mod,
        "_vector_hits_for_query",
        lambda query, cfg: ({"vector_only_plan": 0.93}, {"vector_only_plan": 1.0}),
    )

    results = retrieve(
        db,
        "供应商选择策略",
        config=runtime_retrieval_config(
            surface=RetrievalSurface.PLANNING_EXPLICIT_PATH,
            project_id="planning",
            result_limit=5,
        ),
    )

    assert [item.atom.atom_id for item in results] == ["vector_only_plan"]
    assert results[0].retrieval_source == "vector"


def test_planning_explicit_surface_normalizes_compact_chinese_business_query() -> None:
    db = KnowledgeDB(db_path=":memory:")
    db.init_schema()
    _put_atom(
        db,
        atom_id="green_visit",
        question="绿源拜访会议纪要",
        answer="绿源拜访前要准备公司背景、车身项目现状和产线参观要点。",
        promotion_status=PromotionStatus.CANDIDATE.value,
        quality_auto=0.86,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/planning/两轮车车身业务/2026-03-19_绿源拜访会议纪要.md",
        source_bucket="planning_outputs",
    )

    results = retrieve(
        db,
        "绿源来访准备",
        config=runtime_retrieval_config(
            surface=RetrievalSurface.PLANNING_EXPLICIT_PATH,
            project_id="planning",
            result_limit=5,
        ),
    )

    assert [item.atom.atom_id for item in results] == ["green_visit"]
    assert results[0].retrieval_layer == "candidate_fallback"


def test_planning_explicit_surface_ranks_high_score_fallback_ahead_of_generic_active_hit() -> None:
    db = KnowledgeDB(db_path=":memory:")
    db.init_schema()
    _put_atom(
        db,
        atom_id="generic_active",
        question="项目阶段总结是什么？",
        answer="这是一条泛化 active 命中，但和钛虎合作不够贴题。",
        promotion_status=PromotionStatus.ACTIVE.value,
        quality_auto=0.35,
        groundedness=0.7,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/planning/outputs/generic.md",
        source_bucket="planning_outputs",
    )
    _put_atom(
        db,
        atom_id="specific_candidate",
        question="钛虎机器人关节模组合作的关键合作边界是什么？",
        answer="合作边界包括关节模组代工窗口、责任划分和样机推进节奏。",
        promotion_status=PromotionStatus.CANDIDATE.value,
        quality_auto=0.92,
        groundedness=0.85,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/planning/controlled/tiger.md",
        source_bucket="planning_controlled",
    )

    cfg = runtime_retrieval_config(
        surface=RetrievalSurface.PLANNING_EXPLICIT_PATH,
        project_id="planning",
        result_limit=5,
    )
    cfg.enable_vector_search = False
    results = retrieve(db, "钛虎机器人关节模组合作", config=cfg)

    assert results
    assert results[0].atom.atom_id == "specific_candidate"
    assert results[0].retrieval_layer == "candidate_fallback"


def test_planning_controlled_active_stays_hidden_outside_planning_explicit() -> None:
    db = KnowledgeDB(db_path=":memory:")
    db.init_schema()
    _put_atom(
        db,
        atom_id="controlled_active",
        question="绿源会前准备要点是什么？",
        answer="绿源会前要准备关注点、换色边界和平台复用说明。",
        promotion_status=PromotionStatus.ACTIVE.value,
        quality_auto=0.9,
        groundedness=0.8,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/planning/controlled/green.md",
        source_bucket="planning_controlled",
    )
    _put_atom(
        db,
        atom_id="regular_active",
        question="regular active prep marker",
        answer="常规项目要准备里程碑、边界和负责人口径，regular active prep marker。",
        promotion_status=PromotionStatus.ACTIVE.value,
        quality_auto=0.85,
        groundedness=0.8,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/planning/outputs/generic.md",
        source_bucket="planning_outputs",
    )

    hot_results = retrieve(
        db,
        "regular active prep marker",
        config=runtime_retrieval_config(
            surface=RetrievalSurface.USER_HOT_PATH,
            project_id="planning",
            result_limit=5,
        ),
    )
    hot_ids = [item.atom.atom_id for item in hot_results]
    assert "controlled_active" not in hot_ids
    assert "regular_active" in hot_ids

    explicit_results = retrieve(
        db,
        "绿源来访准备",
        config=runtime_retrieval_config(
            surface=RetrievalSurface.PLANNING_EXPLICIT_PATH,
            project_id="planning",
            result_limit=5,
        ),
    )
    explicit_ids = [item.atom.atom_id for item in explicit_results]
    assert "controlled_active" in explicit_ids
    assert next(item for item in explicit_results if item.atom.atom_id == "controlled_active").retrieval_layer == "promoted_active"


def test_planning_explicit_entity_exact_match_boost_prefers_entity_specific_doc() -> None:
    db = KnowledgeDB(db_path=":memory:")
    db.init_schema()
    _put_atom(
        db,
        atom_id="green_entity",
        question="绿源会中问题单 打印版是什么？",
        answer="绿源会面现场要优先确认平台复用边界、微调边界、标准化轮库回应方式和下一轮方案包。",
        status=AtomStatus.CANDIDATE.value,
        promotion_status=PromotionStatus.CANDIDATE.value,
        quality_auto=0.82,
        groundedness=0.7,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/vol1/1000/projects/planning/两轮车车身业务/2026-03-30_绿源会中问题单_打印版_v1.md",
        source_bucket="planning_controlled",
    )
    _put_atom(
        db,
        atom_id="generic_prep",
        question="资源与现场准备是什么？",
        answer="准备相关内容包括现场资源安排、演示物料和会务节奏。",
        status=AtomStatus.CANDIDATE.value,
        promotion_status=PromotionStatus.CANDIDATE.value,
        quality_auto=0.9,
        groundedness=0.8,
        scope_project="planning",
        doc_project="planning",
        raw_ref="/vol1/1000/projects/planning/两轮车车身业务/通用准备稿.md",
        source_bucket="planning_outputs",
    )

    cfg = runtime_retrieval_config(
        surface=RetrievalSurface.PLANNING_EXPLICIT_PATH,
        project_id="planning",
        result_limit=5,
    )
    cfg.enable_vector_search = False
    results = retrieve(db, "绿源来访准备", config=cfg)

    assert results
    assert results[0].atom.atom_id == "green_entity"
    assert results[0].entity_boost > 0.0
