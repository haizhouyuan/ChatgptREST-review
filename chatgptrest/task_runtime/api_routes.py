"""Task Runtime API Routes.

This module provides REST API endpoints for the Task Harness Runtime.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from chatgptrest.advisor.task_intake import TaskIntakeSpec
from chatgptrest.task_runtime.chunk_contracts import ChunkContractManager
from chatgptrest.task_runtime.delivery_integration import DeliveryPublisher
from chatgptrest.task_runtime.memory_distillation import MemoryDistiller, complete_task
from chatgptrest.task_runtime.promotion_service import PromotionService
from chatgptrest.task_runtime.task_initializer import TaskInitializer, freeze_task_context
from chatgptrest.task_runtime.task_state_machine import TaskStateMachine
from chatgptrest.task_runtime.task_store import (
    TaskStatus,
    create_attempt,
    get_task,
    task_db_conn,
)
from chatgptrest.task_runtime.task_watchdog import TaskWatchdog, WatchdogPolicy

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    """Request to create a new task."""
    intake_spec: dict[str, Any]
    context_snapshot: dict[str, Any] | None = None


class CreateTaskResponse(BaseModel):
    """Response from task creation."""
    task_id: str
    status: str
    workspace_path: str | None


class TaskStatusResponse(BaseModel):
    """Task status response."""
    task_id: str
    status: str
    current_attempt_id: str | None
    current_chunk_id: str | None
    created_at: float
    updated_at: float


class ResumeTaskRequest(BaseModel):
    """Request to resume a suspended task."""
    reason: str | None = None


class SignalRequest(BaseModel):
    """External signal for a task."""
    signal_type: str
    payload: dict[str, Any]


class OperatorDecisionRequest(BaseModel):
    """Operator decision request."""
    chunk_id: str | None = None
    decision: str  # "approve", "reject", "rollback"
    rationale: str
    rollback_target: str | None = None


@router.post("", response_model=CreateTaskResponse)
async def create_task(request: CreateTaskRequest) -> CreateTaskResponse:
    """Create a new task from intake spec."""
    try:
        # Parse intake spec
        intake_spec = TaskIntakeSpec(**request.intake_spec)

        # Initialize task
        initializer = TaskInitializer()
        frozen_context = initializer.initialize_task(
            intake_spec=intake_spec,
            context_snapshot=request.context_snapshot,
        )

        # Freeze context
        freeze_task_context(frozen_context.task_id)

        # Get task record
        with task_db_conn() as conn:
            task = get_task(conn, task_id=frozen_context.task_id)

        return CreateTaskResponse(
            task_id=task.task_id,
            status=task.status.value,
            workspace_path=task.workspace_path,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """Get task status."""
    try:
        with task_db_conn() as conn:
            task = get_task(conn, task_id=task_id)

        return TaskStatusResponse(
            task_id=task.task_id,
            status=task.status.value,
            current_attempt_id=task.current_attempt_id,
            current_chunk_id=task.current_chunk_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/resume")
async def resume_task(task_id: str, request: ResumeTaskRequest) -> dict[str, Any]:
    """Resume a suspended task."""
    try:
        state_machine = TaskStateMachine(task_id)

        if not state_machine.resume():
            raise HTTPException(status_code=400, detail="Failed to resume task")

        return {"task_id": task_id, "status": "resumed"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/signals")
async def inject_signal(task_id: str, request: SignalRequest) -> dict[str, Any]:
    """Inject an external signal."""
    try:
        state_machine = TaskStateMachine(task_id)

        signal_id = state_machine.inject_signal(
            signal_type=request.signal_type,
            payload=request.payload,
        )

        return {
            "task_id": task_id,
            "signal_id": signal_id,
            "signal_type": request.signal_type,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/operator/approve")
async def operator_approve(task_id: str, request: OperatorDecisionRequest) -> dict[str, Any]:
    """Operator approval."""
    try:
        if request.chunk_id:
            # Approve specific chunk
            promotion_service = PromotionService(task_id)
            decision = promotion_service.make_promotion_decision(
                request.chunk_id,
                decision="promote",
                source="operator",
                reviewer_identity="operator",
                rationale=request.rationale,
            )

            return {
                "task_id": task_id,
                "chunk_id": request.chunk_id,
                "decision_id": decision.decision_id,
                "decision": "approved",
            }
        else:
            # Approve task to proceed
            state_machine = TaskStateMachine(task_id)
            result = state_machine.transition(
                to_status=TaskStatus.EXECUTING,
                trigger="operator_approval",
                metadata={"rationale": request.rationale},
            )

            if not result.success:
                raise HTTPException(status_code=400, detail=result.error)

            return {
                "task_id": task_id,
                "decision": "approved",
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/operator/reject")
async def operator_reject(task_id: str, request: OperatorDecisionRequest) -> dict[str, Any]:
    """Operator rejection."""
    try:
        if request.chunk_id:
            # Reject specific chunk
            promotion_service = PromotionService(task_id)
            decision = promotion_service.make_promotion_decision(
                request.chunk_id,
                decision="reject",
                source="operator",
                reviewer_identity="operator",
                rationale=request.rationale,
            )

            return {
                "task_id": task_id,
                "chunk_id": request.chunk_id,
                "decision_id": decision.decision_id,
                "decision": "rejected",
            }
        else:
            # Reject task
            state_machine = TaskStateMachine(task_id)
            result = state_machine.transition(
                to_status=TaskStatus.FAILED,
                trigger="operator_rejection",
                metadata={"rationale": request.rationale},
            )

            if not result.success:
                raise HTTPException(status_code=400, detail=result.error)

            return {
                "task_id": task_id,
                "decision": "rejected",
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/operator/rollback")
async def operator_rollback(task_id: str, request: OperatorDecisionRequest) -> dict[str, Any]:
    """Operator rollback."""
    try:
        if not request.chunk_id:
            raise HTTPException(status_code=400, detail="chunk_id required for rollback")

        promotion_service = PromotionService(task_id)
        decision = promotion_service.make_promotion_decision(
            request.chunk_id,
            decision="rollback",
            source="operator",
            reviewer_identity="operator",
            rationale=request.rationale,
            rollback_target=request.rollback_target,
        )

        return {
            "task_id": task_id,
            "chunk_id": request.chunk_id,
            "decision_id": decision.decision_id,
            "decision": "rollback",
            "rollback_target": request.rollback_target,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
