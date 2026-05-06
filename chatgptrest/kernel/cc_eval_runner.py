"""CC Eval Runner — comprehensive evaluation for hcom→CC pipeline.

Drives data accumulation, A/B testing, and cross-dimensional analysis
across 4 complexity levels × 8 task types.

Usage::

    runner = CcEvalRunner(cc_executor)
    results = runner.run_batch(level="L1")        # run L1 only
    results = runner.run_batch()                    # run all
    ab      = runner.run_ab_test("code_review")     # A/B templates
    stats   = runner.get_stats()                    # accumulated data
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Extended Scenario Model ─────────────────────────────────────────

@dataclass
class EvalScenario:
    """A test scenario for CC pipeline evaluation."""
    name: str
    task_type: str
    complexity: str                                 # L1 / L2 / L3 / L4
    description: str
    files: list[str] = field(default_factory=list)
    expected_min_findings: int = 0
    expected_min_quality: float = 0.3
    golden_keywords: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)
    quality_weights: dict[str, float] = field(default_factory=dict)
    timeout: int = 300


# ── L1: Simple (single file, clear boundary) ───────────────────────

L1_SCENARIOS: list[EvalScenario] = [
    EvalScenario(
        name="idempotency_bug_hunt",
        task_type="code_review",
        complexity="L1",
        description=(
            "Review idempotency guard for race conditions: "
            "what happens if two identical requests arrive within 1ms? "
            "Check TTL expiration edge cases. Check dict thread safety."
        ),
        files=["chatgptrest/core/idempotency.py"],
        expected_min_findings=2,
        expected_min_quality=0.5,
        golden_keywords=["race condition", "thread", "TTL", "dict", "lock"],
        anti_patterns=["looks good", "no issues found"],
        timeout=180,
    ),
    EvalScenario(
        name="rate_limit_bypass",
        task_type="security_audit",
        complexity="L1",
        description=(
            "Audit rate limiter for bypass vectors: "
            "IP spoofing via X-Forwarded-For header injection, "
            "clock skew between checks, memory exhaustion via unique IPs, "
            "and integer overflow in counters."
        ),
        files=["chatgptrest/core/rate_limit.py"],
        expected_min_findings=3,
        expected_min_quality=0.5,
        golden_keywords=["X-Forwarded-For", "memory", "spoofing", "exhaustion"],
        anti_patterns=["OWASP compliant"],
        timeout=180,
    ),
    EvalScenario(
        name="state_machine_tests",
        task_type="test_generation",
        complexity="L1",
        description=(
            "Write comprehensive pytest tests for the state machine: "
            "cover all valid transitions, invalid transitions, "
            "edge cases (re-entry, terminal states), "
            "and concurrent state changes. Use parametrize."
        ),
        files=["chatgptrest/core/state_machine.py"],
        expected_min_findings=0,
        expected_min_quality=0.4,
        golden_keywords=["parametrize", "invalid", "terminal", "concurrent"],
        anti_patterns=["skip", "TODO"],
        timeout=240,
    ),
]

# ── L2: Medium (2-3 files, cross-module data flow) ──────────────────

L2_SCENARIOS: list[EvalScenario] = [
    EvalScenario(
        name="api_db_dataflow",
        task_type="code_review",
        complexity="L2",
        description=(
            "Trace the data flow from API request to database storage "
            "for issue creation. Check for: input validation gaps, "
            "SQL injection, missing error handling, data loss scenarios. "
            "Draw the call chain."
        ),
        files=[
            "chatgptrest/api/routes_issues.py",
            "chatgptrest/core/client_issues.py",
            "chatgptrest/core/db.py",
        ],
        expected_min_findings=3,
        expected_min_quality=0.5,
        golden_keywords=["validation", "injection", "transaction", "call chain"],
        anti_patterns=["single file"],
        timeout=240,
    ),
    EvalScenario(
        name="feishu_graph_bugfix",
        task_type="bug_fix",
        complexity="L2",
        description=(
            "The Feishu webhook handler calls the advisor graph but "
            "doesn't properly handle graph execution errors — "
            "LangGraph exceptions crash the webhook handler. "
            "Add error handling and return appropriate Feishu error card. "
            "Run tests after fixing."
        ),
        files=[
            "chatgptrest/advisor/feishu_handler.py",
            "chatgptrest/advisor/graph.py",
        ],
        expected_min_findings=1,
        expected_min_quality=0.5,
        golden_keywords=["try", "except", "error card", "Feishu"],
        anti_patterns=["pass"],
        timeout=240,
    ),
    EvalScenario(
        name="kb_llm_consistency",
        task_type="architecture_review",
        complexity="L2",
        description=(
            "Review the integration between KB retrieval and LLM answer "
            "generation. Check: are retrieved chunks always used? "
            "Can stale KB data cause hallucination? "
            "Is the relevance threshold appropriate? "
            "Draw a data flow diagram."
        ),
        files=[
            "chatgptrest/kb/kb_hub.py",
            "chatgptrest/advisor/graph.py",
        ],
        expected_min_findings=2,
        expected_min_quality=0.5,
        golden_keywords=["chunk", "relevance", "hallucination", "threshold"],
        anti_patterns=["looks fine"],
        timeout=240,
    ),
]

# ── L3: Complex (3-5 files, implicit dependencies) ──────────────────

L3_SCENARIOS: list[EvalScenario] = [
    EvalScenario(
        name="api_stack_security",
        task_type="security_audit",
        complexity="L3",
        description=(
            "End-to-end security audit of the API stack: "
            "CORS/middleware → authentication → rate limiting → "
            "write guards → request handling. "
            "Create an attack tree showing how an attacker could "
            "bypass each layer. Check for auth bypass, SSRF, "
            "path traversal, and header injection."
        ),
        files=[
            "chatgptrest/api/app.py",
            "chatgptrest/api/routes_advisor_v3.py",
            "chatgptrest/api/write_guards.py",
            "chatgptrest/api/client_ip.py",
            "chatgptrest/core/rate_limit.py",
        ],
        expected_min_findings=5,
        expected_min_quality=0.5,
        golden_keywords=["attack tree", "bypass", "CORS", "header", "layered"],
        anti_patterns=["secure enough"],
        timeout=300,
    ),
    EvalScenario(
        name="evomap_integration_tests",
        task_type="test_generation",
        complexity="L3",
        description=(
            "Write integration tests for the complete EvoMap signal flow: "
            "cc_executor emits signals → observer records → signals queryable. "
            "Mock hcom subprocess but test real signal propagation. "
            "Include negative tests: observer down, malformed signals, "
            "concurrent emission."
        ),
        files=[
            "chatgptrest/evomap/signals.py",
            "chatgptrest/kernel/cc_executor.py",
        ],
        expected_min_findings=0,
        expected_min_quality=0.4,
        golden_keywords=["mock", "integration", "negative", "concurrent", "propagation"],
        anti_patterns=["unit test only"],
        timeout=300,
    ),
    EvalScenario(
        name="service_registry_refactor",
        task_type="refactoring",
        complexity="L3",
        description=(
            "The service registry pattern (_ServiceRegistry) is duplicated "
            "across graph.py and routes_advisor_v3.py with tightly coupled "
            "initialization. Propose and implement a clean dependency injection "
            "pattern that: (1) eliminates the singleton, (2) makes testing easier, "
            "(3) preserves lazy initialization. Don't over-engineer."
        ),
        files=[
            "chatgptrest/advisor/graph.py",
            "chatgptrest/api/routes_advisor_v3.py",
            "chatgptrest/advisor/report_graph.py",
        ],
        expected_min_findings=2,
        expected_min_quality=0.5,
        golden_keywords=["injection", "singleton", "testable", "lazy", "backward"],
        anti_patterns=["framework", "Spring", "decorator hell"],
        timeout=300,
    ),
    EvalScenario(
        name="llm_retry_fallback",
        task_type="bug_fix",
        complexity="L3",
        description=(
            "The LLM connector has no retry logic. When a provider "
            "returns 429, the request fails immediately. Implement: "
            "(1) exponential backoff with jitter, "
            "(2) automatic fallback to next provider via model_router, "
            "(3) circuit breaker for consistently failing providers. "
            "Ensure thread safety."
        ),
        files=[
            "chatgptrest/kernel/llm_connector.py",
            "chatgptrest/kernel/model_router.py",
            "chatgptrest/kernel/mcp_llm_bridge.py",
        ],
        expected_min_findings=2,
        expected_min_quality=0.5,
        golden_keywords=["backoff", "jitter", "circuit breaker", "fallback", "429"],
        anti_patterns=["retry storm", "infinite loop"],
        timeout=300,
    ),
]

# ── L4: Hard (cross-subsystem, ambiguous requirements) ──────────────

L4_SCENARIOS: list[EvalScenario] = [
    EvalScenario(
        name="observability_gap_analysis",
        task_type="architecture_review",
        complexity="L4",
        description=(
            "Analyze the complete observability stack "
            "(Langfuse traces + EvoMap signals + Python logging). "
            "Identify: blind spots (what failures are invisible?), "
            "correlation gaps (can you trace a user request from "
            "API → graph → LLM → response?), "
            "and alert-worthy conditions with no monitoring. "
            "Propose an end-to-end trace ID correlation scheme."
        ),
        files=[
            "chatgptrest/observability/__init__.py",
            "chatgptrest/evomap/signals.py",
            "chatgptrest/kernel/cc_executor.py",
            "chatgptrest/advisor/graph.py",
            "chatgptrest/api/routes_advisor_v3.py",
        ],
        expected_min_findings=5,
        expected_min_quality=0.5,
        golden_keywords=["blind spot", "trace ID", "correlation", "alert", "invisible"],
        anti_patterns=["observability is good"],
        timeout=360,
    ),
    EvalScenario(
        name="multiturn_memory_impl",
        task_type="feature_impl",
        complexity="L4",
        description=(
            "The current advisor is stateless per request. "
            "Implement multi-turn conversation memory: "
            "(1) session ID tracking, "
            "(2) conversation history in-memory storage, "
            "(3) context window management (last N turns), "
            "(4) API changes to accept session_id parameter. "
            "Keep it simple — no external database. "
            "Consider memory limits and session expiration."
        ),
        files=[
            "chatgptrest/advisor/graph.py",
            "chatgptrest/api/routes_advisor_v3.py",
        ],
        expected_min_findings=0,
        expected_min_quality=0.4,
        golden_keywords=["session", "history", "context window", "expiration", "memory limit"],
        anti_patterns=["database", "Redis", "over-engineer"],
        timeout=360,
    ),
    EvalScenario(
        name="e2e_performance_audit",
        task_type="performance",
        complexity="L4",
        description=(
            "A typical advisor request takes 8-15 seconds. "
            "Profile the hot path and identify optimization opportunities: "
            "unnecessary serialization, synchronous waits that could be async, "
            "KB retrieval that could be cached, "
            "LLM prompts that are too verbose. "
            "Quantify each optimization's expected impact."
        ),
        files=[
            "chatgptrest/api/routes_advisor_v3.py",
            "chatgptrest/advisor/graph.py",
            "chatgptrest/kernel/llm_connector.py",
            "chatgptrest/kb/kb_hub.py",
        ],
        expected_min_findings=3,
        expected_min_quality=0.4,
        golden_keywords=["latency", "async", "cache", "serialize", "before/after"],
        anti_patterns=["premature optimization"],
        timeout=360,
    ),
    EvalScenario(
        name="chaos_fault_injection",
        task_type="test_generation",
        complexity="L4",
        description=(
            "Design and implement chaos engineering tests for 5 fault scenarios: "
            "(1) LLM provider returns garbage/empty, "
            "(2) KB search returns zero results, "
            "(3) hcom daemon is dead, "
            "(4) Langfuse is unreachable, "
            "(5) memory/state is corrupted. "
            "For each: define expected behavior, test actual behavior, "
            "fix any crash paths found."
        ),
        files=[
            "chatgptrest/kernel/llm_connector.py",
            "chatgptrest/kernel/model_router.py",
            "chatgptrest/advisor/graph.py",
            "chatgptrest/api/routes_advisor_v3.py",
        ],
        expected_min_findings=3,
        expected_min_quality=0.4,
        golden_keywords=["chaos", "fault", "graceful", "fallback", "silent failure"],
        anti_patterns=["happy path only"],
        timeout=360,
    ),
]

# ── All scenarios combined with level lookup ────────────────────────

ALL_SCENARIOS: list[EvalScenario] = L1_SCENARIOS + L2_SCENARIOS + L3_SCENARIOS + L4_SCENARIOS

SCENARIOS_BY_LEVEL: dict[str, list[EvalScenario]] = {
    "L1": L1_SCENARIOS,
    "L2": L2_SCENARIOS,
    "L3": L3_SCENARIOS,
    "L4": L4_SCENARIOS,
}


# ── A/B Test Result ─────────────────────────────────────────────────

@dataclass
class AbTestResult:
    """Result of an A/B test comparing templates."""
    task_type: str
    scenario: str
    variants: list[dict[str, Any]] = field(default_factory=list)
    winner: str = ""
    confidence: float = 0.0


# ── Enhanced Quality Scorer ─────────────────────────────────────────

def score_output(
    output: str,
    scenario: EvalScenario,
    elapsed: float,
    findings_count: int,
) -> dict[str, float]:
    """Score output across 5 quality dimensions.

    Returns dict with per-dimension scores and weighted total.
    """
    text_lower = output.lower()
    total_words = max(len(output.split()), 1)

    # 1. Correctness (0-1): structural validity
    correctness = 0.0
    if len(output.strip()) > 100:
        correctness += 0.3
    if findings_count > 0 or scenario.task_type in ("test_generation", "feature_impl"):
        correctness += 0.3
    # No anti-patterns present?
    anti_hits = sum(1 for ap in scenario.anti_patterns if ap.lower() in text_lower)
    if anti_hits == 0:
        correctness += 0.4
    else:
        correctness += max(0.0, 0.4 - anti_hits * 0.15)
    correctness = min(1.0, correctness)

    # 2. Completeness (0-1): golden keyword coverage
    if scenario.golden_keywords:
        covered = sum(1 for kw in scenario.golden_keywords if kw.lower() in text_lower)
        completeness = covered / len(scenario.golden_keywords)
    else:
        completeness = 0.5 if len(output) > 500 else 0.2

    # 3. Depth (0-1): analysis depth indicators
    depth_keywords = [
        "because", "root cause", "underlying", "design", "architecture",
        "trade-off", "risk", "impact", "consequences", "根因", "深层", "权衡",
    ]
    depth_hits = sum(1 for dk in depth_keywords if dk.lower() in text_lower)
    depth = min(1.0, depth_hits * 0.12)

    # 4. Actionability (0-1): specific, implementable suggestions
    action_keywords = [
        "fix:", "suggestion:", "recommend", "should", "change to",
        "replace with", "add", "remove", "```", "diff", "建议", "修复",
    ]
    action_hits = sum(1 for ak in action_keywords if ak.lower() in text_lower)
    actionability = min(1.0, action_hits * 0.1)

    # 5. Efficiency (0-1): normalized elapsed time
    efficiency = max(0.0, 1.0 - elapsed / max(scenario.timeout, 1))

    # Weighted total
    weights = scenario.quality_weights or {
        "correctness": 0.3,
        "completeness": 0.2,
        "depth": 0.2,
        "actionability": 0.2,
        "efficiency": 0.1,
    }
    total = sum(
        scores.get(dim, 0.0) * w
        for dim, w in weights.items()
        if (scores := {
            "correctness": correctness,
            "completeness": completeness,
            "depth": depth,
            "actionability": actionability,
            "efficiency": efficiency,
        })
    )

    return {
        "correctness": round(correctness, 3),
        "completeness": round(completeness, 3),
        "depth": round(depth, 3),
        "actionability": round(actionability, 3),
        "efficiency": round(efficiency, 3),
        "total": round(total, 3),
        "golden_coverage": round(completeness, 3),
        "anti_pattern_hits": anti_hits,
    }


# ── Eval Runner ─────────────────────────────────────────────────────

class CcEvalRunner:
    """Comprehensive CC pipeline evaluation runner.

    Supports phased execution by complexity level,
    A/B template testing, and cross-dimensional analysis.
    """

    def __init__(self, cc_executor) -> None:
        self._cc = cc_executor
        self._results: list[dict[str, Any]] = []
        self._ab_results: list[AbTestResult] = []
        self._lock = threading.Lock()

    # ── Batch Evaluation ────────────────────────────────────────

    def run_batch(
        self,
        scenarios: list[EvalScenario] | None = None,
        level: str | None = None,
        agents: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Run scenarios, accumulating EvoMap signals.

        Args:
            scenarios: Custom scenarios (default: ALL_SCENARIOS)
            level: Filter by complexity level (L1/L2/L3/L4)
            agents: Force specific agents (default: auto-select)
        """
        if scenarios is None:
            if level and level in SCENARIOS_BY_LEVEL:
                scenarios = SCENARIOS_BY_LEVEL[level]
            else:
                scenarios = ALL_SCENARIOS

        available = agents or self._cc._get_available_agents()
        if not available:
            logger.error("CcEvalRunner: no CC agents available")
            return [{"error": "no agents available"}]

        results = []
        for i, scenario in enumerate(scenarios):
            agent = available[i % len(available)] if agents else None

            logger.info(
                "CcEvalRunner: [%d/%d] %s (%s/%s) → %s",
                i + 1, len(scenarios), scenario.name,
                scenario.complexity, scenario.task_type,
                agent or "auto",
            )

            from chatgptrest.kernel.cc_executor import CcTask
            task = CcTask(
                task_type=scenario.task_type,
                description=scenario.description,
                files=scenario.files,
                timeout=scenario.timeout,
            )

            result = self._cc.dispatch(task, agent=agent)

            # Enhanced quality scoring
            quality_detail = score_output(
                result.output or "",
                scenario,
                result.elapsed_seconds,
                result.findings_count,
            )

            passed = (
                result.ok
                and result.findings_count >= scenario.expected_min_findings
                and quality_detail["total"] >= scenario.expected_min_quality
            )

            entry = {
                "scenario": scenario.name,
                "complexity": scenario.complexity,
                "task_type": scenario.task_type,
                "agent": result.agent,
                "passed": passed,
                "ok": result.ok,
                "quality_score": result.quality_score,
                "quality_detail": quality_detail,
                "findings_count": result.findings_count,
                "files_modified": result.files_modified,
                "elapsed_seconds": result.elapsed_seconds,
                "template_used": result.template_used,
                "error": result.error,
                "trace_id": result.trace_id,
                "golden_coverage": quality_detail.get("golden_coverage", 0),
                "anti_pattern_hits": quality_detail.get("anti_pattern_hits", 0),
            }
            results.append(entry)

            with self._lock:
                self._results.append(entry)

            if i < len(scenarios) - 1:
                time.sleep(2)

        return results

    # ── A/B Testing ─────────────────────────────────────────────

    def run_ab_test(
        self,
        task_type: str,
        description: str = "",
        files: list[str] | None = None,
        agents: list[str] | None = None,
    ) -> AbTestResult:
        """A/B test all templates for a task type."""
        templates = self._cc._templates.get(task_type, {})
        if not templates:
            return AbTestResult(task_type=task_type, scenario="no_templates")

        available = agents or self._cc._get_available_agents()
        if not available:
            return AbTestResult(task_type=task_type, scenario="no_agents")

        if not description:
            description = f"A/B test for {task_type}"

        ab = AbTestResult(task_type=task_type, scenario=description)

        for i, template_name in enumerate(templates):
            agent = available[i % len(available)]

            from chatgptrest.kernel.cc_executor import CcTask
            task = CcTask(
                task_type=task_type,
                description=description,
                files=files or [],
                timeout=300,
            )

            result = self._cc.dispatch(task, agent=agent, template=template_name)

            ab.variants.append({
                "template": template_name,
                "agent": agent,
                "quality_score": result.quality_score,
                "findings_count": result.findings_count,
                "elapsed_seconds": result.elapsed_seconds,
                "ok": result.ok,
                "output_preview": result.output[:200] if result.output else "",
            })

            if i < len(templates) - 1:
                time.sleep(3)

        if ab.variants:
            best = max(ab.variants, key=lambda v: v["quality_score"])
            worst = min(ab.variants, key=lambda v: v["quality_score"])
            ab.winner = best["template"]
            delta = best["quality_score"] - worst["quality_score"]
            ab.confidence = min(1.0, delta * 5)

        self._cc._emit("ab_test.completed", "", {
            "task_type": task_type,
            "winner": ab.winner,
            "confidence": ab.confidence,
            "variants": len(ab.variants),
        })

        with self._lock:
            self._ab_results.append(ab)

        return ab

    # ── Stats & Analysis ────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get accumulated evaluation statistics with cross-dimensional analysis."""
        with self._lock:
            results = list(self._results)

        if not results:
            return {"total": 0, "message": "No evaluations yet"}

        # Per-agent stats
        agent_stats: dict[str, dict] = {}
        for r in results:
            agent = r.get("agent", "")
            if not agent:
                continue
            s = agent_stats.setdefault(agent, {
                "total": 0, "passed": 0, "total_quality": 0.0,
                "total_findings": 0, "total_elapsed": 0.0,
                "by_complexity": {},
            })
            s["total"] += 1
            if r.get("passed"):
                s["passed"] += 1
            s["total_quality"] += r.get("quality_score", 0)
            s["total_findings"] += r.get("findings_count", 0)
            s["total_elapsed"] += r.get("elapsed_seconds", 0)
            # Per-complexity breakdown
            cx = r.get("complexity", "")
            if cx:
                cx_s = s["by_complexity"].setdefault(cx, {"total": 0, "passed": 0})
                cx_s["total"] += 1
                if r.get("passed"):
                    cx_s["passed"] += 1

        for name, s in agent_stats.items():
            n = max(s["total"], 1)
            s["pass_rate"] = round(s["passed"] / n, 2)
            s["avg_quality"] = round(s["total_quality"] / n, 3)
            s["avg_findings"] = round(s["total_findings"] / n, 1)
            s["avg_elapsed"] = round(s["total_elapsed"] / n, 1)

        # Per-complexity stats
        complexity_stats: dict[str, dict] = {}
        for r in results:
            cx = r.get("complexity", "")
            if not cx:
                continue
            s = complexity_stats.setdefault(cx, {
                "total": 0, "passed": 0, "total_quality": 0.0,
            })
            s["total"] += 1
            if r.get("passed"):
                s["passed"] += 1
            s["total_quality"] += r.get("quality_score", 0)

        for cx, s in complexity_stats.items():
            n = max(s["total"], 1)
            s["pass_rate"] = round(s["passed"] / n, 2)
            s["avg_quality"] = round(s["total_quality"] / n, 3)

        # Per-task-type stats
        task_stats: dict[str, dict] = {}
        for r in results:
            tt = r.get("task_type", "")
            if not tt:
                continue
            s = task_stats.setdefault(tt, {
                "total": 0, "passed": 0, "total_quality": 0.0,
            })
            s["total"] += 1
            if r.get("passed"):
                s["passed"] += 1
            s["total_quality"] += r.get("quality_score", 0)

        for name, s in task_stats.items():
            n = max(s["total"], 1)
            s["pass_rate"] = round(s["passed"] / n, 2)
            s["avg_quality"] = round(s["total_quality"] / n, 3)

        # Template stats
        template_stats: dict[str, dict] = {}
        for r in results:
            tmpl = r.get("template_used", "")
            if not tmpl:
                continue
            s = template_stats.setdefault(tmpl, {
                "total": 0, "total_quality": 0.0, "total_findings": 0,
            })
            s["total"] += 1
            s["total_quality"] += r.get("quality_score", 0)
            s["total_findings"] += r.get("findings_count", 0)

        for name, s in template_stats.items():
            n = max(s["total"], 1)
            s["avg_quality"] = round(s["total_quality"] / n, 3)
            s["avg_findings"] = round(s["total_findings"] / n, 1)

        return {
            "total": len(results),
            "overall_pass_rate": round(
                sum(1 for r in results if r.get("passed")) / len(results), 2
            ),
            "agents": agent_stats,
            "complexity": complexity_stats,
            "task_types": task_stats,
            "templates": template_stats,
            "ab_tests": len(self._ab_results),
            "ab_winners": {
                ab.task_type: ab.winner
                for ab in self._ab_results if ab.winner
            },
        }
