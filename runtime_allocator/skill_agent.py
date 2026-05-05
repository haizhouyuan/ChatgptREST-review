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

_PKG_DIR = Path(__file__).resolve().parent

try:
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
    from runtime_allocator.runtime_state import RuntimeStateStore, get_store
except ImportError:
    from allocator_mvp import (
        PrivacyTier,
        QualityTier,
        QuotaLedger,
        RouteRequest,
        allocate,
        cooldown_ttl_for_error,
    )
    from runtime_invoker import InvokeResult, invoke_llm
    from runtime_probe import ProbeResult, probe_by_protocol
    from runtime_state import RuntimeStateStore, get_store


# ── Profile loading ──────────────────────────────────────────────────────────

_profiles_cache: Optional[dict] = None


def _resolve_profiles_path() -> Path:
    """Resolve runtime_profiles.yaml path with env override and fallback search."""
    env_path = os.getenv("PAPERCLIP_RUNTIME_PROFILES")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    # Search: package_dir/profiles/ then package_dir/
    candidates = [
        _PKG_DIR / "profiles" / "runtime_profiles.yaml",
        _PKG_DIR / "runtime_profiles.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c

    return candidates[0]  # Return default even if missing (will raise)


def load_profiles(path: Optional[Path] = None) -> dict:
    """Load runtime profiles from YAML. Cached after first load."""
    global _profiles_cache
    if _profiles_cache is not None and path is None:
        return _profiles_cache

    p = path or _resolve_profiles_path()
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
    # B1: terminal state + human review
    terminal_state: Optional[str] = None  # "completed", "blocked", "human_review_required",
                                          # "completed_no_trade", "schema_validation_failed"
    requires_human_review: bool = False
    policy_violations: list[str] = field(default_factory=list)
    # B3: parsed/validated output (when schema_model is provided)
    validated_output: Optional[Any] = None


# Privacy/quality ranking (mirrors allocator_mvp for local override gate checks)
_PRIVACY_RANK = {"local": 0, "private_cloud": 1, "external_cloud": 2}
_QUALITY_RANK = {"cheap": 0, "standard": 1, "high": 2, "critical": 3}


# ── Quota lifecycle helpers ──────────────────────────────────────────────────


def _quota_disposition(error_class: Optional[str], error: Optional[str]) -> str:
    """Classify how an attempt's reservation should be resolved.

    Returns one of:
      - "commit_success": call succeeded
      - "refund": don't count against quota (auth, rate limit, config errors)
      - "commit_attempt": count against quota even though it failed (timeouts,
        schema invalid, generic errors)
    """
    if not error and not error_class:
        return "commit_success"
    txt = f"{error_class or ''} {error or ''}".lower()
    if "401" in txt or "403" in txt or "configerror" in txt or "auth" in txt:
        return "refund"
    if "429" in txt or "rate limit" in txt or "quota" in txt:
        return "refund"
    return "commit_attempt"


# ── Core execution ───────────────────────────────────────────────────────────

def _try_validate_schema(
    raw_content: str,
    schema_model,
) -> tuple[bool, Any, Optional[str]]:
    """Try to parse and validate raw JSON content against a Pydantic model.

    Returns (ok, parsed_object, error_message).
    """
    import json
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        return False, None, f"JSON parse error: {e}"
    try:
        obj = schema_model.model_validate(data)
        return True, obj, None
    except Exception as e:
        return False, None, f"Schema validation error: {e}"


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
    state_store: Optional[RuntimeStateStore] = None,
    schema_model=None,
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
    if state_store is None:
        state_store = get_store()

    import uuid as _uuid
    request_id = _uuid.uuid4().hex[:12]

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

    # ── Provider override safety gates ──────────────────────────────────
    # Override bypasses ranking but NOT privacy/quality/policy/health/quota gates.
    # If any gate fails, fallback to normal allocation.
    _override_failed_gates: list[str] = []
    if provider_override:
        reason_codes.append(f"provider_override={provider_override}")
        # Load policy for gate checks
        try:
            from runtime_allocator.policy_store import get_policy
        except ImportError:
            from policy_store import get_policy
        policy_entry = get_policy(task_class)

        # Find the override provider's profile
        override_rt = profiles.get("runtimes", {}).get(provider_override)

        if override_rt is None:
            _override_failed_gates.append(f"unknown_provider={provider_override}")
        else:
            # Privacy gate: task privacy_tier_required
            rt_privacy = override_rt.get("privacy_tier", "external_cloud")
            if _PRIVACY_RANK.get(rt_privacy, 2) > _PRIVACY_RANK.get(privacy_tier, 2):
                _override_failed_gates.append(
                    f"privacy_tier_mismatch: {rt_privacy} > {privacy_tier}"
                )

            # Quality gate: task min_quality_tier
            rt_quality = override_rt.get("quality_tier", "standard")
            if _QUALITY_RANK.get(rt_quality, 1) < _QUALITY_RANK.get(min_quality_tier, 1):
                _override_failed_gates.append(
                    f"quality_tier_mismatch: {rt_quality} < {min_quality_tier}"
                )

            # Policy gate: allowed_privacy
            if policy_entry and policy_entry.allowed_privacy:
                if override_rt.get("privacy_tier", "external_cloud") not in policy_entry.allowed_privacy:
                    _override_failed_gates.append(
                        f"policy_privacy_block: {override_rt.get('privacy_tier')} not in {policy_entry.allowed_privacy}"
                    )

            # Policy gate: allowed_quality
            if policy_entry and policy_entry.allowed_quality:
                if override_rt.get("quality_tier", "standard") not in policy_entry.allowed_quality:
                    _override_failed_gates.append(
                        f"policy_quality_block: {override_rt.get('quality_tier')} not in {policy_entry.allowed_quality}"
                    )

            # Health gate
            if state_store and not state_store.is_usable(provider_override):
                _override_failed_gates.append("health_not_usable")

            # Quota gate (legacy ledger)
            if not ledger.can_reserve(provider_override):
                _override_failed_gates.append("quota_exhausted")

        if _override_failed_gates:
            reason_codes.extend([f"override_gate:{g}" for g in _override_failed_gates])

    decision_requires_review = False
    decision_terminal_state: Optional[str] = None
    if provider_override and not _override_failed_gates:
        provider_id = provider_override
        model = model_override
        # Audit log override usage
        state_store.log_event(
            provider_id=provider_id,
            task_class=task_class,
            status="override_used",
            error_code=f"override={provider_override}",
        )
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
        decision = allocate(route_req, runtimes=runtimes, ledger=ledger, health_store=state_store)

        if decision.blocked:
            total_ms = (time.monotonic() - start_total) * 1000
            return SkillResult(
                provider_id="blocked",
                model_name="none",
                total_latency_ms=total_ms,
                attempts=attempts,
                fallback_chain=fallback_chain,
                reason_codes=decision.reason_codes,
                terminal_state=decision.terminal_state or "blocked",
                requires_human_review=(decision.terminal_state == "human_review_required"),
                error="No available runtime (quota exhausted or policy blocked)",
                error_class="AllocationBlocked",
            )

        provider_id = decision.provider_id
        model = model_override or decision.model_name
        reason_codes.extend(decision.reason_codes)
        fallback_chain.extend(decision.fallback_chain)
        # Track decision-level review/terminal hints
        decision_requires_review = decision.requires_human_review
        decision_terminal_state = decision.terminal_state

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

        # SQLite reservation per attempt (separate from legacy ledger.reserve)
        attempt_id = f"{request_id}:{attempt_idx}"
        try:
            reservation_id = state_store.reserve(
                provider_id=pid,
                request_id=request_id,
                attempt_id=attempt_id,
                task_class=task_class,
                estimated_input_tokens=input_tokens_est,
                estimated_output_tokens=output_tokens_est,
            )
        except Exception as res_err:
            reservation_id = None
            reason_codes.append(f"reserve_failed={res_err.__class__.__name__}")

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

        # Resolve reservation based on disposition
        if reservation_id is not None:
            disposition = _quota_disposition(result.error_class, result.error)
            try:
                if disposition == "commit_success":
                    state_store.commit(
                        reservation_id,
                        actual_input_tokens=result.input_tokens,
                        actual_output_tokens=result.output_tokens,
                    )
                elif disposition == "refund":
                    state_store.refund(reservation_id, reason=result.error_class or "")
                else:  # commit_attempt
                    state_store.commit(reservation_id, 0, 0)
            except Exception as res_err:
                reason_codes.append(f"reserve_resolve_failed={res_err.__class__.__name__}")

        attempt_record = {
            "provider_id": pid,
            "model": mdl,
            "reservation_id": reservation_id,
            "latency_ms": result.latency_ms,
            "success": not result.error,
            "error": result.error,
            "error_class": result.error_class,
        }
        attempts.append(attempt_record)

        if not result.error:
            # ── Schema validation (B3) ──────────────────────────────────
            validated_obj = None
            schema_retry_done = False
            if schema_model is not None:
                ok, validated_obj, schema_err = _try_validate_schema(
                    result.content, schema_model
                )
                if not ok:
                    reason_codes.append(f"schema_invalid:{pid}:{schema_err[:120]}")
                    # Retry once with lower temperature
                    if not schema_retry_done:
                        schema_retry_done = True
                        retry_result = invoke_llm(
                            provider_id=pid,
                            messages=messages,
                            model=mdl,
                            profiles=profiles,
                            temperature=max(temperature - 0.3, 0.0),
                            max_tokens=max_tokens,
                            response_format=response_format,
                            timeout=timeout,
                        )
                        if not retry_result.error:
                            ok, validated_obj, schema_err = _try_validate_schema(
                                retry_result.content, schema_model
                            )
                            if ok:
                                result = retry_result
                                reason_codes.append("schema_retry_success")
                            else:
                                reason_codes.append(f"schema_retry_failed:{schema_err[:120]}")
                                # Fall through to next provider (treat as failure)
                                result.error = f"schema_validation_failed: {schema_err[:200]}"
                                result.error_class = "SchemaValidationError"
                                # Commit reservation as attempt (we used quota)
                                if reservation_id is not None:
                                    state_store.commit(reservation_id, 0, 0)
                                # Update health: degraded but not circuit open
                                state_store.update_health(pid, "degraded", latency_ms=int(result.latency_ms))
                                state_store.log_event(
                                    provider_id=pid, task_class=task_class,
                                    status="schema_validation_failed",
                                    error_class="SchemaValidationError",
                                    error_code=schema_err[:200],
                                    latency_ms=int(result.latency_ms),
                                    tokens_in_est=input_tokens_est,
                                    tokens_out_est=output_tokens_est,
                                )
                                last_error = result
                                continue

            # ── Success path ─────────────────────────────────────────────
            state_store.update_health(pid, "healthy", latency_ms=int(result.latency_ms))
            state_store.log_event(
                provider_id=pid,
                task_class=task_class,
                status="success",
                latency_ms=int(result.latency_ms),
                tokens_in_est=input_tokens_est,
                tokens_out_est=output_tokens_est,
                tokens_actual=result.input_tokens + result.output_tokens,
            )
            total_ms = (time.monotonic() - start_total) * 1000
            success_terminal = "human_review_required" if decision_requires_review else "completed"
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
                terminal_state=success_terminal,
                requires_human_review=decision_requires_review,
                validated_output=validated_obj,
            )

        # On failure: update health, set cooldown, log event, try next
        last_error = result
        cooldown = cooldown_ttl_for_error(result.error_class, result.error)

        # Classify failure for health tracking
        error_text = f"{result.error_class or ''} {result.error or ''}".lower()
        if "429" in error_text or "rate limit" in error_text or "quota" in error_text:
            health_status = "quota_exhausted"
            circuit_seconds = cooldown[1] if cooldown else 300
        elif "404" in error_text:
            health_status = "circuit_open"
            circuit_seconds = cooldown[1] if cooldown else 600
        elif "timeout" in error_text or "connection" in error_text:
            health_status = "degraded"
            circuit_seconds = 0
        else:
            health_status = "degraded"
            circuit_seconds = 0

        state_store.update_health(
            pid, health_status,
            latency_ms=int(result.latency_ms),
            error=result.error,
            circuit_open_seconds=circuit_seconds,
        )
        state_store.log_event(
            provider_id=pid,
            task_class=task_class,
            status="failed",
            error_class=result.error_class,
            error_code=result.error[:200] if result.error else None,
            latency_ms=int(result.latency_ms),
            tokens_in_est=input_tokens_est,
            tokens_out_est=output_tokens_est,
            fallback_from=pid if attempt_idx < len(attempt_targets) - 1 else None,
            fallback_to=attempt_targets[attempt_idx + 1][0] if attempt_idx < len(attempt_targets) - 1 else None,
        )

        if cooldown:
            reason, ttl = cooldown
            ledger.set_cooldown(pid, reason, ttl)
            reason_codes.append(f"cooldown_set={pid}:{reason}:{ttl}s")

    # All attempts failed — fall back to policy terminal_if_unavailable
    total_ms = (time.monotonic() - start_total) * 1000
    try:
        from runtime_allocator.policy_store import get_policy
    except ImportError:
        from policy_store import get_policy
    policy_entry = get_policy(task_class)
    final_terminal = (
        decision_terminal_state
        or (policy_entry.terminal_if_unavailable if policy_entry else "blocked")
    )
    return SkillResult(
        provider_id=attempt_targets[0][0] if attempt_targets else "none",
        model_name=attempt_targets[0][1] if attempt_targets else "none",
        total_latency_ms=total_ms,
        attempts=attempts,
        fallback_chain=fallback_chain,
        reason_codes=reason_codes,
        terminal_state=final_terminal,
        requires_human_review=(final_terminal == "human_review_required"),
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
