from __future__ import annotations

import asyncio
import http.client
import importlib
import json
from types import SimpleNamespace
import urllib.error
from unittest.mock import MagicMock, patch


def _mock_urlopen_json(payload: dict):
    mock_context = MagicMock()
    mock_context.__enter__ = MagicMock(return_value=mock_context)
    mock_context.__exit__ = MagicMock(return_value=False)
    mock_context.read.return_value = json.dumps(payload).encode("utf-8")
    mock_context.getcode.return_value = 200
    return mock_context


def _mock_http_error(code: int, payload: dict, url: str = "http://127.0.0.1:18711/v3/agent/turn") -> urllib.error.HTTPError:
    body = MagicMock()
    body.read.return_value = json.dumps(payload).encode("utf-8")
    return urllib.error.HTTPError(
        url=url,
        code=code,
        msg="error",
        hdrs=None,
        fp=body,
    )


def _reload_agent_mcp(monkeypatch, tmp_path):  # noqa: ANN001
    db_path = tmp_path / "state" / "jobdb.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch()
    monkeypatch.setenv("CHATGPTREST_DB_PATH", str(db_path))
    monkeypatch.setenv("CHATGPTREST_AGENT_SESSION_DIR", str(tmp_path / "agent_sessions"))
    from chatgptrest.mcp import agent_mcp

    return importlib.reload(agent_mcp)


