"""Tests for WP4 Relations Layer.

Tests for:
- test provenance chain CRUD
- test supersession chain traversal
- test find_by_commit/agent/task
- test relation types as edges
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.relations import (
    ProvenanceChain,
    RelationManager,
    RelationType,
)
from chatgptrest.evomap.knowledge.schema import Atom, Edge


class TestProvenanceChain(unittest.TestCase):
    """Test provenance chain CRUD operations."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "knowledge.db")
        self.db = KnowledgeDB(db_path=self.db_path)
        self.db.init_schema()
        self.manager = RelationManager(db_path=self.db_path, db=self.db)

    def tearDown(self):
        self.manager.close()
        self.db.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_add_and_get_provenance(self):
        """Test adding and retrieving provenance."""
        atom = Atom(question="Test Q", answer="Test A")
        self.db.put_atom(atom)

        chain = ProvenanceChain(
            atom_id=atom.atom_id,
            task_id="task_001",
            run_id="run_001",
            commit_hash="abc123",
            branch="main",
            agent_id="agent_001",
        )
        self.manager.add_provenance(atom.atom_id, chain)

        retrieved = self.manager.get_provenance(atom.atom_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.atom_id, atom.atom_id)
        self.assertEqual(retrieved.task_id, "task_001")
        self.assertEqual(retrieved.run_id, "run_001")
        self.assertEqual(retrieved.commit_hash, "abc123")
        self.assertEqual(retrieved.branch, "main")
        self.assertEqual(retrieved.agent_id, "agent_001")

    def test_get_provenance_nonexistent(self):
        """Test retrieving provenance for nonexistent atom."""
        result = self.manager.get_provenance("nonexistent")
        self.assertIsNone(result)

    def test_add_provenance_preserves_first_writer(self):
        """Test later writes do not overwrite the first provenance record."""
        atom = Atom(question="Immutable Q", answer="Immutable A")
        self.db.put_atom(atom)

        first = ProvenanceChain(atom_id=atom.atom_id, task_id="task_first", agent_id="agent_first")
        second = ProvenanceChain(atom_id=atom.atom_id, task_id="task_second", agent_id="agent_second")

        self.manager.add_provenance(atom.atom_id, first)
        self.manager.add_provenance(atom.atom_id, second)

        retrieved = self.manager.get_provenance(atom.atom_id)
        self.assertEqual(retrieved.task_id, "task_first")
        self.assertEqual(retrieved.agent_id, "agent_first")


