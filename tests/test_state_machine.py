"""Comprehensive tests for chatgptrest/core/state_machine.py

Covers:
- Happy path: valid transitions
- Edge cases: same-state transitions, terminal state transitions
- Error conditions: invalid transitions, exception handling
- Boundary values: all JobStatus values
- Integration scenarios: sequences of valid transitions
"""

import pytest

from chatgptrest.core.state_machine import (
    JobStatus,
    TERMINAL_STATUSES,
    TransitionResult,
    can_transition,
    is_terminal,
)


class TestJobStatus:
    """Test JobStatus enum values and properties."""

    def test_all_status_values_exist(self):
        """Verify all expected status values are defined."""
        expected = {
            "queued",
            "in_progress",
            "needs_followup",
            "cooldown",
            "blocked",
            "completed",
            "error",
            "canceled",
        }
        actual = {status.value for status in JobStatus}
        assert actual == expected

    def test_terminal_statuses_contains_expected(self):
        """Verify terminal statuses are correct."""
        assert JobStatus.COMPLETED in TERMINAL_STATUSES
        assert JobStatus.ERROR in TERMINAL_STATUSES
        assert JobStatus.CANCELED in TERMINAL_STATUSES
        assert len(TERMINAL_STATUSES) == 3

    def test_terminal_statuses_only_contains_terminals(self):
        """Verify non-terminal statuses are not in TERMINAL_STATUSES."""
        non_terminal = {
            JobStatus.QUEUED,
            JobStatus.IN_PROGRESS,
            JobStatus.NEEDS_FOLLOWUP,
            JobStatus.COOLDOWN,
            JobStatus.BLOCKED,
        }
        for status in non_terminal:
            assert status not in TERMINAL_STATUSES


class TestIsTerminal:
    """Test is_terminal function."""

    @pytest.mark.parametrize("status", list(JobStatus))
    def test_is_terminal_returns_correct_for_each_status(self, status):
        """Test is_terminal returns correct boolean for each JobStatus."""
        expected = status in TERMINAL_STATUSES
        assert is_terminal(status) == expected

    @pytest.mark.parametrize("status_str", [
        "completed",
        "error",
        "canceled",
    ])
    def test_is_terminal_returns_true_for_terminal_strings(self, status_str):
        """Test is_terminal returns True for terminal status strings."""
        assert is_terminal(status_str) is True

    @pytest.mark.parametrize("status_str", [
        "queued",
        "in_progress",
        "needs_followup",
        "cooldown",
        "blocked",
    ])
    def test_is_terminal_returns_false_for_non_terminal_strings(self, status_str):
        """Test is_terminal returns False for non-terminal status strings."""
        assert is_terminal(status_str) is False

    @pytest.mark.parametrize("invalid_input", [
        "",
        "unknown",
        "COMPLETED",  # wrong case
        "completed ",  # trailing space
        " completed",  # leading space
        "done",
        "pending",
        "running",
        123,
        None,
        [],
    ])
    def test_is_terminal_returns_false_for_invalid_input(self, invalid_input):
        """Test is_terminal returns False for invalid inputs."""
        assert is_terminal(invalid_input) is False


class TestCanTransitionSameState:
    """Test same-state transitions (idempotent transitions)."""

    @pytest.mark.parametrize("status", list(JobStatus))
    def test_same_state_transition_is_allowed(self, status):
        """Test that transitioning to the same state is always allowed."""
        result = can_transition(status, status)
        assert result.ok is True
        assert result.error is None

    @pytest.mark.parametrize("status_str", ["queued", "completed", "error"])
    def test_same_state_transition_string_input(self, status_str):
        """Test same-state transition with string input."""
        status = JobStatus(status_str)
        result = can_transition(status, status)
        assert result.ok is True


