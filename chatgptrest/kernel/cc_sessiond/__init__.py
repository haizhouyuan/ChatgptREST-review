"""
CC-Sessiond: Claude Code Session Daemon

A durable session manager built on Claude Agent SDK with:
- Session persistence (SQLite)
- Event logging
- Job scheduling (concurrency/budget control)
- MiniMax backend support via environment injection
- Backend adapter layer (SDK, CcExecutor)
- Artifact persistence
"""

from .registry import SessionRegistry, SessionRecord, SessionState
from .events import EventLog, Event, EventType
from .scheduler import JobScheduler, BudgetTracker
from .client import CCSessionClient, PromptPackagingError
from .backends import SessionBackend, BackendResult, SDKBackend, CcExecutorBackend
from .artifacts import ArtifactManager

__all__ = [
    "SessionRegistry",
    "SessionRecord", 
    "SessionState",
    "EventLog",
    "Event",
    "EventType",
    "JobScheduler",
    "BudgetTracker",
    "CCSessionClient",
    "PromptPackagingError",
    "SessionBackend",
    "BackendResult",
    "SDKBackend",
    "CcExecutorBackend",
    "ArtifactManager",
]
