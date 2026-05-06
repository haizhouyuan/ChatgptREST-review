"""Tests for Feishu async-first handler architecture.

Validates:
  - Webhook returns within 1s (no sync blocking)
  - Ack card sent immediately before advisor completes
  - Result card sent after completion
  - Error card shows friendly Chinese messages
  - Timing info shown in completion card
  - Full-text link shown when answer is truncated
  - Background thread cleanup
  - Callback async behavior
"""

import hashlib
import json
import time
import threading
import pytest


# ── Helpers ──────────────────────────────────────────────────────


def _make_handler(**kwargs):
    from chatgptrest.advisor.feishu_handler import FeishuHandler
    kwargs.setdefault("webhook_secret", "test-secret")
    return FeishuHandler(**kwargs)


def _msg_payload(message_id="msg_test", chat_id="chat_test", text="测试消息"):
    return {
        "event": {
            "message": {
                "message_id": message_id,
                "chat_id": chat_id,
                "content": f'{{"text": "{text}"}}',
            },
            "sender": {"sender_id": {"user_id": "user_test"}},
        }
    }


def _signed_request(payload: dict, *, secret: str = "test-secret") -> tuple[bytes, dict[str, str]]:
    raw_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(time.time())
    nonce = "test-nonce"
    content = f"{timestamp}\n{nonce}\n{secret}\n".encode() + raw_body
    signature = hashlib.sha256(content).hexdigest()
    headers = {
        "X-Lark-Request-Timestamp": timestamp,
        "X-Lark-Request-Nonce": nonce,
        "X-Lark-Signature": signature,
    }
    return raw_body, headers


def _deliver(handler, payload: dict, *, secret: str = "test-secret") -> dict:
    raw_body, headers = _signed_request(payload, secret=secret)
    return handler.handle_webhook(payload, raw_body=raw_body, headers=headers)


class _TraceRecorder:
    def __init__(self):
        self.updates = []
        self.ended = 0

    def update(self, **kwargs):
        self.updates.append(kwargs)

    def end(self):
        self.ended += 1


# ── T-ASYNC-1: Webhook returns within 1 second ──────────────────


class TestWebhookResponseTime:
    """The webhook must never block on advisor_fn."""

    def test_returns_fast_with_slow_advisor(self):
        """Even with a 10s advisor_fn, webhook returns instantly."""
        def slow_advisor(msg, trace_id=None):
            time.sleep(10)  # simulate very slow LLM call
            return {"selected_route": "slow", "answer": "done"}

        handler = _make_handler(advisor_fn=slow_advisor)
        start = time.time()
        result = _deliver(handler, _msg_payload())
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Webhook took {elapsed:.2f}s — should be < 1s"
        assert result["status"] == "accepted"

    def test_returns_accepted_status(self):
        handler = _make_handler()
        result = _deliver(handler, _msg_payload(message_id="msg_status"))
        assert result["status"] == "accepted"
        assert "trace_id" in result
        assert result["message_id"] == "msg_status"

    def test_concurrent_duplicate_delivery_is_claimed_once(self, tmp_path):
        cards = []
        advisor_started = threading.Event()
        advisor_gate = threading.Event()
        call_count = 0
        call_lock = threading.Lock()

        def gated_advisor(msg, trace_id=None):
            nonlocal call_count
            with call_lock:
                call_count += 1
            advisor_started.set()
            advisor_gate.wait(timeout=5)
            return {"selected_route": "hybrid", "answer": "并发去重测试完成"}

        handler = _make_handler(
            advisor_fn=gated_advisor,
            send_card_fn=lambda cid, card: cards.append(card),
            dedup_db_path=str(tmp_path / "dedup.db"),
        )
        payload = _msg_payload(message_id="msg_concurrent_dup")

        thread_count = 8
        barrier = threading.Barrier(thread_count)
        results: list[dict] = []
        results_lock = threading.Lock()

        def _invoke():
            barrier.wait(timeout=2)
            result = _deliver(handler, payload)
            with results_lock:
                results.append(result)

        threads = [threading.Thread(target=_invoke, daemon=True) for _ in range(thread_count)]
        for thread in threads:
            thread.start()

        advisor_started.wait(timeout=2)
        advisor_gate.set()

        for thread in threads:
            thread.join(timeout=2)

        time.sleep(0.5)

        accepted = [row for row in results if row.get("status") == "accepted"]
        duplicates = [row for row in results if row.get("status") == "duplicate"]

        assert len(results) == thread_count
        assert len(accepted) == 1
        assert len(duplicates) == thread_count - 1
        assert call_count == 1
        assert len(cards) == 2


