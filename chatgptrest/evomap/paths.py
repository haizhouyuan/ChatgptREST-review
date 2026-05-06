"""Shared path helpers for EvoMap runtime state."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_evomap_db_path(raw: str = "") -> str:
    """Resolve the canonical EvoMap SQLite path.

    Preference order:
      1. Explicit *raw* argument
      2. OPENMIND_EVOMAP_DB
      3. OPENMIND_EVO_DB (legacy)
      4. ~/.openmind/evomap/signals.db
    """
    candidate = (
        raw.strip()
        or os.environ.get("OPENMIND_EVOMAP_DB", "").strip()
        or os.environ.get("OPENMIND_EVO_DB", "").strip()
        or "~/.openmind/evomap/signals.db"
    )
    return os.path.expanduser(candidate)


def resolve_kb_registry_db_path(raw: str = "") -> str:
    """Resolve the KB registry path used by EvoMap scoring logic."""
    candidate = raw.strip() or os.environ.get("OPENMIND_KB_DB", "").strip() or "~/.openmind/kb_registry.db"
    return os.path.expanduser(candidate)


def ensure_sqlite_parent_dir(db_path: str) -> None:
    """Create the parent directory for a file-backed SQLite DB path."""
    if not db_path or db_path == ":memory:":
        return
    Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
