from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


def _load_module():
    path = Path(__file__).resolve().parents[1] / "ops" / "chatgpt_agent_shell_v0.py"
    spec = importlib.util.spec_from_file_location("chatgpt_agent_shell_v0", str(path))
    assert spec and spec.loader
    module_name = str(spec.name)
    cached = sys.modules.get(module_name)
    if cached is not None and hasattr(cached, "ChatGPTAgentV0"):
        return cached
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def test_default_client_name_uses_real_shell_identity(tmp_path: Path) -> None:
    mod = _load_module()
    agent = mod.ChatGPTAgentV0(
        base_url="http://127.0.0.1:18711",
        api_token="",
        state_root=tmp_path,
        session_id="test-v0-default-client",
        dry_run=True,
    )
    assert agent.client_name == "chatgpt_agent_shell_v0"


def test_post_submit_sends_trace_headers_and_payload_identity_consistent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mod = _load_module()
    calls: list[dict[str, Any]] = []

    def fake_http_request(  # noqa: ANN001
        self,
        *,
        method: str,
        url: str,
        json_body: dict[str, Any] | None,
        timeout_seconds: float,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        calls.append({"headers": dict(extra_headers or {}), "json_body": dict(json_body or {})})
        return 200, {"job_id": "job-1", "status": "queued"}

    monkeypatch.setattr(mod.ChatGPTAgentV0, "_http_request", fake_http_request)
    agent = mod.ChatGPTAgentV0(
        base_url="http://127.0.0.1:18711",
        api_token="",
        state_root=tmp_path,
        session_id="test-v0-headers",
        client_name="chatgpt_agent_shell_v0",
        client_instance="unit-tests",
        request_id_prefix="rid tests @@@",
        dry_run=False,
    )

    out = agent._post_submit(
        question="给出方案",
        parent_job_id=None,
        turn_id="idem-v0-headers-1",
        turn_no=1,
    )

    assert out["job_id"] == "job-1"
    assert len(calls) == 1
    headers = calls[0]["headers"]
    payload = calls[0]["json_body"]
    assert headers["Idempotency-Key"] == "idem-v0-headers-1"
    assert headers["X-Client-Name"] == "chatgpt_agent_shell_v0"
    assert headers["X-Client-Instance"] == "unit-tests"
    assert " " not in headers["X-Request-ID"]
    assert "@" not in headers["X-Request-ID"]
    assert payload["client"]["name"] == headers["X-Client-Name"]


def test_post_submit_auto_repair_uses_local_allowlist_and_is_request_scoped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod = _load_module()
    calls: list[dict[str, Any]] = []
    responses: list[tuple[int, dict[str, Any]]] = [
        (
            403,
            {
                "detail": {
                    "error": "client_not_allowed",
                    "allowed_client_names": ["chatgptrest-mcp"],
                }
            },
        ),
        (200, {"job_id": "job-2", "status": "queued"}),
    ]

    def fake_http_request(  # noqa: ANN001
        self,
        *,
        method: str,
        url: str,
        json_body: dict[str, Any] | None,
        timeout_seconds: float,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        calls.append({"headers": dict(extra_headers or {}), "json_body": dict(json_body or {})})
        return responses.pop(0)

    monkeypatch.setattr(mod.ChatGPTAgentV0, "_http_request", fake_http_request)
    agent = mod.ChatGPTAgentV0(
        base_url="http://127.0.0.1:18711",
        api_token="",
        state_root=tmp_path,
        session_id="test-v0-repair",
        client_name="chatgpt_agent_shell_v0",
        auto_client_name_repair=True,
        client_name_repair_allowlist=["chatgptrest-mcp"],
        persist_client_name_repair=False,
        dry_run=False,
    )

    out = agent._post_submit(
        question="继续执行",
        parent_job_id=None,
        turn_id="idem-v0-repair-1",
        turn_no=1,
    )

    assert out["job_id"] == "job-2"
    assert len(calls) == 2
    assert calls[0]["headers"]["X-Client-Name"] == "chatgpt_agent_shell_v0"
    assert calls[1]["headers"]["X-Client-Name"] == "chatgptrest-mcp"
    assert calls[1]["json_body"]["client"]["name"] == calls[1]["headers"]["X-Client-Name"]
    assert agent.client_name == "chatgpt_agent_shell_v0"

    err = capsys.readouterr().err
    assert "submit_client_name_repair" in err
    assert "\"repair_result\": \"retry_succeeded\"" in err


def test_post_submit_non_client_not_allowed_403_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mod = _load_module()
    calls: list[dict[str, str]] = []

    def fake_http_request(  # noqa: ANN001
        self,
        *,
        method: str,
        url: str,
        json_body: dict[str, Any] | None,
        timeout_seconds: float,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        calls.append(dict(extra_headers or {}))
        return 403, {"detail": {"error": "different_error", "allowed_client_names": ["chatgptrest-mcp"]}}

    monkeypatch.setattr(mod.ChatGPTAgentV0, "_http_request", fake_http_request)
    agent = mod.ChatGPTAgentV0(
        base_url="http://127.0.0.1:18711",
        api_token="",
        state_root=tmp_path,
        session_id="test-v0-no-retry-403",
        client_name="chatgpt_agent_shell_v0",
        auto_client_name_repair=True,
        client_name_repair_allowlist=["chatgptrest-mcp"],
        dry_run=False,
    )

    with pytest.raises(mod.ChatGPTAgentV0.Error):
        agent._post_submit(
            question="继续执行",
            parent_job_id=None,
            turn_id="idem-v0-no-retry-403",
            turn_no=1,
        )
    assert len(calls) == 1


def test_post_submit_non_403_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mod = _load_module()
    calls: list[dict[str, str]] = []

    def fake_http_request(  # noqa: ANN001
        self,
        *,
        method: str,
        url: str,
        json_body: dict[str, Any] | None,
        timeout_seconds: float,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        calls.append(dict(extra_headers or {}))
        return 500, {"detail": {"error": "server_error"}}

    monkeypatch.setattr(mod.ChatGPTAgentV0, "_http_request", fake_http_request)
    agent = mod.ChatGPTAgentV0(
        base_url="http://127.0.0.1:18711",
        api_token="",
        state_root=tmp_path,
        session_id="test-v0-no-retry-500",
        client_name="chatgpt_agent_shell_v0",
        auto_client_name_repair=True,
        client_name_repair_allowlist=["chatgptrest-mcp"],
        dry_run=False,
    )

    with pytest.raises(mod.ChatGPTAgentV0.Error):
        agent._post_submit(
            question="继续执行",
            parent_job_id=None,
            turn_id="idem-v0-no-retry-500",
            turn_no=1,
        )
    assert len(calls) == 1


def test_post_submit_allowlist_only_current_client_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mod = _load_module()
    calls: list[dict[str, str]] = []

    def fake_http_request(  # noqa: ANN001
        self,
        *,
        method: str,
        url: str,
        json_body: dict[str, Any] | None,
        timeout_seconds: float,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        calls.append(dict(extra_headers or {}))
        return 403, {"detail": {"error": "client_not_allowed", "allowed_client_names": ["chatgpt_agent_shell_v0"]}}

    monkeypatch.setattr(mod.ChatGPTAgentV0, "_http_request", fake_http_request)
    agent = mod.ChatGPTAgentV0(
        base_url="http://127.0.0.1:18711",
        api_token="",
        state_root=tmp_path,
        session_id="test-v0-no-retry-current-only",
        client_name="chatgpt_agent_shell_v0",
        auto_client_name_repair=True,
        client_name_repair_allowlist=["chatgptrest-mcp"],
        dry_run=False,
    )

    with pytest.raises(mod.ChatGPTAgentV0.Error):
        agent._post_submit(
            question="继续执行",
            parent_job_id=None,
            turn_id="idem-v0-no-retry-current-only",
            turn_no=1,
        )
    assert len(calls) == 1

