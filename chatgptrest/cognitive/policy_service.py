from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from chatgptrest.advisor import compute_all_scores, select_route
from chatgptrest.advisor.runtime import AdvisorRuntime
from chatgptrest.cognitive.context_service import ContextResolveOptions, ContextResolver
from chatgptrest.contracts.schemas import IntentSignals, KBProbeResult, Route
from chatgptrest.kernel.policy_engine import QualityContext


_FILLER_PATTERN = re.compile(
    r"(?:那个|就是说?|嗯+|啊+|这个|然后呢?|所以说?|对吧?|你看|怎么说呢)\s*",
    re.UNICODE,
)


@dataclass
class PolicyHintsOptions:
    query: str
    session_id: str = ""
    account_id: str = ""
    agent_id: str = ""
    role_id: str = ""
    thread_id: str = ""
    trace_id: str = ""
    token_budget: int = 1800
    graph_scopes: tuple[str, ...] = ("personal",)
    repo: str = ""
    audience: str = "internal"
    security_label: str = "internal"
    risk_level: str = "low"
    estimated_tokens: int = 0
    urgency_hint: str = "whenever"


@dataclass
class PolicyHintsResult:
    ok: bool
    trace_id: str
    preferred_route: str
    route_rationale: str
    retrieval_plan: list[str]
    hints: list[str]
    quality_gate: dict[str, Any]
    execution_summary: dict[str, Any]
    degraded_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "trace_id": self.trace_id,
            "preferred_route": self.preferred_route,
            "route_rationale": self.route_rationale,
            "retrieval_plan": list(self.retrieval_plan),
            "hints": list(self.hints),
            "quality_gate": self.quality_gate,
            "execution_summary": self.execution_summary,
            "degraded_sources": list(self.degraded_sources),
        }


