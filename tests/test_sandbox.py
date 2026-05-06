"""Tests for EvoMapSandbox (WP6)."""

from __future__ import annotations

import os
import tempfile
import time

import pytest

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.relations import ProvenanceChain, RelationManager
from chatgptrest.evomap.knowledge.schema import Atom, AtomStatus, Document, Edge, Entity, Episode, Evidence, PromotionStatus
from chatgptrest.evomap.sandbox import EvoMapSandbox, SandboxInfo


@pytest.fixture
def temp_dir():
    """Create temporary directory for sandbox."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def base_db(temp_dir):
    """Create a base production DB with some data."""
    db_path = os.path.join(temp_dir, "production.db")
    db = KnowledgeDB(db_path=db_path)
    db.init_schema()

    doc = Document(
        doc_id="doc_test",
        source="test",
        project="evomap",
        raw_ref="test",
        title="Test",
        created_at=time.time(),
        updated_at=time.time(),
        hash="",
    )
    db.put_document(doc)
    db.put_episode(Episode(
        episode_id="ep_test",
        doc_id=doc.doc_id,
        episode_type="test",
        title="Base episode",
        summary="Base sandbox episode",
    ))

    atom = Atom(
        atom_id="at_prod_001",
        episode_id="ep_test",
        atom_type="lesson",
        question="What is production knowledge?",
        answer="Production knowledge is stored in the main DB.",
        status=AtomStatus.CANDIDATE.value,
        promotion_status=PromotionStatus.ACTIVE.value,
    )
    atom.compute_hash()
    db.put_atom(atom)
    db.commit()
    db.close()

    yield db_path


def _create_sandbox_atom_bundle(sandbox_db, atom_id: str):
    doc = Document(
        doc_id=f"doc_{atom_id}",
        source="sandbox",
        project="evomap",
        raw_ref=f"sandbox:{atom_id}",
        title=f"Doc {atom_id}",
        created_at=time.time(),
        updated_at=time.time(),
        hash=f"hash_{atom_id}",
    )
    sandbox_db.put_document(doc)

    episode = Episode(
        episode_id=f"ep_{atom_id}",
        doc_id=doc.doc_id,
        episode_type="sandbox",
        title=f"Episode {atom_id}",
        summary=f"Episode for {atom_id}",
    )
    sandbox_db.put_episode(episode)

    atom = Atom(
        atom_id=atom_id,
        episode_id=episode.episode_id,
        atom_type="lesson",
        question=f"Question for {atom_id}?",
        answer=f"Answer for {atom_id}.",
        status=AtomStatus.CANDIDATE.value,
        promotion_status=PromotionStatus.STAGED.value,
    )
    atom.compute_hash()
    sandbox_db.put_atom(atom)

    sandbox_db.put_evidence(Evidence(
        evidence_id=f"ev_{atom_id}",
        atom_id=atom.atom_id,
        doc_id=doc.doc_id,
        span_ref=f"sandbox:{atom_id}",
        excerpt=f"Evidence for {atom_id}",
        evidence_role="supports",
    ))

    entity = Entity(
        entity_id=f"ent_tool_{atom_id}",
        entity_type="tool",
        name=f"Tool {atom_id}",
        normalized_name=f"tool_{atom_id}",
    )
    sandbox_db.put_entity(entity)
    sandbox_db.put_edge(Edge(
        from_id=atom.atom_id,
        to_id=entity.entity_id,
        edge_type="references",
        from_kind="atom",
        to_kind="entity",
    ))

    relation_manager = RelationManager(db=sandbox_db)
    relation_manager.connect()
    relation_manager.add_provenance(
        atom.atom_id,
        ProvenanceChain(atom_id=atom.atom_id, task_id=f"task_{atom_id}", agent_id="sandbox-agent"),
    )
    sandbox_db.commit()
    return atom, doc, episode, entity


@pytest.fixture
def sandbox(base_db, temp_dir):
    """Create EvoMapSandbox instance."""
    return EvoMapSandbox(
        base_db_path=base_db,
        sandbox_dir=os.path.join(temp_dir, "sandboxes"),
    )


class TestCreate:
    def test_create_sandbox_copies_db(self, sandbox, temp_dir):
        info = sandbox.create("test-sandbox", description="Test sandbox")

        assert info.name == "test-sandbox"
        assert info.description == "Test sandbox"
        assert os.path.exists(info.db_path)

        assert len(sandbox.list_sandboxes()) == 1

    def test_create_duplicate_fails(self, sandbox):
        sandbox.create("dup-sandbox")

        with pytest.raises(ValueError, match="already exists"):
            sandbox.create("dup-sandbox")

    def test_create_missing_base_fails(self, sandbox, temp_dir):
        bad_sandbox = EvoMapSandbox(
            base_db_path=os.path.join(temp_dir, "nonexistent.db"),
            sandbox_dir=os.path.join(temp_dir, "sandboxes"),
        )

        with pytest.raises(FileNotFoundError):
            bad_sandbox.create("should-fail")


class TestGet:
    def test_get_sandbox_db(self, sandbox):
        sandbox.create("get-test")
        db = sandbox.get("get-test")

        assert db is not None
        stats = db.stats()
        assert stats["atoms"] >= 1

        db.close()

    def test_get_nonexistent(self, sandbox):
        db = sandbox.get("nonexistent")
        assert db is None


class TestIsolation:
    def test_modifications_dont_affect_production(self, sandbox, base_db):
        sandbox.create("isolation-test")
        sandbox_db = sandbox.get("isolation-test")

        new_atom = Atom(
            atom_id="at_sandbox_001",
            episode_id="ep_sandbox",
            atom_type="lesson",
            question="Sandbox-only question?",
            answer="This only exists in sandbox.",
            status=AtomStatus.CANDIDATE.value,
        )
        new_atom.compute_hash()
        sandbox_db.put_atom(new_atom)
        sandbox_db.commit()
        sandbox_db.close()

        prod_db = KnowledgeDB(db_path=base_db)
        prod_db.connect()
        prod_conn = prod_db.connect()
        prod_rows = prod_conn.execute("SELECT atom_id FROM atoms").fetchall()
        prod_atom_ids = [r[0] for r in prod_rows]
        assert "at_sandbox_001" not in prod_atom_ids
        prod_db.close()

    def test_production_data_available_in_sandbox(self, sandbox, base_db):
        sandbox.create("data-test")
        sandbox_db = sandbox.get("data-test")

        prod_atom = sandbox_db.get_atom("at_prod_001")
        assert prod_atom is not None
        assert prod_atom.atom_id == "at_prod_001"

        sandbox_db.close()


class TestDiff:
    def test_diff_shows_added_atoms(self, sandbox):
        sandbox.create("diff-test")
        sandbox_db = sandbox.get("diff-test")

        new_atom = Atom(
            atom_id="at_diff_new",
            episode_id="ep_diff",
            atom_type="lesson",
            question="New question?",
            answer="New answer.",
            status=AtomStatus.CANDIDATE.value,
        )
        new_atom.compute_hash()
        sandbox_db.put_atom(new_atom)
        sandbox_db.commit()
        sandbox_db.close()

        diff = sandbox.diff("diff-test")

        assert "at_diff_new" in diff.added_atoms
        assert len(diff.modified_atoms) >= 0

    def test_diff_nonexistent(self, sandbox):
        diff = sandbox.diff("nonexistent")
        assert diff is None


class TestMergeBack:
    def test_merge_back_sets_staged_status(self, sandbox):
        sandbox.create("merge-test")
        sandbox_db = sandbox.get("merge-test")
        new_atom, doc, episode, entity = _create_sandbox_atom_bundle(sandbox_db, "at_merge_001")
        sandbox_db.close()

        result = sandbox.merge_back("merge-test", atom_ids=["at_merge_001"])

        assert result.ok is True
        assert "at_merge_001" in result.merged_atom_ids

        prod_db = KnowledgeDB(db_path=sandbox.base_db_path)
        prod_db.connect()
        merged_atom = prod_db.get_atom("at_merge_001")
        assert merged_atom is not None
        assert merged_atom.promotion_status == PromotionStatus.STAGED.value
        assert prod_db.get_document(doc.doc_id) is not None
        assert prod_db.get_episode(episode.episode_id) is not None
        assert len(prod_db.list_evidence_for_atom("at_merge_001")) == 1
        entity_row = prod_db.connect().execute(
            "SELECT * FROM entities WHERE entity_id = ?",
            (entity.entity_id,),
        ).fetchone()
        assert entity_row is not None
        rel_manager = RelationManager(db=prod_db)
        rel_manager.connect()
        provenance = rel_manager.get_provenance("at_merge_001")
        assert provenance is not None
        prod_db.close()

    def test_merge_nonexistent_fails(self, sandbox):
        sandbox.create("fail-merge")

        result = sandbox.merge_back("fail-merge", atom_ids=["nonexistent"])

        assert result.ok is False
        assert len(result.conflicts) == 1

    def test_merge_all_new_atoms(self, sandbox):
        sandbox.create("merge-all")
        sandbox_db = sandbox.get("merge-all")

        for i in range(3):
            _create_sandbox_atom_bundle(sandbox_db, f"at_multi_{i}")
        sandbox_db.close()

        result = sandbox.merge_back("merge-all")

        assert len(result.merged_atom_ids) == 3


class TestDestroy:
    def test_destroy_removes_files(self, sandbox):
        sandbox.create("destroy-test")
        info = sandbox.list_sandboxes()[0]

        assert os.path.exists(info.db_path)

        result = sandbox.destroy("destroy-test")

        assert result is True
        assert len(sandbox.list_sandboxes()) == 0
        assert not os.path.exists(info.db_path)

    def test_destroy_nonexistent(self, sandbox):
        result = sandbox.destroy("nonexistent")
        assert result is False


class TestCleanupExpired:
    def test_cleanup_removes_expired(self, sandbox, temp_dir):
        sandbox.create("expired-1", ttl_hours=0)
        sandbox.create("keep-2", ttl_hours=72)

        time.sleep(0.1)

        cleaned = sandbox.cleanup_expired()

        assert cleaned == 1
        assert len(sandbox.list_sandboxes()) == 1
        assert sandbox.list_sandboxes()[0].name == "keep-2"

    def test_cleanup_none_expired(self, sandbox):
        sandbox.create("fresh-1", ttl_hours=72)
        sandbox.create("fresh-2", ttl_hours=72)

        cleaned = sandbox.cleanup_expired()

        assert cleaned == 0
        assert len(sandbox.list_sandboxes()) == 2
