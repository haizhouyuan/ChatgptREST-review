"""Tests for Phase 3: Feishu Handler, Dispatch, Simple Routes, Advisor API.

Comprehensive test suite covering T3.1-T3.4.
"""

import hashlib
import json
import time
import uuid

import pytest


def _signed_request(payload: dict, *, secret: str = "test-secret") -> tuple[bytes, dict[str, str]]:
    raw_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(time.time())
    nonce = "test-nonce"
    signature = hashlib.sha256(f"{timestamp}\n{nonce}\n{secret}\n".encode() + raw_body).hexdigest()
    return raw_body, {
        "X-Lark-Request-Timestamp": timestamp,
        "X-Lark-Request-Nonce": nonce,
        "X-Lark-Signature": signature,
    }


# ── T3.1: Feishu Handler ─────────────────────────────────────────

class TestFeishuHandler:
    """Tests for Feishu webhook handler."""

    def _make_handler(self, **kwargs):
        from chatgptrest.advisor.feishu_handler import FeishuHandler
        kwargs.setdefault("webhook_secret", "test-secret")
        return FeishuHandler(**kwargs)

    def _deliver(self, handler, payload: dict, *, secret: str = "test-secret") -> dict:
        raw_body, headers = _signed_request(payload, secret=secret)
        return handler.handle_webhook(payload, raw_body=raw_body, headers=headers)

    def test_challenge_verification(self):
        handler = self._make_handler()
        result = self._deliver(handler, {"challenge": "test123"})
        assert result == {"challenge": "test123"}

    def test_message_event(self):
        handler = self._make_handler()
        payload = {
            "event": {
                "message": {
                    "message_id": "msg_001",
                    "chat_id": "chat_001",
                    "content": '{"text": "帮我写报告"}',
                },
                "sender": {"sender_id": {"user_id": "user_001"}},
            }
        }
        result = self._deliver(handler, payload)
        # Async-first: returns immediately with 'accepted'
        assert result["status"] == "accepted"
        assert result["trace_id"] != ""
        assert result["message_id"] == "msg_001"

    def test_message_dedup(self):
        handler = self._make_handler()
        payload = {
            "event": {
                "message": {
                    "message_id": "msg_dup",
                    "content": '{"text": "test"}',
                },
                "sender": {"sender_id": {"user_id": "u1"}},
            }
        }
        self._deliver(handler, payload)
        result = self._deliver(handler, payload)
        assert result["status"] == "duplicate"

    def test_button_callback_confirm(self):
        handler = self._make_handler(
            resume_fn=lambda tid, action: {"resumed": True}
        )
        payload = {
            "event": {
                "action": {
                    "tag": "btn_001",
                    "value": {"action": "confirm", "trace_id": "tr_001"},
                },
                "operator": {"user_id": "u1"},
            }
        }
        result = self._deliver(handler, payload)
        # Async-first: confirm returns 'accepted' and processes in background
        assert result["status"] == "accepted"
        assert result["trace_id"] == "tr_001"

    def test_button_callback_reject(self):
        handler = self._make_handler()
        payload = {
            "event": {
                "action": {
                    "tag": "btn_002",
                    "value": {"action": "reject", "trace_id": "tr_002"},
                },
                "operator": {"user_id": "u1"},
            }
        }
        result = self._deliver(handler, payload)
        assert result["status"] == "rejected"

    def test_card_json_structure(self):
        from chatgptrest.advisor.feishu_handler import FeishuCard
        card = FeishuCard(
            title="Test",
            intent_restatement="写报告",
            route="funnel",
            trace_id="tr_test",
        )
        j = card.to_card_json()
        assert j["msg_type"] == "interactive"
        assert "elements" in j["card"]
        # Has 3 buttons
        actions = j["card"]["elements"][-1]["actions"]
        assert len(actions) == 3

    def test_send_card_called(self, monkeypatch):
        """Async-first: background thread sends ack card + completion card."""
        import chatgptrest.advisor.feishu_handler as feishu_mod

        monkeypatch.setattr(feishu_mod, "_start_background_trace", lambda **kwargs: None)
        sent = []
        handler = self._make_handler(
            send_card_fn=lambda chat_id, card: sent.append((chat_id, card))
        )
        payload = {
            "event": {
                "message": {
                    "message_id": "msg_card",
                    "chat_id": "chat_card",
                    "content": '{"text": "test card"}',
                },
                "sender": {"sender_id": {"user_id": "u1"}},
            }
        }
        self._deliver(handler, payload)
        deadline = time.time() + 2.0
        while len(sent) < 2 and time.time() < deadline:
            time.sleep(0.05)
        # Async-first: ack card + completion card = 2 cards
        assert len(sent) == 2
        assert sent[0][0] == "chat_card"  # ack card
        assert sent[1][0] == "chat_card"  # completion card


# ── T3.2: Dispatch ───────────────────────────────────────────────

