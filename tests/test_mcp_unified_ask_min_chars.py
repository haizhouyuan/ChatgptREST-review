from __future__ import annotations

import asyncio
import importlib

from chatgptrest.mcp._bg_wait_config import BackgroundWaitConfig


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
    assert captured["client"]["name"] == "chatgptrest_chatgpt_ask_submit"
    params = captured["params"]
    assert isinstance(params, dict)
    assert params.get("min_chars") == 800


def test_chatgptrest_ask_relaxes_chatgpt_default_min_chars_for_compact_output(monkeypatch):
    mod = _load_mcp_server_module()
    captured: dict[str, object] = {}

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        captured["params"] = params
        return {"ok": True, "job_id": "job-chatgpt-compact-1", "kind": kind, "status": "queued"}

    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-chatgpt-compact-1",
            question="只基于附件，用中文用 4 条以内要点回答当前最明确的结论是什么。",
            provider="chatgpt",
            auto_wait=False,
            notify_done=False,
        )
    )

    assert out["ok"] is True
    params = captured["params"]
    assert isinstance(params, dict)
    assert params.get("min_chars") == 200


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
    assert captured["client"]["name"] == "chatgptrest_gemini_ask_submit"
    assert out["requested_preset"] == "auto"
    assert out["effective_preset"] == "pro"
    assert out["provider_capability_profile"]["auto_semantics"] == "alias_to_pro"
    assert out["rewrite_reason"] == "gemini_alias_to_pro"
    params = captured["params"]
    assert isinstance(params, dict)
    assert params.get("min_chars") == 200


def test_chatgptrest_ask_records_execution_lane_truth_for_standard_lane(monkeypatch):
    mod = _load_mcp_server_module()
    captured: dict[str, object] = {}

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        captured["kind"] = kind
        captured["params"] = params
        captured["client"] = client
        return {"ok": True, "job_id": "job-chatgpt-lane-1", "kind": kind, "status": "queued"}

    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-chatgpt-lane-1",
            question="请基于当前预算文档输出一页结论摘要",
            provider="chatgpt",
            preset="auto",
            requested_execution_lane="web_standard",
            premium_allowed=False,
            task_object_contract={"object_type": "document", "object_ref": "docs/budget.md"},
            auto_wait=False,
            notify_done=False,
        )
    )

    assert out["ok"] is True
    assert out["requested_execution_lane"] == "web_standard"
    assert out["effective_execution_lane"] == "web_standard"
    assert out["premium_allowed"] is False
    assert out["premium_justified"] is False
    assert out["task_object_contract"]["object_ref"] == "docs/budget.md"
    assert captured["params"]["premium_allowed"] is False
    assert captured["client"]["execution_governance"]["requested_execution_lane"] == "web_standard"
    assert captured["client"]["execution_governance"]["effective_execution_lane"] == "web_standard"


def test_chatgptrest_ask_blocks_gemini_auto_when_premium_not_allowed(monkeypatch):
    mod = _load_mcp_server_module()
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-gemini-premium-block-1",
            question="请给一个预算风险判断",
            provider="gemini",
            preset="auto",
            premium_allowed=False,
            auto_wait=False,
            notify_done=False,
        )
    )

    assert out["ok"] is False
    assert out["status"] == "preflight_blocked"
    assert "premium_allowed" in out["blocking_reasons"]
    assert out["requested_preset"] == "auto"
    assert out["effective_preset"] == "pro"
    assert out["effective_execution_lane"] == "web_premium"


def test_chatgptrest_ask_blocks_execution_lane_mismatch(monkeypatch):
    mod = _load_mcp_server_module()
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-chatgpt-lane-mismatch-1",
            question="请给一个预算风险判断",
            provider="chatgpt",
            preset="pro_extended",
            requested_execution_lane="web_standard",
            premium_allowed=True,
            preflight={
                "task_goal_clear": True,
                "attachments_complete": True,
                "question_not_trivial": True,
                "premium_justified": True,
            },
            provider_selection={
                "requested_provider": "chatgpt",
                "requested_preset": "pro_extended",
                "reason": "需要更长结论",
            },
            auto_wait=False,
            notify_done=False,
        )
    )

    assert out["ok"] is False
    assert out["status"] == "preflight_blocked"
    assert "requested_execution_lane" in out["blocking_reasons"]
    assert out["requested_execution_lane"] == "web_standard"
    assert out["effective_execution_lane"] == "web_premium"


