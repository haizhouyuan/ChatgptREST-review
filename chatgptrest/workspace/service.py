from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable

from chatgptrest.workspace.contracts import WorkspaceActionResult, WorkspaceRequest

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Northbound Google Workspace task service built on the existing adapter."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], Any] | None = None,
        artifact_root: str | Path | None = None,
    ) -> None:
        self._client_factory = client_factory or _default_client_factory
        self._artifact_root = Path(artifact_root or _default_artifact_root()).expanduser().resolve()

    def auth_state(self) -> dict[str, Any]:
        try:
            client = self._client_factory()
        except Exception as exc:
            return {"ok": False, "error": str(exc), "enabled_services": []}
        ok = False
        try:
            ok = bool(client.load_token() and client.is_authenticated())
        except Exception as exc:
            return {"ok": False, "error": str(exc), "enabled_services": list(getattr(client, "_enabled", []))}
        return {
            "ok": ok,
            "enabled_services": sorted(list(getattr(client, "_enabled", []))),
            "token_path": str(getattr(client, "_token_path", "") or ""),
            "credentials_path": str(getattr(client, "_credentials_path", "") or ""),
        }

    def execute(self, request: WorkspaceRequest) -> WorkspaceActionResult:
        client = self._get_authenticated_client()
        if client is None:
            return WorkspaceActionResult(
                ok=False,
                action=request.action,
                status="failed",
                message="google_workspace_not_authenticated",
            )

        if request.action == "search_drive_files":
            return self._search_drive_files(client, request)
        if request.action == "fetch_drive_file":
            return self._fetch_drive_file(client, request)
        if request.action == "deliver_report_to_docs":
            return self._deliver_report_to_docs(client, request)
        if request.action == "append_sheet_rows":
            return self._append_sheet_rows(client, request)
        if request.action == "send_gmail_notice":
            return self._send_gmail_notice(client, request)
        return WorkspaceActionResult(
            ok=False,
            action=request.action,
            status="failed",
            message="unsupported_workspace_action",
        )

    def _get_authenticated_client(self) -> Any | None:
        try:
            client = self._client_factory()
        except Exception as exc:
            logger.warning("WorkspaceService client init failed: %s", exc)
            return None
        try:
            if client.load_token() and client.is_authenticated():
                return client
        except Exception as exc:
            logger.warning("WorkspaceService token load failed: %s", exc)
        return None

    def _search_drive_files(self, client: Any, request: WorkspaceRequest) -> WorkspaceActionResult:
        payload = dict(request.payload or {})
        files = client.drive_list_files(
            query=str(payload.get("query") or "").strip(),
            page_size=int(payload.get("page_size") or 20),
        )
        return WorkspaceActionResult(
            ok=True,
            action=request.action,
            status="completed",
            message=f"found {len(files)} drive files",
            data={"files": files},
        )

    def _fetch_drive_file(self, client: Any, request: WorkspaceRequest) -> WorkspaceActionResult:
        payload = dict(request.payload or {})
        file_id = str(payload.get("file_id") or "").strip()
        file_name = self._drive_file_name(client, file_id=file_id, default_name=str(payload.get("file_name") or "download.bin"))
        trace_id = str(request.trace_id or "workspace").strip() or "workspace"
        local_path = self._artifact_root / trace_id / "downloads" / file_name
        ok = client.drive_download_file(file_id, str(local_path))
        if not ok:
            return WorkspaceActionResult(
                ok=False,
                action=request.action,
                status="failed",
                message="drive_download_failed",
                data={"file_id": file_id, "local_path": str(local_path)},
            )
        metadata = self._drive_file_metadata(client, file_id=file_id)
        return WorkspaceActionResult(
            ok=True,
            action=request.action,
            status="completed",
            message=f"downloaded {file_name}",
            data={"file_id": file_id, "local_path": str(local_path), "metadata": metadata},
            artifacts=[{"kind": "downloaded_file", "path": str(local_path)}],
        )

    def _deliver_report_to_docs(self, client: Any, request: WorkspaceRequest) -> WorkspaceActionResult:
        payload = dict(request.payload or {})
        body_text = str(payload.get("body_markdown") or payload.get("body_text") or payload.get("body") or "")
        doc = client.docs_create(str(payload.get("title") or "").strip(), body_text=body_text)
        if "error" in doc:
            return WorkspaceActionResult(
                ok=False,
                action=request.action,
                status="failed",
                message=str(doc.get("error") or "docs_create_failed"),
                data={"request": request.to_dict()},
            )

        document_id = str(doc.get("document_id") or "")
        folder_result: dict[str, Any] | None = None
        target_folder = str(payload.get("target_folder") or "").strip()
        if target_folder:
            folder_id = self._ensure_drive_folder_path(client, target_folder)
            if folder_id:
                folder_result = {"folder_id": folder_id, "folder_path": target_folder}
                self._move_drive_file(client, file_id=document_id, folder_id=folder_id)

        email_result: dict[str, Any] | None = None
        notify_email = str(payload.get("notify_email") or "").strip()
        if notify_email:
            email_body = str(payload.get("notify_body_html") or "").strip()
            html = bool(email_body)
            if not email_body:
                email_body = str(payload.get("notify_body_text") or "").strip() or (
                    f"Document created: {str(doc.get('url') or '').strip()}"
                )
            email_result = client.gmail_send(
                to=notify_email,
                subject=str(payload.get("notify_subject") or f"[Workspace] {payload.get('title') or 'Document'}"),
                body=email_body,
                html=html,
            )

        data: dict[str, Any] = {
            "document_id": document_id,
            "url": str(doc.get("url") or ""),
        }
        if folder_result:
            data["folder"] = folder_result
        if email_result:
            data["gmail"] = email_result
        return WorkspaceActionResult(
            ok=True,
            action=request.action,
            status="completed",
            message="google doc delivered",
            data=data,
            artifacts=[
                {"kind": "google_doc", "uri": str(doc.get("url") or ""), "document_id": document_id},
            ],
        )

    def _append_sheet_rows(self, client: Any, request: WorkspaceRequest) -> WorkspaceActionResult:
        payload = dict(request.payload or {})
        spreadsheet_id = str(payload.get("spreadsheet_id") or "").strip()
        created_sheet: dict[str, Any] | None = None
        if not spreadsheet_id:
            created_sheet = client.sheets_create(str(payload.get("spreadsheet_title") or f"Workspace {int(time.time())}"))
            if "error" in created_sheet:
                return WorkspaceActionResult(
                    ok=False,
                    action=request.action,
                    status="failed",
                    message=str(created_sheet.get("error") or "sheets_create_failed"),
                )
            spreadsheet_id = str(created_sheet.get("spreadsheet_id") or "")

        range_name = str(payload.get("range_name") or "Sheet1!A:Z")
        rows = list(payload.get("rows") or [])
        svc = client._get_service("sheets", "v4")
        result = svc.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=str(payload.get("value_input_option") or "USER_ENTERED"),
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()
        data: dict[str, Any] = {
            "spreadsheet_id": spreadsheet_id,
            "range_name": range_name,
            "updated_range": str(result.get("updates", {}).get("updatedRange") or ""),
            "updated_rows": int(result.get("updates", {}).get("updatedRows") or 0),
        }
        if created_sheet:
            data["spreadsheet_url"] = str(created_sheet.get("url") or "")
        return WorkspaceActionResult(
            ok=True,
            action=request.action,
            status="completed",
            message="sheet rows appended",
            data=data,
            artifacts=(
                [{"kind": "google_sheet", "uri": str(created_sheet.get("url") or ""), "spreadsheet_id": spreadsheet_id}]
                if created_sheet else []
            ),
        )

    def _send_gmail_notice(self, client: Any, request: WorkspaceRequest) -> WorkspaceActionResult:
        payload = dict(request.payload or {})
        body_html = str(payload.get("body_html") or "").strip()
        result = client.gmail_send(
            to=str(payload.get("to") or "").strip(),
            subject=str(payload.get("subject") or "").strip(),
            body=body_html or str(payload.get("body_text") or "").strip(),
            html=bool(body_html),
        )
        if "error" in result:
            return WorkspaceActionResult(
                ok=False,
                action=request.action,
                status="failed",
                message=str(result.get("error") or "gmail_send_failed"),
            )
        return WorkspaceActionResult(
            ok=True,
            action=request.action,
            status="completed",
            message="gmail notice sent",
            data={"gmail": result},
        )

    def _ensure_drive_folder_path(self, client: Any, folder_path: str) -> str:
        current_parent = ""
        for part in [segment.strip() for segment in str(folder_path or "").split("/") if segment.strip()]:
            existing_id = self._find_drive_folder_id(client, name=part, parent_id=current_parent)
            if existing_id:
                current_parent = existing_id
                continue
            created = client.drive_create_folder(part, parent_id=current_parent)
            if "error" in created:
                raise RuntimeError(str(created.get("error") or f"failed to create drive folder {part}"))
            current_parent = str(created.get("id") or "")
        return current_parent

    def _find_drive_folder_id(self, client: Any, *, name: str, parent_id: str = "") -> str:
        safe_name = str(name or "").replace("'", "\\'")
        query = (
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false "
            f"and name = '{safe_name}'"
        )
        if parent_id:
            query += f" and '{parent_id}' in parents"
        matches = client.drive_list_files(query=query, page_size=10, fields="files(id, name, parents)")
        if not matches:
            return ""
        return str(matches[0].get("id") or "")

    def _move_drive_file(self, client: Any, *, file_id: str, folder_id: str) -> None:
        svc = client._get_service("drive", "v3")
        file_meta = svc.files().get(fileId=file_id, fields="parents").execute()
        previous_parents = ",".join(list(file_meta.get("parents") or []))
        svc.files().update(
            fileId=file_id,
            addParents=folder_id,
            removeParents=previous_parents or None,
            fields="id, parents",
        ).execute()

    def _drive_file_metadata(self, client: Any, *, file_id: str) -> dict[str, Any]:
        svc = client._get_service("drive", "v3")
        return svc.files().get(fileId=file_id, fields="id, name, mimeType, webViewLink").execute()

    def _drive_file_name(self, client: Any, *, file_id: str, default_name: str) -> str:
        try:
            metadata = self._drive_file_metadata(client, file_id=file_id)
            name = str(metadata.get("name") or "").strip()
            if name:
                return name
        except Exception:
            logger.debug("Drive metadata lookup failed for %s", file_id, exc_info=True)
        return default_name


def _default_client_factory() -> Any:
    from chatgptrest.integrations.google_workspace import GoogleWorkspace

    return GoogleWorkspace()


def _default_artifact_root() -> str:
    raw = str(os.environ.get("CHATGPTREST_WORKSPACE_ARTIFACTS_DIR", "")).strip()
    if raw:
        return raw
    return str(Path(__file__).resolve().parents[2] / "artifacts" / "workspace")
