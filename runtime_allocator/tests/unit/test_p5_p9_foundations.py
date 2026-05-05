"""Foundation tests for P5-P9 modules.

Covers cost attribution, plugin interface, intelligence layer,
compliance, and federation stubs.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from runtime_allocator.runtime_state import RuntimeStateStore
from runtime_allocator.cost_attribution import CostAttribution
from runtime_allocator.intelligence import PredictiveRouter, AnomalyDetector
from runtime_allocator.compliance import AuditTrailExporter, RetentionPolicy
from runtime_allocator.federation import EdgeNode, EdgeRegistry, FederationClient
from runtime_allocator.plugin_interface import (
    ProviderAdapter,
    SkillContract,
    SkillPlugin,
    SkillRegistry,
)


@pytest.fixture
def temp_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    store = RuntimeStateStore(tmp.name)
    yield store
    os.unlink(tmp.name)


class TestP5CostAttribution:
    def test_daily_summary_empty(self, temp_store):
        ca = CostAttribution(temp_store)
        summary = ca.daily_summary()
        assert summary["total_calls"] == 0
        assert summary["total_cost_usd"] == 0.0

    def test_alert_under_budget(self, temp_store):
        ca = CostAttribution(temp_store)
        alert = ca.alert_if_over_budget("acme", daily_budget_usd=100.0)
        assert alert is None


class TestP6PluginInterface:
    def test_registry_empty(self):
        reg = SkillRegistry()
        assert reg.list_skills() == []
        assert reg.list_adapters() == []

    def test_skill_contract_fields(self):
        sc = SkillContract(skill_id="test_skill", version="1.0.0")
        assert sc.skill_id == "test_skill"
        assert sc.required_providers == []


class TestP7Intelligence:
    def test_predictive_router_empty_store(self, temp_store):
        router = PredictiveRouter(temp_store)
        scores = router.score_providers()
        assert scores == {}

    def test_predictive_router_recommend(self, temp_store):
        router = PredictiveRouter(temp_store)
        best = router.recommend_provider(["claudekimi", "minimax"])
        # Empty store returns first candidate with default score
        assert best in ("claudekimi", "minimax")

    def test_anomaly_detector_empty(self, temp_store):
        detector = AnomalyDetector(temp_store)
        anomalies = detector.check_recent_anomalies()
        assert anomalies == []


class TestP8Compliance:
    def test_audit_export_empty(self, temp_store):
        exporter = AuditTrailExporter(temp_store)
        path = exporter.export_range()
        assert path.exists()
        text = path.read_text()
        assert text == ""
        path.unlink()

    def test_retention_policy_empty(self, temp_store):
        policy = RetentionPolicy(temp_store)
        result = policy.apply(retention_days=30)
        assert result["events_deleted"] == 0
        assert result["reservations_deleted"] == 0


class TestP9Federation:
    def test_edge_registry(self):
        reg = EdgeRegistry()
        node = EdgeNode(
            node_id="edge-1",
            region="us-west",
            endpoint="http://edge1.local:8080",
            model_ids=["qwen2.5:32b"],
        )
        reg.register(node)
        assert len(reg.list_nodes()) == 1
        assert reg.get_node("edge-1").region == "us-west"
        reg.deregister("edge-1")
        assert len(reg.list_nodes()) == 0

    def test_federation_client_forward_success(self, monkeypatch):
        class FakeResp:
            status_code = 200
            text = '{"success": true}'
            def json(self):
                return {"success": True, "content": "hello", "provider_id": "claudekimi", "latency_ms": 1500}

        class FakeClient:
            def post(self, url, **kwargs):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", lambda **kw: FakeClient())
        client = FederationClient("http://remote:8080", api_key="secret")
        resp = client.forward_request("dtc_copy", [{"role": "user", "content": "test"}])
        assert resp["status"] == "forwarded"
        assert resp["success"] is True
        assert resp["content"] == "hello"

    def test_federation_client_forward_error(self, monkeypatch):
        import httpx

        class FakeClient:
            def post(self, url, **kwargs):
                raise httpx.ConnectError("no route")

        monkeypatch.setattr("httpx.Client", lambda **kw: FakeClient())
        client = FederationClient("http://remote:8080")
        resp = client.forward_request("dtc_copy", [{"role": "user", "content": "test"}])
        assert resp["status"] == "error"
        assert "no route" in resp["error"]

    def test_federation_health_success(self, monkeypatch):
        class FakeResp:
            status_code = 200
            def json(self):
                return {"status": "healthy"}

        class FakeClient:
            def get(self, url, **kwargs):
                return FakeResp()

        monkeypatch.setattr("httpx.Client", lambda **kw: FakeClient())
        client = FederationClient("http://remote:8080")
        health = client.health_check()
        assert health["reachable"] is True
        assert health["healthy"] is True

    def test_federation_health_unreachable(self, monkeypatch):
        import httpx

        class FakeClient:
            def get(self, url, **kwargs):
                raise httpx.ConnectError("no route")

        monkeypatch.setattr("httpx.Client", lambda **kw: FakeClient())
        client = FederationClient("http://remote:8080")
        health = client.health_check()
        assert health["reachable"] is False
        assert "no route" in health["error"]
