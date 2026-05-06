"""Unit tests for the Paperclip HTTP service layer."""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Ensure dev key is set before importing service
os.environ["PAPERCLIP_API_KEYS"] = "dev-key:admin"
os.environ["PAPERCLIP_PROBE_INTERVAL_SECONDS"] = "0"

from runtime_allocator.service import app


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


class TestHealth:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "p4.0"


class TestMetrics:
    def test_metrics_endpoint(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "paperclip_executions_total" in response.text


class TestAuth:
    def test_missing_api_key_blocked(self, client):
        response = client.post("/v1/execute", json={"task_class": "dtc_copy"})
        assert response.status_code == 401

    def test_invalid_api_key_blocked(self, client):
        response = client.post(
            "/v1/execute",
            json={"task_class": "dtc_copy"},
            headers={"X-API-Key": "bad-key"},
        )
        assert response.status_code == 403

    def test_valid_api_key_allowed(self, client):
        response = client.post(
            "/v1/execute",
            json={"task_class": "dtc_copy", "messages": [{"role": "user", "content": "test"}]},
            headers={"X-API-Key": "dev-key"},
        )
        # Should pass auth; actual execution mocked
        assert response.status_code == 200


class TestExecute:
    def test_execute_unknown_task_class(self, client):
        response = client.post(
            "/v1/execute",
            json={
                "task_class": "unknown_xyz",
                "messages": [{"role": "user", "content": "test"}],
            },
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True  # mocked returns success

    def test_execute_response_structure(self, client):
        response = client.post(
            "/v1/execute",
            json={
                "task_class": "dtc_copy",
                "messages": [{"role": "user", "content": "test"}],
            },
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "provider_id" in data
        assert "latency_ms" in data


class TestPreflight:
    def test_preflight_read_only_task_allowed(self, client):
        response = client.post(
            "/v1/preflight",
            json={
                "task_prompt": "Analyze market data",
                "agent_slug": "finbot",
                "task_type": "finbot_fundamental",
                "model_lane": "high",
            },
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "allowed"

    def test_preflight_model_lane_mismatch_blocked(self, client):
        response = client.post(
            "/v1/preflight",
            json={
                "task_prompt": "Analyze market data",
                "agent_slug": "finbot",
                "task_type": "finbot_fundamental",
                "model_lane": "cheap",
            },
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"
        assert "model_lane_mismatch" in data["reason_codes"]


class TestCloseout:
    def test_closeout_read_only_no_changes_allowed(self, client):
        response = client.post(
            "/v1/closeout",
            json={
                "task_type": "finbot_fundamental",
                "write_scope": "read_only",
                "files_changed": [],
                "files_declared": [],
                "evidence_spans": [],
            },
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "allowed"

    def test_closeout_read_only_with_changes_blocked(self, client):
        response = client.post(
            "/v1/closeout",
            json={
                "task_type": "finbot_fundamental",
                "write_scope": "read_only",
                "files_changed": ["report.md"],
                "files_declared": [],
                "evidence_spans": [],
            },
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"
        assert "read_only_violation" in data["reason_codes"]


class TestProviderHealth:
    def test_provider_health_endpoint(self, client):
        response = client.get(
            "/v1/health/providers",
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data


class TestBilling:
    def test_billing_daily_endpoint(self, client):
        response = client.get(
            "/v1/billing/daily",
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_calls" in data
        assert "total_cost_usd" in data

    def test_billing_alerts_endpoint(self, client):
        response = client.get(
            "/v1/billing/alerts?daily_budget_usd=100.0",
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "alert" in data


class TestSummary:
    def test_summary_admin_only(self, client):
        response = client.get(
            "/v1/summary",
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "budgets" in data
        assert "health" in data
        assert "events_today" in data
