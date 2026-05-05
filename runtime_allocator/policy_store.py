"""Routing policy loader for Paperclip Skill Agent.

Loads routing_policy.yaml and provides policy-aware routing decisions.
Policy is the PRIMARY routing mechanism — primary/fallback chains define
candidate order. Scoring only breaks ties within the same policy tier.

Usage:
    from runtime_allocator.policy_store import load_routing_policy, PolicyEntry
    policies = load_routing_policy()
    entry = policies.get("finbot_trade_proposal")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

_PKG_DIR = Path(__file__).resolve().parent


def _resolve_policy_path() -> Path:
    """Resolve routing_policy.yaml path with env override and fallback."""
    env_path = os.getenv("PAPERCLIP_ROUTING_POLICY")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    candidates = [
        _PKG_DIR / "profiles" / "routing_policy.yaml",
        _PKG_DIR / "routing_policy.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


@dataclass
class PolicyEntry:
    """A single task-class routing policy."""
    task_class: str
    primary: list[str] = field(default_factory=list)
    fallback: list[str] = field(default_factory=list)
    can_degrade: bool = True
    allowed_quality: Optional[list[str]] = None  # e.g. ["critical", "high"]
    allowed_privacy: Optional[list[str]] = None  # e.g. ["local", "private_cloud"]
    terminal_if_unavailable: str = "blocked"
    note: Optional[str] = None

    @property
    def all_candidates(self) -> list[str]:
        """Primary + fallback in policy-defined order."""
        return self.primary + self.fallback


_policy_cache: Optional[dict[str, PolicyEntry]] = None


def load_routing_policy(path: Optional[Path] = None) -> dict[str, PolicyEntry]:
    """Load routing policies from YAML. Returns {task_class: PolicyEntry}.

    Cached after first load. Pass path to override.
    """
    global _policy_cache
    if _policy_cache is not None and path is None:
        return _policy_cache

    p = path or _resolve_policy_path()
    if not p.exists():
        raise FileNotFoundError(f"Routing policy not found: {p}")

    with open(p) as f:
        data = yaml.safe_load(f)

    policies: dict[str, PolicyEntry] = {}
    for task_class, cfg in data.get("policies", {}).items():
        policies[task_class] = PolicyEntry(
            task_class=task_class,
            primary=cfg.get("primary", []),
            fallback=cfg.get("fallback", []),
            can_degrade=cfg.get("can_degrade", True),
            allowed_quality=cfg.get("allowed_quality"),
            allowed_privacy=cfg.get("allowed_privacy"),
            terminal_if_unavailable=cfg.get("terminal_if_unavailable", "blocked"),
            note=cfg.get("note"),
        )

    if path is None:
        _policy_cache = policies
    return policies


def reload_policy() -> dict[str, PolicyEntry]:
    """Force reload policy from disk."""
    global _policy_cache
    _policy_cache = None
    return load_routing_policy()


def get_policy(task_class: str) -> Optional[PolicyEntry]:
    """Get policy for a task class, or None if unknown."""
    policies = load_routing_policy()
    return policies.get(task_class)


# ── CLI ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    policies = load_routing_policy()
    print(f"Loaded {len(policies)} policies:")
    for tc, p in sorted(policies.items()):
        chain = " → ".join(p.all_candidates) if p.all_candidates else "(no candidates)"
        print(f"  {tc:30s} {chain}")