# ── T-ASYNC-2: Ack card sent before advisor completes ────────────


class TestAckCard:
    """Ack card should arrive before advisor finishes."""

    def test_ack_card_sent_immediately(self):
        cards = []
        advisor_started = threading.Event()
        advisor_gate = threading.Event()

        def gated_advisor(msg, trace_id=None):
            advisor_started.set()
            advisor_gate.wait(timeout=5)  # block until we release
            return {"selected_route": "test", "answer": "result"}

        handler = _make_handler(
            advisor_fn=gated_advisor,
            send_card_fn=lambda cid, card: cards.append(card),
        )
        _deliver(handler, _msg_payload(message_id="msg_ack"))

        # Wait for advisor to start (ack card should be sent before advisor runs)
        advisor_started.wait(timeout=2)
        time.sleep(0.1)  # small buffer for card send

        # Ack card should be sent already (before advisor completes)
        assert len(cards) >= 1, "Ack card should be sent before advisor completes"
        ack = cards[0]
        assert "收到" in ack.get("header", {}).get("title", {}).get("content", "")

        # Now release advisor and wait for completion
        advisor_gate.set()
        time.sleep(0.5)

        # Should have ack + completion = 2 cards
        assert len(cards) == 2
        completion = cards[1]
        assert "完成" in completion.get("header", {}).get("title", {}).get("content", "")


# ── T-ASYNC-3: Result card after completion ──────────────────────


class TestResultCard:
    """Result card should contain route, answer, and timing."""

    def test_completion_card_has_timing(self):
        cards = []
        def fast_advisor(msg, trace_id=None):
            time.sleep(0.2)
            return {"selected_route": "quick_answer", "answer": "快速回答内容"}

        handler = _make_handler(
            advisor_fn=fast_advisor,
            send_card_fn=lambda cid, card: cards.append(card),
        )
        _deliver(handler, _msg_payload(message_id="msg_timing"))
        time.sleep(1.0)

        assert len(cards) == 2
        completion = cards[1]
        # Check that timing/note is present
        note_elements = [e for e in completion.get("elements", []) if e.get("tag") == "note"]
        assert note_elements, "Should have note with timing"
        note_text = str(note_elements[0])
        assert "耗时" in note_text or "trace" in note_text

    def test_message_background_starts_and_closes_trace(self, monkeypatch):
        import chatgptrest.observability as obs
        from chatgptrest.advisor.feishu_handler import FeishuEvent

        trace = _TraceRecorder()
        started = []

        def fake_start_request_trace(**kwargs):
            started.append(kwargs)
            return trace

        monkeypatch.setattr(obs, "start_request_trace", fake_start_request_trace)

        handler = _make_handler(
            advisor_fn=lambda msg, trace_id=None: {
                "selected_route": "funnel",
                "status": "completed",
                "answer": "处理完成",
                "conversation_url": "https://chatgpt.com/c/test",
            },
            send_card_fn=lambda cid, card: None,
        )
        handler._process_message_background(
            FeishuEvent(
                event_type="message",
                message_id="msg_trace",
                user_id="user_trace",
                chat_id="chat_trace",
                text="做一个 dashboard",
            ),
            "01234567-89ab-cdef-0123-456789abcdef",
        )

        assert started and started[0]["name"] == "feishu_message"
        assert started[0]["trace_id"] == "0123456789abcdef0123456789abcdef"
        assert started[0]["session_id"] == "chat_trace"
        assert trace.ended == 1
        assert any(update["metadata"]["route"] == "funnel" for update in trace.updates)
        assert any(update["metadata"]["has_conversation_url"] is True for update in trace.updates)

    def test_completion_card_shows_route_label(self):
        cards = []
        handler = _make_handler(
            advisor_fn=lambda msg, trace_id=None: {"selected_route": "deep_research", "answer": "分析结果"},
            send_card_fn=lambda cid, card: cards.append(card),
        )
        _deliver(handler, _msg_payload(message_id="msg_route"))
        time.sleep(0.5)

        completion = cards[1]
        title = completion["header"]["title"]["content"]
        assert "深度研究" in title

    def test_truncated_answer_with_link(self):
        """Long answers get truncated with full-text link."""
        cards = []
        long_answer = "x" * 1000
        handler = _make_handler(
            advisor_fn=lambda msg, trace_id=None: {
                "selected_route": "hybrid",
                "answer": long_answer,
                "conversation_url": "https://chatgpt.com/c/test123",
            },
            send_card_fn=lambda cid, card: cards.append(card),
        )
        _deliver(handler, _msg_payload(message_id="msg_trunc"))
        time.sleep(0.5)

        completion = cards[1]
        # Should have truncation indicator
        answer_elements = [e for e in completion.get("elements", [])
                          if e.get("tag") == "div" and "截断" in str(e)]
        assert answer_elements, "Long answer should show truncation notice"

        # Should have a "view full" action button
        action_elements = [e for e in completion.get("elements", [])
                          if e.get("tag") == "action"]
        assert action_elements, "Should show full-text button for truncated answers"


