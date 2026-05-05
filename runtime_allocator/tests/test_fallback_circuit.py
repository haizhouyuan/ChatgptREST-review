"""D4: Fallback/circuit breaker tests."""

from __future__ import annotations

import pytest

from runtime_allocator.allocator_mvp import cooldown_ttl_for_error


class TestCooldownTtl:
    def test_429_returns_rate_limit_cooldown(self):
        reason, ttl = cooldown_ttl_for_error("HTTP429", "rate limit exceeded")
        assert reason == "rate_limit"
        assert ttl > 0

    def test_auth_error_returns_long_cooldown(self):
        reason, ttl = cooldown_ttl_for_error("HTTP401", "unauthorized")
        assert reason == "auth_error"
        assert ttl > 0

    def test_unknown_error_returns_none(self):
        result = cooldown_ttl_for_error("UnknownError", "something broke")
        assert result is None


class TestSkillResultTerminalState:
    def test_success_sets_completed(self):
        from runtime_allocator.skill_agent import SkillResult
        sr = SkillResult(
            provider_id="claudekimi",
            model_name="test",
            success=True,
            terminal_state="completed",
        )
        assert sr.terminal_state == "completed"
        assert not sr.requires_human_review

    def test_high_stakes_sets_human_review(self):
        from runtime_allocator.skill_agent import SkillResult
        sr = SkillResult(
            provider_id="claudekimi",
            model_name="test",
            success=True,
            terminal_state="human_review_required",
            requires_human_review=True,
        )
        assert sr.requires_human_review

    def test_blocked_sets_blocked(self):
        from runtime_allocator.skill_agent import SkillResult
        sr = SkillResult(
            provider_id="blocked",
            model_name="none",
            terminal_state="blocked",
        )
        assert sr.terminal_state == "blocked"
