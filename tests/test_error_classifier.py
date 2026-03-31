"""Tests for chatgptrest.executors.error_classifier."""
from __future__ import annotations

from chatgptrest.executors.error_classifier import classify_error, ClassificationResult


class TestClassifyError:
    # ── Gemini-specific (Finding-9: needs error_type + provider) ──────────

    def test_gemini_deep_think_by_error_type(self) -> None:
        r = classify_error(
            error_type="GeminiDeepThinkToolNotFound",
            text="some text",
            provider="gemini",
        )
        assert r.matched is True
        assert r.pattern_name == "gemini_deep_think_unavailable"
        assert r.category == "infra"

    def test_gemini_deep_think_wrong_provider_rejected(self) -> None:
        """error_type is gemini-specific — must not match for chatgpt."""
        r = classify_error(
            error_type="GeminiDeepThinkToolNotFound",
            text="",
            provider="chatgpt",
        )
        assert r.matched is False

    def test_gemini_deep_think_by_text(self) -> None:
        r = classify_error(
            error_type="",
            text="a lot of people are using deep think right now",
            provider="gemini",
        )
        assert r.matched is True
        assert r.pattern_name == "gemini_deep_think_overloaded"
        assert r.category == "overloaded"

    # ── Transient (all providers) ─────────────────────────────────────────

    def test_timeout_error_type(self) -> None:
        r = classify_error(error_type="TimeoutError", text="", provider="chatgpt")
        assert r.matched is True
        assert r.category == "transient"

    def test_connection_refused_text(self) -> None:
        r = classify_error(
            error_type="",
            text="Connection refused on port 9222",
            provider="",
        )
        assert r.matched is True
        assert r.category == "transient"

    def test_target_page_closed(self) -> None:
        r = classify_error(
            error_type="Error",
            text="Target page, context or browser has been closed",
        )
        assert r.matched is True

    # ── Blocked ───────────────────────────────────────────────────────────

    def test_rate_limit(self) -> None:
        r = classify_error(error_type="RateLimitError", text="rate limit exceeded")
        assert r.matched is True
        assert r.category == "blocked"

    # ── No match ──────────────────────────────────────────────────────────

    def test_unknown_error(self) -> None:
        r = classify_error(error_type="SomeNewError", text="something unexpected happened")
        assert r.matched is False
        assert r.pattern_name is None
        assert r.category is None

    def test_empty_inputs(self) -> None:
        r = classify_error()
        assert r.matched is False

    # ── Driver not running ────────────────────────────────────────────────

    def test_driver_not_running(self) -> None:
        r = classify_error(error_type="DriverNotRunning", text="")
        assert r.matched is True
        assert r.category == "infra"
