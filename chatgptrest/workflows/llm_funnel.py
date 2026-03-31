"""
LLM-Powered Funnel Stages.

Replaces the template-filling stages with real LLM analysis.
Each stage calls llm_call() with structured prompts to produce
genuine analysis instead of pattern-matching defaults.

Import this module and call `upgrade_funnel_with_llm(engine)` to
replace the default stage processors with LLM-powered versions.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .llm_backend import LLMConfig, LLMResult, llm_call, TIER_FAST, TIER_DEEP, TIER_REASON
from .funnel import (
    FunnelState,
    FunnelEngine,
    STAGE_PROCESSORS,
    process_capture,
    process_triage,
    process_execute_learn,
    extract_intent_from_text,
    classify_request_type,
)
from ..contracts.schemas import (
    FunnelStage,
    ProjectCard,
    Risk,
    RubricSnapshot,
    SuccessMetric,
    Task,
    _now_iso,
    _uuid,
)
from ..contracts.rubric import RubricInput, compute_rubric

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompts for each stage
# ---------------------------------------------------------------------------

EXPLORE_SYSTEM = """你是一个需求分析师。你的任务是深入分析用户的原始输入（可能是语音转文字稿），提取核心需求。

输出 JSON 格式:
{
  "problem_statement": "一句话描述核心问题",
  "job_to_be_done": "用户真正想达成的目标（JTBD框架）",
  "explicit_requests": ["明确提出的请求1", "请求2"],
  "implicit_needs": ["隐含的需求1", "需求2"],
  "key_constraints": ["约束1", "约束2"],
  "domain": "所属领域",
  "complexity_assessment": "low/medium/high",
  "research_questions": ["需要进一步调研的问题1", "问题2"]
}

要求：
- 从模糊输入中提炼清晰需求
- 区分显式需求和隐式需求
- 识别约束条件
- 提出需要调研的问题"""

OPTIONIZE_SYSTEM = """你是一个方案设计师。根据需求分析结果，生成3-5个可行方案。

输出 JSON 格式:
{
  "options": [
    {
      "id": "opt_1",
      "name": "方案名称",
      "approach": "详细描述实现方式",
      "pros": ["优势1", "优势2"],
      "cons": ["劣势1"],
      "estimated_effort": "1周/1月/3月",
      "priority": "must_have/should_have/could_have",
      "tech_stack": ["使用的技术/工具"],
      "key_assumptions": ["前提假设1"]
    }
  ]
}

要求：
- 方案要有实质差异，不是形式上的变体
- 每个方案说明技术可行性
- 考虑用户的资源约束
- 至少一个 MVP/快速验证方案"""

EVALUATE_SYSTEM = """你是一个决策分析师。使用 RICE 框架评估方案。

对每个方案打分（0-10）:
- Reach: 影响范围（这个方案能解决多少核心问题？）
- Impact: 影响深度（每个问题能解决到什么程度？）
- Confidence: 信心度（你对这个评估有多确定？）
- Effort: 所需投入（越小越好）

输出 JSON 格式:
{
  "evaluations": [
    {
      "option_id": "opt_1",
      "option_name": "方案名称",
      "rice": {"reach": 8, "impact": 7, "confidence": 6, "effort": 5},
      "score": 6.72,
      "rationale": "选择此分数的原因",
      "recommended_order": 1
    }
  ],
  "recommendation": "推荐方案及理由",
  "trade_offs": "关键权衡说明"
}"""

VALIDATE_SYSTEM = """你是一个风险分析师。对推荐方案做 Pre-Mortem 分析。

假设项目已经失败了，分析可能的失败原因。

输出 JSON 格式:
{
  "risks": [
    {
      "description": "风险描述",
      "probability": 0.3,
      "impact": 0.8,
      "category": "technical/market/resource/execution/requirement",
      "mitigation": "缓解措施",
      "detection_signal": "如何早期发现此风险",
      "contingency": "如果风险发生的应急方案"
    }
  ],
  "success_metrics": [
    {
      "metric": "指标名称",
      "target": "目标值",
      "measurement_method": "度量方法"
    }
  ],
  "definition_of_done": ["完成标准1", "完成标准2"],
  "pre_mortem_summary": "一段话总结主要风险"
}"""

FREEZE_SYSTEM = """你是一个项目经理。根据前面所有阶段的分析，生成最终的任务分解。

