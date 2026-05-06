from __future__ import annotations

import json
import re


_DEEP_RESEARCH_STUB_RE = re.compile(
    r"(implicit_link|connector_openai_deep_research|openai_deep_research)",
    re.I,
)


_DEEP_RESEARCH_ACK_RE = re.compile(
    r"("
    r"我将.*?(深入研究|深度研究)|"
    r"我将为你.*?(深入研究|深度研究)|"
    r"我将.*?(开始|开展|进行|马上|立即|立刻).*?(研究|调研|调查)|"
    r"我会.*?(开始|开展|进行|马上|立即|立刻).*?(研究|调研|调查)|"
    r"(深研|深入研究|深度研究|深入调研|深度调研)|"
    r"我会在.*?研究完成后|"
    r"我会在研究完成后向你汇报|"
    r"研究完成后.*?我会|"
    r"我(已|已经)将.*?纳入研究|"
    r"(已|已经)将.*?纳入研究|"
    r"报告.*?(准备好|准备完成|完成|写好).{0,60}(后|之后).{0,60}(发给|发送|给你|提供|呈现|汇报|报告|请查收|查收)|"
    r"(稍后|稍等|请稍等|请耐心等待).{0,60}(请查收|查收|给你|发给你|发送给你|提供|呈现|汇报|报告)|"
    r"稍后请查收|"
    r"报告准备好后.{0,60}(请查收|给你|发给你|发送给你|提供|呈现)|"
    r"研究完成后我会.*?(呈现|提供|汇报|报告)|"
    r"研究完成后.{0,60}(将|会).{0,60}(一次性)?(输出|给出|提供|呈现|汇报|报告)|"
    r"我会.*?(第一时间|尽快).*?(呈现|提供|汇报|报告)|"
    r"完成后我会通知你|"
    r"期间你可以继续与我交流|"
    r"期间你可以.{0,60}(随时)?(继续)?(与我交流|和我交流)|"
    r"你可以.{0,60}(随时)?(继续)?(与我交流|和我交流|继续提问)|"
    r"(I( will|'ll) .*?(research|look into|investigate))|"
    r"(I'll .*?(research|look into|investigate))|"
    r"(I'll get back to you)|"
    r"(I will get back to you)"
    r")",
    re.I | re.S,
)


_DEEP_RESEARCH_CONFIRM_RE = re.compile(
    r"("
    r"Reply with OK|"
    r"reply with ok|"
    r"回复.*?OK|"
    r"在我开始研究前|"
    r"在开始研究前|"
    r"拟定.*?(方案|计划)|"
    r"如果你需要.*?(改动|调整|修改|更新)|"
    r"如果没问题.*?(我就|我将).*?(开始研究|开始深入研究|开始深度研究)|"
    r"before I begin|"
    r"before I start|"
    r"if you.*?(changes|adjustments).*?(tell me|let me know)|"
    r"please confirm|"
    r"请确认|"
    r"请在.*?开始.*?前"
    r")",
    re.I | re.S,
)


_DEEP_RESEARCH_WIDGET_FAILURE_RE = re.compile(
    r"("
    r"Research failed|"
    r"研究失败|"
    r"调研失败|"
    r"深入研究失败|"
    r"Something went wrong|"
    r"Try again|"
    r"Please try again"
    r")",
    re.I | re.S,
)


def _deep_research_widget_failure_reason(text: str) -> str | None:
    trimmed = (text or "").strip()
    if not trimmed:
        return None
    # The failure banner is typically very short; avoid false positives from real reports.
    if len(trimmed) > 400:
        return None
    if not _DEEP_RESEARCH_WIDGET_FAILURE_RE.search(trimmed):
        return None
    first = trimmed.splitlines()[0].strip()
    return (first[:200] if first else "Deep Research failed")


def _looks_like_gemini_deep_research_plan_stub(text: str) -> bool:
    trimmed = (text or "").strip()
    if not trimmed or len(trimmed) > 1600:
        return False
    required = (
        "我拟定了一个研究方案" in trimmed
        or "只需要几分钟就可以准备好" in trimmed
        or "生成报告" in trimmed
    )
    if not required:
        return False
    actions = 0
    for token in ("修改方案", "开始研究", "不使用 Deep Research"):
        if token in trimmed:
            actions += 1
    return actions >= 2


def _classify_deep_research_answer(text: str) -> str:
    trimmed = (text or "").strip()
    if not trimmed:
        return "in_progress"

    if (
        len(trimmed) <= 3000
        and (trimmed.lstrip().startswith("{") or trimmed.lstrip().startswith("["))
        and _DEEP_RESEARCH_STUB_RE.search(trimmed)
    ):
        return "in_progress"

    # New Deep Research UI can emit an embedded-app "implicit_link" stub in the transcript/export,
    # e.g. `{"path": "/Deep Research App/implicit_link::connector_openai_deep_research/start", ...}`.
    # This is not the final report content, so treat it as in_progress and let wait/export collect the
    # real output.
    if len(trimmed) <= 2500 and ("implicit_link" in trimmed or "connector_openai_deep_research" in trimmed):
        if trimmed.lstrip().startswith("{") and trimmed.rstrip().endswith("}"):
            try:
                obj = json.loads(trimmed)
            except Exception:
                obj = None
            if isinstance(obj, dict):
                path = str(obj.get("path") or "")
                if "connector_openai_deep_research" in path or "Deep Research" in path:
                    return "in_progress"
        if "connector_openai_deep_research" in trimmed:
            return "in_progress"

    if _looks_like_gemini_deep_research_plan_stub(trimmed):
        return "needs_followup"

    if len(trimmed) <= 900 and _DEEP_RESEARCH_CONFIRM_RE.search(trimmed):
        return "needs_followup"

    question_marks = len(re.findall(r"[?？]", trimmed))
    if question_marks >= 2 and len(trimmed) <= 1600:
        return "needs_followup"
    if question_marks >= 1 and len(trimmed) <= 800 and re.search(r"(能否|是否|请|补充|确认|clarif)", trimmed, re.I):
        return "needs_followup"

    if len(trimmed) <= 1200 and _DEEP_RESEARCH_ACK_RE.search(trimmed):
        return "in_progress"

    return "completed"


def _classify_non_deep_research_answer(text: str) -> str:
    trimmed = (text or "").strip()
    if not trimmed:
        return "in_progress"
    return "completed"


_TRANSIENT_ASSISTANT_ERROR_RE = re.compile(
    r"("
    r"Error in message stream|"
    r"message stream error|"
    r"Network connection lost|"
    r"Attempting to reconnect|"
    r"Something went wrong|"
    r"There was an error"
    r")",
    re.I,
)


def _looks_like_transient_assistant_error(text: str) -> bool:
    trimmed = (text or "").strip()
    if not trimmed:
        return False
    if len(trimmed) > 300:
        return False
    return bool(_TRANSIENT_ASSISTANT_ERROR_RE.search(trimmed))