class PolicyHintsService:
    """Pure, hot-path-safe policy hints for an execution shell."""

    def __init__(self, runtime: AdvisorRuntime):
        self._runtime = runtime

    def resolve(self, options: PolicyHintsOptions) -> PolicyHintsResult:
        trace_id = options.trace_id or str(uuid.uuid4())

        context_result = ContextResolver(self._runtime).resolve(
            ContextResolveOptions(
                query=options.query,
                session_id=options.session_id,
                account_id=options.account_id,
                agent_id=options.agent_id,
                role_id=options.role_id,
                thread_id=options.thread_id,
                trace_id=trace_id,
                token_budget=options.token_budget,
                sources=("memory", "knowledge", "graph", "policy"),
                graph_scopes=options.graph_scopes,
                repo=options.repo,
            )
        )

        normalized = self._normalize_query(options.query)
        intent = self._analyze_intent(normalized)
        probe = self._probe_kb(normalized)
        scores = compute_all_scores(
            intent=intent,
            kb_probe=probe,
            urgency_hint=options.urgency_hint,
        )
        decision = select_route(intent, scores)
        route = self._apply_intent_override(intent.intent_top, decision.route)

        quality_gate = {}
        if self._runtime.policy_engine is not None:
            quality_gate = self._runtime.policy_engine.run_quality_gate(
                QualityContext(
                    audience=options.audience,
                    security_label=options.security_label,
                    content=options.query,
                    estimated_tokens=options.estimated_tokens or max(1, len(options.query) // 4),
                    channel="policy.hints",
                    risk_level=options.risk_level,
                    execution_success=True,
                    business_success=True,
                    claims=[],
                )
            ).to_dict()

        execution_summary = self._summarize_execution_feedback(session_id=options.session_id)
        hints = self._extract_hints(context_result)
        hints.extend(self._feedback_hints(execution_summary))
        hints.append(f"Preferred route: {route}.")
        if options.repo:
            hints.append("Repository-scoped work should call /v2/graph/query before synthesis.")
        if route in {"report", Route.DEEP_RESEARCH.value, "funnel"}:
            hints.append("Escalate to /v2/advisor/ask only when slow-path cognition is worth the added latency.")

        retrieval_plan: list[str] = []
        if probe.answerability > 0.0:
            retrieval_plan.append("Use KB evidence first.")
        if "graph" in context_result.resolved_sources:
            retrieval_plan.append("Use personal graph atoms for structured recall.")
        if options.repo and "repo" in options.graph_scopes:
            retrieval_plan.append("Use repo_graph via /v2/graph/query.")
        if route in {"report", Route.DEEP_RESEARCH.value, "funnel"}:
            retrieval_plan.append("Escalate to /v2/advisor/ask for slow-path cognition.")

        return PolicyHintsResult(
            ok=True,
            trace_id=trace_id,
            preferred_route=route,
            route_rationale=decision.rationale,
            retrieval_plan=list(dict.fromkeys(retrieval_plan)),
            hints=list(dict.fromkeys(hints)),
            quality_gate=quality_gate,
            execution_summary=execution_summary,
            degraded_sources=context_result.degraded_sources,
        )

    def _normalize_query(self, query: str) -> str:
        cleaned = _FILLER_PATTERN.sub("", query)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or query

    def _probe_kb(self, query: str) -> KBProbeResult:
        hub = self._runtime.kb_hub
        if hub is None or not query:
            return KBProbeResult(answerability=0.0, top_chunks=[])
        try:
            hits = hub.search(query, top_k=5, auto_embed=False)
        except TypeError:
            hits = hub.search(query, top_k=5)
        except Exception:
            hits = []

        top_chunks = [
            {
                "artifact_id": hit.artifact_id,
                "title": hit.title,
                "snippet": hit.snippet[:200],
                "score": hit.score,
            }
            for hit in hits
        ]
        answerability = min(0.3 + 0.15 * len(hits), 1.0) if hits else 0.0
        return KBProbeResult(answerability=answerability, top_chunks=top_chunks)

    def _analyze_intent(self, query: str) -> IntentSignals:
        msg_lower = query.lower()

        write_signals = [
            "报告", "总结", "汇报", "介绍", "概述", "综述", "摘要",
            "write", "overview", "introduction", "summary", "report",
        ]
        research_signals = [
            "调研", "研究", "research", "investigate", "审查", "review", "分析", "对比",
        ]
        build_signals = [
            "开发", "实现", "功能", "设计", "架构", "部署",
            "build", "implement", "feature", "design",
        ]
        action_verbs = [
            "放在", "保存到", "上传", "发送到", "发给", "部署到", "写入", "导出", "同步到",
            "drive", "notion", "github", "gitlab",
        ]
        multi_markers = ["和", "并且", "然后", "同时", "以及", "另外", "还要"]

        scores = {"WRITE_REPORT": 0, "DO_RESEARCH": 0, "BUILD_FEATURE": 0}
        for token in write_signals:
            if token in msg_lower:
                scores["WRITE_REPORT"] += 1
        for token in research_signals:
            if token in msg_lower:
                scores["DO_RESEARCH"] += 1
        for token in build_signals:
            if token in msg_lower:
                scores["BUILD_FEATURE"] += 1

        imperative = re.search(
            r"(?:^|[，。；\n])\s*(?:请|帮我|帮忙|把|给我|please|go ahead|make|do)\s*\S",
            query,
            re.IGNORECASE | re.UNICODE,
        )
        if imperative and scores["WRITE_REPORT"] == 0:
            scores["BUILD_FEATURE"] += 2

        intent_top = max(scores, key=scores.get) if any(scores.values()) else "QUICK_QUESTION"
        confidence = min(0.7 + 0.05 * scores.get(intent_top, 0), 0.95) if intent_top != "QUICK_QUESTION" else 0.7
        action_required = any(token in msg_lower for token in action_verbs)
        multi_intent = any(token in query for token in multi_markers) or " and " in msg_lower
        constraint_count = 0
        if re.search(r"\d+\s*字", query) or re.search(r"\d+.?word", msg_lower):
            constraint_count += 1
        if any(token in msg_lower for token in ["格式", "format", "markdown", "pdf", "json"]):
            constraint_count += 1
        if any(token in msg_lower for token in ["中文", "英文", "双语", "english", "chinese"]):
            constraint_count += 1

        step_count = 1
        if action_required:
            step_count += 1
        if multi_intent:
            step_count += 1
        if constraint_count:
            step_count += 1

        return IntentSignals(
            intent_top=intent_top,
            intent_confidence=confidence,
            multi_intent=multi_intent,
            step_count_est=min(step_count, 10),
            constraint_count=constraint_count,
            open_endedness=0.3,
            verification_need=any(token in msg_lower for token in ["验证", "核验", "verify", "correctness"]),
            action_required=action_required,
        )

    def _extract_hints(self, context_result: Any) -> list[str]:
        hints: list[str] = []
        for block in context_result.context_blocks:
            if block.kind != "policy":
                continue
            for line in block.text.splitlines():
                line = line.strip()
                if line.startswith("- "):
                    hints.append(line[2:].strip())
                elif line:
                    hints.append(line)
        return hints

    def _summarize_execution_feedback(self, *, session_id: str) -> dict[str, Any]:
        observer = getattr(self._runtime, "observer", None)
        if observer is None:
            return {
                "recent_signal_count": 0,
                "tool_failures": {},
                "tool_successes": {},
                "negative_feedback_count": 0,
                "delivery_failures": 0,
            }

        signals = observer.query(limit=200)
        if session_id:
            filtered = []
            for signal in signals:
                data = dict(signal.data or {})
                if str(data.get("session_id") or "") == session_id:
                    filtered.append(signal)
            signals = filtered

        tool_failures: dict[str, int] = {}
        tool_successes: dict[str, int] = {}
        negative_feedback_count = 0
        delivery_failures = 0
        for signal in signals:
            data = dict(signal.data or {})
            tool_name = str(data.get("tool") or data.get("tool_name") or "").strip()
            if signal.signal_type in {"tool.failed", "tool.failure"} and tool_name:
                tool_failures[tool_name] = tool_failures.get(tool_name, 0) + 1
            if signal.signal_type == "tool.completed" and tool_name:
                tool_successes[tool_name] = tool_successes.get(tool_name, 0) + 1
            if signal.signal_type == "user.feedback" and str(data.get("rating") or "").lower() in {
                "negative",
                "thumbs_down",
                "reject",
            }:
                negative_feedback_count += 1
            if signal.signal_type in {"delivery.failed", "message.failed"}:
                delivery_failures += 1

        return {
            "recent_signal_count": len(signals),
            "tool_failures": tool_failures,
            "tool_successes": tool_successes,
            "negative_feedback_count": negative_feedback_count,
            "delivery_failures": delivery_failures,
        }

    def _feedback_hints(self, summary: dict[str, Any]) -> list[str]:
        hints: list[str] = []
        tool_failures = dict(summary.get("tool_failures") or {})
        tool_successes = dict(summary.get("tool_successes") or {})
        if tool_failures:
            ranked_failures = sorted(tool_failures.items(), key=lambda item: (-item[1], item[0]))[:3]
            failures_text = ", ".join(f"{name} x{count}" for name, count in ranked_failures)
            hints.append(f"Recent execution failures observed for: {failures_text}.")
        if tool_successes:
            ranked_successes = sorted(tool_successes.items(), key=lambda item: (-item[1], item[0]))[:3]
            successes_text = ", ".join(f"{name} x{count}" for name, count in ranked_successes)
            hints.append(f"Recent successful tool paths include: {successes_text}.")
        if int(summary.get("negative_feedback_count") or 0) > 0:
            hints.append("Recent negative user feedback was observed; prefer explicit verification before final delivery.")
        if int(summary.get("delivery_failures") or 0) > 0:
            hints.append("Recent delivery failures were observed; keep execution plans idempotent and retry-safe.")
        return hints

    def _apply_intent_override(self, intent_top: str, route: str) -> str:
        if intent_top == "WRITE_REPORT" and route != "report":
            return "report"
        if intent_top == "DO_RESEARCH" and route != Route.DEEP_RESEARCH.value:
            return Route.DEEP_RESEARCH.value
        if intent_top == "BUILD_FEATURE" and route != "funnel":
            return "funnel"
        return route
