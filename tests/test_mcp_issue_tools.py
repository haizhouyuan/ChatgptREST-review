from __future__ import annotations

import asyncio

import pytest


def _load_mcp_server_module():
    import chatgptrest.mcp.server as mod

    return mod


def test_mcp_issue_report_posts_expected_body(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()
    calls: list[tuple[str, str, object]] = []

    def fake_http_json(*, method: str, url: str, body=None, **_kwargs):  # noqa: ANN001,ARG001
        calls.append((method, url, body))
        return {"ok": True, "issue_id": "iss_1", "created": True, "status": "open"}

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)

    out = asyncio.run(
        mod.chatgptrest_issue_report(
            project="research",
            title="Deep Research tool-call JSON",
            severity="P1",
            kind="chatgpt_web.ask",
            symptom="json-only",
            raw_error="none",
            job_id="job-1",
            conversation_url="https://chatgpt.com/c/1",
            artifacts_path="jobs/job-1",
            source="codex",
            tags=["deep_research"],
            metadata={"k": "v"},
        )
    )
    assert out["ok"] is True
    assert len(calls) == 1
    method, url, body = calls[0]
    assert method == "POST"
    assert url.endswith("/v1/issues/report")
    assert isinstance(body, dict)
    assert body["project"] == "research"
    assert body["title"] == "Deep Research tool-call JSON"
    assert body["job_id"] == "job-1"


def test_mcp_issue_report_allow_resolved_job_sets_metadata(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()
    calls: list[tuple[str, str, object]] = []

    def fake_http_json(*, method: str, url: str, body=None, **_kwargs):  # noqa: ANN001,ARG001
        calls.append((method, url, body))
        return {"ok": True, "issue_id": "iss_2", "created": True, "status": "open"}

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)

    out = asyncio.run(
        mod.chatgptrest_issue_report(
            project="research",
            title="postmortem",
            job_id="job-2",
            source="codex",
            allow_resolved_job=True,
        )
    )
    assert out["ok"] is True
    assert len(calls) == 1
    _method, _url, body = calls[0]
    assert isinstance(body, dict)
    assert isinstance(body.get("metadata"), dict)
    assert body["metadata"].get("allow_resolved_job") is True


def test_mcp_issue_query_update_link_and_events(monkeypatch: pytest.MonkeyPatch):
    mod = _load_mcp_server_module()
    calls: list[tuple[str, str, object]] = []

    def fake_http_json(*, method: str, url: str, body=None, **_kwargs):  # noqa: ANN001,ARG001
        calls.append((method, url, body))
        return {"ok": True}

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)

    asyncio.run(
        mod.chatgptrest_issue_list(
            project="research",
            kind="chatgpt_web.ask",
            source="worker_auto",
            status="open",
            severity="P1",
            fingerprint_hash="abc123",
            fingerprint_text="tool-call json",
            since_ts=1.0,
            until_ts=2.0,
            limit=20,
        )
    )
    asyncio.run(mod.chatgptrest_issue_get("iss_abc"))
    asyncio.run(mod.chatgptrest_issue_update_status(issue_id="iss_abc", status="mitigated", note="fixed"))
    asyncio.run(mod.chatgptrest_issue_link_evidence(issue_id="iss_abc", job_id="job-2", artifacts_path="jobs/job-2"))
    asyncio.run(mod.chatgptrest_issue_events("iss_abc", after_id=10, limit=50))
    asyncio.run(
        mod.chatgptrest_issue_record_verification(
            issue_id="iss_abc",
            verification_type="live",
            job_id="job-2",
            artifacts_path="jobs/job-2",
        )
    )
    asyncio.run(mod.chatgptrest_issue_list_verifications("iss_abc", after_ts=0.0, limit=20))
    asyncio.run(
        mod.chatgptrest_issue_record_usage(
            issue_id="iss_abc",
            job_id="job-3",
            client_name="chatgptrest-mcp",
            kind="gemini_web.ask",
        )
    )
    asyncio.run(mod.chatgptrest_issue_list_usage("iss_abc", after_ts=0.0, limit=20))
    asyncio.run(mod.chatgptrest_issue_graph_query(issue_id="iss_abc", limit=10, neighbor_depth=2))

    list_urls = [url for method, url, _ in calls if method == "GET" and "/v1/issues?" in url]
    assert list_urls
    assert "kind=chatgpt_web.ask" in list_urls[0]
    assert "source=worker_auto" in list_urls[0]
    assert "fingerprint_hash=abc123" in list_urls[0]
    assert "since_ts=1.0" in list_urls[0]
    assert any(method == "GET" and url.endswith("/v1/issues/iss_abc") for method, url, _ in calls)
    assert any(method == "POST" and url.endswith("/v1/issues/iss_abc/status") for method, url, _ in calls)
    assert any(method == "POST" and url.endswith("/v1/issues/iss_abc/evidence") for method, url, _ in calls)
    assert any(method == "GET" and "/v1/issues/iss_abc/events?" in url for method, url, _ in calls)
    assert any(method == "POST" and url.endswith("/v1/issues/iss_abc/verification") for method, url, _ in calls)
    assert any(method == "GET" and "/v1/issues/iss_abc/verification?" in url for method, url, _ in calls)
    assert any(method == "POST" and url.endswith("/v1/issues/iss_abc/usage") for method, url, _ in calls)
    assert any(method == "GET" and "/v1/issues/iss_abc/usage?" in url for method, url, _ in calls)
    assert any(method == "POST" and url.endswith("/v1/issues/graph/query") for method, url, _ in calls)
