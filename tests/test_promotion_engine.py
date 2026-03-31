"""WP1 + WP2 Promotion Engine Tests.

Tests:
1. Promotion from staged → candidate → active (with groundedness passing)
2. Promotion blocked when groundedness fails
3. Quarantine + audit trail
4. Rollback
5. Retrieval only returns active atoms
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom, PromotionStatus
from chatgptrest.evomap.knowledge.promotion_engine import PromotionEngine
from chatgptrest.evomap.knowledge.groundedness_checker import (
    check_code_symbols,
    check_atom_groundedness,
    enforce_promotion_gate,
)


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


def _make_atom(db, atom_id, promotion_status="staged", valid_from=0.0, answer="test answer") -> Atom:
    """Helper to create and insert an atom."""
    atom = Atom(
        atom_id=atom_id,
        episode_id="ep_1",
        question=f"Question for {atom_id}",
        answer=answer,
        canonical_question="test question",
        valid_from=valid_from,
        status="scored",
        promotion_status=promotion_status,
    )
    db.put_atom(atom)
    return atom


class TestCodeSymbols:
    """Test check_code_symbols function."""

    def test_check_existing_symbol(self):
        """Test that known symbols are found."""
        score, evidence = check_code_symbols(["KnowledgeDB", "Atom"])
        assert score > 0
        assert any("✓" in e for e in evidence)

    def test_check_nonexistent_symbol(self):
        """Test that unknown symbols are not found."""
        score, evidence = check_code_symbols(["NonExistentClassXYZ123"])
        assert score == 0.0

    def test_empty_symbols(self):
        """Test empty input returns score 1.0."""
        score, evidence = check_code_symbols([])
        assert score == 1.0

    def test_check_symbols_uses_configured_project_root(self, monkeypatch, tmp_path):
        """Test that project root can be overridden for non-default deployments."""
        package_dir = tmp_path / "chatgptrest"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "custom_symbol.py").write_text(
            "class CustomGroundedThing:\n    pass\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("EVOMAP_PROJECT_ROOT", str(tmp_path))

        score, evidence = check_code_symbols(["CustomGroundedThing"])

        assert score == 1.0
        assert any("CustomGroundedThing" in line for line in evidence)


class TestGroundednessCheck:
    """Test groundedness check integration."""

    def test_atom_groundedness_with_code_symbols(self):
        """Test that atom groundedness includes code symbols."""
        answer = "Use the KnowledgeDB class to store atoms."
        result = check_atom_groundedness("at_test", answer, 0.0)

        assert result.code_symbol_score > 0
        assert result.code_symbols_checked > 0

    def test_enforce_promotion_gate_passes(self, db):
        """Test enforce_promotion_gate passes for grounded atom."""
        atom = _make_atom(
            db,
            "at_grounded",
            promotion_status="candidate",
            answer="Use /vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/db.py which contains the KnowledgeDB class.",
            valid_from=0.0,
        )

        passed, record = enforce_promotion_gate(db, atom.atom_id)

        assert passed is True
        assert record.passed is True
        assert record.atom_id == atom.atom_id

    def test_enforce_promotion_gate_fails(self, db):
        """Test enforce_promotion_gate fails for ungrounded atom."""
        atom = _make_atom(
            db,
            "at_ungrounded",
            promotion_status="candidate",
            answer="Use NonExistentClassXYZ999 that doesn't exist anywhere.",
            valid_from=0.0,
        )

        passed, record = enforce_promotion_gate(db, atom.atom_id)

        assert passed is False
        assert record.passed is False


class TestPromotionEngine:
    """Test PromotionEngine."""

    def test_promote_staged_to_candidate(self, db):
        """Test valid promotion: staged → candidate."""
        atom = _make_atom(db, "at_1", promotion_status="staged")
        engine = PromotionEngine(db)

        result = engine.promote(
            atom.atom_id,
            PromotionStatus.CANDIDATE,
            reason="passed_p1_checks",
        )

        assert result.success is True
        assert result.to_status == "candidate"

        updated = db.get_atom(atom.atom_id)
        assert updated.promotion_status == "candidate"

    def test_promote_to_active_requires_groundedness(self, db):
        """Test promotion to active requires groundedness gate."""
        atom = _make_atom(
            db,
            "at_active_test",
            promotion_status="candidate",
            answer="Use chatgptrest/evomap/knowledge/db.py for storage in the KnowledgeDB class.",
        )
        engine = PromotionEngine(db)

        result = engine.promote(
            atom.atom_id,
            PromotionStatus.ACTIVE,
            reason="ready_for_production",
        )

        assert result.success is True
        assert result.groundedness_passed is True

    def test_promote_blocked_by_groundedness(self, db):
        """Test promotion to active blocked when groundedness fails."""
        atom = _make_atom(
            db,
            "at_fail_gate",
            promotion_status="candidate",
            answer="Use NonExistentClassXYZ999 that doesn't exist anywhere in the codebase.",
        )
        engine = PromotionEngine(db)

        result = engine.promote(
            atom.atom_id,
            PromotionStatus.ACTIVE,
            reason="attempt_promotion",
        )

        assert result.success is False
        assert result.groundedness_passed is False

    def test_invalid_transition(self, db):
        """Test invalid transition is rejected."""
        atom = _make_atom(db, "at_invalid", promotion_status="archived")
        engine = PromotionEngine(db)

        result = engine.promote(
            atom.atom_id,
            PromotionStatus.ACTIVE,
            reason="should_fail",
        )

        assert result.success is False
        assert "invalid_transition" in result.error

    def test_quarantine(self, db):
        """Test quarantine moves atom to archived."""
        atom = _make_atom(db, "at_quarantine", promotion_status="active")
        engine = PromotionEngine(db)

        result = engine.quarantine(
            atom.atom_id,
            reason="needs_review",
            actor="admin",
        )

        assert result.success is True
        assert result.to_status == "archived"

    def test_supersede_sets_status_and_replacement_pointer(self, db):
        """Test supersede moves atom to superseded and preserves replacement pointer."""
        atom = _make_atom(db, "at_supersede", promotion_status="active")
        replacement = _make_atom(db, "at_replacement", promotion_status="candidate")
        engine = PromotionEngine(db)

        result = engine.supersede(
            atom.atom_id,
            replacement.atom_id,
            reason="replaced_with_newer_answer",
            actor="admin",
        )

        assert result.success is True
        assert result.to_status == "superseded"

        updated = db.get_atom(atom.atom_id)
        assert updated.promotion_status == "superseded"
        assert updated.superseded_by == replacement.atom_id

    def test_rollback(self, db):
        """Test rollback moves atom back to staged."""
        atom = _make_atom(db, "at_rollback", promotion_status="candidate")
        engine = PromotionEngine(db)

        result = engine.rollback(
            atom.atom_id,
            reason="needs_rework",
            actor="admin",
        )

        assert result.success is True
        assert result.to_status == "staged"

    def test_audit_trail(self, db):
        """Test that audit trail records all transitions."""
        atom = _make_atom(db, "at_audit", promotion_status="staged")
        engine = PromotionEngine(db)

        engine.promote(atom.atom_id, PromotionStatus.CANDIDATE, reason="test1")
        atom = db.get_atom(atom.atom_id)
        atom.answer = "Use chatgptrest/evomap/knowledge/db.py for storage in KnowledgeDB."
        db.put_atom(atom)
        engine.promote(atom.atom_id, PromotionStatus.ACTIVE, reason="test2")

        trail = engine.get_audit_trail(atom.atom_id)

        assert len(trail) >= 2
        statuses = [t.to_status for t in trail]
        assert "candidate" in statuses
        assert "active" in statuses



# NOTE: Retrieval promotion_status filtering is tested in test_evomap_e2e.py
# which properly populates the FTS5 virtual table. The _make_atom helper here
# only inserts into the atoms table, not the FTS5 index, so retrieval tests
# would always return empty results.
