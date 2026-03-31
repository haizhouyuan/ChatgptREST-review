"""Routing configuration loader — reads routing_profile.json into typed dataclasses.

Provides:
  - RoutingProfile: top-level config container
  - ProviderConfig, CandidateConfig, RouteEntry, SwitchPolicy, GuardProfile: nested configs
  - load_routing_profile(): load + validate from disk
  - validate_routing_profile(): structural checks (no empty candidates, payg fallback exists)

Usage::

    from chatgptrest.kernel.routing_config import load_routing_profile

    profile = load_routing_profile()  # loads from default path
    print(profile.profile_name, len(profile.routes), "routes")
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default path relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = str(_PROJECT_ROOT / "config" / "routing_profile.json")


# ── Data Classes ──────────────────────────────────────────────────


@dataclass
class TierConfig:
    """Configuration for a single routing tier."""
    max_concurrency: int = 8
    note: str = ""


@dataclass
class RateLimitConfig:
    """Rate limiting configuration for a provider."""
    send_rate_limit_key: str = ""
    min_prompt_interval_seconds: int = 61
    jitter_seconds: int = 15


@dataclass
class HealthGateConfig:
    """Health gate (blocked pre-check) configuration."""
    preflight_tool: str = ""
    preflight_timeout_ms: int = 15000
    blocked_cooldown_seconds: int = 1200


@dataclass
class ProviderConfig:
    """Configuration for a single provider/channel."""
    tier: str = "buffer"
    type: str = "openai_compat_api"
    display_name: str = ""
    job_kind: str = ""
    capabilities: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    avg_latency_hint_ms: int = 3000
    quality_hint: float = 0.7
    invocation: str = ""
    base_url: str = ""
    base_url_env: str = ""
    api_key_env: str = ""
    rate_limit: RateLimitConfig | None = None
    health_gate: HealthGateConfig | None = None
    timeouts: dict[str, int] = field(default_factory=dict)


@dataclass
class ModelConfig:
    """Configuration for a single model in the registry."""
    provider_type: str = "api"
    display_name: str = ""
    avg_latency_hint_ms: int = 3000
    cost_hint: float = 0.01
    quality_hint: float = 0.7
    capabilities: list[str] = field(default_factory=list)
    invocation: str = ""


@dataclass
class OnlyIfCondition:
    """Conditional filter for a candidate."""
    evidence_level_in: list[str] | None = None
    latency_budget_ms_gte: int | None = None
    need_web: bool | None = None
    tooling_required: bool | None = None


@dataclass
class CandidateConfig:
    """A single candidate in a route's fallback chain."""
    provider: str = ""
    mode: str = "api"  # "api" | "web" | "mcp" | "cli"
    model: str = ""
    preset: str = ""
    phase: str = ""
    guard_profile: str = ""
    timeout_ms: int = 180000
    notes: str = ""
    only_if: OnlyIfCondition | None = None


@dataclass
class RouteMatch:
    """Match criteria for a route."""
    scenario: str = ""
    task_type: str = ""


@dataclass
class RouteEntry:
    """A single route: match criteria → ordered candidate list."""
    match: RouteMatch = field(default_factory=RouteMatch)
    candidates: list[CandidateConfig] = field(default_factory=list)


@dataclass
class SwitchPolicy:
    """Policy for switching between candidates on failure."""
    max_attempts_per_candidate: int = 2
    consecutive_failures_to_cooldown: int = 2
    cooldown_seconds_on_429: int = 300
    cooldown_seconds_on_5xx: int = 120
    cooldown_seconds_on_timeout: int = 180
    cooldown_seconds_on_auth_fail: int = 600
    error_mapping: dict[str, str] = field(default_factory=dict)


@dataclass
class GuardProfile:
    """Completion guard configuration."""
    ack_block_enabled: bool = False
    min_chars_default: int = 0
    max_wait_seconds: int = 600
    wait_timeout_seconds: int = 30
    no_duplicate_send: bool = True
    wait_slice_seconds: int = 30
    export_conversation_on_in_progress: bool = True


@dataclass
class RoutingProfile:
    """Top-level routing configuration."""
    schema_version: str = "1.0.0"
    profile_name: str = ""
    updated_at: str = ""
    tiers: dict[str, TierConfig] = field(default_factory=dict)
    tier_order: list[str] = field(default_factory=list)
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    models: dict[str, ModelConfig] = field(default_factory=dict)
    static_routes: dict[str, list[str]] = field(default_factory=dict)
    routes: list[RouteEntry] = field(default_factory=list)
    switch_policy: SwitchPolicy = field(default_factory=SwitchPolicy)
    guards: dict[str, GuardProfile] = field(default_factory=dict)


