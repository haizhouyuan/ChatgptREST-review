"""Shared ingest-quality heuristics for EvoMap knowledge atoms."""

from __future__ import annotations

from collections.abc import Mapping

from chatgptrest.evomap.knowledge.schema import Atom, PromotionStatus


GENERIC_HEADING_QUESTIONS = {
    "files",
    "file",
    "test results",
    "automated tests",
    "manual verification",
    "user review required",
    "problem",
    "scope",
    "summary",
    "results",
    "结论",
    "总结",
}
PATH_BLACKLIST_SEGMENTS = (
    "/.venv/",
    "\\.venv\\",
    "__pycache__",
    "node_modules",
)
LOW_SIGNAL_ACTIVITY_EVENT_TYPES = {
    "tool.completed",
    "agent.tool.use",
}


def classify_atom_ingest_rejections(atom: Atom) -> list[str]:
    """Return deterministic ingest-time rejection reasons for an atom."""
    reasons: list[str] = []
    question = _normalize_text(atom.question)
    canonical_question = _normalize_text(atom.canonical_question)
    answer = str(atom.answer or "").strip()
    answer_lower = answer.lower()

    if _has_path_blacklist_hit(question=question, canonical_question=canonical_question, answer=answer_lower):
        reasons.append("path_blacklist")
    if question in GENERIC_HEADING_QUESTIONS or canonical_question in GENERIC_HEADING_QUESTIONS:
        reasons.append("generic_heading")
    if len(answer) < 30:
        reasons.append("short_answer")
    return reasons


def classify_archive_families(row: Mapping[str, object]) -> list[str]:
    """Return archive-family labels for an atom row-like mapping."""
    families: list[str] = []
    canonical_question = _normalize_text(row.get("canonical_question"))
    if canonical_question == "activity: tool.completed":
        families.append("low_signal_tool_completed")
    question = _normalize_text(row.get("question"))
    answer = str(row.get("answer") or "").strip().lower()
    if _has_path_blacklist_hit(question=question, canonical_question=canonical_question, answer=answer):
        families.append("path_blacklist")
    if question in GENERIC_HEADING_QUESTIONS or canonical_question in GENERIC_HEADING_QUESTIONS:
        families.append("generic_heading")
    return families


def default_activity_promotion(event_type: str) -> tuple[str, str]:
    event_name = _normalize_text(event_type)
    if event_name in LOW_SIGNAL_ACTIVITY_EVENT_TYPES:
        return PromotionStatus.ARCHIVED.value, "low_signal_activity"
    return PromotionStatus.STAGED.value, "activity_ingest"


def _normalize_text(value: object) -> str:
    return str(value or "").strip().lower()


def _has_path_blacklist_hit(*, question: str, canonical_question: str, answer: str) -> bool:
    if any(segment in question or segment in canonical_question for segment in PATH_BLACKLIST_SEGMENTS):
        return True
    if any(segment in answer for segment in PATH_BLACKLIST_SEGMENTS):
        return question in GENERIC_HEADING_QUESTIONS
    return False
