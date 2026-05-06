"""Provider registry — in-memory lookup of all known providers.

Loaded from routing_profile.json, can be refreshed via hot-reload.
"""

from __future__ import annotations

import logging
from typing import Iterable

from .types import Capability, ProviderSpec, ProviderType

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry of all available providers."""

    def __init__(self, providers: dict[str, ProviderSpec] | None = None):
        self._providers: dict[str, ProviderSpec] = providers or {}

    def get(self, provider_id: str) -> ProviderSpec | None:
        return self._providers.get(provider_id)

    def all(self) -> list[ProviderSpec]:
        return list(self._providers.values())

    def enabled(self) -> list[ProviderSpec]:
        return [p for p in self._providers.values() if p.enabled]

    def with_capability(self, cap: Capability) -> list[ProviderSpec]:
        return [p for p in self.enabled() if p.has_capability(cap)]

    def with_all_capabilities(self, caps: set[Capability]) -> list[ProviderSpec]:
        return [p for p in self.enabled() if p.has_all_capabilities(caps)]

    def by_type(self, ptype: ProviderType) -> list[ProviderSpec]:
        return [p for p in self.enabled() if p.type == ptype]

    def by_tier(self, max_tier: int) -> list[ProviderSpec]:
        """Return providers at or above the given tier (lower number = better)."""
        return [p for p in self.enabled() if p.tier <= max_tier]

    def update(self, providers: dict[str, ProviderSpec]) -> None:
        """Atomically replace all providers (for hot-reload)."""
        self._providers = dict(providers)
        logger.debug("ProviderRegistry updated: %d providers", len(self._providers))

    def __len__(self) -> int:
        return len(self._providers)

    def __contains__(self, provider_id: str) -> bool:
        return provider_id in self._providers

    def __repr__(self) -> str:
        ids = list(self._providers.keys())
        return f"ProviderRegistry({ids})"
