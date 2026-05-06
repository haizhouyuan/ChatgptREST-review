"""Obsidian Local REST API integration — production-grade client.

Provides a robust client for the Obsidian Local REST API plugin
(https://github.com/coddingtonbear/obsidian-local-rest-api).

Verified endpoints (plugin v2.x):
  GET  /             → server status / auth check
  GET  /files        → list all files: [{"path": "folder/note.md"}, ...]
  GET  /vault/{path} → read file content (Accept: text/markdown)
  PUT  /vault/{path} → create or overwrite file
  POST /vault/{path} → append to file
  POST /search/simple/ → search vault by query

Features:
  - Automatic retry with exponential backoff (3 attempts)
  - Per-request timeouts (never blocks the caller indefinitely)
  - Structured error classification
  - Folder/tag-based file filtering
  - HTTPS certificate verification disabled (plugin uses self-signed cert)
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
import urllib.parse
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


# ── Defaults ──────────────────────────────────────────────────────

def _default_api_url() -> str:
    return os.environ.get(
        "OPENMIND_OBSIDIAN_API_URL", "https://127.0.0.1:27124"
    ).rstrip("/")


def _default_api_key() -> str:
    return os.environ.get("OPENMIND_OBSIDIAN_API_KEY", "")


def _sync_folders() -> list[str]:
    """Folders to sync. Empty = sync everything."""
    raw = os.environ.get("OPENMIND_OBSIDIAN_SYNC_FOLDERS", "")
    return [f.strip().rstrip("/") for f in raw.split(",") if f.strip()]


def _sync_tags() -> list[str]:
    """Tags to filter by. Empty = no tag filter."""
    raw = os.environ.get("OPENMIND_OBSIDIAN_SYNC_TAGS", "")
    return [t.strip().lstrip("#") for t in raw.split(",") if t.strip()]


# ── Error types ───────────────────────────────────────────────────

class ObsidianAPIError(Exception):
    """Base error for Obsidian API calls."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ObsidianNotConnected(ObsidianAPIError):
    """Obsidian is not reachable (connection refused / timeout)."""
    pass


class ObsidianAuthError(ObsidianAPIError):
    """Authentication failed (401/403)."""
    pass


# ── Client ────────────────────────────────────────────────────────

