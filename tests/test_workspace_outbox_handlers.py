from __future__ import annotations

from chatgptrest.kernel.effects_outbox import EffectsOutbox
from chatgptrest.workspace.outbox_handlers import (
    LEGACY_GOOGLE_WORKSPACE_EFFECT_TYPE,
    WORKSPACE_EFFECT_TYPE,
    enqueue_workspace_request,
    execute_workspace_effects_for_trace,
)
from chatgptrest.workspace.contracts import WorkspaceActionResult, WorkspaceRequest


class _FakeWorkspaceService:
    def __init__(self):
        self.calls: list[dict] = []

    def execute(self, request):
        self.calls.append(request.to_dict())
        return WorkspaceActionResult(
            ok=True,
            action=request.action,
            status="completed",
            message="done",
            data={"url": "https://docs.test/doc-1"},
            artifacts=[{"kind": "google_doc", "uri": "https://docs.test/doc-1"}],
        )


def test_enqueue_workspace_request_uses_standard_effect_type() -> None:
    outbox = EffectsOutbox(":memory:")
    request = WorkspaceRequest(
        action="deliver_report_to_docs",
        trace_id="trace-ws-outbox-1",
        payload={"title": "Report", "body_text": "hello"},
    )

    enqueue_workspace_request(outbox, request)
    effect = outbox.get_by_trace("trace-ws-outbox-1")[0]

    assert effect.effect_type == WORKSPACE_EFFECT_TYPE


def test_execute_workspace_effects_for_trace_consumes_standard_effect() -> None:
    outbox = EffectsOutbox(":memory:")
    request = WorkspaceRequest(
        action="deliver_report_to_docs",
        trace_id="trace-ws-outbox-2",
        payload={"title": "Report", "body_text": "hello"},
    )
    enqueue_workspace_request(outbox, request)

    results = execute_workspace_effects_for_trace(
        outbox,
        trace_id="trace-ws-outbox-2",
        service=_FakeWorkspaceService(),
    )

    assert results[0]["success"] is True
    assert results[0]["workspace_request"]["action"] == "deliver_report_to_docs"
    assert outbox.count(status="done", trace_id="trace-ws-outbox-2") == 1


def test_execute_workspace_effects_for_trace_consumes_legacy_google_delivery() -> None:
    outbox = EffectsOutbox(":memory:")
    outbox.enqueue(
        trace_id="trace-ws-outbox-3",
        effect_type=LEGACY_GOOGLE_WORKSPACE_EFFECT_TYPE,
        effect_key="google_workspace_delivery::trace-ws-outbox-3",
        payload={"title": "Legacy", "body_text": "hello"},
    )

    results = execute_workspace_effects_for_trace(
        outbox,
        trace_id="trace-ws-outbox-3",
        service=_FakeWorkspaceService(),
    )

    assert results[0]["success"] is True
    assert results[0]["workspace_request"]["action"] == "deliver_report_to_docs"
