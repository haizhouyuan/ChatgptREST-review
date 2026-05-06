from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode
from ops.run_evomap_chain_backfill import run_chain_backfill


def _seed_db(db_path: Path) -> None:
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    db.put_document(
        Document(
            doc_id="doc_plan",
            source="planning",
            project="planning",
            raw_ref="/vol1/1000/projects/planning/sample.md",
            title="Sample planning doc",
            created_at=10.0,
            updated_at=20.0,
        )
    )
    db.put_episode(
        Episode(
            episode_id="ep_plan",
            doc_id="doc_plan",
            time_start=30.0,
            time_end=40.0,
        )
    )
    db.put_atom(
        Atom(
            atom_id="at_plan",
            episode_id="ep_plan",
            question="How should we prepare for the visit?",
            answer="Use the planning brief.",
            canonical_question="",
            valid_from=0.0,
            status="scored",
        )
    )
    db.commit()


def test_run_chain_backfill_dry_run_uses_copy(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)

    summary = run_chain_backfill(
        db_path=db_path,
        output_root=tmp_path / "out",
        live=False,
        build_chains_mode="copy",
    )

    assert summary["mode"] == "dry_run"
    assert Path(summary["backfill_target_db"]).exists()
    assert summary["metrics_before"]["valid_from_missing"] == 1
    assert summary["metrics_after_backfill"]["valid_from_missing"] == 0
    assert summary["metrics_after_backfill"]["canonical_missing"] == 0

    live_db = KnowledgeDB(str(db_path))
    live_db.init_schema()
    live_atom = live_db.get_atom("at_plan")
    assert live_atom is not None
    assert live_atom.valid_from == 0.0
    assert live_atom.canonical_question == ""


def test_run_chain_backfill_live_updates_target_db(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)

    summary = run_chain_backfill(
        db_path=db_path,
        output_root=tmp_path / "out",
        live=True,
        build_chains_mode="skip",
    )

    assert summary["mode"] == "live"
    assert summary["metrics_after_backfill"]["valid_from_missing"] == 0
    assert summary["metrics_after_backfill"]["canonical_missing"] == 0

    db = KnowledgeDB(str(db_path))
    db.init_schema()
    atom = db.get_atom("at_plan")
    assert atom is not None
    assert atom.valid_from == 40.0
    assert atom.canonical_question == "How should we prepare for the visit?"

    summary_path = Path(summary["run_dir"]) / "summary.json"
    written = json.loads(summary_path.read_text(encoding="utf-8"))
    assert written["metrics_after_backfill"]["canonical_missing"] == 0


def test_run_chain_backfill_live_builds_chain_metadata_without_rewriting_promotion(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    _seed_db(db_path)
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    db.put_atom(
        Atom(
            atom_id="at_plan_new",
            episode_id="ep_plan",
            question="How should we prepare for the visit?",
            answer="Use the updated planning brief.",
            canonical_question="How should we prepare for the visit?",
            valid_from=50.0,
            status="scored",
            promotion_status="active",
            promotion_reason="preexisting_active",
        )
    )
    db.commit()

    summary = run_chain_backfill(
        db_path=db_path,
        output_root=tmp_path / "out",
        live=True,
        build_chains_mode="live",
        apply_promotion_semantics=False,
    )

    assert summary["chain_metrics_after"]["chain_id_nonempty"] == 2
    assert summary["chain_metrics_after"]["superseded_atoms"] == 0
    assert summary["apply_promotion_semantics"] is False

    atom_old = db.get_atom("at_plan")
    atom_new = db.get_atom("at_plan_new")
    assert atom_old is not None
    assert atom_new is not None
    assert atom_old.chain_id == atom_new.chain_id
    assert atom_old.superseded_by == "at_plan_new"
    assert atom_new.is_chain_head == 1
    assert atom_new.promotion_status == "active"
    assert atom_new.promotion_reason == "preexisting_active"