# ── Parsing Helpers ───────────────────────────────────────────────


def _parse_only_if(data: dict[str, Any] | None) -> OnlyIfCondition | None:
    if not data:
        return None
    return OnlyIfCondition(
        evidence_level_in=data.get("evidence_level_in"),
        latency_budget_ms_gte=data.get("latency_budget_ms_gte"),
        need_web=data.get("need_web"),
        tooling_required=data.get("tooling_required"),
    )


def _parse_candidate(data: dict[str, Any]) -> CandidateConfig:
    return CandidateConfig(
        provider=data.get("provider", ""),
        mode=data.get("mode", "api"),
        model=data.get("model", ""),
        preset=data.get("preset", ""),
        phase=data.get("phase", ""),
        guard_profile=data.get("guard_profile", ""),
        timeout_ms=data.get("timeout_ms", 180000),
        notes=data.get("notes", ""),
        only_if=_parse_only_if(data.get("only_if")),
    )


def _parse_provider(data: dict[str, Any]) -> ProviderConfig:
    rl_data = data.get("rate_limit")
    hg_data = data.get("health_gate")
    return ProviderConfig(
        tier=data.get("tier", "buffer"),
        type=data.get("type", "openai_compat_api"),
        display_name=data.get("display_name", ""),
        job_kind=data.get("job_kind", ""),
        capabilities=data.get("capabilities", []),
        models=data.get("models", []),
        avg_latency_hint_ms=data.get("avg_latency_hint_ms", 3000),
        quality_hint=data.get("quality_hint", 0.7),
        invocation=data.get("invocation", ""),
        base_url=data.get("base_url", ""),
        base_url_env=data.get("base_url_env", ""),
        api_key_env=data.get("api_key_env", ""),
        rate_limit=RateLimitConfig(
            send_rate_limit_key=rl_data.get("send_rate_limit_key", ""),
            min_prompt_interval_seconds=rl_data.get("min_prompt_interval_seconds", 61),
            jitter_seconds=rl_data.get("jitter_seconds", 15),
        ) if rl_data else None,
        health_gate=HealthGateConfig(
            preflight_tool=hg_data.get("preflight_tool", ""),
            preflight_timeout_ms=hg_data.get("preflight_timeout_ms", 15000),
            blocked_cooldown_seconds=hg_data.get("blocked_cooldown_seconds", 1200),
        ) if hg_data else None,
        timeouts=data.get("timeouts", {}),
    )


def _parse_model(data: dict[str, Any]) -> ModelConfig:
    return ModelConfig(
        provider_type=data.get("provider_type", "api"),
        display_name=data.get("display_name", ""),
        avg_latency_hint_ms=data.get("avg_latency_hint_ms", 3000),
        cost_hint=data.get("cost_hint", 0.01),
        quality_hint=data.get("quality_hint", 0.7),
        capabilities=data.get("capabilities", []),
        invocation=data.get("invocation", ""),
    )


def _parse_guard(data: dict[str, Any]) -> GuardProfile:
    return GuardProfile(
        ack_block_enabled=data.get("ack_block_enabled", False),
        min_chars_default=data.get("min_chars_default", 0),
        max_wait_seconds=data.get("max_wait_seconds", 600),
        wait_timeout_seconds=data.get("wait_timeout_seconds", 30),
        no_duplicate_send=data.get("no_duplicate_send", True),
        wait_slice_seconds=data.get("wait_slice_seconds", 30),
        export_conversation_on_in_progress=data.get("export_conversation_on_in_progress", True),
    )


