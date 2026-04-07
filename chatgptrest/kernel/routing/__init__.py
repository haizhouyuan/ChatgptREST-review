"""RoutingFabric — unified model selection for all execution paths.

Three-layer architecture:
  Layer 1: Intent routing (v3 advisor C/K/U/R/I) → "what to do"
  Layer 2: Model routing  (RoutingFabric)        → "who does it"
  Layer 3: Execution      (Worker/CC/MCP)         → "how to run"

Usage::

    from chatgptrest.kernel.routing import RoutingFabric, RouteRequest

    fabric = RoutingFabric.from_config()
    route  = fabric.resolve(RouteRequest(intent_route="report", task_type="report_writing"))
    llm_fn = fabric.get_llm_fn("report", "report_writing")
"""

from chatgptrest.kernel.routing.types import (
    Capability,
    ExecutionOutcome,
    ProviderSpec,
    ProviderType,
    ResolvedCandidate,
    ResolvedRoute,
    RouteRequest,
    TaskProfile,
)
from chatgptrest.kernel.routing.fabric import RoutingFabric

__all__ = [
    "Capability",
    "ExecutionOutcome",
    "ProviderSpec",
    "ProviderType",
    "ResolvedCandidate",
    "ResolvedRoute",
    "RouteRequest",
    "RoutingFabric",
    "TaskProfile",
]
