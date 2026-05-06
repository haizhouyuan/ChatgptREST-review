"""Feishu WebSocket Gateway — receives events via long connection.

Mirrors Openclaw's approach: uses Feishu SDK's WebSocket client for
event subscription (no public URL needed). Processes messages through
the FeishuHandler and replies using the SDK's API client.

Usage:
    # Standalone (for testing):
    python -m chatgptrest.advisor.feishu_ws_gateway

    # As systemd service:
    systemctl --user start chatgptrest-feishu-ws.service

Environment variables:
    FEISHU_APP_ID      — App ID from Feishu developer console
    FEISHU_APP_SECRET  — App Secret from Feishu developer console
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import signal
import sys
import threading

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
)

from chatgptrest.advisor.feishu_handler import DedupStore
from chatgptrest.advisor.task_intake import build_task_intake_spec

logger = logging.getLogger(__name__)


def _resolve_advisor_api_url() -> str:
    """Resolve the Advisor API URL used by the Feishu WS gateway.

    The integrated host currently serves `/v2/advisor/*` from the main
    ChatgptREST API on 18711. Operators can still override this explicitly
    via `ADVISOR_API_URL` if they run a separate ingress.
    """
    return os.environ.get(
        "ADVISOR_API_URL", "http://127.0.0.1:18711/v2/advisor/advise"
    ).strip()


def _advisor_api_headers() -> dict[str, str]:
    """Build HTTP headers for Advisor API calls from the WS gateway."""
    headers = {"Content-Type": "application/json; charset=utf-8"}
    api_key = (
        os.environ.get("ADVISOR_API_KEY", "").strip()
        or os.environ.get("OPENMIND_API_KEY", "").strip()
    )
    if api_key:
        headers["X-Api-Key"] = api_key
    return headers


def _build_advisor_api_payload(
    *, chat_id: str, message_id: str, text: str, user_id: str
) -> dict[str, object]:
    trace_id = f"feishu-ws:{message_id}" if message_id else f"feishu-ws:{chat_id}"
    context = {
        "channel": "feishu_ws",
        "chat_id": chat_id,
        "message_id": message_id,
    }
    payload = {
        "message": text,
        "source": "feishu",
        "user_id": user_id or f"feishu:{chat_id}",
        "session_id": f"feishu:{chat_id}",
        "account_id": user_id,
        "thread_id": message_id,
        "agent_id": "feishu_ws_gateway",
        "trace_id": trace_id,
        "context": context,
    }
    payload["task_intake"] = build_task_intake_spec(
        ingress_lane="advisor_advise_v2",
        default_source="feishu",
        raw_source="feishu",
        message=text,
        trace_id=trace_id,
        session_id=str(payload["session_id"]),
        user_id=str(payload["user_id"]),
        account_id=str(payload["account_id"]),
        thread_id=str(payload["thread_id"]),
        agent_id=str(payload["agent_id"]),
        context=context,
        attachments=[],
        client_name="feishu-ws-gateway",
    ).to_dict()
    return payload


class _ActivityAwareWSClient(lark.ws.Client):
    """Feishu SDK client that reports connection/control/data activity.

    The upstream SDK keeps the long connection alive with ping/pong frames even
    when no human message arrives. Our watchdog must treat that traffic as
    liveness; otherwise an idle-but-healthy socket gets disconnected every few
    minutes.
    """

    def __init__(self, *args, activity_callback=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._activity_callback = activity_callback

    def _mark_activity(self) -> None:
        callback = self._activity_callback
        if callback is None:
            return
        try:
            callback()
        except Exception:
            logger.debug("WS activity callback failed", exc_info=True)

    async def _connect(self) -> None:
        await super()._connect()
        if getattr(self, "_conn", None) is not None:
            self._mark_activity()

    async def _handle_control_frame(self, frame) -> None:
        self._mark_activity()
        await super()._handle_control_frame(frame)

    async def _handle_data_frame(self, frame) -> None:
        self._mark_activity()
        await super()._handle_data_frame(frame)


class FeishuWSGateway:
    """WebSocket-based Feishu bot gateway.

    Connects to Feishu via persistent WebSocket connection (long connection),
    receives events, processes messages, and sends replies — exactly like
    Openclaw's Feishu extension.
    """

    def __init__(
        self,
        app_id: str = "",
        app_secret: str = "",
        log_level: int = lark.LogLevel.INFO,
    ) -> None:
        self._app_id = app_id or os.environ.get("FEISHU_APP_ID", "")
        self._app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET", "")

        if not self._app_id or not self._app_secret:
            raise ValueError(
                "FEISHU_APP_ID and FEISHU_APP_SECRET must be set"
            )

        # Lark SDK client for sending messages
        self._client = lark.Client.builder() \
            .app_id(self._app_id) \
            .app_secret(self._app_secret) \
            .log_level(log_level) \
            .build()
        dedup_db_path = os.environ.get("FEISHU_WS_DEDUP_DB", "").strip() or None
        self._dedup = DedupStore(dedup_db_path)

        # Event dispatcher
        self._event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(self._on_message) \
            .build()

        # WebSocket client
        self._ws_client = self._build_ws_client(log_level=log_level)

        self._running = False
        logger.info(
            "FeishuWSGateway initialized (app_id=%s...)",
            self._app_id[:8],
        )

    def _claim_message_id(self, message_id: str) -> bool:
        if not str(message_id or "").strip():
            return True
        return bool(self._dedup.claim_if_new(str(message_id), platform="feishu_ws"))

    def _build_ws_client(
        self, *, log_level: int = lark.LogLevel.INFO
    ) -> _ActivityAwareWSClient:
        """Build a WS client that surfaces control/data activity to the watchdog."""
        return _ActivityAwareWSClient(
            self._app_id,
            self._app_secret,
            event_handler=self._event_handler,
            log_level=log_level,
            activity_callback=self._touch_heartbeat,
        )

    # ── L2: Systemd Watchdog ─────────────────────────────────────

    def _sd_notify(self, state: str) -> None:
        """Send sd_notify if running under systemd watchdog."""
        try:
            import socket
            addr = os.environ.get("NOTIFY_SOCKET")
            if not addr:
                return
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            if addr[0] == "@":
                addr = "\0" + addr[1:]
            sock.connect(addr)
            sock.sendall(state.encode())
            sock.close()
        except Exception:
            pass

    # ── L3: Health Status File ──────────────────────────────────

    _STATUS_PATH = "/tmp/feishu_ws_gateway_status.json"

    def _write_status_file(self, connected: bool = True) -> None:
        """Write health status file for external probes (maint_daemon)."""
        import time as _time
        try:
            status = {
                "ts": _time.time(),
                "connected": connected,
                "pid": os.getpid(),
                "uptime_s": _time.time() - getattr(self, "_start_ts", _time.time()),
            }
            with open(self._STATUS_PATH, "w") as f:
                json.dump(status, f)
        except Exception:
            pass

    # ── Safe Disconnect ────────────────────────────────────────

    def _safe_disconnect(self, client: object | None = None) -> None:
        """Safely disconnect a Feishu WS client, handling async coroutines.

        The SDK's ``Client._disconnect()`` may be an async coroutine.
        Calling it without ``await`` silently fails (RuntimeWarning:
        coroutine never awaited), leaving the connection stale and
        eventually crashing the service via systemd watchdog.
        """
        target = client or self._ws_client
        disconnect_fn = getattr(target, "_disconnect", None)
        if disconnect_fn is None:
            return
        try:
            if inspect.iscoroutinefunction(disconnect_fn):
                # Running from a non-async thread → use asyncio.run()
                asyncio.run(disconnect_fn())
            else:
                result = disconnect_fn()
                # Handle case where it returns a coroutine despite not being
                # declared as async (e.g. dynamic dispatch).
                if inspect.iscoroutine(result):
                    asyncio.run(result)
        except RuntimeError:
            # "cannot be called from a running event loop" — try a new thread.
            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(asyncio.run, disconnect_fn()).result(timeout=10)
            except Exception as e2:
                logger.debug("Fallback disconnect also failed: %s", e2)
        except Exception as e:
            logger.debug("_safe_disconnect error: %s", e)

    # ── Event Handling ──────────────────────────────────────────

    def _on_message(self, data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        """Handle incoming message event from Feishu WebSocket."""
        self._touch_heartbeat()  # Keep watchdog happy
        try:
            event = data.event
            if not event or not event.message:
                logger.warning("Empty message event received")
                return

            msg = event.message
            sender = event.sender
            message_id = msg.message_id or ""
            chat_id = msg.chat_id or ""
            msg_type = msg.message_type or "text"

            # Extract text content
            text = ""
            if msg.content:
                try:
                    content = json.loads(msg.content)
                    text = content.get("text", "")
                except (json.JSONDecodeError, TypeError):
                    text = msg.content

            user_id = ""
            if sender and sender.sender_id:
                user_id = sender.sender_id.user_id or sender.sender_id.open_id or ""

            logger.info(
                "Feishu message received: msg_id=%s chat_id=%s user=%s text=%s",
                message_id[:12], chat_id[:12], user_id[:12],
                text[:50] + "..." if len(text) > 50 else text,
            )

            # Only handle text messages for now
            if msg_type != "text" or not text.strip():
                logger.info("Skipping non-text or empty message (type=%s)", msg_type)
                return
            if not self._claim_message_id(message_id):
                logger.info("Skipping duplicate Feishu WS message (msg_id=%s)", message_id[:12])
                return

            # Process in a separate thread to not block the WebSocket
            threading.Thread(
                target=self._process_and_reply,
                args=(chat_id, message_id, text, user_id),
                daemon=True,
                name=f"feishu-reply-{message_id[:8]}",
            ).start()

        except Exception as e:
            logger.error("Error handling Feishu message event: %s", e, exc_info=True)

    def _process_and_reply(
        self, chat_id: str, message_id: str, text: str, user_id: str
    ) -> None:
        """Process message through Advisor API and send reply (runs in thread).

        Flow:
            1. Send immediate "⏳ 处理中" ack to Feishu
            2. Call the Advisor API server via HTTP
            3. Send the result back to Feishu
        """
        import time
        import urllib.error
        import urllib.request

        api_url = _resolve_advisor_api_url()

        try:
            # Step 1: Send immediate acknowledgment
            self._send_reply(chat_id, f"⏳ 收到，正在处理...\n\n> {text[:100]}")
            logger.info("Ack sent for msg_id=%s", message_id[:12])

            # Step 2: Call the Advisor API
            t0 = time.time()
            request_payload = _build_advisor_api_payload(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                user_id=user_id,
            )
            trace_id = str(request_payload["trace_id"])
            payload = json.dumps(request_payload).encode("utf-8")

            req = urllib.request.Request(
                api_url,
                data=payload,
                headers=_advisor_api_headers(),
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=1800) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8")[:300]
                except Exception:
                    pass
                raise RuntimeError(f"Advisor API {e.code}: {body}")

            elapsed = time.time() - t0
            logger.info(
                "Advisor response for msg_id=%s took %.1fs route=%s trace=%s",
                message_id[:12], elapsed, result.get("selected_route", "?"), result.get("trace_id", trace_id),
            )

            # Step 3: Format and send result
            answer = self._format_advisor_result(result, elapsed)
            self._send_reply(chat_id, answer)

            logger.info(
                "Result sent for msg_id=%s to chat_id=%s",
                message_id[:12], chat_id[:12],
            )

        except Exception as e:
            logger.error(
                "Failed to process msg_id=%s: %s",
                message_id[:12], e, exc_info=True,
            )
            try:
                # Use friendly error message instead of raw exception
                from chatgptrest.advisor.feishu_handler import _friendly_error
                friendly_msg = _friendly_error(e)
                self._send_reply(
                    chat_id,
                    f"⚠️ {friendly_msg}\n\n💡 你可以直接重新发送消息来重试。",
                )
            except Exception:
                pass

    def _format_advisor_result(self, result: dict, elapsed: float) -> str:
        """Format the advisor result for display in Feishu."""
        status = result.get("status", "completed")
        route = result.get("selected_route", "unknown")
        intent = result.get("intent_top", "")
        kb_hit = result.get("kb_has_answer", False)
        trace_id = str(result.get("trace_id", "")).strip()
        if not trace_id:
            request_metadata = result.get("request_metadata", {})
            if isinstance(request_metadata, dict):
                trace_id = str(request_metadata.get("trace_id", "")).strip()
        degradation = result.get("degradation", [])

        # Extract answer: check top-level first, then dig into route_result
        answer = result.get("answer", "") or result.get("text", "")
        if not answer:
            rr = result.get("route_result", {})
            answer = (
                rr.get("answer", "")
                or rr.get("final_text", "")
                or rr.get("text", "")
                or ""
            )
            # For funnel route, synthesize from project card
            if not answer and rr.get("stage") == "funnel_complete":
                pc = rr.get("project_card", {})
                if pc:
                    answer = (
                        f"**项目分析完成**\n\n"
                        f"问题: {rr.get('problem_statement', '')}\n\n"
                        f"推荐方案: {rr.get('recommended_option', '')}\n\n"
                        f"任务数: {len(rr.get('tasks', []))}"
                    )

        status_emoji = {"completed": "✅", "success": "✅", "error": "❌"}.get(status, "📋")

        route_label = {
            "kb_answer": "知识库回答",
            "quick_answer": "快速回答",
            "deep_research": "深度研究",
            "report": "报告生成",
            "funnel": "任务分析",
            "hybrid": "混合路由",
        }.get(route, route)

        parts = [f"{status_emoji} **{route_label}**"]
        if intent:
            parts.append(f"意图: {intent}")

        if answer:
            # Truncate very long answers for Feishu readability
            if len(answer) > 2000:
                answer = answer[:2000] + "\n\n... (回复过长，已截断)"
            parts.append(f"\n{answer}")
        else:
            parts.append("处理完成，但无文本回复。")

        if isinstance(degradation, list) and degradation:
            degraded_components = []
            for item in degradation:
                if isinstance(item, dict):
                    component = str(item.get("component", "")).strip()
                    reason = str(item.get("reason", "")).strip()
                    degraded_components.append(f"{component}:{reason}" if reason else component)
            if degraded_components:
                parts.append(f"\n⚠️ 降级: {', '.join(filter(None, degraded_components[:3]))}")

        footer = f"\n⏱ {elapsed:.1f}s | 路由: {route}" + (f" | KB命中" if kb_hit else "")
        if trace_id:
            footer += f" | trace: {trace_id[:18]}"
        parts.append(footer)

        return "\n".join(parts)

    def _send_reply(self, chat_id: str, text: str) -> None:
        """Send a text reply to a Feishu chat using the SDK client."""
        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}, ensure_ascii=False))
                .build()
            ) \
            .build()

        response = self._client.im.v1.message.create(request)

        if not response.success():
            logger.error(
                "Failed to send reply to %s: code=%s msg=%s",
                chat_id[:12], response.code, response.msg,
            )
            raise RuntimeError(f"Feishu send failed: {response.code} {response.msg}")

        logger.info("Reply sent to %s (msg_id=%s)",
                     chat_id[:12],
                     response.data.message_id if response.data else "?")

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Start the WebSocket gateway with auto-reconnect.

        If the connection drops or becomes stale, the watchdog thread
        will detect it and trigger a reconnect by disconnecting the
        old client (which unblocks start()), then the main loop
        recreates and restarts.
        """
        import time as _time

        self._running = True
        self._last_event_ts = _time.time()
        self._start_ts = _time.time()
        self._needs_reconnect = False

        # Notify systemd we are ready
        self._sd_notify("READY=1")

        # Start watchdog thread
        watchdog = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="feishu-ws-watchdog",
        )
        watchdog.start()

        # Main loop with auto-reconnect
        while self._running:
            try:
                logger.info("Starting Feishu WebSocket client...")
                self._ws_client.start()
            except Exception as e:
                if not self._running:
                    break
                logger.warning(
                    "WebSocket client exited (reconnecting in 5s): %s", e
                )
            except SystemExit:
                # lark SDK sometimes calls sys.exit on disconnect
                if not self._running:
                    break
                logger.warning("WebSocket client sys.exit, reconnecting...")

            if not self._running:
                break

            _time.sleep(5)
            # Recreate for a clean connection
            self._recreate_ws_client()
            self._last_event_ts = _time.time()  # reset heartbeat

    def stop(self) -> None:
        """Stop the WebSocket gateway."""
        logger.info("Stopping Feishu WebSocket gateway...")
        self._running = False
        # Shut down the reply thread pool to ensure clean resource cleanup.
        try:
            self._reply_pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        # Try to disconnect current client to unblock start()
        self._safe_disconnect()

    def _watchdog_loop(self) -> None:
        """Background watchdog: detect stale connections and force reconnect.

        If no events are received for STALE_THRESHOLD_SEC, the watchdog
        considers the connection dead and forces a disconnect on the
        current client, which causes start() to raise/return and trigger
        the auto-reconnect in the main loop.
        """
        import time as _time

        STALE_THRESHOLD_SEC = 300  # 5 minutes
        CHECK_INTERVAL_SEC = 60   # check every minute

        while self._running:
            _time.sleep(CHECK_INTERVAL_SEC)
            if not self._running:
                break

            elapsed = _time.time() - self._last_event_ts
            if elapsed > STALE_THRESHOLD_SEC:
                logger.warning(
                    "WebSocket stale for %.0fs (>%ds), forcing disconnect...",
                    elapsed, STALE_THRESHOLD_SEC,
                )
                # Disconnect the CURRENT client to unblock start()
                # The main loop will then recreate and restart
                self._safe_disconnect()
                # Also feed systemd watchdog during reconnect attempt
                self._sd_notify("WATCHDOG=1")
                self._write_status_file(connected=False)
            else:
                logger.debug("Watchdog: last event %.0fs ago, healthy", elapsed)
                # L2: feed systemd watchdog when healthy
                self._sd_notify("WATCHDOG=1")
                # L3: update status file
                self._write_status_file(connected=True)

    def _recreate_ws_client(self) -> None:
        """Recreate the WebSocket client for a fresh connection."""
        # Disconnect old client first (if still alive)
        old_client = self._ws_client
        self._safe_disconnect(old_client)

        try:
            self._ws_client = self._build_ws_client(log_level=lark.LogLevel.INFO)
            logger.info("WebSocket client recreated")
        except Exception as e:
            logger.error("Failed to recreate WebSocket client: %s", e)

    def _touch_heartbeat(self) -> None:
        """Update last event timestamp (called on each message)."""
        import time as _time
        self._last_event_ts = _time.time()
        # L2: feed systemd watchdog on every message
        self._sd_notify("WATCHDOG=1")
        # L3: update status file
        self._write_status_file(connected=True)


def main():
    """Entry point for standalone execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")

    if not app_id or not app_secret:
        print("ERROR: FEISHU_APP_ID and FEISHU_APP_SECRET must be set", file=sys.stderr)
        sys.exit(1)

    gateway = FeishuWSGateway(app_id=app_id, app_secret=app_secret)

    # Graceful shutdown
    def handle_signal(signum, frame):
        logger.info("Signal %s received, shutting down...", signum)
        gateway.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    gateway.start()


if __name__ == "__main__":
    main()