def test_public_agent_mcp_auth_state_prefers_openmind_api_key(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    mod = _reload_agent_mcp(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENMIND_API_KEY", "openmind-secret")
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "bearer-secret")
    monkeypatch.delenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", raising=False)

    state = mod.public_agent_mcp_auth_state()

    assert state["ok"] is True
    assert state["source"] == "OPENMIND_API_KEY"


def test_public_agent_mcp_auth_state_falls_back_to_bearer(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    mod = _reload_agent_mcp(monkeypatch, tmp_path)
    monkeypatch.delenv("OPENMIND_API_KEY", raising=False)
    monkeypatch.setenv("CHATGPTREST_API_TOKEN", "bearer-secret")
    monkeypatch.delenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", raising=False)

    state = mod.public_agent_mcp_auth_state()

    assert state["ok"] is True
    assert state["source"] == "CHATGPTREST_API_TOKEN"


def test_public_agent_mcp_auth_state_missing_raises(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    mod = _reload_agent_mcp(monkeypatch, tmp_path)
    monkeypatch.delenv("OPENMIND_API_KEY", raising=False)
    monkeypatch.delenv("CHATGPTREST_API_TOKEN", raising=False)
    monkeypatch.delenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", raising=False)

    with patch.dict("os.environ", {}, clear=False):
        with patch.object(mod, "_base_url", return_value="http://127.0.0.1:18711"):
            try:
                mod.ensure_public_agent_mcp_auth_configured()
            except RuntimeError as exc:
                assert "Public agent MCP requires OPENMIND_API_KEY or CHATGPTREST_API_TOKEN" in str(exc)
            else:
                raise AssertionError("expected RuntimeError")


def test_public_agent_mcp_auth_state_detects_allowlist_drift(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    mod = _reload_agent_mcp(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENMIND_API_KEY", "openmind-secret")
    monkeypatch.setenv("CHATGPTREST_AGENT_MCP_CLIENT_NAME", "chatgptrest-agent-mcp")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp,chatgptrestctl")

    state = mod.public_agent_mcp_auth_state()

    assert state["token_present"] is True
    assert state["allowlist_enforced"] is True
    assert state["client_name"] == "chatgptrest-agent-mcp"
    assert state["allowlisted"] is False
    assert state["ok"] is False
    assert state["runtime_contract_ok"] is False


def test_public_agent_mcp_auth_state_allowlist_match_is_ok(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    mod = _reload_agent_mcp(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENMIND_API_KEY", "openmind-secret")
    monkeypatch.setenv("CHATGPTREST_AGENT_MCP_CLIENT_NAME", "chatgptrest-agent-mcp")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-agent-mcp,chatgptrestctl")

    state = mod.public_agent_mcp_auth_state()

    assert state["allowlist_enforced"] is True
    assert state["allowlisted"] is True
    assert state["ok"] is True


def test_public_agent_mcp_auth_state_allowlist_drift_raises(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    mod = _reload_agent_mcp(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENMIND_API_KEY", "openmind-secret")
    monkeypatch.setenv("CHATGPTREST_AGENT_MCP_CLIENT_NAME", "chatgptrest-agent-mcp")
    monkeypatch.setenv("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST", "chatgptrest-mcp")

    try:
        mod.ensure_public_agent_mcp_auth_configured()
    except RuntimeError as exc:
        assert "service_identity_not_allowlisted" in str(exc)
        assert "chatgptrest-agent-mcp" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_public_agent_fastmcp_stateless_http_defaults_to_false(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.delenv("CHATGPTREST_AGENT_MCP_STATELESS_HTTP", raising=False)
    mod = _reload_agent_mcp(monkeypatch, tmp_path)

    assert mod._agent_fastmcp_stateless_http_default() is False


def test_public_agent_fastmcp_stateless_http_env_overrides(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.setenv("CHATGPTREST_AGENT_MCP_STATELESS_HTTP", "1")
    mod = _reload_agent_mcp(monkeypatch, tmp_path)

    assert mod._agent_fastmcp_stateless_http_default() is True


def test_agent_mcp_turn_forwards_extended_payload() -> None:
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "run_id": "run-123",
        "status": "completed",
        "answer": "Hello!",
        "delivery": {"format": "markdown", "answer_chars": 7},
        "provenance": {"route": "quick_ask", "provider_path": ["chatgpt"]},
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_urlopen_json(mock_response)

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Hello",
                session_id="test-session",
                goal_hint="code_review",
                depth="standard",
                execution_profile="thinking_heavy",
                task_intake={"spec_version": "task-intake-v2", "objective": "Review the repo", "trace_id": "trace-1"},
                contract_patch={"decision_to_support": "Release go/no-go"},
                attachments="/tmp/repo.zip",
                role_id="research",
                user_id="u-1",
                trace_id="trace-1",
                timeout_seconds=300,
            )
        )

        req = mock_urlopen.call_args.args[0]
        assert req.full_url.endswith("/v3/agent/turn")
        headers = {key.lower(): value for key, value in req.header_items()}
        payload = json.loads(req.data.decode("utf-8"))
        assert headers["x-client-name"] == "chatgptrest-mcp"
        assert headers["x-client-instance"]
        assert headers["x-request-id"].startswith("chatgptrest-mcp-")
        assert payload["attachments"] == ["/tmp/repo.zip"]
        assert payload["role_id"] == "research"
        assert payload["user_id"] == "u-1"
        assert payload["trace_id"] == "trace-1"
        assert payload["goal_hint"] == "code_review"
        assert payload["execution_profile"] == "thinking_heavy"
        assert payload["task_intake"]["spec_version"] == "task-intake-v2"
        assert payload["contract_patch"]["decision_to_support"] == "Release go/no-go"
        assert payload["delivery_mode"] == "sync"
        assert result["ok"] is True
        assert result["session_id"] == "test-session"


def test_agent_mcp_turn_forwards_deferred_delivery_mode() -> None:
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "accepted": True,
        "session_id": "test-session",
        "status": "running",
        "stream_url": "/v3/agent/session/test-session/stream",
        "delivery": {"mode": "deferred", "stream_url": "/v3/agent/session/test-session/stream"},
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_urlopen_json(mock_response)

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Hello",
                delivery_mode="deferred",
                auto_watch=False,
                timeout_seconds=30,
            )
        )

        req = mock_urlopen.call_args_list[0].args[0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["delivery_mode"] == "deferred"
        assert result["accepted"] is True
        assert result["delivery"]["mode"] == "deferred"


def test_agent_mcp_turn_forwards_memory_capture_request() -> None:
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "memory-session",
        "run_id": "run-memory",
        "status": "completed",
        "answer": "done",
        "delivery": {"format": "markdown", "answer_chars": 4},
        "provenance": {"route": "quick_ask", "provider_path": ["chatgpt"]},
        "effects": {"memory_capture": {"ok": True, "record_id": "mem-1"}},
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_urlopen_json(mock_response)

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Hello",
                memory_capture={"capture_answer": True, "require_complete_identity": True},
                auto_watch=False,
            )
        )

        req = mock_urlopen.call_args.args[0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["memory_capture"]["capture_answer"] is True
        assert payload["memory_capture"]["require_complete_identity"] is True
        assert result["effects"]["memory_capture"]["record_id"] == "mem-1"


def test_agent_mcp_turn_forwards_real_mcp_caller_identity_from_context() -> None:
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "identity-session",
        "run_id": "run-identity",
        "status": "completed",
        "answer": "done",
        "delivery": {"format": "markdown", "answer_chars": 4},
        "provenance": {"route": "quick_ask", "provider_path": ["chatgpt"]},
    }
    fake_ctx = SimpleNamespace(
        client_id="codex-client-1",
        session=SimpleNamespace(
            client_params=SimpleNamespace(
                clientInfo=SimpleNamespace(name="codex-cli", version="1.2.3"),
            )
        ),
    )

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_urlopen_json(mock_response)

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                fake_ctx,
                message="Inspect this repo",
                goal_hint="code_review",
                timeout_seconds=60,
                auto_watch=False,
            )
        )

        req = mock_urlopen.call_args.args[0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["client"]["name"] == "codex-cli"
        assert payload["client"]["instance"] == "public-mcp"
        assert payload["client"]["mcp_client_name"] == "codex-cli"
        assert payload["client"]["mcp_client_version"] == "1.2.3"
        assert payload["client"]["mcp_client_id"] == "codex-client-1"
        assert result["ok"] is True


def test_agent_mcp_turn_forwards_workspace_request() -> None:
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "workspace-session",
        "run_id": "run-1",
        "status": "completed",
        "answer": "Delivered report to Google Docs",
        "delivery": {"format": "markdown", "answer_chars": 31},
        "provenance": {"route": "workspace_action", "provider_path": ["google_workspace"]},
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_urlopen_json(mock_response)

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="",
                workspace_request={
                    "spec_version": "workspace-request-v1",
                    "action": "deliver_report_to_docs",
                    "payload": {"title": "Daily", "body_markdown": "# Report"},
                },
            )
        )

        req = mock_urlopen.call_args.args[0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["workspace_request"]["action"] == "deliver_report_to_docs"
        assert result["session_id"] == "workspace-session"


def test_agent_mcp_turn_auto_backgrounds_long_research_goal() -> None:
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "accepted": True,
        "session_id": "test-session",
        "status": "running",
        "stream_url": "/v3/agent/session/test-session/stream",
        "delivery": {"mode": "deferred", "stream_url": "/v3/agent/session/test-session/stream"},
    }

    with patch("urllib.request.urlopen") as mock_urlopen, patch.object(agent_mcp, "_start_agent_watch") as mock_watch:
        mock_urlopen.return_value = _mock_urlopen_json(mock_response)
        mock_watch.return_value = {
            "ok": True,
            "watch_id": "agent-watch-1",
            "watch_status": "running",
            "running": True,
        }

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Deep research this company",
                goal_hint="research",
                delivery_mode="sync",
                timeout_seconds=600,
            )
        )

        req = mock_urlopen.call_args.args[0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["delivery_mode"] == "deferred"
        assert result["delivery_mode_requested"] == "sync"
        assert result["delivery_mode_effective"] == "deferred"
        assert result["auto_background_reason"] == "long_goal_auto_background"
        assert result["accepted_for_background"] is True
        assert result["recommended_client_action"] == "wait"
        assert result["wait_tool"] == "advisor_agent_wait"
        assert result["background_watch_started"] is True
        assert result["watch_id"] == "agent-watch-1"


def test_agent_mcp_cancel() -> None:
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "status": "cancelled",
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_urlopen_json(mock_response)
        result = asyncio.run(agent_mcp.advisor_agent_cancel(None, session_id="test-session"))

        assert result["ok"] is True
        assert result["status"] == "cancelled"


def test_agent_mcp_status() -> None:
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "run_id": "run-123",
        "status": "completed",
        "job_id": "job-456",
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _mock_urlopen_json(mock_response)
        result = asyncio.run(agent_mcp.advisor_agent_status(None, session_id="test-session"))

        assert result["ok"] is True
        assert result["job_id"] == "job-456"


def test_agent_mcp_status_includes_background_watch_state() -> None:
    from chatgptrest.mcp import agent_mcp

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "run_id": "run-123",
        "status": "running",
    }

    async def _run() -> dict:
        async with agent_mcp._AGENT_WATCH_LOCK:
            agent_mcp._AGENT_WATCH_STATE.clear()
            agent_mcp._AGENT_WATCH_BY_SESSION.clear()
            agent_mcp._AGENT_WATCH_STATE["agent-watch-1"] = {
                "watch_id": "agent-watch-1",
                "session_id": "test-session",
                "watch_status": "running",
                "started_at": 1.0,
                "updated_at": 2.0,
                "ended_at": None,
                "notify_done": True,
                "last_status": "running",
                "last_event_type": "started",
            }
            agent_mcp._AGENT_WATCH_BY_SESSION["test-session"] = "agent-watch-1"
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_urlopen_json(mock_response)
            return await agent_mcp.advisor_agent_status(None, session_id="test-session")

    result = asyncio.run(_run())
    assert result["ok"] is True
    assert result["watch_id"] == "agent-watch-1"
    assert result["watch_status"] == "running"
    assert result["background_watch"]["session_id"] == "test-session"
    assert result["recommended_client_action"] == "wait"
    assert result["wait_tool"] == "advisor_agent_wait"
    assert result["progress"]["phase"] == "background_running"


def test_agent_mcp_turn_error_handling() -> None:
    from chatgptrest.mcp import agent_mcp

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = Exception("Connection error")

        result = asyncio.run(agent_mcp.advisor_agent_turn(None, message="Hello"))

        assert result["ok"] is False
        assert "error" in result


def test_agent_mcp_turn_recovers_status_after_disconnect() -> None:
    from chatgptrest.mcp import agent_mcp

    recovered_response = {
        "ok": True,
        "session_id": "agent_sess_existing1234",
        "status": "running",
        "run_id": "run-123",
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = [
            http.client.RemoteDisconnected("Remote end closed connection without response"),
            _mock_urlopen_json(recovered_response),
        ]

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Hello",
                session_id="agent_sess_existing1234",
            )
        )

        assert result["ok"] is True
        assert result["transport_recovered"] is True
        assert result["session_id"] == "agent_sess_existing1234"


