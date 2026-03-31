from __future__ import annotations

import pytest

from chatgptrest.workspace.contracts import (
    WorkspaceRequestValidationError,
    build_workspace_request,
    merge_workspace_request,
    recommended_workspace_patch,
    summarize_workspace_request,
    workspace_missing_fields,
)


def test_build_workspace_request_accepts_valid_payload() -> None:
    request = build_workspace_request(
        raw_request={
            "spec_version": "workspace-request-v1",
            "action": "deliver_report_to_docs",
            "payload": {"title": "Report", "body_markdown": "# Hello"},
            "trace_id": "trace-1",
        },
        session_id="sess-1",
    )

    assert request.action == "deliver_report_to_docs"
    assert request.trace_id == "trace-1"
    assert request.session_id == "sess-1"


def test_build_workspace_request_rejects_invalid_version() -> None:
    with pytest.raises(WorkspaceRequestValidationError) as exc_info:
        build_workspace_request(
            raw_request={"spec_version": "workspace-request-v0", "action": "search_drive_files", "payload": {}}
        )

    assert exc_info.value.detail["error"] == "workspace_request_spec_version_mismatch"


def test_merge_workspace_request_deep_merges_payload() -> None:
    merged = merge_workspace_request(
        {"action": "deliver_report_to_docs", "payload": {"title": "A", "body_markdown": "# Draft"}},
        {"payload": {"target_folder": "reports/daily"}},
        trace_id="trace-2",
    )

    assert merged is not None
    assert merged.payload["title"] == "A"
    assert merged.payload["target_folder"] == "reports/daily"


def test_workspace_missing_fields_and_recommended_patch() -> None:
    request = build_workspace_request(
        raw_request={"action": "send_gmail_notice", "payload": {"subject": "hello"}},
        trace_id="trace-3",
    )

    assert workspace_missing_fields(request) == ["to", "body_text"]
    patch = recommended_workspace_patch(request)
    assert patch["workspace_request"]["payload"]["to"] == "<recipient@example.com>"
    assert patch["workspace_request"]["payload"]["body_text"] == "<email body>"


def test_summarize_workspace_request_reports_payload_keys() -> None:
    request = build_workspace_request(
        raw_request={"action": "search_drive_files", "payload": {"query": "name contains 'report'", "page_size": 5}},
        trace_id="trace-4",
    )

    summary = summarize_workspace_request(request)
    assert summary["action"] == "search_drive_files"
    assert summary["payload_keys"] == ["page_size", "query"]