class ObsidianClient:
    """Production-grade client for Obsidian Local REST API.

    Usage::

        client = ObsidianClient()
        if client.ping():
            files = client.list_files()
            content = client.read_file("Notes/idea.md")
            client.write_file("Inbox/report.md", "# Report\\n...")
    """

    REQUEST_TIMEOUT = 10  # seconds per request
    MAX_RETRIES = 3

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.api_url = api_url or _default_api_url()
        self.api_key = api_key or _default_api_key()
        self._sync_folders = _sync_folders()
        self._sync_tags = _sync_tags()

        # Build a session with retry
        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "PUT", "POST", "PATCH"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
            })

    # ── Config helpers ────────────────────────────────────────────

    def is_configured(self) -> bool:
        """Check if API URL and key are set."""
        return bool(self.api_url and self.api_key)

    # ── Core HTTP ─────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict | None = None,
        data: bytes | str | None = None,
        json_body: dict | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        """Make an HTTP request with error classification."""
        url = f"{self.api_url}{path}"
        try:
            resp = self.session.request(
                method,
                url,
                headers=headers or {},
                data=data,
                json=json_body,
                timeout=timeout or self.REQUEST_TIMEOUT,
                verify=False,  # plugin uses self-signed cert
            )
        except requests.ConnectionError as e:
            raise ObsidianNotConnected(
                f"Cannot connect to Obsidian at {self.api_url}: {e}"
            ) from e
        except requests.Timeout as e:
            raise ObsidianNotConnected(
                f"Obsidian request timed out: {e}"
            ) from e

        if resp.status_code in (401, 403):
            raise ObsidianAuthError(
                f"Obsidian auth failed ({resp.status_code})",
                status_code=resp.status_code,
            )

        return resp

    # ── Connection ────────────────────────────────────────────────

    def ping(self) -> bool:
        """Test connection to Obsidian. Returns True if reachable."""
        if not self.is_configured():
            return False
        try:
            resp = self._request("GET", "/", timeout=5)
            return resp.status_code == 200
        except (ObsidianAPIError, Exception) as e:
            logger.debug("Obsidian ping failed: %s", e)
            return False

    # ── File listing ──────────────────────────────────────────────

    def list_files(self, extension: str = ".md") -> list[dict[str, Any]]:
        """List all files in the vault.

        Uses GET /files which returns: [{"path": "folder/note.md"}, ...]
        Filters by extension (default .md) and configured sync folders.

        Returns:
            List of dicts with at least {"path": "..."}.
        """
        if not self.is_configured():
            return []

        try:
            resp = self._request("GET", "/files")
        except ObsidianAPIError as e:
            logger.error("Failed to list Obsidian files: %s", e)
            return []

        if resp.status_code != 200:
            logger.warning(
                "Obsidian /files returned %s: %s",
                resp.status_code, resp.text[:200],
            )
            return []

        try:
            data = resp.json()
        except ValueError:
            logger.error("Obsidian /files returned non-JSON response")
            return []

        # Normalize: API returns [{"path": "..."}, ...] or sometimes just ["path", ...]
        files: list[dict[str, Any]] = []
        if isinstance(data, dict) and "files" in data:
            raw_files = data["files"]
        elif isinstance(data, list):
            raw_files = data
        else:
            logger.warning("Unexpected /files format: %s", type(data))
            return []

        for item in raw_files:
            if isinstance(item, str):
                path = item
            elif isinstance(item, dict):
                path = item.get("path", "")
            else:
                continue

            if not path:
                continue

            # Extension filter
            if extension and not path.endswith(extension):
                continue

            # Folder filter
            if self._sync_folders:
                matched = any(
                    path.startswith(folder + "/") or path.startswith(folder + "\\")
                    for folder in self._sync_folders
                )
                if not matched:
                    continue

            if isinstance(item, dict):
                files.append(item)
            else:
                files.append({"path": path})

        return files

    # ── File reading ──────────────────────────────────────────────

    def read_file(self, file_path: str) -> str:
        """Read the markdown content of a file.

        Uses GET /vault/{path} with Accept: text/markdown.
        Returns empty string on error or if file not found.
        """
        if not self.is_configured():
            return ""

        encoded = urllib.parse.quote(file_path.lstrip("/"), safe="/")
        try:
            resp = self._request(
                "GET",
                f"/vault/{encoded}",
                headers={"Accept": "text/markdown"},
            )
        except ObsidianAPIError as e:
            logger.error("Failed to read '%s': %s", file_path, e)
            return ""

        if resp.status_code == 200:
            return resp.text
        if resp.status_code == 404:
            return ""

        logger.warning(
            "Obsidian read '%s' returned %s", file_path, resp.status_code,
        )
        return ""

    # ── File writing ──────────────────────────────────────────────

    def write_file(self, file_path: str, content: str, *, append: bool = False) -> bool:
        """Write content to a file in the vault.

        Uses PUT /vault/{path} for create/overwrite.
        Uses POST /vault/{path} for append.

        Args:
            file_path: Vault-relative path (e.g. "Inbox/Note.md")
            content: Markdown content
            append: If True, append instead of overwrite

        Returns:
            True on success.
        """
        if not self.is_configured():
            logger.warning("Obsidian not configured, skipping write to %s", file_path)
            return False

        encoded = urllib.parse.quote(file_path.lstrip("/"), safe="/")
        method = "POST" if append else "PUT"

        try:
            resp = self._request(
                method,
                f"/vault/{encoded}",
                headers={"Content-Type": "text/markdown"},
                data=content.encode("utf-8"),
            )
        except ObsidianAPIError as e:
            logger.error("Failed to write '%s': %s", file_path, e)
            return False

        if resp.status_code in (200, 201, 204):
            logger.info("Obsidian write OK: %s (%s)", file_path, method)
            return True

        logger.error(
            "Obsidian write '%s' failed: %s %s",
            file_path, resp.status_code, resp.text[:200],
        )
        return False

    # ── Search ────────────────────────────────────────────────────

    def search(self, query: str, context_length: int = 100) -> list[dict[str, Any]]:
        """Search the vault using Obsidian's built-in search.

        Uses POST /search/simple/ with query body.

        Returns:
            List of search results, each with "filename" and "matches".
        """
        if not self.is_configured():
            return []

        try:
            resp = self._request(
                "POST",
                "/search/simple/",
                headers={"Content-Type": "application/json"},
                json_body={"query": query, "contextLength": context_length},
            )
        except ObsidianAPIError as e:
            logger.error("Obsidian search failed: %s", e)
            return []

        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                return []

        logger.warning("Obsidian search returned %s", resp.status_code)
        return []

    # ── Utility ───────────────────────────────────────────────────

    @staticmethod
    def content_hash(content: str) -> str:
        """SHA-256 hash of content for dedup."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def has_tag(self, content: str, tags: list[str] | None = None) -> bool:
        """Check if markdown content contains any of the specified tags.

        Looks for #tag patterns in the content and YAML frontmatter tags.
        """
        check_tags = tags or self._sync_tags
        if not check_tags:
            return True  # no filter = always match

        content_lower = content.lower()
        for tag in check_tags:
            tag_lower = tag.lower().lstrip("#")
            # Check inline #tag
            if f"#{tag_lower}" in content_lower:
                return True
            # Check YAML frontmatter tags: [tag1, tag2]
            if tag_lower in content_lower:
                return True
        return False
