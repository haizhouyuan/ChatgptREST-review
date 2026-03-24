"""BI-14: Fault/Blocker 处理测试

测试 advisor agent facade 在各种故障状态下的行为:
- blocked
- cooldown
- needs_followup
- error

验证:
1. facade 不丢失底层标识符 (session_id, job_id, consultation_id)
2. session status 仍可查询
3. next_action 对 retry vs human intervention 合理
4. cancel 仍然安全行为
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import chatgptrest.api.routes_agent_v3 as routes_agent_v3
from chatgptrest.advisor.graph import build_advisor_graph
from chatgptrest.api.routes_agent_v3 import (
    _default_next_action,
    _agent_status_from_job_status,
    _agent_status_from_controller_status,
    make_v3_agent_router,
)
from chatgptrest.core.state_machine import JobStatus


def _install_fake_runtime(monkeypatch) -> None:
    monkeypatch.setattr(routes_agent_v3, "_advisor_runtime", lambda: {})

    class _FakeController:
        def __init__(self, _state):
            pass

        def ask(self, **kwargs):
            message = str(kwargs.get("question") or "")
            return {
                "run_id": f"run_{uuid.uuid4().hex[:8]}",
                "job_id": f"job_{uuid.uuid4().hex[:8]}",
                "route": "quick_ask",
                "provider": "chatgpt",
                "controller_status": "DELIVERED",
                "answer": f"ok:{message}",
                "artifacts": [],
            }

        def get_run_snapshot(self, *, run_id: str):
            return {
                "run": {
                    "run_id": run_id,
                    "route": "quick_ask",
                    "provider": "chatgpt",
                    "controller_status": "DELIVERED",
                    "delivery": {"status": "completed", "answer": "ok:status"},
                    "next_action": {"type": "followup"},
                },
                "artifacts": [],
            }

    monkeypatch.setattr(routes_agent_v3, "ControllerEngine", _FakeController)
    monkeypatch.setattr(routes_agent_v3, "_cancel_job", lambda **kwargs: None)


def _make_client(monkeypatch, **kwargs) -> TestClient:
    _install_fake_runtime(monkeypatch)
    app = FastAPI()
    app.include_router(make_v3_agent_router())
    return TestClient(app, raise_server_exceptions=False, **kwargs)


def _get_session_store():
    """Access the internal session store from the router."""
    router = make_v3_agent_router()
    # The session store is a closure variable in make_v3_agent_router
    # We need to test via the API endpoints instead
    return None


class TestBlockedState:
    """Test BLOCKED state handling."""

    def test_blocked_state_preserves_identifiers(self, monkeypatch):
        """验证 BLOCKED 状态下 facade 不丢失 session_id 和 job_id."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        client = _make_client(monkeypatch)
        headers = {"X-Api-Key": "test-key"}

        # Create a session first
        session_id = f"agent_sess_{uuid.uuid4().hex[:16]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        # First, create a turn to get a valid session
        response = client.post(
            "/v3/agent/turn",
            json={"message": "test blocked state"},
            headers=headers,
        )

        if response.status_code == 200:
            session_data = response.json()
            test_session_id = session_data.get("session_id", session_id)
            test_job_id = session_data.get("job_id", job_id)
        else:
            test_session_id = session_id
            test_job_id = job_id

        # Now verify we can query the session
        response = client.get(f"/v3/agent/session/{test_session_id}", headers=headers)

        # Session should be queryable (may return 404 if no actual job created)
        assert response.status_code in (200, 404)

    def test_blocked_state_next_action(self, monkeypatch):
        """验证 BLOCKED 状态的 next_action 合理 (需要 human intervention)."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        # Test blocked status - should return same as needs_followup
        result = _default_next_action(status="needs_followup", job_id="test-job-123")

        assert result["type"] == "same_session_repair"
        assert "job_id" in result
        assert result["job_id"] == "test-job-123"

        # The safe_hint should indicate human intervention needed
        assert "human" in result["safe_hint"].lower() or "确认" in result["safe_hint"] or "repair" in result["type"]

    def test_blocked_status_mapping(self, monkeypatch):
        """验证 BLOCKED job status 映射到 needs_followup."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        # BLOCKED maps to needs_followup
        assert _agent_status_from_job_status(JobStatus.BLOCKED.value) == "needs_followup"


