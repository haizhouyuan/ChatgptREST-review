"""Task Watchdog - Timeout and dead-letter detection.

This module monitors task execution and handles timeouts, stuck tasks,
and dead-letter scenarios.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from chatgptrest.task_runtime.task_state_machine import TaskStateMachine, get_stuck_tasks
from chatgptrest.task_runtime.task_store import TaskStatus, task_db_conn


@dataclass
class WatchdogPolicy:
    """Watchdog policy for a task."""
    heartbeat_interval_seconds: int
    timeout_seconds: int
    max_silence_seconds: int
    auto_recover: bool


class TaskWatchdog:
    """Monitors task execution health."""

    def __init__(self, task_id: str, db_path: Path | None = None):
        self.task_id = task_id
        self.db_path = db_path

    def register(self, policy: WatchdogPolicy) -> bool:
        """Register task with watchdog."""
        import json

        with task_db_conn(self.db_path) as conn:
            now = time.time()
            timeout_at = now + policy.timeout_seconds

            conn.execute("""
                INSERT OR REPLACE INTO task_watchdog (
                    task_id, last_heartbeat_at, timeout_at, watchdog_policy_json
                ) VALUES (?, ?, ?, ?)
            """, (
                self.task_id,
                now,
                timeout_at,
                json.dumps({
                    "heartbeat_interval_seconds": policy.heartbeat_interval_seconds,
                    "timeout_seconds": policy.timeout_seconds,
                    "max_silence_seconds": policy.max_silence_seconds,
                    "auto_recover": policy.auto_recover,
                })
            ))

            conn.commit()
            return True

    def heartbeat(self) -> bool:
        """Record a heartbeat."""
        with task_db_conn(self.db_path) as conn:
            now = time.time()

            conn.execute("""
                UPDATE task_watchdog
                SET last_heartbeat_at = ?
                WHERE task_id = ?
            """, (now, self.task_id))

            success = conn.total_changes > 0
            conn.commit()
            return success

    def extend_timeout(self, additional_seconds: int) -> bool:
        """Extend timeout for long-running tasks."""
        with task_db_conn(self.db_path) as conn:
            conn.execute("""
                UPDATE task_watchdog
                SET timeout_at = timeout_at + ?
                WHERE task_id = ?
            """, (additional_seconds, self.task_id))

            success = conn.total_changes > 0
            conn.commit()
            return success

    def unregister(self) -> bool:
        """Unregister task from watchdog."""
        with task_db_conn(self.db_path) as conn:
            conn.execute("""
                DELETE FROM task_watchdog WHERE task_id = ?
            """, (self.task_id,))

            success = conn.total_changes > 0
            conn.commit()
            return success


def scan_for_timeouts() -> list[str]:
    """Scan for tasks that have exceeded their timeout."""
    with task_db_conn() as conn:
        now = time.time()

        rows = conn.execute("""
            SELECT task_id FROM task_watchdog
            WHERE timeout_at > 0 AND timeout_at < ?
        """, (now,)).fetchall()

        return [row["task_id"] for row in rows]


def scan_for_silent_tasks(max_silence_seconds: int = 3600) -> list[str]:
    """Scan for tasks with no recent heartbeat."""
    with task_db_conn() as conn:
        now = time.time()
        cutoff = now - max_silence_seconds

        rows = conn.execute("""
            SELECT task_id FROM task_watchdog
            WHERE last_heartbeat_at < ?
        """, (cutoff,)).fetchall()

        return [row["task_id"] for row in rows]


def handle_timeout(task_id: str, *, auto_recover: bool = False) -> bool:
    """Handle a timed-out task."""
    state_machine = TaskStateMachine(task_id)

    if auto_recover:
        # Attempt automatic recovery
        state_machine.suspend(
            reason="Timeout - attempting auto-recovery",
            awaiting_signal="operator_review"
        )
        return True
    else:
        # Transition to FAILED
        result = state_machine.transition(
            to_status=TaskStatus.FAILED,
            trigger="watchdog_timeout",
            metadata={"reason": "Task exceeded timeout"}
        )
        return result.success


def handle_stuck_task(task_id: str) -> bool:
    """Handle a stuck task (no progress)."""
    state_machine = TaskStateMachine(task_id)

    state_machine.suspend(
        reason="Task appears stuck - no progress detected",
        awaiting_signal="operator_review"
    )

    return True


def run_watchdog_sweep() -> dict[str, Any]:
    """Run a full watchdog sweep.

    Returns:
        Summary of actions taken
    """
    summary = {
        "timed_out": [],
        "silent": [],
        "stuck": [],
        "recovered": [],
        "failed": [],
    }

    # Check for timeouts
    timed_out = scan_for_timeouts()
    for task_id in timed_out:
        if handle_timeout(task_id, auto_recover=False):
            summary["timed_out"].append(task_id)
            summary["failed"].append(task_id)

    # Check for silent tasks
    silent = scan_for_silent_tasks(max_silence_seconds=3600)
    for task_id in silent:
        if handle_stuck_task(task_id):
            summary["silent"].append(task_id)

    # Check for stuck tasks (no checkpoint progress)
    stuck = get_stuck_tasks(timeout_seconds=3600)
    for task_id in stuck:
        if handle_stuck_task(task_id):
            summary["stuck"].append(task_id)

    return summary
