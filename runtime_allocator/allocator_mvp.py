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
    FINBOT_NEWS = "finbot_news"
    FINBOT_FUNDAMENTAL = "finbot_fundamental"
    FINBOT_TECHNICAL = "finbot_technical"
    FINBOT_DEBATE = "finbot_debate"
    FINBOT_TRADE_PROPOSAL = "finbot_trade_proposal"
    FINBOT_RISK_VETO = "finbot_risk_veto"
    FRONTEND = "frontend"
    CODE_REASONING = "code_reasoning"
    MEETING_SUMMARY = "meeting_summary"
    HR_SENSITIVE = "hr_sensitive"
    DOCUMENT_DRAFT = "document_draft"
    MEMORY_INDEXING = "memory_indexing"
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
        today = self._today()
        used = self._data.get(today, {}).get(provider_id, {})
        return used.get("rpd", 0) < rpd_limit and used.get("tpm", 0) < tpm_limit


# ── Quality scoring ────────────────────────────────────────────────────────

_QUALITY_RANK = {QualityTier.CHEAP: 0, QualityTier.STANDARD: 1, QualityTier.HIGH: 2, QualityTier.CRITICAL: 3}
_PRIVACY_RANK = {PrivacyTier.LOCAL: 0, PrivacyTier.PRIVATE_CLOUD: 1, PrivacyTier.EXTERNAL_CLOUD: 2}

# Task-specific quality requirements
_TASK_QUALITY = {
    TaskClass.FINBOT_RISK_VETO.value: QualityTier.CRITICAL,
    TaskClass.FINBOT_DEBATE.value: QualityTier.HIGH,
    TaskClass.FINBOT_TRADE_PROPOSAL.value: QualityTier.HIGH,
    TaskClass.FINBOT_NEWS.value: QualityTier.STANDARD,
    TaskClass.FINBOT_FUNDAMENTAL.value: QualityTier.HIGH,
    TaskClass.FINBOT_TECHNICAL.value: QualityTier.STANDARD,
    TaskClass.CODE_REASONING.value: QualityTier.HIGH,
    TaskClass.HR_SENSITIVE.value: QualityTier.STANDARD,
    TaskClass.BENCHMARK.value: QualityTier.CHEAP,
}

# Runtime quality scores per task class (0-1 scale)
_RUNTIME_TASK_SCORES = {
    ("claudekimi", "finbot_risk_veto"): 0.95,
    ("claudekimi", "finbot_debate"): 0.90,
    ("claudekimi", "finbot_fundamental"): 0.90,
    ("claudekimi", "finbot_trade_proposal"): 0.85,
    ("claudekimi", "code_reasoning"): 0.90,
    ("minimax", "finbot_news"): 0.75,
    ("minimax", "finbot_technical"): 0.70,
    ("minimax", "finbot_fundamental"): 0.65,
    ("minimax", "document_draft"): 0.70,
    ("minimax", "meeting_summary"): 0.70,
    ("gemini_local", "frontend"): 0.85,
    ("gemini_local", "finbot_news"): 0.80,
    ("gemini_local", "document_draft"): 0.80,
    ("gemini_local", "meeting_summary"): 0.85,
    ("ollama_gpu0", "memory_indexing"): 0.80,
    ("ollama_gpu0", "benchmark"): 0.75,
    ("ollama_gpu0", "hr_sensitive"): 0.70,
}


def _quality_score(rt: Runtime, task_class: str) -> float:
    key = (rt.provider_id, task_class)
    return _RUNTIME_TASK_SCORES.get(key, 0.5)


# ── Policy filters ─────────────────────────────────────────────────────────

def _apply_policy_filters(candidates: list[Runtime], req: RouteRequest) -> list[Runtime]:
    """Apply hard policy filters based on task class."""
    filtered = []
    for rt in candidates:
        # Privacy filter
        if _PRIVACY_RANK[rt.privacy_tier] > _PRIVACY_RANK[req.privacy_tier_required]:
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


# ── Default runtimes ───────────────────────────────────────────────────────

def _default_runtimes() -> list[Runtime]:
    """Return the configured runtimes from environment / defaults."""
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
