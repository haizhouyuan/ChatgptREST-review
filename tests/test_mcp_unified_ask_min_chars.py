from __future__ import annotations

import asyncio
import importlib


def _load_mcp_server_module():
    import chatgptrest.mcp.server as mod

    return importlib.reload(mod)


def test_chatgptrest_ask_sets_chatgpt_default_min_chars(monkeypatch):
    mod = _load_mcp_server_module()
    captured: dict[str, object] = {}

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        captured["idempotency_key"] = idempotency_key
        captured["kind"] = kind
        captured["input"] = input
        captured["params"] = params
        captured["client"] = client
        return {"ok": True, "job_id": "job-chatgpt-1", "kind": kind, "status": "queued"}

    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-chatgpt-1",
            question="review this",
            provider="chatgpt",
            auto_wait=False,
            notify_done=False,
        )
    )

    assert out["ok"] is True
    assert captured["kind"] == "chatgpt_web.ask"
    params = captured["params"]
    assert isinstance(params, dict)
    assert params.get("min_chars") == 800


def test_chatgptrest_ask_sets_gemini_default_min_chars(monkeypatch):
    mod = _load_mcp_server_module()
    captured: dict[str, object] = {}

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        captured["idempotency_key"] = idempotency_key
        captured["kind"] = kind
        captured["input"] = input
        captured["params"] = params
        captured["client"] = client
        return {"ok": True, "job_id": "job-gemini-1", "kind": kind, "status": "queued"}

    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-gemini-1",
            question="research this",
            provider="gemini",
            auto_wait=False,
            notify_done=False,
        )
    )

    assert out["ok"] is True
    assert captured["kind"] == "gemini_web.ask"
    params = captured["params"]
    assert isinstance(params, dict)
    assert params.get("min_chars") == 200


def test_chatgptrest_followup_passes_explicit_min_chars(monkeypatch):
    mod = _load_mcp_server_module()
    captured: dict[str, object] = {}

    async def fake_job_get(_job_id: str, ctx=None):  # noqa: ANN001,ARG001
        return {"ok": True, "job_id": "parent-1", "kind": "chatgpt_web.ask", "status": "completed"}

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        captured["idempotency_key"] = idempotency_key
        captured["kind"] = kind
        captured["input"] = input
        captured["params"] = params
        captured["client"] = client
        return {"ok": True, "job_id": "job-followup-1", "kind": kind, "status": "queued"}

    monkeypatch.setattr(mod, "chatgptrest_job_get", fake_job_get)
    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_followup(
            idempotency_key="idem-followup-1",
            parent_job_id="parent-1",
            question="continue",
            min_chars=1234,
            ctx=None,
        )
    )

    assert out["ok"] is True
    params = captured["params"]
    assert isinstance(params, dict)
    assert params.get("min_chars") == 1234


def test_chatgptrest_followup_does_not_force_deep_research_false(monkeypatch):
    mod = _load_mcp_server_module()
    captured: dict[str, object] = {}

    async def fake_job_get(_job_id: str, ctx=None):  # noqa: ANN001,ARG001
        return {"ok": True, "job_id": "parent-1", "kind": "gemini_web.ask", "status": "completed"}

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        captured["idempotency_key"] = idempotency_key
        captured["kind"] = kind
        captured["input"] = input
        captured["params"] = params
        captured["client"] = client
        return {"ok": True, "job_id": "job-followup-2", "kind": kind, "status": "queued"}

    monkeypatch.setattr(mod, "chatgptrest_job_get", fake_job_get)
    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_followup(
            idempotency_key="idem-followup-2",
            parent_job_id="parent-1",
            question="continue research",
            ctx=None,
        )
    )

    assert out["ok"] is True
    params = captured["params"]
    assert isinstance(params, dict)
    assert "deep_research" not in params


