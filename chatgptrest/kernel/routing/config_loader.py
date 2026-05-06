"""Configuration loader for routing_profile.json v2.0.

Loads providers, task profiles, intent mapping, and health config.
Supports hot-reload via ConfigWatcher integration.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import Capability, ProviderSpec, ProviderType, TaskProfile

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "routing_profile.json"


# ── Parsed config ────────────────────────────────────────────────

@dataclass
class HealthConfig:
    window_seconds: int = 600
    degraded_failure_rate: float = 0.3
    exhausted_failure_rate: float = 0.6
    recovery_successes: int = 3
    cooldown_default_seconds: int = 120


@dataclass
class RoutingConfig:
    """Full parsed routing configuration."""
    version: str = "2.0"
    providers: dict[str, ProviderSpec] = field(default_factory=dict)
    task_profiles: dict[str, TaskProfile] = field(default_factory=dict)
    intent_mapping: dict[str, str] = field(default_factory=dict)
    health: HealthConfig = field(default_factory=HealthConfig)
    _load_errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self._load_errors) == 0 and len(self.providers) > 0


# ── Parsing helpers ──────────────────────────────────────────────

def _parse_capability(s: str) -> Capability | None:
    try:
        return Capability(s)
    except ValueError:
        return None


def _parse_provider_type(s: str) -> ProviderType:
    try:
        return ProviderType(s)
    except ValueError:
        return ProviderType.API


def _parse_provider(pid: str, raw: dict[str, Any]) -> ProviderSpec:
    caps = set()
    for c in raw.get("capabilities", []):
        cap = _parse_capability(c)
        if cap:
            caps.add(cap)

    return ProviderSpec(
        id=pid,
        display_name=raw.get("display_name", pid),
        type=_parse_provider_type(raw.get("type", "api")),
        capabilities=caps,
        tier=int(raw.get("tier", 3)),
        avg_latency_ms=int(raw.get("avg_latency_ms", 5000)),
        max_concurrent=int(raw.get("max_concurrent", 1)),
        cost_per_call=float(raw.get("cost_per_call", 0.0)),
        requires=raw.get("requires", []),
        models=raw.get("models", []),
        presets=raw.get("presets", {}),
        enabled=raw.get("enabled", True),
    )


def _parse_task_profile(tid: str, raw: dict[str, Any]) -> TaskProfile:
    req_caps = set()
    for c in raw.get("required_caps", []):
        cap = _parse_capability(c)
        if cap:
            req_caps.add(cap)
    pref_caps = set()
    for c in raw.get("preferred_caps", []):
        cap = _parse_capability(c)
        if cap:
            pref_caps.add(cap)

    return TaskProfile(
        task_type=tid,
        required_caps=req_caps,
        preferred_caps=pref_caps,
        quality_weight=float(raw.get("quality_weight", 0.5)),
        latency_weight=float(raw.get("latency_weight", 0.3)),
        cost_weight=float(raw.get("cost_weight", 0.2)),
        max_latency_ms=raw.get("max_latency_ms"),
        min_tier=int(raw.get("min_tier", 3)),
        description=raw.get("description", ""),
    )


# ── Main loader ──────────────────────────────────────────────────

def load_config(path: str | Path | None = None) -> RoutingConfig:
    """Load and parse routing_profile.json.

    Args:
        path: Config file path. Falls back to ROUTING_PROFILE_PATH env var,
              then to the default config/routing_profile.json.

    Returns:
        RoutingConfig with providers, task_profiles, intent_mapping, health.
        If loading fails, returns a config with _load_errors populated.
    """
    if path is None:
        path = os.environ.get("ROUTING_PROFILE_PATH", str(_DEFAULT_CONFIG_PATH))
    path = Path(path)

    errors: list[str] = []

    if not path.exists():
        return RoutingConfig(_load_errors=[f"Config file not found: {path}"])

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return RoutingConfig(_load_errors=[f"Failed to read config: {e}"])

    # Providers
    providers: dict[str, ProviderSpec] = {}
    for pid, praw in raw.get("providers", {}).items():
        try:
            providers[pid] = _parse_provider(pid, praw)
        except Exception as e:
            errors.append(f"Provider '{pid}': {e}")

    # Task profiles
    task_profiles: dict[str, TaskProfile] = {}
    for tid, traw in raw.get("task_profiles", {}).items():
        try:
            task_profiles[tid] = _parse_task_profile(tid, traw)
        except Exception as e:
            errors.append(f"TaskProfile '{tid}': {e}")

    # Intent mapping
    intent_mapping = raw.get("intent_mapping", {})

    # Health config
    health_raw = raw.get("health", {})
    health = HealthConfig(
        window_seconds=int(health_raw.get("window_seconds", 600)),
        degraded_failure_rate=float(health_raw.get("degraded_failure_rate", 0.3)),
        exhausted_failure_rate=float(health_raw.get("exhausted_failure_rate", 0.6)),
        recovery_successes=int(health_raw.get("recovery_successes", 3)),
        cooldown_default_seconds=int(health_raw.get("cooldown_default_seconds", 120)),
    )

    # Validate
    if not providers:
        errors.append("No providers defined")
    if not task_profiles:
        errors.append("No task profiles defined")

    # Check intent_mapping references
    for intent, profile in intent_mapping.items():
        if profile not in task_profiles:
            errors.append(
                f"Intent '{intent}' maps to unknown profile '{profile}'"
            )

    cfg = RoutingConfig(
        version=raw.get("version", "2.0"),
        providers=providers,
        task_profiles=task_profiles,
        intent_mapping=intent_mapping,
        health=health,
        _load_errors=errors,
    )

    if errors:
        logger.warning("Routing config loaded with %d warnings: %s", len(errors), errors)
    else:
        logger.info(
            "Routing config loaded: %d providers, %d profiles, %d mappings",
            len(providers), len(task_profiles), len(intent_mapping),
        )
    return cfg


# ── Hot-reload watcher ───────────────────────────────────────────

class ConfigWatcher:
    """Polls routing_profile.json for changes and hot-reloads.

    Thread-safe: consumers read config via .config property which
    returns an atomically-swapped reference.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        poll_interval: float = 5.0,
        on_reload: Any = None,
    ):
        if path is None:
            path = os.environ.get("ROUTING_PROFILE_PATH", str(_DEFAULT_CONFIG_PATH))
        self._path = Path(path)
        self._poll_interval = poll_interval
        self._on_reload = on_reload
        self._config: RoutingConfig = load_config(self._path)
        self._config_version: int = 1
        self._last_mtime: float = self._get_mtime()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def config(self) -> RoutingConfig:
        with self._lock:
            return self._config

    @property
    def config_version(self) -> int:
        with self._lock:
            return self._config_version

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="routing-config-watcher"
        )
        self._thread.start()
        logger.info("ConfigWatcher started, watching %s", self._path)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self._poll_interval + 1)
        logger.info("ConfigWatcher stopped")

    def _get_mtime(self) -> float:
        try:
            return self._path.stat().st_mtime
        except OSError:
            return 0.0

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            self._stop.wait(self._poll_interval)
            if self._stop.is_set():
                break
            try:
                mtime = self._get_mtime()
                if mtime != self._last_mtime and mtime > 0:
                    self._last_mtime = mtime
                    new_cfg = load_config(self._path)
                    if new_cfg.is_valid:
                        with self._lock:
                            self._config = new_cfg
                            self._config_version += 1
                            ver = self._config_version
                        logger.info("Config hot-reloaded (version %d)", ver)
                        if self._on_reload:
                            try:
                                self._on_reload(new_cfg)
                            except Exception as e:
                                logger.warning("on_reload callback failed: %s", e)
                    else:
                        logger.warning(
                            "Config change rejected (invalid): %s",
                            new_cfg._load_errors,
                        )
            except Exception as e:
                logger.warning("ConfigWatcher poll error: %s", e)
