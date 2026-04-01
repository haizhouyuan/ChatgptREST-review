from __future__ import annotations

import json
from pathlib import Path
from typing import Any

COMPLETION_CONTRACT_VERSION = "v1"
CANONICAL_ANSWER_VERSION = "v1"

_RESEARCH_PURPOSES = {
    "analysis",
    "consult",
    "dual_review",
    "grounded_rerun",
    "report",
    "report_grade",
    "research",
    "review",
    "write_report",
}

_RESEARCH_PRESETS = {
    "deep_research",
    "deep-research",
    "deepresearch",
    "pro_extended",
    "thinking_extended",
    "thinking_heavy",
}

_TERMINAL_NONFINAL_STATUSES = {"blocked", "error", "canceled", "cancelled", "needs_followup"}
_IN_PROGRESS_STATUSES = {"queued", "in_progress", "cooldown"}


def _normalized_completion_quality(value: Any) -> str | None:
    quality = str(value or "").strip().lower()
    return quality or None


def _completed_quality_is_non_final(value: Any) -> bool:
    quality = _normalized_completion_quality(value)
    return bool(quality and quality != "final")


def parse_job_params_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def min_chars_required_from_params(params_obj: dict[str, Any] | None) -> int:
    try:
        return max(0, int((params_obj or {}).get("min_chars") or 0))
    except Exception:
        return 0


def is_research_contract_params(params_obj: dict[str, Any] | None) -> bool:
    params = dict(params_obj or {})
    if bool(params.get("deep_research") or False):
        return True
    purpose = str(params.get("purpose") or "").strip().lower()
    if purpose in _RESEARCH_PURPOSES:
        return True
    preset = str(params.get("preset") or "").strip().lower()
    min_chars = min_chars_required_from_params(params)
    if preset in _RESEARCH_PRESETS and min_chars >= 1200:
        return True
    return False


