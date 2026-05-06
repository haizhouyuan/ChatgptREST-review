from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

_CACHE: dict[str, Any] = {"ts": 0.0, "info": None}


def _repo_root() -> Path:
    # chatgptrest/core/build_info.py -> repo root is two levels up from package root.
    return Path(__file__).resolve().parents[2]


def _read_git_head(repo_root: Path) -> str | None:
    head = repo_root / ".git" / "HEAD"
    try:
        raw = head.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return None
    if not raw:
        return None
    if raw.startswith("ref:"):
        ref = raw.split(":", 1)[1].strip()
        if not ref:
            return None
        ref_path = repo_root / ".git" / ref
        try:
            sha = ref_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            return None
        return sha or None
    # Detached HEAD: file contains SHA.
    return raw


def _git_cmd(repo_root: Path, *args: str, timeout_seconds: float) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=float(timeout_seconds),
            check=False,
            text=True,
        )
    except Exception:
        return None
    if int(proc.returncode) != 0:
        return None
    return (proc.stdout or "").strip()


def _get_git_sha(repo_root: Path) -> str | None:
    env_sha = (os.environ.get("CHATGPTREST_GIT_SHA") or "").strip()
    if env_sha:
        return env_sha

    sha = _read_git_head(repo_root)
    if sha and len(sha) >= 7:
        return sha

    sha = _git_cmd(repo_root, "rev-parse", "HEAD", timeout_seconds=0.3)
    return sha


def _get_git_dirty(repo_root: Path) -> bool | None:
    raw = os.environ.get("CHATGPTREST_GIT_DIRTY")
    if raw is not None:
        v = raw.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False

    # Avoid `git status` scanning large ignored/untracked trees (e.g. artifacts/).
    out = _git_cmd(repo_root, "status", "--porcelain=v1", "--untracked-files=no", timeout_seconds=0.8)
    if out is None:
        return None
    return bool(out.strip())


def get_build_info(*, include_dirty: bool = True, cache_ttl_seconds: float = 10.0) -> dict[str, Any]:
    now = time.time()
    try:
        cached = _CACHE.get("info")
        cached_ts = float(_CACHE.get("ts") or 0.0)
    except Exception:
        cached = None
        cached_ts = 0.0

    if cached and (now - cached_ts) <= float(cache_ttl_seconds):
        if include_dirty or cached.get("git_dirty") is None:
            return dict(cached)

    repo_root = _repo_root()
    sha = _get_git_sha(repo_root)
    dirty = _get_git_dirty(repo_root) if include_dirty else None
    info = {
        "git_sha": (sha[:12] if sha else None),
        "git_dirty": dirty,
    }
    _CACHE["ts"] = float(now)
    _CACHE["info"] = dict(info)
    return dict(info)