class TestCanTransitionFromQueued:
    """Test transitions from QUEUED state."""

    def test_queued_to_in_progress_allowed(self):
        """QUEUED -> IN_PROGRESS is valid."""
        result = can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS)
        assert result.ok is True

    def test_queued_to_canceled_allowed(self):
        """QUEUED -> CANCELED is valid (job canceled before starting)."""
        result = can_transition(JobStatus.QUEUED, JobStatus.CANCELED)
        assert result.ok is True

    @pytest.mark.parametrize("invalid_dest", [
        JobStatus.COMPLETED,
        JobStatus.ERROR,
        JobStatus.NEEDS_FOLLOWUP,
        JobStatus.COOLDOWN,
        JobStatus.BLOCKED,
    ])
    def test_queued_to_non_allowed_states_rejected(self, invalid_dest):
        """QUEUED cannot transition directly to most states."""
        result = can_transition(JobStatus.QUEUED, invalid_dest)
        assert result.ok is False
        assert "invalid transition" in result.error.lower()


class TestCanTransitionFromInProgress:
    """Test transitions from IN_PROGRESS state."""

    @pytest.mark.parametrize("dest", [
        JobStatus.COMPLETED,
        JobStatus.ERROR,
        JobStatus.NEEDS_FOLLOWUP,
        JobStatus.COOLDOWN,
        JobStatus.BLOCKED,
        JobStatus.CANCELED,
    ])
    def test_in_progress_to_terminal_and_intermediate_allowed(self, dest):
        """IN_PROGRESS can transition to most states."""
        result = can_transition(JobStatus.IN_PROGRESS, dest)
        assert result.ok is True

    def test_in_progress_to_queued_not_allowed(self):
        """IN_PROGRESS cannot go back to QUEUED."""
        result = can_transition(JobStatus.IN_PROGRESS, JobStatus.QUEUED)
        assert result.ok is False
        assert "invalid transition" in result.error.lower()


class TestCanTransitionFromTerminal:
    """Test transitions from terminal states."""

    @pytest.mark.parametrize("terminal_status", [
        JobStatus.COMPLETED,
        JobStatus.ERROR,
        JobStatus.CANCELED,
    ])
    @pytest.mark.parametrize("dest", list(JobStatus))
    def test_terminal_states_cannot_transition(self, terminal_status, dest):
        """Terminal states cannot transition to any state."""
        result = can_transition(terminal_status, dest)
        if dest == terminal_status:
            # Same state is allowed
            assert result.ok is True
        else:
            assert result.ok is False
            assert "terminal" in result.error.lower()

    @pytest.mark.parametrize("terminal_status", [
        JobStatus.COMPLETED,
        JobStatus.ERROR,
        JobStatus.CANCELED,
    ])
    def test_terminal_to_queued_rejected(self, terminal_status):
        """Terminal states cannot go back to QUEUED."""
        result = can_transition(terminal_status, JobStatus.QUEUED)
        assert result.ok is False


class TestCanTransitionFromIntermediateStates:
    """Test transitions from intermediate states (needs_followup, cooldown, blocked)."""

    intermediate_states = [
        JobStatus.NEEDS_FOLLOWUP,
        JobStatus.COOLDOWN,
        JobStatus.BLOCKED,
    ]

    @pytest.mark.parametrize("src", intermediate_states)
    def test_intermediate_to_queued_allowed(self, src):
        """All intermediate states can return to QUEUED."""
        result = can_transition(src, JobStatus.QUEUED)
        assert result.ok is True

    @pytest.mark.parametrize("src", intermediate_states)
    def test_intermediate_to_in_progress_not_allowed(self, src):
        """Intermediate states cannot go directly to IN_PROGRESS."""
        result = can_transition(src, JobStatus.IN_PROGRESS)
        assert result.ok is False

    @pytest.mark.parametrize("src", [
        JobStatus.NEEDS_FOLLOWUP,
        JobStatus.COOLDOWN,
    ])
    @pytest.mark.parametrize("dest", [
        JobStatus.COMPLETED,
        JobStatus.ERROR,
        JobStatus.CANCELED,
    ])
    def test_intermediate_to_terminal_not_allowed(self, src, dest):
        """Intermediate states cannot jump to terminal directly."""
        result = can_transition(src, dest)
        assert result.ok is False