def widget_export_available_from_path(path: str | Path | None) -> bool:
    raw = str(path or "").strip()
    if not raw:
        return False
    try:
        parsed = json.loads(Path(raw).read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return False
    if not isinstance(parsed, dict):
        return False
    widget = parsed.get("deep_research_widget_export")
    if isinstance(widget, str):
        return bool(widget.strip())
    if isinstance(widget, dict):
        for key in ("markdown", "text", "report_markdown"):
            value = widget.get(key)
            if isinstance(value, str) and value.strip():
                return True
    return False


def build_completion_contract(
    *,
    status: str,
    kind: str | None,
    answer_chars: int | None,
    answer_path: str | None,
    authoritative_job_id: str | None,
    authoritative_answer_path: str | None,
    min_chars_required: int,
    last_event_type: str | None,
    reason_type: str | None,
    completion_quality: str | None,
    conversation_export_path: str | None,
    widget_export_available: bool,
    research_contract: bool,
) -> dict[str, Any]:
    normalized_status = str(status or "").strip().lower()
    last_event = str(last_event_type or "").strip().lower() or None
    reason = str(reason_type or "").strip() or None
    quality = _normalized_completion_quality(completion_quality)
    answer_chars_int = int(answer_chars or 0) if answer_chars is not None else 0
    export_available = bool(str(conversation_export_path or "").strip())
    local_answer_path = str(answer_path or "").strip() or None
    resolved_answer_path = str(authoritative_answer_path or "").strip() or local_answer_path
    resolved_job_id = str(authoritative_job_id or "").strip() or None

    research_blocked = last_event == "completion_guard_research_contract_blocked" or reason == "ResearchCompletionNotFinal"

    if normalized_status == "completed":
        if _completed_quality_is_non_final(quality):
            answer_state = "provisional"
            finality_reason = quality or "completed_nonfinal"
        else:
            answer_state = "final"
            finality_reason = "completed"
    elif normalized_status == "needs_followup":
        answer_state = "provisional" if (research_contract or answer_chars_int > 0 or export_available or research_blocked) else "partial"
        finality_reason = reason or last_event or normalized_status
    elif normalized_status in {"blocked", "error", "canceled", "cancelled"}:
        answer_state = "provisional" if (answer_chars_int > 0 or export_available or research_blocked) else "partial"
        finality_reason = reason or last_event or normalized_status
    elif normalized_status in {"in_progress", "queued", "cooldown"}:
        if last_event in {"completion_guard_downgraded", "completion_guard_research_contract_blocked"}:
            answer_state = "provisional"
        else:
            answer_state = "partial"
        finality_reason = last_event or normalized_status
    else:
        answer_state = "partial"
        finality_reason = last_event or normalized_status or "unknown"

    provenance: dict[str, Any] = {
        "contract_class": "research" if research_contract else "generic",
        "canonical_source": (
            "conversation_authoritative_resolution"
            if resolved_answer_path and local_answer_path and resolved_answer_path != local_answer_path
            else ("answer_artifact" if resolved_answer_path else None)
        ),
        "last_event_type": last_event,
        "completion_quality": quality,
        "conversation_export_path": (str(conversation_export_path or "").strip() or None),
        "authoritative_job_id": resolved_job_id,
    }

    return {
        "kind": (str(kind or "").strip() or None),
        "answer_state": answer_state,
        "finality_reason": finality_reason,
        "answer_chars": (int(answer_chars_int) if answer_chars is not None else None),
        "min_chars_required": int(min_chars_required),
        "authoritative_job_id": resolved_job_id,
        "authoritative_answer_path": resolved_answer_path,
        "answer_provenance": {k: v for k, v in provenance.items() if v is not None},
        "export_available": export_available,
        "widget_export_available": bool(widget_export_available),
    }


def build_canonical_answer_record(
    *,
    status: str | None,
    answer_format: str | None,
    completion_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    contract = _normalized_contract_dict(completion_contract)
    answer_state = str(contract.get("answer_state") or "partial").strip().lower() or "partial"
    authoritative_job_id = str(contract.get("authoritative_job_id") or "").strip() or None
    authoritative_answer_path = str(contract.get("authoritative_answer_path") or "").strip() or None
    provenance = contract.get("answer_provenance")
    normalized_status = str(status or "").strip().lower()
    ready = normalized_status == "completed" and answer_state == "final" and bool(authoritative_answer_path)
    return {
        "record_version": CANONICAL_ANSWER_VERSION,
        "ready": bool(ready),
        "answer_state": answer_state,
        "finality_reason": (str(contract.get("finality_reason") or "").strip() or None),
        "authoritative_job_id": authoritative_job_id,
        "authoritative_answer_path": authoritative_answer_path,
        "answer_chars": contract.get("answer_chars"),
        "answer_format": (str(answer_format or "").strip() or None),
        "answer_provenance": dict(provenance) if isinstance(provenance, dict) else {},
        "export_available": bool(contract.get("export_available")),
        "widget_export_available": bool(contract.get("widget_export_available")),
    }


def _job_like_value(job_or_result: Any, key: str) -> Any:
    if isinstance(job_or_result, dict):
        return job_or_result.get(key)
    return getattr(job_or_result, key, None)


def _normalized_contract_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if raw is None:
        return {}
    data: dict[str, Any] = {}
    for key in (
        "kind",
        "answer_state",
        "finality_reason",
        "answer_chars",
        "min_chars_required",
        "authoritative_job_id",
        "authoritative_answer_path",
        "answer_provenance",
        "export_available",
        "widget_export_available",
    ):
        value = getattr(raw, key, None)
        if value is not None:
            data[key] = value
    return data


def _normalized_canonical_answer_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if raw is None:
        return {}
    data: dict[str, Any] = {}
    for key in (
        "record_version",
        "ready",
        "answer_state",
        "finality_reason",
        "authoritative_job_id",
        "authoritative_answer_path",
        "answer_chars",
        "answer_format",
        "answer_provenance",
        "export_available",
        "widget_export_available",
    ):
        value = getattr(raw, key, None)
        if value is not None:
            data[key] = value
    return data


def completion_contract_from_job_like(job_or_result: Any) -> dict[str, Any]:
    contract = _normalized_contract_dict(_job_like_value(job_or_result, "completion_contract"))
    if contract:
        return contract

    status = str(_job_like_value(job_or_result, "status") or "").strip().lower()
    kind = str(_job_like_value(job_or_result, "kind") or "").strip() or None
    completion_quality = _normalized_completion_quality(_job_like_value(job_or_result, "completion_quality"))
    answer_path = str(
        _job_like_value(job_or_result, "authoritative_answer_path")
        or _job_like_value(job_or_result, "path")
        or _job_like_value(job_or_result, "answer_path")
        or ""
    ).strip() or None
    export_path = str(_job_like_value(job_or_result, "conversation_export_path") or "").strip() or None
    answer_chars_raw = _job_like_value(job_or_result, "answer_chars")
    answer_chars: int | None
    try:
        answer_chars = int(answer_chars_raw) if answer_chars_raw is not None else None
    except Exception:
        answer_chars = None

    if status == "completed":
        if _completed_quality_is_non_final(completion_quality):
            answer_state = "provisional"
            finality_reason = completion_quality or "completed_nonfinal"
        else:
            answer_state = "final"
            finality_reason = "completed"
    elif status in _TERMINAL_NONFINAL_STATUSES:
        answer_state = "provisional" if (answer_path or export_path) else "partial"
        finality_reason = completion_quality or status
    elif status in _IN_PROGRESS_STATUSES:
        answer_state = "provisional" if export_path else "partial"
        finality_reason = completion_quality or status
    else:
        answer_state = "partial"
        finality_reason = completion_quality or status or "unknown"

    provenance = {
        "contract_class": "fallback",
        "canonical_source": ("answer_artifact" if answer_path else None),
        "completion_quality": completion_quality,
        "conversation_export_path": export_path,
    }
    return {
        "kind": kind,
        "answer_state": answer_state,
        "finality_reason": finality_reason,
        "answer_chars": answer_chars,
        "min_chars_required": 0,
        "authoritative_job_id": str(_job_like_value(job_or_result, "job_id") or "").strip() or None,
        "authoritative_answer_path": answer_path,
        "answer_provenance": {k: v for k, v in provenance.items() if v is not None},
        "export_available": bool(export_path),
        "widget_export_available": False,
    }


def canonical_answer_from_job_like(job_or_result: Any) -> dict[str, Any]:
    record = _normalized_canonical_answer_dict(_job_like_value(job_or_result, "canonical_answer"))
    if record:
        return record
    return build_canonical_answer_record(
        status=_job_like_value(job_or_result, "status"),
        answer_format=_job_like_value(job_or_result, "answer_format"),
        completion_contract=completion_contract_from_job_like(job_or_result),
    )


def get_completion_answer_state(job_or_result: Any) -> str:
    return str(completion_contract_from_job_like(job_or_result).get("answer_state") or "partial").strip().lower() or "partial"


def is_research_final(job_or_result: Any) -> bool:
    return get_completion_answer_state(job_or_result) == "final"


def is_authoritative_answer_ready(job_or_result: Any) -> bool:
    return bool(canonical_answer_from_job_like(job_or_result).get("ready"))


def get_authoritative_job_id(job_or_result: Any) -> str | None:
    raw = canonical_answer_from_job_like(job_or_result).get("authoritative_job_id")
    value = str(raw or "").strip()
    return value or None


def get_authoritative_answer_path(job_or_result: Any) -> str | None:
    raw = canonical_answer_from_job_like(job_or_result).get("authoritative_answer_path")
    value = str(raw or "").strip()
    return value or None


def resolve_authoritative_answer_artifact(
    job_or_result: Any,
    *,
    artifacts_dir: str | Path,
) -> Path | None:
    path = get_authoritative_answer_path(job_or_result)
    if not path:
        return None
    try:
        from chatgptrest.core import artifacts

        return artifacts.resolve_artifact_path(Path(artifacts_dir), path)
    except Exception:
        return None


def get_answer_provenance(job_or_result: Any) -> dict[str, Any]:
    provenance = canonical_answer_from_job_like(job_or_result).get("answer_provenance")
    return dict(provenance) if isinstance(provenance, dict) else {}
