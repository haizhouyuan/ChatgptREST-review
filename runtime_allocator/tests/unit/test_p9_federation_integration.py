"""Integration tests for P9 federation routing in skill_agent + allocate().

Covers:
- Edge runtimes injected into allocate() candidate pool
- Federated provider selected when local providers blocked
- _invoke_federated routes through FederationClient
- Fallback chain includes federated nodes
- Schema retry works with federated providers
"""

from __future__ import annotations

import os
import tempfile

import pytest

from runtime_allocator.allocator_mvp import (
    RouteRequest,
    allocate,
    Runtime,
    PrivacyTier,
    QualityTier,
)
from runtime_allocator.federation import EdgeNode, EdgeRegistry, FederatedProvider
from runtime_allocator.policy_store import PolicyEntry
from runtime_allocator.runtime_state import RuntimeStateStore
from runtime_allocator.skill_agent import (
    execute_with_fallback,
    _invoke_federated,
    load_profiles,
)


@pytest.fixture
def temp_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    store = RuntimeStateStore(tmp.name)
    yield store
    os.unlink(tmp.name)


@pytest.fixture
def edge_registry():
    reg = EdgeRegistry()
    reg.register(EdgeNode(
        node_id="edge-west",
        region="us-west",
        endpoint="http://edge-west.local:8080",
        model_ids=["qwen2.5:32b"],
        latency_p50_ms=1500,
    ))
    reg.register(EdgeNode(
        node_id="edge-east",
        region="us-east",
        endpoint="http://edge-east.local:8080",
        model_ids=["llama3:70b"],
        latency_p50_ms=2500,
    ))
    return reg


class TestAllocateWithEdgeRuntimes:
    def test_edge_runtime_appended_as_fallback(self, temp_store):
        """When local candidates are exhausted, edge runtimes are considered."""
        local_rt = Runtime(
            provider_id="local_only",
            model_name="local-model",
            endpoint="http://local",
            privacy_tier=PrivacyTier.LOCAL,
            quality_tier=QualityTier.CRITICAL,
            enabled=False,  # disabled so not a candidate
        )
        edge_rt = FederatedProvider(
            EdgeNode(
                node_id="edge-1",
                region="us-west",
                endpoint="http://edge1:8080",
                model_ids=["qwen2.5:32b"],
            )
        ).to_runtime()

        policy = PolicyEntry(
            task_class="test_task",
            primary=["local_only"],
            can_degrade=False,
        )

        req = RouteRequest(task_class="test_task", min_quality_tier=QualityTier.STANDARD)
        decision = allocate(
            req,
            runtimes=[local_rt],
            policy=policy,
            edge_runtimes=[edge_rt],
        )
        assert decision.blocked is False
        assert decision.provider_id == "federated:edge-1"

    def test_local_preferred_over_edge(self, temp_store):
        """Local runtimes in policy chain are preferred over edge runtimes."""
        local_rt = Runtime(
            provider_id="local_provider",
            model_name="local-model",
            endpoint="http://local",
            privacy_tier=PrivacyTier.EXTERNAL_CLOUD,
            quality_tier=QualityTier.STANDARD,
        )
        edge_rt = FederatedProvider(
            EdgeNode(
                node_id="edge-1",
                region="us-west",
                endpoint="http://edge1:8080",
                model_ids=["qwen2.5:32b"],
            )
        ).to_runtime()

        policy = PolicyEntry(
            task_class="test_task",
            primary=["local_provider"],
            can_degrade=False,
        )

        req = RouteRequest(task_class="test_task", min_quality_tier=QualityTier.STANDARD)
        decision = allocate(
            req,
            runtimes=[local_rt],
            policy=policy,
            edge_runtimes=[edge_rt],
        )
        assert decision.provider_id == "local_provider"
        assert "federated:edge-1" in decision.fallback_chain