def test_agent_mcp_turn_recovers_deferred_watch_after_disconnect() -> None:
    from chatgptrest.mcp import agent_mcp

    recovered_response = {
        "ok": True,
        "session_id": "agent_sess_existing1234",
        "status": "running",
        "run_id": "run-123",
        "stream_url": "/v3/agent/session/agent_sess_existing1234/stream",
    }

    async def fake_resume_watch(**_kwargs):  # noqa: ANN003
        return {
            "ok": True,
            "watch_id": "agent-watch-resumed",
            "watch_status": "running",
            "running": True,
            "done": False,
            "auto_resumed": True,
        }

    with patch("urllib.request.urlopen") as mock_urlopen, patch.object(agent_mcp, "_resume_agent_watch", side_effect=fake_resume_watch):
        mock_urlopen.side_effect = [
            http.client.RemoteDisconnected("Remote end closed connection without response"),
            _mock_urlopen_json(recovered_response),
        ]

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Research this topic",
                session_id="agent_sess_existing1234",
                goal_hint="research",
            )
        )

        assert result["ok"] is True
        assert result["transport_recovered"] is True
        assert result["background_watch_started"] is True
        assert result["background_watch_resumed"] is True
        assert result["watch_id"] == "agent-watch-resumed"


def test_agent_mcp_turn_returns_recoverable_error_with_generated_session_id() -> None:
    from chatgptrest.mcp import agent_mcp

    not_found = MagicMock()
    not_found.read.return_value = b'{"error":"not found"}'
    not_found.fp = True

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = [
            http.client.RemoteDisconnected("Remote end closed connection without response"),
            urllib.error.HTTPError(
                url="http://127.0.0.1:18711/v3/agent/session/agent_sess_missing1234",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=not_found,
            ),
        ]

        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "missing1234abcdef"
            result = asyncio.run(agent_mcp.advisor_agent_turn(None, message="Hello"))

        assert result["ok"] is False
        assert result["recoverable"] is True
        assert result["session_id"] == "agent_sess_missing1234abcde"
        assert result["next_action"]["type"] == "check_status_or_retry"


