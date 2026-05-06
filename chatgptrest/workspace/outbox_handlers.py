from __future__ import annotations

import logging
from typing import Any

from chatgptrest.kernel.effects_outbox import EffectsOutbox
from chatgptrest.workspace.contracts import (
    WorkspaceActionResult,
    WorkspaceRequest,
    WorkspaceRequestValidationError,
    build_workspace_request,
    summarize_workspace_request,
    workspace_action_summary,
    workspace_effect_key,
    workspace_effect_payload,
)
from chatgptrest.workspace.service import WorkspaceService

logger = logging.getLogger(__name__)

WORKSPACE_EFFECT_TYPE = "workspace_action"
LEGACY_GOOGLE_WORKSPACE_EFFECT_TYPE = "google_workspace_delivery"


def workspace_handler_map(service: WorkspaceService | None = None) -> dict[str, Any]:
    svc = service or WorkspaceService()

    def _run_workspace_action(payload: dict[str, Any]) -> dict[str, Any]:
        request = _request_from_effect_payload(payload)
        result = svc.execute(request)
        if not result.ok:
            raise RuntimeError(result.message or f"{request.action} failed")
        return {"workspace_request": request.to_dict(), "workspace_result": result.to_dict()}

    return {
        WORKSPACE_EFFECT_TYPE: _run_workspace_action,
        LEGACY_GOOGLE_WORKSPACE_EFFECT_TYPE: _run_workspace_action,
    }


def enqueue_workspace_request(outbox: EffectsOutbox, request: WorkspaceRequest) -> str | None:
    return outbox.enqueue(
        trace_id=str(request.trace_id or ""),
        effect_type=WORKSPACE_EFFECT_TYPE,
        effect_key=workspace_effect_key(request),
        payload=workspace_effect_payload(request),
    )


def execute_workspace_effects_for_trace(
    outbox: EffectsOutbox,
    *,
    trace_id: str,
    service: WorkspaceService | None = None,
    include_failed: bool = False,
) -> list[dict[str, Any]]:
    handlers = workspace_handler_map(service)
    accepted_statuses = {"pending", "executing"}
    if include_failed:
        accepted_statuses.add("failed")
    results: list[dict[str, Any]] = []
    for effect in outbox.get_by_trace(trace_id):
        if effect.effect_type not in handlers:
            continue
        if effect.status not in accepted_statuses:
            continue
        try:
            payload = handlers[effect.effect_type](effect.payload)
        except Exception as exc:
            outbox.mark_failed(effect.effect_id, str(exc))
            logger.warning(
                "Workspace effect failed: effect_id=%s type=%s trace_id=%s error=%s",
                effect.effect_id,
                effect.effect_type,
                trace_id,
                exc,
            )
            results.append(
                {
                    "effect_id": effect.effect_id,
                    "effect_type": effect.effect_type,
                    "success": False,
                    "error": str(exc),
                }
            )
            continue
        outbox.mark_done(effect.effect_id)
        request_summary = summarize_workspace_request(payload.get("workspace_request"))
        result_summary = workspace_action_summary(payload.get("workspace_result"))
        results.append(
            {
                "effect_id": effect.effect_id,
                "effect_type": effect.effect_type,
                "success": True,
                "workspace_request": request_summary,
                "workspace_result": result_summary,
                "workspace_result_full": dict(payload.get("workspace_result") or {}),
            }
        )
    return results


def _request_from_effect_payload(payload: dict[str, Any]) -> WorkspaceRequest:
    if isinstance(payload.get("workspace_request"), dict):
        return build_workspace_request(raw_request=dict(payload.get("workspace_request") or {}))
    try:
        return build_workspace_request(
            raw_request={
                "action": "deliver_report_to_docs",
                "payload": {
                    "title": payload.get("title"),
                    "body_text": payload.get("body_text"),
                    "target_folder": payload.get("target_folder"),
                    "notify_email": payload.get("notify_email"),
                    "notify_subject": payload.get("notify_subject"),
                    "notify_body_html": payload.get("notify_body_html"),
                    "notify_body_text": payload.get("notify_body_text"),
                },
                "trace_id": payload.get("trace_id"),
                "idempotency_key": payload.get("idempotency_key"),
            }
        )
    except WorkspaceRequestValidationError as exc:
        raise RuntimeError(str(exc.detail.get("message") or "invalid workspace effect payload")) from exc
