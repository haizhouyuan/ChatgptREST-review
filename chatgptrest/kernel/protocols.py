from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from chatgptrest.kernel.event_bus import TraceEvent
from chatgptrest.kernel.memory_manager import MemoryRecord, MemoryTier
from chatgptrest.kernel.policy_engine import QualityContext


@runtime_checkable
class MemorySubstrate(Protocol):
    def stage(self, record: MemoryRecord) -> str: ...

    def promote(self, record_id: str, target: MemoryTier, reason: str = "") -> bool: ...

    def stage_and_promote(self, record: MemoryRecord, target: MemoryTier, reason: str = "") -> str: ...

    def audit_trail(self, record_id: str) -> list[dict[str, Any]]: ...

    def get_episodic(
        self,
        query: str = "",
        category: str = "",
        limit: int = 10,
        agent_id: str = "",
        session_id: str = "",
        role_id: str = "",
        account_id: str = "",
        thread_id: str = "",
        project_id: str = "",
    ) -> list[MemoryRecord]: ...

    def get_by_key(self, key: str) -> MemoryRecord | None: ...

    def update_record_value(
        self,
        record_id: str,
        value: dict[str, Any],
        *,
        reason: str = "",
        agent: str = "system",
    ) -> bool: ...


@runtime_checkable
class KBHubLike(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[Any]: ...


@runtime_checkable
class EvoMapKnowledgeDBLike(Protocol):
    def connect(self) -> Any: ...


@runtime_checkable
class PolicyGateResultLike(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


@runtime_checkable
class QualityGateEngine(Protocol):
    def run_quality_gate(self, context: QualityContext) -> PolicyGateResultLike: ...


@runtime_checkable
class EventBusLike(Protocol):
    def emit(self, event: TraceEvent) -> None: ...


@runtime_checkable
class ContextRuntimeDeps(Protocol):
    memory: MemorySubstrate | None
    kb_hub: KBHubLike | None
    evomap_knowledge_db: EvoMapKnowledgeDBLike | None


@runtime_checkable
class MemoryRuntimeDeps(Protocol):
    memory: MemorySubstrate | None
    policy_engine: QualityGateEngine | None
    event_bus: EventBusLike | None


@runtime_checkable
class GraphRuntimeDeps(Protocol):
    evomap_knowledge_db: EvoMapKnowledgeDBLike | None

