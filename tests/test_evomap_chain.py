"""P1 Evolution Chain tests — schema migration, backfill, chain construction.

Tests:
1. Schema migration: new columns exist, idempotent
2. valid_from backfill: precedence cascade
3. Chain construction: same canonical → same chain, correct rank
4. Supersession: multi-atom chains mark older as superseded
5. Empty canonical_question: atoms stay staged
6. Idempotency: running twice produces identical results
7. Normalization: case/punctuation variants map to same chain
8. Missing timestamps: atoms get promotion_reason='missing_valid_from'
"""

from __future__ import annotations

import os
import tempfile
import time

import pytest

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import (
    Atom,
    Document,
    Episode,
    PromotionStatus,
)
from chatgptrest.evomap.knowledge.chain_builder import (
    BackfillStats,
    ChainStats,
    build_chains,
    backfill_valid_from,
    normalize_question,
    run_p1_migration,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def db():
    """Create a fresh in-memory-like temp DB for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    kdb = KnowledgeDB(db_path=path)
    kdb.connect()
    kdb.init_schema()
    yield kdb
    kdb.close()
    os.unlink(path)


def _make_atom(db, atom_id, episode_id="ep_1", canonical_question="",
               valid_from=0.0, answer="test answer") -> Atom:
    """Helper to create and insert an atom."""
    atom = Atom(
        atom_id=atom_id,
        episode_id=episode_id,
        question=f"Question for {atom_id}",
        answer=answer,
        canonical_question=canonical_question,
        valid_from=valid_from,
        status="scored",
    )
    db.put_atom(atom)
    return atom


def _make_episode(db, episode_id, doc_id="doc_1",
                  time_start=0.0, time_end=0.0) -> Episode:
    """Helper to create and insert an episode."""
    ep = Episode(
        episode_id=episode_id,
        doc_id=doc_id,
        time_start=time_start,
        time_end=time_end,
    )
    db.put_episode(ep)
    return ep


def _make_doc(db, doc_id, created_at=0.0, updated_at=0.0) -> Document:
    """Helper to create and insert a document."""
    doc = Document(
        doc_id=doc_id,
        created_at=created_at,
        updated_at=updated_at,
    )
    db.put_document(doc)
    return doc


# ═══════════════════════════════════════════════════════════════════
# T1: Schema migration
# ═══════════════════════════════════════════════════════════════════


class TestSchemaMigration:
    """T1: New P1 columns exist and migration is idempotent."""

    def test_new_columns_exist(self, db):
        conn = db.connect()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(atoms)").fetchall()}
        for col in ["promotion_status", "superseded_by", "chain_id",
                     "chain_rank", "is_chain_head", "promotion_reason"]:
            assert col in cols, f"Column {col} missing from atoms table"

    def test_migration_idempotent(self, db):
        """Running init_schema twice should not error."""
        db.init_schema()
        db.init_schema()
        conn = db.connect()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(atoms)").fetchall()}
        indices = {r[1] for r in conn.execute("PRAGMA index_list(atoms)").fetchall()}
        assert "promotion_status" in cols
        assert "idx_atoms_promotion" in indices
        assert "idx_atoms_chain" in indices

    def test_default_values(self, db):
        atom = Atom(atom_id="at_test_defaults", question="Q", answer="A")
        db.put_atom(atom)
        db.commit()
        row = db.get_atom("at_test_defaults")
        assert row.promotion_status == "staged"
        assert row.superseded_by == ""
        assert row.chain_id == ""
        assert row.chain_rank == 0
        assert row.is_chain_head == 0
        assert row.promotion_reason == ""


# ═══════════════════════════════════════════════════════════════════
# T2: valid_from backfill
# ═══════════════════════════════════════════════════════════════════


class TestValidFromBackfill:
    """T2: valid_from populates from episode/document timestamps."""

    def test_backfill_from_episode_end(self, db):
        _make_doc(db, "doc_1", created_at=1000.0, updated_at=2000.0)
        _make_episode(db, "ep_1", doc_id="doc_1", time_start=3000.0, time_end=4000.0)
        _make_atom(db, "at_1", episode_id="ep_1", valid_from=0.0)
        db.commit()

        stats = backfill_valid_from(db)
        atom = db.get_atom("at_1")
        assert atom.valid_from == 4000.0
        assert stats.from_episode_end == 1

    def test_backfill_from_episode_start(self, db):
        _make_doc(db, "doc_1", created_at=1000.0, updated_at=2000.0)
        _make_episode(db, "ep_1", doc_id="doc_1", time_start=3000.0, time_end=0.0)
        _make_atom(db, "at_1", episode_id="ep_1", valid_from=0.0)
        db.commit()

        stats = backfill_valid_from(db)
        atom = db.get_atom("at_1")
        assert atom.valid_from == 3000.0
        assert stats.from_episode_start == 1

    def test_backfill_from_doc_updated(self, db):
        _make_doc(db, "doc_1", created_at=1000.0, updated_at=2000.0)
        _make_episode(db, "ep_1", doc_id="doc_1", time_start=0.0, time_end=0.0)
        _make_atom(db, "at_1", episode_id="ep_1", valid_from=0.0)
        db.commit()

        stats = backfill_valid_from(db)
        atom = db.get_atom("at_1")
        assert atom.valid_from == 2000.0
        assert stats.from_doc_updated == 1

    def test_backfill_from_doc_created(self, db):
        _make_doc(db, "doc_1", created_at=1000.0, updated_at=0.0)
        _make_episode(db, "ep_1", doc_id="doc_1", time_start=0.0, time_end=0.0)
        _make_atom(db, "at_1", episode_id="ep_1", valid_from=0.0)
        db.commit()

        stats = backfill_valid_from(db)
        atom = db.get_atom("at_1")
        assert atom.valid_from == 1000.0
        assert stats.from_doc_created == 1

    def test_backfill_preserves_existing(self, db):
        _make_doc(db, "doc_1")
        _make_episode(db, "ep_1", time_end=9999.0)
        _make_atom(db, "at_1", episode_id="ep_1", valid_from=5000.0)
        db.commit()

        stats = backfill_valid_from(db)
        atom = db.get_atom("at_1")
        assert atom.valid_from == 5000.0  # unchanged
        assert stats.already_set == 1


# ═══════════════════════════════════════════════════════════════════
# T3-T4: Chain construction & supersession
# ═══════════════════════════════════════════════════════════════════


class TestChainConstruction:
    """T3-T4: Chain grouping and supersession marking."""

    def test_singleton_chain(self, db):
        _make_atom(db, "at_1", canonical_question="How to deploy?", valid_from=1000.0)
        db.commit()

        stats = build_chains(db)
        atom = db.get_atom("at_1")
        assert atom.chain_id != ""
        assert atom.chain_rank == 1
        assert atom.is_chain_head == 1
        assert atom.promotion_status == "candidate"
        assert atom.superseded_by == ""
        assert stats.singleton_chains == 1
        assert stats.multi_atom_chains == 0

    def test_multi_atom_chain_supersession(self, db):
        # Three atoms with same canonical question, different timestamps
        _make_atom(db, "at_old", canonical_question="How to deploy?", valid_from=1000.0)
        _make_atom(db, "at_mid", canonical_question="How to deploy?", valid_from=2000.0)
        _make_atom(db, "at_new", canonical_question="How to deploy?", valid_from=3000.0)
        db.commit()

        stats = build_chains(db)

        old = db.get_atom("at_old")
        mid = db.get_atom("at_mid")
        new = db.get_atom("at_new")

        # All share same chain
        assert old.chain_id == mid.chain_id == new.chain_id
        assert old.chain_id != ""

        # Rank ordering
        assert old.chain_rank == 1
        assert mid.chain_rank == 2
        assert new.chain_rank == 3

        # Head is newest
        assert new.is_chain_head == 1
        assert old.is_chain_head == 0
        assert mid.is_chain_head == 0

        # Supersession
        assert new.promotion_status == "candidate"
        assert old.promotion_status == "superseded"
        assert mid.promotion_status == "superseded"
        assert old.superseded_by == "at_new"
        assert mid.superseded_by == "at_new"

        assert stats.multi_atom_chains == 1
        assert stats.superseded_count == 2
        assert stats.candidate_count == 1

    def test_different_questions_different_chains(self, db):
        _make_atom(db, "at_a", canonical_question="How to deploy?", valid_from=1000.0)
        _make_atom(db, "at_b", canonical_question="How to debug?", valid_from=1000.0)
        db.commit()

        stats = build_chains(db)
        a = db.get_atom("at_a")
        b = db.get_atom("at_b")
        assert a.chain_id != b.chain_id
        assert stats.total_chains == 2
        assert stats.singleton_chains == 2


# ═══════════════════════════════════════════════════════════════════
# T5: Empty canonical_question
# ═══════════════════════════════════════════════════════════════════


class TestEmptyCanonical:
    """T5: Atoms without canonical_question stay staged."""

    def test_no_canonical_stays_staged(self, db):
        _make_atom(db, "at_no_cq", canonical_question="", valid_from=1000.0)
        db.commit()

        stats = build_chains(db)
        atom = db.get_atom("at_no_cq")
        assert atom.promotion_status == "staged"
        assert atom.chain_id == ""
        assert atom.promotion_reason == "no_canonical_question"
        assert stats.atoms_without_canonical == 1


# ═══════════════════════════════════════════════════════════════════
# T6: Idempotency
# ═══════════════════════════════════════════════════════════════════


class TestIdempotency:
    """T6: Running build_chains twice produces identical results."""

    def test_chains_idempotent(self, db):
        _make_atom(db, "at_1", canonical_question="How to deploy?", valid_from=1000.0)
        _make_atom(db, "at_2", canonical_question="How to deploy?", valid_from=2000.0)
        db.commit()

        stats1 = build_chains(db)
        # Capture state
        a1_first = db.get_atom("at_1")
        a2_first = db.get_atom("at_2")

        # Run again
        stats2 = build_chains(db)
        a1_second = db.get_atom("at_1")
        a2_second = db.get_atom("at_2")

        assert a1_first.chain_id == a1_second.chain_id
        assert a1_first.chain_rank == a1_second.chain_rank
        assert a1_first.promotion_status == a1_second.promotion_status
        assert a2_first.chain_id == a2_second.chain_id
        assert stats1.total_chains == stats2.total_chains


# ═══════════════════════════════════════════════════════════════════
# T7: Normalization
# ═══════════════════════════════════════════════════════════════════


class TestNormalization:
    """T7: Case/punctuation variants map to same chain."""

    def test_normalize_basic(self):
        assert normalize_question("How to X?") == "how to x"
        assert normalize_question("  HOW  TO  X?  ") == "how to x"
        assert normalize_question("how to x") == "how to x"
        assert normalize_question("How to X!!!") == "how to x"
        assert normalize_question("How to X...") == "how to x"

    def test_variants_same_chain(self, db):
        _make_atom(db, "at_1", canonical_question="How to deploy?", valid_from=1000.0)
        _make_atom(db, "at_2", canonical_question="how to deploy", valid_from=2000.0)
        _make_atom(db, "at_3", canonical_question="  HOW  TO  DEPLOY?  ", valid_from=3000.0)
        db.commit()

        build_chains(db)
        a1 = db.get_atom("at_1")
        a2 = db.get_atom("at_2")
        a3 = db.get_atom("at_3")
        assert a1.chain_id == a2.chain_id == a3.chain_id

    def test_empty_stays_empty(self):
        assert normalize_question("") == ""
        assert normalize_question("   ") == ""


# ═══════════════════════════════════════════════════════════════════
# T8: Missing timestamps
# ═══════════════════════════════════════════════════════════════════


class TestMissingTimestamps:
    """T8: Atoms with no traceable timestamp get promotion_reason."""

    def test_missing_ts_marked(self, db):
        # Atom with no episode link
        _make_atom(db, "at_orphan", episode_id="ep_nonexistent", valid_from=0.0)
        db.commit()

        stats = backfill_valid_from(db)
        atom = db.get_atom("at_orphan")
        assert atom.valid_from == 0.0
        assert atom.promotion_reason == "missing_valid_from"
        assert stats.still_missing == 1


# ═══════════════════════════════════════════════════════════════════
# T9: Full P1 pipeline
# ═══════════════════════════════════════════════════════════════════


class TestP1Pipeline:
    """T9: End-to-end P1 migration."""

    def test_full_pipeline(self, db):
        # Setup: doc → episode → atoms
        _make_doc(db, "doc_1", created_at=1000.0, updated_at=2000.0)
        _make_episode(db, "ep_1", doc_id="doc_1", time_start=3000.0, time_end=4000.0)
        _make_atom(db, "at_1", episode_id="ep_1",
                   canonical_question="How to deploy?", valid_from=0.0)
        _make_atom(db, "at_2", episode_id="ep_1",
                   canonical_question="How to deploy?", valid_from=0.0)
        _make_atom(db, "at_3", episode_id="ep_1",
                   canonical_question="How to debug?", valid_from=0.0)
        _make_atom(db, "at_4", episode_id="ep_1",
                   canonical_question="", valid_from=0.0)
        db.commit()

        report = run_p1_migration(db)

        # Backfill worked
        assert report.backfill.from_episode_end == 4

        # Chains: "deploy" has 2 atoms, "debug" has 1, "" has 1
        assert report.chains.total_chains == 2  # deploy + debug
        assert report.chains.atoms_without_canonical == 1
        assert report.chains.superseded_count == 1  # one older deploy atom

        # Verify the chain head
        deploy_atoms = [db.get_atom(f"at_{i}") for i in [1, 2]]
        heads = [a for a in deploy_atoms if a.is_chain_head == 1]
        assert len(heads) == 1

        # DB query methods work
        candidates = db.list_atoms_by_promotion("candidate", limit=100)
        assert len(candidates) >= 2  # deploy-head + debug singleton

        # Report timing
        assert report.elapsed_ms > 0
