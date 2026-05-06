from __future__ import annotations

from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, Episode, Document
from ops.run_evomap_quality_archive import apply_archive, collect_candidates


def _seed_atom(db: KnowledgeDB, *, atom_id: str, question: str, answer: str, canonical_question: str = "", promotion_status: str = "staged") -> None:
    doc = Document(doc_id=f"doc_{atom_id}", source="test", project="test", raw_ref=f"{atom_id}.md", title=atom_id)
    ep = Episode(episode_id=f"ep_{atom_id}", doc_id=doc.doc_id, episode_type="md_section", title=atom_id)
    atom = Atom(
        atom_id=atom_id,
        episode_id=ep.episode_id,
        question=question,
        answer=answer,
        canonical_question=canonical_question,
        promotion_status=promotion_status,
    )
    db.put_document(doc, commit=False)
    db.put_episode(ep, commit=False)
    db.put_atom(atom, commit=False)
    db.commit()


def test_collect_candidates_groups_quality_archive_families(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    _seed_atom(
        db,
        atom_id="at_tool_completed",
        question="What tool.completed event occurred?",
        answer="**Event**: tool.completed\n**Data**: {\"tool\": \"rg\"}",
        canonical_question="activity: tool.completed",
    )
    _seed_atom(
        db,
        atom_id="at_generic",
        question="Files",
        answer="A generic heading atom that should not stay in the live retrieval surface.",
    )
    db.close()

    candidates, summary = collect_candidates(db_path=db_path)

    assert summary["candidate_count"] == 2
    assert summary["family_counts"]["low_signal_tool_completed"] == 1
    assert summary["family_counts"]["generic_heading"] == 1
    assert {item["atom_id"] for item in candidates} == {"at_tool_completed", "at_generic"}


def test_apply_archive_updates_matching_atoms(tmp_path: Path) -> None:
    db_path = tmp_path / "evomap.db"
    db = KnowledgeDB(str(db_path))
    db.init_schema()
    _seed_atom(
        db,
        atom_id="at_tool_completed",
        question="What tool.completed event occurred?",
        answer="**Event**: tool.completed\n**Data**: {\"tool\": \"rg\"}",
        canonical_question="activity: tool.completed",
    )
    db.close()

    candidates, _ = collect_candidates(db_path=db_path)
    result = apply_archive(db_path=db_path, candidates=candidates)

    assert result["updated"] == 1

    db2 = KnowledgeDB(str(db_path))
    archived = db2.get_atom("at_tool_completed")
    assert archived is not None
    assert archived.promotion_status == "archived"
    assert archived.promotion_reason == "quality_archive:low_signal_tool_completed"
    db2.close()
