"""Tests for EvoMap P4 batch fix — promotion rules + empty CQ fix."""
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock

import pytest

from chatgptrest.evomap.knowledge.p4_batch_fix import (
    _normalize_to_canonical,
    fix_empty_canonical_questions,
    promote_eligible_atoms,
    run_p4_batch_fix,
)


@pytest.fixture
def mock_db():
    """Create an in-memory DB with realistic atoms for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_p4.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS atoms (
            atom_id TEXT PRIMARY KEY,
            question TEXT,
            answer TEXT,
            atom_type TEXT DEFAULT 'qa',
            quality_auto REAL DEFAULT 0,
            value_auto REAL DEFAULT 0,
            stability TEXT DEFAULT 'stable',
            status TEXT DEFAULT 'candidate',
            canonical_question TEXT DEFAULT '',
            promotion_status TEXT DEFAULT 'candidate',
            promotion_reason TEXT DEFAULT '',
            valid_from REAL DEFAULT 0,
            episode_id TEXT DEFAULT '',
            source_quality REAL DEFAULT 0,
            scores_json TEXT DEFAULT '',
            groundedness REAL DEFAULT NULL,
            applicability TEXT DEFAULT ''
        )
    """)

    # Good atom — should be promoted
    conn.execute(
        """INSERT INTO atoms (atom_id, question, answer, quality_auto, stability,
           canonical_question, promotion_status) VALUES
           ('a1', 'How to restart Redis?', 'Use systemctl restart redis', 0.7,
            'stable', 'How to restart Redis?', 'candidate')"""
    )

    # Low quality — should NOT be promoted
    conn.execute(
        """INSERT INTO atoms (atom_id, question, answer, quality_auto, stability,
           canonical_question, promotion_status) VALUES
           ('a2', 'Q2', 'A2', 0.1, 'stable', 'cq2', 'candidate')"""
    )

    # No CQ — should NOT be promoted until fixed
    conn.execute(
        """INSERT INTO atoms (atom_id, question, answer, quality_auto, stability,
           canonical_question, promotion_status) VALUES
           ('a3', 'Check disk space on server', 'Use df -h', 0.5, 'stable', '', 'candidate')"""
    )

    # Superseded — should NOT be promoted
    conn.execute(
        """INSERT INTO atoms (atom_id, question, answer, quality_auto, stability,
           canonical_question, promotion_status) VALUES
           ('a4', 'Old question', 'Old answer', 0.8, 'superseded', 'cq4', 'candidate')"""
    )

    # Already active — should stay active
    conn.execute(
        """INSERT INTO atoms (atom_id, question, answer, quality_auto, stability,
           canonical_question, promotion_status) VALUES
           ('a5', 'Active Q', 'Active A', 0.9, 'stable', 'cq5', 'active')"""
    )

    # Procedure type with no CQ — should get "How to X?" prefix
    conn.execute(
        """INSERT INTO atoms (atom_id, question, answer, quality_auto, stability,
           canonical_question, promotion_status, atom_type) VALUES
           ('a6', 'Deploy to staging', 'Run deploy.sh --staging', 0.6, 'stable',
            '', 'candidate', 'procedure')"""
    )

    conn.commit()

    # Wrap with a mock that returns the connection
    db = MagicMock()
    db.connect.return_value = conn
    return db


def test_normalize_to_canonical_question():
    assert _normalize_to_canonical("How to restart Redis?") == "How to restart Redis?"


def test_normalize_adds_question_mark():
    assert _normalize_to_canonical("Check disk space").endswith("?")


def test_normalize_procedure_prefix():
    result = _normalize_to_canonical("deploy to staging", "procedure")
    assert result.startswith("How to")
    assert result.endswith("?")


def test_normalize_empty():
    assert _normalize_to_canonical("") == ""


def test_promote_eligible_atoms(mock_db):
    result = promote_eligible_atoms(mock_db)
    # Only a1 should be promoted (a2=low quality, a3=no CQ, a4=superseded, a5=already active)
    assert result["promoted"] == 1
    assert result["already_active"] >= 2  # a1 -> active + a5 already active


def test_promote_dry_run(mock_db):
    result = promote_eligible_atoms(mock_db, dry_run=True)
    assert result["promoted"] == 1
    # Verify nothing actually changed
    conn = mock_db.connect()
    count = conn.execute(
        "SELECT COUNT(*) FROM atoms WHERE promotion_status = 'active'"
    ).fetchone()[0]
    assert count == 1  # Only a5 was already active


def test_fix_empty_canonical_questions(mock_db):
    result = fix_empty_canonical_questions(mock_db)
    # a3 and a6 have empty CQ
    assert result["fixed"] >= 2

    conn = mock_db.connect()
    # Verify a3 now has a CQ
    cq = conn.execute(
        "SELECT canonical_question FROM atoms WHERE atom_id = 'a3'"
    ).fetchone()[0]
    assert cq and cq.strip()


def test_run_p4_batch_fix(mock_db):
    result = run_p4_batch_fix(mock_db)
    assert result.cq_fixed >= 2
    # After CQ fix, a3 and a6 should now be promotable too
    assert result.promoted >= 3  # a1 + a3 + a6
    assert result.elapsed_ms >= 0


def test_promotion_after_cq_fix_order(mock_db):
    """Verify CQ is fixed BEFORE promotion so atoms become eligible."""
    result = run_p4_batch_fix(mock_db)
    conn = mock_db.connect()

    # a3 should now be promoted (had no CQ before, quality=0.5 >= 0.3)
    status = conn.execute(
        "SELECT promotion_status FROM atoms WHERE atom_id = 'a3'"
    ).fetchone()[0]
    assert status == "active"

    # a6 should also be promoted (procedure, quality=0.6)
    status6 = conn.execute(
        "SELECT promotion_status FROM atoms WHERE atom_id = 'a6'"
    ).fetchone()[0]
    assert status6 == "active"
