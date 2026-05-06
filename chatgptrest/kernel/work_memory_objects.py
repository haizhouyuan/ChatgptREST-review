from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Mapping


WORK_MEMORY_SCHEMA_VERSION = "v1"
WORK_MEMORY_CATEGORY_TO_KIND = {
    "decision_ledger": "decision_ledger",
    "active_project": "active_project",
    "post_call_triage": "post_call_triage",
    "handoff": "handoff",
}
WORK_MEMORY_ACTIVE_REVIEW_STATUSES = {"approved", "active"}
_ALLOWED_REVIEW_STATUSES = {
    "staged",
    "approved",
    "active",
    "rejected",
    "superseded",
}


class WorkMemoryValidationError(ValueError):
    def __init__(self, message: str, *, blocked_by: str = "validation") -> None:
        super().__init__(message)
        self.blocked_by = blocked_by


def is_work_memory_category(category: str) -> bool:
    return str(category or "").strip() in WORK_MEMORY_CATEGORY_TO_KIND


def canonical_kind_for_category(category: str) -> str:
    normalized = str(category or "").strip()
    kind = WORK_MEMORY_CATEGORY_TO_KIND.get(normalized, "")
    if not kind:
        raise WorkMemoryValidationError(f"unsupported work-memory category: {normalized}")
    return kind


@dataclass(kw_only=True)
class WorkMemoryObject:
    kind: str
    schema_version: str = WORK_MEMORY_SCHEMA_VERSION
    object_id: str = ""
    review_status: str = "staged"
    source_refs: list[str] = field(default_factory=list)
    valid_from: str = ""
    valid_to: str = ""
    superseded_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(kw_only=True)
class DecisionLedgerObject(WorkMemoryObject):
    decision_id: str = ""
    statement: str = ""
    domain: str = ""
    confidence: float = 0.0
    supersedes_decision_id: str = ""


@dataclass(kw_only=True)
class ActiveProjectObject(WorkMemoryObject):
    project_id: str = ""
    name: str = ""
    phase: str = ""
    status: str = ""
    blockers: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    key_files: list[str] = field(default_factory=list)
    last_updated: str = ""
    owner: str = ""


@dataclass(kw_only=True)
class PostCallTriageObject(WorkMemoryObject):
    call_id: str = ""
    call_date: str = ""
    participants: list[str] = field(default_factory=list)
    your_positions: list[str] = field(default_factory=list)
    counterparty_positions: list[str] = field(default_factory=list)
    new_facts: list[str] = field(default_factory=list)
    intended_actions: list[str] = field(default_factory=list)
    ledger_update_candidates: list[str] = field(default_factory=list)
    project_refs: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class HandoffObject(WorkMemoryObject):
    handoff_id: str = ""
    created_at: str = ""
    from_agent: str = ""
    from_session: str = ""
    project_refs: list[str] = field(default_factory=list)
    current_situation: str = ""
    changes_made: list[str] = field(default_factory=list)
    open_loops: list[str] = field(default_factory=list)
    next_pickup: str = ""
    do_not_repeat: list[str] = field(default_factory=list)


_WORK_MEMORY_CLASSES = {
    "decision_ledger": DecisionLedgerObject,
    "active_project": ActiveProjectObject,
    "post_call_triage": PostCallTriageObject,
    "handoff": HandoffObject,
}


def build_work_memory_object(
    category: str,
    payload: Mapping[str, Any],
    *,
    fallback_source_ref: str = "",
) -> WorkMemoryObject:
    if not isinstance(payload, Mapping):
        raise WorkMemoryValidationError("work-memory payload must be an object")

    kind = canonical_kind_for_category(category)
    object_cls = _WORK_MEMORY_CLASSES[kind]
    normalized = _normalize_payload(dict(payload), kind=kind, fallback_source_ref=fallback_source_ref)
    allowed_fields = {field_def.name for field_def in fields(object_cls)}
    init_kwargs = {key: value for key, value in normalized.items() if key in allowed_fields}
    obj = object_cls(**init_kwargs)
    return validate_work_memory_object(obj)


