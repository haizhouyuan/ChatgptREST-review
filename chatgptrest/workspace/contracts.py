from __future__ import annotations

import json
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field


_SPEC_VERSION = "workspace-request-v1"
_ACTIONS = {
    "search_drive_files",
    "fetch_drive_file",
    "deliver_report_to_docs",
    "append_sheet_rows",
    "send_gmail_notice",
}


class WorkspaceRequestValidationError(ValueError):
    """Raised when a caller-provided workspace request payload is invalid."""

    def __init__(self, *, error: str, message: str, detail: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        payload = {"error": error, "message": message}
        if detail:
            payload.update(dict(detail))
        self.detail = payload


class WorkspaceRequest(BaseModel):
    spec_version: Literal["workspace-request-v1"] = _SPEC_VERSION
    action: Literal[
        "search_drive_files",
        "fetch_drive_file",
        "deliver_report_to_docs",
        "append_sheet_rows",
        "send_gmail_notice",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    session_id: str | None = None
    idempotency_key: str | None = None
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _model_dump(self)


class WorkspaceActionResult(BaseModel):
    ok: bool
    action: str
    status: Literal["completed", "failed"]
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _model_dump(self)


def build_workspace_request(
    *,
    raw_request: Mapping[str, Any],
    trace_id: str = "",
    session_id: str = "",
) -> WorkspaceRequest:
    payload = dict(raw_request or {})
    _validate_spec_version(payload)
    action = str(payload.get("action") or "").strip()
    if action not in _ACTIONS:
        raise WorkspaceRequestValidationError(
            error="invalid_workspace_action",
            message="Unsupported workspace action",
            detail={"action": action or None, "supported_actions": sorted(_ACTIONS)},
        )
    return WorkspaceRequest(
        action=action,
        payload=dict(payload.get("payload") or {}),
        trace_id=_clean_optional_str(payload.get("trace_id")) or _clean_optional_str(trace_id),
        session_id=_clean_optional_str(payload.get("session_id")) or _clean_optional_str(session_id),
        idempotency_key=_clean_optional_str(payload.get("idempotency_key")),
        dry_run=bool(payload.get("dry_run")),
    )


def merge_workspace_request(
    base: Mapping[str, Any] | None,
    patch: Mapping[str, Any] | None,
    *,
    trace_id: str = "",
    session_id: str = "",
) -> WorkspaceRequest | None:
    if not base and not patch:
        return None
    merged = dict(base or {})
    for key, value in dict(patch or {}).items():
        if value is None:
            continue
        if key == "payload" and isinstance(merged.get("payload"), dict) and isinstance(value, dict):
            merged["payload"] = _deep_merge_dict(dict(merged.get("payload") or {}), dict(value or {}))
            continue
        merged[key] = value
    return build_workspace_request(raw_request=merged, trace_id=trace_id, session_id=session_id)


def summarize_workspace_request(request: WorkspaceRequest | Mapping[str, Any] | None) -> dict[str, Any]:
    if request is None:
        return {}
    req = request if isinstance(request, WorkspaceRequest) else build_workspace_request(raw_request=request)
    payload = dict(req.payload or {})
    return {
        "spec_version": req.spec_version,
        "action": req.action,
        "payload_keys": sorted(payload.keys()),
        "trace_id": str(req.trace_id or ""),
        "session_id": str(req.session_id or ""),
        "dry_run": bool(req.dry_run),
        "idempotency_key": str(req.idempotency_key or ""),
    }


def workspace_missing_fields(request: WorkspaceRequest) -> list[str]:
    payload = dict(request.payload or {})
    if request.action == "search_drive_files":
        return [] if _has_text(payload.get("query")) else ["query"]
    if request.action == "fetch_drive_file":
        return [] if _has_text(payload.get("file_id")) else ["file_id"]
    if request.action == "deliver_report_to_docs":
        missing: list[str] = []
        if not _has_text(payload.get("title")):
            missing.append("title")
        if not (_has_text(payload.get("body_markdown")) or _has_text(payload.get("body_text"))):
            missing.append("body_markdown")
        return missing
    if request.action == "append_sheet_rows":
        missing = []
        if not (_has_text(payload.get("spreadsheet_id")) or _has_text(payload.get("spreadsheet_title"))):
            missing.append("spreadsheet_id")
        rows = payload.get("rows")
        if not isinstance(rows, list) or not rows:
            missing.append("rows")
        return missing
    if request.action == "send_gmail_notice":
        missing = []
        if not _has_text(payload.get("to")):
            missing.append("to")
        if not _has_text(payload.get("subject")):
            missing.append("subject")
        if not (_has_text(payload.get("body_text")) or _has_text(payload.get("body_html"))):
            missing.append("body_text")
        return missing
    return []


def workspace_clarify_questions(request: WorkspaceRequest) -> list[str]:
    missing = workspace_missing_fields(request)
    action = request.action
    questions: list[str] = []
    for field in missing:
        if action == "search_drive_files" and field == "query":
            questions.append("What Drive search query or file name should be used?")
        elif action == "fetch_drive_file" and field == "file_id":
            questions.append("Which Google Drive file_id should be downloaded?")
        elif action == "deliver_report_to_docs" and field == "title":
            questions.append("What title should be used for the Google Doc?")
        elif action == "deliver_report_to_docs" and field == "body_markdown":
            questions.append("What report body should be written to the Google Doc?")
        elif action == "append_sheet_rows" and field == "spreadsheet_id":
            questions.append("Which spreadsheet_id or spreadsheet_title should rows be appended into?")
        elif action == "append_sheet_rows" and field == "rows":
            questions.append("What row values should be appended to the sheet?")
        elif action == "send_gmail_notice" and field == "to":
            questions.append("Which email recipient should receive the Gmail notice?")
        elif action == "send_gmail_notice" and field == "subject":
            questions.append("What email subject should be used?")
        elif action == "send_gmail_notice" and field == "body_text":
            questions.append("What body should be sent in the email notice?")
    return questions


def recommended_workspace_patch(request: WorkspaceRequest) -> dict[str, Any]:
    payload_patch: dict[str, Any] = {}
    for field in workspace_missing_fields(request):
        if field == "query":
            payload_patch[field] = "<drive search query>"
        elif field == "file_id":
            payload_patch[field] = "<google_drive_file_id>"
        elif field == "title":
            payload_patch[field] = "<document title>"
        elif field == "body_markdown":
            payload_patch[field] = "<markdown body>"
        elif field == "spreadsheet_id":
            payload_patch["spreadsheet_title"] = "<spreadsheet title>"
        elif field == "rows":
            payload_patch[field] = [["<col1>", "<col2>"]]
        elif field == "to":
            payload_patch[field] = "<recipient@example.com>"
        elif field == "subject":
            payload_patch[field] = "<email subject>"
        elif field == "body_text":
            payload_patch[field] = "<email body>"
    return {"workspace_request": {"payload": payload_patch}} if payload_patch else {}


def workspace_effect_key(request: WorkspaceRequest) -> str:
    if _has_text(request.idempotency_key):
        return str(request.idempotency_key).strip()
    trace = str(request.trace_id or "workspace").strip() or "workspace"
    return f"workspace_action::{trace}::{request.action}"


def workspace_effect_payload(request: WorkspaceRequest) -> dict[str, Any]:
    return {"workspace_request": request.to_dict()}


def workspace_action_summary(result: WorkspaceActionResult | Mapping[str, Any] | None) -> dict[str, Any]:
    if result is None:
        return {}
    obj = result if isinstance(result, WorkspaceActionResult) else WorkspaceActionResult(**dict(result or {}))
    return {
        "ok": bool(obj.ok),
        "action": str(obj.action or ""),
        "status": str(obj.status or ""),
        "message": str(obj.message or ""),
        "artifact_count": len(list(obj.artifacts or [])),
        "data_keys": sorted(dict(obj.data or {}).keys()),
    }


def _validate_spec_version(payload: Mapping[str, Any]) -> None:
    raw = str(payload.get("spec_version") or "").strip()
    if raw and raw != _SPEC_VERSION:
        raise WorkspaceRequestValidationError(
            error="workspace_request_spec_version_mismatch",
            message="Workspace request spec_version does not match supported version",
            detail={"provided": raw, "supported": _SPEC_VERSION},
        )


def _clean_optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if value is None:
            continue
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dict(existing, value)
        else:
            merged[key] = value
    return merged


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="python")
    return json.loads(model.json())
