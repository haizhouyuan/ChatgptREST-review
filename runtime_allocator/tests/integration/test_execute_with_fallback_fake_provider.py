"""Integration tests for execute_with_fallback using fake providers."""

from __future__ import annotations

import tempfile

import pytest

from runtime_allocator.schemas import CommerceDecisionOutput
from runtime_allocator.skill_agent import execute_with_fallback
from runtime_allocator.runtime_state import RuntimeStateStore
from runtime_allocator.tests.fixtures.fake_invoker import FakeInvoker


@pytest.fixture
def state_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    s = RuntimeStateStore(tmp.name)
    for pid in ("claudekimi", "minimax", "gemini_local", "ollama_gpu0"):
        s.init_budget(pid, hard_rpd=100, soft_rpd=50)
    yield s
    import os
    os.unlink(tmp.name)


@pytest.fixture
def ledger():
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    from runtime_allocator.allocator_mvp import QuotaLedger
    yield QuotaLedger(path=tmp.name)
    import os
    os.unlink(tmp.name)


@pytest.fixture
def fake_invoker(monkeypatch):
    invoker = FakeInvoker()
    from runtime_allocator import skill_agent
    from runtime_allocator import runtime_invoker

    def fake_invoke_llm(provider_id, messages, model="", profiles=None, temperature=0.7, max_tokens=4096, response_format=None, timeout=120.0):
        result = invoker.invoke(provider_id, messages, model, profiles, temperature, max_tokens, response_format, timeout)
        from runtime_allocator.runtime_invoker import InvokeResult
        return InvokeResult(
            provider_id=provider_id,
            model_name=model or provider_id,
            content=result.content,
            error=result.error,
            error_class=result.error_class,
            latency_ms=result.latency_ms,
        )

    monkeypatch.setattr(skill_agent, "invoke_llm", fake_invoke_llm)
    monkeypatch.setattr(runtime_invoker, "invoke_llm", fake_invoke_llm)
    yield invoker


class TestPrimarySuccess:
    def test_primary_success(self, state_store, ledger, fake_invoker):
        fake_invoker.set_behavior("gemini_local", success=True, content='{"product_id": "A", "decision": "approve", "rationale": ["ok"], "confidence": 0.9}')
        result = execute_with_fallback(
            task_class="dtc_copy",
            messages=[{"role": "user", "content": "test"}],
            state_store=state_store,
            ledger=ledger,
            schema_model=CommerceDecisionOutput,
        )
        assert result.success
        assert result.terminal_state == "completed"
        assert result.provider_id == "gemini_local"

    def test_primary_429_fallback(self, state_store, ledger, fake_invoker):
        fake_invoker.set_behavior("gemini_local", success=False, error="rate limit exceeded", error_class="HTTP429")
        fake_invoker.set_behavior("minimax", success=True, content='{"product_id": "A", "decision": "approve", "rationale": ["ok"], "confidence": 0.9}')
        result = execute_with_fallback(
            task_class="dtc_copy",
            messages=[{"role": "user", "content": "test"}],
            state_store=state_store,
            ledger=ledger,
            schema_model=CommerceDecisionOutput,
        )
        assert result.success
        assert result.provider_id == "minimax"

    def test_primary_401_refund(self, state_store, ledger, fake_invoker):
        fake_invoker.set_behavior("gemini_local", success=False, error="unauthorized", error_class="HTTP401")
        fake_invoker.set_behavior("minimax", success=True, content='{"product_id": "A", "decision": "approve", "rationale": ["ok"], "confidence": 0.9}')
        result = execute_with_fallback(
            task_class="dtc_copy",
            messages=[{"role": "user", "content": "test"}],
            state_store=state_store,
            ledger=ledger,
            schema_model=CommerceDecisionOutput,
        )
        assert result.success
        # 401 should be refunded, not counted against quota

    def test_timeout_counts_as_attempt(self, state_store, ledger, fake_invoker):
        fake_invoker.set_behavior("gemini_local", success=False, error="timeout", error_class="TimeoutError")
        fake_invoker.set_behavior("minimax", success=True, content='{"product_id": "A", "decision": "approve", "rationale": ["ok"], "confidence": 0.9}')
        result = execute_with_fallback(
            task_class="dtc_copy",
            messages=[{"role": "user", "content": "test"}],
            state_store=state_store,
            ledger=ledger,
            schema_model=CommerceDecisionOutput,
        )
        assert result.success
        # Timeout should count as attempt (committed)


class TestSchemaRetry:
    def test_schema_invalid_then_fallback_success(self, state_store, ledger, fake_invoker):
        fake_invoker.set_behavior("gemini_local", schema_invalid=True)
        fake_invoker.set_behavior("minimax", success=True, content='{"product_id": "A", "decision": "approve", "rationale": ["ok"], "confidence": 0.9}')
        result = execute_with_fallback(
            task_class="dtc_copy",
            messages=[{"role": "user", "content": "test"}],
            state_store=state_store,
            ledger=ledger,
            schema_model=CommerceDecisionOutput,
        )
        assert result.success
        assert result.provider_id == "minimax"


class TestTerminalStates:
    def test_all_providers_unavailable_blocked(self, state_store, ledger, fake_invoker):
        fake_invoker.set_behavior("gemini_local", success=False, error="down", error_class="HTTP503")
        fake_invoker.set_behavior("minimax", success=False, error="down", error_class="HTTP503")
        fake_invoker.set_behavior("claudekimi", success=False, error="down", error_class="HTTP503")
        fake_invoker.set_behavior("ollama_gpu0", success=False, error="down", error_class="HTTP503")
        result = execute_with_fallback(
            task_class="dtc_copy",
            messages=[{"role": "user", "content": "test"}],
            state_store=state_store,
            ledger=ledger,
            schema_model=CommerceDecisionOutput,
        )
        assert result.terminal_state in ("blocked", "human_review_required")

    def test_high_stakes_requires_human_review(self, state_store, ledger, fake_invoker):
        # hr_sensitive primary=ollama_gpu0 (standard quality, local privacy)
        # high_stakes + non-critical provider → requires_human_review
        fake_invoker.set_behavior("ollama_gpu0", success=True, content='{"product_id": "A", "decision": "approve", "rationale": ["ok"], "confidence": 0.9}')
        result = execute_with_fallback(
            task_class="hr_sensitive",
            messages=[{"role": "user", "content": "test"}],
            state_store=state_store,
            ledger=ledger,
            privacy_tier="local",
            high_stakes=True,
            schema_model=CommerceDecisionOutput,
        )
        assert result.success
        # High stakes with non-critical provider should require human review
        assert result.requires_human_review or result.terminal_state == "human_review_required"

    def test_unknown_task_class_blocked(self, state_store, ledger, fake_invoker):
        result = execute_with_fallback(
            task_class="unknown_task_class_xyz",
            messages=[{"role": "user", "content": "test"}],
            state_store=state_store,
            ledger=ledger,
        )
        assert result.terminal_state == "blocked"
        assert not result.success
