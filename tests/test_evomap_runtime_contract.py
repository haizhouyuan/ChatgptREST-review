from __future__ import annotations

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
) -> None:
    db.put_atom(
        Atom(
            atom_id=atom_id,
            episode_id=f"ep_{atom_id}",
            question=question,
            answer=answer,
            atom_type="procedure",
            status=status,
            promotion_status=promotion_status,
            stability=stability,
            quality_auto=quality_auto,
            groundedness=groundedness,
            valid_from=time.time(),
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
    diagnostic_cfg = runtime_retrieval_config(surface=RetrievalSurface.DIAGNOSTIC_PATH)
    shadow_cfg = runtime_retrieval_config(surface=RetrievalSurface.SHADOW_EXPERIMENT_PATH)
    review_cfg = runtime_retrieval_config(surface=RetrievalSurface.PROMOTION_REVIEW_PATH)

    assert user_cfg.allowed_promotion_status == (PromotionStatus.ACTIVE.value,)
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
