"""Tests for WP3 Evolution Queue.

Tests for:
- test plan submission + listing pending
- test approve → execute flow
- test reject blocks execution
- test revision flow
- test dry_run doesn't modify DB
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chatgptrest.evomap.evolution.models import (
    ApprovalRecord,
    EvolutionPlan,
    PlanOperation,
    PlanStatus,
)
from chatgptrest.evomap.evolution.queue import ApprovalQueue
from chatgptrest.evomap.evolution.executor import ExecutionResult, PlanExecutor
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.schema import Atom


class TestEvolutionQueue(unittest.TestCase):
    """Test the approval queue for evolution plans."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "evolution_queue.db")
        self.queue = ApprovalQueue(db_path=self.db_path)

    def tearDown(self):
        self.queue.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_submit_and_list_pending(self):
        """Test plan submission and listing pending plans."""
        plan = EvolutionPlan(
            title="Test Plan",
            description="Test description",
            created_by="test_agent",
            target_atoms=["at_001", "at_002"],
        )
        plan.add_operation(PlanOperation(op_type="promote", target_id="at_001", params={}))

        plan_id = self.queue.submit_plan(plan)
        self.assertIsNotNone(plan_id)

        pending = self.queue.list_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].plan_id, plan_id)
        self.assertEqual(pending[0].status, PlanStatus.PENDING_APPROVAL.value)

    def test_approve_execute_flow(self):
        """Test approve → execute flow."""
        plan = EvolutionPlan(
            title="Approve Test",
            description="Test approve flow",
            created_by="test_agent",
            target_atoms=[],
        )
        plan_id = self.queue.submit_plan(plan)

        approval = self.queue.approve(plan_id, "reviewer_1", "Looks good")
        self.assertEqual(approval.decision, "approved")
        self.assertEqual(approval.plan_id, plan_id)

        plan = self.queue.get_plan(plan_id)
        self.assertEqual(plan.status, PlanStatus.APPROVED.value)

    def test_reject_blocks_execution(self):
        """Test that rejected plans cannot be executed."""
        plan = EvolutionPlan(
            title="Reject Test",
            description="Test reject flow",
            created_by="test_agent",
            target_atoms=[],
        )
        plan_id = self.queue.submit_plan(plan)

        approval = self.queue.reject(plan_id, "reviewer_1", "Not ready")
        self.assertEqual(approval.decision, "rejected")

        plan = self.queue.get_plan(plan_id)
        self.assertEqual(plan.status, PlanStatus.REJECTED.value)

    def test_revision_flow(self):
        """Test revision request flow."""
        plan = EvolutionPlan(
            title="Revision Test",
            description="Test revision flow",
            created_by="test_agent",
            target_atoms=[],
        )
        plan_id = self.queue.submit_plan(plan)

        approval = self.queue.request_revision(plan_id, "reviewer_1", "Needs more detail")
        self.assertEqual(approval.decision, "revision_requested")

        plan = self.queue.get_plan(plan_id)
        self.assertEqual(plan.status, PlanStatus.REVISION_REQUESTED.value)

    def test_get_approvals(self):
        """Test retrieving approval records."""
        plan = EvolutionPlan(
            title="Approvals Test",
            description="Test approvals",
            created_by="test_agent",
            target_atoms=[],
        )
        plan_id = self.queue.submit_plan(plan)

        self.queue.approve(plan_id, "reviewer_1", "LGTM")
        approvals = self.queue.get_approvals(plan_id)
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0].reviewer, "reviewer_1")

    def test_queue_storage_uses_json_payloads(self):
        """Test stored plan and approval payloads are valid JSON."""
        plan = EvolutionPlan(
            title="JSON Plan",
            description="Test queue serialization",
            created_by="test_agent",
            target_atoms=["at_json_1"],
        )
        plan.add_operation(PlanOperation(op_type="promote", target_id="at_json_1", params={"target_status": "candidate"}))
        plan_id = self.queue.submit_plan(plan)
        self.queue.approve(plan_id, "reviewer_json", "LGTM", conditions=["keep staged"])

        row = self.queue.connect().execute(
            "SELECT target_atoms, operations FROM evolution_plans WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()
        approval_row = self.queue.connect().execute(
            "SELECT conditions FROM approval_records WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()

        self.assertEqual(json.loads(row["target_atoms"]), ["at_json_1"])
        self.assertEqual(json.loads(row["operations"])[0]["params"]["target_status"], "candidate")
        self.assertEqual(json.loads(approval_row["conditions"]), ["keep staged"])


class TestPlanExecutor(unittest.TestCase):
    """Test the plan executor."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.queue_db = os.path.join(self.tmp_dir, "evolution_queue.db")
        self.kb_db = os.path.join(self.tmp_dir, "knowledge.db")

        self.queue = ApprovalQueue(db_path=self.queue_db)
        self.db = KnowledgeDB(db_path=self.kb_db)
        self.db.init_schema()

        self.executor = PlanExecutor(self.queue, self.db)

    def tearDown(self):
        self.queue.close()
        self.db.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_dry_run_no_modification(self):
        """Test that dry_run doesn't modify the database."""
        atom = Atom(question="Test Q", answer="Test A")
        self.db.put_atom(atom)

        plan = EvolutionPlan(
            title="Dry Run Test",
            description="Test dry run",
            created_by="test_agent",
            target_atoms=[atom.atom_id],
        )
        plan.add_operation(PlanOperation(op_type="update_atom", target_id=atom.atom_id, params={"answer": "Updated A"}))
        plan_id = self.queue.submit_plan(plan)
        self.queue.approve(plan_id, "reviewer", "OK")

        result = self.executor.dry_run(plan_id)
        self.assertTrue(result.success)
        self.assertTrue(any("dry run" in w.lower() for w in result.warnings))

        updated_atom = self.db.get_atom(atom.atom_id)
        self.assertEqual(updated_atom.answer, "Test A")

    def test_execute_approved_plan(self):
        """Test executing an approved plan."""
        atom = Atom(
            question="Test Q",
            answer="Use chatgptrest/evomap/knowledge/db.py which contains the KnowledgeDB class.",
            promotion_status="candidate",
        )
        self.db.put_atom(atom)

        plan = EvolutionPlan(
            title="Execute Test",
            description="Test execution",
            created_by="test_agent",
            target_atoms=[atom.atom_id],
        )
        plan.add_operation(PlanOperation(op_type="promote", target_id=atom.atom_id, params={"target_status": "active"}))
        plan_id = self.queue.submit_plan(plan)
        self.queue.approve(plan_id, "reviewer", "OK")

        result = self.executor.execute(plan_id)
        self.assertTrue(result.success)

        updated_atom = self.db.get_atom(atom.atom_id)
        self.assertEqual(updated_atom.promotion_status, "active")

    def test_execute_rolls_back_partial_changes(self):
        """Test failed execution rolls back prior operations in the same plan."""
        atom = Atom(question="Rollback Q", answer="Original answer", promotion_status="staged")
        self.db.put_atom(atom)

        plan = EvolutionPlan(
            title="Rollback Test",
            description="Plan should roll back prior writes on failure",
            created_by="test_agent",
            target_atoms=[atom.atom_id],
        )
        plan.add_operation(PlanOperation(op_type="update_atom", target_id=atom.atom_id, params={"answer": "Updated answer"}))
        plan.add_operation(PlanOperation(op_type="promote", target_id=atom.atom_id, params={"target_status": "active"}))
        plan_id = self.queue.submit_plan(plan)
        self.queue.approve(plan_id, "reviewer", "OK")

        result = self.executor.execute(plan_id)

        self.assertFalse(result.success)
        self.assertEqual(result.executed_operations, [])
        self.assertTrue(any("rolled back" in warning.lower() for warning in result.warnings))

        rolled_back_atom = self.db.get_atom(atom.atom_id)
        self.assertEqual(rolled_back_atom.answer, "Original answer")
        self.assertEqual(rolled_back_atom.promotion_status, "staged")

    def test_execute_supersede_operation_uses_governed_transition(self):
        """Test supersede operation routes through the governed transition path."""
        atom = Atom(question="Old answer", answer="Old answer", promotion_status="active")
        replacement = Atom(question="New answer", answer="New answer", promotion_status="candidate")
        self.db.put_atom(atom)
        self.db.put_atom(replacement)

        plan = EvolutionPlan(
            title="Supersede Test",
            description="Mark old atom superseded",
            created_by="test_agent",
            target_atoms=[atom.atom_id],
        )
        plan.add_operation(
            PlanOperation(
                op_type="supersede",
                target_id=atom.atom_id,
                params={"superseded_by": replacement.atom_id},
            )
        )
        plan_id = self.queue.submit_plan(plan)
        self.queue.approve(plan_id, "reviewer", "OK")

        result = self.executor.execute(plan_id)

        self.assertTrue(result.success)
        updated = self.db.get_atom(atom.atom_id)
        self.assertEqual(updated.promotion_status, "superseded")
        self.assertEqual(updated.superseded_by, replacement.atom_id)

    def test_cannot_execute_unapproved(self):
        """Test that unapproved plans cannot be executed."""
        plan = EvolutionPlan(
            title="Unapproved Test",
            description="Test unapproved",
            created_by="test_agent",
            target_atoms=[],
        )
        plan_id = self.queue.submit_plan(plan)

        can_exec, reason = self.executor.can_execute(plan_id)
        self.assertFalse(can_exec)
        self.assertIn("not approved", reason)

    def test_reject_blocks_execution(self):
        """Test that rejected plans cannot be executed."""
        plan = EvolutionPlan(
            title="Reject Block Test",
            description="Test rejection blocks execution",
            created_by="test_agent",
            target_atoms=[],
        )
        plan_id = self.queue.submit_plan(plan)
        self.queue.reject(plan_id, "reviewer", "Not good")

        can_exec, reason = self.executor.can_execute(plan_id)
        self.assertFalse(can_exec)


if __name__ == "__main__":
    unittest.main(verbosity=2)
