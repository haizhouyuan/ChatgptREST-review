"""Funnel Graph — 3-stage LangGraph subgraph for project planning.

Flow: understand → rubric_a → analyze → rubric_b → finalize → output_card

The original 9-stage funnel is compressed to 3 stages, each using
CoT + Extraction pattern (2 LLM calls per stage):
  - Understand: Capture + Triage + Explore → intent clarity
  - Analyze: Frame + Optionize + Evaluate → options assessment
  - Finalize: Validate + Freeze + Execute/Learn → ProjectCard

Rubric gates between stages:
  - Gate A (after understand): auto-pass if clarity >= threshold
  - Gate B (after analyze): human confirmation required (interrupt_before)
  - Gate C (reject): if rubric fails fatally
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Callable, TypedDict

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


def _get_llm(state):
    """Get LLM connector: prefer state-injected (for tests), fallback to ServiceRegistry."""
    llm = state.get("llm_connector")
    if llm:
        return llm
    try:
        from chatgptrest.advisor.graph import _svc
        svc = _svc(state)
        if svc and svc.llm_connector:
            return svc.llm_connector
    except Exception:
        pass
    return _noop_llm


def _get_gate_a_threshold() -> float:
    """Read the current Gate A threshold from EvoMap tuning when available."""
    try:
        from chatgptrest.advisor.graph import _svc

        tuner = getattr(_svc(), "gate_tuner", None)
        if tuner and hasattr(tuner, "get_threshold"):
            threshold = float(tuner.get_threshold())
            return max(0.0, min(1.0, threshold))
    except Exception:
        pass
    return 0.6

# LLM connector type
LLMConnector = Callable[[str, str], str]


def _noop_llm(prompt: str, system_msg: str = "") -> str:
    return f"[mock: {prompt[:40]}...]"


# ── State ─────────────────────────────────────────────────────────

class FunnelState(TypedDict, total=False):
    """State for the 3-stage Funnel Graph."""
    # Input
    user_message: str
    trace_id: str
    urgency: str
    scenario_pack: dict[str, Any]

    # Stage 1: Understand
    intent_clarity: float        # 0-1
    problem_statement: str
    constraints: list[str]
    stakeholders: list[str]

    # Gate A result
    gate_a_pass: bool
    gate_a_reason: str

    # Stage 2: Analyze
    options: list[dict[str, Any]]   # [{name, pros, cons, score}]
    recommended_option: str
    risk_assessment: str

    # Gate B result
    gate_b_pass: bool
    gate_b_reason: str

    # Stage 3: Finalize
    tasks: list[dict[str, Any]]     # [{title, assignee, deadline, acceptance}]
    project_card: dict[str, Any]    # final ProjectCard
    evidence_refs: list[str]

    # Status
    status: str                     # "in_progress" | "complete" | "rejected"
    rejection_reason: str

    # Config
    llm_connector: Any


# ── Rubric Scoring ────────────────────────────────────────────────

class RubricDimension:
    """6 dimensions for rubric evaluation."""
    CLARITY = "clarity"
    FEASIBILITY = "feasibility"
    EVIDENCE = "evidence"
    RISK = "risk"
    ALIGNMENT = "alignment"
    COMPLETENESS = "completeness"


def compute_rubric(scores: dict[str, float]) -> tuple[float, bool]:
    """Compute aggregate rubric score. Returns (score, pass)."""
    if not scores:
        return 0.0, False
    avg = sum(scores.values()) / len(scores)
    return round(avg, 2), avg >= 0.6


# ── Nodes ─────────────────────────────────────────────────────────

def understand(state: FunnelState) -> dict:
    """Stage 1: Understand — Capture + Triage + Explore.

    CoT: Break down the requirement into problem statement, constraints,
    stakeholders.
    Extract: {intent_clarity, problem_statement, constraints, stakeholders}
    """
    llm = _get_llm(state)
    msg = state.get("user_message", "")
    profile = _planning_profile(state)
    profile_hint = _profile_prompt_hint(profile)

    cot_prompt = (
        f"分析以下需求:\n{msg}\n\n"
        f"{profile_hint}"
        "请按以下格式回答（每项1-2句）:\n"
        "核心问题: ...\n"
        "约束条件: ...（逗号分隔）\n"
        "利益相关者: ...（逗号分隔）\n"
        "需求清晰度: 高/中/低"
    )
    cot_response = llm(cot_prompt, "你是一个需求分析专家。按要求的格式回答。")

    # Parse structured fields from LLM response
    problem = cot_response[:500] if cot_response else (msg[:200] if msg else "TBD")

    # Extract clarity from response (S2-3.3: match on the 清晰度 line only)
    clarity = 0.5  # default: medium
    clarity_line = ""
    for _line in (cot_response or "").split("\n"):
        if "清晰" in _line and (":" in _line or "：" in _line):
            clarity_line = _line
            break
    if clarity_line:
        # Match the value part after the colon
        if re.search(r"高", clarity_line):
            clarity = 0.9
        elif re.search(r"低|模糊", clarity_line):
            clarity = 0.4
        elif re.search(r"中", clarity_line):
            clarity = 0.7
    else:
        # Fallback: scan full response for explicit keywords
        if "需求清晰度高" in (cot_response or "") or "非常清晰" in (cot_response or ""):
            clarity = 0.9
        elif "需求模糊" in (cot_response or "") or "需求不清晰" in (cot_response or ""):
            clarity = 0.4

    # Extract constraints from response
    constraints = []
    for line in cot_response.split("\n"):
        if "约束" in line or "条件" in line:
            parts = line.split(":", 1)
            if len(parts) > 1:
                constraints = [c.strip() for c in parts[1].split("，") if c.strip()]
                if not constraints:
                    constraints = [c.strip() for c in parts[1].split(",") if c.strip()]
            break
    if not constraints:
        constraints = ["待明确"]

    # Extract stakeholders
    stakeholders = []
    for line in cot_response.split("\n"):
        if "相关者" in line or "利益" in line:
            parts = line.split(":", 1)
            if len(parts) > 1:
                stakeholders = [s.strip() for s in parts[1].split("，") if s.strip()]
                if not stakeholders:
                    stakeholders = [s.strip() for s in parts[1].split(",") if s.strip()]
            break
    if not stakeholders:
        stakeholders = ["待明确"]

    return {
        "intent_clarity": clarity,
        "problem_statement": problem,
        "constraints": constraints,
        "stakeholders": stakeholders,
        "trace_id": state.get("trace_id") or str(uuid.uuid4()),
    }


def rubric_a(state: FunnelState) -> dict:
    """Gate A: Auto-pass if clarity threshold met."""
    clarity = state.get("intent_clarity", 0.0)
    threshold = _get_gate_a_threshold() + _funnel_profile_gate_a_delta(_funnel_profile(state))

    rubric_scores = {
        RubricDimension.CLARITY: clarity,
        RubricDimension.COMPLETENESS: 0.7 if state.get("constraints") else 0.3,
    }
    score, _ = compute_rubric(rubric_scores)
    passed = score >= threshold

    if passed:
        return {"gate_a_pass": True, "gate_a_reason": f"score={score:.2f} >= {threshold:.2f}"}
    return {
        "gate_a_pass": False,
        "gate_a_reason": f"score={score:.2f} < {threshold:.2f}",
        "status": "rejected",
        "rejection_reason": f"Gate A failed: rubric score {score}",
    }


def analyze(state: FunnelState) -> dict:
    """Stage 2: Analyze — Frame + Optionize + Evaluate.

    CoT: Generate options, score each.
    Extract: {options, recommended_option, risk_assessment}
    """
    if not state.get("gate_a_pass", False):
        return {}  # Skip if Gate A failed

    llm = _get_llm(state)
    problem = state.get("problem_statement", "")
    profile = _planning_profile(state)
    analysis_hint = _analysis_prompt_hint(profile)

    cot_prompt = (
        f"针对问题: {problem[:300]}\n\n"
        f"{analysis_hint}"
        "请给出 2-3 个解决方案，每个方案包括：\n"
        "- 名称\n- 优势\n- 劣势\n- 评分(1-10)\n\n"
        "最后用以下格式总结:\n"
        "推荐方案: ...\n"
        "风险评估: ...（1-3个关键风险）"
    )
    analysis = llm(cot_prompt, "你是一个方案评估专家。按格式回答。")

    # Extract risk_assessment from response
    risk_assessment = "待详细评估"
    for line in analysis.split("\n"):
        if "风险" in line and ":" in line:
            risk_assessment = line.split(":", 1)[1].strip()
            break
    if not risk_assessment or risk_assessment == "待详细评估":
        # Try to find any line mentioning risk
        for line in analysis.split("\n"):
            if "风险" in line and len(line) > 10:
                risk_assessment = line.strip()
                break

    return {
        "options": [
            {"name": "方案分析", "analysis": analysis[:800]},
        ],
        "recommended_option": analysis[:300] if analysis else "待确定",
        "risk_assessment": risk_assessment,
    }


def rubric_b(state: FunnelState) -> dict:
    """Gate B: Requires human confirmation (interrupt_before in prod)."""
    if not state.get("gate_a_pass", False):
        return {}

    options = state.get("options", [])
    has_recommendation = bool(state.get("recommended_option"))

    rubric_scores = {
        RubricDimension.FEASIBILITY: 0.8 if options else 0.2,
        RubricDimension.EVIDENCE: 0.7,
        RubricDimension.RISK: 0.6,
        RubricDimension.ALIGNMENT: 0.7 if has_recommendation else 0.3,
    }
    score, passed = compute_rubric(rubric_scores)

    return {
        "gate_b_pass": passed,
        "gate_b_reason": f"rubric score={score}",
    }


def finalize_funnel(state: FunnelState) -> dict:
    """Stage 3: Finalize — Validate + Freeze + ProjectCard output."""
    if not (state.get("gate_a_pass") and state.get("gate_b_pass")):
        return {"status": "rejected", "rejection_reason": "Gate check failed"}

    llm = _get_llm(state)
    recommended = state.get("recommended_option", "")
    problem = state.get("problem_statement", "")
    msg = state.get("user_message", "")
    profile = _planning_profile(state)
    finalize_hint = _finalize_prompt_hint(profile)

    cot_prompt = (
        f"项目需求: {msg[:200]}\n"
        f"推荐方案: {recommended[:300]}\n\n"
        f"{finalize_hint}"
        "请生成项目执行计划，按以下格式输出3-5个任务:\n\n"
        "任务1: [名称]\n"
        "负责人: [角色]\n"
        "工期: [天数]\n"
        "验收标准: [标准]\n\n"
        "任务2: [名称]\n"
        "...\n\n"
        "风险缓解: [措施]\n"
        "项目标题: [一句话标题]"
    )
    plan = llm(cot_prompt, "你是一个项目规划专家。严格按格式输出。")

    # Parse structured tasks from LLM output
    tasks = []
    current_task: dict[str, str] = {}
    for line in plan.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("任务") and ":" in line:
            if current_task:
                tasks.append(current_task)
            name = line.split(":", 1)[1].strip().strip("[]")
            current_task = {"name": name, "owner": "", "duration": "", "acceptance": ""}
        elif "负责人" in line and ":" in line:
            current_task["owner"] = line.split(":", 1)[1].strip()
        elif "工期" in line and ":" in line:
            current_task["duration"] = line.split(":", 1)[1].strip()
        elif "验收" in line and ":" in line:
            current_task["acceptance"] = line.split(":", 1)[1].strip()
    if current_task and current_task.get("name"):
        tasks.append(current_task)

    # Fallback: if parsing failed, create at least one task
    if not tasks:
        tasks = [{"name": "项目实施", "owner": "开发团队", "duration": "待定",
                  "acceptance": "功能完整可运行"}]

    # Extract project title
    title = ""
    for line in plan.split("\n"):
        if "项目标题" in line and ":" in line:
            title = line.split(":", 1)[1].strip().strip("[]")
            break
    if not title:
        title = msg[:60] if msg else "Untitled"

    project_card = {
        "title": title,
        "planning_profile": profile,
        "recommended_option": recommended[:300],
        "execution_plan": plan,
        "risk_level": state.get("risk_assessment", "unknown"),
        "evidence_refs": state.get("evidence_refs", []),
        "task_count": len(tasks),
    }

    return {
        "tasks": tasks,
        "project_card": project_card,
        "status": "complete",
    }


# ── Routing ───────────────────────────────────────────────────────

def should_continue_after_a(state: FunnelState) -> str:
    """Route after Gate A: continue or reject."""
    if state.get("gate_a_pass", False):
        return "analyze"
    return END


def should_continue_after_b(state: FunnelState) -> str:
    """Route after Gate B: continue or reject."""
    if state.get("gate_b_pass", False):
        return "finalize"
    return END


def _funnel_profile(state: FunnelState) -> str:
    pack = state.get("scenario_pack")
    if isinstance(pack, dict):
        return str(pack.get("funnel_profile") or pack.get("profile") or "").strip().lower()
    return ""


def _funnel_profile_gate_a_delta(profile: str) -> float:
    if profile in {"implementation_plan", "workforce_planning"}:
        return 0.05
    return 0.0


def _planning_profile(state: FunnelState) -> str:
    pack = state.get("scenario_pack")
    if isinstance(pack, dict):
        return str(pack.get("profile") or "").strip().lower()
    return ""


def _profile_prompt_hint(profile: str) -> str:
    if not profile:
        return ""
    profile_map = {
        "business_planning": "当前交付物类型是业务规划，请强调目标、现状、选项和约束。\n",
        "workforce_planning": "当前交付物类型是人力规划，请特别识别编制、招聘顺序和组织约束。\n",
        "implementation_plan": "当前交付物类型是实施规划，请特别识别里程碑、依赖和验证门槛。\n",
    }
    return profile_map.get(profile, "")


def _analysis_prompt_hint(profile: str) -> str:
    if profile == "workforce_planning":
        return "重点比较不同 staffing/hiring 方案对节奏、风险和组织承载的影响。\n"
    if profile == "business_planning":
        return "重点比较不同业务路径、资源投入和推进顺序。\n"
    if profile == "implementation_plan":
        return "重点比较不同实施路径、里程碑拆分和依赖关系。\n"
    return ""


def _finalize_prompt_hint(profile: str) -> str:
    if profile == "workforce_planning":
        return "输出时请把任务尽量落成人力规划动作，体现 headcount sequence、owner 和风险缓解。\n\n"
    if profile == "business_planning":
        return "输出时请把任务尽量落成业务规划动作，体现 recommended plan、owners 和 next steps。\n\n"
    if profile == "implementation_plan":
        return "输出时请把任务尽量落成实施动作，体现 milestones、validation 和 dependencies。\n\n"
    return ""


# ── Graph Builder ─────────────────────────────────────────────────

def build_funnel_graph() -> StateGraph:
    """Build the 3-stage Funnel StateGraph.

    Flow: understand → rubric_a → [analyze | END] → rubric_b → [finalize | END]

    Usage::

        graph = build_funnel_graph()
        app = graph.compile()
        result = app.invoke({"user_message": "需要做安徽外协交付方案"})
    """
    graph = StateGraph(FunnelState)

    graph.add_node("understand", understand)
    graph.add_node("rubric_a", rubric_a)
    graph.add_node("analyze", analyze)
    graph.add_node("rubric_b", rubric_b)
    graph.add_node("finalize", finalize_funnel)

    graph.set_entry_point("understand")
    graph.add_edge("understand", "rubric_a")
    graph.add_conditional_edges("rubric_a", should_continue_after_a)
    graph.add_edge("analyze", "rubric_b")
    graph.add_conditional_edges("rubric_b", should_continue_after_b)
    graph.add_edge("finalize", END)

    return graph