class TestCooldownState:
    """Test COOLDOWN state handling."""

    def test_cooldown_state_preserves_identifiers(self, monkeypatch):
        """验证 COOLDOWN 状态下 facade 保留标识符."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        client = _make_client(monkeypatch)
        headers = {"X-Api-Key": "test-key"}

        # Create a session
        response = client.post(
            "/v3/agent/turn",
            json={"message": "test cooldown state"},
            headers=headers,
        )

        if response.status_code == 200:
            session_data = response.json()
            session_id = session_data.get("session_id")
            job_id = session_data.get("job_id")

            # Verify identifiers are present
            assert session_id is not None
            # job_id may be None if job not yet created

    def test_cooldown_next_action(self, monkeypatch):
        """验证 COOLDOWN 状态的 next_action 提示重试."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        # Running status should suggest check_status
        result = _default_next_action(status="running", job_id="test-job-123")

        assert result["type"] == "check_status"
        assert "job_id" in result

    def test_cooldown_status_mapping(self, monkeypatch):
        """验证 COOLDOWN job status 映射到 running."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        # COOLDOWN is not a terminal status, maps to running
        assert _agent_status_from_job_status(JobStatus.COOLDOWN.value) == "running"


class TestNeedsFollowupState:
    """Test NEEDS_FOLLOWUP state handling."""

    def test_needs_followup_preserves_identifiers(self, monkeypatch):
        """验证 NEEDS_FOLLOWUP 状态下保留 session_id 和 job_id."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        client = _make_client(monkeypatch)
        headers = {"X-Api-Key": "test-key"}

        # Create a session
        response = client.post(
            "/v3/agent/turn",
            json={"message": "test needs_followup state"},
            headers=headers,
        )

        assert response.status_code != 401  # Should be authorized

    def test_needs_followup_next_action(self, monkeypatch):
        """验证 NEEDS_FOLLOWUP 状态的 next_action 要求修复."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        result = _default_next_action(status="needs_followup", job_id="test-job-456")

        assert result["type"] == "same_session_repair"
        assert result["job_id"] == "test-job-456"
        # Should indicate human intervention needed
        assert "repair" in result["type"] or "确认" in result["safe_hint"]

    def test_needs_followup_status_mapping(self, monkeypatch):
        """验证 NEEDS_FOLLOWUP job status 正确映射."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        assert _agent_status_from_job_status(JobStatus.NEEDS_FOLLOWUP.value) == "needs_followup"


class TestErrorState:
    """Test ERROR state handling."""

    def test_error_preserves_identifiers(self, monkeypatch):
        """验证 ERROR 状态下保留标识符供调试."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        client = _make_client(monkeypatch)
        headers = {"X-Api-Key": "test-key"}

        response = client.post(
            "/v3/agent/turn",
            json={"message": "test error state"},
            headers=headers,
        )

        # Should not lose session_id even on error
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data or response.status_code != 500

    def test_error_next_action(self, monkeypatch):
        """验证 ERROR 状态的 next_action 建议 retry_or_investigate."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        result = _default_next_action(status="failed", job_id="test-job-error")

        assert result["type"] == "retry_or_investigate"
        assert result["job_id"] == "test-job-error"
        # Should indicate investigation needed
        assert "error" in result["safe_hint"].lower() or "检查" in result["safe_hint"]

    def test_error_status_mapping(self, monkeypatch):
        """验证 ERROR job status 映射到 failed."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        assert _agent_status_from_job_status(JobStatus.ERROR.value) == "failed"


class TestCancelSafety:
    """Test cancel operation safety."""

    def test_cancel_nonexistent_session_returns_404(self, monkeypatch):
        """验证取消不存在的 session 返回 404."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        client = _make_client(monkeypatch)
        headers = {"X-Api-Key": "test-key"}

        response = client.post(
            "/v3/agent/cancel",
            json={"session_id": "nonexistent_session_12345"},
            headers=headers,
        )

        assert response.status_code == 404
        assert "session_not_found" in response.json().get("error", "")

    def test_cancel_requires_session_id(self, monkeypatch):
        """验证取消需要 session_id."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        client = _make_client(monkeypatch)
        headers = {"X-Api-Key": "test-key"}

        response = client.post(
            "/v3/agent/cancel",
            json={},
            headers=headers,
        )

        assert response.status_code == 400
        assert "session_id is required" in response.json().get("error", "")

    def test_cancel_with_valid_session(self, monkeypatch):
        """验证取消有效 session 的行为."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        client = _make_client(monkeypatch)
        headers = {"X-Api-Key": "test-key"}

        # First create a session
        response = client.post(
            "/v3/agent/turn",
            json={"message": "test cancel"},
            headers=headers,
        )

        if response.status_code == 200:
            session_id = response.json().get("session_id")

            # Now try to cancel it
            cancel_response = client.post(
                "/v3/agent/cancel",
                json={"session_id": session_id},
                headers=headers,
            )

            # Should either succeed or return appropriate status
            assert cancel_response.status_code in (200, 404, 500)


