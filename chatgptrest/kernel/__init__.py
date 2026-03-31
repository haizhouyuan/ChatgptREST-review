"""Kernel — infrastructure layer for the ChatgptREST platform.

Provides:
  - ArtifactStore: content-addressable artifact storage with provenance
  - PolicyEngine: pluggable security / cost / delivery / quality-gate chain
  - EventBus: TraceEvent publish-subscribe backbone
  - RoutingEngine: scene-based model routing (config-driven)
  - QuotaSensor: provider health tracking for quota-aware routing
  - ConfigWatcher: hot-reload watcher for routing config
  - idempotency helpers (re-exported from core)
"""

from chatgptrest.kernel.artifact_store import ArtifactStore, Artifact
from chatgptrest.kernel.policy_engine import PolicyEngine, QualityContext, QualityGateResult
from chatgptrest.kernel.event_bus import EventBus
from chatgptrest.kernel.routing_config import (
    RoutingProfile,
    load_routing_profile,
)
from chatgptrest.kernel.routing_engine import (
    RoutingEngine,
    RouteRequest,
    ResolvedRoute,
    ResolvedCandidate,
)
from chatgptrest.kernel.quota_sensor import (
    QuotaSensor,
    TierHealth,
    HealthStatus,
)
from chatgptrest.kernel.config_watcher import ConfigWatcher

__all__ = [
    "ArtifactStore",
    "Artifact",
    "PolicyEngine",
    "QualityContext",
    "QualityGateResult",
    "EventBus",
    "RoutingEngine",
    "RouteRequest",
    "ResolvedRoute",
    "ResolvedCandidate",
    "RoutingProfile",
    "load_routing_profile",
    "QuotaSensor",
    "TierHealth",
    "HealthStatus",
    "ConfigWatcher",
]

