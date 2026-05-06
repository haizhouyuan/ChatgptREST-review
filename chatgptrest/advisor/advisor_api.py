"""Advisor API — FastAPI endpoint for the Advisor Graph.

Endpoints:
  POST /v2/advisor/advise — async start advisor graph
  GET  /v2/advisor/trace/{trace_id} — query status/result
  POST /v2/advisor/webhook/feishu — receive Feishu webhooks

All graph execution is synchronous in v1 (async in v2).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


# ── Trace Store ───────────────────────────────────────────────────

class TraceStore:
    """In-memory trace store for advisor results.

    In production, this would be backed by SQLite or the EventBus.
    S1-2.2: Capped at MAX_TRACES to prevent OOM on long-running instances.
    """

    MAX_TRACES = 5000

    def __init__(self) -> None:
        self._traces: dict[str, dict[str, Any]] = {}

    def put(self, trace_id: str, data: dict[str, Any]) -> None:
        self._traces[trace_id] = data
        # Evict oldest when over limit
        if len(self._traces) > self.MAX_TRACES:
            oldest_key = next(iter(self._traces))
            del self._traces[oldest_key]

    def get(self, trace_id: str) -> dict[str, Any] | None:
        return self._traces.get(trace_id)

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        items = list(self._traces.values())
        return items[-limit:]


# ── API Handlers (framework-agnostic) ─────────────────────────────

class AdvisorAPI:
    """Advisor Graph API handlers.

    Framework-agnostic: can be mounted on FastAPI, Flask, or used
    directly in tests.

    Usage::

        api = AdvisorAPI(
            advisor_fn=lambda msg: advisor_graph.invoke({"user_message": msg}),
        )
        result = api.advise("帮我写个报告")
        trace = api.get_trace(result["trace_id"])
    """

    def __init__(
        self,
        *,
        advisor_fn: Any = None,
        feishu_handler: Any = None,
        trace_store: TraceStore | None = None,
    ) -> None:
        from chatgptrest.advisor.graph import build_advisor_graph
        self._advisor_fn = advisor_fn
        if self._advisor_fn is None:
            graph = build_advisor_graph()
            compiled = graph.compile()
            self._advisor_fn = compiled.invoke

        self._feishu = feishu_handler
        self._traces = trace_store or TraceStore()

    def advise(self, message: str, **kwargs: Any) -> dict[str, Any]:
        """Start advisor graph for a message.

        Returns: {trace_id, status, route, rationale}
        """
        trace_id = kwargs.get("trace_id", str(uuid.uuid4()))
        normalized_trace_id = trace_id.replace("-", "").lower()
        if len(normalized_trace_id) != 32 or any(ch not in "0123456789abcdef" for ch in normalized_trace_id):
            normalized_trace_id = ""

        lf_trace = None
        try:
            from chatgptrest.observability import start_request_trace

            lf_trace = start_request_trace(
                name="advisor_api",
                user_id=str(kwargs.get("user_id") or "api"),
                session_id=str(kwargs.get("session_id") or trace_id),
                trace_id=normalized_trace_id,
                tags=["openmind", "advisor_api"],
                metadata={"message_len": len(message)},
            )
        except Exception:
            pass

        try:
            result = self._advisor_fn({
                "user_message": message,
                "trace_id": trace_id,
                **kwargs,
            })
        except Exception as exc:
            if lf_trace:
                try:
                    lf_trace.update(metadata={"status": "error", "error": type(exc).__name__})
                    lf_trace.end()
                except Exception:
                    pass
            raise

        # Extract answer text from nested route_result for easy access
        route_result = result.get("route_result", {})
        answer = (
            route_result.get("answer", "")
            or route_result.get("final_text", "")
            or route_result.get("text", "")
            or ""
        )
        # For funnel route, synthesize answer from project card
        if not answer and route_result.get("stage") == "funnel_complete":
            pc = route_result.get("project_card", {})
            if pc:
                answer = (
                    f"**项目分析完成**\n\n"
                    f"问题: {route_result.get('problem_statement', '')}\n\n"
                    f"推荐方案: {route_result.get('recommended_option', '')}\n\n"
                    f"任务数: {len(route_result.get('tasks', []))}"
                )

        # Extract conversation_url if available (for full-text links)
        conversation_url = result.get("conversation_url", "")

        trace_data = {
            "trace_id": trace_id,
            "status": "completed",
            "user_message": message,
            "selected_route": result.get("selected_route", ""),
            "route_rationale": result.get("route_rationale", ""),
            "route_scores": result.get("route_scores", {}),
            "intent_top": result.get("intent_top", ""),
            "route_result": route_result,
            "route_status": result.get("route_status", ""),
            "kb_has_answer": result.get("kb_has_answer", False),
            "kb_top_chunks": result.get("kb_top_chunks", []),
            "kb_answerability": result.get("kb_answerability", 0.0),
            # Top-level answer for easy consumption by Feishu handlers
            "answer": answer,
            "conversation_url": conversation_url,
        }

        if lf_trace:
            try:
                lf_trace.update(
                    metadata={
                        "status": "completed",
                        "route": trace_data["selected_route"],
                        "intent": trace_data["intent_top"],
                    }
                )
                lf_trace.end()
            except Exception:
                pass

        self._traces.put(trace_id, trace_data)
        return trace_data

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """Get trace status and result."""
        return self._traces.get(trace_id)

    def list_traces(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent traces."""
        return self._traces.list_recent(limit)

    def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle Feishu webhook."""
        if self._feishu:
            return self._feishu.handle_webhook(payload)
        return {"status": "feishu_handler_not_configured"}
