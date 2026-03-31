"""Task State Machine - Enforces valid state transitions and concurrency control.

This module implements the task lifecycle state machine with proper transition validation,
optimistic locking, and checkpoint/resume support.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Literal

from chatgptrest.task_runtime.task_store import TaskStatus, task_db_conn, update_task_status


# Valid state transitions
_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.INITIALIZED, TaskStatus.FAILED, TaskStatus.CANCELED},
    TaskStatus.INITIALIZED: {TaskStatus.FROZEN, TaskStatus.FAILED, TaskStatus.CANCELED},
    TaskStatus.FROZEN: {TaskStatus.PLANNED, TaskStatus.FAILED, TaskStatus.CANCELED},
    TaskStatus.PLANNED: {TaskStatus.EXECUTING, TaskStatus.FAILED, TaskStatus.CANCELED},
    TaskStatus.EXECUTING: {
        TaskStatus.AWAITING_EVALUATION,
        TaskStatus.AWAITING_OPERATOR,
        TaskStatus.FAILED,
        TaskStatus.CANCELED,
    },
    TaskStatus.AWAITING_EVALUATION: {
        TaskStatus.EXECUTING,  # Retry after evaluation
        TaskStatus.AWAITING_OPERATOR,
        TaskStatus.PROMOTED,
        TaskStatus.FAILED,
        TaskStatus.CANCELED,
    },
    TaskStatus.AWAITING_OPERATOR: {
        TaskStatus.EXECUTING,  # Operator approved retry
        TaskStatus.PROMOTED,
        TaskStatus.FAILED,
        TaskStatus.CANCELED,
    },
    TaskStatus.PROMOTED: {TaskStatus.PUBLISHED, TaskStatus.FAILED},
    TaskStatus.PUBLISHED: {TaskStatus.DISTILLED, TaskStatus.FAILED},
    TaskStatus.DISTILLED: {TaskStatus.COMPLETED},
    TaskStatus.COMPLETED: set(),  # Terminal
    TaskStatus.FAILED: set(),  # Terminal
    TaskStatus.CANCELED: set(),  # Terminal
}


def can_transition(from_status: TaskStatus, to_status: TaskStatus) -> bool:
    """Check if a state transition is valid."""
    return to_status in _TRANSITIONS.get(from_status, set())


def is_terminal(status: TaskStatus) -> bool:
    """Check if a status is terminal."""
    return status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED}


@dataclass
class StateTransitionResult:
    """Result of a state transition attempt."""
    success: bool
    error: str | None = None
    new_version: int | None = None


class TaskStateMachine:
    """Task state machine with concurrency control."""

    def __init__(self, task_id: str, db_path: Path | None = None):
        self.task_id = task_id
        self.db_path = db_path

    def transition(
        self,
        *,
        to_status: TaskStatus,
        trigger: str,
        metadata: dict[str, Any] | None = None,
        expected_version: int | None = None,
    ) -> StateTransitionResult:
        """Attempt a state transition with optimistic locking."""
        with task_db_conn(self.db_path) as conn:
            # Get current state
            row = conn.execute("""
                SELECT status, state_version FROM task_state WHERE task_id = ?
            """, (self.task_id,)).fetchone()

            if row is None:
                return StateTransitionResult(
                    success=False,
                    error=f"Task not found: {self.task_id}"
                )

            current_status = TaskStatus(row["status"])
            current_version = row["state_version"]

            # Check version if provided (optimistic lock)
            if expected_version is not None and current_version != expected_version:
                return StateTransitionResult(
                    success=False,
                    error=f"Version mismatch: expected {expected_version}, got {current_version}"
                )

            # Validate transition
            if not can_transition(current_status, to_status):
                return StateTransitionResult(
                    success=False,
                    error=f"Invalid transition: {current_status.value} -> {to_status.value}"
                )

            # Perform transition
            try:
                update_task_status(
                    conn,
                    task_id=self.task_id,
                    new_status=to_status,
                    trigger=trigger,
                    metadata=metadata,
                )

                # Get new version
                row = conn.execute("""
                    SELECT state_version FROM task_state WHERE task_id = ?
                """, (self.task_id,)).fetchone()

                return StateTransitionResult(
                    success=True,
                    new_version=row["state_version"]
                )
            except Exception as e:
                return StateTransitionResult(
                    success=False,
                    error=str(e)
                )

    def checkpoint(self, *, phase: str, state_data: dict[str, Any]) -> bool:
        """Create a checkpoint for recovery."""
        with task_db_conn(self.db_path) as conn:
            now = time.time()

            conn.execute("""
                UPDATE task_state
                SET phase = ?, state_data_json = ?, last_checkpoint_at = ?,
                    state_version = state_version + 1
                WHERE task_id = ?
            """, (phase, json.dumps(state_data), now, self.task_id))

            conn.commit()
            return True

    def suspend(self, *, reason: str, awaiting_signal: str | None = None) -> bool:
        """Suspend task execution."""
        with task_db_conn(self.db_path) as conn:
            now = time.time()

            conn.execute("""
                UPDATE task_state
                SET blocked_reason = ?, awaiting_signal = ?, last_checkpoint_at = ?
                WHERE task_id = ?
            """, (reason, awaiting_signal, now, self.task_id))

            conn.commit()
            return True

    def resume(self) -> bool:
        """Resume suspended task."""
        with task_db_conn(self.db_path) as conn:
            conn.execute("""
                UPDATE task_state
                SET blocked_reason = NULL, awaiting_signal = NULL,
                    recovery_epoch = recovery_epoch + 1
                WHERE task_id = ?
            """, (self.task_id,))

            conn.commit()
            return True

    def acquire_lock(self, *, owner: str, timeout_seconds: int = 300) -> bool:
        """Acquire exclusive lock for task execution."""
        with task_db_conn(self.db_path) as conn:
            now = time.time()
            expires_at = now + timeout_seconds

            # Check if already locked
            row = conn.execute("""
                SELECT active_lock_owner FROM task_state WHERE task_id = ?
            """, (self.task_id,)).fetchone()

            if row and row["active_lock_owner"]:
                return False

            # Acquire lock
            conn.execute("""
                UPDATE task_state
                SET active_lock_owner = ?
                WHERE task_id = ? AND active_lock_owner IS NULL
            """, (owner, self.task_id))

            if conn.total_changes == 0:
                return False

            conn.commit()
            return True

    def release_lock(self, *, owner: str) -> bool:
        """Release execution lock."""
        with task_db_conn(self.db_path) as conn:
            conn.execute("""
                UPDATE task_state
                SET active_lock_owner = NULL
                WHERE task_id = ? AND active_lock_owner = ?
            """, (self.task_id, owner))

            success = conn.total_changes > 0
            conn.commit()
            return success

    def inject_signal(
        self,
        *,
        signal_type: str,
        payload: dict[str, Any],
    ) -> str:
        """Inject an external signal for the task."""
        import uuid

        signal_id = str(uuid.uuid4())

        with task_db_conn(self.db_path) as conn:
            now = time.time()

            conn.execute("""
                INSERT INTO task_external_signals (
                    signal_id, task_id, signal_type, payload_json, received_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (signal_id, self.task_id, signal_type, json.dumps(payload), now))

            conn.commit()

        return signal_id

    def get_pending_signals(self) -> list[dict[str, Any]]:
        """Get unprocessed signals for this task."""
        with task_db_conn(self.db_path) as conn:
            rows = conn.execute("""
                SELECT signal_id, signal_type, payload_json, received_at
                FROM task_external_signals
                WHERE task_id = ? AND processed_at IS NULL
                ORDER BY received_at ASC
            """, (self.task_id,)).fetchall()

            return [
                {
                    "signal_id": row["signal_id"],
                    "signal_type": row["signal_type"],
                    "payload": json.loads(row["payload_json"]),
                    "received_at": row["received_at"],
                }
                for row in rows
            ]

    def mark_signal_processed(self, *, signal_id: str) -> bool:
        """Mark a signal as processed."""
        with task_db_conn(self.db_path) as conn:
            now = time.time()

            conn.execute("""
                UPDATE task_external_signals
                SET processed_at = ?
                WHERE signal_id = ?
            """, (now, signal_id))

            success = conn.total_changes > 0
            conn.commit()
            return success


def get_stuck_tasks(*, timeout_seconds: int = 3600) -> list[str]:
    """Find tasks that may be stuck (no checkpoint for timeout period)."""
    with task_db_conn() as conn:
        now = time.time()
        cutoff = now - timeout_seconds

        rows = conn.execute("""
            SELECT task_id FROM task_state
            WHERE status IN (?, ?, ?)
            AND last_checkpoint_at < ?
        """, (
            TaskStatus.EXECUTING.value,
            TaskStatus.AWAITING_EVALUATION.value,
            TaskStatus.AWAITING_OPERATOR.value,
            cutoff
        )).fetchall()

        return [row["task_id"] for row in rows]


def force_unlock_task(*, task_id: str, reason: str) -> bool:
    """Force unlock a stuck task (operator intervention)."""
    with task_db_conn() as conn:
        conn.execute("""
            UPDATE task_state
            SET active_lock_owner = NULL,
                blocked_reason = ?,
                recovery_epoch = recovery_epoch + 1
            WHERE task_id = ?
        """, (f"Force unlocked: {reason}", task_id))

        success = conn.total_changes > 0
        conn.commit()
        return success
