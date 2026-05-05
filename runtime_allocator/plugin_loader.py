"""Dynamic plugin loader for ProviderAdapter and SkillPlugin.

Discovers plugins via Python entry points under the groups:
- paperclip.provider_adapters
- paperclip.skill_plugins

Example entry point in pyproject.toml:
    [project.entry-points."paperclip.provider_adapters"]
    my_adapter = "my_package.adapters:MyAdapter"
"""

from __future__ import annotations

import logging
from typing import Optional

from runtime_allocator.plugin_interface import (
    ProviderAdapter,
    SkillPlugin,
    SkillRegistry,
)

logger = logging.getLogger("paperclip_plugin_loader")


def discover_plugins(registry: Optional[SkillRegistry] = None) -> SkillRegistry:
    """Discover and register all plugins from entry points.

    Returns a populated SkillRegistry.
    """
    if registry is None:
        registry = SkillRegistry()

    try:
        from importlib.metadata import entry_points
    except ImportError:
        from importlib_metadata import entry_points  # type: ignore

    # Provider adapters
    try:
        adapters = entry_points(group="paperclip.provider_adapters")
        for ep in adapters:
            try:
                adapter_cls = ep.load()
                adapter = adapter_cls()
                if isinstance(adapter, ProviderAdapter):
                    registry.register_adapter(adapter)
                    logger.info("loaded_adapter", extra={"provider_id": adapter.provider_id})
            except Exception as exc:
                logger.warning("adapter_load_failed", extra={"entry_point": ep.name, "error": str(exc)})
    except Exception as exc:
        logger.warning("adapter_discovery_failed", extra={"error": str(exc)})

    # Skill plugins
    try:
        skills = entry_points(group="paperclip.skill_plugins")
        for ep in skills:
            try:
                skill_cls = ep.load()
                skill = skill_cls()
                if isinstance(skill, SkillPlugin):
                    registry.register_skill(skill)
                    logger.info("loaded_skill", extra={"skill_id": skill.contract.skill_id})
            except Exception as exc:
                logger.warning("skill_load_failed", extra={"entry_point": ep.name, "error": str(exc)})
    except Exception as exc:
        logger.warning("skill_discovery_failed", extra={"error": str(exc)})

    return registry
