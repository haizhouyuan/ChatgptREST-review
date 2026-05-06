"""Selector — composite scoring algorithm for provider ranking.

Given a TaskProfile and a set of candidate providers, produces
a ranked list of ResolvedCandidates with scores and rationale.
"""

from __future__ import annotations

import logging
from typing import Any

from .types import (
    Capability,
    ProviderSpec,
    ProviderType,
    ResolvedCandidate,
    TaskProfile,
)
from .health_tracker import HealthStatus, HealthTracker, ProviderHealth

logger = logging.getLogger(__name__)


# ── Scoring constants ────────────────────────────────────────────

# Quality scores by tier (static baseline, overridden by EvoMap history)
_TIER_QUALITY: dict[int, float] = {
    1: 0.90,
    2: 0.70,
    3: 0.50,
}

# Latency score: lower is better, normalized to [0,1]
_LATENCY_CEILING_MS = 30000

# Cost score: lower is better (currently all free/near-free)
_COST_CEILING = 1.0

# Bonus for matching preferred capabilities
_PREFERRED_CAP_BONUS = 0.05


class Selector:
    """Ranks providers for a given TaskProfile.

    Pipeline:
      1. Filter by required capabilities
      2. Filter by min_tier
      3. Filter by max_latency_ms
      4. Filter by health (skip EXHAUSTED/OFFLINE/COOLDOWN)
      5. Score remaining candidates
      6. Sort by composite score descending
      7. Append tier-3 fallbacks if list is short

    Scoring formula::

        score = (
            quality_weight * quality_score
          + latency_weight * latency_score
          + cost_weight * cost_score
          + preferred_cap_bonus
        ) * health_degradation_factor
    """

    def __init__(
        self,
        health_tracker: HealthTracker | None = None,
        quality_history: dict[tuple[str, str], float] | None = None,
    ):
        self._health = health_tracker or HealthTracker()
        # (provider_id, task_type) -> historical quality score [0,1]
        self._quality_history = quality_history or {}

    def select(
        self,
        candidates: list[ProviderSpec],
        profile: TaskProfile,
        *,
        max_results: int = 5,
        include_fallbacks: bool = True,
    ) -> list[ResolvedCandidate]:
        """Rank candidates for the given task profile.

        Args:
            candidates: Pool of potentially matching providers.
            profile: Task requirements and scoring weights.
            max_results: Maximum candidates to return.
            include_fallbacks: If True, appends tier-3 providers when
                               the primary list has fewer than 2 entries.

        Returns:
            Sorted list of ResolvedCandidate (best first).
        """
        # Step 1-3: Filter
        filtered = self._filter(candidates, profile)

        # Step 4: Health filter
        available: list[tuple[ProviderSpec, ProviderHealth]] = []
        skipped_health: list[str] = []
        for p in filtered:
            h = self._health.get_health(p.id)
            if h.is_available():
                available.append((p, h))
            else:
                skipped_health.append(f"{p.id}({h.status.value})")

        if skipped_health:
            logger.debug(
                "Health-filtered providers: %s", ", ".join(skipped_health)
            )

        # Step 5: Score
        scored: list[ResolvedCandidate] = []
        for provider, health in available:
            score, breakdown = self._score(provider, health, profile)
            scored.append(ResolvedCandidate(
                provider=provider,
                score=round(score, 4),
                score_breakdown=breakdown,
                reason=self._reason(provider, breakdown),
            ))

        # Step 6: Sort
        scored.sort(key=lambda c: c.score, reverse=True)

        # Step 7: Fallbacks
        if include_fallbacks and len(scored) < 2:
            fallbacks = self._fallbacks(candidates, profile, exclude={
                c.provider.id for c in scored
            })
            scored.extend(fallbacks)

        return scored[:max_results]

    def update_quality_history(
        self,
        provider_id: str,
        task_type: str,
        quality: float,
    ) -> None:
        """Update the quality baseline from EvoMap feedback."""
        key = (provider_id, task_type)
        # Exponential moving average
        old = self._quality_history.get(key)
        if old is not None:
            self._quality_history[key] = 0.7 * old + 0.3 * quality
        else:
            self._quality_history[key] = quality

    # ── Internals ────────────────────────────────────────────────

    def _filter(
        self,
        candidates: list[ProviderSpec],
        profile: TaskProfile,
    ) -> list[ProviderSpec]:
        result = []
        for p in candidates:
            if not p.enabled:
                continue
            # Required capabilities
            if not p.has_all_capabilities(profile.required_caps):
                continue
            # Min tier (lower number = better tier)
            if p.tier > profile.min_tier:
                continue
            # Max latency
            if profile.max_latency_ms and p.avg_latency_ms > profile.max_latency_ms:
                continue
            result.append(p)
        return result

    def _score(
        self,
        provider: ProviderSpec,
        health: ProviderHealth,
        profile: TaskProfile,
    ) -> tuple[float, dict[str, float]]:
        # Quality: from history or tier-based static
        q_key = (provider.id, profile.task_type)
        quality = self._quality_history.get(q_key, _TIER_QUALITY.get(provider.tier, 0.5))

        # Latency: lower is better
        latency = max(0.0, 1.0 - provider.avg_latency_ms / _LATENCY_CEILING_MS)

        # Cost: lower is better
        cost = max(0.0, 1.0 - provider.cost_per_call / _COST_CEILING) if _COST_CEILING > 0 else 1.0

        # Preferred capability bonus
        pref_bonus = 0.0
        for cap in profile.preferred_caps:
            if provider.has_capability(cap):
                pref_bonus += _PREFERRED_CAP_BONUS

        # Composite
        raw = (
            profile.quality_weight * quality
            + profile.latency_weight * latency
            + profile.cost_weight * cost
            + pref_bonus
        )

        # Apply health degradation
        degradation = health.degradation_factor
        final = raw * degradation

        breakdown = {
            "quality": round(quality, 3),
            "latency": round(latency, 3),
            "cost": round(cost, 3),
            "pref_bonus": round(pref_bonus, 3),
            "raw": round(raw, 4),
            "health_factor": round(degradation, 2),
            "final": round(final, 4),
        }
        return final, breakdown

    def _reason(
        self,
        provider: ProviderSpec,
        breakdown: dict[str, float],
    ) -> str:
        return (
            f"{provider.id} (tier {provider.tier}): "
            f"q={breakdown['quality']:.2f} "
            f"l={breakdown['latency']:.2f} "
            f"$={breakdown['cost']:.2f} "
            f"h={breakdown['health_factor']:.1f} "
            f"→ {breakdown['final']:.3f}"
        )

    def _fallbacks(
        self,
        all_providers: list[ProviderSpec],
        profile: TaskProfile,
        exclude: set[str],
    ) -> list[ResolvedCandidate]:
        """Add tier-3 API fallbacks when the primary list is thin."""
        result = []
        for p in all_providers:
            if p.id in exclude:
                continue
            if not p.enabled:
                continue
            if not p.has_all_capabilities(profile.required_caps):
                continue
            h = self._health.get_health(p.id)
            if not h.is_available():
                continue
            score, breakdown = self._score(p, h, profile)
            result.append(ResolvedCandidate(
                provider=p,
                score=round(score * 0.8, 4),  # Slight penalty for fallback
                score_breakdown=breakdown,
                reason=f"[fallback] {self._reason(p, breakdown)}",
            ))
        result.sort(key=lambda c: c.score, reverse=True)
        return result[:2]
