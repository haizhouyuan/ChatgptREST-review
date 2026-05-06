from __future__ import annotations

from typing import Any, Mapping

from chatgptrest.kernel.memory_manager import MemoryManager, MemoryRecord, MemorySource, MemoryTier, SourceType


INTERACTION_LEARNING_CATEGORY = "user_correction"
_CORRECTION_MARKERS = (
    "不是让你",
    "不是在",
    "我的意思不是",
    "我不是让你",
    "我觉得不够",
    "还要提高到codex",
    "要高质量",
    "该反馈反馈",
    "最终落实成任务闭环",
    "质量不够高",
    "我要的不是这个",
    "重点不对",
    "先回复对方",
    "先告诉我怎么回对方",
    "太长了",
    "太短了",
    "简单点",
    "展开一点",
    "too long",
    "too short",
    "not what i asked",
    "reply first",
    "high quality",
)
_PREFERENCE_KEYS = {
    "raw_ingress_mode",
    "quality_bar",
    "preferred_executor_family",
    "closure_style",
    "brevity_preference",
    "depth_preference",
    "focus_preference",
    "reply_first_preference",
}
_PREFERENCE_META_KEY = "_preference_meta"


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(str(phrase).strip().lower() in lowered for phrase in phrases if str(phrase).strip())


def extract_user_correction_signals(message: str) -> dict[str, Any] | None:
    text = str(message or "").strip()
    haystack = text.lower()
    if not text or not any(marker in text or marker in haystack for marker in _CORRECTION_MARKERS):
        return None

    payload: dict[str, Any] = {"kind": "user_correction", "source_message": text[:1000]}
    if "不是让你" in text or "我的意思不是" in text or "我不是让你" in text or "not what i asked" in haystack:
        payload["raw_ingress_mode"] = "preserve_user_wording"
    if (
        "要高质量" in text
        or "质量不够高" in text
        or "提高到codex" in haystack
        or "codex 也就是你的高度" in text
        or "high quality" in haystack
    ):
        payload["quality_bar"] = "codex_grade"
        payload["preferred_executor_family"] = "codex"
    if "最终落实成任务闭环" in text or "该反馈反馈" in text:
        payload["closure_style"] = "task_closure"
    if _contains_any(text, ("太长了", "简单点", "简短一点", "too long")):
        payload["brevity_preference"] = "short"
    if _contains_any(text, ("太短了", "展开一点", "详细一点", "too short")):
        payload["depth_preference"] = "detailed"
    if _contains_any(text, ("重点不对", "我要的不是这个", "focus is wrong", "not what i asked")):
        payload["focus_preference"] = "tighten_focus"
    if _contains_any(text, ("先回复对方", "先告诉我怎么回对方", "reply first")):
        payload["reply_first_preference"] = "reply_first"
    return payload if len(payload) > 2 else None


def merge_learning_payload(
    existing: Mapping[str, Any] | None,
    incoming: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(existing or {})
    incoming_payload = dict(incoming or {})
    meta = dict(merged.get(_PREFERENCE_META_KEY) or {})
    for key, value in incoming_payload.items():
        if value in ("", None, [], {}):
            continue
        if key in _PREFERENCE_KEYS:
            pref_meta = dict(meta.get(key) or {})
            counts = dict(pref_meta.get("counts") or {})
            value_key = str(value)
            counts[value_key] = int(counts.get(value_key) or 0) + 1
            pref_meta["counts"] = counts
            pref_meta["last_value"] = value_key
            pref_meta["last_source_message"] = str(incoming_payload.get("source_message") or "")[:200]
            meta[key] = pref_meta
            winner = max(
                counts.items(),
                key=lambda item: (int(item[1]), 1 if item[0] == value_key else 0),
            )[0]
            merged[key] = winner
            continue
        merged[key] = value
    if meta:
        merged[_PREFERENCE_META_KEY] = meta
    return merged


def interaction_learning_key(*, account_id: str, thread_id: str) -> str:
    return f"user_correction:{str(account_id or '').strip()}:{str(thread_id or '').strip()}"


def load_interaction_learning(
    memory: MemoryManager | None,
    *,
    account_id: str,
    thread_id: str,
) -> dict[str, Any] | None:
    if memory is None:
        return None
    key = interaction_learning_key(account_id=account_id, thread_id=thread_id)
    record = memory.get_by_key(key)
    if record is None:
        return None
    payload = dict(record.value or {})
    payload["record_id"] = str(record.record_id or "")
    payload["key"] = key
    return payload or None


def record_interaction_learning(
    memory: MemoryManager | None,
    *,
    account_id: str,
    thread_id: str,
    session_id: str,
    agent_id: str,
    role_id: str,
    project_id: str,
    learning_payload: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if memory is None:
        return None
    incoming = dict(learning_payload or {})
    if not incoming:
        return None
    key = interaction_learning_key(account_id=account_id, thread_id=thread_id)
    existing = load_interaction_learning(memory, account_id=account_id, thread_id=thread_id)
    merged = merge_learning_payload(existing, incoming)
    merged["account_id"] = str(account_id or "").strip()
    merged["thread_id"] = str(thread_id or "").strip()
    if session_id:
        merged["last_session_id"] = str(session_id or "").strip()
    source = MemorySource(
        type=SourceType.USER_INPUT.value,
        agent=str(agent_id or "openclaw"),
        role=str(role_id or ""),
        session_id=str(session_id or ""),
        account_id=str(account_id or ""),
        thread_id=str(thread_id or ""),
        project_id=str(project_id or ""),
        task_id=str(session_id or ""),
    ).to_dict()
    record_id = memory.stage_and_promote(
        MemoryRecord(
            category=INTERACTION_LEARNING_CATEGORY,
            key=key,
            value=merged,
            confidence=1.0,
            source=source,
            evidence_span=str(incoming.get("source_message") or "")[:500],
        ),
        MemoryTier.META,
        "interaction learning updated",
    )
    merged["record_id"] = str(record_id or "")
    merged["key"] = key
    return merged