def validate_work_memory_object(obj: WorkMemoryObject) -> WorkMemoryObject:
    if str(obj.kind or "").strip() not in _WORK_MEMORY_CLASSES:
        raise WorkMemoryValidationError(f"unsupported work-memory kind: {obj.kind}")
    if str(obj.schema_version or "").strip() != WORK_MEMORY_SCHEMA_VERSION:
        raise WorkMemoryValidationError(
            f"unsupported schema_version: {obj.schema_version}",
            blocked_by="schema_version",
        )
    review_status = str(obj.review_status or "").strip().lower()
    if review_status not in _ALLOWED_REVIEW_STATUSES:
        raise WorkMemoryValidationError(f"invalid review_status: {obj.review_status}")
    obj.review_status = review_status
    obj.source_refs = _normalize_text_list(obj.source_refs)
    if not obj.source_refs:
        raise WorkMemoryValidationError("source_refs is required", blocked_by="missing_source_refs")
    obj.valid_from = str(obj.valid_from or _now_iso()).strip()
    obj.valid_to = str(obj.valid_to or "").strip()
    obj.superseded_by = str(obj.superseded_by or "").strip()

    if isinstance(obj, DecisionLedgerObject):
        obj.decision_id = _required_text(obj.decision_id, "decision_id")
        obj.object_id = obj.object_id or obj.decision_id
        obj.statement = _required_text(obj.statement, "statement")
        obj.domain = _required_text(obj.domain, "domain")
        obj.supersedes_decision_id = str(obj.supersedes_decision_id or "").strip()
        try:
            obj.confidence = max(0.0, min(float(obj.confidence), 1.0))
        except Exception as exc:
            raise WorkMemoryValidationError("confidence must be numeric") from exc
        return obj

    if isinstance(obj, ActiveProjectObject):
        obj.project_id = _required_text(obj.project_id, "project_id")
        obj.object_id = obj.object_id or obj.project_id
        obj.name = _required_text(obj.name, "name")
        obj.phase = _required_text(obj.phase, "phase")
        obj.status = _required_text(obj.status, "status")
        obj.blockers = _normalize_text_list(obj.blockers)
        obj.next_steps = _normalize_text_list(obj.next_steps)
        obj.key_files = _normalize_text_list(obj.key_files)
        obj.last_updated = str(obj.last_updated or obj.valid_from).strip()
        obj.owner = str(obj.owner or "").strip()
        return obj

    if isinstance(obj, PostCallTriageObject):
        obj.call_id = _required_text(obj.call_id, "call_id")
        obj.object_id = obj.object_id or obj.call_id
        obj.call_date = _required_text(obj.call_date, "call_date")
        obj.participants = _normalize_text_list(obj.participants)
        obj.your_positions = _normalize_text_list(obj.your_positions)
        obj.counterparty_positions = _normalize_text_list(obj.counterparty_positions)
        obj.new_facts = _normalize_text_list(obj.new_facts)
        obj.intended_actions = _normalize_text_list(obj.intended_actions)
        obj.ledger_update_candidates = _normalize_text_list(obj.ledger_update_candidates)
        obj.project_refs = _normalize_text_list(obj.project_refs)
        return obj

    if isinstance(obj, HandoffObject):
        obj.handoff_id = _required_text(obj.handoff_id, "handoff_id")
        obj.object_id = obj.object_id or obj.handoff_id
        obj.created_at = str(obj.created_at or obj.valid_from).strip()
        obj.from_agent = _required_text(obj.from_agent, "from_agent")
        obj.from_session = _required_text(obj.from_session, "from_session")
        obj.project_refs = _normalize_text_list(obj.project_refs)
        obj.current_situation = _required_text(obj.current_situation, "current_situation")
        obj.changes_made = _normalize_text_list(obj.changes_made)
        obj.open_loops = _normalize_text_list(obj.open_loops)
        obj.next_pickup = _required_text(obj.next_pickup, "next_pickup")
        obj.do_not_repeat = _normalize_text_list(obj.do_not_repeat)
        return obj

    raise WorkMemoryValidationError(f"unsupported work-memory object type: {type(obj).__name__}")


def work_memory_is_active(obj_or_payload: WorkMemoryObject | Mapping[str, Any]) -> bool:
    review_status = ""
    if isinstance(obj_or_payload, WorkMemoryObject):
        review_status = obj_or_payload.review_status
    elif isinstance(obj_or_payload, Mapping):
        review_status = str(obj_or_payload.get("review_status") or "")
    return str(review_status).strip().lower() in WORK_MEMORY_ACTIVE_REVIEW_STATUSES


def _normalize_payload(
    payload: dict[str, Any],
    *,
    kind: str,
    fallback_source_ref: str,
) -> dict[str, Any]:
    normalized = dict(payload)
    payload_kind = str(normalized.get("kind") or kind).strip()
    if payload_kind != kind:
        raise WorkMemoryValidationError(
            f"kind/category mismatch: expected {kind}, got {payload_kind}",
            blocked_by="kind_mismatch",
        )
    normalized["kind"] = kind
    normalized["schema_version"] = str(
        normalized.get("schema_version") or WORK_MEMORY_SCHEMA_VERSION
    ).strip()
    source_refs = _normalize_text_list(normalized.get("source_refs"))
    if not source_refs and fallback_source_ref:
        source_refs = [fallback_source_ref]
    normalized["source_refs"] = source_refs
    normalized["review_status"] = str(normalized.get("review_status") or "staged").strip()
    normalized["valid_from"] = str(normalized.get("valid_from") or "").strip()
    normalized["valid_to"] = str(normalized.get("valid_to") or "").strip()
    normalized["superseded_by"] = str(normalized.get("superseded_by") or "").strip()

    for list_field in (
        "blockers",
        "next_steps",
        "key_files",
        "participants",
        "your_positions",
        "counterparty_positions",
        "new_facts",
        "intended_actions",
        "ledger_update_candidates",
        "project_refs",
        "changes_made",
        "open_loops",
        "do_not_repeat",
    ):
        if list_field in normalized:
            normalized[list_field] = _normalize_text_list(normalized.get(list_field))
    return normalized


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise WorkMemoryValidationError(f"{field_name} is required")
    return text


def _normalize_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                items.append(text)
        return items
    text = str(value or "").strip()
    return [text] if text else []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