# ── T-ASYNC-4: Friendly error messages ───────────────────────────


class TestFriendlyErrors:
    """Error cards should show friendly Chinese messages, not raw exceptions."""

    def test_friendly_error_mapping(self):
        from chatgptrest.advisor.feishu_handler import _friendly_error
        # Known error types
        assert "繁忙" in _friendly_error("MaxAttemptsExceeded: too many retries")
        assert "中断" in _friendly_error("TargetClosedError: page closed")
        assert "上传" in _friendly_error("DriveUploadNotReady: quota exceeded")
        assert "超时" in _friendly_error("WaitNoProgressTimeout: no response")
        assert "连接" in _friendly_error("InfraError: connection refused")
        # Unknown error - still friendly
        result = _friendly_error("a" * 200)
        assert "处理" in result  # generic fallback

    def test_error_card_no_traceback(self):
        """Error card should NOT expose Python exception details."""
        cards = []
        def failing_advisor(msg, trace_id=None):
            raise RuntimeError("TargetClosedError: Locator.count: Target page closed")

        handler = _make_handler(
            advisor_fn=failing_advisor,
            send_card_fn=lambda cid, card: cards.append(card),
        )
        _deliver(handler, _msg_payload(message_id="msg_err"))
        time.sleep(0.5)

        assert len(cards) == 2  # ack + error
        error_card = cards[1]
        card_text = str(error_card)
        assert "Locator.count" not in card_text, "Should not expose raw exception"
        assert "处理未成功" in error_card["header"]["title"]["content"]
        # Should show friendly message
        assert "中断" in card_text or "恢复" in card_text

    def test_error_card_has_retry_hint(self):
        cards = []
        handler = _make_handler(
            advisor_fn=lambda msg, trace_id=None: (_ for _ in ()).throw(TimeoutError("slow")),
            send_card_fn=lambda cid, card: cards.append(card),
        )
        _deliver(handler, _msg_payload(message_id="msg_retry"))
        time.sleep(0.5)

        error_card = cards[1]
        card_text = str(error_card)
        assert "重试" in card_text


# ── T-ASYNC-5: Callback async behavior ──────────────────────────


class TestCallbackAsync:
    """Button callbacks should also be async-first."""

    def test_confirm_returns_immediately(self):
        def slow_resume(tid, action):
            time.sleep(5)
            return {"resumed": True}

        handler = _make_handler(resume_fn=slow_resume)
        payload = {
            "event": {
                "action": {
                    "tag": "btn_async",
                    "value": {"action": "confirm", "trace_id": "tr_async"},
                },
                "operator": {"user_id": "u1"},
            }
        }
        start = time.time()
        result = _deliver(handler, payload)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Callback took {elapsed:.2f}s — should be < 1s"
        assert result["status"] == "accepted"

    def test_reject_is_synchronous(self):
        """Non-blocking actions (reject, modify) stay synchronous."""
        handler = _make_handler()
        payload = {
            "event": {
                "action": {
                    "tag": "btn_reject",
                    "value": {"action": "reject", "trace_id": "tr_rej"},
                },
                "operator": {"user_id": "u1"},
            }
        }
        result = _deliver(handler, payload)
        assert result["status"] == "rejected"

    def test_callback_background_starts_and_closes_trace(self, monkeypatch):
        import chatgptrest.observability as obs
        from chatgptrest.advisor.feishu_handler import FeishuEvent

        trace = _TraceRecorder()
        started = []

        def fake_start_request_trace(**kwargs):
            started.append(kwargs)
            return trace

        monkeypatch.setattr(obs, "start_request_trace", fake_start_request_trace)

        handler = _make_handler(
            resume_fn=lambda trace_id, action: {"status": "resumed", "trace_id": trace_id, "action": action},
        )
        handler._process_callback_background(
            FeishuEvent(
                event_type="button_callback",
                user_id="user_callback",
                action_value="confirm",
                trace_id="89abcdef-0123-4567-89ab-cdef01234567",
            ),
        )

        assert started and started[0]["name"] == "feishu_callback"
        assert started[0]["trace_id"] == "89abcdef0123456789abcdef01234567"
        assert trace.ended == 1
        assert any(update["metadata"]["status"] == "resumed" for update in trace.updates)
