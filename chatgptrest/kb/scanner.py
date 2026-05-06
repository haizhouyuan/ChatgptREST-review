"""
KB File Scanner – Discovers artifacts from configured directories.

Two modes:
- Backfill: scan known roots and register every file as an artifact candidate
- Watch: monitor roots for create/update events (via filesystem polling)

Design (from KB DR):
- Idempotent: same file scanned twice → same result
- Debounced: skip files modified within last N seconds (write-in-progress)
- Configurable: include/exclude patterns, max depth
- Event-emitting: produces trace events for the event log
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .registry import ArtifactRegistry, Artifact, _detect_content_type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scanner configuration
# ---------------------------------------------------------------------------

@dataclass
class ScanRoot:
    """A directory root to scan for KB artifacts."""
    path: str
    source_system: str = "filesystem"
    project_id: str = ""
    para_bucket: str = "unclassified"
    max_depth: int = 10
    include_extensions: list[str] = field(default_factory=lambda: [
        ".md", ".json", ".py", ".ts", ".tsx", ".yaml", ".yml",
        ".csv", ".pdf", ".docx", ".xlsx", ".pptx", ".log", ".txt",
        ".sh", ".sql", ".html", ".css", ".js",
    ])
    exclude_patterns: list[str] = field(default_factory=lambda: [
        "__pycache__", "node_modules", ".git", ".venv", "venv",
        ".next", "dist", "build", ".cache", ".DS_Store",
    ])


# Default scan roots for this project
DEFAULT_SCAN_ROOTS = [
    ScanRoot(
        path="/vol1/1000/projects/ChatgptREST",
        source_system="chatgptrest",
        project_id="chatgptrest",
        para_bucket="project",
    ),
    ScanRoot(
        path="/vol1/1000/projects/openclaw",
        source_system="openclaw",
        project_id="openclaw",
        para_bucket="project",
    ),
    ScanRoot(
        path="/vol1/1000/projects/planning",
        source_system="planning",
        project_id="planning",
        para_bucket="area",
    ),
    ScanRoot(
        path="/vol1/1000/projects/ChatgptREST/artifacts",
        source_system="deep-research",
        project_id="chatgptrest",
        para_bucket="resource",
    ),
]


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class FileScanner:
    """
    Scans configured directories and registers artifacts.

    Usage::

        reg = ArtifactRegistry("/path/to/kb.db")
        scanner = FileScanner(reg)
        stats = scanner.backfill_scan()
        print(f"Found {stats['total']} files, {stats['new']} new")
    """

    def __init__(
        self,
        registry: ArtifactRegistry,
        roots: list[ScanRoot] | None = None,
        debounce_seconds: float = 2.0,
    ):
        self.registry = registry
        self.roots = roots or DEFAULT_SCAN_ROOTS
        self.debounce_seconds = debounce_seconds

    def _should_include(self, path: Path, root: ScanRoot) -> bool:
        """Check if a file should be included in the scan."""
        # Check exclude patterns
        parts = path.parts
        for pattern in root.exclude_patterns:
            if pattern in parts:
                return False

        # Check extension
        if root.include_extensions:
            if path.suffix.lower() not in root.include_extensions:
                return False

        # Debounce: skip files modified very recently (still being written)
        try:
            mtime = path.stat().st_mtime
            if time.time() - mtime < self.debounce_seconds:
                return False
        except OSError:
            return False

        return True

    def _iter_files(self, root: ScanRoot) -> list[Path]:
        """Iterate files under a scan root, respecting max_depth."""
        root_path = Path(root.path)
        if not root_path.exists():
            logger.warning(f"Scan root does not exist: {root.path}")
            return []

        files = []
        for dirpath, dirnames, filenames in os.walk(root_path):
            current = Path(dirpath)
            # Check depth
            depth = len(current.relative_to(root_path).parts)
            if depth > root.max_depth:
                dirnames.clear()
                continue

            # Filter out excluded directories
            dirnames[:] = [
                d for d in dirnames
                if d not in root.exclude_patterns
            ]

            for fname in filenames:
                fpath = current / fname
                if self._should_include(fpath, root):
                    files.append(fpath)

        return files

    def backfill_scan(
        self,
        roots: list[ScanRoot] | None = None,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, int]:
        """
        Full backfill scan of all configured roots.

        Returns stats: total, new, updated, skipped, errors
        """
        scan_roots = roots or self.roots
        stats = {"total": 0, "new": 0, "updated": 0, "skipped": 0, "errors": 0}

        for root in scan_roots:
            files = self._iter_files(root)
            logger.info(f"Scanning {root.path}: {len(files)} files found")

            for i, fpath in enumerate(files):
                stats["total"] += 1
                try:
                    existing = self.registry.get_by_path(str(fpath))
                    art = self.registry.register_file(
                        fpath,
                        source_system=root.source_system,
                        project_id=root.project_id,
                        para_bucket=root.para_bucket,
                    )

                    # Update quality score
                    self.registry.update_quality(art.artifact_id)

                    if existing and existing.content_hash == art.content_hash:
                        stats["skipped"] += 1
                    elif existing:
                        stats["updated"] += 1
                    else:
                        stats["new"] += 1

                    if progress_callback and (i + 1) % 100 == 0:
                        progress_callback(i + 1, len(files))

                except Exception as e:
                    stats["errors"] += 1
                    logger.warning(f"Error scanning {fpath}: {e}")

        return stats

    def scan_single_root(self, root: ScanRoot) -> dict[str, int]:
        """Scan a single root directory."""
        return self.backfill_scan([root])

    def detect_changes(
        self,
        root: ScanRoot,
        since_timestamp: float,
    ) -> list[Path]:
        """
        Find files modified since the given timestamp.
        Useful for incremental updates.
        """
        changed = []
        for fpath in self._iter_files(root):
            try:
                if fpath.stat().st_mtime > since_timestamp:
                    changed.append(fpath)
            except OSError:
                continue
        return changed
