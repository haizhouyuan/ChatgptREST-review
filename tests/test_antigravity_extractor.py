"""Tests for AntigravityConversationExtractor.

Creates a mock brain/ directory structure and validates the full
Document → Episode → Atom → Evidence extraction pipeline.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from chatgptrest.evomap.knowledge.extractors.antigravity_extractor import (
    AntigravityExtractor,
    _infer_atom_type,
    _is_artifact_md,
    _split_by_headings,
)
from chatgptrest.evomap.knowledge.schema import AtomType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def brain_dir(tmp_path):
    """Create a mock Antigravity brain directory with sample conversations."""
    brain = tmp_path / "brain"
    brain.mkdir()

    # ── Conversation 1: has implementation_plan + walkthrough ────
    conv1 = brain / "conv-001-test"
    conv1.mkdir()

    impl_plan = conv1 / "implementation_plan.md"
    impl_plan.write_text(
        "# Auth System Redesign\n\n"
        "## 方案选择\n\nWe chose JWT over session-based auth because:\n"
        "- Stateless and scalable\n"
        "- Built-in expiry\n"
        "- Works well with microservices\n\n"
        "## Proposed Changes\n\n"
        "### Component: AuthService\n\n"
        "Add token validation middleware that checks Bearer tokens.\n"
        "This requires changes to 3 files and adds 2 new dependencies.\n\n"
        "## Verification Plan\n\n"
        "Run pytest with auth integration tests.\n"
        "Check token refresh flow works end-to-end.\n",
        encoding="utf-8",
    )
    impl_meta = conv1 / "implementation_plan.md.metadata.json"
    impl_meta.write_text(json.dumps({
        "Summary": "Auth system redesign from session-based to JWT tokens",
        "ArtifactType": "implementation_plan",
    }))

    walkthrough = conv1 / "walkthrough.md"
    walkthrough.write_text(
        "# Auth Redesign Walkthrough\n\n"
        "## Changes Made\n\n"
        "Replaced session middleware with JWT validation.\n"
        "Added token refresh endpoint at /api/auth/refresh.\n\n"
        "## 修复 Bug\n\n"
        "Fixed token expiry check that was using wrong timezone.\n"
        "The bug caused premature token invalidation in UTC+8.\n\n"
        "## Validation Results\n\n"
        "All 15 auth tests passing. Token refresh flow verified.\n",
        encoding="utf-8",
    )
    walk_meta = conv1 / "walkthrough.md.metadata.json"
    walk_meta.write_text(json.dumps({
        "Summary": "Walkthrough of JWT auth implementation with bug fix",
        "ArtifactType": "walkthrough",
    }))

    # task.md (should be skipped)
    task = conv1 / "task.md"
    task.write_text("- [x] Implement JWT\n- [ ] Test refresh\n")
    task_meta = conv1 / "task.md.metadata.json"
    task_meta.write_text(json.dumps({"Summary": "Task checklist", "ArtifactType": "task"}))

    # ── Conversation 2: single domain document ────
    conv2 = brain / "conv-002-test"
    conv2.mkdir()

    analysis = conv2 / "architecture_analysis.md"
    analysis.write_text(
        "# Core Engine Architecture\n\n"
        "The engine uses a plugin-based architecture with these layers:\n"
        "1. Transport layer (HTTP/gRPC)\n"
        "2. Business logic layer\n"
        "3. Data access layer\n\n"
        "Each plugin registers handlers via the ServiceRegistry.\n"
        "This pattern allows runtime extension without recompilation.\n"
        "The key lesson learned is to always version plugin interfaces.\n",
        encoding="utf-8",
    )
    analysis_meta = conv2 / "architecture_analysis.md.metadata.json"
    analysis_meta.write_text(json.dumps({
        "Summary": "Deep analysis of core engine architecture",
        "ArtifactType": "other",
    }))

    # ── Conversation 3: empty/skip dirs ────
    conv3 = brain / "conv-003-empty"
    conv3.mkdir()
    # Only binary files (no MD artifacts)
    (conv3 / "screenshot.png").write_bytes(b"\x89PNG")
    (conv3 / ".system_generated").mkdir()

    return brain


class MockDB:
    """Simple mock that records all puts."""

    def __init__(self):
        self.documents: list = []
        self.episodes: list = []
        self.atoms: list = []
        self.evidences: list = []
        self.committed = False

    def put_document(self, doc):
        self.documents.append(doc)

    def put_episode(self, ep):
        self.episodes.append(ep)

    def put_atom(self, atom):
        self.atoms.append(atom)

    def put_evidence(self, ev):
        self.evidences.append(ev)

    def commit(self):
        self.committed = True


# ---------------------------------------------------------------------------
# Unit tests: helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    """Test helper functions."""

    def test_is_artifact_md_valid(self):
        assert _is_artifact_md("implementation_plan.md")
        assert _is_artifact_md("walkthrough.md")
        assert _is_artifact_md("architecture_analysis.md")

    def test_is_artifact_md_skip_patterns(self):
        assert not _is_artifact_md("plan.md.resolved.123")
        assert not _is_artifact_md("plan.md.metadata.json")
        assert not _is_artifact_md("task.md")  # skip task checklists
        assert not _is_artifact_md("screenshot.png")
        assert not _is_artifact_md("data.json")

    def test_infer_atom_type_decision(self):
        assert _infer_atom_type("方案选择") == AtomType.DECISION
        assert _infer_atom_type("Decision: JWT vs Sessions") == AtomType.DECISION

    def test_infer_atom_type_troubleshooting(self):
        assert _infer_atom_type("修复 Bug") == AtomType.TROUBLESHOOTING
        assert _infer_atom_type("Fix: Token Expiry Issue") == AtomType.TROUBLESHOOTING

    def test_infer_atom_type_procedure(self):
        assert _infer_atom_type("部署步骤") == AtomType.PROCEDURE
        assert _infer_atom_type("Workflow: CI/CD Pipeline") == AtomType.PROCEDURE

    def test_infer_atom_type_lesson(self):
        assert _infer_atom_type("经验总结") == AtomType.LESSON
        assert _infer_atom_type("Lesson Learned") == AtomType.LESSON

    def test_infer_atom_type_default(self):
        assert _infer_atom_type("Proposed Changes") == AtomType.QA

    def test_split_by_headings_basic(self):
        content = (
            "# Title\n\n"
            "## Section One\n\n"
            "Content for section one, which is long enough.\n\n"
            "## Section Two\n\n"
            "Content for section two, also long enough here.\n"
        )
        sections = _split_by_headings(content)
        assert len(sections) == 2
        assert sections[0][0] == "Section One"
        assert "Content for section one" in sections[0][1]
        assert sections[1][0] == "Section Two"

    def test_split_by_headings_h3(self):
        content = (
            "## Parent\n\nParent content that is long enough.\n\n"
            "### Child A\n\nChild A content that is long enough.\n\n"
            "### Child B\n\nChild B content that is long enough.\n"
        )
        sections = _split_by_headings(content)
        assert len(sections) == 3

    def test_split_no_headings_fallback(self):
        content = "# Just a Title\n\nSome content without any H2/H3 headings but long enough to matter and be extracted."
        sections = _split_by_headings(content)
        assert len(sections) == 1
        assert sections[0][0] == "Just a Title"

    def test_split_skips_tiny_sections(self):
        content = "## Big Section\n\nThis is a long enough section.\n\n## Tiny\n\nShort.\n"
        sections = _split_by_headings(content)
        # "Tiny" section has < 30 chars, should be skipped
        assert len(sections) == 1
        assert sections[0][0] == "Big Section"


# ---------------------------------------------------------------------------
# Integration tests: full pipeline
# ---------------------------------------------------------------------------

class TestAntigravityExtractor:
    """Test the full extraction pipeline."""

    def test_scan_finds_conversations(self, brain_dir):
        db = MockDB()
        ext = AntigravityExtractor(db, brain_dir=str(brain_dir))
        convs = ext._scan_conversations()
        # conv-001 has 2 artifacts (impl_plan + walkthrough, task.md skipped)
        # conv-002 has 1 artifact
        # conv-003 has none (only png)
        assert len(convs) == 2
        assert "conv-001-test" in convs
        assert "conv-002-test" in convs
        assert "conv-003-empty" not in convs

    def test_extract_documents(self, brain_dir):
        db = MockDB()
        ext = AntigravityExtractor(db, brain_dir=str(brain_dir))
        docs = list(ext.extract_documents())
        assert len(docs) == 2

        # Check conv-001 doc
        doc1 = next(d for d in docs if d.raw_ref == "conv-001-test")
        assert doc1.source == "antigravity"
        assert doc1.project == "antigravity"
        assert "Auth system redesign" in doc1.title
        meta = json.loads(doc1.meta_json)
        assert meta["artifact_count"] == 2

    def test_extract_episodes(self, brain_dir):
        db = MockDB()
        ext = AntigravityExtractor(db, brain_dir=str(brain_dir))
        docs = list(ext.extract_documents())
        doc1 = next(d for d in docs if d.raw_ref == "conv-001-test")

        episodes = list(ext.extract_episodes(doc1))
        assert len(episodes) == 2  # impl_plan + walkthrough (task.md skipped)

        # Check episode titles
        titles = {ep.title for ep in episodes}
        assert "Implementation Plan" in titles
        assert "Walkthrough" in titles

        # Check metadata in source_ext
        for ep in episodes:
            ext_data = json.loads(ep.source_ext)
            assert "artifact_type" in ext_data
            assert "conversation_id" in ext_data

    def test_extract_atoms(self, brain_dir):
        db = MockDB()
        ext = AntigravityExtractor(db, brain_dir=str(brain_dir))
        docs = list(ext.extract_documents())
        doc1 = next(d for d in docs if d.raw_ref == "conv-001-test")
        episodes = list(ext.extract_episodes(doc1))

        total_atoms = 0
        for ep in episodes:
            atoms = list(ext.extract_atoms(ep))
            total_atoms += len(atoms)

            for atom in atoms:
                assert atom.question  # heading text
                assert atom.answer    # section content
                assert atom.hash      # computed SHA-256
                assert len(atom.answer) >= 30

        # impl_plan has 3 H2 sections (方案选择, Proposed Changes, Verification Plan)
        # walkthrough has 3 H2 sections (Changes Made, 修复 Bug, Validation Results)
        assert total_atoms >= 4  # at least 4 sections long enough

    def test_extract_atoms_type_inference(self, brain_dir):
        db = MockDB()
        ext = AntigravityExtractor(db, brain_dir=str(brain_dir))
        docs = list(ext.extract_documents())
        doc1 = next(d for d in docs if d.raw_ref == "conv-001-test")
        episodes = list(ext.extract_episodes(doc1))

        all_atoms = []
        for ep in episodes:
            all_atoms.extend(ext.extract_atoms(ep))

        atom_types = {a.question: a.atom_type for a in all_atoms}
        # 方案选择 → DECISION
        if "方案选择" in atom_types:
            assert atom_types["方案选择"] == AtomType.DECISION
        # 修复 Bug → TROUBLESHOOTING
        if "修复 Bug" in atom_types:
            assert atom_types["修复 Bug"] == AtomType.TROUBLESHOOTING

    def test_extract_evidence(self, brain_dir):
        db = MockDB()
        ext = AntigravityExtractor(db, brain_dir=str(brain_dir))
        docs = list(ext.extract_documents())
        doc1 = next(d for d in docs if d.raw_ref == "conv-001-test")
        episodes = list(ext.extract_episodes(doc1))

        for ep in episodes:
            atoms = list(ext.extract_atoms(ep))
            for atom in atoms:
                evidences = list(ext.extract_evidence(atom, ep))
                assert len(evidences) == 1
                ev = evidences[0]
                assert ev.atom_id == atom.atom_id
                assert ev.doc_id == doc1.doc_id
                assert ev.span_ref  # file path
                assert ev.excerpt  # excerpt text
                assert ev.evidence_role == "supports"

    def test_extract_all_pipeline(self, brain_dir):
        """Full pipeline: extract_all() populates all DB tables."""
        db = MockDB()
        ext = AntigravityExtractor(db, brain_dir=str(brain_dir))
        ext.extract_all()

        assert db.committed
        assert len(db.documents) == 2  # 2 conversations with artifacts
        assert len(db.episodes) >= 3   # 2 from conv-001 + 1 from conv-002
        assert len(db.atoms) >= 4      # multiple sections from each
        assert len(db.evidences) >= 4  # one per atom

        # Check no duplicates
        doc_ids = {d.doc_id for d in db.documents}
        assert len(doc_ids) == len(db.documents)

    def test_empty_brain_dir(self, tmp_path):
        """Extractor handles missing brain dir gracefully."""
        db = MockDB()
        ext = AntigravityExtractor(db, brain_dir=str(tmp_path / "nonexistent"))
        ext.extract_all()
        assert db.committed
        assert len(db.documents) == 0

    def test_conversation_hash_changes_on_mtime(self, brain_dir):
        """Hash changes when file is modified."""
        import time

        db = MockDB()
        ext = AntigravityExtractor(db, brain_dir=str(brain_dir))
        convs = ext._scan_conversations()

        hash1 = ext._conversation_hash("conv-001-test", convs["conv-001-test"])

        # Ensure mtime changes (sub-second filesystems)
        time.sleep(0.05)

        # Modify a file
        impl_plan = brain_dir / "conv-001-test" / "implementation_plan.md"
        impl_plan.write_text("# Updated content\n\n## New Section\n\nNew content here that is long enough.\n")

        # Reset cache
        ext._conv_artifacts = {}
        convs = ext._scan_conversations()
        hash2 = ext._conversation_hash("conv-001-test", convs["conv-001-test"])

        assert hash1 != hash2
