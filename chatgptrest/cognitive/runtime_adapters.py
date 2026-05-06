from __future__ import annotations

from dataclasses import dataclass

from chatgptrest.advisor.runtime import AdvisorRuntime
from chatgptrest.kernel.protocols import (
    ContextRuntimeDeps,
    GraphRuntimeDeps,
    MemoryRuntimeDeps,
)


@dataclass(frozen=True)
class ContextRuntimeAdapter(ContextRuntimeDeps):
    memory: object | None
    kb_hub: object | None
    evomap_knowledge_db: object | None

    @classmethod
    def from_runtime(cls, runtime: AdvisorRuntime) -> "ContextRuntimeAdapter":
        return cls(
            memory=runtime.memory,
            kb_hub=runtime.kb_hub,
            evomap_knowledge_db=runtime.evomap_knowledge_db,
        )


@dataclass(frozen=True)
class MemoryRuntimeAdapter(MemoryRuntimeDeps):
    memory: object | None
    policy_engine: object | None
    event_bus: object | None

    @classmethod
    def from_runtime(cls, runtime: AdvisorRuntime) -> "MemoryRuntimeAdapter":
        return cls(
            memory=runtime.memory,
            policy_engine=runtime.policy_engine,
            event_bus=runtime.event_bus,
        )


@dataclass(frozen=True)
class GraphRuntimeAdapter(GraphRuntimeDeps):
    evomap_knowledge_db: object | None

    @classmethod
    def from_runtime(cls, runtime: AdvisorRuntime) -> "GraphRuntimeAdapter":
        return cls(evomap_knowledge_db=runtime.evomap_knowledge_db)

