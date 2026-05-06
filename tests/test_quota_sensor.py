"""Tests for QuotaSensor — provider health tracking."""

from __future__ import annotations

import time
from chatgptrest.kernel.quota_sensor import QuotaSensor, TierHealth, HealthStatus


def test_healthy_by_default():
    s = QuotaSensor()
    h = s.check("unknown_provider")
    assert h.status == HealthStatus.HEALTHY
    assert h.is_available


def test_report_failure_degrades():
    s = QuotaSensor(degrade_threshold=2, exhaust_threshold=5)
    s.report_failure("p1", "timeout")
    assert s.check("p1").status == HealthStatus.HEALTHY  # 1 failure not enough

    s.report_failure("p1", "timeout")
    assert s.check("p1").status == HealthStatus.DEGRADED  # 2 failures = degraded

    assert s.check("p1").is_available  # degraded is still available


def test_exhausted_after_many_failures():
    s = QuotaSensor(degrade_threshold=2, exhaust_threshold=4)
    for _ in range(4):
        s.report_failure("p1", "rate_limited")
    h = s.check("p1")
    assert h.status == HealthStatus.EXHAUSTED
    assert not h.is_available


def test_report_cooldown():
    s = QuotaSensor()
    s.report_cooldown("p1", until_ts=time.time() + 999, reason="rate_limited")
    h = s.check("p1")
    assert h.status == HealthStatus.COOLDOWN
    assert h.is_in_cooldown


def test_cooldown_lifts_automatically():
    s = QuotaSensor()
    s.report_cooldown("p1", until_ts=time.time() - 1, reason="past")
    h = s.check("p1")
    assert h.status == HealthStatus.DEGRADED  # cooldown lifted


def test_report_success_recovers():
    s = QuotaSensor(degrade_threshold=2, recovery_successes=2)
    s.report_failure("p1", "timeout")
    s.report_failure("p1", "timeout")
    assert s.check("p1").status == HealthStatus.DEGRADED

    s.report_success("p1")
    assert s.check("p1").status == HealthStatus.DEGRADED  # need 2 successes

    s.report_success("p1")
    assert s.check("p1").status == HealthStatus.HEALTHY  # recovered!


def test_failure_with_cooldown():
    s = QuotaSensor()
    s.report_failure("p1", "rate_limited", cooldown_seconds=300)
    h = s.check("p1")
    assert h.status == HealthStatus.COOLDOWN
    assert h.cooldown_until > time.time()


def test_check_all():
    s = QuotaSensor()
    s.report_failure("p1", "timeout")
    s.report_failure("p1", "timeout")
    s.report_success("p2")
    all_health = s.check_all()
    assert "p1" in all_health
    assert "p2" in all_health


def test_reset():
    s = QuotaSensor()
    s.report_failure("p1", "timeout")
    s.report_failure("p1", "timeout")
    assert s.check("p1").status == HealthStatus.DEGRADED
    s.reset("p1")
    assert s.check("p1").status == HealthStatus.HEALTHY


def test_tier_health_to_dict():
    h = TierHealth(provider_id="test", status=HealthStatus.DEGRADED)
    d = h.to_dict()
    assert d["provider_id"] == "test"
    assert d["status"] == "degraded"
