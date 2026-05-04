"""Paperclip Skill Agent - Runtime Control Plane.

The single entry point all orchestrators call instead of managing providers directly.
Handles: profile loading, allocation, invocation, fallback, cooldown, result validation.

Usage:
    from runtime_allocator.skill_agent import execute_with_fallback
    result = execute_with_fallback(
        task_class="finbot_trade_proposal",
        messages=[{"role": "user", "content": "..."}],
    )
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from runtime_allocator.allocator_mvp import (
    PrivacyTier,
    QualityTier,
    QuotaLedger,
    RouteRequest,
    allocate,
    cooldown_ttl_for_error,
)
from runtime_allocator.runtime_invoker import InvokeResult, invoke_llm
from runtime_allocator.runtime_probe import ProbeResult, probe_by_protocol


# ── Profile loading ──────────────────────────────────────────────────────────

_PROFILES_PATH = Path(__file__).parent / "profiles" / "runtime_profiles.yaml"
_profiles_cache: Optional[dict] = None


def load_profiles(path: Optional[Path] = None) -> dict:
    """Load runtime profiles from YAML. Cached after first load."""
    global _profiles_cache
    if _profiles_cache is not None and path is None:
        return _profiles_cache

    p = path or _PROFILES_PATH
    if not p.exists():
        raise FileNotFoundError(f"Runtime profiles not found: {p}")

    with open(p) as f:
        data = yaml.safe_load(f)

    if path is None:
        _profiles_cache = data
    return data


def reload_profiles() -> dict:
    """Force reload profiles from disk."""
    global _profiles_cache
    _profiles_cache = None
    return load_profiles()


# ── Result dataclass ────────────────────────────────────────────────────────

@dataclass
class SkillResult:
    """Unified result from execute_with_fallback."""
    provider_id: str
    model_name: str
    content: str = ""
    finish_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    attempts: list[dict] = field(default_factory=list)
    fallback_chain: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    error: Optional[str] = None
    error_class: Optional[str] = None
    success: bool = False


# ── Core execution ───────────────────────────────────────────────────────────

def execute_with_fallback(
    task_class: str,
    messages: list[dict],
    privacy_tier: str = "external_cloud",
    min_quality_tier: str = "standard",
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
    needs_tool_calling: bool = False,
    needs_json: bool = True,
    input_tokens_est: int = 4000,
    output_tokens_est: int = 2000,
    can_degrade: bool = True,
    high_stakes: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: Optional[dict] = None,
    timeout: float = 120.0,
    max_retries: int = 2,
    profiles: Optional[dict] = None,
    ledger: Optional[QuotaLedger] = None,
) -> SkillResult:
    """Execute an LLM call with automatic routing, fallback, and cooldown.

    This is the SINGLE entry point all Paperclip orchestrators should call.

    Args:
        task_class: Task classification for routing (e.g. "finbot_trade_proposal")
        messages: OpenAI-format messages
        privacy_tier: Required privacy level ("local", "private_cloud", "external_cloud")
        min_quality_tier: Minimum quality tier ("cheap", "standard", "high", "critical")
        provider_override: Force a specific provider (skips allocator)
        model_override: Override model name
        needs_tool_calling: Whether the task needs tool calling support
        needs_json: Whether the task needs JSON mode
        input_tokens_est: Estimated input tokens
        output_tokens_est: Estimated output tokens
        can_degrade: Whether to relax quality on failure
        high_stakes: Whether this is a high-stakes task
        temperature: Sampling temperature
        max_tokens: Max output tokens
        response_format: Optional JSON mode spec
        timeout: Per-attempt timeout
        max_retries: Max retry attempts across fallback chain
        profiles: Runtime profiles dict (auto-loaded if None)
        ledger: QuotaLedger instance (auto-created if None)

    Returns:
        SkillResult with content, metadata, and attempt history.
    """
    start_total = time.monotonic()

    if profiles is None:
        profiles = load_profiles()
    if ledger is None:
        ledger = QuotaLedger()

    reason_codes: list[str] = []
    fallback_chain: list[str] = []
    attempts: list[dict] = []

    # Build runtime list from profiles
    from runtime_allocator.allocator_mvp import Runtime
    runtimes = []
    for pid, rt in profiles.get("runtimes", {}).items():
        runtimes.append(Runtime(
            provider_id=pid,
            model_name=rt.get("model_name", ""),
            endpoint=rt.get("endpoint", ""),
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

    # Provider override: bypass allocator
    if provider_override:
        provider_id = provider_override
        model = model_override
        reason_codes.append(f"provider_override={provider_override}")
        # Still reserve in ledger for tracking
        ledger.reserve(provider_id)
    else:
        # Allocate via allocator
        route_req = RouteRequest(
            task_class=task_class,
            privacy_tier_required=PrivacyTier(privacy_tier),
            min_quality_tier=QualityTier(min_quality_tier),
            needs_tool_calling=needs_tool_calling,
            needs_json=needs_json,
            input_tokens_est=input_tokens_est,
            output_tokens_est=output_tokens_est,
            can_degrade=can_degrade,
            high_stakes=high_stakes,
        )
        decision = allocate(route_req, runtimes=runtimes, ledger=ledger)

        if decision.blocked:
            total_ms = (time.monotonic() - start_total) * 1000
            return SkillResult(
                provider_id="blocked",
                model_name="none",
                total_latency_ms=total_ms,
                attempts=attempts,
                fallback_chain=fallback_chain,
                reason_codes=decision.reason_codes,
                error="No available runtime (quota exhausted or policy blocked)",
                error_class="AllocationBlocked",
            )

        provider_id = decision.provider_id
        model = model_override or decision.model_name
        reason_codes.extend(decision.reason_codes)
        fallback_chain.extend(decision.fallback_chain)

    # Build ordered attempt list: primary + fallbacks
    primary_profile = profiles.get("runtimes", {}).get(provider_id, {})
    attempt_targets = [(provider_id, model or primary_profile.get("model_name", ""))]

    # Add fallbacks from allocator
    for fb_id in fallback_chain:
        fb_profile = profiles.get("runtimes", {}).get(fb_id, {})
        if fb_profile.get("enabled", True) and not ledger.is_cooling_down(fb_id):
            attempt_targets.append((fb_id, fb_profile.get("model_name", "")))

    # Execute with fallback
    last_error = None
    for attempt_idx, (pid, mdl) in enumerate(attempt_targets[:max_retries + 1]):
        if ledger.is_cooling_down(pid):
            attempts.append({
                "provider_id": pid,
                "model": mdl,
                "skipped": True,
                "reason": "cooldown",
            })
            continue

        result = invoke_llm(
            provider_id=pid,
            messages=messages,
            model=mdl,
            profiles=profiles,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
        )

        attempt_record = {
            "provider_id": pid,
            "model": mdl,
            "latency_ms": result.latency_ms,
            "success": not result.error,
            "error": result.error,
            "error_class": result.error_class,
        }
        attempts.append(attempt_record)

        if not result.error:
            total_ms = (time.monotonic() - start_total) * 1000
            return SkillResult(
                provider_id=pid,
                model_name=mdl,
                content=result.content,
                finish_reason=result.finish_reason,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                total_latency_ms=total_ms,
                attempts=attempts,
                fallback_chain=fallback_chain,
                reason_codes=reason_codes,
                success=True,
            )

        # On failure: set cooldown and try next
        last_error = result
        cooldown = cooldown_ttl_for_error(result.error_class, result.error)
        if cooldown:
            reason, ttl = cooldown
            ledger.set_cooldown(pid, reason, ttl)
            reason_codes.append(f"cooldown_set={pid}:{reason}:{ttl}s")

    # All attempts failed
    total_ms = (time.monotonic() - start_total) * 1000
    return SkillResult(
        provider_id=attempt_targets[0][0] if attempt_targets else "none",
        model_name=attempt_targets[0][1] if attempt_targets else "none",
        total_latency_ms=total_ms,
        attempts=attempts,
        fallback_chain=fallback_chain,
        reason_codes=reason_codes,
        error=last_error.error if last_error else "No attempts made",
        error_class=last_error.error_class if last_error else "NoAttempts",
    )


# ── Convenience wrappers ────────────────────────────────────────────────────

def execute_json(
    task_class: str,
    messages: list[dict],
    **kwargs,
) -> tuple[Optional[dict], SkillResult]:
    """Execute and parse response as JSON. Returns (parsed_json, skill_result)."""
    kwargs.setdefault("response_format", {"type": "json_object"})
    result = execute_with_fallback(task_class, messages, **kwargs)

    if not result.success:
        return None, result

    try:
        parsed = json.loads(result.content)
        return parsed, result
    except json.JSONDecodeError:
        result.reason_codes.append("json_parse_failed")
        return None, result


def execute_text(
    task_class: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    **kwargs,
) -> SkillResult:
    """Simple text completion wrapper."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return execute_with_fallback(task_class, messages, **kwargs)


# ── Health check ─────────────────────────────────────────────────────────────

def health_check(profiles: Optional[dict] = None) -> dict[str, Any]:
    """Probe all runtimes and return health summary."""
    if profiles is None:
        profiles = load_profiles()

    results = {}
    for pid, rt in profiles.get("runtimes", {}).items():
        if not rt.get("enabled", True):
            results[pid] = {"available": False, "reason": "disabled"}
            continue
        probe = probe_by_protocol(rt.get("endpoint", ""), pid, rt.get("protocol", "openai_compatible"))
        results[pid] = {
            "available": probe.available,
            "latency_ms": probe.latency_ms,
            "error": probe.error,
            "model_loaded": probe.model_loaded,
        }
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "health":
        health = health_check()
        print(json.dumps(health, indent=2))
    else:
        result = execute_text(
            task_class="benchmark",
            prompt="Say hello in one word.",
            max_tokens=10,
            can_degrade=True,
        )
        if result.success:
            print(f"OK [{result.provider_id}]: {result.content[:100]}")
        else:
            print(f"FAIL: {result.error}")
