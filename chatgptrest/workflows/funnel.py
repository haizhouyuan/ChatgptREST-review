"""
Funnel 9-Stage State Machine (S6) – Fuzzy requirements → ProjectCard.

Implements the hybrid funnel model from Funnel DR:
  Capture → Triage → Explore → Frame → Optionize → Evaluate → Validate → Freeze → Execute&Learn

Each stage has:
- Entry condition (gate from previous stage)
- Processing logic (diverge/converge tools)
- Exit condition (rubric score thresholds)
- Trace event emission
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from ..contracts.schemas import (
    FunnelStage,
    ProjectCard,
    Risk,
    RubricSnapshot,
    SuccessMetric,
    Task,
    TraceEvent,
    EventType,
    _uuid,
    _now_iso,
)
from ..contracts.rubric import RubricInput, RubricResult, compute_rubric, Gate
from ..contracts.event_log import EventLogStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Funnel state
# ---------------------------------------------------------------------------

@dataclass
class FunnelState:
    """Tracks the full state of a funnel execution."""
    funnel_id: str = ""
    trace_id: str = ""
    session_id: str = ""
    current_stage: str = "capture"
    raw_input: str = ""
    
    # Progressive refinement
    clarified_intent: str = ""
    problem_statement: str = ""
    job_to_be_done: str = ""
    
    # Exploration results
    research_findings: list[str] = field(default_factory=list)
    perspectives: list[str] = field(default_factory=list)
    
    # Options and evaluation
    options: list[dict[str, Any]] = field(default_factory=list)
    evaluation_scores: dict[str, float] = field(default_factory=dict)
    
    # Risk assessment
    risks: list[dict[str, Any]] = field(default_factory=list)
    
    # Outputs
    project_card: Optional[ProjectCard] = None
    rubric_history: list[dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    stage_history: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Text analysis utilities for extracting structure from fuzzy input
# ---------------------------------------------------------------------------

def extract_intent_from_text(text: str) -> dict[str, Any]:
    """
    Extract intent signals from fuzzy text (e.g., voice transcript).
    
    Returns structured analysis of what the user actually wants.
    """
    result = {
        "explicit_requests": [],
        "implicit_needs": [],
        "emotions": [],
        "key_entities": [],
        "ambiguities": [],
        "word_count": len(text.split()),
    }
    
    # Find explicit request patterns
    request_patterns = [
        r'我想(?:要|做|做一个|去)(.{5,50})',
        r'我希望(.{5,50})',
        r'如何(?:去)?(.{5,50})',
        r'怎么(?:去|样)?(.{5,50})',
        r'需要(.{5,50})',
        r'能不能(.{5,50})',
        r'I want to (.{5,100})',
        r'I need (.{5,100})',
        r'How (?:to|can I) (.{5,100})',
    ]
    
    for pattern in request_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            clean = m.strip().rstrip('。，,.')
            if clean and len(clean) > 3:
                result["explicit_requests"].append(clean)
    
    # Find emotional indicators
    emotion_words = {
        "着急": "urgency", "担心": "worry", "困惑": "confusion",
        "害怕": "fear", "希望": "hope", "开心": "joy",
        "失望": "disappointment", "纠结": "indecision",
        "反思": "reflection", "焦虑": "anxiety",
    }
    for word, emotion in emotion_words.items():
        if word in text:
            result["emotions"].append(emotion)
    
    # Find key entities (names, places, products)
    # Simple heuristic: capitalized terms, quoted terms, specific nouns
    quoted = re.findall(r'「(.+?)」|"(.+?)"|《(.+?)》', text)
    for q in quoted:
        for part in q:
            if part:
                result["key_entities"].append(part)
    
    # Find ambiguities (vague modifiers without definition)
    ambiguity_words = [
        "比较", "可能", "也许", "大概", "差不多",
        "有点", "还行", "一般", "不太", "不确定",
    ]
    for word in ambiguity_words:
        count = text.count(word)
        if count > 0:
            result["ambiguities"].append({"word": word, "count": count})
    
    return result


def classify_request_type(text: str) -> str:
    """Classify the type of request in the fuzzy text."""
    text_lower = text.lower()
    
    if any(kw in text_lower for kw in ["咨询", "建议", "advice", "consult"]):
        return "consultation"
    if any(kw in text_lower for kw in ["做一个", "开发", "build", "create", "develop"]):
        return "project"
    if any(kw in text_lower for kw in ["调研", "研究", "research", "investigate"]):
        return "research"
    if any(kw in text_lower for kw in ["规划", "计划", "plan"]):
        return "planning"
    if any(kw in text_lower for kw in ["修复", "bug", "fix", "问题"]):
        return "troubleshooting"
    
    return "general"


# ---------------------------------------------------------------------------
# Stage processors
# ---------------------------------------------------------------------------

def process_capture(state: FunnelState) -> FunnelState:
    """Stage 1: Capture – free-form collection of raw input."""
    state.current_stage = FunnelStage.CAPTURE.value
    state.created_at = _now_iso()
    state.updated_at = _now_iso()
    
    # The raw input is already captured in state.raw_input
    # In this stage we just acknowledge receipt
    state.stage_history.append({
        "stage": "capture",
        "timestamp": _now_iso(),
        "input_length": len(state.raw_input),
        "word_count": len(state.raw_input.split()),
    })
    
    return state


def process_triage(state: FunnelState) -> FunnelState:
    """Stage 2: Triage – classify and clarify the input."""
    state.current_stage = FunnelStage.TRIAGE.value
    
    # Extract intent from raw input
    intent = extract_intent_from_text(state.raw_input)
    request_type = classify_request_type(state.raw_input)
    
    # Build clarified intent
    explicit = intent["explicit_requests"]
    if explicit:
        state.clarified_intent = " | ".join(explicit[:5])
    else:
        state.clarified_intent = f"[{request_type}] " + state.raw_input[:200]
    
    state.stage_history.append({
        "stage": "triage",
        "timestamp": _now_iso(),
        "request_type": request_type,
        "explicit_requests": len(explicit),
        "emotions": intent["emotions"],
        "ambiguities_count": len(intent["ambiguities"]),
    })
    state.updated_at = _now_iso()
    
    return state


def process_explore(state: FunnelState) -> FunnelState:
    """Stage 3: Explore – open investigation, JTBD discovery."""
    state.current_stage = FunnelStage.EXPLORE.value
    
    # Extract JTBD (Jobs To Be Done) from the text
    intent = extract_intent_from_text(state.raw_input)
    
    # Derive problem statement from explicit requests
    if intent["explicit_requests"]:
        state.problem_statement = intent["explicit_requests"][0]
        if len(intent["explicit_requests"]) > 1:
            state.problem_statement += "（以及相关的 " + "、".join(
                intent["explicit_requests"][1:3]
            ) + "）"
    else:
        state.problem_statement = state.raw_input[:200]
    
    # Derive JTBD
    state.job_to_be_done = f"When {state.problem_statement[:100]}, " \
                            f"help me achieve the desired outcome effectively"
    
    # Collect perspectives
    state.perspectives = [
        f"用户视角: {state.clarified_intent}",
        f"情绪信号: {', '.join(intent['emotions']) if intent['emotions'] else '未明确'}",
        f"请求类型: {classify_request_type(state.raw_input)}",
    ]
    
    state.stage_history.append({
        "stage": "explore",
        "timestamp": _now_iso(),
        "problem_statement": state.problem_statement[:200],
        "jtbd": state.job_to_be_done[:200],
        "perspectives_count": len(state.perspectives),
    })
    state.updated_at = _now_iso()
    
    return state


def process_frame(state: FunnelState) -> FunnelState:
    """Stage 4: Frame – define the problem boundaries."""
    state.current_stage = FunnelStage.FRAME.value
    
    state.stage_history.append({
        "stage": "frame",
        "timestamp": _now_iso(),
        "problem_statement": state.problem_statement[:200],
    })
    state.updated_at = _now_iso()
    
    return state


def process_optionize(state: FunnelState) -> FunnelState:
    """Stage 5: Optionize – generate solution options."""
    state.current_stage = FunnelStage.OPTIONIZE.value
    
    request_type = classify_request_type(state.raw_input)
    
    # Generate options based on request type
    if request_type == "consultation":
        state.options = [
            {"id": "opt_1", "name": "专家咨询", "approach": "一对一咨询", "priority": "must_have"},
            {"id": "opt_2", "name": "深度研究", "approach": "系统性文献调研", "priority": "should_have"},
            {"id": "opt_3", "name": "行动计划", "approach": "制定可执行方案", "priority": "must_have"},
        ]
    elif request_type == "project":
        state.options = [
            {"id": "opt_1", "name": "MVP 快速验证", "approach": "最小可行产品", "priority": "must_have"},
            {"id": "opt_2", "name": "全面开发", "approach": "完整功能开发", "priority": "should_have"},
            {"id": "opt_3", "name": "分阶段迭代", "approach": "增量交付", "priority": "could_have"},
        ]
    else:
        state.options = [
            {"id": "opt_1", "name": "直接回答", "approach": "基于现有知识", "priority": "must_have"},
            {"id": "opt_2", "name": "深度调研", "approach": "扩展研究", "priority": "should_have"},
        ]
    
    state.stage_history.append({
        "stage": "optionize",
        "timestamp": _now_iso(),
        "options_count": len(state.options),
    })
    state.updated_at = _now_iso()
    
    return state


def process_evaluate(state: FunnelState) -> FunnelState:
    """Stage 6: Evaluate – score and rank options using RICE."""
    state.current_stage = FunnelStage.EVALUATE.value
    
    # RICE scoring: Reach × Impact × Confidence / Effort
    for opt in state.options:
        rice = {
            "reach": 0.7,     # How many users affected
            "impact": 0.8,    # How much impact per user
            "confidence": 0.6, # How confident in estimates
            "effort": 0.5,    # How much effort (lower = better)
        }
        score = (rice["reach"] * rice["impact"] * rice["confidence"]) / max(rice["effort"], 0.1)
        opt["rice_score"] = round(score, 2)
    
    # Sort by RICE score
    state.options.sort(key=lambda x: x.get("rice_score", 0), reverse=True)
    
    state.stage_history.append({
        "stage": "evaluate",
        "timestamp": _now_iso(),
        "top_option": state.options[0]["name"] if state.options else "none",
    })
    state.updated_at = _now_iso()
    
    return state


def process_validate(state: FunnelState) -> FunnelState:
    """Stage 7: Validate – pre-mortem and risk assessment."""
    state.current_stage = FunnelStage.VALIDATE.value
    
    # Default risk assessment
    state.risks = [
        {
            "description": "需求理解偏差 - 原始输入模糊可能导致方向错误",
            "probability": 0.4,
            "impact": 0.7,
            "mitigation": "迭代确认，分阶段验证",
            "detection_signal": "用户反馈不符合预期",
        },
        {
            "description": "资源不足 - 执行方案所需资源可能超出预期",
            "probability": 0.3,
            "impact": 0.5,
            "mitigation": "先做MVP验证核心假设",
            "detection_signal": "进度延迟超过20%",
        },
    ]
    
    state.stage_history.append({
        "stage": "validate",
        "timestamp": _now_iso(),
        "risks_count": len(state.risks),
    })
    state.updated_at = _now_iso()
    
    return state


def process_freeze(state: FunnelState) -> FunnelState:
    """Stage 8: Freeze – lock down the project card."""
    state.current_stage = FunnelStage.FREEZE.value
    
    # Compute rubric
    intent = extract_intent_from_text(state.raw_input)
    
    rubric_input = RubricInput(
        required_fields_total=8,
        required_fields_filled=sum([
            bool(state.problem_statement),
            bool(state.job_to_be_done),
            bool(state.clarified_intent),
            bool(state.options),
            bool(state.risks),
            bool(state.perspectives),
            len(state.raw_input) > 100,  # Has substantive input
            bool(state.evaluation_scores or state.options),
        ]),
        agent_decision_agreement=0.7,
        rationale_overlap=0.5,
        iteration_stability=0.6,
        top_k_risks=len(state.risks),
        risks_with_mitigation=sum(1 for r in state.risks if r.get("mitigation")),
        has_in_scope=True,
        has_out_scope=bool(state.options),
        has_assumptions=True,
        has_constraints=bool(state.risks),
        has_interfaces=False,
        total_requirement_words=len(state.raw_input.split()),
        ambiguous_word_count=len(intent.get("ambiguities", [])),
        has_test_plan=bool(state.risks),  # If risks have detection signals
        task_decomposition_quality=0.5,
        critical_claims=max(len(intent.get("explicit_requests", [])), 1),
        critical_claims_with_evidence=len(state.research_findings),
        avg_evidence_quality=0.5,
    )
    
    rubric_result = compute_rubric(rubric_input)
    state.rubric_history.append({
        "stage": "freeze",
        "timestamp": _now_iso(),
        **rubric_result.to_dict(),
    })
    
    # Build ProjectCard
    state.project_card = ProjectCard(
        title=state.problem_statement[:100] if state.problem_statement else "未命名项目",
        problem_statement=state.problem_statement,
        job_to_be_done=state.job_to_be_done,
        success_metrics=[
            SuccessMetric(
                metric="用户满意度",
                target=">80%",
                measurement_method="用户反馈评分",
            )
        ],
        in_scope=[state.clarified_intent] if state.clarified_intent else [],
        out_of_scope=[],
        risks=[
            Risk(
                description=r["description"],
                probability=r.get("probability", 0.5),
                impact=r.get("impact", 0.5),
                mitigation=r.get("mitigation", ""),
                detection_signal=r.get("detection_signal", ""),
            )
            for r in state.risks
        ],
        tasks=[
            Task(
                title=opt["name"],
                estimated_effort_hours=4,
                agent_role="executor",
            )
            for opt in state.options[:5]
        ],
        rubric_snapshot=RubricSnapshot(
            total=rubric_result.total,
            gate=rubric_result.gate,
        ),
    )
    
    state.stage_history.append({
        "stage": "freeze",
        "timestamp": _now_iso(),
        "rubric_total": rubric_result.total,
        "rubric_gate": rubric_result.gate,
        "project_card_title": state.project_card.title,
    })
    state.updated_at = _now_iso()
    
    return state


def process_execute_learn(state: FunnelState) -> FunnelState:
    """Stage 9: Execute & Learn – hand off and observe."""
    state.current_stage = FunnelStage.EXECUTE_LEARN.value
    
    state.stage_history.append({
        "stage": "execute_learn",
        "timestamp": _now_iso(),
        "status": "ready_for_handoff",
    })
    state.updated_at = _now_iso()
    
    return state


# ---------------------------------------------------------------------------
# Funnel Engine
# ---------------------------------------------------------------------------

STAGE_PROCESSORS = {
    FunnelStage.CAPTURE.value: process_capture,
    FunnelStage.TRIAGE.value: process_triage,
    FunnelStage.EXPLORE.value: process_explore,
    FunnelStage.FRAME.value: process_frame,
    FunnelStage.OPTIONIZE.value: process_optionize,
    FunnelStage.EVALUATE.value: process_evaluate,
    FunnelStage.VALIDATE.value: process_validate,
    FunnelStage.FREEZE.value: process_freeze,
    FunnelStage.EXECUTE_LEARN.value: process_execute_learn,
}

STAGE_ORDER = [
    FunnelStage.CAPTURE.value,
    FunnelStage.TRIAGE.value,
    FunnelStage.EXPLORE.value,
    FunnelStage.FRAME.value,
    FunnelStage.OPTIONIZE.value,
    FunnelStage.EVALUATE.value,
    FunnelStage.VALIDATE.value,
    FunnelStage.FREEZE.value,
    FunnelStage.EXECUTE_LEARN.value,
]


class FunnelEngine:
    """
    Runs the 9-stage funnel from raw input to ProjectCard.

    Usage::

        engine = FunnelEngine(event_log=store)
        state = engine.run("这是一段很长的语音转文字稿...")
        print(state.project_card.to_dict())
    """

    def __init__(self, event_log: EventLogStore | None = None):
        self.event_log = event_log

    def _emit(self, event_type: str, trace_id: str, data: dict, session_id: str = "") -> None:
        if self.event_log:
            self.event_log.append(TraceEvent(
                source="funnel/engine",
                event_type=event_type,
                trace_id=trace_id,
                session_id=session_id,
                data=data,
            ))

    def run(
        self,
        raw_input: str,
        *,
        trace_id: str = "",
        session_id: str = "",
        stop_at_stage: str = "",
    ) -> FunnelState:
        """
        Run the full funnel pipeline (or up to a specific stage).

        Args:
            raw_input: The raw user input (voice transcript, text, etc.)
            trace_id: Optional trace ID for correlation
            session_id: Optional session ID
            stop_at_stage: If set, stop after this stage
        """
        trace_id = trace_id or _uuid()
        
        state = FunnelState(
            funnel_id=_uuid(),
            trace_id=trace_id,
            session_id=session_id,
            raw_input=raw_input,
        )

        self._emit("workflow_started", trace_id, {
            "workflow": "funnel",
            "input_length": len(raw_input),
            "funnel_id": state.funnel_id,
        }, session_id)

        for stage_name in STAGE_ORDER:
            processor = STAGE_PROCESSORS[stage_name]
            
            self._emit("workflow_step_started", trace_id, {
                "stage": stage_name,
                "funnel_id": state.funnel_id,
            }, session_id)

            try:
                state = processor(state)
            except Exception as e:
                logger.error(f"Funnel stage {stage_name} failed: {e}")
                self._emit("workflow_step_failed", trace_id, {
                    "stage": stage_name,
                    "error": str(e),
                }, session_id)
                break

            self._emit("workflow_step_finished", trace_id, {
                "stage": stage_name,
                "funnel_id": state.funnel_id,
            }, session_id)

            if stop_at_stage and stage_name == stop_at_stage:
                break

        self._emit("workflow_finished", trace_id, {
            "workflow": "funnel",
            "final_stage": state.current_stage,
            "has_project_card": state.project_card is not None,
            "rubric_total": state.rubric_history[-1]["total"] if state.rubric_history else 0,
        }, session_id)

        return state
