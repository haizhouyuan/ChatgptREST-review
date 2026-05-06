"""Three-Source Fusion ModelRouter — EvoMap + Langfuse + Static Rules.

Selects the optimal model for each LLM call based on:
  1. EvoMap signals: real-time success rate, latency, error patterns
  2. Langfuse traces: token costs, quality scores, deep analytics
  3. Static rules:   cold-start defaults, hard constraints

The router is fail-open: if EvoMap/Langfuse are unavailable,
it falls back to static rules (current _ROUTE_MAP behavior).

Usage::

    router = ModelRouter()
    models = router.select("coding", trace_id="tr_001")
    # → ["qwen3-coder-plus", "kimi-k2.5", "MiniMax-M2.5"]
    # (order based on historical performance)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Provider Types ────────────────────────────────────────────────

class ProviderType:
    """How a model is invoked — determines the calling mechanism."""
    API = "api"              # Coding Plan API (qwen/kimi/glm/minimax) — fast, API key
    WEB_CHATGPT = "web_chatgpt"  # ChatGPT Web via Playwright MCP — slow, high quality
    WEB_GEMINI = "web_gemini"    # Gemini Web via Playwright MCP — slow, high quality
    CLI_GEMINI = "cli_gemini"    # Gemini CLI MCP → Gemini Pro 3.1 Preview — medium, powerful
    MCP = "mcp"              # Generic MCP tool invocation


@dataclass
class ModelInfo:
    """Model metadata for routing."""
    name: str
    provider_type: str  # ProviderType
    display_name: str = ""
    avg_latency_hint: float = 3000  # expected latency ms (for cold-start)
    cost_hint: float = 0.01         # $/call estimate
    quality_hint: float = 0.7       # expected quality (for cold-start)
    capabilities: list[str] = field(default_factory=list)  # ["coding", "research", ...]
    invocation: str = ""  # how to call: API endpoint, MCP tool name, etc.


# ── Model Registry ───────────────────────────────────────────────

MODEL_REGISTRY: dict[str, ModelInfo] = {
    # ── API Models (Coding Plan API) ──
    "MiniMax-M2.5": ModelInfo(
        "MiniMax-M2.5", ProviderType.API, "MiniMax M2.5",
        avg_latency_hint=3000, cost_hint=0.01, quality_hint=0.8,
        capabilities=["planning", "review", "report", "research", "default"],
    ),
    "qwen3.5-plus": ModelInfo(
        "qwen3.5-plus", ProviderType.API, "Qwen 3.5 Plus",
        avg_latency_hint=4000, cost_hint=0.01, quality_hint=0.75,
        capabilities=["planning", "research", "review", "default"],
    ),
    "qwen3-coder-plus": ModelInfo(
        "qwen3-coder-plus", ProviderType.API, "Qwen 3 Coder Plus",
        avg_latency_hint=3500, cost_hint=0.01, quality_hint=0.85,
        capabilities=["coding", "debug"],
    ),
    "kimi-k2.5": ModelInfo(
        "kimi-k2.5", ProviderType.API, "Kimi K2.5",
        avg_latency_hint=3500, cost_hint=0.01, quality_hint=0.75,
        capabilities=["coding", "debug", "default"],
    ),
    "glm-5": ModelInfo(
        "glm-5", ProviderType.API, "GLM 5",
        avg_latency_hint=3000, cost_hint=0.01, quality_hint=0.7,
        capabilities=["planning", "debug", "review", "report"],
    ),
    # ── Web Models (Playwright MCP) ──
    "chatgpt-web": ModelInfo(
        "chatgpt-web", ProviderType.WEB_CHATGPT, "ChatGPT Web (GPT-4o)",
        avg_latency_hint=40000, cost_hint=0.0, quality_hint=0.9,
        capabilities=["research", "report", "planning", "review"],
        invocation="chatgpt_web.ask",
    ),
    "gemini-web": ModelInfo(
        "gemini-web", ProviderType.WEB_GEMINI, "Gemini Web (2.5 Pro)",
        avg_latency_hint=30000, cost_hint=0.0, quality_hint=0.9,
        capabilities=["research", "report", "planning", "coding"],
        invocation="gemini_web.ask",
    ),
    # ── CLI MCP Model ──
    "gemini-cli": ModelInfo(
        "gemini-cli", ProviderType.CLI_GEMINI, "Gemini Pro 3.1 Preview (CLI MCP)",
        avg_latency_hint=15000, cost_hint=0.0, quality_hint=0.95,
        capabilities=["research", "coding", "planning", "report", "review", "debug", "default"],
        invocation="gemini_cli_ask",
    ),
}


# ── Static Rules (cold-start + hard constraints) ─────────────────

STATIC_ROUTES: dict[str, list[str]] = {
    # Fast tasks: API first, CLI MCP for quality boost
    "planning":  ["gemini-cli", "MiniMax-M2.5", "qwen3.5-plus"],
    "coding":    ["gemini-cli", "qwen3-coder-plus", "kimi-k2.5"],
    "debug":     ["gemini-cli", "kimi-k2.5", "MiniMax-M2.5"],
    "review":    ["gemini-cli", "MiniMax-M2.5", "qwen3.5-plus"],
    # Deep tasks: Web models for highest quality, CLI MCP as backup
    "research":  ["gemini-web", "chatgpt-web", "gemini-cli"],
    "report":    ["gemini-web", "chatgpt-web", "gemini-cli"],
    # Default: CLI MCP first (balanced speed/quality), API fallback
    "default":   ["gemini-cli", "MiniMax-M2.5", "qwen3.5-plus"],
}

# All known models for scoring
ALL_MODELS = sorted(MODEL_REGISTRY.keys())

# Minimum observations before trusting EvoMap data
MIN_OBSERVATIONS = 5

# Scoring weights
WEIGHT_SUCCESS_RATE = 0.4
WEIGHT_LATENCY = 0.3
WEIGHT_QUALITY = 0.2
WEIGHT_COST = 0.1


@dataclass
class ModelScore:
    """Scoring result for a single model."""
    model: str
    total_score: float = 0.0
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    quality_score: float = 0.0
    cost_efficiency: float = 0.0
    observations: int = 0
    source: str = "static"  # "static" | "evomap" | "fusion"
    provider_type: str = "api"  # ProviderType for the selected model

    def to_dict(self) -> dict:
        info = MODEL_REGISTRY.get(self.model)
        return {
            "model": self.model,
            "provider": self.provider_type,
            "score": round(self.total_score, 3),
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": int(self.avg_latency_ms),
            "quality": round(self.quality_score, 3),
            "cost_eff": round(self.cost_efficiency, 3),
            "obs": self.observations,
            "source": self.source,
        }


@dataclass
class RoutingDecision:
    """Complete routing decision with explanation."""
    task_type: str
    models: list[str]
    scores: list[ModelScore]
    source: str  # "static" | "evomap" | "fusion"
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "models": self.models,
            "scores": [s.to_dict() for s in self.scores],
            "source": self.source,
            "rationale": self.rationale,
        }


class ModelRouter:
    """Three-source fusion model router.

    Queries EvoMap for real-time performance data, Langfuse for quality
    metrics, and falls back to static rules when data is insufficient.

    Can be initialized from config::

        from chatgptrest.kernel.routing_config import load_routing_profile
        router = ModelRouter.from_config(load_routing_profile())
    """

    def __init__(
        self,
        *,
        evomap_observer: Any = None,
        langfuse_client: Any = None,
        static_routes: dict[str, list[str]] | None = None,
        lookback_hours: int = 24,
        model_registry: dict[str, ModelInfo] | None = None,
    ) -> None:
        self._observer = evomap_observer
        self._langfuse = langfuse_client
        self._static = static_routes or STATIC_ROUTES
        self._registry = model_registry or MODEL_REGISTRY
        self._lookback_hours = lookback_hours
        # Cache for Langfuse data (refreshed periodically)
        self._langfuse_cache: dict[str, dict] = {}
        self._langfuse_cache_time: float = 0
        self._langfuse_cache_ttl: float = 300  # 5 min

    @classmethod
    def from_config(
        cls,
        profile: Any,
        *,
        evomap_observer: Any = None,
        langfuse_client: Any = None,
        lookback_hours: int = 24,
    ) -> "ModelRouter":
        """Create a ModelRouter from a RoutingProfile.

        Extracts MODEL_REGISTRY and STATIC_ROUTES from the config,
        replacing the hardcoded defaults.
        """
        # Build model registry from config
        registry: dict[str, ModelInfo] = {}
        for name, mcfg in profile.models.items():
            registry[name] = ModelInfo(
                name=name,
                provider_type=mcfg.provider_type,
                display_name=mcfg.display_name,
                avg_latency_hint=mcfg.avg_latency_hint_ms,
                cost_hint=mcfg.cost_hint,
                quality_hint=mcfg.quality_hint,
                capabilities=list(mcfg.capabilities),
                invocation=mcfg.invocation,
            )

        # Build static routes from config
        static_routes = dict(profile.static_routes)

        return cls(
            evomap_observer=evomap_observer,
            langfuse_client=langfuse_client,
            static_routes=static_routes,
            lookback_hours=lookback_hours,
            model_registry=registry,
        )

    def select(
        self,
        task_type: str,
        *,
        trace_id: str = "",
        top_k: int = 3,
    ) -> RoutingDecision:
        """Select optimal models for a task type.

        Returns models ordered by score (best first), with fallback chain.
        """
        task_lower = task_type.lower() if task_type else "default"

        # Determine which static route key matches
        matched_key = "default"
        for key in self._static:
            if key in task_lower:
                matched_key = key
                break

        static_models = self._static.get(matched_key, self._static["default"])

        # Try to get EvoMap performance data
        evomap_stats = self._query_evomap_stats()

        # Try to get Langfuse quality data
        langfuse_stats = self._query_langfuse_stats()

        # Score all candidate models
        # Only include task-specific static models + any models with EvoMap/Langfuse data
        observed_models = set(evomap_stats.keys()) | set(langfuse_stats.keys())
        candidates = set(static_models) | observed_models
        scores = []
        has_data = False

        for model in candidates:
            score = self._score_model(
                model, matched_key, static_models,
                evomap_stats.get(model, {}),
                langfuse_stats.get(model, {}),
            )
            scores.append(score)
            if score.observations >= MIN_OBSERVATIONS:
                has_data = True

        # Sort by total_score descending
        scores.sort(key=lambda s: s.total_score, reverse=True)

        # Pick top-k models
        selected = [s.model for s in scores[:top_k]]
        source = "fusion" if has_data else "static"

        # Build rationale
        if has_data:
            top = scores[0]
            rationale = (
                f"Fusion routing: {top.model} scored {top.total_score:.2f} "
                f"(sr={top.success_rate:.0%}, lat={top.avg_latency_ms:.0f}ms, "
                f"q={top.quality_score:.2f}, obs={top.observations})"
            )
        else:
            rationale = f"Cold-start: using static route '{matched_key}'"

        decision = RoutingDecision(
            task_type=matched_key,
            models=selected,
            scores=scores[:top_k],
            source=source,
            rationale=rationale,
        )

        logger.info(
            "ModelRouter: task=%s → %s [%s] %s",
            matched_key, selected, source, rationale,
        )
        return decision

    def _score_model(
        self,
        model: str,
        task_key: str,
        static_order: list[str],
        evomap: dict,
        langfuse: dict,
    ) -> ModelScore:
        """Compute composite score for a model."""
        info = self._registry.get(model)
        score = ModelScore(model=model)
        score.provider_type = info.provider_type if info else ProviderType.API

        # ── Static position score (baseline) ──
        if model in static_order:
            pos = static_order.index(model)
            static_score = 1.0 - (pos / max(len(static_order), 1))
        else:
            # Check if model has the task_key as a capability
            if info and task_key in info.capabilities:
                static_score = 0.5  # capable but not preferred
            else:
                static_score = 0.2  # not suitable

        # ── EvoMap: success rate + latency ──
        evo_completed = evomap.get("completed", 0)
        evo_failed = evomap.get("failed", 0)
        evo_total = evo_completed + evo_failed
        score.observations = evo_total

        if evo_total >= MIN_OBSERVATIONS:
            # Success rate
            score.success_rate = evo_completed / evo_total
            # Latency (normalized: lower = better, cap at 60s for web models)
            avg_lat = evomap.get("avg_latency_ms", 3000)
            score.avg_latency_ms = avg_lat
            max_latency = max(60000 if score.provider_type in (ProviderType.WEB_CHATGPT, ProviderType.WEB_GEMINI) else 10000, 1)
            latency_score = max(0, 1.0 - (avg_lat / max_latency))
            score.source = "evomap"
        else:
            # Not enough data — use ModelInfo hints
            score.success_rate = info.quality_hint if info else 0.8
            score.avg_latency_ms = info.avg_latency_hint if info else 3000
            max_latency = max(60000 if score.provider_type in (ProviderType.WEB_CHATGPT, ProviderType.WEB_GEMINI) else 10000, 1)
            latency_score = max(0, 1.0 - (score.avg_latency_ms / max_latency))
            score.source = "static"

        # ── Langfuse: quality score ──
        lf_quality = langfuse.get("quality_score", None)
        if lf_quality is not None:
            score.quality_score = lf_quality
            score.source = "fusion"
        else:
            # Gate pass rate from EvoMap as proxy
            gate_passed = evomap.get("gate_passed", 0)
            gate_total = evomap.get("gate_total", 0)
            if gate_total > 0:
                score.quality_score = gate_passed / gate_total
            else:
                score.quality_score = 0.7  # default

        # ── Langfuse: cost efficiency ──
        lf_cost = langfuse.get("avg_cost_per_call", None)
        if lf_cost is not None and lf_cost > 0:
            # Lower cost = higher efficiency (normalize to 0-1)
            score.cost_efficiency = max(0, 1.0 - (lf_cost / 0.1))  # $0.10 as max
        else:
            score.cost_efficiency = 0.5  # neutral default

        # ── Composite score ──
        if evo_total >= MIN_OBSERVATIONS:
            score.total_score = (
                WEIGHT_SUCCESS_RATE * score.success_rate
                + WEIGHT_LATENCY * latency_score
                + WEIGHT_QUALITY * score.quality_score
                + WEIGHT_COST * score.cost_efficiency
            )
        else:
            # Cold start: rely on static position
            score.total_score = static_score * 0.8 + 0.2 * score.quality_score

        return score

    def _query_evomap_stats(self) -> dict[str, dict]:
        """Query EvoMap for per-model performance stats.

        Returns {model_name: {completed, failed, avg_latency_ms, gate_passed, gate_total}}
        """
        if not self._observer:
            return {}

        try:
            import datetime
            since = (
                datetime.datetime.now()
                - datetime.timedelta(hours=self._lookback_hours)
            ).isoformat()

            # Query LLM signals
            llm_signals = self._observer.query(
                domain="llm", since=since, limit=1000,
            )

            stats: dict[str, dict] = {}
            for s in llm_signals:
                model = s.data.get("model", "unknown")
                if model not in stats:
                    stats[model] = {
                        "completed": 0, "failed": 0,
                        "total_latency": 0, "avg_latency_ms": 0,
                        "gate_passed": 0, "gate_total": 0,
                    }

                if s.signal_type == "llm.call_completed":
                    stats[model]["completed"] += 1
                    stats[model]["total_latency"] += s.data.get("latency_ms", 0)
                elif s.signal_type == "llm.call_failed":
                    stats[model]["failed"] += 1

            # Calculate averages
            for model, st in stats.items():
                if st["completed"] > 0:
                    st["avg_latency_ms"] = st["total_latency"] / st["completed"]
                del st["total_latency"]

            # Also query gate signals for quality proxy
            gate_signals = self._observer.query(
                domain="gate", since=since, limit=500,
            )
            # Gate signals don't carry per-model info, so we apply
            # them as a global quality proxy across all tracked models.
            # TODO: Enhance gate signals to include the specific model used.
            for s in gate_signals:
                # BUG-5 fix: only apply gate signal to the specific model that generated it
                model_id = getattr(s, "data", {}).get("model", "") if hasattr(s, "data") else ""
                if model_id and model_id in stats:
                    if s.signal_type == "gate.passed":
                        stats[model_id]["gate_passed"] += 1
                        stats[model_id]["gate_total"] += 1
                    elif s.signal_type == "gate.failed":
                        stats[model_id]["gate_total"] += 1
                else:
                    # Legacy signals without model info — log but don't pollute all models
                    logger.debug("Gate signal without model info: %s", s.signal_type)

            return stats

        except Exception as e:
            logger.warning("EvoMap query failed: %s", e)
            return {}

    def _query_langfuse_stats(self) -> dict[str, dict]:
        """Query Langfuse for quality and cost metrics.

        Returns {model_name: {quality_score, avg_cost_per_call}}
        Cached for 5 minutes to avoid excessive API calls.
        """
        if not self._langfuse:
            return {}

        # Check cache
        now = time.time()
        if now - self._langfuse_cache_time < self._langfuse_cache_ttl:
            return self._langfuse_cache

        try:
            # Fetch recent traces
            traces_response = self._langfuse.api.trace.list(limit=100)
            traces = traces_response.data if hasattr(traces_response, 'data') else (
                traces_response if isinstance(traces_response, list) else []
            )

            stats: dict[str, dict] = {}
            for t in traces:
                meta = t.metadata or {} if hasattr(t, 'metadata') else {}
                model = meta.get("model", meta.get("provider", ""))
                if not model:
                    continue

                if model not in stats:
                    stats[model] = {
                        "total_quality": 0, "quality_count": 0,
                        "total_cost": 0, "cost_count": 0,
                    }

                # Quality from scores
                if hasattr(t, 'scores') and t.scores:
                    for score in t.scores:
                        if hasattr(score, 'value') and score.value is not None:
                            stats[model]["total_quality"] += score.value
                            stats[model]["quality_count"] += 1

                # Cost from usage
                if hasattr(t, 'total_cost') and t.total_cost:
                    stats[model]["total_cost"] += t.total_cost
                    stats[model]["cost_count"] += 1

            # Calculate averages
            result_stats: dict[str, dict] = {}
            for model, st in stats.items():
                result_stats[model] = {}
                if st["quality_count"] > 0:
                    result_stats[model]["quality_score"] = (
                        st["total_quality"] / st["quality_count"]
                    )
                if st["cost_count"] > 0:
                    result_stats[model]["avg_cost_per_call"] = (
                        st["total_cost"] / st["cost_count"]
                    )

            self._langfuse_cache = result_stats
            self._langfuse_cache_time = now
            return result_stats

        except Exception as e:
            logger.warning("Langfuse query failed: %s", e)
            return self._langfuse_cache  # return stale cache on error

    # ── Langfuse Score Writeback ──────────────────────────────────

    def write_quality_score(
        self, trace_id: str, score: float, comment: str = "",
    ) -> None:
        """Write quality score back to Langfuse for a trace.

        Called when gate.passed/failed signals are emitted.
        score: 0.0 (failed) to 1.0 (passed)
        """
        if not self._langfuse:
            return
        try:
            self._langfuse.create_score(
                trace_id=trace_id,
                name="gate_quality",
                value=score,
                comment=comment or f"Auto-scored: {'pass' if score > 0.5 else 'fail'}",
            )
            logger.debug("Langfuse score written: trace=%s score=%.1f", trace_id, score)
        except Exception as e:
            logger.warning("Langfuse score write failed: %s", e)
