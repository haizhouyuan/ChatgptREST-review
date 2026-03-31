"""Advisor LangGraph — StateGraph that wraps the existing routing engine.

Nodes: normalize → kb_probe → analyze_intent → route_decision → [branch]

The graph reuses the existing `advisor.route_request()` logic, wrapping
each step as a LangGraph node for:
  - Checkpoint persistence (SqliteSaver)
  - Human-in-the-loop gates (interrupt_before)
  - Graph-level observability (trace, replay)

Design decisions:
  - State is lean (TypedDict, no large text in checkpoint)
  - Nodes are pure functions of state → state update
  - No LLM calls in this file — intent is rules-based or injected
  - SqliteSaver for local dev; can swap to PostgresSaver for prod
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
import pathlib
import re
import uuid
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from chatgptrest.contracts.schemas import (
    IntentSignals,
    KBProbeResult,
    Route,
    RouteScores,
)
from chatgptrest.workspace.outbox_handlers import execute_workspace_effects_for_trace

logger = logging.getLogger(__name__)


def _kb_direct_synthesis_enabled() -> bool:
    raw = os.environ.get("OPENMIND_KB_DIRECT_SYNTHESIS")
    if raw is None:
        return False
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


_CJK_BLOCK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_ASCII_TOKEN_RE = re.compile(r"[a-z0-9_]{3,}", re.I)


_REGISTRY_FIELDS = (
    "llm_connector",
    "evomap_observer",
    "kb_registry",
    "kb_hub",
    "memory",
    "event_bus",
    "model_router",
    "mcp_bridge",
    "cc_executor",
    "policy_engine",
    "routing_fabric",
    "evomap_knowledge_db",
    "writeback_service",
)
_runtime_override: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "advisor_runtime_override",
    default=None,
)


# ── Service Registry (P1-1: holds live objects outside serializable state) ───

class _ServiceRegistry:
    """Module-level singleton holding live service references.

    These objects (LLMConnector, KBHub, etc.) can't be serialized by
    SqliteSaver, so we keep them here — outside the LangGraph state.
    Graph nodes access services via ``_svc()`` instead of ``state.get('_xxx')``.
    """

    def __init__(self) -> None:
        import threading
        self._lock = threading.Lock()
        self.clear()

    def configure(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def clear(self) -> None:
        with self._lock:
            for name in _REGISTRY_FIELDS:
                setattr(self, name, None)


_registry = _ServiceRegistry()


def configure_services(**kwargs: Any) -> None:
    """Called by routes_advisor_v3 to inject live service objects."""
    _registry.configure(**kwargs)


def reset_services() -> None:
    """Clear the legacy registry so stale live objects do not leak across resets."""
    _registry.clear()


@contextlib.contextmanager
def bind_runtime_services(runtime: Any):
    """Bind runtime services for the current invocation without serializing them into graph state."""
    token = _runtime_override.set(runtime)
    try:
        yield runtime
    finally:
        _runtime_override.reset(token)


def _svc(state: AdvisorState | dict[str, Any] | None = None) -> Any:
    """Prefer explicit runtime binding, fallback to the legacy module registry."""
    if isinstance(state, dict):
        runtime = state.get("_runtime")
        if runtime is not None:
            return runtime
    runtime = _runtime_override.get()
    if runtime is not None:
        return runtime
    return _registry


def _get_llm_fn(task_type: str = "default", *, state: AdvisorState | None = None):
    """Get the best llm_fn for a task — delegates to RoutingFabric.

    If RoutingFabric is available (Phase 3+), uses it for unified
    model selection with automatic fallback chain and health tracking.
    **Always falls back to API LLM connector if RoutingFabric returns empty.**

    Returns:
        Callable (prompt, system_msg) -> str
    """
    svc = _svc(state)
    api_llm = svc.llm_connector  # Always available as final fallback

    # Phase 3: Use RoutingFabric with API fallback
    if svc.routing_fabric:
        fabric_fn = svc.routing_fabric.get_llm_fn(task_type=task_type)

        def _with_api_fallback(prompt: str, system_msg: str = "") -> str:
            """Try RoutingFabric first, fall back to API models."""
            result = ""
            try:
                result = fabric_fn(prompt, system_msg)
            except Exception as e:
                logger.warning(
                    "RoutingFabric error for %s: %s, falling back to API",
                    task_type, e,
                )
            # F-01: Accept any non-empty stripped result (short answers like 'Yes' are valid)
            if result and result.strip():
                return result
            # Fabric failed or returned empty → fall back to API models
            if api_llm is not None:
                logger.info(
                    "RoutingFabric empty for %s, falling back to API connector",
                    task_type,
                )
                try:
                    return api_llm(prompt, system_msg)
                except Exception as e:
                    logger.warning("API fallback also failed for %s: %s", task_type, e)
            return ""

        return _with_api_fallback

    return api_llm


# ── State ─────────────────────────────────────────────────────────

class AdvisorState(TypedDict, total=False):
    """LangGraph state for the Advisor graph.

    Kept lean: only IDs, scores, and signals. No large text blobs.
    The original user_message is the only text field.
    """
    # Input
    user_message: str
    session_id: str
    account_id: str
    thread_id: str
    agent_id: str
    role_id: str
    trace_id: str
    urgency_hint: str

    # After normalize
    normalized_message: str

    # After kb_probe
    kb_has_answer: bool
    kb_top_chunks: list[dict[str, Any]]
    kb_answerability: float

    # After analyze_intent
    intent_top: str
    intent_confidence: float
    multi_intent: bool
    step_count_est: int
    constraint_count: int
    open_endedness: float
    verification_need: bool
    action_required: bool

    # After route_decision
    route_scores: dict[str, float]
    selected_route: str
    route_rationale: str

    # After route execution
    route_result: dict[str, Any]
    route_status: str

    # P1-1: Service references removed from state (now in _ServiceRegistry).
    # Legacy compat: nodes that still do state.get('_xxx') will get None
    # and fall back to the registry via _svc().


# ── Helpers ───────────────────────────────────────────────────────

def _emit_event(state: AdvisorState, event_type: str, source: str, data: dict | None = None):
    """Emit a TraceEvent to the EventBus. Fail-open: never raises."""
    bus = _svc(state).event_bus
    if not bus:
        return
    try:
        from chatgptrest.kernel.event_bus import TraceEvent
        bus.emit(TraceEvent.create(
            source=source,
            event_type=event_type,
            trace_id=state.get("trace_id", ""),
            data=data or {},
        ))
    except Exception as e:
        logger.warning("EventBus emit failed (non-fatal): %s", e)


def _policy_check(state: AdvisorState, effect_type: str, content: str = "", security_label: str = "internal") -> bool:
    """Check PolicyEngine before executing an effect. Fail-closed for external effects.

    Scans content in chunks (2000 chars each) to avoid truncation bypass.
    """
    engine = _svc(state).policy_engine
    if not engine:
        logger.debug("PolicyEngine not configured — allowing %s (no engine)", effect_type)
        return True  # no engine = allow (intentional for simple deployments)
    try:
        from chatgptrest.kernel.policy_engine import QualityContext
        # Scan full content in chunks to prevent truncation bypass
        chunk_size = 2000
        chunks = [content[i:i + chunk_size] for i in range(0, max(len(content), 1), chunk_size)] if content else [""]
        for chunk in chunks:
            ctx = QualityContext(
                audience=effect_type,
                security_label=security_label,
                content=chunk,
                channel=effect_type,
            )
            result = engine.run_quality_gate(ctx)
            if not result.allowed:
                logger.warning("PolicyEngine rejected chunk in %s (len=%d)", effect_type, len(chunk))
                return False
        return True
    except Exception as e:
        logger.warning("PolicyEngine check failed (fail-closed): %s", e)
        return False  # fail-closed


# ── Nodes ─────────────────────────────────────────────────────────

# Filler words commonly used in Chinese voice input
_FILLER_PATTERN = re.compile(
    r"(?:那个|就是说?|嗯+|啊+|这个|然后呢?|所以说?|对吧?|你看|怎么说呢)\s*",
    re.UNICODE,
)


def normalize(state: AdvisorState) -> dict:
    """Clean up user message: strip fillers, normalize whitespace."""
    msg = state.get("user_message", "")
    # Strip Chinese voice fillers
    cleaned = _FILLER_PATTERN.sub("", msg)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return {
        "normalized_message": cleaned or msg,
        "trace_id": state.get("trace_id") or str(uuid.uuid4()),
    }


def kb_probe(state: AdvisorState) -> dict:
    """Probe the KB for relevant documents using KBHub hybrid search.

    Uses KBHub.search() for FTS5 + optional vector search.
    Returns kb_has_answer, kb_top_chunks, kb_answerability.
    """
    # If kb fields are already populated (e.g., by caller), just pass through
    if "kb_answerability" in state:
        return {
            "kb_has_answer": state.get("kb_answerability", 0) > 0.5,
        }

    hub = _svc(state).kb_hub
    msg = state.get("normalized_message", state.get("user_message", ""))

    if hub and msg:
        try:
            hits = hub.search(msg, top_k=5)
            if hits:
                query_terms = _extract_query_terms(msg)
                chunks = [
                    {
                        "artifact_id": h.artifact_id,
                        "title": h.title,
                        "snippet": h.snippet[:200],
                        "score": h.score,
                        "term_overlap": _term_overlap_ratio(
                            query_terms, f"{h.title or ''}\n{h.snippet or ''}"
                        ),
                    }
                    for h in hits
                ]
                max_overlap = max(float(c.get("term_overlap") or 0.0) for c in chunks)
                avg_overlap = sum(float(c.get("term_overlap") or 0.0) for c in chunks) / max(len(chunks), 1)
                hit_signal = min(0.2, 0.05 * len(hits))
                overlap_signal = max(max_overlap, avg_overlap * 0.8)
                answerability = min(hit_signal + 0.8 * overlap_signal, 1.0)
                has_answer = answerability >= 0.45 and max_overlap >= 0.18
                logger.info(
                    "KB probe: %d hits, max_overlap=%.2f, answerability=%.2f, has_answer=%s",
                    len(hits), max_overlap, answerability, has_answer,
                )
                return {
                    "kb_has_answer": has_answer,
                    "kb_top_chunks": chunks,
                    "kb_answerability": answerability,
                    "open_issues": [],  # populated below if no early return
                }
        except Exception as e:
            logger.warning("KB probe failed: %s", e)

    # Default: no KB match
    # Also probe Issue Ledger for open issues (context injection)
    open_issues_context: list[dict] = []
    try:
        from chatgptrest.core import client_issues
        from chatgptrest.core.db import connect as _db_connect
        db_conn = _db_connect()
        if db_conn:
            issues_list, _, _ = client_issues.list_issues(
                db_conn,
                status="open,in_progress",
                limit=10,
            )
            if issues_list:
                open_issues_context = [
                    {
                        "issue_id": iss.issue_id,
                        "title": iss.title,
                        "severity": iss.severity,
                        "count": iss.count,
                        "kind": iss.kind,
                        "status": iss.status,
                    }
                    for iss in issues_list
                ]
    except Exception as e:
        logger.debug("Issue Ledger probe failed: %s", e)

    return {
        "kb_has_answer": False,
        "kb_top_chunks": [],
        "kb_answerability": 0.0,
        "open_issues": open_issues_context,
    }


def analyze_intent(state: AdvisorState) -> dict:
    """Analyze intent from the normalized message.

    Uses rule-based heuristics with expanded keyword coverage.
    Detects action_required, multi_intent, and step_count from message content.

    KEY ROUTING PRINCIPLE:
      If the user wants a WRITTEN DELIVERABLE (report, article, summary,
      introduction, overview, comparison), intent = WRITE_REPORT.
      DO_RESEARCH is only for pure investigation without written output.
    """
    msg = state.get("normalized_message", state.get("user_message", ""))
    msg_lower = msg.lower()

    # ── Intent classification (expanded keywords) ────────────
    intent_top = "QUICK_QUESTION"
    confidence = 0.7

    # Content-creation signals — user wants a written deliverable
    _WRITE_DELIVERABLE_SIGNALS = [
        # Chinese verbs for writing/creating
        "报告", "总结", "汇报", "周报", "月报",
        "写一篇", "做一篇", "撰写", "草拟", "起草", "介绍",
        "做一份", "写一份", "做个", "写个",
        "概述", "简介", "概要", "综述", "摘要", "现状摘要",
        # Understanding/learning (user wants content, not just answer)
        "了解", "了解一下", "科普", "讲解", "解读",
        # English writing verbs
        "write", "overview", "introduction", "summarize",
        "summary", "article", "essay", "brief", "report",
        # Report types
        "趋势", "现状", "前景", "发展趋势", "进展报告", "进展汇报",
    ]
    _WRITE_ANALYSIS_SIGNALS = [
        # Analysis/comparison terms can mean a deliverable, but do not outrank pure research alone.
        "分析", "对比", "比较", "评估", "优劣", "选型",
        "技术选型", "可行性",
        "analyze", "analysis", "compare", "comparison",
    ]
    _WRITE_SIGNALS = _WRITE_DELIVERABLE_SIGNALS + _WRITE_ANALYSIS_SIGNALS
    # Pure research — investigation without specific written deliverable
    _RESEARCH_ONLY_SIGNALS = [
        "调研", "研究", "research", "investigate",
        "审查", "review", "check", "诊断", "debug", "排查",
        "投资",
    ]
    # Build/feature signals
    _BUILD_SIGNALS = [
        "开发", "build", "实现", "feature", "功能", "设计", "design", "架构",
        "新建", "创建", "制作", "搭建", "部署", "配置",
        "create", "make", "setup", "deploy",
    ]
    _BUILD_DELIVERABLE_SIGNALS = [
        "项目卡", "任务拆分", "任务分解", "需求拆解", "mvp", "验收标准",
        "原型", "小应用", "系统设计", "功能设计",
        "业务流程", "关键业务流程", "核心实体", "实体关系",
        "最小可行版本", "最小可行方案", "积分系统",
    ]
    _RESEARCH_DISAMBIGUATION_SIGNALS = [
        "先做研究判断", "研究判断", "只做研究", "先做研究", "先调研",
        "不写正式汇报", "不写正式报告", "不写报告", "不要写报告", "先不写报告",
    ]

    # Match intents via scoring model (P2: replaces strict if/elif keyword precedence).
    # Each matching keyword adds 1 point; imperative patterns add 2 bonus points.
    # Highest score wins, preventing research from always beating build on mixed messages.
    import re as _intent_re
    _scores: dict[str, float] = {"WRITE_REPORT": 0, "DO_RESEARCH": 0, "BUILD_FEATURE": 0}
    for kw in _WRITE_SIGNALS:
        if kw in msg_lower:
            _scores["WRITE_REPORT"] += 1
    for kw in _RESEARCH_ONLY_SIGNALS:
        if kw in msg_lower:
            _scores["DO_RESEARCH"] += 1
    for kw in _BUILD_SIGNALS:
        if kw in msg_lower:
            _scores["BUILD_FEATURE"] += 1
    for kw in _BUILD_DELIVERABLE_SIGNALS:
        if kw in msg_lower:
            _scores["BUILD_FEATURE"] += 2

    # Imperative patterns (命令式): direct commands strongly indicate BUILD_FEATURE
    _IMPERATIVE_RE = _intent_re.compile(
        r"(?:^|[，。；\n])\s*(?:请|帮我|帮忙|把|给我|you need to|please|go ahead|make|do)\s*\S",
        _intent_re.IGNORECASE | _intent_re.UNICODE,
    )
    has_build_semantics = _scores["BUILD_FEATURE"] > 0
    if _IMPERATIVE_RE.search(msg) and has_build_semantics:
        _scores["BUILD_FEATURE"] += 2  # strong bonus for imperative commands
    _PRODUCT_BUILD_RE = _intent_re.compile(
        r"(?:做|开发|实现|设计|搭建|规划).{0,12}(?:系统|应用|平台|工具|流程|方案|实体)",
        _intent_re.IGNORECASE | _intent_re.UNICODE,
    )
    if _PRODUCT_BUILD_RE.search(msg):
        _scores["BUILD_FEATURE"] += 3

    research_score = sum(1 for kw in _RESEARCH_ONLY_SIGNALS if kw in msg_lower)
    write_deliverable_score = sum(1 for kw in _WRITE_DELIVERABLE_SIGNALS if kw in msg_lower)
    write_analysis_score = sum(1 for kw in _WRITE_ANALYSIS_SIGNALS if kw in msg_lower)

    # "调研/研究 + 分析" without an explicit report/deliverable noun is still research,
    # not report writing. This preserves direct research routing for prompts like
    # "调研一下竞品分析" while letting "写个竞品分析报告" remain WRITE_REPORT.
    if (
        research_score > 0
        and write_deliverable_score == 0
        and write_analysis_score > 0
        and _scores["BUILD_FEATURE"] <= research_score
    ):
        _scores["DO_RESEARCH"] += write_analysis_score
    if any(kw in msg_lower for kw in _RESEARCH_DISAMBIGUATION_SIGNALS):
        _scores["DO_RESEARCH"] += 3
        _scores["WRITE_REPORT"] = max(0, _scores["WRITE_REPORT"] - 1)

    # Pick highest-scoring intent
    best_intent = max(_scores, key=lambda k: _scores[k])
    if _scores[best_intent] > 0:
        intent_top = best_intent
        confidence = min(0.7 + 0.05 * _scores[best_intent], 0.95)

    # ── Action detection: requires external service interaction ──
    _ACTION_VERBS = [
        "放在", "放到", "保存到", "存到", "上传到", "上传", "发送到", "发到",
        "发给", "推送", "部署到", "写入", "导出", "同步到",
        "google drive", "drive", "飞书", "邮件", "slack", "notion",
        "github", "gitlab",
    ]
    _ACTION_COMMAND_RE = _intent_re.compile(
        r"(?:给|向).{0,8}(?:发(?:一条)?通知|通知)|发(?:一条)?通知|notify",
        _intent_re.IGNORECASE | _intent_re.UNICODE,
    )
    action_required = any(kw in msg_lower for kw in _ACTION_VERBS) or bool(_ACTION_COMMAND_RE.search(msg))

    # ── Multi-intent detection ──────────────────────────────
    _MULTI_MARKERS = ["和", "并且", "然后", "同时", "以及", "再", "另外", "还要"]
    multi_intent = any(m in msg for m in _MULTI_MARKERS) or " and " in msg_lower
    # Also detect implicit multi-intent: comma-separated actions
    comma_clauses = len([c for c in msg.split("，") if len(c.strip()) > 3])
    if comma_clauses >= 3:
        multi_intent = True

    # ── Step count estimation ───────────────────────────────
    step_count = 1
    if action_required:
        step_count += 1  # external action = extra step
    if any(kw in msg_lower for kw in ["格式", "format", "md", "markdown", "pdf"]):
        step_count += 1  # formatting = extra step
    if multi_intent:
        step_count += 1
    step_count = min(step_count + comma_clauses - 1, 10)

    # ── Constraint detection ────────────────────────────────
    import re as _re
    constraint_count = 0
    if _re.search(r'\d+\s*字', msg) or _re.search(r'\d+.?word', msg_lower):
        constraint_count += 1
    if any(kw in msg_lower for kw in ["格式", "format", "md", "markdown", "pdf", "json"]):
        constraint_count += 1
    if any(kw in msg_lower for kw in ["中文", "英文", "双语", "english", "chinese"]):
        constraint_count += 1

    scenario_pack = state.get("scenario_pack")
    if isinstance(scenario_pack, dict):
        preferred_intent = str(scenario_pack.get("intent_top") or state.get("intent_top") or "").strip()
        if preferred_intent:
            intent_top = preferred_intent
            try:
                confidence = max(confidence, float(state.get("intent_confidence", 0.95) or 0.95))
            except Exception:
                confidence = max(confidence, 0.95)

    return {
        "intent_top": intent_top,
        "intent_confidence": confidence,
        "multi_intent": multi_intent,
        "step_count_est": max(step_count, state.get("step_count_est", 1)),
        "constraint_count": max(constraint_count, state.get("constraint_count", 0)),
        "open_endedness": state.get("open_endedness", 0.3),
        "verification_need": state.get("verification_need", False),
        "action_required": action_required or state.get("action_required", False),
    }


def _extract_query_terms(text: str) -> set[str]:
    raw = str(text or "").strip().lower()
    terms: set[str] = set()
    for token in _ASCII_TOKEN_RE.findall(raw):
        terms.add(token)
    for block in _CJK_BLOCK_RE.findall(raw):
        cleaned = block.strip()
        if len(cleaned) <= 4:
            terms.add(cleaned)
            continue
        for size in (2, 3):
            for idx in range(0, max(len(cleaned) - size + 1, 0)):
                terms.add(cleaned[idx: idx + size])
    return {t for t in terms if len(t.strip()) >= 2}


def _term_overlap_ratio(query_terms: set[str], text: str) -> float:
    if not query_terms:
        return 0.0
    haystack = str(text or "").lower()
    matched = sum(1 for term in query_terms if term in haystack)
    return round(matched / max(len(query_terms), 1), 4)


def route_decision(state: AdvisorState) -> dict:
    """Apply C/K/U/R/I routing decision tree with intent-aware overrides."""
    from chatgptrest.advisor import compute_all_scores, select_route

    intent = IntentSignals(
        intent_top=state.get("intent_top", ""),
        intent_confidence=state.get("intent_confidence", 0.0),
        multi_intent=state.get("multi_intent", False),
        step_count_est=state.get("step_count_est", 1),
        constraint_count=state.get("constraint_count", 0),
        open_endedness=state.get("open_endedness", 0.0),
        verification_need=state.get("verification_need", False),
        action_required=state.get("action_required", False),
    )

    kb_probe_result = KBProbeResult(
        answerability=state.get("kb_answerability", 0.0),
        top_chunks=state.get("kb_top_chunks", []),
    )

    scores = compute_all_scores(
        intent=intent,
        kb_probe=kb_probe_result,
        urgency_hint=state.get("urgency_hint", "whenever"),
    )

    decision = select_route(intent, scores)

    # ── Intent-aware route override ──────────────────────────
    # The generic scorer often defaults to "hybrid", but intent
    # determines which executor produces the right deliverable:
    #   WRITE_REPORT → report_graph (draft→review→finalize, real report text)
    #   DO_RESEARCH  → deep_research (LLM deep analysis, real research output)
    #   BUILD_FEATURE → funnel (ProjectCard→tasks→dispatch)
    #   QUICK_QUESTION → kb_answer or funnel (depending on KB hit)
    intent_top = state.get("intent_top", "")
    route = decision.route
    rationale = decision.rationale

    if intent.action_required and intent_top == "QUICK_QUESTION" and route in ("hybrid", "kb_answer", "quick_ask", ""):
        route = "action"
        rationale += " → Override: explicit action request → action pipeline"
    elif intent_top == "WRITE_REPORT" and route not in ("report", "write_report"):
        route = "report"
        rationale += f" → Override: WRITE_REPORT intent → report pipeline"
    elif intent_top == "DO_RESEARCH" and route not in ("deep_research",):
        route = "deep_research"
        rationale += f" → Override: DO_RESEARCH intent → deep_research pipeline"
    elif intent_top == "BUILD_FEATURE" and route not in ("funnel", "build_feature", "action"):
        route = "funnel"
        rationale += f" → Override: BUILD_FEATURE intent → funnel pipeline"

    return_val = {
        "route_scores": scores.to_dict(),
        "selected_route": route,
        "route_rationale": rationale,
    }

    # Record intent + route to Meta memory
    memory = _svc(state).memory
    if memory:
        try:
            from chatgptrest.kernel.memory_manager import MemoryRecord, MemoryTier
            trace_id = state.get("trace_id", "")
            memory.stage_and_promote(MemoryRecord(
                category="route_stat",
                key=f"route:{trace_id}",
                value={
                    "intent": intent_top,
                    "confidence": state.get("intent_confidence", 0),
                    "route": route,
                    "kb_has_answer": state.get("kb_has_answer", False),
                    "message_preview": state.get("user_message", "")[:50],
                },
                confidence=1.0,
                source={"type": "system", "agent": "advisor", "task_id": trace_id},
            ), MemoryTier.META, "route decision")
        except Exception as e:
            logger.warning("Memory record failed: %s", e)

    # Emit route_selected event
    _emit_event(state, "route.selected", "advisor", {
        "intent": intent_top,
        "route": route,
        "kb_has_answer": state.get("kb_has_answer", False),
        "confidence": state.get("intent_confidence", 0),
    })

    return return_val


# ── KB Writeback Helper ────────────────────────────────────────────


def _resolve_report_type(state: AdvisorState) -> str:
    report_type = str(state.get("report_type") or "").strip().lower()
    if report_type:
        return report_type
    scenario_pack = state.get("scenario_pack")
    if isinstance(scenario_pack, dict):
        provider_hints = dict(scenario_pack.get("provider_hints") or {})
        hinted = str(provider_hints.get("report_type") or "").strip().lower()
        if hinted in {"progress", "analysis", "summary"}:
            return hinted
    return "progress"


def _research_scope_note(scenario_pack: dict[str, Any]) -> str:
    if not scenario_pack:
        return ""
    profile = str(scenario_pack.get("profile") or "").strip()
    acceptance = dict(scenario_pack.get("acceptance") or {})
    evidence_required = dict(scenario_pack.get("evidence_required") or {})
    sections = [str(item).strip() for item in list(acceptance.get("required_sections") or []) if str(item).strip()]
    lines: list[str] = []
    if profile:
        lines.append(f"- research_profile: {profile}")
    if sections:
        lines.append(f"- required_sections: {', '.join(sections)}")
    min_evidence = acceptance.get("min_evidence_items")
    if min_evidence:
        lines.append(f"- minimum_evidence_items: {int(min_evidence)}")
    if evidence_required.get("prefer_primary_sources"):
        lines.append("- prefer_primary_sources: true")
    if evidence_required.get("require_traceable_claims"):
        lines.append("- require_traceable_claims: true")
    return "\n".join(lines)

def _kb_writeback_and_record(
    state: AdvisorState,
    content: str,
    artifact_name: str,
    artifact_type: str,
    source_system: str,
    project_id: str,
    para_bucket: str = "resource",
    structural_role: str = "analysis",
    extra_metadata: dict | None = None,
    content_type: str = "markdown",
    knowledge_plane: str = "runtime_working",
) -> dict | None:
    """Common KB writeback and registration logic.

    Args:
        state: AdvisorState for accessing services
        content: Content to write to KB
        artifact_name: Name prefix for the artifact file
        artifact_type: Type string (e.g., "research", "report", "funnel")
        source_system: Source system identifier
        project_id: Project/trace ID
        para_bucket: KB para_bucket
        structural_role: KB structural_role
        extra_metadata: Additional metadata for FTS5 indexing
        content_type: File content type ("markdown" or "json")

    Returns:
        Dict with artifact_path and optional artifact_id, or None on failure
    """
    # #59 fix: explicit env var for artifact dir (was ambiguous as both dir and DB path)
    svc = _svc(state)

    # B6: PolicyEngine check before KB writeback
    if not _policy_check(state, "kb_writeback", content):
        logger.warning("PolicyEngine rejected %s KB writeback", artifact_type)
        _emit_event(state, "kb.writeback_rejected", "policy",
                    {"type": artifact_type, "reason": "policy_check_failed"})
        return {"type": artifact_type}

    requested_plane = str(knowledge_plane or "runtime_working").strip().lower()
    writeback = getattr(svc, "writeback_service", None)
    if writeback:
        try:
            from chatgptrest.cognitive.ingest_service import KnowledgeIngestItem, KnowledgeIngestService

            task_intake = dict(state.get("task_intake") or {}) if isinstance(state.get("task_intake"), dict) else {}
            scenario_pack = dict(state.get("scenario_pack") or {}) if isinstance(state.get("scenario_pack"), dict) else {}
            risk_level = (
                str(state.get("risk_level") or "")
                or str(state.get("risk_class") or "")
                or str(task_intake.get("risk_class") or "")
                or "low"
            )
            ingest_result = KnowledgeIngestService(svc).ingest(
                [
                    KnowledgeIngestItem(
                        title=f"{artifact_type.capitalize()}: {state.get('user_message', '')[:60]}",
                        content=content,
                        trace_id=project_id,
                        session_id=str(state.get("session_id") or ""),
                        source_system=source_system,
                        source_ref=f"advisor://{artifact_type}/{project_id}",
                        content_type=content_type,
                        project_id=project_id,
                        para_bucket=para_bucket,
                        structural_role=structural_role,
                        domain_tags=list(dict.fromkeys([artifact_type] + list((scenario_pack.get("domain_tags") or []) if isinstance(scenario_pack.get("domain_tags"), list) else []))),
                        audience=str(state.get("audience") or "internal"),
                        security_label=str(state.get("security_label") or "internal"),
                        risk_level=str(risk_level).strip() or "low",
                        estimated_tokens=max(1, len(content) // 4),
                        graph_extract=requested_plane == "canonical_knowledge",
                    )
                ]
            )
            item = ingest_result.results[0]
            return {
                "artifact_path": item.file_path,
                "artifact_id": item.artifact_id or None,
                "type": artifact_type,
                "success": item.ok,
                "accepted": item.accepted,
                "message": item.message,
                "quality_gate": dict(item.quality_gate or {}),
                "graph_refs": dict(item.graph_refs or {}),
                "knowledge_plane": str((item.graph_refs or {}).get("knowledge_plane") or requested_plane),
                "write_path": str((item.graph_refs or {}).get("write_path") or ("working_only" if requested_plane != "canonical_knowledge" else "canonical_requested")),
            }
        except Exception as e:
            logger.warning("KnowledgeIngestService writeback failed, falling back to direct KB writeback: %s", e)

    if writeback:
        result = writeback.writeback(
            content=content,
            trace_id=project_id,
            content_type=content_type,
            title=f"{artifact_type.capitalize()}: {state.get('user_message', '')[:60]}",
            file_name=f"{artifact_name}.{ 'json' if content_type == 'json' else 'md'}",
            project_id=project_id,
            para_bucket=para_bucket,
            structural_role=structural_role,
            source_system=source_system,
            domain_tags=[artifact_type],
        )
        kb_record: dict[str, Any] = {
            "artifact_path": result.file_path,
            "artifact_id": result.artifact_id or None,
            "type": artifact_type,
            "success": result.success,
            "knowledge_plane": "runtime_working",
            "write_path": "fallback_working_only",
        }
    else:
        kb_dir_str = os.environ.get("OPENMIND_KB_ARTIFACT_DIR", "")
        if not kb_dir_str:
            kb_dir_str = os.environ.get("OPENMIND_KB_PATH", "")
            if kb_dir_str:
                logger.warning("OPENMIND_KB_PATH is deprecated for artifact dir, use OPENMIND_KB_ARTIFACT_DIR")
        if not kb_dir_str:
            kb_dir_str = os.path.expanduser("~/.openmind/kb")
        kb_dir = pathlib.Path(kb_dir_str)
        kb_dir.mkdir(parents=True, exist_ok=True)
        extension = "json" if content_type == "json" else "md"
        artifact_path = kb_dir / f"{artifact_name}.{extension}"
        artifact_path.write_text(content, encoding="utf-8")
        kb_record = {
            "artifact_path": str(artifact_path),
            "type": artifact_type,
            "success": True,
            "knowledge_plane": "runtime_working",
            "write_path": "filesystem_working_only",
        }

    _emit_event(state, "kb.writeback", "kb",
                {
                    "path": str(kb_record.get("artifact_path") or ""),
                    "type": artifact_type,
                    "knowledge_plane": kb_record.get("knowledge_plane"),
                    "write_path": kb_record.get("write_path"),
                })

    return kb_record


def _summarize_dispatch_for_kb(dispatch_result: Any) -> dict[str, Any] | None:
    """Strip local filesystem details before writing dispatch state into KB."""
    if not isinstance(dispatch_result, dict):
        return None

    summary: dict[str, Any] = {
        "status": dispatch_result.get("status"),
        "trace_id": dispatch_result.get("trace_id"),
    }
    error = dispatch_result.get("error")
    if error:
        summary["error"] = str(error)[:200]

    result = dispatch_result.get("result")
    if isinstance(result, dict):
        deliverables = result.get("deliverables")
        code_files = result.get("code_files")
        summary["result"] = {
            "session_id": result.get("session_id"),
            "task_count": result.get("task_count"),
            "deliverable_count": len(deliverables) if isinstance(deliverables, list) else 0,
            "code_file_count": len(code_files) if isinstance(code_files, list) else 0,
            "has_project_dir": bool(result.get("project_dir")),
        }

    return summary


# ── Route Execution Nodes ─────────────────────────────────────────

def execute_quick_ask(state: AdvisorState) -> dict:
    """Execute quick_ask route: KB search + LLM synthesis.

    If KB has relevant chunks, synthesize a natural language answer.
    If no KB hits, use LLM directly for a quick answer.
    """
    from chatgptrest.advisor.simple_routes import quick_ask
    from chatgptrest.kernel.llm_connector import bind_llm_signal_trace

    msg = state.get("normalized_message", state.get("user_message", ""))
    llm_fn = state.get("llm_connector")
    kb_chunks = state.get("kb_top_chunks", []) if state.get("kb_has_answer", False) else []
    trace_id = state.get("trace_id", "")
    session_id = state.get("session_id", "")

    # #46: Build context-enriched system prompt via ContextAssembler
    context_system_prompt = ""
    svc = _svc(state)
    if svc.memory:
        try:
            from chatgptrest.cognitive.context_service import ContextResolveOptions, ContextResolver

            resolved = ContextResolver(svc).resolve(
                ContextResolveOptions(
                    query=msg,
                    session_id=session_id,
                    account_id=str(state.get("account_id", "") or ""),
                    agent_id=str(state.get("agent_id", "") or ""),
                    role_id=str(state.get("role_id", "") or ""),
                    thread_id=str(state.get("thread_id", "") or ""),
                    trace_id=trace_id,
                )
            )
            context_system_prompt = resolved.prompt_prefix
        except Exception as e:
            logger.debug("ContextAssembler failed (non-fatal): %s", e)

    kb_search_fn = state.get("_kb_search_fn")
    result = quick_ask(
        msg,
        trace_id=trace_id,
        kb_search_fn=kb_search_fn if kb_search_fn else lambda q, k: kb_chunks,
    )

    # If we have KB context or LLM, synthesize a proper text answer
    base_sys = "你是一个知识助手，根据提供的知识库内容回答问题。"
    if context_system_prompt:
        base_sys = f"{context_system_prompt}\n\n{base_sys}"

    if result.answer and _kb_direct_synthesis_enabled():
        try:
            llm_fn = llm_fn or _get_llm_fn("default", state=state)
            if llm_fn:
                synthesis_prompt = (
                    f"根据以下知识库内容，简洁准确地回答用户问题。\n\n"
                    f"用户问题：{msg}\n\n"
                    f"知识库内容：\n{result.answer}\n\n"
                    f"请直接回答，不要重复问题。"
                )
                with bind_llm_signal_trace(trace_id):
                    synthesized = llm_fn(synthesis_prompt, base_sys)
                result.answer = synthesized
        except Exception as e:
            logger.warning("LLM synthesis failed, using raw KB answer: %s", e)
    elif not result.answer:
        # No KB hits — use LLM directly
        try:
            llm_fn = llm_fn or _get_llm_fn("default", state=state)
            with bind_llm_signal_trace(trace_id):
                direct_answer = llm_fn(msg, base_sys)
            result.answer = direct_answer
            result.status = "success"
        except Exception as e:
            logger.warning("LLM direct answer failed: %s", e)

    # #46: Record conversation turn to working memory
    if svc.memory and result.answer:
        try:
            from chatgptrest.kernel.memory_manager import MemoryRecord, MemoryTier
            svc.memory.stage_and_promote(MemoryRecord(
                key=f"turn:{trace_id}:user",
                value={"role": "user", "message": msg},
                source={"type": "user_input", "agent": "advisor", "session_id": session_id},
            ), MemoryTier.WORKING, "quick_ask user turn")
            svc.memory.stage_and_promote(MemoryRecord(
                key=f"turn:{trace_id}:assistant",
                value={"role": "assistant", "message": result.answer[:500]},
                source={"type": "llm_response", "agent": "advisor", "session_id": session_id},
            ), MemoryTier.WORKING, "quick_ask assistant turn")
        except Exception as e:
            logger.debug("Memory record failed (non-fatal): %s", e)

    return {
        "route_result": result.to_dict(),
        "route_status": result.status,
    }


def execute_deep_research(state: AdvisorState) -> dict:
    """Execute deep_research route: KB context + LLM deep analysis.

    Produces real research deliverable with EvoMap signals + KB writeback.
    """
    from chatgptrest.advisor.simple_routes import deep_research
    from chatgptrest.kernel.llm_connector import bind_llm_signal_trace

    llm_fn = state.get("llm_connector") or _get_llm_fn("research", state=state)
    observer = _svc(state).evomap_observer
    kb_reg = _svc(state).kb_registry
    kb_hub = _svc(state).kb_hub
    trace_id = state.get("trace_id", "")
    scenario_pack = dict(state.get("scenario_pack") or {}) if isinstance(state.get("scenario_pack"), dict) else {}
    research_scope_note = _research_scope_note(scenario_pack)
    query_text = state.get("normalized_message", state.get("user_message", ""))

    def _emit(sig_type, source, domain=None, data=None):
        # Phase-1 fix: route through EventBus instead of direct observer call
        _emit_event(state, sig_type, source, data)

    _emit("route.selected", "advisor", "routing",
          {"route": "deep_research", "intent": state.get("intent_top")})

    # G3: Use KBHub for real KB context
    kb_context = ""
    if kb_hub:
        try:
            hits = kb_hub.search(query_text, top_k=10)
            if hits:
                kb_context = "\n".join(
                    f"- [{h.title}] {h.snippet[:150]}" for h in hits[:5]
                )
                _emit("kb.search_hit", "deep_research", "kb",
                      {"hit_count": len(hits), "top_score": hits[0].score})
        except Exception as e:
            logger.warning("Deep research KB search failed: %s", e)

    # Build kb_search_fn for deep_research
    def _kb_search(q, k=5):
        if kb_hub:
            try:
                return [
                    {"artifact_id": h.artifact_id, "title": h.title,
                     "snippet": h.snippet[:200], "score": h.score}
                    for h in kb_hub.search(q, top_k=k)
                ]
            except Exception as e:
                logger.warning("KB search in deep_research failed: %s", e)
        return []

    if research_scope_note:
        if kb_context:
            kb_context = f"研究约束:\n{research_scope_note}\n\n---\n{kb_context}"
        else:
            kb_context = f"研究约束:\n{research_scope_note}"

    with bind_llm_signal_trace(trace_id):
        result = deep_research(
            query_text,
            trace_id=trace_id,
            llm_fn=llm_fn if llm_fn else lambda p, s: f"[deep research: {p[:50]}]",
            kb_search_fn=_kb_search,
            kb_context=kb_context,
        )

        _emit("report.step_completed", "deep_research", "report",
              {"status": result.status, "answer_len": len(result.answer or "")})

        # ── Quality Review Gate ──────────────────────────────────
        review_pass = True
        review_notes: list[str] = []
        if result.status == "success" and result.answer and llm_fn:
            try:
                review_len = min(len(result.answer), 2000)
                review_prompt = (
                    f"请审核以下研究报告（前{review_len}字）:\n"
                    f"{result.answer[:review_len]}\n\n"
                    "评估维度:\n"
                    "1. 结构完整性（有摘要/分析/结论）\n"
                    "2. 论据充分性（有数据/对比/引用）\n"
                    "3. 可操作性（有推荐/排序/建议）\n\n"
                    "请给出1-10分的综合评分，然后用1-3条简短审核意见。\n"
                    "格式：第一行写'评分：X/10'，后面写审核意见。"
                )
                review_resp = llm_fn(review_prompt, "你是一个研究报告审核专家。简洁回答。")

                # Extract score from response (look for X/10 pattern)
                score_match = re.search(r"(\d+)\s*/\s*10", review_resp)
                review_score = int(score_match.group(1)) if score_match else 7
                review_pass = review_score >= 6  # 6/10 threshold

                # Fallback: also check for explicit pass/fail keywords
                if not score_match:
                    review_pass = ("通过" in review_resp or "pass" in review_resp.lower()
                                   or "合格" in review_resp or "良好" in review_resp)

                review_notes = [l.strip() for l in review_resp.strip().split("\n") if l.strip()]

                _emit("research.review_completed", "deep_research", "quality",
                      {"review_pass": review_pass, "notes_count": len(review_notes)})
            except Exception as e:
                logger.warning("Deep research review failed: %s", e)
                review_notes = [f"审核失败: {e}"]

    # KB writeback for research output
    if result.status == "success" and result.answer:
        # Append review notes if review didn't pass
        answer_text = result.answer
        if not review_pass and review_notes:
            answer_text += "\n\n---\n> ⚠️ 审核建议（供参考）:\n" + "\n".join(
                f"> - {n}" for n in review_notes
            )

        try:
            kb_record = _kb_writeback_and_record(
                state=state,
                content=answer_text,
                artifact_name=f"research_{trace_id[:12]}",
                artifact_type="research",
                source_system="openmind_research",
                project_id=trace_id,
                para_bucket="resource",
                structural_role="analysis",
                extra_metadata={"stability": "draft", "quarantine": True, "source": "auto_research"},
                knowledge_plane="canonical_knowledge",
            )
        except Exception as e:
            logger.warning("Research KB writeback failed: %s", e)

    # R4: Record research result to Episodic memory
    memory = _svc(state).memory
    if memory and result.status == "success":
        try:
            from chatgptrest.kernel.memory_manager import MemoryRecord, MemoryTier
            memory.stage_and_promote(MemoryRecord(
                category="research_result",
                key=f"research:{trace_id}",
                value={
                    "query": state.get("user_message", "")[:100],
                    "answer_len": len(result.answer) if result.answer else 0,
                    "review_pass": review_pass,
                    "evidence_count": len(result.evidence_refs),
                },
                confidence=0.8 if review_pass else 0.5,
                source={"type": "system", "agent": "deep_research", "task_id": trace_id},
            ), MemoryTier.EPISODIC, "research result")
        except Exception as e:
            logger.warning("Episodic memory record failed: %s", e)

    rd = result.to_dict()
    rd["stage"] = "research_complete"
    rd["review_pass"] = review_pass
    rd["review_notes"] = review_notes
    return {
        "route_result": rd,
        "route_status": result.status,
    }


def execute_report(state: AdvisorState) -> dict:
    """Execute report route: full pipeline with KB + EvoMap.

    Full pipeline: purpose_identify → evidence_pack → draft → review → finalize
    Then: KB writeback + ArtifactRegistry + EvoMap signals.
    """
    from chatgptrest.advisor.report_graph import build_report_graph
    from chatgptrest.kernel.llm_connector import bind_llm_signal_trace

    runtime = _svc(state)
    trace_id = state.get("trace_id", "")
    scenario_pack = dict(state.get("scenario_pack") or {}) if isinstance(state.get("scenario_pack"), dict) else {}
    report_type = _resolve_report_type(state)

    def _emit(sig_type, source, domain=None, data=None):
        # Phase-1 fix: route through EventBus instead of direct observer call
        _emit_event(state, sig_type, source, data)

    _emit("route.selected", "advisor", "routing",
          {"route": "report", "intent": state.get("intent_top")})

    try:
        report_app = build_report_graph().compile()
        with bind_runtime_services(runtime), bind_llm_signal_trace(trace_id):
            result = report_app.invoke({
                "user_message": state.get("user_message", ""),
                "trace_id": trace_id,
                "report_type": report_type,
                "scenario_pack": scenario_pack,
                "_delivery_target": state.get("_delivery_target", ""),
            })
    except Exception as e:
        logger.error("Report sub-graph failed: %s", e)
        result = {
            "final_status": "error",
            "final_text": f"报告生成失败: {e}",
            "draft_sections": [],
            "review_notes": [str(e)],
            "review_pass": False,
        }

    final_status = result.get("final_status", "error")
    final_text = result.get("final_text", "") or result.get("internal_draft_text", "")
    review_notes = result.get("review_notes", [])
    review_pass = result.get("review_pass", False)
    workspace_delivery: list[dict[str, Any]] = []

    outbox = getattr(runtime, "outbox", None)
    if outbox and trace_id:
        try:
            workspace_delivery = execute_workspace_effects_for_trace(outbox, trace_id=trace_id)
        except Exception as e:
            logger.warning("Workspace effect execution failed for trace %s: %s", trace_id, e)
            workspace_delivery = [{"success": False, "error": str(e)}]

    if workspace_delivery:
        successful = next((item for item in workspace_delivery if item.get("success")), None)
        if successful:
            result_full = dict(successful.get("workspace_result_full") or {})
            data = dict(result_full.get("data") or {})
            doc_url = str(data.get("url") or "").strip()
            if doc_url:
                final_text += f"\n\n---\n> 📄 **Google Docs 已交付**: {doc_url}\n"
            gmail_meta = dict(data.get("gmail") or {})
            if gmail_meta:
                final_text += "> 📧 **Gmail 通知已发送**\n"
        else:
            first_error = str(workspace_delivery[0].get("error") or "workspace delivery failed").strip()
            final_text += f"\n\n---\n> ⚠️ **Workspace 交付失败**: {first_error}\n"

    _emit("report.step_completed", "report", "report",
          {"status": final_status, "review_pass": review_pass,
           "text_len": len(final_text)})

    # Stage: KB Writeback — persist the report artifact
    kb_record = None
    trace = trace_id or "unknown"
    if final_status == "complete" and final_text:
        try:
            kb_record = _kb_writeback_and_record(
                state=state,
                content=final_text,
                artifact_name=f"report_{trace[:12]}",
                artifact_type="report",
                source_system="openmind_report",
                project_id=trace,
                para_bucket="resource",
                structural_role="analysis",
                extra_metadata={"stability": "draft", "quarantine": True, "source": "auto_report"},
                knowledge_plane="canonical_knowledge",
            )
        except Exception as e:
            logger.warning("KB writeback failed: %s", e)

    # R4: Record report result to Episodic memory
    memory = _svc(state).memory
    if memory and final_text:
        try:
            from chatgptrest.kernel.memory_manager import MemoryRecord, MemoryTier
            memory.stage_and_promote(MemoryRecord(
                category="report_result",
                key=f"report:{trace}",
                value={
                    "query": state.get("user_message", "")[:100],
                    "text_len": len(final_text),
                    "review_pass": review_pass,
                    "status": final_status,
                },
                confidence=0.8 if review_pass else 0.5,
                source={"type": "system", "agent": "report_graph", "task_id": trace},
            ), MemoryTier.EPISODIC, "report result")
        except Exception as e:
            logger.warning("Episodic memory record failed: %s", e)

    return {
        "route_result": {
            "stage": "report_complete",
            "final_status": final_status,
            "final_text": final_text or "",
            "draft_sections": result.get("draft_sections", []),
            "evidence_count": result.get("evidence_count", 0),
            "review_notes": review_notes,
            "review_pass": review_pass,
            "kb_writeback": kb_record,
            "workspace_delivery": workspace_delivery,
        },
        "route_status": final_status,
    }


def execute_funnel(state: AdvisorState) -> dict:
    """Execute funnel route: full pipeline with KB + EvoMap.

    Pipeline stages (all stages emit EvoMap signals):
    1. 需求分析: understand → rubric_a → analyze → rubric_b → finalize
    2. ProjectCard: finalize_funnel produces project_card + tasks
    3. 派发: AgentDispatcher.dispatch(ContextPackage)
    4. 入库: KB writeback + ArtifactRegistry registration
    """
    from chatgptrest.advisor.funnel_graph import build_funnel_graph
    from chatgptrest.advisor.dispatch import AgentDispatcher

    runtime = _svc(state)
    llm = state.get("llm_connector") or runtime.llm_connector or (lambda p, s="": f"[funnel: {p[:40]}]")
    trace_id = state.get("trace_id", "")

    def _emit(sig_type, source, domain=None, data=None):
        # Phase-1 fix: route through EventBus instead of direct observer call
        _emit_event(state, sig_type, source, data)

    # ── Stage 1+2: Funnel analysis → ProjectCard ──────────────
    _emit("route.selected", "advisor", "routing",
          {"route": "funnel", "intent": state.get("intent_top")})

    try:
        funnel_app = build_funnel_graph().compile()
        funnel_result = funnel_app.invoke({
            "user_message": state.get("user_message", ""),
            "trace_id": trace_id,
            "scenario_pack": dict(state.get("scenario_pack") or {}) if isinstance(state.get("scenario_pack"), dict) else {},
        })
    except Exception as e:
        logger.error("Funnel sub-graph failed: %s", e)
        funnel_result = {
            "status": "error",
            "problem_statement": state.get("user_message", "")[:200],
            "project_card": {},
            "tasks": [],
            "recommended_option": "",
            "gate_a_pass": None,
            "gate_b_pass": None,
        }

    funnel_status = funnel_result.get("status", "error")
    project_card = funnel_result.get("project_card", {})
    tasks = funnel_result.get("tasks", [])
    recommended = funnel_result.get("recommended_option", "")
    problem = funnel_result.get("problem_statement", "")

    _emit("funnel.stage_completed", "funnel", "funnel",
          {"status": funnel_status, "task_count": len(tasks)})

    # Record gates
    gate_a = funnel_result.get("gate_a_pass")
    gate_b = funnel_result.get("gate_b_pass")
    if gate_a is not None:
        _emit("gate.passed" if gate_a else "gate.failed", "funnel", "gate",
              {"gate": "A", "pass": gate_a})
    if gate_b is not None:
        _emit("gate.passed" if gate_b else "gate.failed", "funnel", "gate",
              {"gate": "B", "pass": gate_b})

    # Write quality scores back to Langfuse via ModelRouter (feedback loop)
    # (trace_id already assigned on L811)
    if trace_id:
        try:
            svc = _svc(state)
            mr = getattr(svc, "model_router", None)
            if mr is None:
                # Try from state
                mr = state.get("_model_router")
            if mr:
                overall_pass = (gate_a is None or gate_a) and (gate_b is None or gate_b)
                mr.write_quality_score(
                    trace_id=trace_id,
                    score=1.0 if overall_pass else 0.0,
                    comment=f"gate_a={'pass' if gate_a else 'fail'}, gate_b={'pass' if gate_b else 'fail'}",
                )
        except Exception:
            pass  # fail-open

    # ── Stage 3: Dispatch → Agent Teams ──────────────────────
    dispatch_result = None
    if funnel_status == "complete" and project_card:
        try:
            dispatcher = AgentDispatcher(outbox=runtime.outbox, llm_fn=llm)
            # Include tasks in project_card for dispatch
            card_with_tasks = dict(project_card)
            card_with_tasks["tasks"] = tasks
            funnel_with_tasks = dict(funnel_result)
            funnel_with_tasks["project_card"] = card_with_tasks
            ctx = dispatcher.build_context_package(
                funnel_with_tasks,
                trace_id=trace_id,
                advisor_rationale=state.get("route_rationale", ""),
            )
            dispatch_result = dispatcher.dispatch(ctx)
            _emit("dispatch.task_completed", "dispatch", "dispatch",
                  {"dispatch_status": dispatch_result.get("status")})
            logger.info("Dispatch result: %s", dispatch_result.get("status"))
        except Exception as e:
            logger.warning("Dispatch failed: %s", e)
            dispatch_result = {"status": "failed", "error": str(e)}
            _emit("dispatch.task_failed", "dispatch", "dispatch", {"error": str(e)})

    # ── Stage 4: KB Writeback + Registry ─────────────────────
    kb_record = None
    if funnel_status == "complete":
        trace = trace_id or "unknown"
        try:
            funnel_content = json.dumps({
                "trace_id": trace,
                "project_card": project_card,
                "tasks": tasks,
                "problem_statement": problem,
                "recommended_option": recommended,
                "dispatch_summary": _summarize_dispatch_for_kb(dispatch_result),
            }, ensure_ascii=False, indent=2)
            kb_record = _kb_writeback_and_record(
                state=state,
                content=funnel_content,
                artifact_name=f"funnel_{trace[:12]}",
                artifact_type="funnel",
                source_system="openmind_funnel",
                project_id=trace,
                para_bucket="project",
                structural_role="plan",
                extra_metadata={"stability": "draft", "quarantine": True, "source": "auto_funnel"},
                content_type="json",
                knowledge_plane="canonical_knowledge",
            )
        except Exception as e:
            logger.warning("KB writeback failed: %s", e)

    return {
        "route_result": {
            "stage": "funnel_complete",
            "status": funnel_status,
            "problem_statement": problem[:300] if problem else "",
            "recommended_option": recommended[:300] if recommended else "",
            "project_card": project_card,
            "tasks": tasks,
            "gate_a_pass": gate_a,
            "gate_b_pass": gate_b,
            "dispatch": dispatch_result,
            "kb_writeback": kb_record,
        },
        "route_status": funnel_status,
    }


# ── Route Router ──────────────────────────────────────────────────

def route_to_executor(state: AdvisorState) -> str:
    """Route to the appropriate execution node based on selected_route."""
    route = state.get("selected_route", "")

    if route == "kb_answer":
        return "execute_quick_ask"
    elif route == "deep_research":
        return "execute_deep_research"
    elif route in ("report", "write_report"):
        return "execute_report"
    elif route in ("funnel", "build_feature"):
        return "execute_funnel"
    elif route in ("clarify", "clarification"):
        return "execute_quick_ask"
    elif route == "action":
        return "execute_funnel"
    elif route == "hybrid":
        return "execute_quick_ask"
    else:
        # Default: quick_ask for unknown routes
        return "execute_quick_ask"


# ── Graph Builder ─────────────────────────────────────────────────

def build_advisor_graph() -> StateGraph:
    """Build the Advisor StateGraph with real route execution.

    Flow: normalize → kb_probe → analyze_intent → route_decision
          → [quick_ask | deep_research | report | funnel] → END

    Usage::

        graph = build_advisor_graph()
        app = graph.compile()
        result = app.invoke({"user_message": "帮我写个安徽项目进展报告"})
    """
    graph = StateGraph(AdvisorState)

    # Phase 1: Analysis nodes
    graph.add_node("normalize", normalize)
    graph.add_node("kb_probe", kb_probe)
    graph.add_node("analyze_intent", analyze_intent)
    graph.add_node("route_decision", route_decision)

    # Phase 2: Execution nodes (one per route)
    graph.add_node("execute_quick_ask", execute_quick_ask)
    graph.add_node("execute_deep_research", execute_deep_research)
    graph.add_node("execute_report", execute_report)
    graph.add_node("execute_funnel", execute_funnel)

    # Analysis edges (linear)
    graph.set_entry_point("normalize")
    graph.add_edge("normalize", "kb_probe")
    graph.add_edge("kb_probe", "analyze_intent")
    graph.add_edge("analyze_intent", "route_decision")

    # Conditional routing: route_decision → one of 4 execution nodes
    graph.add_conditional_edges("route_decision", route_to_executor)

    # All execution nodes → END
    graph.add_edge("execute_quick_ask", END)
    graph.add_edge("execute_deep_research", END)
    graph.add_edge("execute_report", END)
    graph.add_edge("execute_funnel", END)

    return graph