def test_chatgptrest_ask_returns_push_receipt_when_background_wait_starts(monkeypatch):
    mod = _load_mcp_server_module()
    captured: dict[str, object] = {}

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        captured["client"] = client
        return {
            "ok": True,
            "job_id": "job-chatgpt-2",
            "kind": kind,
            "status": "queued",
            "estimated_wait_seconds": 420,
        }

    async def fake_background_wait_start(*, job_id, cfg, ctx=None):  # noqa: ANN001,ARG001
        captured["cfg"] = cfg
        return {
            "ok": True,
            "watch_id": "wait-1",
            "watch_status": "running",
            "running": True,
            "already_running": False,
        }

    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_background_wait_start", fake_background_wait_start)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-chatgpt-2",
            question="请基于当前仓代码做一个简短评审结论",
            provider="chatgpt",
            preset="pro_extended",
            preflight={
                "task_goal_clear": True,
                "attachments_complete": True,
                "question_not_trivial": True,
                "premium_justified": True,
            },
            provider_selection={
                "requested_provider": "chatgpt",
                "requested_preset": "pro_extended",
                "reason": "需要 Pro 长文判断",
            },
            client_context={
                "origin": "hermes-workbench",
                "task_id": "tsk-123",
                "state_file": "/tmp/workbench-state.json",
            },
            delivery_preference="push_only",
            auto_wait=True,
            notify_done=False,
        )
    )

    assert out["ok"] is True
    assert out["accepted"] is True
    assert out["completion_mode"] == "push"
    assert out["push_enabled"] is True
    assert out["front_action"] == "return_now"
    assert out["expected_wait_bucket"] == "medium"
    assert out["watch_id"] == "wait-1"
    assert out["client_context"]["task_id"] == "tsk-123"
    assert captured["client"]["client_context"]["task_id"] == "tsk-123"
    assert captured["cfg"].push_context["task_id"] == "tsk-123"
    assert captured["cfg"].auto_codex_autofix is False
    assert out["preflight"]["blocking_reasons"] == []


def test_chatgptrest_ask_does_not_start_background_wait_for_foreground_delivery(monkeypatch):
    mod = _load_mcp_server_module()

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        return {
            "ok": True,
            "job_id": "job-chatgpt-foreground-1",
            "kind": kind,
            "status": "queued",
            "estimated_wait_seconds": 120,
        }

    async def fake_background_wait_start(**_kwargs):  # noqa: ANN001
        raise AssertionError("foreground_wait delivery should not auto-start background push")

    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_background_wait_start", fake_background_wait_start)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-chatgpt-foreground-1",
            question="请给一个简短状态结论",
            provider="chatgpt",
            delivery_preference="foreground_wait",
            auto_wait=True,
            notify_done=False,
        )
    )

    assert out["ok"] is True
    assert out["completion_mode"] == "foreground_wait"
    assert out["push_enabled"] is False
    assert "watch_id" not in out


def test_background_wait_start_accepts_cfg_object(monkeypatch):
    mod = _load_mcp_server_module()

    async def fake_runner(**_kwargs):  # noqa: ANN001
        return None

    monkeypatch.setattr(mod, "_background_wait_runner", fake_runner)
    monkeypatch.setattr(mod, "_background_wait_stateless_http_default", lambda: False)

    out = asyncio.run(
        mod._background_wait_start(  # noqa: SLF001
            job_id="job-cfg-1",
            timeout_seconds=1,
            poll_seconds=1.0,
            notify_controller=False,
            notify_done=False,
            auto_repair_check=False,
            auto_repair_check_mode="quick",
            auto_repair_check_timeout_seconds=60,
            auto_repair_check_probe_driver=True,
            auto_repair_check_capture_ui=False,
            auto_repair_check_recent_failures=5,
            auto_repair_notify_controller=False,
            auto_repair_notify_done=False,
            auto_codex_autofix=True,
            auto_codex_autofix_timeout_seconds=600,
            auto_codex_autofix_model=None,
            auto_codex_autofix_max_risk="low",
            auto_codex_autofix_allow_actions=None,
            auto_codex_autofix_apply_actions=True,
            force_restart=False,
            cfg=BackgroundWaitConfig(
                timeout_seconds=321,
                poll_seconds=2.5,
                notify_controller=False,
                notify_done=False,
            ),
            ctx=None,
        )
    )

    assert out["ok"] is True
    assert out["watch_id"].startswith("wait-")
    assert out["timeout_seconds"] == 321
    assert out["poll_seconds"] == 2.5


