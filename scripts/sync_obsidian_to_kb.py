#!/usr/bin/env python3
"""Sync Obsidian Vault → OpenMind KBHub (production-grade).

Supports TWO modes:
  1. LOCAL mode (recommended): Reads .md files directly from a local vault
     directory (synced via rclone/Syncthing/Obsidian Sync).
     Set: OPENMIND_OBSIDIAN_VAULT_PATH=/path/to/vault

  2. API mode (fallback): Reads via Obsidian Local REST API plugin.
     Set: OPENMIND_OBSIDIAN_API_KEY=your-key

LOCAL mode is 100x faster and does not require Obsidian to be running.

Usage:
    PYTHONPATH=. python scripts/sync_obsidian_to_kb.py

Environment Variables:
    OPENMIND_OBSIDIAN_VAULT_PATH   - Local vault directory (enables LOCAL mode)
    OPENMIND_OBSIDIAN_API_URL      - Obsidian REST API URL (API mode)
    OPENMIND_OBSIDIAN_API_KEY      - Bearer token (API mode)
    OPENMIND_OBSIDIAN_SYNC_FOLDERS - Folders to sync (comma-separated, empty=all)
    OPENMIND_OBSIDIAN_SYNC_TAGS    - Tags to filter (comma-separated, empty=all)
    CHATGPTREST_KB_DB_PATH         - KB SQLite path
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("obsidian_sync")


# ── Sync State DB ─────────────────────────────────────────────────

def _get_sync_db_path() -> str:
    artifact_dir = os.environ.get(
        "OPENMIND_KB_ARTIFACT_DIR",
        "/vol1/1000/projects/ChatgptREST/data/kb",
    )
    os.makedirs(artifact_dir, exist_ok=True)
    return os.path.join(artifact_dir, "obsidian_sync.db")


def _init_sync_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            path         TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            synced_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def _get_stored_hash(conn: sqlite3.Connection, path: str) -> str:
    row = conn.execute(
        "SELECT content_hash FROM sync_state WHERE path = ?", (path,)
    ).fetchone()
    return row[0] if row else ""


def _update_hash(conn: sqlite3.Connection, path: str, content_hash: str) -> None:
    conn.execute(
        """INSERT INTO sync_state (path, content_hash)
           VALUES (?, ?)
           ON CONFLICT(path) DO UPDATE SET
             content_hash = excluded.content_hash,
             synced_at = datetime('now')""",
        (path, content_hash),
    )
    conn.commit()


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ── Filtering ─────────────────────────────────────────────────────

def _get_sync_folders() -> list[str]:
    raw = os.environ.get("OPENMIND_OBSIDIAN_SYNC_FOLDERS", "")
    return [f.strip().rstrip("/") for f in raw.split(",") if f.strip()]


def _get_sync_tags() -> list[str]:
    raw = os.environ.get("OPENMIND_OBSIDIAN_SYNC_TAGS", "")
    return [t.strip().lstrip("#") for t in raw.split(",") if t.strip()]


def _matches_folder(path: str, folders: list[str]) -> bool:
    if not folders:
        return True
    return any(path.startswith(f + "/") for f in folders)


def _has_tag(content: str, tags: list[str]) -> bool:
    if not tags:
        return True
    content_lower = content.lower()
    for tag in tags:
        if f"#{tag.lower()}" in content_lower:
            return True
        if tag.lower() in content_lower:
            return True
    return False


# ── LOCAL mode: read from filesystem ──────────────────────────────

def scan_local_vault(vault_path: str) -> list[tuple[str, str]]:
    """Scan local vault directory for .md files.

    Returns list of (relative_path, full_content).
    """
    vault = Path(vault_path)
    if not vault.is_dir():
        logger.error("Vault path does not exist: %s", vault_path)
        return []

    folders = _get_sync_folders()
    tags = _get_sync_tags()
    results: list[tuple[str, str]] = []

    for md_file in vault.rglob("*.md"):
        # Skip hidden directories (.obsidian, .trash, .git)
        parts = md_file.relative_to(vault).parts
        if any(p.startswith(".") for p in parts):
            continue

        rel_path = str(md_file.relative_to(vault))

        # Folder filter
        if not _matches_folder(rel_path, folders):
            continue

        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning("Cannot read %s: %s", rel_path, e)
            continue

        if not content.strip():
            continue

        # Tag filter
        if not _has_tag(content, tags):
            continue

        results.append((rel_path, content))

    return results


# ── API mode: read from Obsidian REST API ─────────────────────────

def scan_api_vault() -> list[tuple[str, str]]:
    """Scan vault via Obsidian Local REST API.

    Returns list of (path, content).
    """
    from chatgptrest.integrations.obsidian_api import ObsidianClient

    client = ObsidianClient()
    if not client.is_configured():
        logger.error("Obsidian API not configured.")
        return []
    if not client.ping():
        logger.error("Cannot connect to Obsidian at %s", client.api_url)
        return []

    logger.info("Connected to Obsidian API at %s", client.api_url)
    md_files = client.list_files(extension=".md")
    logger.info("Found %d files.", len(md_files))

    results: list[tuple[str, str]] = []
    tags = _get_sync_tags()

    for file_info in md_files:
        path = file_info.get("path", "")
        if not path:
            continue
        try:
            content = client.read_file(path)
            if not content.strip():
                continue
            if not _has_tag(content, tags):
                continue
            results.append((path, content))
        except Exception as e:
            logger.warning("Failed to read %s: %s", path, e)

    return results


# ── Main ──────────────────────────────────────────────────────────

def main() -> None:
    load_dotenv()

    # Late import
    from chatgptrest.kb.hub import KBHub

    vault_path = os.environ.get("OPENMIND_OBSIDIAN_VAULT_PATH", "")

    # Choose mode
    if vault_path:
        logger.info("MODE: LOCAL filesystem (%s)", vault_path)
        files = scan_local_vault(vault_path)
    else:
        logger.info("MODE: Obsidian REST API")
        files = scan_api_vault()

    if not files:
        logger.info("No files to sync.")
        return

    logger.info("Processing %d markdown files.", len(files))

    # Initialize KB
    db_path = os.environ.get(
        "CHATGPTREST_KB_DB_PATH",
        "/vol1/1000/projects/ChatgptREST/data/kb/kb.db",
    )
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    vec_path = db_path.replace(".db", "_vec.db") if db_path != ":memory:" else None
    hub = KBHub(db_path=db_path, vec_db_path=vec_path)

    # Sync state
    sync_conn = _init_sync_db(_get_sync_db_path())

    synced = 0
    skipped = 0
    errors = 0

    for rel_path, content in files:
        try:
            current_hash = _content_hash(content)
            stored_hash = _get_stored_hash(sync_conn, rel_path)

            if current_hash == stored_hash:
                skipped += 1
                continue

            title = Path(rel_path).stem
            artifact_id = f"obsidian::{rel_path}"

            hub.index_document(
                artifact_id=artifact_id,
                title=title,
                content=content,
                source_path=rel_path,
                tags=["obsidian"],
                content_type="markdown",
                author="obsidian_sync",
            )

            _update_hash(sync_conn, rel_path, current_hash)
            synced += 1
            logger.info("Synced: %s", rel_path)

        except Exception:
            logger.exception("Failed to sync %s", rel_path)
            errors += 1

    logger.info(
        "Obsidian sync complete. Synced: %d | Skipped: %d | Errors: %d",
        synced, skipped, errors,
    )

    hub.close()
    sync_conn.close()


if __name__ == "__main__":
    main()
