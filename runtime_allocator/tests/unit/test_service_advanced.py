"""Advanced service tests: rate limiting, gate integration, metrics."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["PAPERCLIP_API_KEYS"] = "dev-key:admin"
os.environ["PAPERCLIP_RATE_LIMIT_RPS"] = "100"
os.environ["PAPERCLIP_RATE_LIMIT_BURST"] = "200"
os.environ["PAPERCLIP_PROBE_INTERVAL_SECONDS"] = "0"

from runtime_allocator.service import _rate_limiter, app


def _reset_rate_limiter():
    _rate_limiter.rps = 100.0
    _rate_limiter.burst = 200
    _rate_limiter.reset_all()


@pytest.fixture
def client(monkeypatch):
    """TestClient with mocked execute_with_fallback to avoid real provider calls."""
    import runtime_allocator.service as svc
    import runtime_allocator.skill_agent as sa

    def _fake_execute(*args, **kwargs):
        return sa.SkillResult(
            provider_id="mock",
            model_name="mock-model",
            content='{"result": "ok"}',
            success=True,
            terminal_state="completed",
            latency_ms=10.0,
        )

    monkeypatch.setattr(svc, "execute_with_fallback", _fake_execute)
    return TestClient(app)


class TestRateLimiting:
    def setup_method(self):
        _reset_rate_limiter()

    def test_high_volume_requests_allowed(self, client):
        # With burst=200, first 200 should pass
        for i in range(50):
            response = client.post(
                "/v1/execute",
                json={"task_class": "dtc_copy", "messages": [{"role": "user", "content": "test"}]},
                headers={"X-API-Key": "dev-key"},
            )
            assert response.status_code == 200


class TestGateIntegration:
    def setup_method(self):
        _reset_rate_limiter()

    def test_preflight_blocks_read_only_violation(self, client):
        response = client.post(
            "/v1/execute",
            json={
                "task_class": "finbot_fundamental",
                "messages": [{"role": "user", "content": "test"}],
                "write_scope": "mutate",
            },
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["preflight_status"] == "blocked"
        assert not data["success"]

    def test_preflight_allows_read_only(self, client):
        response = client.post(
            "/v1/execute",
            json={
                "task_class": "finbot_fundamental",
                "messages": [{"role": "user", "content": "test"}],
                "write_scope": "read_only",
            },
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["preflight_status"] == "allowed"


class TestMetricsAfterRequests:
    def setup_method(self):
        _reset_rate_limiter()

    def test_prometheus_metrics_updated(self, client):
        # Make a request to generate metrics
        client.post(
            "/v1/execute",
            json={"task_class": "unknown_task_xyz", "messages": [{"role": "user", "content": "test"}]},
            headers={"X-API-Key": "dev-key"},
        )
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "paperclip_gate_checks_total" in response.text
