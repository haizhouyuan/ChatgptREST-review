"""Runtime Allocator MVP - Deterministic routing + quota tracking.

Routes tasks to optimal runtime based on capability matching, quota,
and risk policy. Core logic is pure Python — no LLM calls.

Usage:
    from runtime_allocator.allocator_mvp import allocate, RouteRequest
    decision = allocate(RouteRequest(task_class="finbot_news", ...))
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional


# ── Enums ──────────────────────────────────────────────────────────────────

class PrivacyTier(str, Enum):
    LOCAL = "local"
    PRIVATE_CLOUD = "private_cloud"
    EXTERNAL_CLOUD = "external_cloud"


class QualityTier(str, Enum):
    CHEAP = "cheap"
    STANDARD = "standard"
    HIGH = "high"
    CRITICAL = "critical"


class TaskClass(str, Enum):
    # Finbot
    FINBOT_NEWS = "finbot_news"
    FINBOT_FUNDAMENTAL = "finbot_fundamental"
    FINBOT_TECHNICAL = "finbot_technical"
    FINBOT_DEBATE = "finbot_debate"
    FINBOT_TRADE_PROPOSAL = "finbot_trade_proposal"
    FINBOT_RISK_VETO = "finbot_risk_veto"
    # Planning
    STRATEGY_BRIEF = "strategy_brief"
    STRATEGIC_PLAN = "strategic_plan"
    HR_SENSITIVE = "hr_sensitive"
    HR_SENSITIVE_REVIEW = "hr_sensitive_review"
    MEETING_SUMMARY = "meeting_summary"
    MEETING_EXTRACTION = "meeting_extraction"
    DOCUMENT_DRAFT = "document_draft"
    DECISION_MEMO = "decision_memo"
    # Labebe
    LABEBE_PRODUCT_EVAL = "labebe_product_eval"
    LABEBE_CONTENT_GEN = "labebe_content_gen"
    LABEBE_REVIEW_ANALYSIS = "labebe_review_analysis"
    # Memory
    MEMORY_INDEXING = "memory_indexing"
    MEMORY_BENCHMARK = "memory_benchmark"
    MEMORY_COMPARISON = "memory_comparison"
    MEMORY_RECOMMENDATION = "memory_recommendation"
    # LLM Research
    LLM_RESEARCH_EVAL = "llm_research_eval"
    LLM_RESEARCH_BENCHMARK = "llm_research_benchmark"
    # General
    FRONTEND = "frontend"
    CODE_REASONING = "code_reasoning"
    BENCHMARK = "benchmark"


# ── Data models ────────────────────────────────────────────────────────────

@dataclass
class Runtime:
    provider_id: str
    model_name: str
    endpoint: str
    privacy_tier: PrivacyTier
    quality_tier: QualityTier
    supports_tools: bool = True
    supports_json: bool = True
    max_context_tokens: int = 128000
    cost_per_mtok_in: float = 0.0
    cost_per_mtok_out: float = 0.0
    latency_p50_ms: int = 2000
    enabled: bool = True


@dataclass
class RouteRequest:
    task_class: str
    privacy_tier_required: PrivacyTier = PrivacyTier.EXTERNAL_CLOUD
    min_quality_tier: QualityTier = QualityTier.STANDARD
    needs_tool_calling: bool = False
    needs_json: bool = True
    input_tokens_est: int = 2000
    output_tokens_est: int = 1000
    can_degrade: bool = True
    high_stakes: bool = False


@dataclass
class RouteDecision:
    provider_id: str
    model_name: str
    endpoint: str
    reservation_id: str
    fallback_chain: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    requires_human_review: bool = False
    blocked: bool = False


# ── Quota ledger (JSON file-backed) ────────────────────────────────────────

class QuotaLedger:
    """Simple file-backed quota tracker. Tracks requests per day per provider."""

    def __init__(self, path: str = None):
        self.path = Path(path or os.path.expanduser("~/.paperclip/runtime_quota_ledger.json"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self):
        self.path.write_text(json.dumps(self._data, indent=2))

    def _today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def get_used(self, provider_id: str, dimension: str = "rpd") -> int:
        today = self._today()
        return self._data.get(today, {}).get(provider_id, {}).get(dimension, 0)

    def reserve(self, provider_id: str, dimension: str = "rpd", amount: int = 1) -> str:
        today = self._today()
        if today not in self._data:
            self._data[today] = {}
        if provider_id not in self._data[today]:
            self._data[today][provider_id] = {"rpd": 0, "tpm": 0}
        self._data[today][provider_id][dimension] = (
            self._data[today][provider_id].get(dimension, 0) + amount
        )
        reservation_id = str(uuid.uuid4())[:8]
        self._save()
        return reservation_id

    def can_reserve(self, provider_id: str, rpd_limit: int = 1000, tpm_limit: int = 60) -> bool:
        if self.is_cooling_down(provider_id):
            return False
        today = self._today()
        used = self._data.get(today, {}).get(provider_id, {})
        return used.get("rpd", 0) < rpd_limit and used.get("tpm", 0) < tpm_limit

    # ── Cooldown management ──────────────────────────────────────────────────

    def set_cooldown(
        self,
        provider_id: str,
        reason: str,
        ttl_seconds: int,
        dimension: str = "provider",
    ) -> None:
        """Put a provider into cooldown for ttl_seconds."""
        now = datetime.now()
        until = now + timedelta(seconds=ttl_seconds)
        today = self._today()

        self._data.setdefault(today, {})
        self._data[today].setdefault("_cooldowns", {})
        self._data[today]["_cooldowns"][f"{dimension}:{provider_id}"] = {
            "until": until.isoformat(),
            "reason": reason,
            "set_at": now.isoformat(),
        }
        self._save()

    def get_cooldown(
        self,
        provider_id: str,
        dimension: str = "provider",
    ) -> Optional[dict]:
        """Get cooldown info for a provider, or None if not cooling down."""
        today = self._today()
        key = f"{dimension}:{provider_id}"
        entry = self._data.get(today, {}).get("_cooldowns", {}).get(key)
        if not entry:
            return None

        try:
            until = datetime.fromisoformat(entry["until"])
        except Exception:
            return None

        if until <= datetime.now():
            return None

        return entry

    def is_cooling_down(
        self,
        provider_id: str,
        dimension: str = "provider",
    ) -> bool:
        """Check if a provider is currently in cooldown."""
        return self.get_cooldown(provider_id, dimension=dimension) is not None


def cooldown_ttl_for_error(error_class: str | None, error: str | None) -> tuple[str, int] | None:
    """Classify an error and return (reason, ttl_seconds) for cooldown, or None."""
    text = f"{error_class or ''} {error or ''}".lower()

    if "429" in text or "rate limit" in text or "too many" in text:
        return "rate_limit", 3600

    if "connection refused" in text or "connectionerror" in text or "timeout" in text:
        return "endpoint_unavailable", 900

    if "unauthorized" in text or "invalid api key" in text or "authentication" in text:
        return "auth_error", 86400

    return None


# ── Quality scoring ────────────────────────────────────────────────────────

_QUALITY_RANK = {QualityTier.CHEAP: 0, QualityTier.STANDARD: 1, QualityTier.HIGH: 2, QualityTier.CRITICAL: 3}
_PRIVACY_RANK = {PrivacyTier.LOCAL: 0, PrivacyTier.PRIVATE_CLOUD: 1, PrivacyTier.EXTERNAL_CLOUD: 2}

# Task-specific quality requirements
_TASK_QUALITY = {
    # Finbot
    TaskClass.FINBOT_RISK_VETO.value: QualityTier.CRITICAL,
    TaskClass.FINBOT_DEBATE.value: QualityTier.HIGH,
    TaskClass.FINBOT_TRADE_PROPOSAL.value: QualityTier.HIGH,
    TaskClass.FINBOT_NEWS.value: QualityTier.STANDARD,
    TaskClass.FINBOT_FUNDAMENTAL.value: QualityTier.HIGH,
    TaskClass.FINBOT_TECHNICAL.value: QualityTier.STANDARD,
    # Planning
    TaskClass.STRATEGY_BRIEF.value: QualityTier.HIGH,
    TaskClass.STRATEGIC_PLAN.value: QualityTier.HIGH,
    TaskClass.HR_SENSITIVE.value: QualityTier.STANDARD,
    TaskClass.HR_SENSITIVE_REVIEW.value: QualityTier.STANDARD,
    TaskClass.MEETING_SUMMARY.value: QualityTier.STANDARD,
    TaskClass.MEETING_EXTRACTION.value: QualityTier.STANDARD,
    TaskClass.DOCUMENT_DRAFT.value: QualityTier.STANDARD,
    TaskClass.DECISION_MEMO.value: QualityTier.STANDARD,
    # Labebe
    TaskClass.LABEBE_PRODUCT_EVAL.value: QualityTier.STANDARD,
    TaskClass.LABEBE_CONTENT_GEN.value: QualityTier.STANDARD,
    TaskClass.LABEBE_REVIEW_ANALYSIS.value: QualityTier.STANDARD,
    # Memory
    TaskClass.MEMORY_INDEXING.value: QualityTier.STANDARD,
    TaskClass.MEMORY_BENCHMARK.value: QualityTier.CHEAP,
    TaskClass.MEMORY_COMPARISON.value: QualityTier.HIGH,
    TaskClass.MEMORY_RECOMMENDATION.value: QualityTier.HIGH,
    # LLM Research
    TaskClass.LLM_RESEARCH_EVAL.value: QualityTier.HIGH,
    TaskClass.LLM_RESEARCH_BENCHMARK.value: QualityTier.CHEAP,
    # General
    TaskClass.CODE_REASONING.value: QualityTier.HIGH,
    TaskClass.BENCHMARK.value: QualityTier.CHEAP,
}

# Runtime quality scores per task class (0-1 scale)
_RUNTIME_TASK_SCORES = {
    # claudekimi
    ("claudekimi", "finbot_risk_veto"): 0.95,
    ("claudekimi", "finbot_debate"): 0.90,
    ("claudekimi", "finbot_fundamental"): 0.90,
    ("claudekimi", "finbot_trade_proposal"): 0.85,
    ("claudekimi", "code_reasoning"): 0.90,
    ("claudekimi", "strategy_brief"): 0.85,
    ("claudekimi", "strategic_plan"): 0.85,
    ("claudekimi", "llm_research_eval"): 0.90,
    ("claudekimi", "memory_comparison"): 0.85,
    ("claudekimi", "memory_recommendation"): 0.85,
    ("claudekimi", "document_draft"): 0.75,
    ("claudekimi", "memory_indexing"): 0.70,
    # minimax
    ("minimax", "finbot_news"): 0.75,
    ("minimax", "finbot_technical"): 0.70,
    ("minimax", "finbot_fundamental"): 0.65,
    ("minimax", "document_draft"): 0.70,
    ("minimax", "meeting_summary"): 0.70,
    ("minimax", "labebe_product_eval"): 0.70,
    ("minimax", "labebe_content_gen"): 0.75,
    ("minimax", "labebe_review_analysis"): 0.70,
    ("minimax", "decision_memo"): 0.70,
    ("minimax", "meeting_extraction"): 0.70,
    # gemini_local
    ("gemini_local", "frontend"): 0.85,
    ("gemini_local", "finbot_news"): 0.80,
    ("gemini_local", "document_draft"): 0.80,
    ("gemini_local", "meeting_summary"): 0.85,
    ("gemini_local", "strategy_brief"): 0.75,
    ("gemini_local", "labebe_content_gen"): 0.80,
    ("gemini_local", "memory_comparison"): 0.75,
    # ollama_gpu0
    ("ollama_gpu0", "memory_indexing"): 0.80,
    ("ollama_gpu0", "memory_benchmark"): 0.80,
    ("ollama_gpu0", "benchmark"): 0.75,
    ("ollama_gpu0", "hr_sensitive"): 0.70,
    ("ollama_gpu0", "hr_sensitive_review"): 0.70,
    ("ollama_gpu0", "llm_research_benchmark"): 0.75,
}


def _quality_score(rt: Runtime, task_class: str) -> float:
    key = (rt.provider_id, task_class)
    return _RUNTIME_TASK_SCORES.get(key, 0.5)


# ── Policy filters ─────────────────────────────────────────────────────────

def _apply_policy_filters(candidates: list[Runtime], req: RouteRequest) -> list[Runtime]:
    """Apply hard policy filters based on task class."""
    # Determine effective minimum quality tier: max of request min and task-specific requirement.
    task_required = _TASK_QUALITY.get(req.task_class)
    if task_required is not None:
        effective_min = max(_QUALITY_RANK[req.min_quality_tier], _QUALITY_RANK[task_required])
    else:
        effective_min = _QUALITY_RANK[req.min_quality_tier]

    filtered = []
    for rt in candidates:
        # Privacy filter
        if _PRIVACY_RANK[rt.privacy_tier] > _PRIVACY_RANK[req.privacy_tier_required]:
            continue
        # Quality tier hard gate — cheap models must not win high-stakes tasks.
        if _QUALITY_RANK[rt.quality_tier] < effective_min:
            continue
        # Tool calling filter
        if req.needs_tool_calling and not rt.supports_tools:
            continue
        # JSON support filter
        if req.needs_json and not rt.supports_json:
            continue
        # Context window filter
        total_tokens = req.input_tokens_est + req.output_tokens_est
        if rt.max_context_tokens < total_tokens:
            continue
        filtered.append(rt)

    # Task-specific policy
    if req.task_class == TaskClass.FINBOT_RISK_VETO.value:
        filtered = [r for r in filtered if r.quality_tier == QualityTier.CRITICAL]
        req.can_degrade = False

    if req.task_class == TaskClass.HR_SENSITIVE.value:
        filtered = [r for r in filtered if r.privacy_tier in (PrivacyTier.LOCAL, PrivacyTier.PRIVATE_CLOUD)]

    return filtered


# ── Main allocation function ───────────────────────────────────────────────

def allocate(
    req: RouteRequest,
    runtimes: list[Runtime] = None,
    ledger: QuotaLedger = None,
) -> RouteDecision:
    """Route a task to the best available runtime."""

    if runtimes is None:
        runtimes = _default_runtimes()
    if ledger is None:
        ledger = QuotaLedger()

    # 1. Filter enabled + policy
    candidates = [r for r in runtimes if r.enabled]
    candidates = _apply_policy_filters(candidates, req)

    # 2. Quota preflight
    candidates = [
        r for r in candidates
        if ledger.can_reserve(r.provider_id)
    ]

    if not candidates:
        if req.can_degrade:
            # Try again with relaxed quality
            req.min_quality_tier = QualityTier.CHEAP
            candidates = [r for r in runtimes if r.enabled]
            candidates = _apply_policy_filters(candidates, req)
            candidates = [r for r in candidates if ledger.can_reserve(r.provider_id)]

        if not candidates:
            return RouteDecision(
                provider_id="blocked",
                model_name="none",
                endpoint="",
                reservation_id="",
                blocked=True,
                reason_codes=["no_available_runtime", "quota_exhausted"],
            )

    # 3. Score and select
    scored = []
    for rt in candidates:
        score = (
            4.0 * _quality_score(rt, req.task_class)
            - 1.5 * (rt.cost_per_mtok_in + rt.cost_per_mtok_out) / 10.0
            - 1.0 * rt.latency_p50_ms / 10000.0
        )
        scored.append((score, rt))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = scored[0][1]

    # 4. Reserve quota
    reservation_id = ledger.reserve(selected.provider_id)

    # 5. Build fallback chain
    fallback_chain = [s[1].provider_id for s in scored[1:4]]

    # 6. Reason codes
    reason_codes = [f"quality_score={scored[0][0]:.2f}"]
    if req.high_stakes and selected.quality_tier != QualityTier.CRITICAL:
        reason_codes.append("high_stakes_non_critical_runtime")

    return RouteDecision(
        provider_id=selected.provider_id,
        model_name=selected.model_name,
        endpoint=selected.endpoint,
        reservation_id=reservation_id,
        fallback_chain=fallback_chain,
        reason_codes=reason_codes,
        requires_human_review=req.high_stakes and selected.quality_tier != QualityTier.CRITICAL,
    )


# ── Env var resolution + YAML loading ──────────────────────────────────────

_PROFILES_YAML = Path(__file__).parent / "profiles" / "runtime_profiles.yaml"


def _resolve_env(template: str) -> str:
    """Resolve ${VAR:default} patterns in endpoint strings."""
    if "${" not in template:
        return template

    def _replace(m):
        var_spec = m.group(1)
        if ":" in var_spec:
            var_name, default = var_spec.split(":", 1)
        else:
            var_name, default = var_spec, ""
        return os.getenv(var_name, default)

    return re.sub(r"\$\{([^}]+)\}", _replace, template)


def _default_runtimes() -> list[Runtime]:
    """Load configured runtimes from YAML profiles, with env var resolution."""
    try:
        import yaml as _yaml
    except ImportError:
        return _hardcoded_runtimes()

    yaml_path = _PROFILES_YAML
    if not yaml_path.exists():
        return _hardcoded_runtimes()

    try:
        with open(yaml_path) as f:
            data = _yaml.safe_load(f)
    except Exception:
        return _hardcoded_runtimes()

    runtimes = []
    for pid, rt in data.get("runtimes", {}).items():
        if not rt.get("enabled", True):
            continue
        runtimes.append(Runtime(
            provider_id=pid,
            model_name=rt.get("model_name", ""),
            endpoint=_resolve_env(rt.get("endpoint", "")),
            privacy_tier=PrivacyTier(rt.get("privacy_tier", "external_cloud")),
            quality_tier=QualityTier(rt.get("quality_tier", "standard")),
            supports_tools=rt.get("supports_tools", False),
            supports_json=rt.get("supports_json", True),
            max_context_tokens=rt.get("max_context_tokens", 128000),
            cost_per_mtok_in=rt.get("cost_per_mtok_in", 0.0),
            cost_per_mtok_out=rt.get("cost_per_mtok_out", 0.0),
            latency_p50_ms=rt.get("latency_p50_ms", 2000),
            enabled=rt.get("enabled", True),
        ))

    return runtimes if runtimes else _hardcoded_runtimes()


def _hardcoded_runtimes() -> list[Runtime]:
    """Fallback: hardcoded runtimes if YAML loading fails."""
    return [
        Runtime(
            provider_id="claudekimi",
            model_name="mimo-v2.5-pro",
            endpoint=os.getenv("CLAUDEKIMI_ENDPOINT", "http://127.0.0.1:8080/v1"),
            privacy_tier=PrivacyTier.EXTERNAL_CLOUD,
            quality_tier=QualityTier.CRITICAL,
            cost_per_mtok_in=3.0,
            cost_per_mtok_out=15.0,
            latency_p50_ms=3000,
        ),
        Runtime(
            provider_id="minimax",
            model_name="MiniMax-M2.7-highspeed",
            endpoint=os.getenv("MINIMAX_API_HOST", "https://api.minimaxi.com") + "/v1",
            privacy_tier=PrivacyTier.EXTERNAL_CLOUD,
            quality_tier=QualityTier.STANDARD,
            cost_per_mtok_in=0.5,
            cost_per_mtok_out=2.0,
            latency_p50_ms=1500,
        ),
        Runtime(
            provider_id="gemini_local",
            model_name="gemini-2.5-pro",
            endpoint="gemini-cli",
            privacy_tier=PrivacyTier.EXTERNAL_CLOUD,
            quality_tier=QualityTier.HIGH,
            supports_tools=False,
            cost_per_mtok_in=0.0,
            cost_per_mtok_out=0.0,
            latency_p50_ms=2500,
        ),
        Runtime(
            provider_id="ollama_gpu0",
            model_name="qwen2.5:32b",
            endpoint="http://localhost:11434/v1",
            privacy_tier=PrivacyTier.LOCAL,
            quality_tier=QualityTier.STANDARD,
            supports_tools=False,
            cost_per_mtok_in=0.0,
            cost_per_mtok_out=0.0,
            latency_p50_ms=5000,
        ),
    ]


# ── CLI entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    task_class = sys.argv[1] if len(sys.argv) > 1 else "finbot_news"
    req = RouteRequest(task_class=task_class)
    decision = allocate(req)
    print(json.dumps(asdict(decision), indent=2))
