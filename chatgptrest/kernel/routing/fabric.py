"""RoutingFabric — the unified entry point for all model selection.

All 4 previously-independent model selection paths converge here:
  1. graph._get_llm_fn()       → fabric.get_llm_fn(intent_route, task_type)
  2. report_graph._get_llm()   → fabric.get_llm_fn("report", "report_writing")
  3. llm_connector._select()   → fabric.resolve(...).api_only()
  4. cc_native.py              → fabric.resolve(intent_route="cc_task")

Usage::

    fabric = RoutingFabric.from_config()
    
    # Option A: Get a callable LLM function (with automatic fallback chain)
    llm_fn = fabric.get_llm_fn("report", "report_writing")
    answer = llm_fn("Write a report about...", "You are a report writer.")
    
    # Option B: Get ranked providers (for custom execution logic)
    route = fabric.resolve(RouteRequest(intent_route="deep_research"))
    for candidate in route.candidates:
        print(candidate.provider.id, candidate.score)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from .config_loader import ConfigWatcher, RoutingConfig, load_config
from .feedback import FeedbackCollector
from .health_tracker import HealthTracker
from .provider_registry import ProviderRegistry
from .selector import Selector
from .types import (
    ExecutionOutcome,
    ProviderType,
    ResolvedCandidate,
    ResolvedRoute,
    RouteRequest,
    TaskProfile,
)

logger = logging.getLogger(__name__)

# Type alias for an LLM callable
LLMFn = Callable[[str, str], str]


class RoutingFabric:
    """Unified model routing — the single source of truth for 'who executes'.

    Architecture:
        ProviderRegistry  →  Selector  →  ResolvedRoute
              ↑                  ↑
        ConfigWatcher       HealthTracker  ←  FeedbackCollector
    """

    def __init__(
        self,
        config: RoutingConfig | None = None,
        health_tracker: HealthTracker | None = None,
        evomap_observer: Any = None,
        mcp_bridge: Any = None,
        llm_connector: Any = None,
    ):
        """Initialize the fabric.

        Args:
            config: Parsed routing config. If None, loads from default path.
            health_tracker: Provider health monitor. Created if None.
            evomap_observer: EvoMap observer for feedback signals.
            mcp_bridge: McpLlmBridge instance for MCP_WEB providers.
            llm_connector: LLMConnector instance for API providers.
        """
        self._config = config or load_config()
        self._registry = ProviderRegistry(self._config.providers)

        # Health
        hcfg = self._config.health
        self._health = health_tracker or HealthTracker(
            window_seconds=hcfg.window_seconds,
            degraded_failure_rate=hcfg.degraded_failure_rate,
            exhausted_failure_rate=hcfg.exhausted_failure_rate,
            recovery_successes=hcfg.recovery_successes,
            cooldown_default_seconds=hcfg.cooldown_default_seconds,
        )

        # Selector
        self._selector = Selector(health_tracker=self._health)

        # Feedback
        self._feedback = FeedbackCollector(
            health_tracker=self._health,
            evomap_observer=evomap_observer,
            on_quality_update=self._selector.update_quality_history,
        )

        # Execution bridges
        self._mcp_bridge = mcp_bridge
        self._llm_connector = llm_connector
        self._evomap_observer = evomap_observer

        # Config watcher (started explicitly)
        self._watcher: ConfigWatcher | None = None
        self._config_version = 1

        if self._config.is_valid:
            logger.info(
                "RoutingFabric initialized: %d providers, %d profiles",
                len(self._registry), len(self._config.task_profiles),
            )
        else:
            logger.warning(
                "RoutingFabric initialized with config errors: %s",
                self._config._load_errors,
            )

    @classmethod
    def from_config(
        cls,
        config_path: str | None = None,
        **kwargs: Any,
    ) -> "RoutingFabric":
        """Create a RoutingFabric from a config file."""
        config = load_config(config_path)
        return cls(config=config, **kwargs)

    # ── Core API ─────────────────────────────────────────────────

    def resolve(self, request: RouteRequest) -> ResolvedRoute:
        """Resolve a route request to a ranked list of providers.

        This is the core method. Given an intent route and/or task type,
        it returns a list of providers ranked by composite score.

        Args:
            request: What we need (intent_route, task_type, context).

        Returns:
            ResolvedRoute with ranked candidates.
        """
        # Determine task profile
        profile = self._resolve_profile(request)
        if not profile:
            logger.warning(
                "No profile found for intent=%s task=%s, using default",
                request.intent_route, request.task_type,
            )
            profile = self._config.task_profiles.get("default", TaskProfile(task_type="default"))

        # Get candidates from registry
        candidates = self._registry.enabled()

        # Run selector
        ranked = self._selector.select(candidates, profile)

        route = ResolvedRoute(
            candidates=ranked,
            task_profile=profile,
            rationale=self._build_rationale(request, profile, ranked),
            config_version=self._config_version,
        )

        logger.debug(
            "Resolved %s/%s → %s",
            request.intent_route, request.task_type,
            [c.provider.id for c in ranked[:3]],
        )
        return route

    def get_llm_fn(
        self,
        intent_route: str = "",
        task_type: str = "",
        *,
        trace_id: str = "",
    ) -> LLMFn:
        """Get a callable LLM function with automatic fallback chain.

        The returned function tries each provider in priority order.
        If one fails, it automatically falls back to the next.
        All outcomes are reported to the feedback collector.

        Args:
            intent_route: From v3 advisor ("report", "deep_research", ...).
            task_type: Direct task type (overrides intent_mapping).
            trace_id: For tracing/observability.

        Returns:
            A callable ``(prompt: str, system_msg: str) -> str``.
        """
        route = self.resolve(RouteRequest(
            intent_route=intent_route,
            task_type=task_type,
            trace_id=trace_id,
        ))

        effective_task = task_type or self._config.intent_mapping.get(
            intent_route, "default"
        )

        def _chain(prompt: str, system_msg: str = "") -> str:
            total_candidates = len(route.candidates)
            for idx, candidate in enumerate(route.candidates):
                provider = candidate.provider
                start = time.perf_counter()
                try:
                    result = self._invoke_provider(provider, prompt, system_msg)
                    if result and len(result.strip()) > 10:
                        latency = int((time.perf_counter() - start) * 1000)
                        self._feedback.report(ExecutionOutcome(
                            provider_id=provider.id,
                            task_type=effective_task,
                            success=True,
                            latency_ms=latency,
                            trace_id=trace_id,
                        ))
                        logger.info(
                            "RoutingFabric: %s returned %d chars in %dms",
                            provider.id, len(result), latency,
                        )
                        return result
                    else:
                        logger.info(
                            "RoutingFabric: %s returned empty, trying next",
                            provider.id,
                        )
                        latency = int((time.perf_counter() - start) * 1000)
                        self._feedback.report(ExecutionOutcome(
                            provider_id=provider.id,
                            task_type=effective_task,
                            success=False,
                            latency_ms=latency,
                            error_type="empty_response",
                            trace_id=trace_id,
                        ))
                        if idx + 1 < total_candidates:
                            self._feedback.emit_fallback(
                                trace_id=trace_id,
                                task_type=effective_task,
                                from_provider_id=provider.id,
                                to_provider_id=route.candidates[idx + 1].provider.id,
                                attempt_index=idx + 1,
                                total_candidates=total_candidates,
                                error_type="empty_response",
                                latency_ms=latency,
                            )
                except Exception as e:
                    latency = int((time.perf_counter() - start) * 1000)
                    error_type = self._classify_error(e)
                    self._feedback.report(ExecutionOutcome(
                        provider_id=provider.id,
                        task_type=effective_task,
                        success=False,
                        latency_ms=latency,
                        error_type=error_type,
                        trace_id=trace_id,
                    ))
                    if idx + 1 < total_candidates:
                        self._feedback.emit_fallback(
                            trace_id=trace_id,
                            task_type=effective_task,
                            from_provider_id=provider.id,
                            to_provider_id=route.candidates[idx + 1].provider.id,
                            attempt_index=idx + 1,
                            total_candidates=total_candidates,
                            error_type=error_type,
                            latency_ms=latency,
                        )
                    logger.warning(
                        "RoutingFabric: %s failed (%s): %s, trying next",
                        provider.id, error_type, e,
                    )
            # All candidates exhausted
            logger.error(
                "RoutingFabric: all %d candidates failed for %s/%s",
                len(route.candidates), intent_route, effective_task,
            )
            return ""

        return _chain

    def report_outcome(self, outcome: ExecutionOutcome) -> None:
        """Manually report execution outcome (for worker/executor integration)."""
        self._feedback.report(outcome)

    # ── Observability ────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return operational status of the routing fabric."""
        health_map = self._health.all_health()
        return {
            "config_version": self._config_version,
            "total_providers": len(self._registry),
            "enabled_providers": len(self._registry.enabled()),
            "provider_health": {
                pid: {
                    "status": h.status.value,
                    "failure_rate": round(h.failure_rate, 3),
                    "latency_ms": round(h.recent_latency_ms, 1),
                    "available": h.is_available(),
                }
                for pid, h in health_map.items()
            },
            "task_profiles": list(self._config.task_profiles.keys()),
            "intent_mappings": dict(self._config.intent_mapping),
        }

    # ── Hot-reload ───────────────────────────────────────────────

    def start_watcher(self, config_path: str | None = None) -> None:
        """Start watching config file for changes."""
        if self._watcher:
            return
        self._watcher = ConfigWatcher(
            path=config_path,
            on_reload=self._on_config_reload,
        )
        self._watcher.start()

    def stop_watcher(self) -> None:
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

    def _on_config_reload(self, new_config: RoutingConfig) -> None:
        self._config = new_config
        self._registry.update(new_config.providers)
        self._config_version += 1
        logger.info(
            "RoutingFabric config reloaded (version %d)",
            self._config_version,
        )

    # ── Internals ────────────────────────────────────────────────

    def _resolve_profile(self, request: RouteRequest) -> TaskProfile | None:
        """Find the TaskProfile for a request."""
        # Direct task_type takes precedence
        if request.task_type and request.task_type in self._config.task_profiles:
            return self._config.task_profiles[request.task_type]

        # Map intent_route → task_type
        if request.intent_route:
            mapped = self._config.intent_mapping.get(request.intent_route)
            if mapped and mapped in self._config.task_profiles:
                return self._config.task_profiles[mapped]

        # Fallback to default
        return self._config.task_profiles.get("default")

    def _invoke_provider(
        self,
        provider: Any,
        prompt: str,
        system_msg: str,
    ) -> str:
        """Invoke a provider. Routes to the appropriate bridge/connector."""
        if provider.type == ProviderType.MCP_WEB:
            return self._invoke_mcp(provider, prompt, system_msg)
        elif provider.type in (ProviderType.API, ProviderType.NATIVE_API):
            return self._invoke_api(provider, prompt, system_msg)
        else:
            logger.warning("Unsupported provider type: %s", provider.type)
            return ""

    def _invoke_mcp(self, provider: Any, prompt: str, system_msg: str) -> str:
        """Invoke via McpLlmBridge."""
        if not self._mcp_bridge:
            logger.debug("No MCP bridge available, skipping %s", provider.id)
            return ""

        # Check if MCP bridge recognizes this provider
        model_name = provider.id  # e.g. "chatgpt-web", "gemini-web"
        if not hasattr(self._mcp_bridge, "is_mcp_model"):
            return ""
        if not self._mcp_bridge.is_mcp_model(model_name):
            return ""

        fn = self._mcp_bridge.make_llm_fn(model_name)
        return fn(prompt, system_msg)

    def _invoke_api(self, provider: Any, prompt: str, system_msg: str) -> str:
        """Invoke via LLMConnector."""
        if not self._llm_connector:
            logger.debug("No LLM connector available, skipping %s", provider.id)
            return ""

        # For API providers, we use the connector directly
        # The connector manages its own model selection among API models
        if callable(self._llm_connector):
            return self._llm_connector(prompt, system_msg)
        elif hasattr(self._llm_connector, "__call__"):
            return self._llm_connector(prompt, system_msg)
        return ""

    def _classify_error(self, exc: Exception) -> str:
        """Classify an exception for feedback reporting."""
        msg = str(exc).lower()
        if "timeout" in msg:
            return "timeout"
        if "429" in msg or "rate" in msg or "limit" in msg:
            return "rate_limit"
        if "connection" in msg or "cdp" in msg or "browser" in msg:
            return "infra"
        return "unknown"

    def _build_rationale(
        self,
        request: RouteRequest,
        profile: TaskProfile,
        ranked: list[ResolvedCandidate],
    ) -> str:
        parts = [
            f"intent={request.intent_route or '?'}",
            f"task={profile.task_type}",
            f"candidates={len(ranked)}",
        ]
        if ranked:
            top = ranked[0]
            parts.append(f"top={top.provider.id}(score={top.score:.3f})")
        return " | ".join(parts)
