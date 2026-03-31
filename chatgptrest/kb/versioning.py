"""KB Document Versioning — track changes, history, and rollback.

Provides:
  - KBVersionManager: Create, retrieve, list versions, diff, rollback
  - KBVersion dataclass: Version metadata and content
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# DDL for version table
_VERSION_DDL = """
CREATE TABLE IF NOT EXISTS kb_versions (
    doc_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    author TEXT DEFAULT 'system',
    change_note TEXT,
    PRIMARY KEY (doc_id, version)
);

CREATE INDEX IF NOT EXISTS idx_kb_versions_doc ON kb_versions(doc_id);
CREATE INDEX IF NOT EXISTS idx_kb_versions_time ON kb_versions(created_at);
"""


@dataclass
class KBVersion:
    """A single version of a KB document."""
    doc_id: str
    version: int
    content: str
    content_hash: str
    created_at: str = ""
    author: str = "system"
    change_note: str = ""


class KBVersionManager:
    """Manage document versions in KB.

    Usage::

        vm = KBVersionManager(":memory:")

        # Create a new version
        version = vm.create_version(
            doc_id="doc_001",
            content="Initial content",
            author="alice",
            change_note="Initial draft"
        )

        # Update to new version
        new_version = vm.create_version(
            doc_id="doc_001",
            content="Updated content",
            author="bob",
            change_note="Fixed typos"
        )

        # Get latest version
        latest = vm.get_version("doc_001")

        # Get specific version
        v1 = vm.get_version("doc_001", version=1)

        # List all versions
        versions = vm.list_versions("doc_001")

        # Diff between versions
        diff_text = vm.diff("doc_001", 1, 2)

        # Rollback to previous version
        restored = vm.rollback("doc_001", 1)
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            conn.executescript(_VERSION_DDL)
            conn.commit()
            self._conn = conn

    def _ensure_conn(self) -> sqlite3.Connection:
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            return self._conn

    def create_version(
        self,
        doc_id: str,
        content: str,
        author: str = "system",
        change_note: str = "",
    ) -> KBVersion:
        """Create a new version of a document."""
        with self._lock:
            conn = self._ensure_conn()

            # Get next version number under the same lock to avoid cross-thread races.
            row = conn.execute(
                "SELECT MAX(version) as max_ver FROM kb_versions WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
            next_version = (row["max_ver"] or 0) + 1

            # Compute content hash
            content_hash = _content_hash(content)
            created_at = _now_iso()

            conn.execute(
                """INSERT INTO kb_versions
                   (doc_id, version, content, content_hash, created_at, author, change_note)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, next_version, content, content_hash, created_at, author, change_note),
            )
            conn.commit()

            return KBVersion(
                doc_id=doc_id,
                version=next_version,
                content=content,
                content_hash=content_hash,
                created_at=created_at,
                author=author,
                change_note=change_note,
            )

    def get_version(self, doc_id: str, version: int | None = None) -> KBVersion | None:
        """Get a specific version, or latest if version is None."""
        with self._lock:
            conn = self._ensure_conn()

            if version is None:
                row = conn.execute(
                    """SELECT * FROM kb_versions
                       WHERE doc_id = ? ORDER BY version DESC LIMIT 1""",
                    (doc_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM kb_versions WHERE doc_id = ? AND version = ?",
                    (doc_id, version),
                ).fetchone()

            if row is None:
                return None

            return KBVersion(
                doc_id=row["doc_id"],
                version=row["version"],
                content=row["content"],
                content_hash=row["content_hash"],
                created_at=row["created_at"],
                author=row["author"],
                change_note=row["change_note"] or "",
            )

    def list_versions(self, doc_id: str) -> list[KBVersion]:
        """List all versions of a document, newest first."""
        with self._lock:
            conn = self._ensure_conn()
            rows = conn.execute(
                "SELECT * FROM kb_versions WHERE doc_id = ? ORDER BY version DESC",
                (doc_id,),
            ).fetchall()

            return [
                KBVersion(
                    doc_id=r["doc_id"],
                    version=r["version"],
                    content=r["content"],
                    content_hash=r["content_hash"],
                    created_at=r["created_at"],
                    author=r["author"],
                    change_note=r["change_note"] or "",
                )
                for r in rows
            ]

    def diff(self, doc_id: str, v1: int, v2: int) -> str:
        """Generate unified diff between two versions."""
        with self._lock:
            version1 = self.get_version(doc_id, v1)
            version2 = self.get_version(doc_id, v2)

            if version1 is None or version2 is None:
                return f"Version {v1} or {v2} not found for {doc_id}"

            lines1 = version1.content.splitlines(keepends=True)
            lines2 = version2.content.splitlines(keepends=True)

            import difflib
            diff = difflib.unified_diff(
                lines1, lines2,
                fromfile=f"{doc_id}:{v1}",
                tofile=f"{doc_id}:{v2}",
                lineterm="",
            )
            return "".join(diff)

    def rollback(self, doc_id: str, target_version: int) -> KBVersion | None:
        """Rollback to a specific version (creates new version with old content)."""
        with self._lock:
            target = self.get_version(doc_id, target_version)
            if target is None:
                return None

            # Create new version with rolled-back content
            return self.create_version(
                doc_id=doc_id,
                content=target.content,
                author="system",
                change_note=f"Rollback to version {target_version}",
            )

    def gc(self, keep_last: int = 10) -> int:
        """#54: Garbage collect old versions, keeping only the most recent per document.

        Args:
            keep_last: Number of most recent versions to keep per document.

        Returns:
            Number of versions deleted.
        """
        with self._lock:
            conn = self._ensure_conn()
            # Find documents with more than keep_last versions
            rows = conn.execute(
                """SELECT doc_id, COUNT(*) as cnt
                   FROM kb_versions GROUP BY doc_id HAVING cnt > ?""",
                (keep_last,),
            ).fetchall()

            deleted = 0
            for row in rows:
                doc_id = row["doc_id"]
                # Delete oldest versions beyond the retention limit
                conn.execute(
                    """DELETE FROM kb_versions
                       WHERE doc_id = ? AND version NOT IN (
                           SELECT version FROM kb_versions
                           WHERE doc_id = ? ORDER BY version DESC LIMIT ?
                       )""",
                    (doc_id, doc_id, keep_last),
                )
                deleted += conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
            if deleted:
                logger.info("Version GC: pruned %d old versions across %d documents", deleted, len(rows))
            return deleted

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
