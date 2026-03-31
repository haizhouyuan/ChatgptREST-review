from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _expand(raw: str) -> str:
    return os.path.expanduser(raw.strip())


_LEGACY_EVOMAP_KNOWLEDGE_DB = Path(_expand("~/.openmind/evomap_knowledge.db"))
_CANONICAL_EVOMAP_KNOWLEDGE_DB = REPO_ROOT / "data" / "evomap_knowledge.db"


def _is_readable_sqlite(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _is_legacy_evomap_knowledge_db(path: Path) -> bool:
    try:
        return path.expanduser().resolve() == _LEGACY_EVOMAP_KNOWLEDGE_DB.expanduser().resolve()
    except FileNotFoundError:
        return str(path.expanduser()) == str(_LEGACY_EVOMAP_KNOWLEDGE_DB.expanduser())


def resolve_openmind_kb_search_db_path(raw: str = "") -> str:
    candidate = (
        raw.strip()
        or os.environ.get("OPENMIND_KB_SEARCH_DB", "").strip()
        or os.environ.get("OPENMIND_KB_PATH", "").strip()
        or "~/.openmind/kb_search.db"
    )
    return _expand(candidate)


def resolve_openmind_kb_vector_db_path(raw: str = "") -> str:
    candidate = raw.strip() or os.environ.get("OPENMIND_KB_VEC_DB", "").strip() or "~/.openmind/kb_vectors.db"
    return _expand(candidate)


def resolve_openmind_event_bus_db_path(raw: str = "") -> str:
    candidate = (
        raw.strip()
        or os.environ.get("OPENMIND_EVENTBUS_DB", "").strip()
        or os.environ.get("OPENMIND_EVENTS_DB", "").strip()
        or "~/.openmind/events.db"
    )
    return _expand(candidate)


def resolve_evomap_knowledge_runtime_db_path(raw: str = "") -> str:
    if raw.strip():
        return _expand(raw)

    env_candidate = os.environ.get("EVOMAP_KNOWLEDGE_DB", "").strip()
    if env_candidate:
        env_path = Path(_expand(env_candidate))
        if not _is_legacy_evomap_knowledge_db(env_path):
            return str(env_path)

    return str(_CANONICAL_EVOMAP_KNOWLEDGE_DB)


def resolve_consult_kb_db_path(db_path: Path | None = None, *, repo_root: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    kb_path_raw = os.environ.get("CHATGPTREST_KB_DB_PATH", "").strip()
    if kb_path_raw:
        candidates.append(Path(_expand(kb_path_raw)))
    candidates.append(Path(resolve_openmind_kb_search_db_path()))
    if db_path and db_path.parent.exists():
        candidates.append(db_path.parent / "kb.sqlite3")
    root = repo_root or REPO_ROOT
    candidates.extend([root / "state" / "kb.sqlite3", root / "kb.sqlite3"])
    seen: set[str] = set()
    for candidate in candidates:
        resolved = str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        if _is_readable_sqlite(candidate):
            return candidate
    return None


def resolve_evomap_knowledge_read_db_path(*, repo_root: Path | None = None, raw: str = "") -> str | None:
    candidates: list[Path] = []
    if raw.strip():
        candidates.append(Path(_expand(raw)))
    env_path = os.environ.get("EVOMAP_KNOWLEDGE_DB", "").strip()
    if env_path:
        env_candidate = Path(_expand(env_path))
        if not _is_legacy_evomap_knowledge_db(env_candidate):
            candidates.append(env_candidate)
    root = repo_root or REPO_ROOT
    candidates.append(root / "data" / "evomap_knowledge.db")
    seen: set[str] = set()
    for candidate in candidates:
        resolved = str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        if _is_readable_sqlite(candidate):
            return resolved
    return None
