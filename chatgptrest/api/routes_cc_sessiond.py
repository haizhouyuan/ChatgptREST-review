from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import os

from ..kernel.cc_sessiond import CCSessionClient, PromptPackagingError, SessionState


_client_module: Optional[CCSessionClient] = None


def get_cc_sessiond_client() -> Optional[CCSessionClient]:
    global _client_module
    if _client_module is None:
        db_path = Path(os.environ.get("CC_SESSIOND_DB", "/tmp/cc-sessions.db"))
        _client_module = CCSessionClient(
            db_path=db_path,
            minimax_api_key=os.environ.get("MINIMAX_API_KEY"),
            max_concurrent=int(os.environ.get("CC_SESSIOND_MAX_CONCURRENT", "3")),
            budget_per_hour=float(os.environ.get("CC_SESSIOND_BUDGET_HOURLY", "10.0")),
            budget_total=float(os.environ.get("CC_SESSIOND_BUDGET_TOTAL", "100.0")),
        )
    return _client_module


def make_cc_sessiond_router() -> APIRouter:
    router = APIRouter(prefix="/v1/cc-sessions", tags=["cc-sessions"])

    def get_client() -> CCSessionClient:
        return get_cc_sessiond_client()

    class CreateSessionRequest(BaseModel):
        prompt: str
        options: Optional[dict] = None
        priority: Optional[int] = 0

    class ContinueSessionRequest(BaseModel):
        prompt: str

    @router.post("")
    async def create_session(request: CreateSessionRequest):
        """Create a new cc-session."""
        client = get_client()
        try:
            session_id = await client.create_session(
                prompt=request.prompt,
                options=request.options,
                priority=request.priority or 0,
            )
        except PromptPackagingError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"session_id": session_id, "state": "pending"}

    @router.get("/{session_id}")
    async def get_session(session_id: str):
        """Get session status."""
        client = get_client()
        record = client.get_session(session_id)
        if not record:
            raise HTTPException(404, "Session not found")
        return client.get_status(session_id)

    @router.post("/{session_id}/continue")
    async def continue_session(session_id: str, request: ContinueSessionRequest):
        """Continue an existing session."""
        client = get_client()
        record = client.get_session(session_id)
        if not record:
            raise HTTPException(404, "Session not found")

        try:
            new_session_id = await client.create_session(
                prompt=request.prompt,
                options={"continue_from": session_id},
                parent_session_id=session_id,
                continue_mode="resume_same_session",
            )
        except PromptPackagingError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"session_id": new_session_id, "state": "pending"}

    @router.post("/{session_id}/cancel")
    async def cancel_session(session_id: str):
        """Cancel a session."""
        client = get_client()
        success = await client.cancel(session_id)
        if not success:
            raise HTTPException(404, "Session not found or already completed")
        return {"session_id": session_id, "state": "cancelled"}

    @router.get("/{session_id}/events")
    async def get_session_events(
        session_id: str,
        after_id: int = 0,
        limit: int = 100,
    ):
        """Get session events."""
        client = get_client()
        record = client.get_session(session_id)
        if not record:
            raise HTTPException(404, "Session not found")
        
        events = client.get_events(session_id, after_id, limit)
        return {"session_id": session_id, "events": events}

    @router.get("/{session_id}/result")
    async def get_session_result(session_id: str):
        """Get session result."""
        client = get_client()
        record = client.get_session(session_id)
        if not record:
            raise HTTPException(404, "Session not found")
        
        if record.result:
            return {"session_id": session_id, "result": record.result}
        if record.error:
            return {"session_id": session_id, "error": record.error}
        
        return {"session_id": session_id, "state": record.state.value}

    @router.get("/{session_id}/wait")
    async def wait_session(
        session_id: str,
        timeout: Optional[float] = 300,
    ):
        """Wait for session to complete."""
        client = get_client()
        try:
            result = await client.wait(session_id, timeout=timeout)
            return {"session_id": session_id, "state": "completed", "result": result}
        except TimeoutError as e:
            raise HTTPException(408, str(e))
        except RuntimeError as e:
            raise HTTPException(400, str(e))

    @router.get("")
    async def list_sessions(
        state: Optional[str] = None,
        limit: int = 100,
    ):
        """List sessions."""
        client = get_client()
        state_enum = SessionState(state) if state else None
        sessions = client.list_sessions(state_enum, limit)
        return {"sessions": sessions}

    @router.get("/scheduler/status")
    async def get_scheduler_status():
        """Get scheduler status."""
        client = get_client()
        return client.get_scheduler_status()

    return router
