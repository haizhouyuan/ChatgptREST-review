"""Auto-trigger helpers for durable work-memory capture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any


@dataclass(frozen=True)
class AutoWorkMemoryCapture:
    category: str
    title: str
    summary: str
    content: str
    source_ref: str
    object_payload: dict[str, Any]
    confidence: float
    trigger: str

    def to_capture_request(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "capture_answer": False,
            "capture_message": False,
            "source_ref": self.source_ref,
            "require_complete_identity": False,
            "category": self.category,
            "security_label": "internal",
            "confidence": self.confidence,
            "object_payload": dict(self.object_payload),
            "auto_generated": True,
            "trigger": self.trigger,
        }


_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*$")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]|(?:\d+[\.\)]))\s+(.*\S)\s*$")
_CLEAN_RE = re.compile(r"[`*_#]+")
_WHITESPACE_RE = re.compile(r"\s+")
_TRIAGE_HEADINGS = {
    "meeting_context": {"meeting_context", "meeting context", "会议背景", "会议上下文", "会议情况", "背景"},
    "key_points": {"key_points", "key points", "关键要点", "关键点", "要点", "重点"},
    "decisions": {"decisions", "decision", "决策", "决定", "结论"},
    "action_items": {"action_items", "action items", "actions", "行动项", "待办", "下一步", "next steps"},
    "open_questions": {"open_questions", "open questions", "未决问题", "待确认", "待澄清", "开放问题"},
}
_PARTICIPANT_LABELS = ("participants", "attendees", "参会", "与会", "参会人")
_PROJECT_LABELS = ("project", "projects", "项目")


def plan_auto_work_memory_capture(
    *,
    session_id: str,
    trace_id: str,
    route: str,
    status: str,
    answer: str,
    message: str,
    agent_id: str,
    scenario_pack: dict[str, Any] | None,
    next_action: dict[str, Any] | None,
) -> AutoWorkMemoryCapture | None:
    normalized_status = str(status or "").strip().lower()
    normalized_profile = str(dict(scenario_pack or {}).get("profile") or "").strip().lower()
    if normalized_status == "completed" and normalized_profile == "meeting_summary":
        triage = _plan_post_call_triage(
            session_id=session_id,
            trace_id=trace_id,
            route=route,
            answer=answer,
        )
        if triage is not None:
            return triage
    if normalized_status in {"needs_followup", "needs_input"}:
        return _plan_handoff(
            session_id=session_id,
            trace_id=trace_id,
            route=route,
            answer=answer,
            message=message,
            agent_id=agent_id,
            next_action=next_action or {},
        )
    return None


def _plan_post_call_triage(
    *,
    session_id: str,
    trace_id: str,
    route: str,
    answer: str,
) -> AutoWorkMemoryCapture | None:
    clean_answer = str(answer or "").strip()
    if not clean_answer:
        return None
    sections = _extract_markdown_sections(clean_answer)
    key_points = _extract_items(sections.get("key_points", ""))
    decisions = _extract_items(sections.get("decisions", ""))
    action_items = _extract_items(sections.get("action_items", ""))
    open_questions = _extract_items(sections.get("open_questions", ""))
    if not any((key_points, decisions, action_items, open_questions)):
        return None

    meeting_context = sections.get("meeting_context", "")
    participants = _extract_labeled_values(meeting_context, _PARTICIPANT_LABELS)
    project_refs = _extract_labeled_values(meeting_context, _PROJECT_LABELS)
    summary_items = decisions[:2] or action_items[:2] or key_points[:2] or open_questions[:2]
    summary = "; ".join(summary_items)[:280] or "Post-call triage captured from meeting summary."
    suffix = (trace_id or session_id or "call").replace(":", "-")[:48]
    object_payload = {
        "call_id": f"triage-{suffix}",
        "call_date": _now_iso(),
        "participants": participants,
        "new_facts": key_points,
        "intended_actions": action_items,
        "ledger_update_candidates": decisions + open_questions,
        "project_refs": project_refs,
        "review_status": "approved",
    }
    return AutoWorkMemoryCapture(
        category="post_call_triage",
        title="Advisor post-call triage",
        summary=summary,
        content=clean_answer,
        source_ref=f"advisor-agent://session/{session_id}/{route or 'turn'}/post-call-triage",
        object_payload=object_payload,
        confidence=0.9,
        trigger="meeting_summary_post_call_triage",
    )


def _plan_handoff(
    *,
    session_id: str,
    trace_id: str,
    route: str,
    answer: str,
    message: str,
    agent_id: str,
    next_action: dict[str, Any],
) -> AutoWorkMemoryCapture | None:
    base_text = str(answer or "").strip() or str(message or "").strip()
    if not base_text and not next_action:
        return None

    safe_hint = str(next_action.get("safe_hint") or "").strip()
    next_action_type = str(next_action.get("type") or "").strip()
    open_loops: list[str] = []
    if safe_hint:
        open_loops.append(safe_hint)
    clarify = dict(next_action.get("clarify_diagnostics") or {}) if isinstance(next_action.get("clarify_diagnostics"), dict) else {}
    missing_fields = [str(item).strip() for item in list(clarify.get("missing_fields") or []) if str(item).strip()]
    if missing_fields:
        open_loops.append(f"missing_fields: {', '.join(missing_fields)}")
    if next_action_type:
        open_loops.append(f"next_action_type: {next_action_type}")

    changes_made = _extract_items(base_text)[:3]
    summary = safe_hint or _clip_text(base_text, 160)
    next_pickup = safe_hint or next_action_type or "Resume this session and resolve the pending follow-up."
    suffix = (trace_id or session_id or "handoff").replace(":", "-")[:48]
    object_payload = {
        "handoff_id": f"handoff-{suffix}",
        "from_agent": str(agent_id or "advisor").strip() or "advisor",
        "from_session": str(session_id or "").strip() or "unknown-session",
        "current_situation": _clip_text(base_text, 280) or "Pending follow-up requires pickup.",
        "changes_made": changes_made,
        "open_loops": open_loops[:5],
        "next_pickup": next_pickup[:280],
        "review_status": "approved",
    }
    return AutoWorkMemoryCapture(
        category="handoff",
        title="Advisor session handoff",
        summary=summary or "Pending follow-up requires a session handoff.",
        content=base_text or next_pickup,
        source_ref=f"advisor-agent://session/{session_id}/{route or 'turn'}/handoff",
        object_payload=object_payload,
        confidence=0.88,
        trigger="session_handoff_followup",
    )


def _extract_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in str(text or "").splitlines():
        line = raw_line.rstrip()
        match = _HEADING_RE.match(line)
        if match:
            current = _canonical_heading(match.group(2))
            sections.setdefault(current, [])
            continue
        if current:
            sections.setdefault(current, []).append(line)
    return {
        key: "\n".join(lines).strip()
        for key, lines in sections.items()
        if key
    }


def _canonical_heading(raw: str) -> str:
    cleaned = _WHITESPACE_RE.sub(" ", _CLEAN_RE.sub(" ", str(raw or "").strip().lower())).strip()
    underscored = cleaned.replace(" ", "_")
    for canonical, aliases in _TRIAGE_HEADINGS.items():
        if cleaned in aliases or underscored in aliases:
            return canonical
    return underscored


def _extract_items(text: str) -> list[str]:
    items: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        bullet = _BULLET_RE.match(line)
        candidate = bullet.group(1).strip() if bullet else line
        if candidate:
            items.append(candidate)
    return items


def _extract_labeled_values(text: str, labels: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    for raw_line in _extract_items(text):
        lower = raw_line.lower()
        for label in labels:
            marker = f"{label}:"
            marker_cn = f"{label}："
            if marker in lower:
                value = raw_line.split(":", 1)[1]
                items.extend(_split_people_or_refs(value))
                break
            if marker_cn in lower:
                value = raw_line.split("：", 1)[1]
                items.extend(_split_people_or_refs(value))
                break
            if lower.startswith(label):
                remainder = raw_line[len(label):].lstrip(":： ").strip()
                items.extend(_split_people_or_refs(remainder))
                break
    return list(dict.fromkeys(item for item in items if item))


def _split_people_or_refs(raw: str) -> list[str]:
    parts = re.split(r"[,，、;/]\s*", str(raw or "").strip())
    return [part.strip() for part in parts if part.strip()]


def _clip_text(text: str, limit: int) -> str:
    compact = _WHITESPACE_RE.sub(" ", str(text or "").strip())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
