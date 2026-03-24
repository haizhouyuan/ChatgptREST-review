"""Google Workspace integration adapter for OpenMind V3.

Provides a unified interface to Google Workspace services:
  - Google Drive (files, folders, sharing)
  - Google Calendar (events, free/busy)
  - Google Sheets (read/write cells)
  - Google Docs (create/read documents)
  - Gmail (send emails)
  - Google Tasks (create/list tasks)

Authentication:
  Uses OAuth 2.0 Desktop App flow. First run requires browser authorization.
  Token is cached at OPENMIND_GOOGLE_TOKEN_PATH (default: ~/.openmind/google_token.json).

Usage::

    from chatgptrest.integrations.google_workspace import GoogleWorkspace

    gw = GoogleWorkspace()
    gw.authenticate()

    # Drive
    files = gw.drive_list_files(query="name contains 'report'")
    url = gw.drive_upload_file("/path/to/report.md", folder_id="...")

    # Calendar
    events = gw.calendar_list_events(time_min="2026-03-01T00:00:00Z")

    # Sheets
    data = gw.sheets_read("spreadsheet_id", "Sheet1!A1:D10")
    gw.sheets_write("spreadsheet_id", "Sheet1!A1", [["col1", "col2"], ["val1", "val2"]])
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Scopes for Google Workspace services
_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/tasks",
]


def _default_credentials_path() -> str:
    return os.environ.get(
        "OPENMIND_GOOGLE_CREDENTIALS_PATH",
        os.path.expanduser("~/.openmind/google_credentials.json"),
    )


def _default_token_path() -> str:
    return os.environ.get(
        "OPENMIND_GOOGLE_TOKEN_PATH",
        os.path.expanduser("~/.openmind/google_token.json"),
    )


def _enabled_services() -> set[str]:
    """Parse OPENMIND_GOOGLE_SERVICES env var (CSV). Empty = all."""
    raw = os.environ.get("OPENMIND_GOOGLE_SERVICES", "").strip()
    if not raw:
        return {"drive", "calendar", "sheets", "docs", "gmail", "tasks"}
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


class GoogleWorkspace:
    """Unified Google Workspace client for OpenMind V3."""

    def __init__(
        self,
        credentials_path: str | None = None,
        token_path: str | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        self._credentials_path = credentials_path or _default_credentials_path()
        self._token_path = token_path or _default_token_path()
        self._scopes = scopes or _SCOPES
        self._creds: Any = None
        self._services: dict[str, Any] = {}
        self._enabled = _enabled_services()
        
        # Enforce a global timeout so API hangs won't freeze the system
        import socket
        socket.setdefaulttimeout(15.0)

    # ── Authentication ───────────────────────────────────────────────

    def authenticate(self, *, headless: bool = False) -> bool:
        """Authenticate with Google using OAuth 2.0.

        Args:
            headless: If True, use console-based auth flow (no local browser).

        Returns:
            True if authentication succeeded.
        """
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            logger.error(
                "Google auth libraries not installed. "
                "Run: pip install google-api-python-client google-auth-oauthlib"
            )
            return False

        creds = None

        # Try loading existing token
        if os.path.exists(self._token_path):
            try:
                creds = Credentials.from_authorized_user_file(self._token_path, self._scopes)
                logger.info("Loaded existing Google token from %s", self._token_path)
            except Exception as exc:
                logger.warning("Failed to load token: %s", exc)
                creds = None

        # Refresh or create new token
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Refreshed Google token")
            except Exception as exc:
                logger.warning("Token refresh failed: %s — re-authorizing", exc)
                creds = None

        if not creds or not creds.valid:
            if not os.path.exists(self._credentials_path):
                logger.error(
                    "Google credentials not found at %s. "
                    "Download from Google Cloud Console → APIs & Services → Credentials.",
                    self._credentials_path,
                )
                return False

            flow = InstalledAppFlow.from_client_secrets_file(
                self._credentials_path, self._scopes
            )
            if headless:
                logger.warning(
                    "OOB (run_console) is deprecated by Google. "
                    "Starting local server to receive the auth token. "
                    "You will see a 'Please visit this URL' message. "
                    "Click it, authorize, and if it redirects to localhost:PORT, "
                    "you will need to SSH port-forward that PORT to your browser."
                )
                creds = flow.run_local_server(port=0, open_browser=False)
            else:
                creds = flow.run_local_server(port=0)

            # Save token for future use
            token_dir = os.path.dirname(self._token_path)
            if token_dir:
                os.makedirs(token_dir, exist_ok=True)
            with open(self._token_path, "w") as f:
                f.write(creds.to_json())
            logger.info("Saved new Google token to %s", self._token_path)

        self._creds = creds
        return True

    def load_token(self) -> bool:
        """Attempt to load existing token without triggering a new OAuth flow."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError:
            return False

        if not os.path.exists(self._token_path):
            return False

        try:
            creds = Credentials.from_authorized_user_file(self._token_path, self._scopes)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            self._creds = creds
            return self.is_authenticated()
        except Exception as exc:
            logger.warning("Failed to silently load Google token: %s", exc)
            return False

    def is_authenticated(self) -> bool:
        """Check if credentials are valid."""
        return self._creds is not None and self._creds.valid

    def _get_service(self, service_name: str, version: str) -> Any:
        """Get or create a Google API service client."""
        key = f"{service_name}:{version}"
        if key not in self._services:
            from googleapiclient.discovery import build

            self._services[key] = build(service_name, version, credentials=self._creds)
        return self._services[key]

    # ── Google Drive ────────────────────────────────────────────────

    def drive_list_files(
        self,
        query: str = "",
        page_size: int = 20,
        fields: str = "files(id, name, mimeType, modifiedTime, webViewLink)",
    ) -> list[dict[str, Any]]:
        """List files from Google Drive.

        Args:
            query: Drive search query (e.g. "name contains 'report'")
            page_size: Max results per page
            fields: Fields to include in response

        Returns:
            List of file metadata dicts.
        """
        if "drive" not in self._enabled:
            logger.warning("Drive service not enabled")
            return []

        svc = self._get_service("drive", "v3")
        try:
            results = svc.files().list(
                q=query or None,
                pageSize=page_size,
                fields=f"nextPageToken, {fields}",
            ).execute()
            return results.get("files", [])
        except Exception as exc:
            logger.error("Drive list failed: %s", exc)
            return []

    def drive_upload_file(
        self,
        local_path: str,
        *,
        folder_id: str = "",
        name: str = "",
        mime_type: str = "",
    ) -> dict[str, Any]:
        """Upload a file to Google Drive.

        Args:
            local_path: Path to local file
            folder_id: Target folder ID (empty = root)
            name: File name in Drive (default: basename of local_path)
            mime_type: MIME type (auto-detected if empty)

        Returns:
            File metadata dict with id, name, webViewLink.
        """
        if "drive" not in self._enabled:
            return {"error": "Drive service not enabled"}

        from googleapiclient.http import MediaFileUpload

        svc = self._get_service("drive", "v3")
        file_name = name or os.path.basename(local_path)

        file_metadata: dict[str, Any] = {"name": file_name}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaFileUpload(
            local_path,
            mimetype=mime_type or None,
            resumable=True,
        )

        try:
            result = svc.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, name, webViewLink, mimeType",
            ).execute()
            logger.info("Uploaded %s → Drive id=%s", local_path, result.get("id"))
            return result
        except Exception as exc:
            logger.error("Drive upload failed: %s", exc)
            return {"error": str(exc)}

    def drive_create_folder(self, name: str, *, parent_id: str = "") -> dict[str, Any]:
        """Create a folder in Google Drive."""
        if "drive" not in self._enabled:
            return {"error": "Drive service not enabled"}

        svc = self._get_service("drive", "v3")
        metadata: dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        try:
            result = svc.files().create(
                body=metadata, fields="id, name, webViewLink"
            ).execute()
            return result
        except Exception as exc:
            logger.error("Drive folder creation failed: %s", exc)
            return {"error": str(exc)}

    def drive_download_file(self, file_id: str, local_path: str) -> bool:
        """Download a file from Google Drive."""
        if "drive" not in self._enabled:
            return False

        from googleapiclient.http import MediaIoBaseDownload
        import io

        svc = self._get_service("drive", "v3")
        try:
            request = svc.files().get_media(fileId=file_id)
            os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
            with open(local_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            logger.info("Downloaded Drive file %s → %s", file_id, local_path)
            return True
        except Exception as exc:
            logger.error("Drive download failed: %s", exc)
            return False

    # ── Google Calendar ──────────────────────────────────────────────

    def calendar_list_events(
        self,
        *,
        calendar_id: str = "primary",
        time_min: str = "",
        time_max: str = "",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """List upcoming events from Google Calendar.

        Args:
            calendar_id: Calendar ID (default: primary)
            time_min: ISO 8601 start time (default: now)
            time_max: ISO 8601 end time (optional)
            max_results: Max events to return

        Returns:
            List of event dicts.
        """
        if "calendar" not in self._enabled:
            return []

        svc = self._get_service("calendar", "v3")
        if not time_min:
            time_min = datetime.now(timezone.utc).isoformat()

        try:
            kwargs: dict[str, Any] = {
                "calendarId": calendar_id,
                "timeMin": time_min,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }
            if time_max:
                kwargs["timeMax"] = time_max

            results = svc.events().list(**kwargs).execute()
            return results.get("items", [])
        except Exception as exc:
            logger.error("Calendar list failed: %s", exc)
            return []

    def calendar_create_event(
        self,
        *,
        summary: str,
        start: str,
        end: str,
        description: str = "",
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Create a calendar event."""
        if "calendar" not in self._enabled:
            return {"error": "Calendar service not enabled"}

        svc = self._get_service("calendar", "v3")
        event_body: dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }
        if description:
            event_body["description"] = description

        try:
            result = svc.events().insert(
                calendarId=calendar_id, body=event_body
            ).execute()
            return result
        except Exception as exc:
            logger.error("Calendar create event failed: %s", exc)
            return {"error": str(exc)}

    # ── Google Sheets ────────────────────────────────────────────────

    def sheets_read(
        self, spreadsheet_id: str, range_name: str
    ) -> list[list[str]]:
        """Read data from a Google Sheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            range_name: A1 notation range (e.g. "Sheet1!A1:D10")

        Returns:
            2D list of cell values.
        """
        if "sheets" not in self._enabled:
            return []

        svc = self._get_service("sheets", "v4")
        try:
            result = svc.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id, range=range_name
            ).execute()
            return result.get("values", [])
        except Exception as exc:
            logger.error("Sheets read failed: %s", exc)
            return []

    def sheets_write(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
        *,
        value_input_option: str = "USER_ENTERED",
    ) -> dict[str, Any]:
        """Write data to a Google Sheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            range_name: A1 notation range
            values: 2D list of values to write
            value_input_option: How input data should be interpreted

        Returns:
            Update response dict.
        """
        if "sheets" not in self._enabled:
            return {"error": "Sheets service not enabled"}

        svc = self._get_service("sheets", "v4")
        try:
            body = {"values": values}
            result = svc.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body,
            ).execute()
            return result
        except Exception as exc:
            logger.error("Sheets write failed: %s", exc)
            return {"error": str(exc)}

    def sheets_create(self, title: str) -> dict[str, Any]:
        """Create a new Google Sheet."""
        if "sheets" not in self._enabled:
            return {"error": "Sheets service not enabled"}

        svc = self._get_service("sheets", "v4")
        try:
            body = {"properties": {"title": title}}
            result = svc.spreadsheets().create(body=body).execute()
            return {
                "spreadsheet_id": result["spreadsheetId"],
                "url": result["spreadsheetUrl"],
            }
        except Exception as exc:
            logger.error("Sheets create failed: %s", exc)
            return {"error": str(exc)}

    # ── Google Docs ──────────────────────────────────────────────────

    def docs_create(self, title: str, *, body_text: str = "") -> dict[str, Any]:
        """Create a new Google Doc.

        Args:
            title: Document title
            body_text: Initial plain text content (optional)

        Returns:
            Dict with documentId, url.
        """
        if "docs" not in self._enabled:
            return {"error": "Docs service not enabled"}

        svc = self._get_service("docs", "v1")
        try:
            doc = svc.documents().create(body={"title": title}).execute()
            doc_id = doc["documentId"]

            if body_text:
                svc.documents().batchUpdate(
                    documentId=doc_id,
                    body={
                        "requests": [
                            {
                                "insertText": {
                                    "location": {"index": 1},
                                    "text": body_text,
                                }
                            }
                        ]
                    },
                ).execute()

            return {
                "document_id": doc_id,
                "url": f"https://docs.google.com/document/d/{doc_id}/edit",
            }
        except Exception as exc:
            logger.error("Docs create failed: %s", exc)
            return {"error": str(exc)}

    def docs_read(self, document_id: str) -> str:
        """Read the text content of a Google Doc."""
        if "docs" not in self._enabled:
            return ""

        svc = self._get_service("docs", "v1")
        try:
            doc = svc.documents().get(documentId=document_id).execute()
            # Extract plain text from document body
            text_parts: list[str] = []
            for element in doc.get("body", {}).get("content", []):
                if "paragraph" in element:
                    for pe in element["paragraph"].get("elements", []):
                        if "textRun" in pe:
                            text_parts.append(pe["textRun"]["content"])
            return "".join(text_parts)
        except Exception as exc:
            logger.error("Docs read failed: %s", exc)
            return ""

    # ── Gmail ────────────────────────────────────────────────────────

    def gmail_send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
    ) -> dict[str, Any]:
        """Send an email via Gmail.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text or HTML)
            html: If True, body is treated as HTML

        Returns:
            Message metadata dict.
        """
        if "gmail" not in self._enabled:
            return {"error": "Gmail service not enabled"}

        import base64
        from email.mime.text import MIMEText

        svc = self._get_service("gmail", "v1")
        mime_type = "html" if html else "plain"
        message = MIMEText(body, mime_type)
        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        try:
            result = svc.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
            logger.info("Sent email to %s, id=%s", to, result.get("id"))
            return result
        except Exception as exc:
            logger.error("Gmail send failed: %s", exc)
            return {"error": str(exc)}

    # ── Google Tasks ─────────────────────────────────────────────────

    def tasks_list(self, *, tasklist_id: str = "@default", max_results: int = 20) -> list[dict]:
        """List tasks from Google Tasks."""
        if "tasks" not in self._enabled:
            return []

        svc = self._get_service("tasks", "v1")
        try:
            results = svc.tasks().list(
                tasklist=tasklist_id, maxResults=max_results
            ).execute()
            return results.get("items", [])
        except Exception as exc:
            logger.error("Tasks list failed: %s", exc)
            return []

    def tasks_create(
        self,
        *,
        title: str,
        notes: str = "",
        due: str = "",
        tasklist_id: str = "@default",
    ) -> dict[str, Any]:
        """Create a task in Google Tasks.

        Args:
            title: Task title
            notes: Task notes/description
            due: Due date in RFC 3339 format
            tasklist_id: Task list ID

        Returns:
            Task metadata dict.
        """
        if "tasks" not in self._enabled:
            return {"error": "Tasks service not enabled"}

        svc = self._get_service("tasks", "v1")
        task_body: dict[str, Any] = {"title": title}
        if notes:
            task_body["notes"] = notes
        if due:
            task_body["due"] = due

        try:
            result = svc.tasks().insert(
                tasklist=tasklist_id, body=task_body
            ).execute()
            return result
        except Exception as exc:
            logger.error("Tasks create failed: %s", exc)
            return {"error": str(exc)}

    # ── Status / Health ──────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return integration health status."""
        result: dict[str, Any] = {
            "authenticated": self.is_authenticated(),
            "credentials_path": self._credentials_path,
            "credentials_exists": os.path.exists(self._credentials_path),
            "token_path": self._token_path,
            "token_exists": os.path.exists(self._token_path),
            "enabled_services": sorted(self._enabled),
            "active_services": sorted(self._services.keys()),
        }
        if self._creds:
            result["token_expired"] = bool(self._creds.expired)
            result["token_expiry"] = str(self._creds.expiry) if self._creds.expiry else None
        return result