def _parse_profile(raw: dict[str, Any]) -> RoutingProfile:
    """Parse raw JSON dict into a RoutingProfile."""
    # Tiers
    tiers_raw = raw.get("tiers", {})
    tier_order = tiers_raw.get("tier_order", ["membership", "buffer", "payg"])
    tiers = {}
    for name in tier_order:
        td = tiers_raw.get(name, {})
        tiers[name] = TierConfig(
            max_concurrency=td.get("max_concurrency", 8),
            note=td.get("note", ""),
        )

    # Providers
    providers = {}
    for pid, pdata in raw.get("providers", {}).items():
        providers[pid] = _parse_provider(pdata)

    # Models
    models = {}
    for mid, mdata in raw.get("models", {}).items():
        models[mid] = _parse_model(mdata)

    # Static routes
    static_routes = raw.get("static_routes", {})

    # Routes
    routes = []
    for rdata in raw.get("routes", []):
        match_data = rdata.get("match", {})
        routes.append(RouteEntry(
            match=RouteMatch(
                scenario=match_data.get("scenario", ""),
                task_type=match_data.get("task_type", ""),
            ),
            candidates=[_parse_candidate(c) for c in rdata.get("candidates", [])],
        ))

    # Switch policy
    sp_data = raw.get("switch_policy", {})
    switch_policy = SwitchPolicy(
        max_attempts_per_candidate=sp_data.get("max_attempts_per_candidate", 2),
        consecutive_failures_to_cooldown=sp_data.get("consecutive_failures_to_cooldown", 2),
        cooldown_seconds_on_429=sp_data.get("cooldown_seconds_on_429", 300),
        cooldown_seconds_on_5xx=sp_data.get("cooldown_seconds_on_5xx", 120),
        cooldown_seconds_on_timeout=sp_data.get("cooldown_seconds_on_timeout", 180),
        cooldown_seconds_on_auth_fail=sp_data.get("cooldown_seconds_on_auth_fail", 600),
        error_mapping=sp_data.get("error_mapping", {}),
    )

    # Guards
    guards = {}
    for gname, gdata in raw.get("guards", {}).items():
        guards[gname] = _parse_guard(gdata)

    return RoutingProfile(
        schema_version=raw.get("schema_version", "1.0.0"),
        profile_name=raw.get("profile_name", ""),
        updated_at=raw.get("updated_at", ""),
        tiers=tiers,
        tier_order=tier_order,
        providers=providers,
        models=models,
        static_routes=static_routes,
        routes=routes,
        switch_policy=switch_policy,
        guards=guards,
    )


# ── Validation ────────────────────────────────────────────────────


class RoutingConfigError(ValueError):
    """Raised when routing profile validation fails."""
    pass


def validate_routing_profile(profile: RoutingProfile) -> list[str]:
    """Validate a routing profile. Returns list of error messages (empty = valid)."""
    errors: list[str] = []

    # Must have at least one route
    if not profile.routes:
        errors.append("No routes defined")

    # Each route must have non-empty candidates
    for i, route in enumerate(profile.routes):
        if not route.candidates:
            errors.append(
                f"Route[{i}] ({route.match.scenario}/{route.match.task_type}): "
                f"empty candidates list"
            )

        # Each candidate must reference an existing provider
        for j, cand in enumerate(route.candidates):
            if cand.provider not in profile.providers:
                errors.append(
                    f"Route[{i}].candidate[{j}]: provider '{cand.provider}' "
                    f"not found in providers registry"
                )

    # Each route should have at least one payg-tier candidate for fallback safety
    for i, route in enumerate(profile.routes):
        has_payg = False
        for cand in route.candidates:
            prov = profile.providers.get(cand.provider)
            if prov and prov.tier == "payg":
                has_payg = True
                break
        if not has_payg:
            # Warning, not error — payg may not be configured
            logger.warning(
                "Route[%d] (%s/%s) has no payg-tier fallback candidate",
                i, route.match.scenario, route.match.task_type,
            )

    # Tier order must be non-empty
    if not profile.tier_order:
        errors.append("tier_order is empty")

    return errors


# ── Public API ────────────────────────────────────────────────────


def load_routing_profile(
    path: str | None = None,
    *,
    validate: bool = True,
) -> RoutingProfile:
    """Load routing profile from JSON file.

    Args:
        path: Path to routing_profile.json. Defaults to config/routing_profile.json.
        validate: If True, run validation checks on load.

    Returns:
        Parsed RoutingProfile.

    Raises:
        RoutingConfigError: If validation fails.
        FileNotFoundError: If config file not found.
    """
    config_path = path or os.environ.get(
        "ROUTING_PROFILE_PATH", DEFAULT_CONFIG_PATH,
    )

    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Routing profile not found: {config_path}")

    with open(p, "r", encoding="utf-8") as f:
        raw = json.load(f)

    profile = _parse_profile(raw)

    if validate:
        errors = validate_routing_profile(profile)
        if errors:
            raise RoutingConfigError(
                f"Routing profile validation failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    logger.info(
        "Loaded routing profile: %s (v%s) — %d routes, %d providers, %d models",
        profile.profile_name,
        profile.schema_version,
        len(profile.routes),
        len(profile.providers),
        len(profile.models),
    )

    return profile