class TestSupersessionChain(unittest.TestCase):
    """Test supersession chain traversal."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "knowledge.db")
        self.db = KnowledgeDB(db_path=self.db_path)
        self.db.init_schema()
        self.manager = RelationManager(db_path=self.db_path, db=self.db)

    def tearDown(self):
        self.manager.close()
        self.db.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_supersession_chain_traversal(self):
        """Test following supersedes edges."""
        atom1 = Atom(question="Old Q", answer="Old A")
        atom2 = Atom(question="New Q", answer="New A")
        atom3 = Atom(question="Newest Q", answer="Newest A")

        self.db.put_atom(atom1)
        self.db.put_atom(atom2)
        self.db.put_atom(atom3)

        edge1 = Edge(
            from_id=atom2.atom_id,
            to_id=atom1.atom_id,
            edge_type=RelationType.SUPERSEDES.value,
            from_kind="atom",
            to_kind="atom",
        )
        edge2 = Edge(
            from_id=atom3.atom_id,
            to_id=atom2.atom_id,
            edge_type=RelationType.SUPERSEDES.value,
            from_kind="atom",
            to_kind="atom",
        )
        self.db.put_edge(edge1)
        self.db.put_edge(edge2)

        chain = self.manager.get_supersession_chain(atom3.atom_id)
        self.assertEqual(len(chain), 2)
        self.assertIn(atom2.atom_id, chain)
        self.assertIn(atom1.atom_id, chain)

    def test_supersession_chain_breaks_cycle(self):
        """Test traversal stops when supersedes edges contain a cycle."""
        atom1 = Atom(question="Cycle Q1", answer="Cycle A1")
        atom2 = Atom(question="Cycle Q2", answer="Cycle A2")

        self.db.put_atom(atom1)
        self.db.put_atom(atom2)

        self.db.put_edge(Edge(
            from_id=atom1.atom_id,
            to_id=atom2.atom_id,
            edge_type=RelationType.SUPERSEDES.value,
            from_kind="atom",
            to_kind="atom",
        ))
        self.db.put_edge(Edge(
            from_id=atom2.atom_id,
            to_id=atom1.atom_id,
            edge_type=RelationType.SUPERSEDES.value,
            from_kind="atom",
            to_kind="atom",
        ))

        chain = self.manager.get_supersession_chain(atom1.atom_id)

        self.assertEqual(chain, [atom2.atom_id, atom1.atom_id])


class TestFindBy(unittest.TestCase):
    """Test finding atoms by various provenance criteria."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "knowledge.db")
        self.db = KnowledgeDB(db_path=self.db_path)
        self.db.init_schema()
        self.manager = RelationManager(db_path=self.db_path, db=self.db)

    def tearDown(self):
        self.manager.close()
        self.db.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_find_by_commit(self):
        """Test finding atoms by commit hash."""
        atom1 = Atom(question="Q1", answer="A1")
        atom2 = Atom(question="Q2", answer="A2")
        self.db.put_atom(atom1)
        self.db.put_atom(atom2)

        self.manager.add_provenance(atom1.atom_id, ProvenanceChain(atom_id=atom1.atom_id, commit_hash="abc123"))
        self.manager.add_provenance(atom2.atom_id, ProvenanceChain(atom_id=atom2.atom_id, commit_hash="abc123"))

        results = self.manager.find_by_commit("abc123")
        self.assertEqual(len(results), 2)
        self.assertIn(atom1.atom_id, results)
        self.assertIn(atom2.atom_id, results)

    def test_find_by_agent(self):
        """Test finding atoms by agent ID."""
        atom = Atom(question="Q3", answer="A3")
        self.db.put_atom(atom)

        self.manager.add_provenance(atom.atom_id, ProvenanceChain(atom_id=atom.atom_id, agent_id="agent_x"))

        results = self.manager.find_by_agent("agent_x")
        self.assertEqual(len(results), 1)
        self.assertIn(atom.atom_id, results)

    def test_find_by_task(self):
        """Test finding atoms by task ID."""
        atom = Atom(question="Q4", answer="A4")
        self.db.put_atom(atom)

        self.manager.add_provenance(atom.atom_id, ProvenanceChain(atom_id=atom.atom_id, task_id="task_y"))

        results = self.manager.find_by_task("task_y")
        self.assertEqual(len(results), 1)
        self.assertIn(atom.atom_id, results)


class TestRelationTypes(unittest.TestCase):
    """Test relation types as edges."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "knowledge.db")
        self.db = KnowledgeDB(db_path=self.db_path)
        self.db.init_schema()
        self.manager = RelationManager(db_path=self.db_path, db=self.db)

    def tearDown(self):
        self.manager.close()
        self.db.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_add_edge_with_relation_type(self):
        """Test adding edge with relation type."""
        atom1 = Atom(question="Q1", answer="A1")
        atom2 = Atom(question="Q2", answer="A2")
        self.db.put_atom(atom1)
        self.db.put_atom(atom2)

        self.manager.add_edge(
            from_id=atom2.atom_id,
            to_id=atom1.atom_id,
            edge_type=RelationType.SUPERSEDES,
            from_kind="atom",
            to_kind="atom",
        )

        edges = self.db.get_edges_from(atom2.atom_id)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].edge_type, RelationType.SUPERSEDES.value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