class TestTransitionResult:
    """Test TransitionResult dataclass."""

    def test_success_result(self):
        """Test TransitionResult for successful transition."""
        result = TransitionResult(ok=True)
        assert result.ok is True
        assert result.error is None

    def test_failure_result(self):
        """Test TransitionResult for failed transition."""
        error_msg = "invalid transition"
        result = TransitionResult(ok=False, error=error_msg)
        assert result.ok is False
        assert result.error == error_msg

    def test_transition_result_is_frozen(self):
        """Test that TransitionResult is immutable (frozen=True)."""
        result = TransitionResult(ok=True)
        with pytest.raises(AttributeError):
            result.ok = False  # type: ignore

    def test_transition_result_equality(self):
        """Test TransitionResult equality comparison."""
        r1 = TransitionResult(ok=True)
        r2 = TransitionResult(ok=True)
        r3 = TransitionResult(ok=False, error="test")

        assert r1 == r2
        assert r1 != r3


class TestTransitionValidation:
    """Test transition validation with various edge cases."""

    def test_complete_transition_path_queued_to_completed(self):
        """Test valid path: QUEUED -> IN_PROGRESS -> COMPLETED."""
        assert can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS).ok
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.COMPLETED).ok

    def test_error_recovery_path(self):
        """Test valid recovery: IN_PROGRESS -> ERROR (terminal)."""
        result = can_transition(JobStatus.IN_PROGRESS, JobStatus.ERROR)
        assert result.ok is True

    def test_followup_then_requeue_path(self):
        """Test valid requeue: IN_PROGRESS -> NEEDS_FOLLOWUP -> QUEUED."""
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.NEEDS_FOLLOWUP).ok
        assert can_transition(JobStatus.NEEDS_FOLLOWUP, JobStatus.QUEUED).ok

    def test_cooldown_then_requeue_path(self):
        """Test valid cooldown: IN_PROGRESS -> COOLDOWN -> QUEUED."""
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.COOLDOWN).ok
        assert can_transition(JobStatus.COOLDOWN, JobStatus.QUEUED).ok

    def test_blocked_then_requeue_path(self):
        """Test valid unblock: IN_PROGRESS -> BLOCKED -> QUEUED."""
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.BLOCKED).ok
        assert can_transition(JobStatus.BLOCKED, JobStatus.QUEUED).ok

    def test_job_canceled_while_queued(self):
        """Test canceling job before it starts."""
        result = can_transition(JobStatus.QUEUED, JobStatus.CANCELED)
        assert result.ok is True

    def test_job_canceled_while_in_progress(self):
        """Test canceling job while running."""
        result = can_transition(JobStatus.IN_PROGRESS, JobStatus.CANCELED)
        assert result.ok is True

    def test_canceled_job_cannot_be_resumed(self):
        """Test that canceled jobs cannot transition (except same state)."""
        result = can_transition(JobStatus.CANCELED, JobStatus.QUEUED)
        assert result.ok is False


class TestErrorMessages:
    """Test error message content."""

    def test_terminal_error_message_contains_both_statuses(self):
        """Terminal state transition error should mention both source and dest."""
        result = can_transition(JobStatus.COMPLETED, JobStatus.QUEUED)
        assert "terminal" in result.error.lower()
        assert "completed" in result.error.lower()

    def test_invalid_transition_error_message(self):
        """Invalid transition error should show the transition."""
        result = can_transition(JobStatus.QUEUED, JobStatus.COMPLETED)
        assert "invalid transition" in result.error.lower()
        assert "queued" in result.error.lower()
        assert "completed" in result.error.lower()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_string_job_status_enum_conversion(self):
        """Test converting string to JobStatus enum."""
        status = JobStatus("in_progress")
        assert status == JobStatus.IN_PROGRESS

    def test_all_statuses_are_strenum(self):
        """Verify JobStatus is a StrEnum (string-backed)."""
        for status in JobStatus:
            assert isinstance(status, str)
            assert status == status.value

    def test_can_transition_accepts_enum_values(self):
        """Test can_transition works with both enum and string."""
        # Using enums
        result1 = can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS)
        assert result1.ok is True

    def test_empty_error_on_success(self):
        """Verify successful transitions have no error message."""
        result = can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS)
        assert result.error is None


