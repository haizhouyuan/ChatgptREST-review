"""Core types for the RoutingFabric.

Defines the data model:
  - ProviderSpec: what a provider can do
  - TaskProfile:  what a task needs
  - RouteRequest: input to resolve()
  - ResolvedRoute / ResolvedCandidate: output of resolve()
  - ExecutionOutcome: feedback after execution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Enumerations ─────────────────────────────────────────────────

class ProviderType(str, Enum):
    """How the provider is invoked."""
    MCP_WEB = "mcp_web"        # Browser-based via MCP (ChatGPT Web, Gemini Web)
    API = "api"                # HTTP API (Coding Plan / OpenAI-compatible)
    NATIVE_API = "native_api"  # Direct SDK (Anthropic Python)
    CLI = "cli"                # CLI subprocess (claude code)


class Capability(str, Enum):
    """What a provider can do."""
    CHAT = "chat"
    DEEP_RESEARCH = "deep_research"
    CODE_GEN = "code_gen"
    IMAGE_GEN = "image_gen"
    WEB_SEARCH = "web_search"
    TOOL_USE = "tool_use"
    ANALYSIS = "analysis"


# ── Provider ─────────────────────────────────────────────────────

@dataclass
class ProviderSpec:
    """Describes a provider's identity, capabilities, and constraints.

    A provider is a *channel* to an LLM (not a specific model).
    Examples: "chatgpt-web", "gemini-web", "qwen-api", "claude-api".
    """
    id: str                                   # Unique ID, e.g. "chatgpt-web"
    display_name: str = ""                    # Human label
    type: ProviderType = ProviderType.API
    capabilities: set[Capability] = field(default_factory=set)
    tier: int = 3                             # 1=flagship, 2=high, 3=standard
    avg_latency_ms: int = 5000
    max_concurrent: int = 1
    cost_per_call: float = 0.0                # Estimated cost
    requires: list[str] = field(default_factory=list)  # Runtime deps
    models: list[str] = field(default_factory=list)    # For API providers
    presets: dict[str, dict[str, Any]] = field(default_factory=dict)
    enabled: bool = True

    def has_capability(self, cap: Capability) -> bool:
        return cap in self.capabilities

    def has_all_capabilities(self, caps: set[Capability]) -> bool:
        return caps.issubset(self.capabilities)


# ── Task Profile ─────────────────────────────────────────────────

@dataclass
class TaskProfile:
    """Describes what a task type needs from a provider.

    Used by the Selector to match and score providers.
    """
    task_type: str                            # e.g. "report_writing"
    required_caps: set[Capability] = field(default_factory=set)
    preferred_caps: set[Capability] = field(default_factory=set)
    quality_weight: float = 0.5               # Weight in composite score
    latency_weight: float = 0.3
    cost_weight: float = 0.2
    max_latency_ms: int | None = None         # Hard latency cap
    min_tier: int = 3                         # Minimum tier (1=must be flagship)
    description: str = ""


# ── Route Request / Response ─────────────────────────────────────

@dataclass
class RouteRequest:
    """Input to RoutingFabric.resolve()."""
    intent_route: str = ""       # From v3 advisor: "report", "deep_research", ...
    task_type: str = ""          # Overrides intent_mapping if provided
    context: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""


@dataclass
class ResolvedCandidate:
    """A single provider in the resolved chain."""
    provider: ProviderSpec
    score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    reason: str = ""


@dataclass
class ResolvedRoute:
    """Output of RoutingFabric.resolve()."""
    candidates: list[ResolvedCandidate] = field(default_factory=list)
    task_profile: TaskProfile | None = None
    rationale: str = ""
    config_version: int = 0

    @property
    def top(self) -> ResolvedCandidate | None:
        """Best candidate."""
        return self.candidates[0] if self.candidates else None

    def api_only(self) -> list[str]:
        """Return model names from API-type providers only."""
        result: list[str] = []
        for c in self.candidates:
            if c.provider.type == ProviderType.API:
                result.extend(c.provider.models or [])
        return result or ["MiniMax-M2.5", "qwen3.5-plus", "kimi-k2.5"]  # fallback


# ── Execution Feedback ───────────────────────────────────────────

@dataclass
class ExecutionOutcome:
    """Reported after each LLM call for feedback loop."""
    provider_id: str
    task_type: str
    success: bool
    latency_ms: int = 0
    quality_score: float | None = None     # From Gate/Review scoring
    error_type: str | None = None          # "timeout", "rate_limit", "infra", ...
    cooldown_seconds: int | None = None    # If got 429
    trace_id: str = ""
    timestamp: str = ""
