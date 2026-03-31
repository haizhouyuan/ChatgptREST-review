from __future__ import annotations

from pathlib import Path

from chatgptrest.core.path_resolver import credentials_env_candidates, resolve_finagent_root, resolve_finbot_artifact_roots


def test_resolve_finagent_root_prefers_env(monkeypatch):
    monkeypatch.setenv("CHATGPTREST_FINAGENT_ROOT", "/tmp/custom-finagent")
    assert resolve_finagent_root(start=Path("/tmp/worktrees/ChatgptREST/chatgptrest/core/path_resolver.py")) == Path("/tmp/custom-finagent")


def test_resolve_finagent_root_discovers_projects_sibling(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CHATGPTREST_FINAGENT_ROOT", raising=False)
    repo_root = tmp_path / "worktrees" / "ChatgptREST"
    anchor = repo_root / "chatgptrest" / "core" / "path_resolver.py"
    anchor.parent.mkdir(parents=True)
    finagent_root = tmp_path / "projects" / "finagent"
    finagent_root.mkdir(parents=True)

    assert resolve_finagent_root(start=anchor) == finagent_root


def test_credentials_env_candidates_include_env_and_discovered_maint(tmp_path: Path, monkeypatch):
    env_path = tmp_path / "secrets" / "custom.env"
    monkeypatch.setenv("CHATGPTREST_CREDENTIALS_ENV", str(env_path))
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo_root = tmp_path / "projects" / "ChatgptREST"
    anchor = repo_root / "chatgptrest" / "observability" / "__init__.py"
    anchor.parent.mkdir(parents=True)
    maint_path = tmp_path / "maint" / "MAIN" / "secrets" / "credentials.env"
    maint_path.parent.mkdir(parents=True)

    candidates = credentials_env_candidates(start=anchor)

    assert candidates[0] == env_path
    assert home / ".config" / "chatgptrest" / "chatgptrest.env" in candidates
    assert maint_path in candidates


def test_resolve_finbot_artifact_roots_prefers_env_then_repo(monkeypatch, tmp_path: Path):
    env_root = tmp_path / "external-finbot"
    monkeypatch.setenv("CHATGPTREST_FINBOT_ARTIFACT_ROOT", str(env_root))
    repo_root = tmp_path / "projects" / "ChatgptREST"
    anchor = repo_root / "chatgptrest" / "dashboard" / "service.py"
    anchor.parent.mkdir(parents=True)

    roots = resolve_finbot_artifact_roots(start=anchor)

    assert roots[0] == env_root
    assert repo_root / "artifacts" / "finbot" in roots