class TestDispatch:
    """Tests for Agent Teams dispatch."""

    def _make_dispatcher(self, **kwargs):
        from chatgptrest.advisor.dispatch import AgentDispatcher
        return AgentDispatcher(**kwargs)

    def test_build_context_package(self):
        from chatgptrest.advisor.dispatch import AgentDispatcher
        d = AgentDispatcher()
        ctx = d.build_context_package(
            {"project_card": {"title": "Test"}, "recommended_option": "A"},
            trace_id="tr_001",
        )
        assert ctx.trace_id == "tr_001"
        assert ctx.project_card == {"title": "Test"}
        assert ctx.reasoning_summary == "A"

    def test_dispatch_success(self):
        d = self._make_dispatcher()
        from chatgptrest.advisor.dispatch import ContextPackage
        ctx = ContextPackage(trace_id="tr_002", project_card={"title": "Test"})
        result = d.dispatch(ctx)
        assert result["status"] == "dispatched"
        assert result["trace_id"] == "tr_002"

    def test_dispatch_with_custom_hcom(self):
        calls = []
        d = self._make_dispatcher(
            hcom_fn=lambda ctx: (calls.append(ctx), {"ok": True})[1]
        )
        from chatgptrest.advisor.dispatch import ContextPackage
        ctx = ContextPackage(trace_id="tr_003")
        d.dispatch(ctx)
        assert len(calls) == 1

    def test_context_package_serialization(self):
        from chatgptrest.advisor.dispatch import ContextPackage
        ctx = ContextPackage(
            trace_id="tr_004",
            project_card={"title": "Test", "tasks": [{"name": "task1"}]},
            constraints=["budget", "timeline"],
        )
        j = ctx.to_json()
        assert "tr_004" in j
        assert "budget" in j


# ── T3.3: Simple Routes ──────────────────────────────────────────

class TestSimpleRoutes:
    """Tests for quick_ask and deep_research."""

    def test_quick_ask_no_hits(self):
        from chatgptrest.advisor.simple_routes import quick_ask
        result = quick_ask("test question")
        assert result.status == "no_answer"
        assert result.route == "quick_ask"

    def test_quick_ask_with_hits(self):
        from chatgptrest.advisor.simple_routes import quick_ask
        hits = [
            {"artifact_id": "a1", "title": "Doc 1", "snippet": "Answer text"},
            {"artifact_id": "a2", "title": "Doc 2", "snippet": "More text"},
        ]
        result = quick_ask(
            "test",
            kb_search_fn=lambda q, k: hits,
        )
        assert result.status == "success"
        assert len(result.evidence_refs) == 2
        assert "Answer text" in result.answer

    def test_quick_ask_latency(self):
        from chatgptrest.advisor.simple_routes import quick_ask
        result = quick_ask("test", kb_search_fn=lambda q, k: [{"id": "a1", "text": "x"}])
        assert result.latency_ms < 1000  # should be very fast

    def test_deep_research(self):
        from chatgptrest.advisor.simple_routes import deep_research
        result = deep_research(
            "分析竞品",
            kb_search_fn=lambda q, k: [{"artifact_id": "a1", "text": "竞品数据"}],
        )
        assert result.status == "success"
        assert result.route == "deep_research"
        assert len(result.answer) > 0

    def test_deep_research_custom_llm(self):
        from chatgptrest.advisor.simple_routes import deep_research
        result = deep_research(
            "analyze",
            llm_fn=lambda p, s: "Custom deep analysis result",
        )
        assert "Custom deep analysis" in result.answer

    def test_quick_ask_writeback(self):
        from chatgptrest.advisor.simple_routes import quick_ask
        writes = []
        result = quick_ask(
            "test",
            kb_search_fn=lambda q, k: [{"id": "a1", "text": "data"}],
            writeback_fn=lambda doc_id, text, w: writes.append((doc_id, w)),
        )
        assert len(writes) == 1
        assert writes[0][1] == 0.3  # quarantine weight


# ── T3.4: Advisor API ────────────────────────────────────────────

class TestAdvisorAPI:
    """Tests for the Advisor API."""

    def _make_api(self, **kwargs):
        from chatgptrest.advisor.advisor_api import AdvisorAPI
        return AdvisorAPI(**kwargs)

    def test_advise(self):
        api = self._make_api()
        result = api.advise("帮我写个报告")
        assert result["status"] == "completed"
        assert result["selected_route"] != ""
        assert result["trace_id"] != ""

    def test_get_trace(self):
        api = self._make_api()
        result = api.advise("test message")
        trace = api.get_trace(result["trace_id"])
        assert trace is not None
        assert trace["user_message"] == "test message"

    def test_get_trace_not_found(self):
        api = self._make_api()
        assert api.get_trace("nonexistent") is None

    def test_list_traces(self):
        api = self._make_api()
        api.advise("msg 1")
        api.advise("msg 2")
        traces = api.list_traces()
        assert len(traces) == 2

    def test_webhook_no_handler(self):
        api = self._make_api()
        result = api.handle_webhook({"test": True})
        assert result["status"] == "feishu_handler_not_configured"

    def test_custom_advisor_fn(self):
        api = self._make_api(
            advisor_fn=lambda state: {
                "selected_route": "custom",
                "route_rationale": "test",
            }
        )
        result = api.advise("custom test")
        assert result["selected_route"] == "custom"

    def test_advise_starts_and_closes_request_trace(self, monkeypatch):
        import chatgptrest.observability as obs

        started = []

        class TraceRecorder:
            def __init__(self):
                self.updates = []
                self.ended = 0

            def update(self, **kwargs):
                self.updates.append(kwargs)

            def end(self):
                self.ended += 1

        trace = TraceRecorder()

        def fake_start_request_trace(**kwargs):
            started.append(kwargs)
            return trace

        monkeypatch.setattr(obs, "start_request_trace", fake_start_request_trace)

        api = self._make_api(
            advisor_fn=lambda state: {
                "selected_route": "custom",
                "route_rationale": "test",
                "intent_top": "QUICK_QUESTION",
            }
        )
        result = api.advise("custom test", trace_id="01234567-89ab-cdef-0123-456789abcdef")

        assert result["selected_route"] == "custom"
        assert started and started[0]["name"] == "advisor_api"
        assert started[0]["trace_id"] == "0123456789abcdef0123456789abcdef"
        assert trace.ended == 1
        assert any(update["metadata"]["route"] == "custom" for update in trace.updates)
