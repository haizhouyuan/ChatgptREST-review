"""Validation pack for the Google Workspace northbound surface revival."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import chatgptrest.api.routes_agent_v3 as routes_agent_v3
from chatgptrest.advisor.report_graph import finalize
from chatgptrest.workspace.contracts import WorkspaceActionResult, build_workspace_request
from chatgptrest.workspace.service import WorkspaceService


@dataclass
class GoogleWorkspaceSurfaceCheckResult:
    name: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "details": dict(self.details),
            "mismatches": dict(self.mismatches),
        }


@dataclass
class GoogleWorkspaceSurfaceValidationReport:
    num_checks: int
    num_passed: int
    num_failed: int
    results: list[GoogleWorkspaceSurfaceCheckResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "results": [item.to_dict() for item in self.results],
        }


class _FakeSheetsValues:
    def append(self, **_kwargs):
        class _Request:
            def execute(self_nonlocal):
                return {"updates": {"updatedRange": "Sheet1!A1:B2", "updatedRows": 2}}

        return _Request()


class _FakeSheetsSpreadsheets:
    def values(self):
        return _FakeSheetsValues()


class _FakeSheetsService:
    def spreadsheets(self):
        return _FakeSheetsSpreadsheets()


class _FakeDriveFiles:
    def get(self, **kwargs):
        class _Request:
            def execute(self_nonlocal):
                if kwargs.get("fields") == "parents":
                    return {"parents": ["root"]}
                return {
                    "id": kwargs["fileId"],
                    "name": "downloaded.md",
                    "mimeType": "text/markdown",
                    "webViewLink": "https://drive.test/file",
                }

        return _Request()

    def update(self, **kwargs):
        class _Request:
            def execute(self_nonlocal):
                return {"id": kwargs["fileId"], "parents": [kwargs["addParents"]]}

        return _Request()


class _FakeDriveService:
    def files(self):
        return _FakeDriveFiles()


class _FakeGoogleWorkspace:
    def __init__(self):
        self._enabled = {"drive", "docs", "gmail", "sheets"}
        self._token_path = "/tmp/google-token.json"
        self._credentials_path = "/tmp/google-credentials.json"

    def load_token(self):
        return True

    def is_authenticated(self):
        return True

    def _get_service(self, service_name: str, version: str):
        if service_name == "sheets":
            return _FakeSheetsService()
        if service_name == "drive":
            return _FakeDriveService()
        raise AssertionError(f"unexpected service {service_name}:{version}")

    def drive_list_files(self, query: str = "", page_size: int = 20, fields: str = ""):
        if "mimeType = 'application/vnd.google-apps.folder'" in query:
            return []
        return [{"id": "file-1", "name": "Report", "webViewLink": "https://drive.test/report"}]

    def drive_download_file(self, file_id: str, local_path: str):
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_text(f"downloaded:{file_id}", encoding="utf-8")
        return True

    def drive_create_folder(self, name: str, *, parent_id: str = ""):
        return {"id": f"folder-{name}", "name": name, "webViewLink": f"https://drive.test/{name}"}

    def docs_create(self, title: str, *, body_text: str = ""):
        return {"document_id": "doc-1", "url": "https://docs.test/doc-1", "title": title, "body_text": body_text}

    def gmail_send(self, *, to: str, subject: str, body: str, html: bool = False):
        return {"id": "gmail-1", "labelIds": ["SENT"], "to": to, "subject": subject}

    def sheets_create(self, title: str):
        return {"spreadsheet_id": "sheet-1", "url": "https://sheets.test/sheet-1", "title": title}


def run_google_workspace_surface_validation() -> GoogleWorkspaceSurfaceValidationReport:
    checks = [
        _capability_audit_check(),
        _rclone_remote_check(),
        _workspace_auth_state_check(),
        _public_agent_workspace_clarify_check(),
        _public_agent_workspace_patch_check(),
        _workspace_service_docs_gmail_check(),
        _workspace_service_drive_check(),
        _workspace_service_sheets_check(),
        _report_graph_workspace_outbox_check(),
        _cli_workspace_request_check(),
        _skill_wrapper_workspace_request_check(),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return GoogleWorkspaceSurfaceValidationReport(
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        results=checks,
    )


def _capability_audit_check() -> GoogleWorkspaceSurfaceCheckResult:
    from chatgptrest.integrations.google_workspace import GoogleWorkspace

    adapter_methods = {
        "drive_list_files": hasattr(GoogleWorkspace, "drive_list_files"),
        "drive_download_file": hasattr(GoogleWorkspace, "drive_download_file"),
        "drive_upload_file": hasattr(GoogleWorkspace, "drive_upload_file"),
        "calendar_list_events": hasattr(GoogleWorkspace, "calendar_list_events"),
        "calendar_create_event": hasattr(GoogleWorkspace, "calendar_create_event"),
        "sheets_read": hasattr(GoogleWorkspace, "sheets_read"),
        "sheets_write": hasattr(GoogleWorkspace, "sheets_write"),
        "sheets_create": hasattr(GoogleWorkspace, "sheets_create"),
        "docs_create": hasattr(GoogleWorkspace, "docs_create"),
        "docs_read": hasattr(GoogleWorkspace, "docs_read"),
        "gmail_send": hasattr(GoogleWorkspace, "gmail_send"),
        "tasks_list": hasattr(GoogleWorkspace, "tasks_list"),
        "tasks_create": hasattr(GoogleWorkspace, "tasks_create"),
    }
    setup_text = Path("scripts/setup_google_workspace.sh").read_text(encoding="utf-8", errors="replace")
    env_text = Path("chatgptrest/core/env.py").read_text(encoding="utf-8", errors="replace")
    docs_text = Path("docs/handoff_gemini_drive_attachments_20251230.md").read_text(
        encoding="utf-8", errors="replace"
    )
    details = {
        "adapter_methods_present": [name for name, present in adapter_methods.items() if present],
        "setup_script_declares_required_apis": all(
            marker in setup_text for marker in ("Drive", "Calendar", "Sheets", "Docs", "Gmail", "Tasks")
        ),
        "env_keys_present": all(
            marker in env_text
            for marker in ("OPENMIND_GOOGLE_CREDENTIALS_PATH", "OPENMIND_GOOGLE_TOKEN_PATH", "OPENMIND_GOOGLE_SERVICES")
        ),
        "drive_transport_handoff_present": "gdrive:chatgptrest_uploads" in docs_text,
    }
    passed = all(adapter_methods.values()) and all(
        bool(details[key])
        for key in ("setup_script_declares_required_apis", "env_keys_present", "drive_transport_handoff_present")
    )
    return _build_check(
        name="capability_audit",
        details=details,
        expectations={
            "setup_script_declares_required_apis": True,
            "env_keys_present": True,
            "drive_transport_handoff_present": True,
        },
        required_fields=("adapter_methods_present",),
        passed_override=passed,
    )


def _rclone_remote_check() -> GoogleWorkspaceSurfaceCheckResult:
    try:
        proc = subprocess.run(
            ["rclone", "listremotes"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        remotes = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except Exception as exc:
        remotes = []
        return GoogleWorkspaceSurfaceCheckResult(
            name="rclone_remote_present",
            passed=False,
            details={"error": str(exc)},
            mismatches={"rclone_remote_present": {"expected": "gdrive:", "actual": str(exc)}},
        )
    details = {"remotes": remotes}
    return _build_check(
        name="rclone_remote_present",
        details=details,
        expectations={"has_gdrive": True},
        computed={"has_gdrive": "gdrive:" in remotes},
    )


def _workspace_auth_state_check() -> GoogleWorkspaceSurfaceCheckResult:
    state = WorkspaceService().auth_state()
    details = dict(state)
    details["credentials_exists"] = Path(str(state.get("credentials_path") or "")).exists()
    details["token_exists"] = Path(str(state.get("token_path") or "")).exists()
    return _build_check(
        name="workspace_auth_state",
        details=details,
        expectations={"ok": True},
        required_fields=("enabled_services", "credentials_path", "token_path"),
    )


def _public_agent_workspace_clarify_check() -> GoogleWorkspaceSurfaceCheckResult:
    with _workspace_agent_client() as client:
        headers = {"X-Api-Key": "test-openmind-key"}
        response = client.post(
            "/v3/agent/turn",
            headers=headers,
            json={
                "workspace_request": {
                    "action": "deliver_report_to_docs",
                    "payload": {"title": "Daily report"},
                }
            },
        )
        body = response.json()
    return _build_check(
        name="public_agent_workspace_clarify",
        details={
            "status_code": response.status_code,
            "status": str(body.get("status") or ""),
            "route": str((body.get("provenance") or {}).get("route") or ""),
            "next_action": str((body.get("next_action") or {}).get("type") or ""),
            "missing_fields": list((body.get("workspace_diagnostics") or {}).get("missing_fields") or []),
        },
        expectations={
            "status_code": 200,
            "status": "needs_followup",
            "route": "workspace_clarify",
            "next_action": "await_workspace_patch",
        },
        required_fields=("missing_fields",),
    )


def _public_agent_workspace_patch_check() -> GoogleWorkspaceSurfaceCheckResult:
    with _workspace_agent_client() as client:
        headers = {"X-Api-Key": "test-openmind-key"}
        first = client.post(
            "/v3/agent/turn",
            headers=headers,
            json={
                "workspace_request": {
                    "action": "deliver_report_to_docs",
                    "payload": {"title": "Daily report"},
                }
            },
        )
        first_body = first.json()
        session_id = str(first_body.get("session_id") or "")
        second = client.post(
            "/v3/agent/turn",
            headers=headers,
            json={
                "session_id": session_id,
                "contract_patch": {
                    "workspace_request": {
                        "payload": {
                            "body_markdown": "# Daily report",
                            "notify_email": "ops@example.com",
                        }
                    }
                },
            },
        )
        body = second.json()
    return _build_check(
        name="public_agent_workspace_same_session_patch",
        details={
            "status_code": second.status_code,
            "status": str(body.get("status") or ""),
            "route": str((body.get("provenance") or {}).get("route") or ""),
            "session_id": str(body.get("session_id") or ""),
            "workspace_result_url": str(((body.get("workspace_result") or {}).get("data") or {}).get("url") or ""),
        },
        expectations={
            "status_code": 200,
            "status": "completed",
            "route": "workspace_action",
            "session_id": session_id,
            "workspace_result_url": "https://docs.test/doc-1",
        },
    )


def _workspace_service_docs_gmail_check() -> GoogleWorkspaceSurfaceCheckResult:
    with TemporaryDirectory() as tmpdir:
        service = WorkspaceService(client_factory=_FakeGoogleWorkspace, artifact_root=Path(tmpdir))
        request = build_workspace_request(
            raw_request={
                "action": "deliver_report_to_docs",
                "payload": {
                    "title": "Launch report",
                    "body_markdown": "# Hello",
                    "target_folder": "reports/daily",
                    "notify_email": "ops@example.com",
                    "notify_subject": "ready",
                },
            },
            trace_id="trace-gws-docs-1",
        )
        result = service.execute(request)
    return _build_check(
        name="workspace_service_docs_gmail_chain",
        details={
            "ok": result.ok,
            "status": result.status,
            "document_id": str(result.data.get("document_id") or ""),
            "folder_path": str((result.data.get("folder") or {}).get("folder_path") or ""),
            "gmail_id": str((result.data.get("gmail") or {}).get("id") or ""),
        },
        expectations={
            "ok": True,
            "status": "completed",
            "document_id": "doc-1",
            "folder_path": "reports/daily",
            "gmail_id": "gmail-1",
        },
    )


def _workspace_service_drive_check() -> GoogleWorkspaceSurfaceCheckResult:
    with TemporaryDirectory() as tmpdir:
        service = WorkspaceService(client_factory=_FakeGoogleWorkspace, artifact_root=Path(tmpdir))
        search_request = build_workspace_request(
            raw_request={"action": "search_drive_files", "payload": {"query": "name contains 'report'"}},
            trace_id="trace-gws-drive-1",
        )
        fetch_request = build_workspace_request(
            raw_request={"action": "fetch_drive_file", "payload": {"file_id": "file-123"}},
            trace_id="trace-gws-drive-2",
        )
        search_result = service.execute(search_request)
        fetch_result = service.execute(fetch_request)
        local_path_present = Path(str(fetch_result.data.get("local_path") or "")).exists()
    return _build_check(
        name="workspace_service_drive_chain",
        details={
            "search_ok": search_result.ok,
            "search_count": len(list(search_result.data.get("files") or [])),
            "fetch_ok": fetch_result.ok,
            "local_path_present": local_path_present,
        },
        expectations={
            "search_ok": True,
            "fetch_ok": True,
            "local_path_present": True,
        },
    )


def _workspace_service_sheets_check() -> GoogleWorkspaceSurfaceCheckResult:
    with TemporaryDirectory() as tmpdir:
        service = WorkspaceService(client_factory=_FakeGoogleWorkspace, artifact_root=Path(tmpdir))
        request = build_workspace_request(
            raw_request={
                "action": "append_sheet_rows",
                "payload": {
                    "spreadsheet_title": "Workspace Validation",
                    "rows": [["A", "B"], ["1", "2"]],
                },
            },
            trace_id="trace-gws-sheets-1",
        )
        result = service.execute(request)
    return _build_check(
        name="workspace_service_sheets_chain",
        details={
            "ok": result.ok,
            "status": result.status,
            "spreadsheet_id": str(result.data.get("spreadsheet_id") or ""),
            "updated_rows": int(result.data.get("updated_rows") or 0),
        },
        expectations={
            "ok": True,
            "status": "completed",
            "spreadsheet_id": "sheet-1",
            "updated_rows": 2,
        },
    )


def _report_graph_workspace_outbox_check() -> GoogleWorkspaceSurfaceCheckResult:
    queued: dict[str, Any] = {}

    class _FakeOutbox:
        def enqueue(self, **kwargs):
            queued.update(kwargs)
            return "eff_workspace_validation"

    result = finalize(
        {
            "internal_draft_text": "Queued report",
            "review_pass": True,
            "redact_pass": True,
            "_delivery_target": "google_drive",
            "_effects_outbox": _FakeOutbox(),
            "trace_id": "trace-workspace-validation",
            "purpose": "Workspace validation",
        }
    )
    return _build_check(
        name="report_graph_workspace_outbox_contract",
        details={
            "final_status": str(result.get("final_status") or ""),
            "effect_type": str(queued.get("effect_type") or ""),
            "effect_key": str(queued.get("effect_key") or ""),
            "workspace_action": str((((queued.get("payload") or {}).get("workspace_request") or {}).get("action")) or ""),
        },
        expectations={
            "final_status": "complete",
            "effect_type": "workspace_action",
            "effect_key": "workspace_action::trace-workspace-validation::deliver_report_to_docs",
            "workspace_action": "deliver_report_to_docs",
        },
    )


def _cli_workspace_request_check(
    *,
    public_mcp_tool_impl: Any | None = None,
) -> GoogleWorkspaceSurfaceCheckResult:
    import chatgptrest.cli as cli_mod

    captured: list[dict[str, Any]] = []

    def fake_public_mcp_tool(
        *,
        mcp_url: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_seconds: float,
    ) -> Any:
        captured.append(
            {
                "mcp_url": mcp_url,
                "tool_name": tool_name,
                "arguments": dict(arguments),
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"ok": True, "status": "completed", "session_id": "sess-cli-ws"}

    if public_mcp_tool_impl is None:
        helper = fake_public_mcp_tool
    else:
        def helper(
            *,
            mcp_url: str,
            tool_name: str,
            arguments: dict[str, Any],
            timeout_seconds: float,
        ) -> Any:
            captured.append(
                {
                    "mcp_url": mcp_url,
                    "tool_name": tool_name,
                    "arguments": dict(arguments),
                    "timeout_seconds": timeout_seconds,
                }
            )
            return public_mcp_tool_impl(
                mcp_url=mcp_url,
                tool_name=tool_name,
                arguments=arguments,
                timeout_seconds=timeout_seconds,
            )
    with patch.object(cli_mod, "_call_public_mcp_tool", helper):
        with redirect_stdout(io.StringIO()):
            rc = cli_mod.main(
                [
                    "--base-url",
                    "http://localhost:1",
                    "agent",
                    "turn",
                    "--workspace-request-json",
                    '{"spec_version":"workspace-request-v1","action":"deliver_report_to_docs","payload":{"title":"日报","body_markdown":"# content"}}',
                ]
            )
    call = captured[0]
    body = dict(call["arguments"])
    return _build_check(
        name="cli_workspace_request_northbound",
        details={
            "rc": rc,
            "tool_name": str(call["tool_name"]),
            "message": str(body.get("message") or ""),
            "workspace_action": str(((body.get("workspace_request") or {}).get("action")) or ""),
        },
        expectations={
            "rc": 0,
            "tool_name": "advisor_agent_turn",
            "message": "",
            "workspace_action": "deliver_report_to_docs",
        },
    )


def _skill_wrapper_workspace_request_check() -> GoogleWorkspaceSurfaceCheckResult:
    module = _load_skill_module()
    calls: list[dict[str, Any]] = []

    def fake_run_mcp_tool(*, mcp_url: str, tool_name: str, arguments: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        calls.append(
            {
                "mcp_url": mcp_url,
                "tool_name": tool_name,
                "arguments": dict(arguments),
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"ok": True, "session_id": "sess-skill-ws", "status": "completed", "answer": "done"}

    with patch.object(module, "_run_mcp_tool", fake_run_mcp_tool), patch.object(module, "_python_bin", lambda _root: Path(os.sys.executable)):
        with redirect_stdout(io.StringIO()):
            rc = module.main(
                [
                    "--workspace-request-json",
                    '{"spec_version":"workspace-request-v1","action":"deliver_report_to_docs","payload":{"title":"日报","body_markdown":"# content"}}',
                ]
            )
    arguments = calls[0]["arguments"]
    return _build_check(
        name="skill_wrapper_workspace_request_northbound",
        details={
            "rc": rc,
            "tool_name": str(calls[0]["tool_name"]),
            "message": str(arguments.get("message") or ""),
            "workspace_action": str(((arguments.get("workspace_request") or {}).get("action")) or ""),
        },
        expectations={
            "rc": 0,
            "tool_name": "advisor_agent_turn",
            "message": "",
            "workspace_action": "deliver_report_to_docs",
        },
    )


@contextmanager
def _workspace_agent_client() -> Iterator[TestClient]:
    with TemporaryDirectory() as state_root:
        app = FastAPI()
        with patch.dict(
            os.environ,
            {
                "OPENMIND_API_KEY": "test-openmind-key",
                "OPENMIND_AUTH_MODE": "strict",
                "CHATGPTREST_AGENT_SESSION_STATE_ROOT": state_root,
            },
            clear=False,
        ):
            class _FakeWorkspaceService:
                def execute(self, request):
                    return WorkspaceActionResult(
                        ok=True,
                        action=request.action,
                        status="completed",
                        message="done",
                        data={"url": "https://docs.test/doc-1"},
                        artifacts=[{"kind": "google_doc", "uri": "https://docs.test/doc-1"}],
                    )

            with patch.object(routes_agent_v3, "WorkspaceService", _FakeWorkspaceService):
                app.include_router(routes_agent_v3.make_v3_agent_router())
                with TestClient(app) as client:
                    yield client


def _build_check(
    *,
    name: str,
    details: dict[str, Any],
    expectations: dict[str, Any],
    required_fields: tuple[str, ...] = (),
    computed: dict[str, Any] | None = None,
    passed_override: bool | None = None,
) -> GoogleWorkspaceSurfaceCheckResult:
    merged_details = dict(details)
    if computed:
        merged_details.update(computed)
    mismatches: dict[str, dict[str, Any]] = {}
    for key, expected in expectations.items():
        actual = merged_details.get(key)
        if actual != expected:
            mismatches[key] = {"expected": expected, "actual": actual}
    for key in required_fields:
        if not merged_details.get(key):
            mismatches[key] = {"expected": "non-empty", "actual": merged_details.get(key)}
    passed = passed_override if passed_override is not None else not mismatches
    return GoogleWorkspaceSurfaceCheckResult(name=name, passed=bool(passed), details=merged_details, mismatches=mismatches)


def render_google_workspace_surface_report_markdown(report: GoogleWorkspaceSurfaceValidationReport) -> str:
    lines = [
        "# Google Workspace Surface Validation Report",
        "",
        f"- Checks: {report.num_checks}",
        f"- Passed: {report.num_passed}",
        f"- Failed: {report.num_failed}",
        "",
        "| Check | Pass | Key Details | Mismatch |",
        "| --- | --- | --- | --- |",
    ]
    for item in report.results:
        detail_text = ", ".join(f"{key}={json.dumps(value, ensure_ascii=False)}" for key, value in item.details.items())
        mismatch_text = ", ".join(
            f"{key}: expected {json.dumps(value['expected'], ensure_ascii=False)} got {json.dumps(value['actual'], ensure_ascii=False)}"
            for key, value in item.mismatches.items()
        )
        lines.append(
            f"| {item.name} | {'yes' if item.passed else 'no'} | {detail_text or '-'} | {mismatch_text or '-'} |"
        )
    return "\n".join(lines) + "\n"


def write_google_workspace_surface_report(
    report: GoogleWorkspaceSurfaceValidationReport, *, out_dir: Path
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report_v1.json"
    md_path = out_dir / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_google_workspace_surface_report_markdown(report), encoding="utf-8")
    return json_path, md_path


def _load_skill_module():
    path = Path("skills-src/chatgptrest-call/scripts/chatgptrest_call.py").resolve()
    spec = importlib.util.spec_from_file_location("chatgptrest_call_skill_validation", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
