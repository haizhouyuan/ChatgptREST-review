"""P6: Ecosystem plugin interface for custom skills and provider adapters.

Defines the contracts third-party plugins must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SkillContract:
    """Versioned contract for a custom skill."""

    skill_id: str
    version: str = "1.0.0"
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    required_providers: list[str] = field(default_factory=list)
    privacy_tier: str = "external_cloud"
    quality_tier: str = "standard"


class ProviderAdapter(ABC):
    """Base class for custom LLM provider adapters.

    Third-party adapters must implement invoke() and probe().
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier."""
        ...

    @abstractmethod
    def invoke(
        self,
        messages: list[dict],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ) -> dict:
        """Invoke the provider and return a standardized response dict."""
        ...

    @abstractmethod
    def probe(self) -> dict:
        """Return health probe result dict."""
        ...


class SkillPlugin(ABC):
    """Base class for custom skill plugins.

    Skills encapsulate reusable task logic (prompt templates,
    post-processing, validation) that can be registered in the
    skill registry and invoked via execute_with_fallback().
    """

    @property
    @abstractmethod
    def contract(self) -> SkillContract:
        ...

    @abstractmethod
    def execute(self, inputs: dict, context: dict) -> dict:
        """Execute the skill with given inputs and runtime context."""
        ...


class SkillRegistry:
    """In-memory registry of loaded skill plugins."""

    def __init__(self):
        self._skills: dict[str, SkillPlugin] = {}
        self._adapters: dict[str, ProviderAdapter] = {}

    def register_skill(self, plugin: SkillPlugin):
        self._skills[plugin.contract.skill_id] = plugin

    def register_adapter(self, adapter: ProviderAdapter):
        self._adapters[adapter.provider_id] = adapter

    def get_skill(self, skill_id: str) -> Optional[SkillPlugin]:
        return self._skills.get(skill_id)

    def get_adapter(self, provider_id: str) -> Optional[ProviderAdapter]:
        return self._adapters.get(provider_id)

    def list_skills(self) -> list[dict]:
        return [
            {
                "skill_id": s.contract.skill_id,
                "version": s.contract.version,
                "required_providers": s.contract.required_providers,
            }
            for s in self._skills.values()
        ]

    def list_adapters(self) -> list[dict]:
        return [
            {"provider_id": a.provider_id}
            for a in self._adapters.values()
        ]