def test_chatgptrest_result_marks_non_final_completed_answers_for_review(monkeypatch):
    mod = _load_mcp_server_module()
    calls: list[tuple[str, str]] = []

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        calls.append((method, url))
        if url.endswith("/v1/jobs/job-short-1"):
            return {
                "ok": True,
                "job_id": "job-short-1",
                "kind": "chatgpt_web.ask",
                "status": "completed",
                "completion_quality": "completed_under_min_chars",
            }
        if "/v1/jobs/job-short-1/answer?" in url:
            return {
                "ok": True,
                "content": "short answer",
                "total_bytes": 12,
                "length": 12,
                "offset": 0,
            }
        raise AssertionError(f"unexpected url: {url}")

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    async def fake_prefetch_get(_job_id: str):  # noqa: ANN001
        return None

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(mod, "_answer_prefetch_get", fake_prefetch_get)

    out = asyncio.run(mod.chatgptrest_result("job-short-1", include_answer=True, max_answer_chars=100))

    assert out["status"] == "completed"
    assert out["answer"] == "short answer"
    assert out["completion_quality"] == "completed_under_min_chars"
    assert out["action_hint"] == "review_completed_answer"
    assert any(url.endswith("/v1/jobs/job-short-1") for _method, url in calls)
    assert any("/v1/jobs/job-short-1/answer?" in url for _method, url in calls)


def test_chatgptrest_result_reads_chunked_answer_payload(monkeypatch):
    mod = _load_mcp_server_module()

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        if url.endswith("/v1/jobs/job-chunk-1"):
            return {
                "ok": True,
                "job_id": "job-chunk-1",
                "kind": "chatgpt_web.ask",
                "status": "completed",
                "completion_quality": "final",
            }
        if "/v1/jobs/job-chunk-1/answer?" in url:
            return {
                "ok": True,
                "chunk": "chunked answer",
                "returned_chars": 14,
                "offset": 0,
                "next_offset": None,
                "done": True,
            }
        raise AssertionError(f"unexpected url: {url}")

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    async def fake_prefetch_get(_job_id: str):  # noqa: ANN001
        return None

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(mod, "_answer_prefetch_get", fake_prefetch_get)

    out = asyncio.run(mod.chatgptrest_result("job-chunk-1", include_answer=True, max_answer_chars=100))

    assert out["status"] == "completed"
    assert out["answer"] == "chunked answer"
    assert out["answer_length"] == 14
    assert out["answer_offset"] == 0
    assert out["answer_truncated"] is False
    assert out["answer_source"] == "api"
    assert out["action_hint"] == "answer_ready"


def test_chatgptrest_result_prefetch_cache_supports_chunk_normalized_entries(monkeypatch):
    mod = _load_mcp_server_module()

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        if url.endswith("/v1/jobs/job-cache-1"):
            return {
                "ok": True,
                "job_id": "job-cache-1",
                "kind": "chatgpt_web.ask",
                "status": "completed",
                "completion_quality": "final",
            }
        raise AssertionError(f"unexpected url: {url}")

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    async def fake_prefetch_get(_job_id: str):  # noqa: ANN001
        return {
            "content": "cached chunk answer",
            "offset": 0,
            "length": 19,
            "total_bytes": 19,
            "next_offset": None,
            "done": True,
        }

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(mod, "_answer_prefetch_get", fake_prefetch_get)

    out = asyncio.run(mod.chatgptrest_result("job-cache-1", include_answer=True, max_answer_chars=100))

    assert out["status"] == "completed"
    assert out["answer"] == "cached chunk answer"
    assert out["answer_source"] == "prefetch_cache"
    assert out["answer_truncated"] is False
    assert out["action_hint"] == "answer_ready"


def test_answer_prefetch_normalizes_chunk_payload(monkeypatch):
    from chatgptrest.mcp import _answer_cache

    _answer_cache._CACHE.clear()

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        if "/v1/jobs/job-prefetch-1/answer?" in url:
            return {
                "ok": True,
                "chunk": "prefetched answer",
                "returned_chars": 17,
                "offset": 0,
                "next_offset": None,
                "done": True,
            }
        raise AssertionError(f"unexpected url: {url}")

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(_answer_cache.asyncio, "to_thread", fake_to_thread)

    asyncio.run(
        _answer_cache.prefetch(
            "job-prefetch-1",
            http_json_fn=fake_http_json,
            base_url="http://example.test",
            auth_headers={},
        )
    )
    cached = asyncio.run(_answer_cache.get("job-prefetch-1"))

    assert cached is not None
    assert cached["content"] == "prefetched answer"
    assert cached["length"] == 17
    assert cached["done"] is True
    assert cached["next_offset"] is None
