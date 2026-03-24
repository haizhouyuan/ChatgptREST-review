"""Multi-dimensional error classifier for ChatgptREST executors.

Matches on ``error_type`` (exact), ``text`` (regex), and optionally ``provider``.
Falls back gracefully — ``classify_error()`` returning ``matched=False`` means
the executor should use its original logic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorPattern:
    """A single classifiable error pattern."""

    name: str
    category: str  # "transient", "overloaded", "infra", "ui_noise", "blocked", "ui_drift"
    text_patterns: tuple[str, ...] = ()
    error_type_exact: tuple[str, ...] = ()
    providers: tuple[str, ...] | None = None  # None = all providers
    auto_repair_hint: str | None = None  # e.g. "restart_chrome", "refresh", "wait"

    def matches(
        self,
        *,
        error_type: str = "",
        text: str = "",
        provider: str = "",
    ) -> bool:
        provider_ok = self.providers is None or provider.strip().lower() in self.providers

        # 1. error_type exact match (provider-aware)
        if self.error_type_exact:
            et = error_type.strip().lower()
            if et and et in {e.lower() for e in self.error_type_exact}:
                return provider_ok

        # 2. text regex match (provider-aware)
        if self.text_patterns:
            for p in self.text_patterns:
                if re.search(p, text, re.I):
                    return provider_ok

        return False


@dataclass(frozen=True)
class ClassificationResult:
    matched: bool
    pattern_name: str | None = None
    category: str | None = None
    auto_repair_hint: str | None = None


# ---------------------------------------------------------------------------
# Pattern library
# ---------------------------------------------------------------------------

ERROR_PATTERNS: tuple[ErrorPattern, ...] = (
    # ── Gemini-specific ───────────────────────────────────────────────────
    ErrorPattern(
        name="gemini_deep_think_unavailable",
        category="infra",
        error_type_exact=(
            "GeminiDeepThinkToolNotFound",
            "GeminiDeepThinkDidNotApply",
        ),
        text_patterns=(
            r"gemini tool not found:.*deep\s*think",
            r"deep think.*did not apply",
        ),
        providers=("gemini",),
    ),
    ErrorPattern(
        name="gemini_deep_think_overloaded",
        category="overloaded",
        text_patterns=(r"a lot of people are using deep think",),
        providers=("gemini",),
    ),
    ErrorPattern(
        name="gemini_mode_selector_not_found",
        category="infra",
        error_type_exact=("GeminiModeSelectorNotFound",),
        providers=("gemini",),
    ),
    ErrorPattern(
        name="gemini_answer_guard_rejected",
        category="ui_noise",
        error_type_exact=("GeminiAnswerGuardRejected",),
        providers=("gemini",),
    ),

    # ── Transient (all providers) ─────────────────────────────────────────
    ErrorPattern(
        name="transient_connection",
        category="transient",
        error_type_exact=(
            "TimeoutError",
            "ConnectionError",
            "RemoteDisconnected",
            "ClosedResourceError",
            "ConnectionClosedError",
        ),
        text_patterns=(
            r"connection refused",
            r"timed? ?out",
            r"target page.*closed",
            r"target closed",
            r"browser has been closed",
            r"session closed",
            r"navigating frame was detached",
        ),
    ),
    ErrorPattern(
        name="transient_cdp",
        category="transient",
        error_type_exact=("CDPError", "CDPSessionClosed"),
        text_patterns=(
            r"cdp session closed",
            r"websocket.*closed",
        ),
    ),

    # ── Blocked / rate-limited (all providers) ────────────────────────────
    ErrorPattern(
        name="rate_limited",
        category="blocked",
        error_type_exact=("RateLimitError", "CooldownActive"),
        text_patterns=(
            r"rate.?limit",
            r"cooldown",
            r"too many requests",
            r"429",
        ),
    ),
    ErrorPattern(
        name="account_blocked",
        category="blocked",
        error_type_exact=("AccountBlocked", "AccountSuspended"),
        text_patterns=(
            r"account.*blocked",
            r"account.*suspended",
            r"temporarily unavailable",
        ),
    ),

    # ── UI noise (all providers) ──────────────────────────────────────────
    ErrorPattern(
        name="empty_response",
        category="ui_noise",
        text_patterns=(
            r"empty response",
            r"no assistant message",
            r"answer_text is empty",
        ),
    ),
    ErrorPattern(
        name="network_error_ui",
        category="transient",
        text_patterns=(
            r"network\s*error",
            r"failed to fetch",
            r"ERR_CONNECTION",
        ),
    ),

    # ── Infrastructure ────────────────────────────────────────────────────
    ErrorPattern(
        name="driver_not_running",
        category="infra",
        error_type_exact=("DriverNotRunning", "MCPConnectionError"),
        text_patterns=(
            r"driver.*not running",
            r"mcp.*connection.*error",
            r"cannot connect to driver",
        ),
        auto_repair_hint="restart_driver",
    ),

    # ── Qwen-specific ─────────────────────────────────────────────────────
    ErrorPattern(
        name="qwen_session_expired",
        category="blocked",
        error_type_exact=("QwenSessionExpired",),
        text_patterns=(
            r"session.*expired",
            r"登录.*过期",
            r"请重新登录",
        ),
        providers=("qwen",),
        auto_repair_hint="restart_chrome",
    ),
    ErrorPattern(
        name="qwen_captcha",
        category="blocked",
        text_patterns=(
            r"验证码",
            r"captcha",
            r"滑动.*验证",
        ),
        providers=("qwen",),
        auto_repair_hint="pause_processing",
    ),
    ErrorPattern(
        name="qwen_network_error",
        category="transient",
        text_patterns=(
            r"网络.*错误",
            r"网络.*异常",
            r"请求.*失败",
        ),
        providers=("qwen",),
        auto_repair_hint="wait",
    ),

    # ── UI drift / selector changes (all providers) ──────────────────────
    ErrorPattern(
        name="selector_not_found",
        category="ui_drift",
        text_patterns=(
            r"selector.*not found",
            r"element.*not found",
            r"no element matches",
            r"locator\..*timeout",
            r"waiting for locator",
        ),
        auto_repair_hint="capture_ui",
    ),
    ErrorPattern(
        name="ui_layout_changed",
        category="ui_drift",
        text_patterns=(
            r"unexpected.*layout",
            r"page structure.*changed",
            r"dom.*unexpected",
        ),
        auto_repair_hint="capture_ui",
    ),
)


def classify_error(
    *,
    error_type: str = "",
    text: str = "",
    provider: str = "",
) -> ClassificationResult:
    """Classify an error by type, text, and provider.

    Returns ``ClassificationResult(matched=False)`` when no pattern matches,
    signalling the caller to fall back to its original error handling.
    """
    for p in ERROR_PATTERNS:
        if p.matches(error_type=error_type, text=text, provider=provider):
            return ClassificationResult(
                matched=True,
                pattern_name=p.name,
                category=p.category,
                auto_repair_hint=p.auto_repair_hint,
            )
    return ClassificationResult(matched=False)
