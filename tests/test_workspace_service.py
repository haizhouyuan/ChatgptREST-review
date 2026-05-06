from __future__ import annotations

from pathlib import Path

from chatgptrest.workspace.contracts import build_workspace_request
from chatgptrest.workspace.service import WorkspaceService


class _FakeSheetsValues:
    def __init__(self):
        self.calls: list[dict] = []

    def append(self, **kwargs):
        self.calls.append(kwargs)

        class _Request:
            def execute(self_nonlocal):
                return {"updates": {"updatedRange": "Sheet1!A1:B2", "updatedRows": 2}}

        return _Request()


class _FakeSheetsSpreadsheets:
    def __init__(self, values):
        self._values = values

    def values(self):
        return self._values


class _FakeSheetsService:
    def __init__(self, values):
        self._spreadsheets = _FakeSheetsSpreadsheets(values)

    def spreadsheets(self):
        return self._spreadsheets


class _FakeDriveFiles:
    def __init__(self):
        self.get_calls: list[dict] = []
        self.update_calls: list[dict] = []

    def get(self, **kwargs):
        self.get_calls.append(kwargs)

        class _Request:
            def execute(self_nonlocal):
                if kwargs.get("fields") == "parents":
                    return {"parents": ["root"]}
                return {"id": kwargs["fileId"], "name": "downloaded.md", "mimeType": "text/markdown", "webViewLink": "https://drive.test/file"}

        return _Request()

    def update(self, **kwargs):
        self.update_calls.append(kwargs)

        class _Request:
            def execute(self_nonlocal):
                return {"id": kwargs["fileId"], "parents": [kwargs["addParents"]]}

        return _Request()


class _FakeDriveService:
    def __init__(self, files):
        self._files = files

    def files(self):
        return self._files


class _FakeGoogleWorkspace:
    def __init__(self):
        self._enabled = {"drive", "docs", "gmail", "sheets"}
        self._token_path = "/tmp/google-token.json"
        self._credentials_path = "/tmp/google-credentials.json"
        self.values = _FakeSheetsValues()
        self.drive_files = _FakeDriveFiles()
        self.gmail_calls: list[dict] = []
        self.uploads: list[tuple[str, str]] = []
        self.downloads: list[tuple[str, str]] = []
        self.created_folders: list[tuple[str, str]] = []

    def load_token(self):
        return True

    def is_authenticated(self):
        return True

    def _get_service(self, service_name: str, version: str):
        if service_name == "sheets":
            return _FakeSheetsService(self.values)
        if service_name == "drive":
            return _FakeDriveService(self.drive_files)
        raise AssertionError(f"unexpected service {service_name}:{version}")

    def drive_list_files(self, query: str = "", page_size: int = 20, fields: str = ""):
        if "mimeType = 'application/vnd.google-apps.folder'" in query:
            return []
        return [{"id": "file-1", "name": "Report", "webViewLink": "https://drive.test/report"}]

    def drive_download_file(self, file_id: str, local_path: str):
        self.downloads.append((file_id, local_path))
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_text("payload", encoding="utf-8")
        return True

    def drive_create_folder(self, name: str, *, parent_id: str = ""):
        self.created_folders.append((name, parent_id))
        return {"id": f"folder-{name}", "name": name, "webViewLink": f"https://drive.test/{name}"}

    def docs_create(self, title: str, *, body_text: str = ""):
        return {"document_id": "doc-1", "url": "https://docs.test/doc-1", "title": title, "body_text": body_text}

    def gmail_send(self, *, to: str, subject: str, body: str, html: bool = False):
        self.gmail_calls.append({"to": to, "subject": subject, "body": body, "html": html})
        return {"id": "gmail-1", "labelIds": ["SENT"]}

    def sheets_create(self, title: str):
        return {"spreadsheet_id": "sheet-1", "url": "https://sheets.test/sheet-1", "title": title}


def test_workspace_service_deliver_report_to_docs_moves_file_and_sends_email(tmp_path) -> None:
    service = WorkspaceService(client_factory=_FakeGoogleWorkspace, artifact_root=tmp_path)
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
        trace_id="trace-ws-1",
    )

    result = service.execute(request)

    assert result.ok is True
    assert result.data["document_id"] == "doc-1"
    assert result.data["folder"]["folder_path"] == "reports/daily"
    assert result.data["gmail"]["id"] == "gmail-1"


def test_workspace_service_fetch_drive_file_downloads_to_controlled_artifact_dir(tmp_path) -> None:
    service = WorkspaceService(client_factory=_FakeGoogleWorkspace, artifact_root=tmp_path)
    request = build_workspace_request(
        raw_request={"action": "fetch_drive_file", "payload": {"file_id": "file-123"}},
        trace_id="trace-ws-2",
    )

    result = service.execute(request)

    assert result.ok is True
    assert result.artifacts[0]["kind"] == "downloaded_file"
    assert str(tmp_path) in result.data["local_path"]


def test_workspace_service_append_sheet_rows_creates_sheet_when_missing_id(tmp_path) -> None:
    service = WorkspaceService(client_factory=_FakeGoogleWorkspace, artifact_root=tmp_path)
    request = build_workspace_request(
        raw_request={
            "action": "append_sheet_rows",
            "payload": {
                "spreadsheet_title": "Workspace Validation",
                "rows": [["A", "B"], ["1", "2"]],
            },
        },
        trace_id="trace-ws-3",
    )

    result = service.execute(request)

    assert result.ok is True
    assert result.data["spreadsheet_id"] == "sheet-1"
    assert result.data["updated_rows"] == 2
