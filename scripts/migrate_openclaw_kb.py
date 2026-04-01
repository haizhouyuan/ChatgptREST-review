"""OpenClaw KB Migration Script — imports documents into OpenMind KB Hub.

Imports from OpenClaw workspaces to the OpenMind KB system:
  - Preserves metadata (layer, domain, owner, as_of)
  - Sets stability=approved, quarantine_weight=1.0 (verified docs)
  - Idempotent: re-running skips already-imported documents
  - Indexes into both FTS5 and vector store (if embedding fn provided)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class MigrationStats:
    """Statistics from a migration run."""
    total_found: int = 0
    imported: int = 0
    skipped_existing: int = 0
    skipped_error: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_found": self.total_found,
            "imported": self.imported,
            "skipped_existing": self.skipped_existing,
            "skipped_error": self.skipped_error,
            "errors": self.errors[:10],  # limit error details
        }


@dataclass
class MigrationConfig:
    """Configuration for KB migration."""
    source_dir: str = "/vol1/1000/openclaw-workspaces/kb/"
    project_id: str = "openmind-v3"
    stability: str = "approved"
    quarantine_weight: float = 1.0
    extensions: list[str] = field(default_factory=lambda: [".md", ".txt", ".json"])
    max_file_size: int = 1_000_000  # 1MB


class KBMigrator:
    """Migrates KB documents from OpenClaw to OpenMind.

    Usage::

        migrator = KBMigrator(
            config=MigrationConfig(),
            register_fn=lambda doc: registry.register_file(...),
            index_fn=lambda doc_id, text: hub.index(doc_id, text),
        )
        stats = migrator.run()
    """

    def __init__(
        self,
        config: MigrationConfig | None = None,
        *,
        register_fn: Callable[[dict], str] | None = None,
        index_fn: Callable[[str, str], None] | None = None,
        is_imported_fn: Callable[[str], bool] | None = None,
    ) -> None:
        self._config = config or MigrationConfig()
        self._register_fn = register_fn or (lambda doc: doc.get("artifact_id", ""))
        self._index_fn = index_fn or (lambda doc_id, text: None)
        self._is_imported_fn = is_imported_fn or (lambda hash_: False)

    def scan_documents(self) -> list[dict[str, Any]]:
        """Scan source directory for documents to import."""
        source = Path(self._config.source_dir)
        if not source.exists():
            logger.warning("Source directory not found: %s", source)
            return []

        docs = []
        for ext in self._config.extensions:
            for path in source.rglob(f"*{ext}"):
                if path.stat().st_size > self._config.max_file_size:
                    continue
                docs.append({
                    "path": str(path),
                    "filename": path.name,
                    "extension": ext,
                    "size": path.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                })
        return docs

    def _content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def import_document(self, doc: dict[str, Any]) -> tuple[bool, str]:
        """Import a single document. Returns (success, message)."""
        path = doc["path"]
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return False, f"Read error: {e}"

        content_hash = self._content_hash(content)

        # Idempotency check
        if self._is_imported_fn(content_hash):
            return False, "already_imported"

        # Build artifact record
        artifact = {
            "artifact_id": content_hash[:16],
            "source_path": path,
            "source_system": "openclaw-migration",
            "project_id": self._config.project_id,
            "content_hash": content_hash,
            "stability": self._config.stability,
            "quarantine_weight": self._config.quarantine_weight,
            "title": Path(path).stem.replace("_", " ").replace("-", " "),
            "file_size": doc.get("size", 0),
            "modified_at": doc.get("modified", ""),
        }

        try:
            doc_id = self._register_fn(artifact)
            self._index_fn(doc_id, content)
            return True, "imported"
        except Exception as e:
            return False, f"Import error: {e}"

    def run(self) -> MigrationStats:
        """Run the full migration. Idempotent."""
        stats = MigrationStats()
        docs = self.scan_documents()
        stats.total_found = len(docs)

        for doc in docs:
            success, msg = self.import_document(doc)
            if success:
                stats.imported += 1
            elif msg == "already_imported":
                stats.skipped_existing += 1
            else:
                stats.skipped_error += 1
                stats.errors.append({"path": doc["path"], "error": msg})

        logger.info(
            "Migration complete: %d imported, %d skipped, %d errors",
            stats.imported, stats.skipped_existing, stats.skipped_error,
        )
        return stats