输出 JSON 格式:
{
  "tasks": [
    {
      "title": "任务标题",
      "description": "详细描述",
      "estimated_hours": 4,
      "depends_on": [],
      "agent_role": "developer/researcher/designer/reviewer",
      "outputs": ["产出物1"],
      "verification": ["验证方法1"]
    }
  ],
  "milestones": [
    {"name": "里程碑", "tasks": ["task_1", "task_2"], "target_date": "相对时间"}
  ],
  "total_estimated_hours": 40,
  "recommended_team": "建议的执行团队/agent配置"
}"""


# ---------------------------------------------------------------------------
# LLM-powered stage processors
# ---------------------------------------------------------------------------

def _parse_json_response(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try direct parse first
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Try extracting from code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {}


def process_explore_llm(state: FunnelState, config: LLMConfig | None = None) -> FunnelState:
    """LLM-powered Explore stage: real need analysis."""
    state.current_stage = FunnelStage.EXPLORE.value

    result = llm_call(
        prompt=f"分析以下用户需求（可能是语音转写稿）:\n\n{state.raw_input[:6000]}",
        system=EXPLORE_SYSTEM,
        tier=TIER_DEEP,
        config=config,
    )

    if result.ok:
        parsed = _parse_json_response(result.text)
        state.problem_statement = parsed.get("problem_statement", state.raw_input[:200])
        state.job_to_be_done = parsed.get("job_to_be_done", "")

        # Store research findings from LLM analysis
        state.research_findings = parsed.get("research_questions", [])
        state.perspectives = [
            f"显式需求: {', '.join(parsed.get('explicit_requests', [])[:3])}",
            f"隐式需求: {', '.join(parsed.get('implicit_needs', [])[:3])}",
            f"约束: {', '.join(parsed.get('key_constraints', [])[:3])}",
            f"领域: {parsed.get('domain', '未知')}",
            f"复杂度: {parsed.get('complexity_assessment', '未评估')}",
        ]

        state.stage_history.append({
            "stage": "explore",
            "timestamp": _now_iso(),
            "llm_provider": result.provider,
            "llm_model": result.model,
            "latency_ms": result.latency_ms,
            "problem_statement": state.problem_statement[:200],
        })
    else:
        # Fallback to rule-based
        from .funnel import process_explore
        state = process_explore(state)
        state.stage_history[-1]["llm_fallback"] = True
        state.stage_history[-1]["llm_error"] = result.error[:200]

    state.updated_at = _now_iso()
    return state


def process_optionize_llm(state: FunnelState, config: LLMConfig | None = None) -> FunnelState:
    """LLM-powered Optionize stage: real option generation."""
    state.current_stage = FunnelStage.OPTIONIZE.value

    context = (
        f"需求: {state.problem_statement}\n"
        f"JTBD: {state.job_to_be_done}\n"
        f"视角: {'; '.join(state.perspectives)}\n"
        f"调研问题: {'; '.join(state.research_findings[:3])}"
    )

    result = llm_call(
        prompt=f"为以下需求生成方案选项:\n\n{context}",
        system=OPTIONIZE_SYSTEM,
        tier=TIER_DEEP,
        config=config,
    )

    if result.ok:
        parsed = _parse_json_response(result.text)
        state.options = parsed.get("options", [])

        state.stage_history.append({
            "stage": "optionize",
            "timestamp": _now_iso(),
            "llm_provider": result.provider,
            "options_count": len(state.options),
            "latency_ms": result.latency_ms,
        })
    else:
        from .funnel import process_optionize
        state = process_optionize(state)
        state.stage_history[-1]["llm_fallback"] = True

    state.updated_at = _now_iso()
    return state


def process_evaluate_llm(state: FunnelState, config: LLMConfig | None = None) -> FunnelState:
    """LLM-powered Evaluate stage: real RICE scoring."""
    state.current_stage = FunnelStage.EVALUATE.value

    options_text = json.dumps(state.options, ensure_ascii=False, indent=2, default=str)

    result = llm_call(
        prompt=(
            f"需求: {state.problem_statement}\n\n"
            f"方案列表:\n{options_text[:4000]}\n\n"
            f"请用 RICE 框架评估每个方案。"
        ),
        system=EVALUATE_SYSTEM,
        tier=TIER_DEEP,
        config=config,
    )

    if result.ok:
        parsed = _parse_json_response(result.text)
        evaluations = parsed.get("evaluations", [])

        # Update options with RICE scores
        eval_map = {e.get("option_id", ""): e for e in evaluations}
        for opt in state.options:
            oid = opt.get("id", "")
            if oid in eval_map:
                rice = eval_map[oid].get("rice", {})
                r, i, c, e_ = (
                    rice.get("reach", 5) / 10,
                    rice.get("impact", 5) / 10,
                    rice.get("confidence", 5) / 10,
                    rice.get("effort", 5) / 10,
                )
                opt["rice_score"] = round((r * i * c) / max(e_, 0.1), 2)
                opt["rice_rationale"] = eval_map[oid].get("rationale", "")

        state.options.sort(key=lambda x: x.get("rice_score", 0), reverse=True)
        state.evaluation_scores = {
            "recommendation": parsed.get("recommendation", ""),
            "trade_offs": parsed.get("trade_offs", ""),
        }

        state.stage_history.append({
            "stage": "evaluate",
            "timestamp": _now_iso(),
            "llm_provider": result.provider,
            "top_option": state.options[0].get("name", "") if state.options else "",
            "latency_ms": result.latency_ms,
        })
    else:
        from .funnel import process_evaluate
        state = process_evaluate(state)
        state.stage_history[-1]["llm_fallback"] = True

    state.updated_at = _now_iso()
    return state


def process_validate_llm(state: FunnelState, config: LLMConfig | None = None) -> FunnelState:
    """LLM-powered Validate stage: real pre-mortem + risk analysis."""
    state.current_stage = FunnelStage.VALIDATE.value

    top_option = json.dumps(state.options[0], ensure_ascii=False, default=str) if state.options else "{}"

    result = llm_call(
        prompt=(
            f"需求: {state.problem_statement}\n"
            f"推荐方案: {top_option[:3000]}\n\n"
            f"做 Pre-Mortem 分析。"
        ),
        system=VALIDATE_SYSTEM,
        tier=TIER_REASON,
        config=config,
    )

    if result.ok:
        parsed = _parse_json_response(result.text)
        state.risks = parsed.get("risks", [])

        state.stage_history.append({
            "stage": "validate",
            "timestamp": _now_iso(),
            "llm_provider": result.provider,
            "risks_count": len(state.risks),
            "latency_ms": result.latency_ms,
        })
    else:
        from .funnel import process_validate
        state = process_validate(state)
        state.stage_history[-1]["llm_fallback"] = True

    state.updated_at = _now_iso()
    return state


def process_freeze_llm(state: FunnelState, config: LLMConfig | None = None) -> FunnelState:
    """LLM-powered Freeze stage: real task decomposition + ProjectCard."""
    state.current_stage = FunnelStage.FREEZE.value

    context = (
        f"需求: {state.problem_statement}\n"
        f"JTBD: {state.job_to_be_done}\n"
        f"推荐方案: {json.dumps(state.options[:2], ensure_ascii=False, default=str)[:2000]}\n"
        f"风险: {json.dumps(state.risks[:3], ensure_ascii=False, default=str)[:1000]}"
    )

    result = llm_call(
        prompt=f"为以下项目生成任务分解:\n\n{context}",
        system=FREEZE_SYSTEM,
        tier=TIER_DEEP,
        config=config,
    )

    tasks_list = []
    success_metrics = []
    definition_of_done = []

    if result.ok:
        parsed = _parse_json_response(result.text)
        raw_tasks = parsed.get("tasks", [])

        for t in raw_tasks[:10]:  # Cap at 10 tasks
            tasks_list.append(Task(
                title=t.get("title", ""),
                description=t.get("description", ""),
                estimated_effort_hours=t.get("estimated_hours", 4),
                agent_role=t.get("agent_role", "executor"),
                outputs=t.get("outputs", []),
                verification=t.get("verification", []),
            ))

        definition_of_done = parsed.get("definition_of_done", [])

    if not tasks_list:
        # Minimal fallback
        tasks_list = [Task(title=opt.get("name", "task"), estimated_effort_hours=4)
                      for opt in state.options[:3]]

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
            len(state.raw_input) > 100,
            bool(tasks_list),
        ]),
        agent_decision_agreement=0.7,
        rationale_overlap=0.5,
        iteration_stability=0.6,
        top_k_risks=len(state.risks),
        risks_with_mitigation=sum(1 for r in state.risks if isinstance(r, dict) and r.get("mitigation")),
        has_in_scope=True,
        has_out_scope=bool(state.options),
        has_assumptions=True,
        has_constraints=bool(state.risks),
        has_interfaces=False,
        total_requirement_words=len(state.raw_input.split()),
        ambiguous_word_count=len(intent.get("ambiguities", [])),
        has_test_plan=bool(definition_of_done),
        task_decomposition_quality=min(len(tasks_list) / 5, 1.0),
        critical_claims=max(len(intent.get("explicit_requests", [])), 1),
        critical_claims_with_evidence=len(state.research_findings),
        avg_evidence_quality=0.5 if state.research_findings else 0.0,
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
            SuccessMetric(metric=m.get("metric", ""), target=m.get("target", ""),
                         measurement_method=m.get("measurement_method", ""))
            for m in (success_metrics or [{"metric": "完成度", "target": "100%",
                                           "measurement_method": "任务清单"}])
        ],
        in_scope=[state.clarified_intent] if state.clarified_intent else [],
        out_of_scope=[],
        risks=[
            Risk(
                description=r["description"] if isinstance(r, dict) else str(r),
                probability=r.get("probability", 0.5) if isinstance(r, dict) else 0.5,
                impact=r.get("impact", 0.5) if isinstance(r, dict) else 0.5,
                mitigation=r.get("mitigation", "") if isinstance(r, dict) else "",
                detection_signal=r.get("detection_signal", "") if isinstance(r, dict) else "",
            )
            for r in state.risks[:5]
        ],
        tasks=tasks_list,
        definition_of_done=definition_of_done,
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
        "tasks_count": len(tasks_list),
        "llm_powered": result.ok if result else False,
    })
    state.updated_at = _now_iso()

    return state


# ---------------------------------------------------------------------------
# Upgrade function
# ---------------------------------------------------------------------------

def upgrade_funnel_with_llm(
    engine: FunnelEngine,
    config: LLMConfig | None = None,
) -> FunnelEngine:
    """
    Upgrade a FunnelEngine with LLM-powered stages.

    Replaces Explore, Optionize, Evaluate, Validate, Freeze
    with LLM-powered versions. Keeps Capture, Triage, Frame,
    Execute&Learn as rule-based (they don't need LLM).

    Usage::

        engine = FunnelEngine(event_log=store)
        engine = upgrade_funnel_with_llm(engine)
        state = engine.run("用户的原始需求...")
    """
    cfg = config or LLMConfig.from_env()

    # Replace stage processors with LLM-powered versions
    # These are module-level dicts that FunnelEngine.run() reads
    STAGE_PROCESSORS[FunnelStage.EXPLORE.value] = lambda s: process_explore_llm(s, cfg)
    STAGE_PROCESSORS[FunnelStage.OPTIONIZE.value] = lambda s: process_optionize_llm(s, cfg)
    STAGE_PROCESSORS[FunnelStage.EVALUATE.value] = lambda s: process_evaluate_llm(s, cfg)
    STAGE_PROCESSORS[FunnelStage.VALIDATE.value] = lambda s: process_validate_llm(s, cfg)
    STAGE_PROCESSORS[FunnelStage.FREEZE.value] = lambda s: process_freeze_llm(s, cfg)

    logger.info(
        f"Funnel upgraded with LLM stages. "
        f"Providers: {cfg.available_providers()}, "
        f"Default: {cfg.default_provider}"
    )

    return engine