def test_background_wait_start_accepts_cfg_without_flat_kwargs(monkeypatch):
    mod = _load_mcp_server_module()

    async def fake_runner(**_kwargs):  # noqa: ANN001
        return None

    monkeypatch.setattr(mod, "_background_wait_runner", fake_runner)
    monkeypatch.setattr(mod, "_background_wait_stateless_http_default", lambda: False)

    out = asyncio.run(
        mod._background_wait_start(  # noqa: SLF001
            job_id="job-cfg-2",
            cfg=BackgroundWaitConfig(
                timeout_seconds=654,
                poll_seconds=3.5,
                notify_controller=False,
                notify_done=False,
            ),
            ctx=None,
        )
    )

    assert out["ok"] is True
    assert out["watch_id"].startswith("wait-")
    assert out["timeout_seconds"] == 654
    assert out["poll_seconds"] == 3.5


def test_chatgptrest_ask_blocks_invalid_preflight_for_premium_request(monkeypatch):
    mod = _load_mcp_server_module()
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-chatgpt-3",
            question="请基于当前仓代码做一个简短评审结论",
            provider="chatgpt",
            preset="pro_extended",
            preflight={
                "task_goal_clear": True,
                "attachments_complete": True,
                "question_not_trivial": True,
                "premium_justified": False,
            },
            provider_selection={
                "requested_provider": "chatgpt",
                "requested_preset": "pro_extended",
                "reason": "",
            },
            delivery_preference="push_only",
            auto_wait=True,
            notify_done=False,
        )
    )

    assert out["ok"] is False
    assert out["status"] == "preflight_blocked"
    assert "premium_justified" in out["blocking_reasons"]
    assert "provider_selection.reason" in out["blocking_reasons"]
    assert out["effective_preset"] == "pro_extended"
    assert out["provider_capability_profile"]["provider_id"] == "chatgpt"


def test_chatgptrest_ask_treats_gemini_auto_as_premium_for_preflight(monkeypatch):
    mod = _load_mcp_server_module()
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-gemini-premium-1",
            question="请评审这份方案并给出完整判断。",
            provider="gemini",
            preset="auto",
            preflight={
                "task_goal_clear": True,
                "attachments_complete": True,
                "question_not_trivial": True,
                "premium_justified": False,
            },
            provider_selection={
                "requested_provider": "gemini",
                "requested_preset": "auto",
                "reason": "",
            },
            delivery_preference="push_only",
            auto_wait=True,
            notify_done=False,
        )
    )

    assert out["ok"] is False
    assert out["status"] == "preflight_blocked"
    assert "premium_justified" in out["blocking_reasons"]
    assert "provider_selection.reason" in out["blocking_reasons"]
    assert out["requested_preset"] == "auto"
    assert out["effective_preset"] == "pro"
    assert out["provider_capability_profile"]["auto_semantics"] == "alias_to_pro"
    assert out["rewrite_reason"] == "gemini_alias_to_pro"


def test_chatgptrest_ask_uses_background_wait_floor_for_push_delivery(monkeypatch):
    mod = _load_mcp_server_module()
    captured: dict[str, object] = {}

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        captured["params"] = params
        return {"ok": True, "job_id": "job-chatgpt-bgfloor-1", "kind": kind, "status": "queued"}

    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-chatgpt-bgfloor-1",
            question="请基于附件给出完整判断。",
            provider="chatgpt",
            delivery_preference="push_only",
            max_wait_seconds=30,
            auto_wait=False,
            notify_done=False,
        )
    )

    assert out["ok"] is True
    params = captured["params"]
    assert isinstance(params, dict)
    assert params.get("max_wait_seconds") == 1800


