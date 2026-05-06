"""RoutingEngine — resolves scene+task_type to an ordered candidate chain.

Takes a RouteRequest (scenario, task_type, latency_budget, evidence_level)
and returns a ResolvedRoute with ordered candidates, guard profile, and rationale.

The engine reads from RoutingProfile (loaded from routing_profile.json) and
optionally integrates with:
  - QuotaSensor: skip exhausted / deprioritize degraded providers
  - EvoMapObserver: emit route_selected / outcome signals
  - ModelRouter: EvoMap/Langfuse-enhanced candidate scoring

Usage::

    from chatgptrest.kernel.routing_config import load_routing_profile
    from chatgptrest.kernel.routing_engine import RoutingEngine, RouteRequest

    engine = RoutingEngine(load_routing_profile())
    resolved = engine.resolve(RouteRequest(scenario="research", task_type="research"))
    print(resolved.candidates)  # ordered candidate list
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from chatgptrest.kernel.routing_config import (
    CandidateConfig,
    GuardProfile,
    RoutingProfile,
    SwitchPolicy,
    load_routing_profile,
)

logger = logging.getLogger(__name__)


# ── Request / Response ────────────────────────────────────────────


@dataclass
class RouteRequest:
    """Input to the routing engine."""
    scenario: str = "default"
    task_type: str = "default"
    latency_budget_ms: int = 0       # 0 = no constraint
    evidence_level: str = "none"     # "none" | "light" | "strict"
    need_web: bool = False
    tooling_required: bool = False
    trace_id: str = ""


@dataclass
class ResolvedCandidate:
    """A resolved candidate with its provider config attached."""
    provider: str = ""
    mode: str = "api"
    model: str = ""
    preset: str = ""
    phase: str = ""
    guard_profile_name: str = ""
    timeout_ms: int = 180000
    tier: str = "buffer"
    notes: str = ""
    quota_status: str = ""  # "healthy" | "degraded" | "exhausted" | "cooldown"

    def to_dict(self) -> dict[str, Any]:
        d = {
            "provider": self.provider,
            "mode": self.mode,
            "model": self.model,
            "preset": self.preset,
            "phase": self.phase,
            "guard_profile": self.guard_profile_name,
            "timeout_ms": self.timeout_ms,
            "tier": self.tier,
            "notes": self.notes,
        }
        if self.quota_status:
            d["quota_status"] = self.quota_status
        return d


@dataclass
class ResolvedRoute:
    """Output from the routing engine."""
    scenario: str = ""
    task_type: str = ""
    candidates: list[ResolvedCandidate] = field(default_factory=list)
    guard_profile: GuardProfile | None = None
    switch_policy: SwitchPolicy = field(default_factory=SwitchPolicy)
    rationale: str = ""
    source: str = "config"  # "config" | "config_with_scoring" | "default_fallback"
    config_version: int = 0

    @property
    def primary(self) -> ResolvedCandidate | None:
        """First candidate (primary choice)."""
        return self.candidates[0] if self.candidates else None

    @property
    def fallbacks(self) -> list[ResolvedCandidate]:
        """All candidates except the primary."""
        return self.candidates[1:] if len(self.candidates) > 1 else []

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "task_type": self.task_type,
            "candidates": [c.to_dict() for c in self.candidates],
            "guard_profile": self.guard_profile.__dict__ if self.guard_profile else None,
            "rationale": self.rationale,
            "source": self.source,
            "config_version": self.config_version,
        }


# ── Routing Engine ────────────────────────────────────────────────


class RoutingEngine:
    """Resolves route requests to ordered candidate chains.

    Uses routing_profile.json configuration. Optionally integrates with:
      - QuotaSensor for provider health awareness
      - EvoMapObserver for signal emission
      - ModelRouter for performance-based scoring
    """

    def __init__(
        self,
        profile: RoutingProfile | None = None,
        *,
        model_router: Any = None,
        quota_sensor: Any = None,
        evomap_observer: Any = None,
    ) -> None:
        if profile is None:
            try:
                profile = load_routing_profile()
            except FileNotFoundError:
                logger.warning("No routing_profile.json found, using empty profile")
                profile = RoutingProfile()
        self._profile = profile
        self._model_router = model_router
        self._quota_sensor = quota_sensor
        self._observer = evomap_observer
        self._config_version: int = 1
        self._load_ts: float = time.time()

    @property
    def profile(self) -> RoutingProfile:
        return self._profile

    @property
    def config_version(self) -> int:
        return self._config_version

    def resolve(self, request: RouteRequest) -> ResolvedRoute:
        """Resolve a route request to an ordered candidate chain.

        Pipeline:
        1. Find matching route (exact → scenario → task_type → default → static)
        2. Filter by only_if conditions
        3. Apply quota health (skip exhausted, deprioritize degraded)
        4. Build resolved candidates
        5. Emit route_selected signal (if observer attached)
        """
        route_entry = self._find_route(request.scenario, request.task_type)

        if route_entry is None:
            resolved = self._synthesize_from_static(request)
            self._emit_route_selected(request, resolved)
            return resolved

        # Filter candidates based on only_if conditions
        filtered = []
        skipped_conditions = []
        for cand in route_entry.candidates:
            if self._passes_conditions(cand, request):
                filtered.append(cand)
            else:
                skipped_conditions.append(cand.provider)

        if not filtered:
            logger.warning(
                "All candidates filtered for %s/%s (skipped: %s), using unfiltered",
                request.scenario, request.task_type, skipped_conditions,
            )
            filtered = route_entry.candidates

        # Apply quota health filtering
        available = []
        skipped_quota = []
        for cand in filtered:
            health = self._check_quota(cand.provider)
            if health and health.get("status") == "exhausted":
                skipped_quota.append(f"{cand.provider}(exhausted)")
            else:
                available.append((cand, health))

        if not available:
            # All exhausted — fall back to full list (fail-open)
            logger.warning(
                "All candidates quota-exhausted for %s/%s, using full list",
                request.scenario, request.task_type,
            )
            available = [(c, self._check_quota(c.provider)) for c in filtered]

        # Sort: healthy first, degraded last (stable within same status)
        def _quota_sort_key(item):
            _, health = item
            status = health.get("status", "healthy") if health else "healthy"
            return {"healthy": 0, "degraded": 1, "cooldown": 2, "exhausted": 3}.get(status, 1)
        available.sort(key=_quota_sort_key)

        # Build resolved candidates
        candidates = []
        primary_guard = ""
        for cand, health in available:
            prov = self._profile.providers.get(cand.provider)
            tier = prov.tier if prov else "buffer"
            quota_status = health.get("status", "") if health else ""
            rc = ResolvedCandidate(
                provider=cand.provider,
                mode=cand.mode,
                model=cand.model,
                preset=cand.preset,
                phase=cand.phase,
                guard_profile_name=cand.guard_profile,
                timeout_ms=cand.timeout_ms,
                tier=tier,
                notes=cand.notes,
                quota_status=quota_status,
            )
            candidates.append(rc)
            if not primary_guard and cand.guard_profile:
                primary_guard = cand.guard_profile

        # Resolve guard profile
        guard = self._profile.guards.get(primary_guard) if primary_guard else None
        if guard is None and "global" in self._profile.guards:
            guard = self._profile.guards["global"]

        # Build rationale
        primary = candidates[0] if candidates else None
        rationale = (
            f"Route {request.scenario}/{request.task_type} → "
            f"{primary.provider}/{primary.model or primary.preset or primary.mode}"
            f" ({primary.tier})"
            if primary else
            f"No candidates for {request.scenario}/{request.task_type}"
        )
        if skipped_conditions:
            rationale += f" [condition_filtered: {', '.join(skipped_conditions)}]"
        if skipped_quota:
            rationale += f" [quota_skipped: {', '.join(skipped_quota)}]"

        resolved = ResolvedRoute(
            scenario=request.scenario,
            task_type=request.task_type,
            candidates=candidates,
            guard_profile=guard,
            switch_policy=self._profile.switch_policy,
            rationale=rationale,
            source="config",
            config_version=self._config_version,
        )

        logger.info(
            "RoutingEngine: %s/%s → %d candidates [v%d] %s",
            request.scenario, request.task_type,
            len(candidates), self._config_version,
            rationale,
        )

        # Emit route_selected signal
        self._emit_route_selected(request, resolved)

        return resolved

    def report_outcome(
        self,
        provider_id: str,
        *,
        success: bool,
        error_type: str = "",
        latency_ms: int = 0,
        cooldown_seconds: int = 0,
        trace_id: str = "",
    ) -> None:
        """Report the outcome of using a candidate. Updates QuotaSensor and emits signal."""
        # Update QuotaSensor
        if self._quota_sensor:
            if success:
                self._quota_sensor.report_success(provider_id)
            elif cooldown_seconds > 0:
                self._quota_sensor.report_failure(
                    provider_id, error_type, cooldown_seconds=cooldown_seconds,
                )
            else:
                self._quota_sensor.report_failure(provider_id, error_type)

        # Emit EvoMap signal
        if self._observer:
            try:
                from chatgptrest.evomap.signals import Signal
                self._observer.record(Signal(
                    trace_id=trace_id,
                    signal_type="route.candidate_outcome",
                    source="routing_engine",
                    domain="routing",
                    data={
                        "provider": provider_id,
                        "success": success,
                        "error_type": error_type,
                        "latency_ms": latency_ms,
                        "config_version": self._config_version,
                    },
                ))
            except Exception:
                pass  # fail-open

    def reload(self, path: str | None = None) -> None:
        """Reload configuration from disk.

        Thread-safe: builds new profile, then replaces reference.
        In-flight requests use the old profile until they complete.
        """
        new_profile = load_routing_profile(path, validate=True)
        self._profile = new_profile
        self._config_version += 1
        self._load_ts = time.time()
        logger.info(
            "RoutingEngine: reloaded config v%d (%s, %d routes)",
            self._config_version, new_profile.profile_name, len(new_profile.routes),
        )

    # ── Internal ──────────────────────────────────────────────────

    def _check_quota(self, provider_id: str) -> dict | None:
        """Check provider quota health. Returns dict or None if no sensor."""
        if not self._quota_sensor:
            return None
        try:
            health = self._quota_sensor.check(provider_id)
            return health.to_dict() if hasattr(health, "to_dict") else {"status": "healthy"}
        except Exception:
            return None  # fail-open

    def _emit_route_selected(self, request: RouteRequest, resolved: ResolvedRoute) -> None:
        """Emit route_selected signal to EvoMap observer."""
        if not self._observer:
            return
        try:
            from chatgptrest.evomap.signals import Signal
            self._observer.record(Signal(
                trace_id=request.trace_id,
                signal_type="route.selected",
                source="routing_engine",
                domain="routing",
                data={
                    "scenario": resolved.scenario,
                    "task_type": resolved.task_type,
                    "primary": resolved.primary.to_dict() if resolved.primary else None,
                    "candidate_count": len(resolved.candidates),
                    "source": resolved.source,
                    "config_version": self._config_version,
                },
            ))
        except Exception:
            pass  # fail-open: never break routing for observability

    def _find_route(self, scenario: str, task_type: str):
        """Find best matching route entry."""
        s_lower = scenario.lower() if scenario else "default"
        t_lower = task_type.lower() if task_type else "default"

        # 1. Exact match
        for entry in self._profile.routes:
            if (entry.match.scenario.lower() == s_lower
                    and entry.match.task_type.lower() == t_lower):
                return entry

        # 2. Scenario match (any task_type)
        for entry in self._profile.routes:
            if entry.match.scenario.lower() == s_lower:
                return entry

        # 3. Task_type match (any scenario)
        for entry in self._profile.routes:
            if entry.match.task_type.lower() == t_lower:
                return entry

        # 4. Default route
        for entry in self._profile.routes:
            if entry.match.scenario.lower() == "default":
                return entry

        return None

    def _passes_conditions(
        self, cand: CandidateConfig, req: RouteRequest,
    ) -> bool:
        """Check if a candidate's only_if conditions are satisfied."""
        oi = cand.only_if
        if oi is None:
            return True  # No conditions = always passes

        if oi.evidence_level_in is not None:
            if req.evidence_level not in oi.evidence_level_in:
                return False

        if oi.latency_budget_ms_gte is not None:
            if req.latency_budget_ms > 0 and req.latency_budget_ms < oi.latency_budget_ms_gte:
                return False

        if oi.need_web is not None:
            if oi.need_web and not req.need_web:
                return False

        if oi.tooling_required is not None:
            if oi.tooling_required and not req.tooling_required:
                return False

        return True

    def _synthesize_from_static(self, request: RouteRequest) -> ResolvedRoute:
        """Synthesize a route from static_routes when no route entry matches."""
        s_lower = request.scenario.lower() if request.scenario else "default"

        models = self._profile.static_routes.get(
            s_lower,
            self._profile.static_routes.get("default", []),
        )

        candidates = []
        for model_name in models:
            model_cfg = self._profile.models.get(model_name)
            provider = ""
            mode = "api"
            if model_cfg:
                pt = model_cfg.provider_type
                if pt == "web_chatgpt":
                    provider = "chatgpt_web"
                    mode = "web"
                elif pt == "web_gemini":
                    provider = "gemini_web"
                    mode = "web"
                elif pt == "cli_gemini":
                    provider = "gemini_cli"
                    mode = "mcp"
                else:
                    provider = "coding_plan"
                    mode = "api"

            prov = self._profile.providers.get(provider)
            tier = prov.tier if prov else "buffer"

            candidates.append(ResolvedCandidate(
                provider=provider,
                mode=mode,
                model=model_name,
                timeout_ms=180000,
                tier=tier,
            ))

        rationale = (
            f"Synthesized from static_routes[{s_lower}]: "
            f"{', '.join(models)}"
        )

        return ResolvedRoute(
            scenario=request.scenario,
            task_type=request.task_type,
            candidates=candidates,
            switch_policy=self._profile.switch_policy,
            rationale=rationale,
            source="default_fallback",
            config_version=self._config_version,
        )
