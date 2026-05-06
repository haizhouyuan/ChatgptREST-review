"""Feishu Webhook Handler — receives Feishu events and drives the Advisor Graph.

Flow (async-first architecture):
  1. Receive webhook POST from Feishu (message or button callback)
  2. Verify signature (HMAC-SHA256) and timestamp freshness
  3. Dedup by message_id (persistent SQLite, survives restart)
  4. Return HTTP 200 immediately (< 1s)
  5. Background thread: send ack card → invoke advisor → send result card
  6. Handle button callbacks → resume LangGraph checkpoint (also async)

P0 fixes applied:
  - Signature verification with configurable secret
  - Persistent dedup via SQLite (not in-memory set)
  - trace_id passed through to advisor_fn
  - Card sending goes through outbox_fn (not direct side-effect)
  - Async-first: webhook never blocks on advisor_fn (P0 timeout fix)
  - Friendly error messages instead of raw exceptions
  - Progress ack card sent immediately on message receipt
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Friendly Error Mapping ────────────────────────────────────────

ERROR_FRIENDLY_MAP: dict[str, str] = {
    "MaxAttemptsExceeded": "模型暂时繁忙，已达最大重试次数，请稍后再试",
    "TargetClosedError": "浏览器连接中断，系统正在自动恢复",
    "DriveUploadNotReady": "文件上传服务暂时不可用，请稍后重试",
    "WaitNoProgressTimeout": "模型响应超时，请稍后重试",
    "WaitNoThreadUrlTimeout": "模型启动超时，请稍后重试",
    "InfraError": "基础设施连接失败，请检查网络后重试",
    "RuntimeError": "处理过程中发生错误，请重试",
    "TimeoutError": "处理超时，请稍后重试",
    "GeminiUnsupportedRegion": "Gemini 在当前区域不可用",
}


def _friendly_error(error: Exception | str) -> str:
    """Convert exception to user-friendly Chinese message."""
    err_str = str(error)
    err_type = type(error).__name__ if isinstance(error, Exception) else ""
    # Check if any known error pattern appears in the error string first
    # (more specific — e.g. RuntimeError wrapping TargetClosedError)
    for key, friendly in ERROR_FRIENDLY_MAP.items():
        if key.lower() in err_str.lower():
            return friendly
    # Then check Python exception type name
    if err_type in ERROR_FRIENDLY_MAP:
        return ERROR_FRIENDLY_MAP[err_type]
    # Fallback: generic but still friendly
    if len(err_str) > 100:
        return "处理过程中发生错误，请稍后重试或联系管理员"
    return f"处理出错: {err_str[:80]}"


def _start_background_trace(
    *,
    name: str,
    trace_id: str,
    user_id: str = "",
    session_id: str = "",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Create a Langfuse root span for background Feishu work if available."""
    normalized_trace_id = trace_id.replace("-", "").lower()
    if len(normalized_trace_id) != 32 or any(ch not in "0123456789abcdef" for ch in normalized_trace_id):
        normalized_trace_id = ""
    try:
        from chatgptrest.observability import start_request_trace

        return start_request_trace(
            name=name,
            user_id=user_id or "feishu",
            session_id=session_id or trace_id,
            trace_id=normalized_trace_id,
            tags=tags or ["openmind", "feishu"],
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.warning("Feishu background trace start failed: %s", exc)
        return None


def _close_background_trace(trace, *, metadata: dict[str, Any] | None = None) -> None:
    """Best-effort trace finalization for background Feishu work."""
    if not trace:
        return
    try:
        if metadata:
            trace.update(metadata=metadata)
        trace.end()
    except Exception:
        pass


# ── Models ────────────────────────────────────────────────────────

@dataclass
class FeishuEvent:
    """Parsed Feishu webhook event."""
    event_type: str = ""         # "message" | "button_callback"
    message_id: str = ""
    user_id: str = ""
    chat_id: str = ""
    text: str = ""
    timestamp: str = ""
    # Button callback fields
    action_value: str = ""       # "confirm" | "modify" | "reject"
    trace_id: str = ""           # for button callbacks, links back to trace

    @classmethod
    def from_webhook(cls, payload: dict[str, Any]) -> "FeishuEvent":
        """Parse a raw Feishu webhook payload."""
        event = payload.get("event", {})
        message = event.get("message", {})
        action = event.get("action", {})

        # Determine event type
        if "message" in event:
            return cls(
                event_type="message",
                message_id=message.get("message_id", str(uuid.uuid4())),
                user_id=event.get("sender", {}).get("sender_id", {}).get("user_id", ""),
                chat_id=message.get("chat_id", ""),
                text=cls._extract_text(message),
                timestamp=message.get("create_time", ""),
            )
        elif "action" in event:
            return cls(
                event_type="button_callback",
                message_id=action.get("tag", str(uuid.uuid4())),
                user_id=event.get("operator", {}).get("user_id", ""),
                action_value=action.get("value", {}).get("action", ""),
                trace_id=action.get("value", {}).get("trace_id", ""),
            )
        return cls(event_type="unknown")

    @staticmethod
    def _extract_text(message: dict) -> str:
        """Extract plain text from Feishu message content."""
        content = message.get("content", "{}")
        try:
            parsed = json.loads(content)
            return parsed.get("text", "")
        except (json.JSONDecodeError, TypeError):
            return str(content)


@dataclass
class FeishuCard:
    """Interactive message card for Feishu."""
    title: str = ""
    intent_restatement: str = ""
    risk_notes: str = ""
    route: str = ""
    trace_id: str = ""

    def to_card_json(self) -> dict[str, Any]:
        """Build Feishu interactive card JSON."""
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": self.title},
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": (
                                f"**意图理解**: {self.intent_restatement}\n"
                                f"**路由决策**: {self.route}\n"
                                f"**风险提示**: {self.risk_notes}"
                            ),
                        },
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "✅ 确认执行"},
                                "type": "primary",
                                "value": {"action": "confirm", "trace_id": self.trace_id},
                            },
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "✏️ 修改"},
                                "type": "default",
                                "value": {"action": "modify", "trace_id": self.trace_id},
                            },
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                                "type": "danger",
                                "value": {"action": "reject", "trace_id": self.trace_id},
                            },
                        ],
                    },
                ],
            },
        }


