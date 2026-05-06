from __future__ import annotations

import os
from pathlib import Path


def repo_root(anchor: Path | None = None) -> Path:
    base = anchor if anchor is not None else Path(__file__)
    return Path(base).resolve().parents[2]


def _dedupe_paths(paths: list[Path]) -> tuple[Path, ...]:
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return tuple(deduped)


def _env_path(name: str) -> Path | None:
    raw = str(os.environ.get(name) or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def discover_project_root(project_name: str, *, start: Path | None = None) -> Path | None:
    root = repo_root(start)
    for ancestor in (root, *root.parents):
        direct = ancestor / project_name
        if direct.exists():
            return direct
        projects_child = ancestor / "projects" / project_name
        if projects_child.exists():
            return projects_child
    return None


def resolve_finagent_root(*, start: Path | None = None) -> Path:
    env_path = _env_path("CHATGPTREST_FINAGENT_ROOT")
    if env_path is not None:
        return env_path
    discovered = discover_project_root("finagent", start=start)
    if discovered is not None:
        return discovered
    root = repo_root(start)
    return root.parent / "finagent"


def resolve_finbot_artifact_roots(*, start: Path | None = None) -> tuple[Path, ...]:
    root = repo_root(start)
    paths: list[Path] = []
    env_path = _env_path("CHATGPTREST_FINBOT_ARTIFACT_ROOT")
    if env_path is not None:
        paths.append(env_path)
    paths.append(root / "artifacts" / "finbot")
    return _dedupe_paths(paths)


def credentials_env_candidates(*, start: Path | None = None) -> tuple[Path, ...]:
    root = repo_root(start)
    paths: list[Path] = []
    env_path = _env_path("CHATGPTREST_CREDENTIALS_ENV")
    if env_path is not None:
        paths.append(env_path)
    paths.append(Path("~/.config/chatgptrest/chatgptrest.env").expanduser())
    for ancestor in (root, *root.parents):
        paths.append(ancestor / "MAIN" / "secrets" / "credentials.env")
        paths.append(ancestor / "maint" / "MAIN" / "secrets" / "credentials.env")
    return _dedupe_paths(paths)
