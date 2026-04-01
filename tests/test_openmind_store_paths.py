from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from chatgptrest.core.openmind_paths import (
    resolve_consult_kb_db_path,
    resolve_evomap_knowledge_read_db_path,
    resolve_evomap_knowledge_runtime_db_path,
    resolve_openmind_event_bus_db_path,
    resolve_openmind_kb_search_db_path,
    resolve_openmind_kb_vector_db_path,
)


def _touch_sqlite(path: Path, content: bytes = b"sqlite-test") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_path_helpers_prefer_canonical_envs(monkeypatch) -> None:
    monkeypatch.setenv("OPENMIND_KB_PATH", "/tmp/legacy-kb.db")
    monkeypatch.setenv("OPENMIND_KB_SEARCH_DB", "/tmp/canonical-kb.db")
    monkeypatch.setenv("OPENMIND_KB_VEC_DB", "/tmp/canonical-kb-vec.db")
    monkeypatch.setenv("OPENMIND_EVENTS_DB", "/tmp/legacy-events.db")
    monkeypatch.setenv("OPENMIND_EVENTBUS_DB", "/tmp/canonical-events.db")
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", "/tmp/canonical-knowledge.db")

    assert resolve_openmind_kb_search_db_path() == "/tmp/canonical-kb.db"
    assert resolve_openmind_kb_vector_db_path() == "/tmp/canonical-kb-vec.db"
    assert resolve_openmind_event_bus_db_path() == "/tmp/canonical-events.db"
    assert resolve_evomap_knowledge_runtime_db_path() == "/tmp/canonical-knowledge.db"


def test_runtime_path_helper_ignores_legacy_home_env(monkeypatch) -> None:
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", "~/.openmind/evomap_knowledge.db")

    resolved = resolve_evomap_knowledge_runtime_db_path()

    assert resolved.endswith("/data/evomap_knowledge.db")
    assert ".openmind/evomap_knowledge.db" not in resolved


def test_consult_kb_path_prefers_runtime_openmind_db_when_readable(tmp_path: Path, monkeypatch) -> None:
    kb_search = tmp_path / "openmind" / "kb_search.db"
    _touch_sqlite(kb_search)
    monkeypatch.setenv("OPENMIND_KB_SEARCH_DB", str(kb_search))
    monkeypatch.delenv("CHATGPTREST_KB_DB_PATH", raising=False)

    resolved = resolve_consult_kb_db_path(repo_root=tmp_path / "repo")

    assert resolved == kb_search


def test_evomap_read_path_ignores_zero_byte_home_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home_fallback = tmp_path / "home" / ".openmind" / "evomap_knowledge.db"
    home_fallback.parent.mkdir(parents=True, exist_ok=True)
    home_fallback.write_bytes(b"")

    repo_root = tmp_path / "repo"
    repo_db = repo_root / "data" / "evomap_knowledge.db"
    _touch_sqlite(repo_db)
    monkeypatch.delenv("EVOMAP_KNOWLEDGE_DB", raising=False)

    resolved = resolve_evomap_knowledge_read_db_path(repo_root=repo_root)

    assert resolved == str(repo_db)


def test_evomap_read_path_returns_none_when_only_zero_byte_candidates_exist(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home_fallback = tmp_path / "home" / ".openmind" / "evomap_knowledge.db"
    home_fallback.parent.mkdir(parents=True, exist_ok=True)
    home_fallback.write_bytes(b"")
    monkeypatch.delenv("EVOMAP_KNOWLEDGE_DB", raising=False)

    resolved = resolve_evomap_knowledge_read_db_path(repo_root=tmp_path / "repo")

    assert resolved is None


def test_evomap_read_path_ignores_readable_home_archive(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home_archive = tmp_path / "home" / ".openmind" / "evomap_knowledge.db"
    _touch_sqlite(home_archive)
    monkeypatch.delenv("EVOMAP_KNOWLEDGE_DB", raising=False)

    resolved = resolve_evomap_knowledge_read_db_path(repo_root=tmp_path / "repo")

    assert resolved is None


def test_evomap_read_path_ignores_legacy_home_env(tmp_path: Path, monkeypatch) -> None:
    repo_db = tmp_path / "repo" / "data" / "evomap_knowledge.db"
    _touch_sqlite(repo_db)
    monkeypatch.setenv("EVOMAP_KNOWLEDGE_DB", "~/.openmind/evomap_knowledge.db")

    resolved = resolve_evomap_knowledge_read_db_path(repo_root=tmp_path / "repo")

    assert resolved == str(repo_db)


def test_ops_evomap_defaults_follow_canonical_runtime_db() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_atom_refinement = _load_module(repo_root / "ops" / "run_atom_refinement.py", "test_run_atom_refinement")
    p4_batch_fix = _load_module(
        repo_root / "chatgptrest" / "evomap" / "knowledge" / "p4_batch_fix.py",
        "test_p4_batch_fix",
    )

    expected = resolve_evomap_knowledge_runtime_db_path()

    assert run_atom_refinement._DEFAULT_DB == expected
    assert p4_batch_fix._DEFAULT_DB == expected
