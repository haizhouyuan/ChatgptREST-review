"""Chunk Contracts - Contract-bounded execution units.

This module implements Phase 2: Chunk Contract Execution.
Generators can only work within chunk contracts, not freely push entire tasks.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from chatgptrest.task_runtime.task_store import (
    ChunkContract,
    ChunkStatus,
    create_chunk,
    get_chunk,
    task_db_conn,
)
from chatgptrest.task_runtime.task_workspace import TaskWorkspace


@dataclass
class ChunkExecutionContext:
    """Execution context for a chunk."""
    chunk_id: str
    task_id: str
    attempt_id: str
    objective: str
    inputs: dict[str, Any]
    constraints: dict[str, Any]
    done_definition: str
    artifact_contract: dict[str, Any]
    executor_profile: str
    timeout_seconds: int


class ChunkContractManager:
    """Manages chunk contract lifecycle."""

    def __init__(self, task_id: str, db_path: Path | None = None):
        self.task_id = task_id
        self.db_path = db_path
        self.workspace = TaskWorkspace(task_id)

    def create_chunk_contract(
        self,
        *,
        attempt_id: str,
        objective: str,
        inputs: dict[str, Any],
        constraints: dict[str, Any],
        done_definition: str,
        grader_requirements: dict[str, Any],
        artifact_contract: dict[str, Any],
        executor_profile: str = "default",
        timeout_seconds: int = 3600,
    ) -> ChunkContract:
        """Create a new chunk contract."""
        with task_db_conn(self.db_path) as conn:
            chunk = create_chunk(
                conn,
                task_id=self.task_id,
                attempt_id=attempt_id,
                objective=objective,
                inputs=inputs,
                constraints=constraints,
                done_definition=done_definition,
                grader_requirements=grader_requirements,
                artifact_contract=artifact_contract,
                executor_profile=executor_profile,
                timeout_policy={"timeout_seconds": timeout_seconds},
            )

        # Write contract to workspace
        contract_data = {
            "chunk_id": chunk.chunk_id,
            "chunk_no": chunk.chunk_no,
            "objective": objective,
            "inputs": inputs,
            "constraints": constraints,
            "done_definition": done_definition,
            "grader_requirements": grader_requirements,
            "artifact_contract": artifact_contract,
            "executor_profile": executor_profile,
            "timeout_seconds": timeout_seconds,
            "created_at": chunk.created_at,
        }

        self.workspace.write_chunk_contract(chunk.chunk_id, contract_data)

        # Log progress
        self.workspace.append_progress_ledger({
            "event": "chunk_created",
            "chunk_id": chunk.chunk_id,
            "chunk_no": chunk.chunk_no,
            "objective": objective,
            "ts": time.time(),
        })

        return chunk

    def get_execution_context(self, chunk_id: str) -> ChunkExecutionContext:
        """Get execution context for a chunk."""
        with task_db_conn(self.db_path) as conn:
            chunk = get_chunk(conn, chunk_id=chunk_id)

        inputs = json.loads(chunk.inputs_json)
        constraints = json.loads(chunk.constraints_json)
        artifact_contract = json.loads(chunk.artifact_contract_json)
        timeout_policy = json.loads(chunk.timeout_policy_json)

        return ChunkExecutionContext(
            chunk_id=chunk.chunk_id,
            task_id=chunk.task_id,
            attempt_id=chunk.attempt_id,
            objective=chunk.objective,
            inputs=inputs,
            constraints=constraints,
            done_definition=chunk.done_definition,
            artifact_contract=artifact_contract,
            executor_profile=chunk.executor_profile,
            timeout_seconds=timeout_policy.get("timeout_seconds", 3600),
        )

    def start_chunk_execution(self, chunk_id: str) -> bool:
        """Mark chunk as executing."""
        with task_db_conn(self.db_path) as conn:
            now = time.time()

            conn.execute("""
                UPDATE task_chunks
                SET status = ?, updated_at = ?
                WHERE chunk_id = ? AND status = ?
            """, (ChunkStatus.EXECUTING.value, now, chunk_id, ChunkStatus.PENDING.value))

            success = conn.total_changes > 0
            conn.commit()

            if success:
                self.workspace.append_progress_ledger({
                    "event": "chunk_started",
                    "chunk_id": chunk_id,
                    "ts": now,
                })

            return success

    def complete_chunk_execution(
        self,
        chunk_id: str,
        *,
        artifacts: list[str],
        summary: str,
    ) -> bool:
        """Mark chunk as completed (awaiting evaluation)."""
        with task_db_conn(self.db_path) as conn:
            now = time.time()

            conn.execute("""
                UPDATE task_chunks
                SET status = ?, updated_at = ?
                WHERE chunk_id = ? AND status = ?
            """, (ChunkStatus.COMPLETED.value, now, chunk_id, ChunkStatus.EXECUTING.value))

            success = conn.total_changes > 0
            conn.commit()

            if success:
                self.workspace.append_progress_ledger({
                    "event": "chunk_completed",
                    "chunk_id": chunk_id,
                    "artifacts": artifacts,
                    "summary": summary,
                    "ts": now,
                })

            return success

    def fail_chunk_execution(
        self,
        chunk_id: str,
        *,
        error: str,
    ) -> bool:
        """Mark chunk as failed."""
        with task_db_conn(self.db_path) as conn:
            now = time.time()

            conn.execute("""
                UPDATE task_chunks
                SET status = ?, updated_at = ?
                WHERE chunk_id = ?
            """, (ChunkStatus.FAILED.value, now, chunk_id))

            success = conn.total_changes > 0
            conn.commit()

            if success:
                self.workspace.append_progress_ledger({
                    "event": "chunk_failed",
                    "chunk_id": chunk_id,
                    "error": error,
                    "ts": now,
                })

            return success

    def list_chunks_for_attempt(self, attempt_id: str) -> list[ChunkContract]:
        """List all chunks for an attempt."""
        with task_db_conn(self.db_path) as conn:
            rows = conn.execute("""
                SELECT * FROM task_chunks
                WHERE attempt_id = ?
                ORDER BY chunk_no ASC
            """, (attempt_id,)).fetchall()

            return [
                ChunkContract(
                    chunk_id=row["chunk_id"],
                    task_id=row["task_id"],
                    attempt_id=row["attempt_id"],
                    chunk_no=row["chunk_no"],
                    objective=row["objective"],
                    inputs_json=row["inputs_json"],
                    constraints_json=row["constraints_json"],
                    done_definition=row["done_definition"],
                    grader_requirements_json=row["grader_requirements_json"],
                    artifact_contract_json=row["artifact_contract_json"],
                    executor_profile=row["executor_profile"],
                    timeout_policy_json=row["timeout_policy_json"],
                    status=ChunkStatus(row["status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def get_pending_chunks(self, attempt_id: str) -> list[ChunkContract]:
        """Get pending chunks for an attempt."""
        with task_db_conn(self.db_path) as conn:
            rows = conn.execute("""
                SELECT * FROM task_chunks
                WHERE attempt_id = ? AND status = ?
                ORDER BY chunk_no ASC
            """, (attempt_id, ChunkStatus.PENDING.value)).fetchall()

            return [
                ChunkContract(
                    chunk_id=row["chunk_id"],
                    task_id=row["task_id"],
                    attempt_id=row["attempt_id"],
                    chunk_no=row["chunk_no"],
                    objective=row["objective"],
                    inputs_json=row["inputs_json"],
                    constraints_json=row["constraints_json"],
                    done_definition=row["done_definition"],
                    grader_requirements_json=row["grader_requirements_json"],
                    artifact_contract_json=row["artifact_contract_json"],
                    executor_profile=row["executor_profile"],
                    timeout_policy_json=row["timeout_policy_json"],
                    status=ChunkStatus(row["status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]


def validate_chunk_artifacts(
    chunk_id: str,
    *,
    artifact_contract: dict[str, Any],
    actual_artifacts: list[str],
) -> tuple[bool, list[str]]:
    """Validate that chunk artifacts match contract.

    Returns:
        (is_valid, missing_artifacts)
    """
    required = artifact_contract.get("required", [])
    missing = []

    for req in required:
        if req not in actual_artifacts:
            missing.append(req)

    return len(missing) == 0, missing
