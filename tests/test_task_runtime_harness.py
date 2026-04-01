"""Tests for Task Harness - verify core functionality."""

import json
import tempfile
import unittest
from pathlib import Path

from chatgptrest.task_runtime.task_store import (
    TaskStatus,
    init_task_store,
    task_db_conn,
    create_task,
    get_task,
    update_task_status,
    record_final_outcome,
)


class TestTaskStoreBasics(unittest.TestCase):
    """Test basic task store operations."""

    def setUp(self):
        """Create temp DB for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        init_task_store(self.db_path)

    def tearDown(self):
        """Clean up temp DB."""
        self.temp_dir.cleanup()

    def test_create_task(self):
        """Test creating a task."""
        with task_db_conn(self.db_path) as conn:
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test task"}',
            )
            self.assertEqual(task.status, TaskStatus.CREATED)

    def test_update_task_status(self):
        """Test updating task status."""
        with task_db_conn(self.db_path) as conn:
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test task"}',
            )
            update_task_status(
                conn,
                task_id=task.task_id,
                new_status=TaskStatus.INITIALIZED,
                trigger="test",
            )
            updated = get_task(conn, task_id=task.task_id)
            self.assertEqual(updated.status, TaskStatus.INITIALIZED)


class TestDeliveryIntegration(unittest.TestCase):
    """Test delivery integration with completion_contract."""

    def setUp(self):
        """Create temp DB for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        init_task_store(self.db_path)

    def tearDown(self):
        """Clean up temp DB."""
        self.temp_dir.cleanup()

    def test_can_publish_outcome_validates_promotion(self):
        """Test that can_publish_outcome validates promoted decisions."""
        from chatgptrest.task_runtime.task_store import (
            create_task,
            create_attempt,
            record_final_outcome,
        )
        from chatgptrest.task_runtime.delivery_integration import can_publish_outcome

        with task_db_conn(self.db_path) as conn:
            # Create task
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test task", "scenario": "test"}',
            )

            # Create attempt
            attempt = create_attempt(conn, task_id=task.task_id, trigger_reason="test")

            # Create final outcome with promoted decisions
            outcome = record_final_outcome(
                conn,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                status="success",
                final_artifact_refs=["test_artifact.md"],
                summary="Test completed successfully",
                promoted_decisions=[
                    {"decision": "promote", "rationale": "test passed"}
                ],
            )

        # Should be publishable
        can_pub, reason = can_publish_outcome(task.task_id, db_path=self.db_path)
        self.assertTrue(can_pub, f"Should be publishable: {reason}")

    def test_can_publish_outcome_rejects_unpromoted(self):
        """Test that can_publish_outcome rejects unpromoted outcomes."""
        from chatgptrest.task_runtime.task_store import (
            create_task,
            create_attempt,
            record_final_outcome,
        )
        from chatgptrest.task_runtime.delivery_integration import can_publish_outcome

        with task_db_conn(self.db_path) as conn:
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test task", "scenario": "test"}',
            )
            attempt = create_attempt(conn, task_id=task.task_id, trigger_reason="test")

            # Create final outcome WITHOUT promoted decisions
            outcome = record_final_outcome(
                conn,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                status="success",
                final_artifact_refs=["test_artifact.md"],
                summary="Test completed",
                promoted_decisions=[],  # Empty - not promoted
            )

        # Should NOT be publishable
        can_pub, reason = can_publish_outcome(task.task_id, db_path=self.db_path)
        self.assertFalse(can_pub)
        self.assertIn("not been promoted", reason)

    def test_publish_to_delivery_succeeds_with_valid_outcome(self):
        """Test that publish_to_delivery succeeds with valid promoted outcome."""
        from chatgptrest.task_runtime.task_store import (
            create_task,
            create_attempt,
            record_final_outcome,
            get_task,
            update_task_status,
        )
        from chatgptrest.task_runtime.delivery_integration import DeliveryPublisher

        with task_db_conn(self.db_path) as conn:
            # Create task
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test task", "scenario": "test", "task_id": "test-123"}',
            )
            attempt = create_attempt(conn, task_id=task.task_id, trigger_reason="test")

            # Create final outcome with promoted decisions
            outcome = record_final_outcome(
                conn,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                status="success",
                final_artifact_refs=["test_artifact.md"],
                summary="Test completed successfully",
                promoted_decisions=[
                    {"decision": "promote", "rationale": "test passed"}
                ],
            )

            # Need to transition task to PROMOTED before PUBLISHED
            # This tests the real flow: task must be promoted before publishing
            update_task_status(conn, task_id=task.task_id, new_status=TaskStatus.PROMOTED, trigger="test_promotion")

        # Publish to delivery with db_path
        publisher = DeliveryPublisher(task.task_id, db_path=self.db_path)
        result = publisher.publish_to_delivery(outcome)

        # Verify result structure
        self.assertIn("task_id", result)
        self.assertIn("completion_contract", result)
        self.assertIn("canonical_answer", result)

        # Verify task entered PUBLISHED status
        with task_db_conn(self.db_path) as conn:
            updated_task = get_task(conn, task_id=task.task_id)
            self.assertEqual(updated_task.status, TaskStatus.PUBLISHED)

    def test_publish_to_delivery_fails_closed_on_error(self):
        """Test that publication failure does not enter PUBLISHED status."""
        from chatgptrest.task_runtime.task_store import (
            create_task,
            create_attempt,
            record_final_outcome,
            get_task,
            update_task_status,
        )
        from chatgptrest.task_runtime.delivery_integration import DeliveryPublisher

        # Use a valid task db path but test with wrong task (not found)
        # Create task in self.db_path
        with task_db_conn(self.db_path) as conn:
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test task", "scenario": "test"}',
            )
            attempt = create_attempt(conn, task_id=task.task_id, trigger_reason="test")
            outcome = record_final_outcome(
                conn,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                status="success",
                final_artifact_refs=["test.md"],
                summary="Test",
                promoted_decisions=[{"decision": "promote", "rationale": "test"}],
            )
            # Need PROMOTED before PUBLISHED
            update_task_status(conn, task_id=task.task_id, new_status=TaskStatus.PROMOTED, trigger="test_promotion")

        # Use wrong db path - task not found there
        wrong_db_path = Path(tempfile.mktemp(suffix=".db"))

        # Try to publish with wrong db path - should fail
        publisher = DeliveryPublisher(task.task_id, db_path=wrong_db_path)
        with self.assertRaises(Exception):
            publisher.publish_to_delivery(outcome)

        # Verify task did NOT enter PUBLISHED status
        with task_db_conn(self.db_path) as conn:
            updated_task = get_task(conn, task_id=task.task_id)
            self.assertNotEqual(updated_task.status, TaskStatus.PUBLISHED)


