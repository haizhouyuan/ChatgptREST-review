"""P2 Groundedness Checker tests.

Tests:
1. Path extraction from text
2. Unit extraction from text
3. Existing path → high score
4. Missing path → low score
5. Low score → demotion to staged
6. No references → score 1.0 (cannot disprove)
7. Relative path extraction and resolution
"""

from __future__ import annotations

import os
import tempfile

import pytest

from chatgptrest.evomap.knowledge.groundedness_checker import (
    GroundednessResult,
    P2Stats,
    check_atom_groundedness,
    check_paths_exist,
    extract_paths,
    extract_relpaths,
    extract_units,
    run_p2_groundedness,
)
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    kdb = KnowledgeDB(db_path=path)
    kdb.connect()
    kdb.init_schema()
    yield kdb
    kdb.close()
    os.unlink(path)


# ═══════════════════════════════════════════════════════════════════
# Path/Unit extraction
# ═══════════════════════════════════════════════════════════════════


class TestExtraction:

    def test_extract_absolute_paths(self):
        text = "Config at /vol1/1000/projects/ChatgptREST/config.py and /home/user/.bashrc"
        paths = extract_paths(text)
        assert "/vol1/1000/projects/ChatgptREST/config.py" in paths
        assert "/home/user/.bashrc" in paths

    def test_extract_relative_paths(self):
        text = "See chatgptrest/core/client_issues.py and ops/maint_daemon.py"
        paths = extract_relpaths(text)
        assert any("chatgptrest/core/client_issues.py" in p for p in paths)
        assert any("ops/maint_daemon.py" in p for p in paths)

    def test_extract_units(self):
        text = "Managed by chatgptrest-maint-daemon.service and backup.timer"
        units = extract_units(text)
        assert "chatgptrest-maint-daemon.service" in units
        assert "backup.timer" in units

    def test_no_matches(self):
        text = "This atom has no paths or units."
        assert extract_paths(text) == []
        assert extract_relpaths(text) == []
        assert extract_units(text) == []


# ═══════════════════════════════════════════════════════════════════
# Path check scoring
# ═══════════════════════════════════════════════════════════════════


class TestPathCheck:

    def test_existing_path(self):
        # /tmp always exists
        score, evidence = check_paths_exist(["/tmp"])
        assert score == 1.0
        assert any("✓" in e for e in evidence)

    def test_missing_path(self):
        score, evidence = check_paths_exist(["/nonexistent/path/foo.py"])
        assert score == 0.0
        assert any("✗" in e for e in evidence)

    def test_mixed_paths(self):
        score, evidence = check_paths_exist(["/tmp", "/nonexistent/foo.py"])
        assert score == 0.5

    def test_no_paths(self):
        score, evidence = check_paths_exist([])
        assert score == 1.0
        assert "no_paths_referenced" in evidence


# ═══════════════════════════════════════════════════════════════════
# Full atom check
# ═══════════════════════════════════════════════════════════════════


class TestAtomGroundedness:

    def test_no_references(self):
        result = check_atom_groundedness("at_1", "Simple advice", 1000.0)
        assert result.overall == 1.0

    def test_existing_path_in_answer(self):
        result = check_atom_groundedness(
            "at_2", "Check the file at /tmp for details", 1000.0
        )
        assert result.overall >= 0.7

    def test_missing_path_in_answer(self):
        result = check_atom_groundedness(
            "at_3", "See /vol1/nonexistent/fake/path/config.py for details", 1000.0
        )
        assert result.overall < 0.7


# ═══════════════════════════════════════════════════════════════════
# Batch run + demotion
# ═══════════════════════════════════════════════════════════════════


class TestBatchGroundedness:

    def test_batch_run_with_demotion(self, db):
        # An atom referencing a path that doesn't exist
        bad = Atom(
            atom_id="at_bad",
            question="Where is the config?",
            answer="See /vol1/nonexistent/completely/fake/service/config.py for the config.",
            promotion_status="candidate",
            valid_from=1000.0,
        )
        db.put_atom(bad)

        # An atom with no references
        good = Atom(
            atom_id="at_good",
            question="How to deploy?",
            answer="Run the deploy script with npm run deploy.",
            promotion_status="candidate",
            valid_from=1000.0,
        )
        db.put_atom(good)
        db.commit()

        stats = run_p2_groundedness(db)
        assert stats.total == 2
        assert stats.checked == 2

        # Good atom should keep candidate
        good_after = db.get_atom("at_good")
        assert good_after.promotion_status == "candidate"

        # Bad atom should be demoted
        bad_after = db.get_atom("at_bad")
        assert bad_after.promotion_status == "staged"
        assert bad_after.promotion_reason == "low_groundedness"

    def test_batch_run_updates_staged_atoms_for_runtime_visibility(self, db):
        staged = Atom(
            atom_id="at_staged",
            question="What completed?",
            answer="team.run.completed",
            promotion_status="staged",
            valid_from=1000.0,
        )
        db.put_atom(staged)
        db.commit()

        stats = run_p2_groundedness(db)
        assert stats.total == 1
        assert stats.checked == 1

        staged_after = db.get_atom("at_staged")
        assert staged_after is not None
        assert staged_after.promotion_status == "staged"
        assert staged_after.groundedness >= 0.7