def test_agent_mcp_turn_preserves_structured_duplicate_error_fields() -> None:
    from chatgptrest.mcp import agent_mcp

    duplicate_payload = {
        "detail": {
            "error": "duplicate_public_agent_session_in_progress",
            "existing_session_id": "agent_sess_existing_duplicate",
            "wait_tool": "advisor_agent_wait",
            "recommended_client_action": "wait",
            "hint": "reuse the existing running session",
        }
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _mock_http_error(409, duplicate_payload)

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Review the imported repo",
                session_id="agent_sess_duplicate_request",
                goal_hint="code_review",
            )
        )

    assert result["ok"] is False
    assert result["status_code"] == 409
    assert result["session_id"] == "agent_sess_duplicate_request"
    assert result["error"] == "duplicate_public_agent_session_in_progress"
    assert result["existing_session_id"] == "agent_sess_existing_duplicate"
    assert result["wait_tool"] == "advisor_agent_wait"
    assert result["recommended_client_action"] == "wait"
    assert result["detail"]["hint"] == "reuse the existing running session"


def test_agent_mcp_turn_preserves_structured_microtask_block_error_fields() -> None:
    from chatgptrest.mcp import agent_mcp

    blocked_payload = {
        "detail": {
            "error": "public_agent_microtask_blocked",
            "reason": "json_only_microtask",
            "hint": "use a registered non-live automation lane",
        }
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _mock_http_error(400, blocked_payload)

        result = asyncio.run(
            agent_mcp.advisor_agent_turn(
                None,
                message="Return only JSON with a yes/no sufficiency decision.",
                goal_hint="research",
            )
        )

    assert result["ok"] is False
    assert result["status_code"] == 400
    assert result["error"] == "public_agent_microtask_blocked"
    assert result["reason"] == "json_only_microtask"
    assert result["detail"]["hint"] == "use a registered non-live automation lane"


def test_agent_mcp_wait_returns_terminal_session() -> None:
    from chatgptrest.mcp import agent_mcp

    initial_response = {
        "ok": True,
        "session_id": "test-session",
        "status": "running",
        "stream_url": "/v3/agent/session/test-session/stream",
        "delivery": {"mode": "deferred", "stream_url": "/v3/agent/session/test-session/stream"},
    }
    terminal_response = {
        "ok": True,
        "session_id": "test-session",
        "status": "completed",
        "answer": "final report",
        "artifacts": [{"kind": "conversation_url", "uri": "https://chatgpt.com/c/test"}],
    }

    with patch.object(agent_mcp, "_session_status", return_value=initial_response), patch.object(
        agent_mcp,
        "_wait_stream_terminal",
        return_value=terminal_response,
    ):
        result = asyncio.run(agent_mcp.advisor_agent_wait(None, session_id="test-session", timeout_seconds=120))

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["wait_status"] == "completed"
    assert result["timed_out"] is False
    assert result["recommended_client_action"] == "followup"


def test_agent_mcp_wait_reports_timeout_for_non_terminal_session() -> None:
    from chatgptrest.mcp import agent_mcp

    initial_response = {
        "ok": True,
        "session_id": "test-session",
        "status": "running",
        "stream_url": "/v3/agent/session/test-session/stream",
        "delivery": {"mode": "deferred", "stream_url": "/v3/agent/session/test-session/stream"},
    }

    with patch.object(agent_mcp, "_session_status", side_effect=[initial_response, initial_response]), patch.object(
        agent_mcp,
        "_wait_stream_terminal",
        return_value=None,
    ):
        result = asyncio.run(agent_mcp.advisor_agent_wait(None, session_id="test-session", timeout_seconds=5))

    assert result["ok"] is True
    assert result["status"] == "running"
    assert result["wait_status"] == "timeout"
    assert result["timed_out"] is True
    assert result["recommended_client_action"] == "wait"


def test_agent_mcp_wait_prefers_fresh_terminal_session_over_stale_stream_snapshot() -> None:
    from chatgptrest.mcp import agent_mcp

    initial_response = {
        "ok": True,
        "session_id": "test-session",
        "status": "running",
        "stream_url": "/v3/agent/session/test-session/stream",
        "delivery": {"mode": "deferred", "stream_url": "/v3/agent/session/test-session/stream"},
    }
    stale_stream_response = {
        "ok": True,
        "session_id": "test-session",
        "status": "running",
        "stream_url": "/v3/agent/session/test-session/stream",
        "delivery": {"mode": "deferred", "stream_url": "/v3/agent/session/test-session/stream"},
    }
    refreshed_terminal = {
        "ok": True,
        "session_id": "test-session",
        "status": "needs_followup",
        "next_action": {"type": "same_session_repair", "job_id": "job-1"},
    }

    with patch.object(
        agent_mcp,
        "_session_status",
        side_effect=[initial_response, refreshed_terminal],
    ), patch.object(
        agent_mcp,
        "_wait_stream_terminal",
        return_value=stale_stream_response,
    ):
        result = asyncio.run(agent_mcp.advisor_agent_wait(None, session_id="test-session", timeout_seconds=5))

    assert result["ok"] is True
    assert result["status"] == "needs_followup"
    assert result["wait_status"] == "completed"
    assert result["timed_out"] is False
    assert result["recommended_client_action"] == "patch_same_session"


def test_agent_mcp_status_autostarts_api_after_transport_failure(monkeypatch) -> None:  # noqa: ANN001
    from chatgptrest.mcp import agent_mcp

    monkeypatch.setenv("CHATGPTREST_MCP_AUTO_START_API", "1")
    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "run_id": "run-123",
        "status": "running",
    }

    with patch("urllib.request.urlopen") as mock_urlopen, patch.object(agent_mcp, "_maybe_autostart_api_for_base_url", return_value=True) as mock_autostart:
        mock_urlopen.side_effect = [
            urllib.error.URLError("connection refused"),
            _mock_urlopen_json(mock_response),
        ]

        result = asyncio.run(agent_mcp.advisor_agent_status(None, session_id="test-session"))

        assert result["ok"] is True
        assert result["status"] == "running"
        mock_autostart.assert_called_once()