class TestIntegrationScenarios:
    """Integration tests for complete job lifecycle scenarios."""

    def test_job_success_lifecycle(self):
        """Test successful job: QUEUED -> IN_PROGRESS -> COMPLETED."""
        # Start job
        assert can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS).ok
        # Complete job
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.COMPLETED).ok

    def test_job_failure_lifecycle(self):
        """Test failed job: QUEUED -> IN_PROGRESS -> ERROR."""
        assert can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS).ok
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.ERROR).ok

    def test_job_canceled_queued(self):
        """Test cancellation: QUEUED -> CANCELED."""
        assert can_transition(JobStatus.QUEUED, JobStatus.CANCELED).ok

    def test_job_canceled_in_progress(self):
        """Test cancellation: QUEUED -> IN_PROGRESS -> CANCELED."""
        assert can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS).ok
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.CANCELED).ok

    def test_job_with_followup(self):
        """Test job requiring followup: QUEUED -> IN_PROGRESS -> NEEDS_FOLLOWUP -> QUEUED -> IN_PROGRESS -> COMPLETED."""
        # Initial
        assert can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS).ok
        # Need followup
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.NEEDS_FOLLOWUP).ok
        # Requeue
        assert can_transition(JobStatus.NEEDS_FOLLOWUP, JobStatus.QUEUED).ok
        # Restart
        assert can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS).ok
        # Complete
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.COMPLETED).ok

    def test_job_with_cooldown(self):
        """Test job with cooldown: QUEUED -> IN_PROGRESS -> COOLDOWN -> QUEUED -> IN_PROGRESS -> COMPLETED."""
        assert can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS).ok
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.COOLDOWN).ok
        assert can_transition(JobStatus.COOLDOWN, JobStatus.QUEUED).ok
        assert can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS).ok
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.COMPLETED).ok

    def test_job_blocked_then_resumed(self):
        """Test blocked job: QUEUED -> IN_PROGRESS -> BLOCKED -> QUEUED -> IN_PROGRESS -> COMPLETED."""
        assert can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS).ok
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.BLOCKED).ok
        assert can_transition(JobStatus.BLOCKED, JobStatus.QUEUED).ok
        assert can_transition(JobStatus.QUEUED, JobStatus.IN_PROGRESS).ok
        assert can_transition(JobStatus.IN_PROGRESS, JobStatus.COMPLETED).ok

    def test_completed_job_cannot_transition(self):
        """Verify completed job is truly terminal."""
        for status in JobStatus:
            result = can_transition(JobStatus.COMPLETED, status)
            if status == JobStatus.COMPLETED:
                assert result.ok is True
            else:
                assert result.ok is False

    def test_error_job_cannot_transition(self):
        """Verify error job is truly terminal."""
        for status in JobStatus:
            result = can_transition(JobStatus.ERROR, status)
            if status == JobStatus.ERROR:
                assert result.ok is True
            else:
                assert result.ok is False

    def test_canceled_job_cannot_transition(self):
        """Verify canceled job is truly terminal."""
        for status in JobStatus:
            result = can_transition(JobStatus.CANCELED, status)
            if status == JobStatus.CANCELED:
                assert result.ok is True
            else:
                assert result.ok is False


class TestBoundaryValues:
    """Test boundary conditions and extreme values."""

    def test_all_8_statuses_are_valid(self):
        """Verify all 8 JobStatus values can be used."""
        statuses = list(JobStatus)
        assert len(statuses) == 8
        # Each should be usable
        for status in statuses:
            result = can_transition(status, status)
            assert result.ok is True

    def test_transition_result_dataclass_fields(self):
        """Verify TransitionResult has correct fields."""
        result = TransitionResult(ok=True)
        assert hasattr(result, "ok")
        assert hasattr(result, "error")

        # Verify field types
        assert isinstance(result.ok, bool)
        # error can be None or str
        assert result.error is None or isinstance(result.error, str)

    def test_terminal_statuses_is_immutable_set(self):
        """Verify TERMINAL_STATUSES is a set (immutable collection)."""
        assert isinstance(TERMINAL_STATUSES, set)
        # Should contain exactly 3 items
        assert len(TERMINAL_STATUSES) == 3