def test_chatgptrest_ask_preserves_foreground_wait_max_wait_seconds(monkeypatch):
    mod = _load_mcp_server_module()
    captured: dict[str, object] = {}

    async def fake_job_create(*, idempotency_key, kind, input, params, client, ctx=None):  # noqa: ANN001,ARG001,A002
        captured["params"] = params
        return {"ok": True, "job_id": "job-chatgpt-fg-1", "kind": kind, "status": "queued"}

    monkeypatch.setattr(mod, "chatgptrest_job_create", fake_job_create)
    monkeypatch.setattr(mod, "_tmux_notify", lambda _msg: None)

    out = asyncio.run(
        mod.chatgptrest_ask(
            idempotency_key="idem-chatgpt-fg-1",
            question="请基于附件给出完整判断。",
            provider="chatgpt",
            delivery_preference="foreground_wait",
            max_wait_seconds=45,
            auto_wait=True,
            notify_done=False,
        )
    )

    assert out["ok"] is True
    params = captured["params"]
    assert isinstance(params, dict)
    assert params.get("max_wait_seconds") == 45


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
    assert out["completion_quality"] == "completed_under_min_chars"
    assert out["answer_state"] == "provisional"
    assert out["action_hint"] == "await_research_finality"
    assert "answer" not in out
    assert any(url.endswith("/v1/jobs/job-short-1") for _method, url in calls)
    assert not any("/v1/jobs/job-short-1/answer?" in url for _method, url in calls)


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


def test_chatgptrest_result_completed_non_final_research_waits_for_contract(monkeypatch):
    mod = _load_mcp_server_module()
    calls: list[tuple[str, str]] = []

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        calls.append((method, url))
        if url.endswith("/v1/jobs/job-provisional-1"):
            return {
                "ok": True,
                "job_id": "job-provisional-1",
                "kind": "chatgpt_web.ask",
                "status": "completed",
                "completion_contract": {
                    "answer_state": "provisional",
                    "authoritative_answer_path": "jobs/job-provisional-1/answer.md",
                    "answer_provenance": {"contract_class": "research"},
                },
            }
        raise AssertionError(f"unexpected url: {url}")

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    async def fake_prefetch_get(_job_id: str):  # noqa: ANN001
        return None

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(mod, "_answer_prefetch_get", fake_prefetch_get)

    out = asyncio.run(mod.chatgptrest_result("job-provisional-1", include_answer=True, max_answer_chars=100))

    assert out["status"] == "completed"
    assert out["answer_state"] == "provisional"
    assert out["authoritative_answer_path"] == "jobs/job-provisional-1/answer.md"
    assert out["action_hint"] == "await_research_finality"
    assert "answer" not in out
    assert calls == [("GET", f"{mod._base_url()}/v1/jobs/job-provisional-1")]


def test_chatgptrest_result_completed_parent_points_to_authoritative_child(monkeypatch):
    mod = _load_mcp_server_module()
    calls: list[tuple[str, str]] = []

    def fake_http_json(*, method: str, url: str, **_kwargs):  # noqa: ARG001
        calls.append((method, url))
        if url.endswith("/v1/jobs/job-parent-1"):
            return {
                "ok": True,
                "job_id": "job-parent-1",
                "kind": "chatgpt_web.ask",
                "status": "completed",
                "completion_contract": {
                    "answer_state": "provisional",
                    "authoritative_job_id": "job-child-1",
                    "authoritative_answer_path": "jobs/job-child-1/answer.md",
                    "answer_provenance": {"contract_class": "research", "canonical_source": "conversation_authoritative_resolution"},
                },
                "canonical_answer": {
                    "ready": False,
                    "answer_state": "provisional",
                    "authoritative_job_id": "job-child-1",
                    "authoritative_answer_path": "jobs/job-child-1/answer.md",
                },
            }
        raise AssertionError(f"unexpected url: {url}")

    async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    async def fake_prefetch_get(_job_id: str):  # noqa: ANN001
        return None

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    monkeypatch.setattr(mod.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(mod, "_answer_prefetch_get", fake_prefetch_get)

    out = asyncio.run(mod.chatgptrest_result("job-parent-1", include_answer=True, max_answer_chars=100))

    assert out["status"] == "completed"
    assert out["answer_state"] == "provisional"
    assert out["authoritative_job_id"] == "job-child-1"
    assert out["authoritative_answer_path"] == "jobs/job-child-1/answer.md"
    assert out["action_hint"] == "fetch_authoritative_answer"
    assert "answer" not in out
    assert calls == [("GET", f"{mod._base_url()}/v1/jobs/job-parent-1")]


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
