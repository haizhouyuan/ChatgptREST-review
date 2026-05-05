"""Unit tests for the Paperclip HTTP service layer."""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Ensure dev key is set before importing service
os.environ["PAPERCLIP_API_KEYS"] = "dev-key:admin"

from runtime_allocator.service import app

client = TestClient(app)


class TestHealth:
    def test_health_endpoint(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "p4.0"


class TestMetrics:
    def test_metrics_endpoint(self):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "paperclip_executions_total" in response.text


class TestAuth:
    def test_missing_api_key_blocked(self):
        response = client.post("/v1/execute", json={"task_class": "dtc_copy"})
        assert response.status_code == 401

    def test_invalid_api_key_blocked(self):
        response = client.post(
            "/v1/execute",
            json={"task_class": "dtc_copy"},
            headers={"X-API-Key": "bad-key"},
        )
        assert response.status_code == 403

    def test_valid_api_key_allowed(self):
        response = client.post(
            "/v1/execute",
            json={"task_class": "dtc_copy", "messages": [{"role": "user", "content": "test"}]},
            headers={"X-API-Key": "dev-key"},
        )
        # Should pass auth; actual execution may fail due to no providers
        assert response.status_code in (200, 500)


class TestExecute:
    def test_execute_unknown_task_class(self):
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
        assert not data["success"]
        # Either blocked by allocator or error from missing profiles
        assert data["terminal_state"] == "blocked" or data["error"] != ""

    def test_execute_response_structure(self):
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


class TestSummary:
    def test_summary_admin_only(self):
        response = client.get(
            "/v1/summary",
            headers={"X-API-Key": "dev-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "budgets" in data
        assert "health" in data
        assert "events_today" in data
