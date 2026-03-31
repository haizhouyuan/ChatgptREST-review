from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Any
from dataclasses import dataclass


@dataclass
class BackendResult:
    ok: bool
    session_id: str
    backend: str
    backend_run_id: Optional[str]
    state: str
    output_text: Optional[str] = None
    structured_output: Optional[dict] = None
    quality_score: Optional[float] = None
    cost_usd: Optional[float] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class SessionBackend(ABC):
    """Base protocol for session execution backends."""

    backend_name: str

    @abstractmethod
    async def create_run(
        self,
        session_id: str,
        prompt: str,
        options: dict,
    ) -> AsyncIterator[Any]:
        """Create and run a new session. Yields events."""
        pass

    @abstractmethod
    async def continue_run(
        self,
        session_id: str,
        backend_run_id: str,
        prompt: str,
        options: dict,
    ) -> AsyncIterator[Any]:
        """Continue an existing session."""
        pass

    @abstractmethod
    async def cancel_run(
        self,
        session_id: str,
        backend_run_id: str,
    ) -> bool:
        """Cancel a running session."""
        pass

    @abstractmethod
    async def poll_run(
        self,
        session_id: str,
        backend_run_id: str,
    ) -> BackendResult:
        """Poll for session status."""
        pass

    @abstractmethod
    async def result_from_run(
        self,
        session_id: str,
        backend_run_id: str,
    ) -> BackendResult:
        """Get final result from a session."""
        pass
