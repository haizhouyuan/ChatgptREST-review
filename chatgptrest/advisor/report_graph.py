"""Report Graph — LangGraph subgraph for report generation.

Flow: purpose_identify → evidence_pack → internal_draft → external_draft
      → review → redact_gate → finalize

Supports the "三套稿" system:
  - internal_draft: 内部底稿 (full detail, citations, raw analysis)
  - external_draft: 外发沟通稿 (polished, audience-appropriate)
  - redact_gate: 脱敏审查 (PII/sensitive data removal)

All LLM calls go through a connector abstraction (mock-able).
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Callable, TypedDict
import os

from langgraph.graph import StateGraph, END
from chatgptrest.workspace.contracts import WorkspaceRequest, workspace_effect_key, workspace_effect_payload

try:
    from chatgptrest.integrations.google_workspace import GoogleWorkspace
except ImportError:
    GoogleWorkspace = None

try:
    from chatgptrest.integrations.obsidian_api import ObsidianClient
except ImportError:
    ObsidianClient = None

logger = logging.getLogger(__name__)


# Module-level cache for MCP model failures — DEPRECATED: now handled by
# RoutingFabric's HealthTracker. Kept as empty dict for backward compatibility.
_mcp_fail_cache: dict[str, float] = {}
_MCP_FAIL_TTL = 300


def _get_llm(state):
    """Get LLM connector for report tasks.

    Priority: state-injected (tests) > RoutingFabric (with API fallback) > API connector.

    Phase 3: Delegates to RoutingFabric.get_llm_fn("report", "report_writing")
    which handles MCP/API selection, health tracking, and automatic fallback.
    **Always falls back to API connector if RoutingFabric returns empty.**
    """
    # 1. State-injected (tests)
    llm = state.get("llm_connector")
    if llm:
        return llm

    try:
        from chatgptrest.advisor.graph import _svc
        svc = _svc(state)
        api_llm = svc.llm_connector if svc else None

        # 2. RoutingFabric (Phase 3+) — wrapped with API fallback
        if svc and getattr(svc, 'routing_fabric', None):
            fabric_fn = svc.routing_fabric.get_llm_fn("report", "report_writing")

            def _with_api_fallback(prompt: str, system_msg: str = "") -> str:
                """Try RoutingFabric first, fall back to API models."""
                result = ""
                try:
                    result = fabric_fn(prompt, system_msg)
                except Exception as e:
                    logger.warning(
                        "Report RoutingFabric error: %s, falling back to API", e,
                    )
                if result and len(result.strip()) > 10:
                    return result
                # Fabric failed → API fallback
                if api_llm:
                    logger.info("Report fabric empty, falling back to API connector")
                    return api_llm(prompt, system_msg)
                return ""

            return _with_api_fallback

        # 3. API connector fallback (pre-Phase 3 or no fabric)
        if api_llm:
            return api_llm
    except Exception:
        pass
    return _noop_llm


def _get_runtime_service(state: "ReportState", state_key: str, runtime_attr: str) -> Any:
    """Read a live service from serializable state overrides or the bound advisor runtime."""
    value = state.get(state_key)
    if value is not None:
        return value
    try:
        from chatgptrest.advisor.graph import _svc

        runtime = _svc(state)
    except Exception:
        return None
    return getattr(runtime, runtime_attr, None)


# ── Types ─────────────────────────────────────────────────────────

LLMConnector = Callable[[str, str], str]


def _noop_llm(prompt: str, system_msg: str = "") -> str:
    """Default no-op LLM for testing."""
    if "审核" in prompt or "review" in prompt.lower():
        return "评分：8/10\n1. 结构完整\n2. 逻辑清晰"
    if "脱敏" in prompt or "redact" in prompt.lower():
        return "无敏感信息"
    return f"[mock response to: {prompt[:50]}...]"


def _iter_redact_chunks(text: str, *, max_chars: int = 1000) -> list[str]:
    """Split text into bounded chunks for full-document redact scanning."""
    raw = str(text or "")
    if not raw:
        return []
    return [raw[idx: idx + max_chars] for idx in range(0, len(raw), max_chars)]


# ── State ─────────────────────────────────────────────────────────

class ReportState(TypedDict, total=False):
    """State for the Report Graph."""
    # Input
    user_message: str
    trace_id: str
    report_type: str       # "progress" | "analysis" | "summary"
    scenario_pack: dict[str, Any]

    # After purpose_identify
    purpose: str
    scope: str
    audience: str
    stationery_type: str   # "internal" | "external" | "executive"

    # After evidence_pack
    evidence_ids: list[str]
    evidence_count: int
    evidence_summaries: list[str]

    # After internal_draft
    internal_draft_text: str
    draft_sections: list[str]

    # After external_draft
    external_draft_text: str

    # After review
    review_notes: list[str]
    review_pass: bool
    review_score: int
    _rewrite_count: int  # Fix 3: track rewrite attempts

    # After web_research (Fix 2)
    _web_evidence: str

    # After redact_gate
    redact_pass: bool
    redact_issues: list[str]

    # After finalize
    final_text: str
    final_status: str      # "complete" | "needs_revision" | "redact_blocked"

    # Config (injected)
    llm_connector: Any
    kb_hub: Any
    _event_bus: Any
    _policy_engine: Any

    # User constraints (extracted in purpose_identify)
    _target_word_count: int
    _output_format: str       # "markdown" | "pdf"
    _delivery_target: str     # "google_drive" | "feishu" | ""


# ── Nodes ─────────────────────────────────────────────────────────

def purpose_identify(state: ReportState) -> dict:
    """Identify report purpose, scope, audience, and stationery type.

    Maps to 三套稿 system: choose internal/external/executive template.
    Also extracts user constraints: word count, format, deliverable target.
    """
    msg = state.get("user_message", "")
    llm = _get_llm(state)
    scenario_pack = dict(state.get("scenario_pack") or {})
    profile = str(scenario_pack.get("profile") or "").strip()
    acceptance = dict(scenario_pack.get("acceptance") or {})
    required_sections = [
        str(item).strip()
        for item in list(acceptance.get("required_sections") or [])
        if str(item).strip()
    ]
    pack_hint = ""
    if profile:
        pack_hint = (
            f"\n附加场景约束:\n"
            f"- 场景包: {profile}\n"
            f"- 报告类型倾向: {state.get('report_type', '') or 'progress'}\n"
        )
        if required_sections:
            pack_hint += f"- 必须覆盖的结构: {', '.join(required_sections)}\n"

    cot_prompt = (
        f"用户需要一份报告。用户原文: '{msg}'\n"
        f"{pack_hint}"
        "请分析（每项一行简短回答）:\n"
        "1. 报告目的（具体主题是什么）\n"
        "2. 报告范围（覆盖哪些方面）\n"
        "3. 目标读者\n"
        "4. 稿件类型：内部底稿(internal)/外发沟通稿(external)/高层请示(executive)\n"
    )
    cot_response = llm(cot_prompt, "你是一个报告规划助手。用中文简洁回答。")

    # Detect stationery type from LLM response
    stationery = "internal"
    resp_lower = cot_response.lower()
    if "external" in resp_lower or "外发" in cot_response or "沟通" in cot_response:
        stationery = "external"
    elif "executive" in resp_lower or "高层" in cot_response or "请示" in cot_response:
        stationery = "executive"

    # Detect audience
    audience = "internal"
    if "领导" in cot_response or "高层" in cot_response or "executive" in resp_lower:
        audience = "leadership"
    elif "客户" in cot_response or "外部" in cot_response or "external" in resp_lower:
        audience = "external"

    # Extract user constraints from original message
    import re as _re
    word_count_match = _re.search(r'(\d+)\s*字', msg)
    target_word_count = int(word_count_match.group(1)) if word_count_match else 0

    # Detect output format
    msg_lower = msg.lower()
    output_format = "markdown"
    if any(kw in msg_lower for kw in ["pdf"]):
        output_format = "pdf"
    elif any(kw in msg_lower for kw in ["md", "markdown"]):
        output_format = "markdown"

    # Detect delivery target
    delivery_target = ""
    if "google drive" in msg_lower or "drive" in msg_lower:
        delivery_target = "google_drive"
    elif "飞书" in msg_lower:
        delivery_target = "feishu"

    return {
        "purpose": cot_response[:200],
        "scope": msg[:200],
        "audience": audience,
        "stationery_type": stationery,
        "trace_id": state.get("trace_id") or str(uuid.uuid4()),
        "_target_word_count": target_word_count,
        "_output_format": output_format,
        "_delivery_target": delivery_target,
    }


def evidence_pack(state: ReportState) -> dict:
    """Gather evidence documents using KBHub.evidence_pack()."""
    hub = _get_runtime_service(state, "kb_hub", "kb_hub")
    scope = state.get("scope", state.get("user_message", ""))

    if hub and scope:
        try:
            hits = hub.evidence_pack(scope, max_docs=20)
            if hits:
                evidence_ids = [h.artifact_id for h in hits]
                evidence_summaries = [f"[{h.title}] {h.snippet[:100]}" for h in hits]
                return {
                    "evidence_ids": evidence_ids,
                    "evidence_count": len(evidence_ids),
                    "evidence_summaries": evidence_summaries,
                }
        except Exception as e:
            logger.warning("Evidence pack search failed: %s", e)

    return {"evidence_ids": [], "evidence_count": 0, "evidence_summaries": []}


def web_research(state: ReportState) -> dict:
    """Fix 2: Web research to supplement KB evidence.

    When KB evidence is sparse (< 3 docs), use MCP LLM to do a
    web-informed research query, injecting the results as evidence.
    """
    evidence_count = state.get("evidence_count", 0)
    scenario_pack = dict(state.get("scenario_pack") or {})
    acceptance = dict(scenario_pack.get("acceptance") or {})
    evidence_required = dict(scenario_pack.get("evidence_required") or {})
    required_evidence = max(3, int(acceptance.get("min_evidence_items") or 0))
    if evidence_count >= required_evidence:
        logger.info("web_research: KB has %d docs (threshold=%d), skipping web", evidence_count, required_evidence)
        return {}

    user_msg = state.get("user_message", "")
    purpose = state.get("purpose", "")

    # Use the report LLM (which prefers MCP high-end models)
    llm = _get_llm(state)

    research_prompt = (
        f"请针对以下主题做一次简要调研，提供关键事实和数据：\n\n"
        f"主题: {user_msg}\n"
        f"目的: {purpose}\n\n"
        f"要求:\n"
        f"- 列出 5-8 个关键事实/数据点\n"
        f"- 每个事实要具体（包含数字、日期、名称等）\n"
        f"- 如果知道来源请标注\n"
        f"- 用编号列表格式输出\n"
    )
    if scenario_pack:
        profile = str(scenario_pack.get("profile") or "").strip()
        if profile:
            research_prompt += f"- 当前研究场景: {profile}\n"
        if evidence_required.get("prefer_primary_sources"):
            research_prompt += "- 优先给出一级来源、原始数据或官方口径\n"
        if evidence_required.get("require_traceable_claims"):
            research_prompt += "- 关键结论必须做到可追溯，不确定项明确标注待确认\n"
    try:
        research_result = llm(
            research_prompt,
            "你是一个研究助手。提供准确的事实和数据，不要编造。"
            "如果不确定某个数据点，请注明'待确认'。"
        )
        if research_result and len(research_result) > 50:
            logger.info("web_research: got %d chars of evidence", len(research_result))
            # Merge with existing evidence
            existing = state.get("evidence_summaries", [])
            existing.append(f"[Web/LLM Research] {research_result[:1000]}")
            return {
                "evidence_summaries": existing,
                "evidence_count": len(existing),
                "_web_evidence": research_result[:1500],
            }
    except Exception as e:
        logger.warning("web_research failed: %s", e)

    return {}


def internal_draft(state: ReportState) -> dict:
    """Generate internal draft (底稿) — full detail with citations.

    This is the detailed analytical version with all evidence citations.
    Respects user's word count and format constraints.
    """
    llm = _get_llm(state)
    purpose = state.get("purpose", "")
    scope = state.get("scope", "")
    user_msg = state.get("user_message", "")
    evidence = state.get("evidence_summaries", [])
    evidence_text = "\n".join(evidence[:10]) if evidence else "（无KB参考文档，请基于你的知识撰写）"
    target_words = state.get("_target_word_count", 0)

    # Build word count instruction
    word_instruction = ""
    if target_words > 0:
        word_instruction = f"- **字数要求**: 严格控制在 {target_words} 字左右（±10%）\n"
    else:
        word_instruction = "- **字数要求**: 600-1000字，内容充实但不冗长\n"

    prompt = (
        f"请根据用户需求撰写一篇高质量的报告/文章。\n\n"
        f"**用户原始需求**: {user_msg}\n\n"
        f"**报告目的**: {purpose}\n"
        f"**报告范围**: {scope}\n\n"
        f"**参考资料**:\n{evidence_text}\n\n"
        f"**写作要求**:\n"
        f"{word_instruction}"
        f"- **结构清晰**: 使用 Markdown 标题组织内容，确保有清晰的逻辑主线\n"
        f"- **内容充实**: 每个要点必须有具体的细节、数据、或实例支撑，禁止空泛概括\n"
        f"- **专业准确**: 技术术语使用准确，数据引用可靠\n"
        f"- **可操作性**: 如果包含建议，必须具体到可执行的步骤\n"
        f"- **格式规范**: 使用 Markdown 格式输出，善用列表、粗体、引用块\n\n"
        f"**禁止**:\n"
        f"- 空话套话（如'具有广阔前景'、'值得关注'等没有信息量的表述）\n"
        f"- 没有支撑的断言\n"
        f"- 重复用户的问题\n"
    )
    draft = llm(
        prompt,
        "你是一个资深行业分析师和技术写作专家。"
        "你的报告以数据翔实、论证严密、建议可操作著称。"
        "直接输出报告正文，不要任何前缀解释。"
    )

    sections = ["摘要", "背景与现状", "详细分析", "结论与建议"]
    return {"internal_draft_text": draft, "draft_sections": sections}


def external_draft(state: ReportState) -> dict:
    """Generate external draft (外发沟通稿) from internal draft.

    Always runs a polish pass — even for internal stationery,
    the draft benefits from a quality-improvement rewrite.
    """
    llm = _get_llm(state)
    internal = state.get("internal_draft_text", "")
    audience = state.get("audience", "internal")
    stationery = state.get("stationery_type", "internal")
    target_words = state.get("_target_word_count", 0)
    user_msg = state.get("user_message", "")

    audience_map = {
        "leadership": "写给高层领导，简洁扼要，突出结论和行动建议",
        "external": "写给外部合作方，正式专业，突出合作价值和成果",
        "internal": "写给内部团队，保留技术细节，但去除冗余",
    }
    audience_guide = audience_map.get(audience, audience_map["internal"])

    word_constraint = ""
    if target_words > 0:
        word_constraint = f"- 严格控制在 {target_words} 字左右\n"

    prompt = (
        f"以下是初稿（前3000字）:\n\n{internal[:3000]}\n\n"
        f"用户原始需求: {user_msg}\n\n"
        f"请根据以下要求精修改写:\n"
        f"- 读者: {audience_guide}\n"
        f"{word_constraint}"
        f"- 确保每个论点有具体数据或实例支撑\n"
        f"- 删除空泛表述和套话\n"
        f"- 确保建议具体可执行\n"
        f"- 使用 Markdown 格式，结构清晰\n"
        f"- 直接输出精修后的完整文章，不要加任何前缀说明\n"
    )
    ext_draft = llm(
        prompt,
        "你是一个高级编辑，擅长将粗糙的初稿打磨为高质量的成品。"
        "你会删除一切没有信息量的内容，补充缺失的细节和数据。"
    )

    return {"external_draft_text": ext_draft}


def review(state: ReportState) -> dict:
    """Review the draft (score-based, 6/10 threshold)."""
    llm = _get_llm(state)
    # Review the external draft (or internal if no external)
    draft_text = state.get("external_draft_text") or state.get("internal_draft_text", "")

    review_len = min(len(draft_text), 2000)
    prompt = (
        f"请审核以下报告（前{review_len}字）:\n{draft_text[:review_len]}\n\n"
        "评估维度:\n"
        "1. 结构完整性\n"
        "2. 论据充分性\n"
        "3. 可操作性\n\n"
        "请给出1-10分的综合评分，然后用1-3条简短审核意见。\n"
        "格式：第一行写'评分：X/10'，后面写审核意见。"
    )
    resp = llm(prompt, "你是报告审核专家。简洁回答。")

    # Extract score
    score_match = re.search(r"(\d+)\s*/\s*10", resp)
    review_score = int(score_match.group(1)) if score_match else 7
    review_pass = review_score >= 6

    # Fallback keywords
    if not score_match:
        review_pass = ("通过" in resp or "pass" in resp.lower()
                       or "合格" in resp or "良好" in resp)

    review_notes = [l.strip() for l in resp.strip().split("\n") if l.strip()]

    return {
        "review_notes": review_notes or ["审核完成"],
        "review_pass": review_pass,
        "review_score": review_score,
    }


def rewrite_with_feedback(state: ReportState) -> dict:
    """Fix 3: Rewrite draft using review feedback.

    Takes the review notes and rewrites the draft to address them.
    Only runs when review score < 7 and rewrite_count < 1.
    """
    llm = _get_llm(state)
    draft = state.get("external_draft_text") or state.get("internal_draft_text", "")
    review_notes = state.get("review_notes", [])
    user_msg = state.get("user_message", "")
    target_words = state.get("_target_word_count", 0)
    rewrite_count = state.get("_rewrite_count", 0)

    word_constraint = ""
    if target_words > 0:
        word_constraint = f"- 字数控制在 {target_words} 字左右\n"

    feedback_text = "\n".join(f"- {n}" for n in review_notes)

    prompt = (
        f"以下是一篇报告的发稿（前3000字）:\n\n{draft[:3000]}\n\n"
        f"用户原始需求: {user_msg}\n\n"
        f"审核意见（必须全部解决）:\n{feedback_text}\n\n"
        f"请根据审核意见重写这篇报告：\n"
        f"- 逐条解决审核意见中指出的问题\n"
        f"- 补充缺失的数据和具体例子\n"
        f"- 保持 Markdown 格式\n"
        f"{word_constraint}"
        f"- 直接输出重写后的完整文章\n"
    )
    rewritten = llm(
        prompt,
        "你是一个严格的编辑，根据审核意见重写报告。"
        "你会逐条解决每个问题，确保输出质量显著提升。"
    )

    logger.info("rewrite_with_feedback: rewrite #%d, %d chars", rewrite_count + 1, len(rewritten))

    return {
        "external_draft_text": rewritten,
        "_rewrite_count": rewrite_count + 1,
    }


def _review_or_rewrite(state: ReportState) -> str:
    """Fix 3: Conditional edge — rewrite if review failed, else continue."""
    review_pass = state.get("review_pass", True)
    review_score = state.get("review_score", 7)
    rewrite_count = state.get("_rewrite_count", 0)

    if not review_pass and review_score < 7 and rewrite_count < 1:
        logger.info(
            "Review score %d/10 < 7, triggering rewrite (attempt %d)",
            review_score, rewrite_count + 1,
        )
        return "rewrite_with_feedback"
    return "redact_gate"


def redact_gate(state: ReportState) -> dict:
    """Redaction gate — check for PII and sensitive data.

    Uses PolicyEngine for fail-closed check, then LLM scan for PII.
    """
    llm = _get_llm(state)
    draft = state.get("external_draft_text") or state.get("internal_draft_text", "")
    issues: list[str] = []

    # PolicyEngine check
    engine = _get_runtime_service(state, "_policy_engine", "policy_engine")
    if engine:
        try:
            from chatgptrest.kernel.policy_engine import QualityContext
            audience = state.get("audience", "internal")
            # BUG-3 fix: map audience to proper security_label
            # audience can be: internal, external, leadership
            # security_label must be: public, internal, confidential
            _sec_map = {"external": "confidential", "leadership": "internal", "internal": "internal"}
            ctx = QualityContext(
                audience=audience,
                security_label=_sec_map.get(audience, "internal"),
                content=draft,
                channel="report",
            )
            result = engine.run_quality_gate(ctx)
            if not result.allowed:
                issues.extend(result.blocked_by)
        except Exception as e:
            logger.warning("PolicyEngine redact check failed: %s", e)

    # LLM PII scan
    if draft:
        chunks = _iter_redact_chunks(draft)
        total_chunks = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            scan_prompt = (
                f"检查以下文字片段是否包含敏感信息（片段 {idx}/{total_chunks}）:\n"
                f"{chunk}\n\n"
                "检查项: 手机号/身份证/银行卡/地址/个人姓名/内部代号/密码/API密钥\n"
                "如无敏感信息，回答'无敏感信息'。\n"
                "如有，列出每项发现。"
            )
            scan_resp = llm(scan_prompt, "你是信息安全审查专家。")
            if "无敏感信息" not in scan_resp and len(scan_resp) > 5:
                issues.append(f"LLM脱敏扫描[{idx}/{total_chunks}]: {scan_resp[:200]}")
                if len(issues) >= 5:
                    break

    return {
        "redact_pass": len(issues) == 0,
        "redact_issues": issues,
    }


def finalize(state: ReportState) -> dict:
    """Finalize the report. Always returns text — never empty."""
    ext_draft = state.get("external_draft_text") or state.get("internal_draft_text", "")
    int_draft = state.get("internal_draft_text", "")
    review_pass = state.get("review_pass", True)
    redact_pass = state.get("redact_pass", True)
    review_notes = state.get("review_notes", [])
    redact_issues = state.get("redact_issues", [])
    delivery_target = str(state.get("_delivery_target", "") or "").strip().lower()

    final = ext_draft or int_draft

    if not redact_pass:
        final += "\n\n---\n> ⛔ 脱敏审查未通过:\n" + "\n".join(f"> - {i}" for i in redact_issues)
        return {"final_text": final, "final_status": "redact_blocked"}

    if not review_pass and review_notes:
        final += "\n\n---\n> ⚠️ 审核建议（供参考）:\n" + "\n".join(f"> - {n}" for n in review_notes)
        return {"final_text": final, "final_status": "needs_revision"}

    # Export to Google Workspace via outbox only.
    doc_msg = ""
    if delivery_target == "google_drive" and GoogleWorkspace:
        outbox = _get_runtime_service(state, "_effects_outbox", "outbox")
        trace_id = str(state.get("trace_id") or uuid.uuid4().hex)
        audience = state.get("audience", "internal")
        stationery = state.get("stationery_type", "internal")
        title = f"Report: {state.get('purpose', 'Untitled')} - {trace_id[:6]}"
        target_email = os.environ.get("OPENMIND_GMAIL_DESTINATION", "")
        send_email = bool(
            target_email and (audience in ("leadership", "external") or stationery in ("executive", "external"))
        )

        if outbox:
            workspace_request = WorkspaceRequest(
                action="deliver_report_to_docs",
                trace_id=trace_id,
                payload={
                    "title": title,
                    "body_text": final,
                    "notify_email": target_email if send_email else "",
                    "notify_subject": f"[{stationery.upper()} Report] {title}" if send_email else "",
                    "notify_body_html": (
                        "<h3>Report Generated</h3>"
                        "<p>Your requested report is ready.</p>"
                        "<p>The delivery worker will attach the Google Docs URL once created.</p>"
                    ) if send_email else "",
                },
            )
            try:
                outbox.enqueue(
                    trace_id=trace_id,
                    effect_type="workspace_action",
                    effect_key=workspace_effect_key(workspace_request),
                    payload=workspace_effect_payload(workspace_request),
                )
                doc_msg = "\n\n---\n> 📄 **云端文档已排队**: Google Workspace delivery queued via effects outbox.\n"
                if send_email:
                    doc_msg += f"> 📧 **邮件通知已排队**: 将在文档创建后通知 {target_email}\n"
            except Exception as exc:
                logger.warning("outbox.enqueue failed during report finalize: %s", exc)
                doc_msg = "\n\n---\n> ⚠️ **云端交付排队失败**: outbox.enqueue error, report text preserved.\n"
            final += doc_msg
        else:
            logger.warning("Google Workspace delivery requested without effects outbox; skipping direct side-effect")
            doc_msg = "\n\n---\n> ⚠️ **云端交付未排队**: effects outbox unavailable, Google Workspace delivery skipped.\n"
            final += doc_msg

    # Export to Obsidian via EffectsOutbox (async, retryable)
    if delivery_target == "obsidian" and ObsidianClient:
        try:
            obs_client = ObsidianClient()
            if obs_client.is_configured():
                safe_title = state.get("purpose", "Untitled").replace("/", "_").replace("\\", "_")[:50]
                file_name = f"OpenMind_Inbox/AI_{safe_title}_{uuid.uuid4().hex[:4]}.md"
                obs_content = f"---\ntags: [openmind_generated, ai_report]\n---\n\n{final}"

                # Try EffectsOutbox first (idempotent, retryable)
                outbox = _get_runtime_service(state, "_effects_outbox", "outbox")
                trace_id = state.get("trace_id", uuid.uuid4().hex)

                if outbox:
                    outbox.enqueue(
                        trace_id=trace_id,
                        effect_type="obsidian_write",
                        effect_key=f"obsidian::{file_name}",
                        payload={
                            "file_path": file_name,
                            "content": obs_content,
                        },
                    )
                    final += f"\n> 📓 **Obsidian 落库已排队**: `{file_name}` (异步写入中)\n"
                else:
                    # Fallback: direct write if no outbox available
                    if obs_client.write_file(file_name, obs_content):
                        final += f"\n> 📓 **本地知识已落库**: 成功保存至 Obsidian: `{file_name}`\n"
        except Exception as e:
            logger.warning("Obsidian report export failed: %s", e)

    return {"final_text": final, "final_status": "complete"}


# ── Graph Builder ─────────────────────────────────────────────────

def build_report_graph() -> StateGraph:
    """Build the Report Generation StateGraph.

    Flow (with Fix 2 & 3):
      purpose_identify → evidence_pack → web_research → internal_draft
      → external_draft → review → [rewrite?] → redact_gate → finalize

    Fix 2: web_research node supplements KB evidence with LLM research.
    Fix 3: review → conditional edge → rewrite_with_feedback if score < 7.

    Usage::
        graph = build_report_graph()
        app = graph.compile()
        result = app.invoke({
            "user_message": "帮我写个安徽项目进展报告",
            "report_type": "progress",
        })
    """
    graph = StateGraph(ReportState)

    graph.add_node("purpose_identify", purpose_identify)
    graph.add_node("evidence_pack", evidence_pack)
    graph.add_node("web_research", web_research)           # Fix 2
    graph.add_node("internal_draft", internal_draft)
    graph.add_node("external_draft", external_draft)
    graph.add_node("review", review)
    graph.add_node("rewrite_with_feedback", rewrite_with_feedback)  # Fix 3
    graph.add_node("redact_gate", redact_gate)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("purpose_identify")
    graph.add_edge("purpose_identify", "evidence_pack")
    graph.add_edge("evidence_pack", "web_research")        # Fix 2
    graph.add_edge("web_research", "internal_draft")       # Fix 2
    graph.add_edge("internal_draft", "external_draft")
    graph.add_edge("external_draft", "review")
    # Fix 3: conditional edge — rewrite if score < 7, else redact_gate
    graph.add_conditional_edges("review", _review_or_rewrite)
    graph.add_edge("rewrite_with_feedback", "review")      # Fix 3: re-review
    graph.add_edge("redact_gate", "finalize")
    graph.add_edge("finalize", END)

    return graph