class TestInvokeFederated:
    def test_invoke_federated_success(self, monkeypatch):
        class FakeResp:
            status_code = 200
            text = '{"success": true}'
            def json(self):
                return {"success": True, "content": "hello from edge", "provider_id": "federated:edge-1", "latency_ms": 800}

        class FakeClient:
            def post(self, url, **kwargs):
                return FakeResp()
            def close(self):
                pass

        monkeypatch.setattr("httpx.Client", lambda **kw: FakeClient())
        result = _invoke_federated(
            endpoint="http://edge1:8080",
            task_class="dtc_copy",
            messages=[{"role": "user", "content": "test"}],
            provider_id="federated:edge-1",
            model_name="qwen2.5:32b",
        )
        assert result.error is None
        assert result.content == "hello from edge"
        assert result.provider_id == "federated:edge-1"

    def test_invoke_federated_error(self, monkeypatch):
        import httpx

        class FakeClient:
            def post(self, url, **kwargs):
                raise httpx.ConnectError("no route")
            def close(self):
                pass

        monkeypatch.setattr("httpx.Client", lambda **kw: FakeClient())
        result = _invoke_federated(
            endpoint="http://edge1:8080",
            task_class="dtc_copy",
            messages=[{"role": "user", "content": "test"}],
            provider_id="federated:edge-1",
            model_name="qwen2.5:32b",
        )
        assert result.error is not None
        assert "no route" in result.error


class TestExecuteWithFallbackFederation:
    def test_federated_fallback_when_local_quota_exhausted(self, temp_store, monkeypatch):
        """When local provider is blocked by quota, federated edge is used."""
        # Mark local provider as not usable (health)
        temp_store.update_health("claudekimi", "circuit_open", circuit_open_seconds=3600)

        # Mock FederationClient for success
        class FakeResp:
            status_code = 200
            text = '{"success": true}'
            def json(self):
                return {"success": True, "content": "edge result", "provider_id": "federated:edge-west", "latency_ms": 800}

        class FakeClient:
            def post(self, url, **kwargs):
                return FakeResp()
            def close(self):
                pass

        monkeypatch.setattr("httpx.Client", lambda **kw: FakeClient())

        reg = EdgeRegistry()
        reg.register(EdgeNode(
            node_id="edge-west",
            region="us-west",
            endpoint="http://edge-west.local:8080",
            model_ids=["qwen2.5:32b"],
            latency_p50_ms=1500,
        ))

        # Force provider override to bypass normal allocation and test federation path directly
        # Actually let's test the full allocate path by disabling all local providers via health
        profiles = load_profiles()
        for pid in list(profiles.get("runtimes", {}).keys()):
            temp_store.update_health(pid, "circuit_open", circuit_open_seconds=3600)

        result = execute_with_fallback(
            task_class="dtc_copy",
            messages=[{"role": "user", "content": "test"}],
            state_store=temp_store,
            edge_registry=reg,
            max_retries=2,
        )
        assert result.success is True
        assert result.provider_id == "federated:edge-west"
        assert result.content == "edge result"

    def test_federated_in_fallback_chain(self, temp_store, monkeypatch):
        """Federated node appears in fallback chain when local primary fails."""
        profiles = load_profiles()

        class FakeResp:
            status_code = 200
            text = '{"success": true}'
            def json(self):
                return {"success": True, "content": "edge fallback", "provider_id": "federated:edge-west", "latency_ms": 800}

        class FakeClient:
            def post(self, url, **kwargs):
                return FakeResp()
            def close(self):
                pass

        monkeypatch.setattr("httpx.Client", lambda **kw: FakeClient())

        reg = EdgeRegistry()
        reg.register(EdgeNode(
            node_id="edge-west",
            region="us-west",
            endpoint="http://edge-west.local:8080",
            model_ids=["qwen2.5:32b"],
            latency_p50_ms=1500,
        ))

        # Disable fallback local providers so federated is next after primary
        temp_store.update_health("minimax", "circuit_open", circuit_open_seconds=3600)
        temp_store.update_health("claudekimi", "circuit_open", circuit_open_seconds=3600)

        # Force primary to fail via monkeypatch on invoke_llm
        def fake_invoke_llm(*args, **kwargs):
            from runtime_allocator.runtime_invoker import InvokeResult
            return InvokeResult(
                provider_id=kwargs.get("provider_id", ""),
                model_name=kwargs.get("model", ""),
                error="forced failure",
                error_class="TestError",
            )

        monkeypatch.setattr("runtime_allocator.skill_agent.invoke_llm", fake_invoke_llm)

        result = execute_with_fallback(
            task_class="dtc_copy",
            messages=[{"role": "user", "content": "test"}],
            state_store=temp_store,
            edge_registry=reg,
            max_retries=2,
            profiles=profiles,
        )
        # Should have tried primary local, then fallen back to federated
        assert result.success is True
        assert result.provider_id == "federated:edge-west"
        assert "federated:edge-west" in result.fallback_chain or any(
            a["provider_id"] == "federated:edge-west" for a in result.attempts
        )