# ── Persistent Dedup Store ────────────────────────────────────────

class DedupStore:
    """SQLite-backed message dedup store. Survives restarts.

    Falls back to in-memory set if db_path is None.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._lock = threading.Lock()
        if db_path:
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS dedup "
                "(platform TEXT, message_id TEXT, ts REAL, "
                "PRIMARY KEY (platform, message_id))"
            )
            self._conn.commit()
            self._memory: set[str] | None = None
        else:
            self._conn = None  # type: ignore
            self._memory = set()

    def seen(self, message_id: str, platform: str = "feishu") -> bool:
        """Check if message was already processed."""
        with self._lock:
            if self._memory is not None:
                return message_id in self._memory
            row = self._conn.execute(
                "SELECT 1 FROM dedup WHERE platform=? AND message_id=?",
                (platform, message_id),
            ).fetchone()
            return row is not None

    def mark(self, message_id: str, platform: str = "feishu") -> None:
        """Mark message as processed."""
        with self._lock:
            self._mark_unlocked(message_id, platform)

    def claim_if_new(self, message_id: str, platform: str = "feishu") -> bool:
        """Atomically claim a message ID if it has not been seen before."""
        with self._lock:
            if self._memory is not None:
                if message_id in self._memory:
                    return False
                self._mark_unlocked(message_id, platform)
                return True

            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO dedup (platform, message_id, ts) VALUES (?, ?, ?)",
                (platform, message_id, time.time()),
            )
            self._conn.commit()
            return int(cursor.rowcount or 0) > 0

    def _mark_unlocked(self, message_id: str, platform: str = "feishu") -> None:
        if self._memory is not None:
            self._memory.add(message_id)
            # ARCH-10 fix: cap in-memory dedup set to prevent OOM
            if len(self._memory) > 10000:
                # Evict ~20% oldest (sets are unordered but this prevents unbounded growth)
                to_remove = list(self._memory)[:2000]
                self._memory -= set(to_remove)
            return
        self._conn.execute(
            "INSERT OR IGNORE INTO dedup (platform, message_id, ts) VALUES (?, ?, ?)",
            (platform, message_id, time.time()),
        )
        self._conn.commit()


# ── Signature Verification ────────────────────────────────────────

def verify_signature(
    payload_bytes: bytes,
    timestamp: str,
    nonce: str,
    signature: str,
    secret: str,
) -> bool:
    """Verify Feishu webhook signature (HMAC-SHA256).
    """
    if not secret:
        logger.error("verify_signature: webhook_secret is empty — refusing unsigned webhook")
        return False

    # Feishu signature: sha256(timestamp + nonce + secret + body)
    content = f"{timestamp}\n{nonce}\n{secret}\n".encode() + payload_bytes
    computed = hashlib.sha256(content).hexdigest()
    return hmac.compare_digest(computed, signature)


def check_timestamp_freshness(timestamp: str, max_age_seconds: int = 300) -> bool:
    """Check that webhook timestamp is within acceptable window."""
    try:
        ts = float(timestamp)
        return abs(time.time() - ts) < max_age_seconds
    except (ValueError, TypeError):
        return False


# ── Handler ───────────────────────────────────────────────────────

class FeishuHandler:
    """Handles Feishu webhook events.

    P0 fixes:
      - Persistent dedup (SQLite-backed, survives restart)
      - Signature verification (HMAC-SHA256)
      - trace_id passed to advisor_fn
      - Card sending via outbox_fn

    Usage::

        handler = FeishuHandler(
            advisor_fn=lambda msg, trace_id: advisor_graph.invoke({
                "user_message": msg, "trace_id": trace_id}),
            send_card_fn=lambda chat_id, card: feishu_api.send(chat_id, card),
        )
        result = handler.handle_webhook(payload)
    """

    def __init__(
        self,
        *,
        advisor_fn: Callable[..., dict] | None = None,
        send_card_fn: Callable[[str, dict], None] | None = None,
        resume_fn: Callable[[str, str], dict] | None = None,
        outbox_fn: Callable[[str, dict], None] | None = None,
        dedup_db_path: str | None = None,
        webhook_secret: str = "",
    ) -> None:
        self._advisor_fn = advisor_fn or (
            lambda msg, trace_id=None: {"selected_route": "hybrid", "route_rationale": "default"}
        )
        self._send_card_fn = send_card_fn or (lambda chat_id, card: None)
        self._resume_fn = resume_fn or (lambda trace_id, action: {})
        self._outbox_fn = outbox_fn  # If set, card sending goes through outbox
        self._dedup = DedupStore(dedup_db_path)
        self._webhook_secret = webhook_secret
        if not webhook_secret:
            logger.warning(
                "FeishuHandler: webhook_secret is empty — incoming webhooks will be rejected. "
                "Set FEISHU_WEBHOOK_SECRET to accept Feishu callbacks."
            )

    def handle_webhook(self, payload: dict[str, Any], *, raw_body: bytes = b"",
                       headers: dict[str, str] | None = None) -> dict[str, Any]:
        """Process a Feishu webhook payload.

        S3-4.4: Now verifies signature and timestamp before processing.
        Returns a result dict with status and any response data.
        """
        # S3-4.4: Verify signature and timestamp before processing, including challenge handshake.
        hdrs = headers or {}
        timestamp = hdrs.get("X-Lark-Request-Timestamp", payload.get("header", {}).get("create_time", ""))
        nonce = hdrs.get("X-Lark-Request-Nonce", "")
        signature = hdrs.get("X-Lark-Signature", "")

        if not verify_signature(raw_body or b"", timestamp, nonce, signature, self._webhook_secret):
            logger.warning("Feishu webhook signature verification failed")
            return {"status": "error", "code": 401, "reason": "signature_verification_failed"}

        if not check_timestamp_freshness(timestamp):
            logger.warning("Feishu webhook timestamp too old: %s", timestamp)
            return {"status": "error", "code": 401, "reason": "timestamp_expired"}

        if "challenge" in payload:
            return {"challenge": payload["challenge"]}

        event = FeishuEvent.from_webhook(payload)

        if event.event_type == "message":
            return self._handle_message(event)
        elif event.event_type == "button_callback":
            return self._handle_callback(event)
        else:
            return {"status": "ignored", "reason": "unknown event type"}

    def _handle_message(self, event: FeishuEvent) -> dict[str, Any]:
        """Handle a new message event (async-first).

        Returns immediately with accepted status. Processing happens
        in a background thread that sends ack + result cards via Feishu API.
        """
        # Persistent dedup
        if not self._dedup.claim_if_new(event.message_id):
            return {"status": "duplicate", "message_id": event.message_id}

        trace_id = str(uuid.uuid4())

        # Launch background processing thread
        thread = threading.Thread(
            target=self._process_message_background,
            args=(event, trace_id),
            name=f"feishu-{trace_id[:8]}",
            daemon=True,
        )
        thread.start()

        # Return immediately — Feishu gets HTTP 200 within milliseconds
        return {
            "status": "accepted",
            "trace_id": trace_id,
            "message_id": event.message_id,
        }

    def _process_message_background(self, event: FeishuEvent, trace_id: str) -> None:
        """Background thread: ack → advisor → result card."""
        start_time = time.time()
        lf_trace = None
        try:
            # Step 1: Send ack card immediately
            ack_card = self._build_ack_card(
                request_text=event.text[:100],
                trace_id=trace_id,
            )
            self._send_card(event.chat_id, ack_card, trace_id)

            lf_trace = _start_background_trace(
                name="feishu_message",
                trace_id=trace_id,
                user_id=event.user_id,
                session_id=event.chat_id,
                tags=["openmind", "feishu", "message"],
                metadata={
                    "message_id": event.message_id,
                    "message_len": len(event.text),
                },
            )

            # Step 2: Run advisor (this is the slow part: 3-30 min)
            result = self._advisor_fn(event.text, trace_id=trace_id)
            elapsed = time.time() - start_time

            status = result.get("status", "completed")
            route = result.get("selected_route", "unknown")
            answer = result.get("answer", result.get("text", ""))
            conv_url = result.get("conversation_url", "")

            # Step 3: Send completion card
            completion_card = self._build_completion_card(
                route=route,
                status=status,
                answer=answer,
                trace_id=trace_id,
                request_text=event.text[:60],
                elapsed_seconds=elapsed,
                conversation_url=conv_url,
            )
            self._send_card(event.chat_id, completion_card, trace_id)
            logger.info(
                "Feishu message processed: trace=%s route=%s elapsed=%.0fs",
                trace_id[:12], route, elapsed,
            )
            _close_background_trace(
                lf_trace,
                metadata={
                    "status": status,
                    "route": route,
                    "elapsed_ms": round(elapsed * 1000),
                    "has_conversation_url": bool(conv_url),
                },
            )

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "Advisor failed for feishu message: trace=%s elapsed=%.0fs error=%s",
                trace_id[:12], elapsed, e, exc_info=True,
            )
            error_card = self._build_error_card(
                error=e,
                trace_id=trace_id,
                request_text=event.text[:60],
            )
            self._send_card(event.chat_id, error_card, trace_id)
            _close_background_trace(
                lf_trace,
                metadata={
                    "status": "error",
                    "elapsed_ms": round(elapsed * 1000),
                    "error": type(e).__name__,
                },
            )

    def _send_card(self, chat_id: str, card_json: dict, trace_id: str) -> None:
        """Send card via outbox or direct, with error handling."""
        try:
            if self._outbox_fn:
                self._outbox_fn("feishu_card", {
                    "chat_id": chat_id,
                    "card": card_json,
                    "trace_id": trace_id,
                })
            else:
                self._send_card_fn(chat_id, card_json)
        except Exception as e:
            logger.warning("Failed to send Feishu card: %s", e)

    def _build_ack_card(
        self, *, request_text: str, trace_id: str,
    ) -> dict:
        """Build an immediate acknowledgement card."""
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📥 收到，正在处理..."},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**需求**: {request_text}"},
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "正在分析意图并路由到最佳模型，预计 3-10 分钟完成。\n完成后会自动推送结果卡片 ✨",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": f"trace: {trace_id[:12]}..."},
                    ],
                },
            ],
        }

    def _build_completion_card(
        self, *, route: str, status: str, answer: str,
        trace_id: str, request_text: str,
        elapsed_seconds: float = 0.0,
        conversation_url: str = "",
    ) -> dict:
        """Build a completion notification card with timing and full-text link."""
        status_emoji = {"completed": "✅", "success": "✅", "error": "❌"}.get(status, "📋")
        route_label = {
            "kb_answer": "知识库回答",
            "quick_answer": "快速回答",
            "deep_research": "深度研究",
            "report": "报告生成",
            "funnel": "任务分析",
            "hybrid": "混合路由",
            "error": "处理失败",
        }.get(route, route)

        # Truncate answer for card display
        is_truncated = len(answer) > 800
        display_answer = answer[:800] + "\n\n...（内容已截断）" if is_truncated else answer
        if not display_answer:
            display_answer = f"已完成 {route_label} 路由处理"

        # Timing display
        timing = ""
        if elapsed_seconds > 0:
            mins = int(elapsed_seconds // 60)
            secs = int(elapsed_seconds % 60)
            timing = f" | 耗时 {mins}分{secs}秒" if mins else f" | 耗时 {secs}秒"

        elements = [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**需求**: {request_text}"},
            },
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**结果**:\n{display_answer}"},
            },
        ]

        # Add "view full text" button if truncated and conversation_url available
        if is_truncated and conversation_url:
            elements.append({
                "tag": "action",
                "actions": [{
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "📄 查看完整回答"},
                    "type": "primary",
                    "url": conversation_url,
                }],
            })

        elements.extend([
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"trace: {trace_id[:12]}... | {route_label}{timing}"},
                ],
            },
        ])

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{status_emoji} 处理完成 — {route_label}"},
                "template": "green" if status in ("completed", "success") else "red",
            },
            "elements": elements,
        }

    def _build_error_card(
        self, *, error: Exception | str, trace_id: str, request_text: str = "",
    ) -> dict:
        """Build a user-friendly error notification card for Feishu."""
        friendly_msg = _friendly_error(error)

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "⚠️ 处理未成功"},
                "template": "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**请求**: {request_text[:100]}"},
                },
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**原因**: {friendly_msg}"},
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "💡 你可以直接重新发送消息来重试",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": f"trace: {trace_id[:12]}..."},
                    ],
                },
            ],
        }

    def _handle_callback(self, event: FeishuEvent) -> dict[str, Any]:
        """Handle a button callback event (async-first).

        For 'confirm' action, processes in background thread since resume_fn
        may take time. Other actions return immediately.
        """
        action = event.action_value
        trace_id = event.trace_id

        if action == "confirm":
            # Resume may be slow — process in background
            thread = threading.Thread(
                target=self._process_callback_background,
                args=(event,),
                name=f"feishu-cb-{trace_id[:8]}",
                daemon=True,
            )
            thread.start()
            return {"status": "accepted", "trace_id": trace_id, "action": "confirm"}
        elif action == "modify":
            return {"status": "awaiting_modification", "trace_id": trace_id}
        elif action == "reject":
            return {"status": "rejected", "trace_id": trace_id}
        else:
            return {"status": "unknown_action", "action": action}

    def _process_callback_background(self, event: FeishuEvent) -> None:
        """Background thread for button callback processing."""
        trace_id = event.trace_id
        lf_trace = _start_background_trace(
            name="feishu_callback",
            trace_id=trace_id,
            user_id=event.user_id,
            session_id=trace_id,
            tags=["openmind", "feishu", "callback"],
            metadata={"action": event.action_value},
        )
        try:
            result = self._resume_fn(trace_id, event.action_value)
            logger.info("Callback processed: trace=%s action=%s", trace_id[:12], event.action_value)
            _close_background_trace(
                lf_trace,
                metadata={"status": result.get("status", "completed"), "action": event.action_value},
            )
        except Exception as e:
            logger.error(
                "Resume callback failed: trace=%s error=%s",
                trace_id[:12], e, exc_info=True,
            )
            _close_background_trace(
                lf_trace,
                metadata={"status": "error", "action": event.action_value, "error": type(e).__name__},
            )
