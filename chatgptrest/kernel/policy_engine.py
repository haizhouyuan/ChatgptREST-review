"""Policy engine with pluggable quality-gate checker chain.

Adapted from planning/aios kernel for ChatgptREST.

Provides:
  - PII / sensitive-data detection (fail-closed for unknown labels)
  - Cost / token budget enforcement
  - Security label × audience delivery constraints
  - Execution / business dual-success semantics
  - Claim-evidence gating for external outputs
  - Composable quality gate that aggregates all checkers
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol, Union


# ── Data types ────────────────────────────────────────────────────

@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    conditions: list[str] = field(default_factory=list)


@dataclass
class QualityContext:
    """Input context passed through quality checkers."""
    audience: str
    security_label: str
    content: Union[str, bytes]
    estimated_tokens: int = 0
    channel: str = "default"
    risk_level: str = "low"
    execution_success: bool = True
    business_success: bool = True
    claims: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class QualityGateResult:
    allowed: bool
    reason: str
    decisions: dict[str, PolicyDecision] = field(default_factory=dict)
    blocked_by: list[str] = field(default_factory=list)
    requires_human_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "blocked_by": self.blocked_by,
            "requires_human_review": self.requires_human_review,
            "decisions": {
                name: {"allowed": d.allowed, "reason": d.reason, "conditions": list(d.conditions)}
                for name, d in self.decisions.items()
            },
        }


# ── Checker protocol ─────────────────────────────────────────────

class QualityChecker(Protocol):
    name: str

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision: ...


# ── Built-in checkers ─────────────────────────────────────────────

class StructureChecker:
    name = "structure"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        content = context.content
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")
        if not str(content).strip():
            return PolicyDecision(allowed=False, reason="Empty content", conditions=["requires_human_review"])
        return PolicyDecision(allowed=True, reason="Structure OK")


class ExecutionBusinessChecker:
    name = "execution_business"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        return engine.check_execution_business(
            execution_success=context.execution_success,
            business_success=context.business_success,
            audience=context.audience,
        )


class DeliveryChecker:
    name = "delivery"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        return engine.check_delivery_label(context.security_label, context.audience)


class CostChecker:
    name = "cost"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        return engine.check_cost(context.estimated_tokens, context.channel)


class SecurityChecker:
    name = "security"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        if context.security_label not in engine.ALLOWED_LABELS:
            return PolicyDecision(
                allowed=False,
                reason=f"Unknown security_label '{context.security_label}'",
                conditions=["requires_human_review"],
            )
        return engine.check_security(context.content, context.security_label)


class ClaimEvidenceChecker:
    name = "claim_evidence"

    def check(self, *, engine: PolicyEngine, context: QualityContext) -> PolicyDecision:
        return engine.check_claim_evidence(context.claims, context.audience, context.risk_level)


# ── Policy engine ─────────────────────────────────────────────────

class PolicyEngine:
    """Policy engine with fail-closed defaults."""

    ALLOWED_LABELS = {"public", "internal", "confidential"}

    SENSITIVE_PATTERNS = {
        "path": re.compile(
            r"(?:[A-Za-z]:\\(?:[^\\\/:*?\"<>|\r\n]+\\?)+|/(?:home|Users|tmp|var|etc|opt|vol\d+)(?:/[^\\\/:*?\"<>|\r\n]+)+)"
        ),
        "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "phone_cn": re.compile(r"\b1[3-9]\d{9}\b"),
        "phone_us": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        "id_card_cn": re.compile(
            r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"
        ),
        "credit_card": re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"),
        "api_key": re.compile(
            r'(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token)\s*[:=]\s*["\']?[\w-]{20,}["\']?',
            re.IGNORECASE,
        ),
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.max_tokens_per_task = self.config.get("max_tokens_per_task", 100_000)
        self.max_cost_per_task = self.config.get("max_cost_per_task", 10.0)
        self.confidential_allowed_audiences = self.config.get(
            "confidential_allowed_audiences", ["internal", "admin"]
        )
        self.sensitive_patterns_enabled = self.config.get("sensitive_patterns_enabled", True)

    # ── Individual checks ─────────────────────────────────────────

    def check_delivery_label(self, security_label: str, audience: str) -> PolicyDecision:
        # Fail-closed: unknown labels are blocked
        if security_label not in self.ALLOWED_LABELS:
            return PolicyDecision(
                allowed=False,
                reason=f"Unknown security_label '{security_label}' — fail-closed",
                conditions=["requires_human_review"],
            )
        if security_label == "confidential":
            if audience == "external":
                return PolicyDecision(
                    allowed=False,
                    reason="Confidential → external blocked (fail-closed)",
                    conditions=["requires_human_review"],
                )
            if audience not in self.confidential_allowed_audiences:
                return PolicyDecision(allowed=False, reason=f"Confidential → {audience} blocked")
        if security_label == "internal" and audience == "external":
            return PolicyDecision(allowed=False, reason="Internal → external blocked")
        return PolicyDecision(allowed=True, reason="Delivery allowed")

    def check_cost(self, estimated_tokens: int, channel: str) -> PolicyDecision:
        if estimated_tokens > self.max_tokens_per_task:
            return PolicyDecision(
                allowed=False,
                reason=f"Tokens {estimated_tokens} > limit {self.max_tokens_per_task}",
                conditions=["reduce_scope"],
            )
        channel_limits = self.config.get("channel_limits", {})
        if channel in channel_limits and estimated_tokens > channel_limits[channel]:
            return PolicyDecision(allowed=False, reason=f"Channel {channel} limit exceeded")
        cost_per_1k = self.config.get("cost_per_1k_tokens", 0.01)
        estimated_cost = (estimated_tokens / 1000) * cost_per_1k
        if estimated_cost > self.max_cost_per_task:
            return PolicyDecision(allowed=False, reason=f"Cost ${estimated_cost:.2f} > ${self.max_cost_per_task}")
        return PolicyDecision(allowed=True, reason="Cost OK")

    def check_security(self, content: Union[str, bytes], security_label: str) -> PolicyDecision:
        if security_label not in self.ALLOWED_LABELS:
            return PolicyDecision(
                allowed=False,
                reason=f"Unknown label '{security_label}'",
                conditions=["requires_human_review"],
            )
        if not self.sensitive_patterns_enabled:
            return PolicyDecision(allowed=True, reason="Security disabled")
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")
        detected = []
        for name, pat in self.SENSITIVE_PATTERNS.items():
            matches = pat.findall(content)
            if matches:
                detected.append(f"{name}:{len(matches)}")
        if detected:
            return PolicyDecision(
                allowed=False,
                reason=f"Sensitive data: {', '.join(detected)}",
                conditions=["pii_redaction_required", "requires_human_review"],
            )
        return PolicyDecision(allowed=True, reason="Security OK")

    def check_execution_business(
        self, execution_success: bool, business_success: bool, audience: str
    ) -> PolicyDecision:
        if not execution_success:
            return PolicyDecision(allowed=False, reason="Execution failed", conditions=["requires_human_review"])
        if not business_success:
            if audience == "external":
                return PolicyDecision(
                    allowed=False,
                    reason="business_success=False blocked for external",
                    conditions=["requires_human_review"],
                )
            return PolicyDecision(allowed=True, reason="business_success=False (internal ok)", conditions=["requires_attention"])
        return PolicyDecision(allowed=True, reason="Exec/business OK")

    def check_claim_evidence(
        self, claims: list[dict[str, Any]], audience: str, risk_level: str
    ) -> PolicyDecision:
        strict = audience == "external" or risk_level == "high"
        if not strict:
            return PolicyDecision(allowed=True, reason="Claim check skipped (non-strict)")
        if not claims:
            return PolicyDecision(
                allowed=False,
                reason="Missing claims for external/high-risk output",
                conditions=["requires_human_review"],
            )
        for i, claim in enumerate(claims):
            refs = claim.get("evidence_refs")
            has_refs = isinstance(refs, list) and len(refs) > 0
            if not has_refs:
                reason = f"Claim[{i}] missing evidence_refs"
                if claim.get("quote"):
                    reason = f"Quote-only claim[{i}] without evidence"
                return PolicyDecision(allowed=False, reason=reason, conditions=["requires_human_review"])
        return PolicyDecision(allowed=True, reason="Claims OK")

    # ── Quality gate ──────────────────────────────────────────────

    def default_checkers(self) -> list[QualityChecker]:
        return [
            StructureChecker(),
            ExecutionBusinessChecker(),
            DeliveryChecker(),
            CostChecker(),
            SecurityChecker(),
            ClaimEvidenceChecker(),
        ]

    def run_quality_gate(
        self,
        context: QualityContext,
        checkers: list[QualityChecker] | None = None,
    ) -> QualityGateResult:
        decisions: dict[str, PolicyDecision] = {}
        blocked_by: list[str] = []
        requires_human = False

        for checker in (checkers or self.default_checkers()):
            d = checker.check(engine=self, context=context)
            decisions[checker.name] = d
            if not d.allowed:
                blocked_by.append(checker.name)
            if "requires_human_review" in d.conditions:
                requires_human = True

        allowed = all(d.allowed for d in decisions.values())
        if not allowed:
            requires_human = True
        return QualityGateResult(
            allowed=allowed,
            reason="Quality gate passed" if allowed else f"Blocked by: {', '.join(blocked_by)}",
            decisions=decisions,
            blocked_by=blocked_by,
            requires_human_review=requires_human,
        )
