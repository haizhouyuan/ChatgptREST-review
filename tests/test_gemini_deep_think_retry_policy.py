from __future__ import annotations

from chatgpt_web_mcp.server import (
    _gemini_deep_think_retry_attempts,
    _gemini_deep_think_retry_wait_timeout_seconds,
)


def test_gemini_deep_think_retry_attempts_default(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_DEEP_THINK_INPLACE_RETRIES_PER_ROUND", raising=False)
    monkeypatch.delenv("GEMINI_DEEP_THINK_RETRY_ATTEMPTS", raising=False)
    assert _gemini_deep_think_retry_attempts() == 3


def test_gemini_deep_think_retry_attempts_clamped(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_DEEP_THINK_INPLACE_RETRIES_PER_ROUND", raising=False)
    monkeypatch.setenv("GEMINI_DEEP_THINK_RETRY_ATTEMPTS", "999")
    assert _gemini_deep_think_retry_attempts() == 10
    monkeypatch.setenv("GEMINI_DEEP_THINK_RETRY_ATTEMPTS", "-5")
    assert _gemini_deep_think_retry_attempts() == 0


def test_gemini_deep_think_inplace_retry_env_takes_precedence(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_DEEP_THINK_RETRY_ATTEMPTS", "2")
    monkeypatch.setenv("GEMINI_DEEP_THINK_INPLACE_RETRIES_PER_ROUND", "4")
    assert _gemini_deep_think_retry_attempts() == 4


def test_gemini_deep_think_retry_wait_timeout_default_and_clamped(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_DEEP_THINK_RETRY_WAIT_TIMEOUT_SECONDS", raising=False)
    assert _gemini_deep_think_retry_wait_timeout_seconds() == 180

    monkeypatch.setenv("GEMINI_DEEP_THINK_RETRY_WAIT_TIMEOUT_SECONDS", "5")
    assert _gemini_deep_think_retry_wait_timeout_seconds() == 30

    monkeypatch.setenv("GEMINI_DEEP_THINK_RETRY_WAIT_TIMEOUT_SECONDS", "9999")
    assert _gemini_deep_think_retry_wait_timeout_seconds() == 900
