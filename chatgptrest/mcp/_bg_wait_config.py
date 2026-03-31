"""BackgroundWaitConfig — shared config dataclass for background wait parameters.

Encapsulates the ~20 parameters that are passed between
``_background_wait_start``, ``_background_wait_runner``, and their callers,
eliminating 6× repeated 20-line parameter lists.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class BackgroundWaitConfig:
    """Immutable configuration for a background-wait session."""

    # ── Core wait params ────────────────────────────────────────────
    timeout_seconds: int = 43200
    poll_seconds: float = 1.0
    notify_controller: bool = True
    notify_done: bool = True

    # ── Auto repair-check ───────────────────────────────────────────
    auto_repair_check: bool = False
    auto_repair_check_mode: str = "quick"
    auto_repair_check_timeout_seconds: int = 60
    auto_repair_check_probe_driver: bool = True
    auto_repair_check_capture_ui: bool = True
    auto_repair_check_recent_failures: int = 5
    auto_repair_notify_controller: bool = False
    auto_repair_notify_done: bool = False

    # ── Auto codex-autofix ──────────────────────────────────────────
    auto_codex_autofix: bool = True
    auto_codex_autofix_timeout_seconds: int = 600
    auto_codex_autofix_model: str | None = None
    auto_codex_autofix_max_risk: str = "low"
    auto_codex_autofix_allow_actions: str | list[str] | None = None
    auto_codex_autofix_apply_actions: bool = True

    # ── Restart behavior ────────────────────────────────────────────
    force_restart: bool = False