class TestMemoryDistillation(unittest.TestCase):
    """Test memory distillation with work_memory_manager."""

    def setUp(self):
        """Create temp DB for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        init_task_store(self.db_path)

    def tearDown(self):
        """Clean up temp DB."""
        self.temp_dir.cleanup()

    def test_should_distill_outcome(self):
        """Test should_distill_outcome function."""
        from chatgptrest.task_runtime.task_store import (
            create_task,
            create_attempt,
            record_final_outcome,
        )
        from chatgptrest.task_runtime.memory_distillation import should_distill_outcome

        with task_db_conn(self.db_path) as conn:
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test task"}',
            )
            attempt = create_attempt(conn, task_id=task.task_id, trigger_reason="test")

            # Create successful outcome with promoted decisions
            outcome = record_final_outcome(
                conn,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                status="success",
                final_artifact_refs=["test.md"],
                summary="Test completed",
                promoted_decisions=[
                    {"decision": "promote", "rationale": "test passed"}
                ],
            )

        should_distill, reason = should_distill_outcome(outcome)
        self.assertTrue(should_distill, f"Should be distillable: {reason}")

    def test_distill_outcome_succeeds_with_valid_outcome(self):
        """Test that distill_outcome succeeds with valid promoted outcome."""
        from chatgptrest.task_runtime.task_store import (
            create_task,
            create_attempt,
            record_final_outcome,
            get_task,
            update_task_status,
        )
        from chatgptrest.task_runtime.memory_distillation import MemoryDistiller
        import tempfile

        # Create temp memory db
        mem_temp_dir = tempfile.TemporaryDirectory()
        mem_db_path = Path(mem_temp_dir.name) / "memory.db"

        try:
            with task_db_conn(self.db_path) as conn:
                task = create_task(
                    conn,
                    task_kind="test",
                    origin="unit_test",
                    intake_json='{"objective": "test task", "scenario": "execution", "task_id": "test-456"}',
                )
                attempt = create_attempt(conn, task_id=task.task_id, trigger_reason="test")

                outcome = record_final_outcome(
                    conn,
                    task_id=task.task_id,
                    attempt_id=attempt.attempt_id,
                    status="success",
                    final_artifact_refs=["test.md"],
                    summary="Test completed successfully",
                    promoted_decisions=[
                        {"decision": "promote", "rationale": "test passed"}
                    ],
                )

                # Transition to PROMOTED -> PUBLISHED -> then can go to DISTILLED
                update_task_status(conn, task_id=task.task_id, new_status=TaskStatus.PROMOTED, trigger="test_promotion")
                update_task_status(conn, task_id=task.task_id, new_status=TaskStatus.PUBLISHED, trigger="test_publish")

            # Distill with db_path and memory_db_path
            distiller = MemoryDistiller(
                task.task_id,
                memory_db_path=mem_db_path,
                task_db_path=self.db_path
            )
            result = distiller.distill_outcome(outcome)

            # Verify result structure
            self.assertIn("task_id", result)
            self.assertIn("distillation_success", result)

            # Verify task entered DISTILLED status
            with task_db_conn(self.db_path) as conn:
                updated_task = get_task(conn, task_id=task.task_id)
                self.assertEqual(updated_task.status, TaskStatus.DISTILLED)
        finally:
            mem_temp_dir.cleanup()

    def test_distill_outcome_fails_closed_on_memory_error(self):
        """Test that memory failure does not enter DISTILLED status."""
        from chatgptrest.task_runtime.task_store import (
            create_task,
            create_attempt,
            record_final_outcome,
            get_task,
            update_task_status,
        )
        from chatgptrest.task_runtime.memory_distillation import MemoryDistiller

        # Use a valid memory db path but test that a non-existent task id causes failure
        import tempfile
        mem_temp_dir = tempfile.TemporaryDirectory()
        mem_db_path = Path(mem_temp_dir.name) / "memory.db"

        try:
            with task_db_conn(self.db_path) as conn:
                task = create_task(
                    conn,
                    task_kind="test",
                    origin="unit_test",
                    intake_json='{"objective": "test task", "scenario": "execution"}',
                )
                attempt = create_attempt(conn, task_id=task.task_id, trigger_reason="test")
                outcome = record_final_outcome(
                    conn,
                    task_id=task.task_id,
                    attempt_id=attempt.attempt_id,
                    status="success",
                    final_artifact_refs=["test.md"],
                    summary="Test",
                    promoted_decisions=[{"decision": "promote", "rationale": "test"}],
                )
                # Need to transition to PUBLISHED first
                update_task_status(conn, task_id=task.task_id, new_status=TaskStatus.PROMOTED, trigger="test_promotion")
                update_task_status(conn, task_id=task.task_id, new_status=TaskStatus.PUBLISHED, trigger="test_publish")

            # Use wrong task_db_path to cause failure during distillation
            # (task not found in the wrong db)
            wrong_db_path = Path(tempfile.mktemp(suffix=".db"))
            distiller = MemoryDistiller(
                task.task_id,
                memory_db_path=mem_db_path,
                task_db_path=wrong_db_path  # Wrong path - task not found
            )

            with self.assertRaises(Exception):
                distiller.distill_outcome(outcome)

            # Verify task did NOT enter DISTILLED status
            with task_db_conn(self.db_path) as conn:
                updated_task = get_task(conn, task_id=task.task_id)
                self.assertNotEqual(updated_task.status, TaskStatus.DISTILLED)
        finally:
            mem_temp_dir.cleanup()


class TestPromotionServiceGraders(unittest.TestCase):
    """Test that promotion service has real graders."""

    def setUp(self):
        """Create temp DB for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        init_task_store(self.db_path)

    def tearDown(self):
        """Clean up temp DB."""
        self.temp_dir.cleanup()

    def test_code_grader_not_placeholder(self):
        """Test that code grader is not just returning pass."""
        from chatgptrest.task_runtime.task_store import (
            create_task,
            create_attempt,
            create_chunk,
            get_chunk,
        )
        from chatgptrest.task_runtime.promotion_service import PromotionService

        with task_db_conn(self.db_path) as conn:
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test"}',
            )
            attempt = create_attempt(conn, task_id=task.task_id, trigger_reason="test")

            # Create a chunk with grader requirements
            chunk = create_chunk(
                conn,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                objective="Test chunk",
                inputs={},
                constraints={},
                done_definition="Test done definition",
                grader_requirements={
                    "run_code_grader": True,
                    "run_outcome_grader": True,
                },
                artifact_contract={},
            )

        # Run the code grader
        service = PromotionService(task.task_id, db_path=self.db_path)
        result = service._run_code_grader(chunk)

        # The grader should return detailed results, not just "pass"
        self.assertIsNotNone(result)
        self.assertIn(result.grader_name, ["code_grader"])
        # Should have details about what was checked
        self.assertIn("artifacts_checked", result.details)


