"""Simple Routes — quick_ask and deep_research handlers.

Quick Ask: KB-only answer, no LLM call, <10s response time.
Deep Research: forwards to ChatgptREST deep_research mode with KB context.

Both routes write results back to KB (quarantine weight 0.3).
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class SimpleRouteResult:
    """Result from a simple route execution."""
    trace_id: str = ""
    route: str = ""            # "quick_ask" | "deep_research"
    answer: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    status: str = "success"    # "success" | "error" | "no_answer"
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "route": self.route,
            "answer": self.answer,
            "evidence_refs": self.evidence_refs,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "error": self.error,
        }


# ── KB search type ────────────────────────────────────────────────

KBSearchFn = Callable[[str, int], list[dict[str, Any]]]
LLMFn = Callable[[str, str], str]
KBWritebackFn = Callable[[str, str, float], None]


def _default_kb_search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Default no-op KB search for testing."""
    return []


def _default_llm(prompt: str, system_msg: str = "") -> str:
    return f"[mock deep research: {prompt[:50]}...]"


def _default_writeback(doc_id: str, text: str, weight: float) -> None:
    pass


# ── Quick Ask ─────────────────────────────────────────────────────

def quick_ask(
    query: str,
    *,
    trace_id: str = "",
    kb_search_fn: KBSearchFn = _default_kb_search,
    writeback_fn: KBWritebackFn = _default_writeback,
    top_k: int = 5,
) -> SimpleRouteResult:
    """Answer directly from KB without LLM call.

    Returns top-K KB hits as the answer. Target: <10s.
    """
    start = time.perf_counter()
    trace_id = trace_id or str(uuid.uuid4())

    try:
        hits = kb_search_fn(query, top_k)
        elapsed = (time.perf_counter() - start) * 1000

        if not hits:
            return SimpleRouteResult(
                trace_id=trace_id,
                route="quick_ask",
                status="no_answer",
                latency_ms=elapsed,
            )

        # Build answer from top hits
        evidence_refs = [h.get("artifact_id", h.get("id", "")) for h in hits]
        answer_parts = []
        for h in hits[:3]:  # Top 3 for answer
            title = h.get("title", "")
            snippet = h.get("snippet", h.get("text", ""))[:200]
            if title:
                answer_parts.append(f"**{title}**: {snippet}")
            else:
                answer_parts.append(snippet)

        answer = "\n\n".join(answer_parts)

        # Writeback to KB with quarantine weight
        try:
            writeback_fn(f"qa_{trace_id}", answer, 0.3)
        except Exception as e:
            logger.warning("KB writeback failed: %s", e)

        return SimpleRouteResult(
            trace_id=trace_id,
            route="quick_ask",
            answer=answer,
            evidence_refs=evidence_refs,
            latency_ms=elapsed,
            status="success",
        )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return SimpleRouteResult(
            trace_id=trace_id,
            route="quick_ask",
            status="error",
            error=str(e),
            latency_ms=elapsed,
        )


# ── Deep Research ─────────────────────────────────────────────────

def deep_research(
    query: str,
    *,
    trace_id: str = "",
    kb_search_fn: KBSearchFn = _default_kb_search,
    llm_fn: LLMFn = _default_llm,
    writeback_fn: KBWritebackFn = _default_writeback,
    top_k: int = 10,
    kb_context: str = "",
) -> SimpleRouteResult:
    """Deep research: KB context + LLM deep research mode.

    1. Gather KB context (top-K hits or pre-built)
    2. Send query + context to ChatgptREST deep_research
    3. Write result back to KB (quarantine weight 0.3)
    """
    start = time.perf_counter()
    trace_id = trace_id or str(uuid.uuid4())

    try:
        # Gather KB context (use pre-built if available)
        evidence_refs = []
        if not kb_context:
            hits = kb_search_fn(query, top_k)
            context_parts = []
            for h in hits:
                evidence_refs.append(h.get("artifact_id", h.get("id", "")))
                snippet = h.get("snippet", h.get("text", ""))[:300]
                context_parts.append(snippet)
            kb_context = "\n---\n".join(context_parts) if context_parts else ""

        context_label = kb_context if kb_context else "无相关KB文档"

        # Send to deep research
        prompt = (
            f"用户问题: {query}\n\n"
            f"相关KB上下文:\n{context_label}\n\n"
            "请进行深度分析研究，给出详细回答。"
        )
        answer = llm_fn(prompt, "你是一个深度研究助手")

        elapsed = (time.perf_counter() - start) * 1000

        # Writeback to KB
        try:
            writeback_fn(f"dr_{trace_id}", answer, 0.3)
        except Exception as e:
            logger.warning("KB writeback failed: %s", e)

        return SimpleRouteResult(
            trace_id=trace_id,
            route="deep_research",
            answer=answer,
            evidence_refs=evidence_refs,
            latency_ms=elapsed,
            status="success",
        )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return SimpleRouteResult(
            trace_id=trace_id,
            route="deep_research",
            status="error",
            error=str(e),
            latency_ms=elapsed,
        )