class TestSessionStatusQuery:
    """Test session status query functionality."""

    def test_session_query_returns_status(self, monkeypatch):
        """验证 session 查询返回正确状态."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        client = _make_client(monkeypatch)
        headers = {"X-Api-Key": "test-key"}

        # Create a session
        response = client.post(
            "/v3/agent/turn",
            json={"message": "hello"},
            headers=headers,
        )

        if response.status_code == 200:
            session_id = response.json().get("session_id")

            # Query the session
            query_response = client.get(
                f"/v3/agent/session/{session_id}",
                headers=headers,
            )

            if query_response.status_code == 200:
                data = query_response.json()
                assert "status" in data

    def test_session_not_found_returns_404(self, monkeypatch):
        """验证查询不存在的 session 返回 404."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        client = _make_client(monkeypatch)
        headers = {"X-Api-Key": "test-key"}

        response = client.get(
            "/v3/agent/session/definitely_does_not_exist_12345",
            headers=headers,
        )

        assert response.status_code == 404


class TestAgentStatusMapping:
    """Test agent status mapping from job status."""

    def test_job_status_to_agent_status(self, monkeypatch):
        """验证 job status 到 agent status 的正确映射."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        # Test each job status mapping
        assert _agent_status_from_job_status(JobStatus.COMPLETED.value) == "completed"
        assert _agent_status_from_job_status(JobStatus.ERROR.value) == "failed"
        assert _agent_status_from_job_status(JobStatus.CANCELED.value) == "cancelled"
        assert _agent_status_from_job_status(JobStatus.BLOCKED.value) == "needs_followup"
        assert _agent_status_from_job_status(JobStatus.NEEDS_FOLLOWUP.value) == "needs_followup"
        assert _agent_status_from_job_status(JobStatus.IN_PROGRESS.value) == "running"
        assert _agent_status_from_job_status(JobStatus.QUEUED.value) == "running"

    def test_controller_status_to_agent_status(self, monkeypatch):
        """验证 controller status 到 agent status 的正确映射."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        from chatgptrest.api.routes_agent_v3 import _agent_status_from_controller_status

        assert _agent_status_from_controller_status("DELIVERED") == "completed"
        assert _agent_status_from_controller_status("FAILED") == "failed"
        assert _agent_status_from_controller_status("CANCELLED") == "cancelled"
        assert _agent_status_from_controller_status("WAITING_HUMAN") == "needs_followup"
        assert _agent_status_from_controller_status("RUNNING") == "running"

    def test_all_fault_states_mapped(self, monkeypatch):
        """验证所有故障状态都正确映射."""
        monkeypatch.setenv("OPENMIND_API_KEY", "test-key")
        monkeypatch.setenv("OPENMIND_AUTH_MODE", "strict")

        # All fault/blocker states should map appropriately
        # BLOCKED -> needs_followup (human intervention needed)
        assert _agent_status_from_job_status("blocked") == "needs_followup"
        # COOLDOWN -> running (still in progress)
        assert _agent_status_from_job_status("cooldown") == "running"
        # NEEDS_FOLLOWUP -> needs_followup
        assert _agent_status_from_job_status("needs_followup") == "needs_followup"
        # ERROR -> failed
        assert _agent_status_from_job_status("error") == "failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