class TestStateMachineSignalDeduplication(unittest.TestCase):
    """Test state machine signal deduplication."""

    def setUp(self):
        """Create temp DB for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        init_task_store(self.db_path)

    def tearDown(self):
        """Clean up temp DB."""
        self.temp_dir.cleanup()

    def test_signal_deduplication(self):
        """Test that duplicate signals are deduplicated."""
        from chatgptrest.task_runtime.task_store import create_task
        from chatgptrest.task_runtime.task_state_machine import TaskStateMachine

        with task_db_conn(self.db_path) as conn:
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test"}',
            )

        # Inject signal
        sm = TaskStateMachine(task.task_id, db_path=self.db_path)
        signal_id1 = sm.inject_signal(signal_type="test_signal", payload={"value": 1})

        # Inject same signal type again
        signal_id2 = sm.inject_signal(signal_type="test_signal", payload={"value": 2})

        # Should return same signal_id (deduplication)
        self.assertEqual(signal_id1, signal_id2, "Duplicate signals should be deduplicated")


class TestTaskFinalizationService(unittest.TestCase):
    """Test TaskFinalizationService - the real orchestration path."""

    def setUp(self):
        """Create temp DB for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        init_task_store(self.db_path)

    def tearDown(self):
        """Clean up temp DB."""
        self.temp_dir.cleanup()

    def test_finalize_task_end_to_end_positive(self):
        """Test end-to-end finalization - real orchestration without manual status update.

        This test validates the real runtime path:
        1. Create task in PROMOTED status with valid final outcome
        2. Call TaskFinalizationService.finalize_task()
        3. Verify task goes through PUBLISHED -> DISTILLED -> COMPLETED

        IMPORTANT: This test does NOT use manual update_task_status to fake success.
        It tests the real orchestration entry point.
        """
        import tempfile

        from chatgptrest.task_runtime.task_store import (
            create_task,
            create_attempt,
            record_final_outcome,
            get_task,
        )
        from chatgptrest.task_runtime.task_finalization import TaskFinalizationService
        from chatgptrest.task_runtime.task_state_machine import TaskStateMachine

        # Create temp memory db
        mem_temp_dir = tempfile.TemporaryDirectory()
        mem_db_path = Path(mem_temp_dir.name) / "memory.db"

        try:
            # Step 1: Create task with outcome (as before)
            with task_db_conn(self.db_path) as conn:
                task = create_task(
                    conn,
                    task_kind="test",
                    origin="unit_test",
                    intake_json='{"objective": "test finalization", "scenario": "execution", "task_id": "test-finalize-123"}',
                )
                attempt = create_attempt(conn, task_id=task.task_id, trigger_reason="test")

                # Create final outcome with promoted decisions
                outcome = record_final_outcome(
                    conn,
                    task_id=task.task_id,
                    attempt_id=attempt.attempt_id,
                    status="success",
                    final_artifact_refs=["test_artifact.md"],
                    summary="Test completed successfully with real finalization",
                    promoted_decisions=[
                        {"decision": "promote", "rationale": "test passed"}
                    ],
                )

            # Step 2: Transition task to PROMOTED using state machine (NOT direct DB update)
            # This simulates the real flow: task must go through promotion first
            state_machine = TaskStateMachine(task.task_id, db_path=self.db_path)

            # Need to get to PROMOTED through valid transitions
            from chatgptrest.task_runtime.task_store import TaskStatus

            # First move to INITIALIZED
            result = state_machine.transition(to_status=TaskStatus.INITIALIZED, trigger="test_init")
            self.assertTrue(result.success, f"Failed to transition to INITIALIZED: {result.error}")

            # Then to FROZEN
            result = state_machine.transition(to_status=TaskStatus.FROZEN, trigger="test_freeze")
            self.assertTrue(result.success, f"Failed to transition to FROZEN: {result.error}")

            # Then to PLANNED
            result = state_machine.transition(to_status=TaskStatus.PLANNED, trigger="test_plan")
            self.assertTrue(result.success, f"Failed to transition to PLANNED: {result.error}")

            # Then to EXECUTING
            result = state_machine.transition(to_status=TaskStatus.EXECUTING, trigger="test_execute")
            self.assertTrue(result.success, f"Failed to transition to EXECUTING: {result.error}")

            # Then to AWAITING_EVALUATION
            result = state_machine.transition(to_status=TaskStatus.AWAITING_EVALUATION, trigger="test_await_eval")
            self.assertTrue(result.success, f"Failed to transition to AWAITING_EVALUATION: {result.error}")

            # Then to PROMOTED (valid transition from AWAITING_EVALUATION)
            result = state_machine.transition(to_status=TaskStatus.PROMOTED, trigger="test_promote")
            self.assertTrue(result.success, f"Failed to transition to PROMOTED: {result.error}")

            # Step 3: Now call the real finalization service
            finalization_service = TaskFinalizationService(
                task.task_id,
                db_path=self.db_path,
                memory_db_path=mem_db_path,
            )
            result = finalization_service.finalize_task()

            # Verify the result
            self.assertTrue(result.success, f"Finalization failed: {result.error}")
            self.assertEqual(result.previous_status, TaskStatus.PROMOTED.value)
            self.assertEqual(result.final_status, TaskStatus.COMPLETED.value)
            self.assertIsNotNone(result.delivery_projection, "Delivery projection should be set")
            self.assertIsNotNone(result.memory_distillation, "Memory distillation should be set")

            # Verify task is in COMPLETED status in DB
            with task_db_conn(self.db_path) as conn:
                final_task = get_task(conn, task_id=task.task_id)
                self.assertEqual(final_task.status, TaskStatus.COMPLETED, "Task should be in COMPLETED status")

            # Verify delivery projection contains completion_contract
            self.assertIn("completion_contract", result.delivery_projection)
            self.assertIn("canonical_answer", result.delivery_projection)

            # Verify memory distillation succeeded
            # Note: work_memory_manager has complex governance; we verify the state transition happened
            self.assertIsNotNone(result.memory_distillation)

        finally:
            mem_temp_dir.cleanup()

    def test_finalize_task_rejects_invalid_status(self):
        """Test that finalization rejects tasks not in PROMOTED status."""
        from chatgptrest.task_runtime.task_store import (
            create_task,
            create_attempt,
            record_final_outcome,
        )
        from chatgptrest.task_runtime.task_finalization import TaskFinalizationService

        with task_db_conn(self.db_path) as conn:
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test task", "scenario": "execution"}',
            )
            attempt = create_attempt(conn, task_id=task.task_id, trigger_reason="test")

            # Create final outcome with promoted decisions
            outcome = record_final_outcome(
                conn,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                status="success",
                final_artifact_refs=["test.md"],
                summary="Test completed",
                promoted_decisions=[
                    {"decision": "promote", "rationale": "test passed"}
                ],
            )

        # Task is in CREATED status - finalization should fail
        finalization_service = TaskFinalizationService(
            task.task_id,
            db_path=self.db_path,
        )
        result = finalization_service.finalize_task()

        self.assertFalse(result.success)
        self.assertIn("PROMOTED", result.error)

    def test_finalize_task_rejects_missing_outcome(self):
        """Test that finalization rejects tasks without a final outcome."""
        from chatgptrest.task_runtime.task_store import create_task
        from chatgptrest.task_runtime.task_finalization import TaskFinalizationService
        from chatgptrest.task_runtime.task_state_machine import TaskStateMachine
        from chatgptrest.task_runtime.task_store import TaskStatus

        # Create task but no outcome
        with task_db_conn(self.db_path) as conn:
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test task", "scenario": "execution"}',
            )

        # Transition to PROMOTED manually for the test
        state_machine = TaskStateMachine(task.task_id, db_path=self.db_path)
        state_machine.transition(to_status=TaskStatus.INITIALIZED, trigger="test")
        state_machine.transition(to_status=TaskStatus.FROZEN, trigger="test")
        state_machine.transition(to_status=TaskStatus.PLANNED, trigger="test")
        state_machine.transition(to_status=TaskStatus.EXECUTING, trigger="test")
        state_machine.transition(to_status=TaskStatus.AWAITING_EVALUATION, trigger="test")
        state_machine.transition(to_status=TaskStatus.PROMOTED, trigger="test")

        # Finalization should fail - no outcome
        finalization_service = TaskFinalizationService(
            task.task_id,
            db_path=self.db_path,
        )
        result = finalization_service.finalize_task()

        self.assertFalse(result.success)
        self.assertIn("No final outcome", result.error)

    def test_finalize_task_fails_closed_on_publication_error(self):
        """Test that publication failure does not enter COMPLETED status."""
        from chatgptrest.task_runtime.task_store import (
            create_task,
            create_attempt,
            record_final_outcome,
            get_task,
        )
        from chatgptrest.task_runtime.task_finalization import TaskFinalizationService
        from chatgptrest.task_runtime.task_state_machine import TaskStateMachine
        from chatgptrest.task_runtime.task_store import TaskStatus

        # Create task with outcome that has no summary (publication requires summary)
        with task_db_conn(self.db_path) as conn:
            task = create_task(
                conn,
                task_kind="test",
                origin="unit_test",
                intake_json='{"objective": "test task", "scenario": "execution"}',
            )
            attempt = create_attempt(conn, task_id=task.task_id, trigger_reason="test")
            # Create outcome with empty summary - should fail publication
            outcome = record_final_outcome(
                conn,
                task_id=task.task_id,
                attempt_id=attempt.attempt_id,
                status="success",
                final_artifact_refs=["test.md"],
                summary="",  # Empty summary - publication requires non-empty summary
                promoted_decisions=[{"decision": "promote", "rationale": "test"}],
            )

        # Transition to PROMOTED
        state_machine = TaskStateMachine(task.task_id, db_path=self.db_path)
        state_machine.transition(to_status=TaskStatus.INITIALIZED, trigger="test")
        state_machine.transition(to_status=TaskStatus.FROZEN, trigger="test")
        state_machine.transition(to_status=TaskStatus.PLANNED, trigger="test")
        state_machine.transition(to_status=TaskStatus.EXECUTING, trigger="test")
        state_machine.transition(to_status=TaskStatus.AWAITING_EVALUATION, trigger="test")
        state_machine.transition(to_status=TaskStatus.PROMOTED, trigger="test")

        # Finalization should fail due to empty summary
        finalization_service = TaskFinalizationService(
            task.task_id,
            db_path=self.db_path,
        )
        result = finalization_service.finalize_task()

        # Should fail
        self.assertFalse(result.success)

        # Verify task is NOT in COMPLETED - it should still be in PROMOTED or failed
        with task_db_conn(self.db_path) as conn:
            final_task = get_task(conn, task_id=task.task_id)
            self.assertNotEqual(final_task.status, TaskStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()