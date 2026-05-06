from __future__ import annotations

import sqlite3
from pathlib import Path

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.retrieval import retrieve, runtime_retrieval_config
from chatgptrest.evomap.knowledge.schema import Atom, Document, Episode


def test_atom_from_row_preserves_scope_fields() -> None:
    atom = Atom.from_row(
        {
            "atom_id": "at_1",
            "episode_id": "ep_1",
            "question": "q",
            "answer": "a",
            "scope_project": "project-alpha",
            "scope_component": "component-x",
        }
    )

    assert atom.scope_project == "project-alpha"
    assert atom.scope_component == "component-x"


def test_init_schema_adds_scope_columns_to_legacy_atoms_table(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_evomap.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE atoms (
                atom_id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL DEFAULT '',
                atom_type TEXT NOT NULL DEFAULT 'qa',
                question TEXT NOT NULL DEFAULT '',
                answer TEXT NOT NULL DEFAULT '',
                canonical_question TEXT NOT NULL DEFAULT '',
                alt_questions TEXT NOT NULL DEFAULT '[]',
                constraints TEXT NOT NULL DEFAULT '[]',
                prerequisites TEXT NOT NULL DEFAULT '[]',
                intent TEXT NOT NULL DEFAULT '',
                format TEXT NOT NULL DEFAULT 'plain',
                applicability TEXT NOT NULL DEFAULT '{}',
                stability TEXT NOT NULL DEFAULT 'versioned',
                status TEXT NOT NULL DEFAULT 'candidate',
                valid_from REAL NOT NULL DEFAULT 0,
                valid_to REAL NOT NULL DEFAULT 0,
                quality_auto REAL NOT NULL DEFAULT 0,
                value_auto REAL NOT NULL DEFAULT 0,
                novelty REAL NOT NULL DEFAULT 0,
                groundedness REAL NOT NULL DEFAULT 0,
                confidence REAL NOT NULL DEFAULT 0,
                reusability REAL NOT NULL DEFAULT 0,
                scores_json TEXT NOT NULL DEFAULT '{}',
                source_quality REAL NOT NULL DEFAULT 0,
                hash TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    db = KnowledgeDB(db_path=str(db_path))
    db.init_schema()

    cols = {row[1] for row in db.connect().execute("PRAGMA table_info(atoms)").fetchall()}
    assert "scope_project" in cols
    assert "scope_component" in cols


def test_put_atom_infers_scope_project_from_episode_document(tmp_path: Path) -> None:
    db = KnowledgeDB(db_path=str(tmp_path / "evomap.db"))
    db.init_schema()

    doc = Document(doc_id="doc_1", project="project-alpha", raw_ref="doc://1", title="Doc 1")
    ep = Episode(episode_id="ep_1", doc_id=doc.doc_id, episode_type="md_section", title="Ep 1")
    atom = Atom(
        atom_id="at_1",
        episode_id=ep.episode_id,
        question="Question",
        answer="Answer",
        applicability='{"component":"component-x"}',
    )

    db.put_document(doc)
    db.put_episode(ep)
    db.put_atom(atom)

    persisted = db.get_atom(atom.atom_id)
    assert persisted is not None
    assert persisted.scope_project == "project-alpha"
    assert persisted.scope_component == "component-x"


def test_put_atom_if_absent_preserves_explicit_scope_fields(tmp_path: Path) -> None:
    db = KnowledgeDB(db_path=str(tmp_path / "evomap.db"))
    db.init_schema()

    atom = Atom(
        atom_id="at_1",
        episode_id="ep_1",
        question="Question",
        answer="Answer",
        scope_project="project-explicit",
        scope_component="component-explicit",
    )

    inserted = db.put_atom_if_absent(atom)
    persisted = db.get_atom(atom.atom_id)

    assert inserted is True
    assert persisted is not None
    assert persisted.scope_project == "project-explicit"
    assert persisted.scope_component == "component-explicit"


def test_bulk_put_atoms_infers_scope_project_for_each_atom(tmp_path: Path) -> None:
    db = KnowledgeDB(db_path=str(tmp_path / "evomap.db"))
    db.init_schema()

    doc = Document(doc_id="doc_1", project="project-bulk", raw_ref="doc://bulk", title="Bulk")
    ep = Episode(episode_id="ep_1", doc_id=doc.doc_id, episode_type="md_section", title="Ep 1")
    db.put_document(doc)
    db.put_episode(ep)

    atoms = [
        Atom(atom_id="at_1", episode_id=ep.episode_id, question="Q1", answer="A1"),
        Atom(atom_id="at_2", episode_id=ep.episode_id, question="Q2", answer="A2"),
    ]

    db.bulk_put_atoms(atoms)

    persisted = [db.get_atom(atom.atom_id) for atom in atoms]
    assert all(item is not None for item in persisted)
    assert {item.scope_project for item in persisted if item is not None} == {"project-bulk"}


def test_retrieve_filters_by_project_scope_when_requested(tmp_path: Path) -> None:
    db = KnowledgeDB(db_path=str(tmp_path / "evomap.db"))
    db.init_schema()

    for project in ("project-alpha", "project-beta"):
        doc = Document(doc_id=f"doc_{project}", project=project, raw_ref=f"doc://{project}", title=project)
        ep = Episode(episode_id=f"ep_{project}", doc_id=doc.doc_id, episode_type="md_section", title=project)
        atom = Atom(
            atom_id=f"at_{project}",
            episode_id=ep.episode_id,
            question="supplier readiness baseline",
            answer=f"{project} supplier readiness baseline",
            scope_project=project,
            quality_auto=0.8,
        )
        db.put_document(doc)
        db.put_episode(ep)
        db.put_atom(atom)

    hits = retrieve(
        db,
        "supplier readiness baseline",
        config=runtime_retrieval_config(surface="diagnostic_path", project_id="project-beta"),
    )

    assert [item.atom.scope_project for item in hits] == ["project-beta"]