def test_agent_mcp_status_auto_resumes_persisted_watch(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    mod = _reload_agent_mcp(monkeypatch, tmp_path)
    mod._AGENT_WATCH_STORE.put(
        "test-session",
        {
            "watch_id": "agent-watch-persisted-1",
            "session_id": "test-session",
            "watch_status": "running",
            "started_at": 1.0,
            "updated_at": 2.0,
            "ended_at": None,
            "notify_done": True,
            "stream_url": "/v3/agent/session/test-session/stream",
            "timeout_seconds": 900,
            "last_status": "running",
            "last_event_type": "started",
        },
    )
    mod = importlib.reload(mod)

    captured: dict[str, object] = {}

    async def fake_resume_watch(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return {
            "ok": True,
            "watch_id": "agent-watch-resumed-1",
            "watch_status": "running",
            "running": True,
            "done": False,
            "auto_resumed": True,
        }

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "run_id": "run-123",
        "status": "running",
        "stream_url": "/v3/agent/session/test-session/stream",
    }

    with patch("urllib.request.urlopen") as mock_urlopen, patch.object(mod, "_resume_agent_watch", side_effect=fake_resume_watch):
        mock_urlopen.return_value = _mock_urlopen_json(mock_response)
        result = asyncio.run(mod.advisor_agent_status(None, session_id="test-session"))

        assert result["ok"] is True
        assert result["auto_resumed"] is True
        assert result["watch_id"] == "agent-watch-persisted-1"
        assert result["background_watch"]["session_id"] == "test-session"
        assert isinstance(captured.get("state"), dict)
        assert captured["state"]["watch_id"] == "agent-watch-persisted-1"
        assert captured["state"]["timeout_seconds"] == 900


def test_agent_mcp_status_does_not_resume_persisted_canceled_watch(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    mod = _reload_agent_mcp(monkeypatch, tmp_path)
    mod._AGENT_WATCH_STORE.put(
        "test-session",
        {
            "watch_id": "agent-watch-persisted-1",
            "session_id": "test-session",
            "watch_status": "canceled",
            "started_at": 1.0,
            "updated_at": 2.0,
            "ended_at": 3.0,
            "notify_done": True,
            "stream_url": "/v3/agent/session/test-session/stream",
            "timeout_seconds": 900,
            "last_status": "cancelled",
            "last_event_type": "canceled",
        },
    )
    mod = importlib.reload(mod)

    async def _should_not_start(**_kwargs):  # noqa: ANN003
        raise AssertionError("canceled watch should not auto-resume")

    mock_response = {
        "ok": True,
        "session_id": "test-session",
        "run_id": "run-123",
        "status": "running",
        "stream_url": "/v3/agent/session/test-session/stream",
    }

    with patch("urllib.request.urlopen") as mock_urlopen, patch.object(mod, "_ensure_agent_watch", side_effect=_should_not_start):
        mock_urlopen.return_value = _mock_urlopen_json(mock_response)
        result = asyncio.run(mod.advisor_agent_status(None, session_id="test-session"))

        assert result["ok"] is True
        assert result["status"] == "running"
        assert result.get("auto_resumed") is not True
        assert result["watch_id"] == "agent-watch-persisted-1"
        assert result["watch_status"] == "canceled"
        assert result["background_watch"]["watch_status"] == "canceled"


def test_agent_mcp_defaults_to_runtime_loopback_port() -> None:
    from chatgptrest.mcp import agent_mcp

    assert agent_mcp.mcp.settings.host == "127.0.0.1"
    assert agent_mcp.mcp.settings.port == 18712


def test_repo_bootstrap_tool_returns_packet(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    mod = _reload_agent_mcp(monkeypatch, tmp_path)

    monkeypatch.setattr(
        "chatgptrest.repo_cognition.bootstrap.generate_bootstrap_packet",
        lambda **kwargs: {"schema_version": "bootstrap-v1", "task": {"description": kwargs["task_description"]}},
    )

    result = asyncio.run(mod.repo_bootstrap(None, task_description="Fix ingress drift", goal_hint="public_agent"))

    assert result["ok"] is True
    assert result["packet"]["schema_version"] == "bootstrap-v1"
    assert result["packet"]["task"]["description"] == "Fix ingress drift"


def test_repo_doc_obligations_tool_returns_validation(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    mod = _reload_agent_mcp(monkeypatch, tmp_path)

    monkeypatch.setattr(
        "chatgptrest.repo_cognition.obligations.compute_change_obligations",
        lambda changed_files: [
            {
                "pattern": "chatgptrest/mcp/",
                "plane": "public_agent",
                "must_update": ["AGENTS.md"],
                "baseline_tests": ["tests/test_agent_mcp.py"],
                "dynamic_test_strategy": "gitnexus_impact",
                "reason": "MCP changes",
                "matched_files": changed_files,
                "missing_updates": ["AGENTS.md"],
            }
        ],
    )
    monkeypatch.setattr(
        "chatgptrest.repo_cognition.obligations.validate_obligations",
        lambda obligations: {
            "ok": False,
            "required_docs": ["AGENTS.md"],
            "required_tests": ["tests/test_agent_mcp.py"],
            "missing_docs": [],
            "missing_tests": [],
            "missing_updates": ["AGENTS.md"],
        },
    )

    result = asyncio.run(mod.repo_doc_obligations(None, changed_files=["chatgptrest/mcp/agent_mcp.py"]))

    assert result["ok"] is False
    assert result["validation"]["missing_updates"] == ["AGENTS.md"]
