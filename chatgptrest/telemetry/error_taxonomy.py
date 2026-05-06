"""
Error Taxonomy: Structured provider error classification and recovery.

Pro insight: "至少定义 LOGIN_EXPIRED, DOM_DRIFT, STALL_NO_GROWTH, RATE_LIMIT,
PROMPT_TOO_LARGE, LOW_QUALITY_OUTPUT — 每类对应固定恢复策略，而不是统一 retry=3"

Gemini insight: "Gemini circuit breaker + health-aware routing"

This module replaces blind retry with error-type-specific recovery strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


class ErrorCategory(str, Enum):
    """Structured error classification for provider failures."""

    # Authentication / session
    LOGIN_EXPIRED = "login_expired"
    SESSION_DRIFT = "session_drift"

    # DOM / UI automation
    DOM_DRIFT = "dom_drift"
    SELECTOR_STALE = "selector_stale"
    ELEMENT_NOT_FOUND = "element_not_found"

    # Content / generation
    STALL_NO_GROWTH = "stall_no_growth"
    LOW_QUALITY_OUTPUT = "low_quality_output"
    PROMPT_TOO_LARGE = "prompt_too_large"
    CONTENT_POLICY = "content_policy"
    INCOMPLETE_RESPONSE = "incomplete_response"

    # Network / infrastructure
    RATE_LIMIT = "rate_limit"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    BROWSER_CRASH = "browser_crash"

    # Extension / driver
    EXTENSION_BLOCKED = "extension_blocked"
    FILE_UPLOAD_FAILED = "file_upload_failed"
    GITHUB_INDEX_FAILED = "github_index_failed"

    # Unknown
    UNKNOWN = "unknown"


@dataclass
class RecoveryStrategy:
    """How to recover from a specific error category."""

    action: Literal[
        "retry_same",           # Retry same request
        "retry_fresh_thread",   # New conversation thread
        "refresh_session",      # Re-login / refresh cookies
        "restart_browser",      # Kill and restart Chrome
        "downgrade_preset",     # Use simpler preset
        "compress_prompt",      # Reduce prompt size
        "skip_and_fallback",    # Skip this provider, use another
        "abort",                # Don't retry, fail permanently
        "wait_and_retry",       # Wait for cooldown then retry
    ]
    max_retries: int = 1
    backoff_seconds: int = 30
    fallback_provider: Optional[str] = None
    notes: str = ""


# ─────────────────────────────────────────────
# Recovery strategy mapping
# ─────────────────────────────────────────────

RECOVERY_STRATEGIES: dict[ErrorCategory, RecoveryStrategy] = {
    ErrorCategory.LOGIN_EXPIRED: RecoveryStrategy(
        action="refresh_session",
        max_retries=2,
        backoff_seconds=15,
        notes="Re-login via stored cookies or manual intervention",
    ),
    ErrorCategory.SESSION_DRIFT: RecoveryStrategy(
        action="retry_fresh_thread",
        max_retries=1,
        backoff_seconds=5,
        notes="Start new conversation to escape drifted session state",
    ),
    ErrorCategory.DOM_DRIFT: RecoveryStrategy(
        action="retry_fresh_thread",
        max_retries=2,
        backoff_seconds=10,
        notes="Gemini DOM changes frequently; fresh thread avoids stale selectors",
    ),
    ErrorCategory.SELECTOR_STALE: RecoveryStrategy(
        action="retry_fresh_thread",
        max_retries=2,
        backoff_seconds=10,
        notes="Use 3-layer selector fallback (aria-label → visible text → CSS)",
    ),
    ErrorCategory.ELEMENT_NOT_FOUND: RecoveryStrategy(
        action="retry_fresh_thread",
        max_retries=1,
        backoff_seconds=15,
        notes="Page layout changed; try fresh thread",
    ),
    ErrorCategory.STALL_NO_GROWTH: RecoveryStrategy(
        action="retry_fresh_thread",
        max_retries=1,
        backoff_seconds=30,
        notes="Model stopped generating; kill thread and retry",
    ),
    ErrorCategory.LOW_QUALITY_OUTPUT: RecoveryStrategy(
        action="downgrade_preset",
        max_retries=1,
        backoff_seconds=5,
        notes="Short/garbage output; retry with explicit instructions",
    ),
    ErrorCategory.PROMPT_TOO_LARGE: RecoveryStrategy(
        action="compress_prompt",
        max_retries=1,
        backoff_seconds=5,
        notes="Split/compress prompt before retrying",
    ),
    ErrorCategory.CONTENT_POLICY: RecoveryStrategy(
        action="abort",
        max_retries=0,
        notes="Content policy rejection; don't retry same content",
    ),
    ErrorCategory.INCOMPLETE_RESPONSE: RecoveryStrategy(
        action="retry_same",
        max_retries=2,
        backoff_seconds=10,
        notes="Response cut off; retry with 'continue' prompt",
    ),
    ErrorCategory.RATE_LIMIT: RecoveryStrategy(
        action="wait_and_retry",
        max_retries=3,
        backoff_seconds=120,
        fallback_provider="local",
        notes="Rate limited; wait or fall back to local model",
    ),
    ErrorCategory.NETWORK_ERROR: RecoveryStrategy(
        action="retry_same",
        max_retries=2,
        backoff_seconds=30,
        notes="Network glitch; simple retry",
    ),
    ErrorCategory.TIMEOUT: RecoveryStrategy(
        action="retry_fresh_thread",
        max_retries=1,
        backoff_seconds=60,
        notes="Request timed out; may need fresh thread to escape stuck state",
    ),
    ErrorCategory.BROWSER_CRASH: RecoveryStrategy(
        action="restart_browser",
        max_retries=1,
        backoff_seconds=30,
        notes="Chrome crashed; restart CDP browser",
    ),
    ErrorCategory.EXTENSION_BLOCKED: RecoveryStrategy(
        action="skip_and_fallback",
        max_retries=0,
        fallback_provider="chatgpt",
        notes="Extension interfering; switch provider or restart without extension",
    ),
    ErrorCategory.FILE_UPLOAD_FAILED: RecoveryStrategy(
        action="skip_and_fallback",
        max_retries=1,
        backoff_seconds=10,
        notes="File upload failed; try without attachment",
    ),
    ErrorCategory.GITHUB_INDEX_FAILED: RecoveryStrategy(
        action="wait_and_retry",
        max_retries=2,
        backoff_seconds=120,
        notes="GitHub indexing not ready; wait and retry",
    ),
    ErrorCategory.UNKNOWN: RecoveryStrategy(
        action="retry_same",
        max_retries=1,
        backoff_seconds=30,
        notes="Unknown error; single retry then manual investigation",
    ),
}


def classify_error(
    error_message: str,
    *,
    provider: str = "unknown",
    phase: str = "unknown",
) -> ErrorCategory:
    """
    Classify a raw error message into a structured ErrorCategory.

    Uses keyword matching — intentionally simple and extensible.
    """
    msg = error_message.lower()

    # Login / auth
    if any(kw in msg for kw in [
        "login", "sign in", "authentication", "expired",
        "session", "cookie", "unauthorized", "403",
    ]):
        if "drift" in msg or "stale" in msg:
            return ErrorCategory.SESSION_DRIFT
        return ErrorCategory.LOGIN_EXPIRED

    # DOM / UI
    if any(kw in msg for kw in [
        "selector", "css", "xpath", "dom",
        "aria", "element not found", "stale element",
    ]):
        if "not found" in msg or "no such element" in msg:
            return ErrorCategory.ELEMENT_NOT_FOUND
        if "stale" in msg:
            return ErrorCategory.SELECTOR_STALE
        return ErrorCategory.DOM_DRIFT

    # Content
    if any(kw in msg for kw in [
        "no growth", "stall", "stuck", "not responding",
        "empty response", "no output",
    ]):
        return ErrorCategory.STALL_NO_GROWTH

    if any(kw in msg for kw in [
        "quality", "garbage", "placeholder", "too short",
        "min_chars",
    ]):
        return ErrorCategory.LOW_QUALITY_OUTPUT

    if any(kw in msg for kw in [
        "too large", "too long", "token limit", "max length",
        "prompt.*large", "oversize",
    ]):
        return ErrorCategory.PROMPT_TOO_LARGE

    if any(kw in msg for kw in [
        "content policy", "blocked", "safety", "filtered",
        "violat",
    ]):
        return ErrorCategory.CONTENT_POLICY

    if any(kw in msg for kw in [
        "incomplete", "truncated", "cut off",
    ]):
        return ErrorCategory.INCOMPLETE_RESPONSE

    # Rate limit
    if any(kw in msg for kw in [
        "rate limit", "too many requests", "throttl", "429",
        "cooldown",
    ]):
        return ErrorCategory.RATE_LIMIT

    # Network
    if any(kw in msg for kw in [
        "network", "connection", "dns", "refused",
        "unreachable",
    ]):
        return ErrorCategory.NETWORK_ERROR

    if any(kw in msg for kw in ["timeout", "timed out"]):
        return ErrorCategory.TIMEOUT

    # Browser
    if any(kw in msg for kw in [
        "browser", "chrome", "crash", "devtools",
        "target closed", "page closed",
    ]):
        return ErrorCategory.BROWSER_CRASH

    # Extension
    if any(kw in msg for kw in [
        "extension", "addon", "plugin",
    ]):
        return ErrorCategory.EXTENSION_BLOCKED

    # File upload
    if any(kw in msg for kw in [
        "upload", "file", "input_files", "set_input",
    ]):
        return ErrorCategory.FILE_UPLOAD_FAILED

    # GitHub
    if any(kw in msg for kw in [
        "github", "index", "greyed out", "indexing",
    ]):
        return ErrorCategory.GITHUB_INDEX_FAILED

    return ErrorCategory.UNKNOWN


def get_recovery_strategy(category: ErrorCategory) -> RecoveryStrategy:
    """Get the recovery strategy for an error category."""
    return RECOVERY_STRATEGIES.get(
        category,
        RECOVERY_STRATEGIES[ErrorCategory.UNKNOWN],
    )


@dataclass
class ProviderHealth:
    """Rolling health score for a provider."""

    provider: str
    success_count: int = 0
    failure_count: int = 0
    recent_errors: list[ErrorCategory] = field(default_factory=list)
    _max_recent: int = 20

    @property
    def total(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 1.0
        return self.success_count / self.total

    @property
    def status(self) -> Literal["green", "yellow", "red"]:
        rate = self.success_rate
        if rate >= 0.85:
            return "green"
        if rate >= 0.70:
            return "yellow"
        return "red"

    def record_success(self) -> None:
        self.success_count += 1

    def record_failure(self, category: ErrorCategory) -> None:
        self.failure_count += 1
        self.recent_errors.append(category)
        if len(self.recent_errors) > self._max_recent:
            self.recent_errors = self.recent_errors[-self._max_recent:]

    @property
    def dominant_error(self) -> Optional[ErrorCategory]:
        """Most frequent recent error category."""
        if not self.recent_errors:
            return None
        counts: dict[ErrorCategory, int] = {}
        for e in self.recent_errors:
            counts[e] = counts.get(e, 0) + 1
        return max(counts, key=counts.get)

    def should_accept_critical_task(self) -> bool:
        """Whether this provider should accept critical-path tasks."""
        return self.status != "red"

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "success_rate": round(self.success_rate, 3),
            "status": self.status,
            "total_jobs": self.total,
            "dominant_error": (
                self.dominant_error.value if self.dominant_error else None
            ),
        }
