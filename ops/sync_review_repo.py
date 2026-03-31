#!/usr/bin/env python3
"""Sync selected code to the public review repo for Gemini/ChatGPT code import.

Branch-based workflow:
  1. Push code to a review-<timestamp> branch in the public review repo
  2. Mirror the same content to the repo's stable import branch for Gemini code import
  3. Use the review branch for branch-pinned external review and the repo root for Gemini import
  4. After review, --finalize deletes the reviewed branch and clears the stable import branch
  5. TTL cleanup can also delete stale review branches; optionally clear the import branch when no reviews remain

Respects Gemini's limits:
  - ≤5000 files
  - ≤100MB total

Usage:
  # First time: create the public repo
  python ops/sync_review_repo.py --create --repo-name ChatgptREST-review

  # Push code for review (creates timestamped branch)
  python ops/sync_review_repo.py --sync --push
  python ops/sync_review_repo.py --sync --push \\
      --pr-branch feat/issue-ledger \\
      --review-instructions "Review the Issue Ledger integration"

  # Custom branch name
  python ops/sync_review_repo.py --sync --push --branch-name my-review

  # Cleanup: delete remote review branches older than 24h (local kept)
  python ops/sync_review_repo.py --cleanup
  python ops/sync_review_repo.py --cleanup --max-age-hours 48

  # Finalize one review immediately after the answer is generated
  python ops/sync_review_repo.py --finalize --branch-name review-20260317-120000
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REVIEW_REPO = "ChatgptREST-review"
DEFAULT_REVIEW_REMOTE = "review"
DEFAULT_REPO_DIR = "/tmp/ChatgptREST-review"
DEFAULT_IMPORT_BRANCH = "main"
LOCAL_LOG_FILE = REPO_ROOT / "artifacts" / "review_branches.jsonl"
DEFAULT_CLEAR_PLACEHOLDER = "This public review mirror has been cleared after review finalization."

# Source directories to sync (relative to REPO_ROOT)
SOURCE_DIRS = [
    "chatgptrest",
    "chatgpt_web_mcp",
    "config",
    "openclaw_extensions",
    "ops",
    "scripts",
    "skills-src",
    "tests",
    ".agents",
    "docs",
]

# Files to ALWAYS include at root
ROOT_FILES = [
    "README.md",
    "pyproject.toml",
]

# Exclusions
EXCLUDE_DIRS = {
    "__pycache__", ".git", "node_modules", ".cache", ".venv",
    "venv", ".env", "secrets", "artifacts",
}

EXCLUDE_FILES = {
    ".env", ".env.production", ".env.local",
}


def public_source_repo_url() -> str:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            check=False,
        )
        raw = (result.stdout or "").strip()
        if raw.startswith("git@github.com:"):
            slug = raw.removeprefix("git@github.com:")
            if slug.endswith(".git"):
                slug = slug[:-4]
            return f"https://github.com/{slug}"
        if raw.startswith("https://github.com/"):
            return raw[:-4] if raw.endswith(".git") else raw
    except Exception:
        pass
    return str(REPO_ROOT)

EXCLUDE_EXTENSIONS = {
    ".pyc", ".pyo", ".sqlite3", ".db", ".log", ".heapsnapshot",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".webm",
}

SENSITIVE_MARKERS = [
    "PRIVATE KEY",
    "sk-",
    "AIza",
]
SENSITIVE_TEXT_ALLOWLIST = {
    "ops/sync_review_repo.py",
    "skills-src/chatgptrest-call/SKILL.md",
}


def is_excluded(path: Path, rel_path: str) -> bool:
    """Check if a file should be excluded from sync."""
    parts = set(Path(rel_path).parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.name in EXCLUDE_FILES:
        return True
    if path.suffix in EXCLUDE_EXTENSIONS:
        return True
    return False


def has_sensitive_content(path: Path, rel_path: str = "") -> bool:
    """Quick check for obviously sensitive content."""
    if rel_path in SENSITIVE_TEXT_ALLOWLIST:
        return False
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")[:5000]
        return any(marker in content for marker in SENSITIVE_MARKERS)
    except Exception:
        return True


def sync_source_files(
    dst_dir: Path,
    *,
    include_dirs: list[str] | None = None,
) -> dict[str, int]:
    """Sync source files to destination directory.

    Returns stats dict with files, skipped, bytes counts.
    """
    stats = {"files": 0, "skipped": 0, "bytes": 0}
    dirs_to_sync = include_dirs or SOURCE_DIRS

    for dir_rel in dirs_to_sync:
        src_dir = REPO_ROOT / dir_rel
        if not src_dir.is_dir():
            continue
        for root, dirs, filenames in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            root_path = Path(root)
            for name in sorted(filenames):
                src_path = root_path / name
                rel_path = str(src_path.relative_to(REPO_ROOT))

                if is_excluded(src_path, rel_path):
                    stats["skipped"] += 1
                    continue
                if has_sensitive_content(src_path, rel_path):
                    stats["skipped"] += 1
                    continue

                dst_path = dst_dir / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
                stats["files"] += 1
                stats["bytes"] += src_path.stat().st_size

    # Sync root-level files
    for fname in ROOT_FILES:
        fpath = REPO_ROOT / fname
        rel_path = str(fpath.relative_to(REPO_ROOT))
        if fpath.exists() and not has_sensitive_content(fpath, rel_path):
            dst_path = dst_dir / fname
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fpath, dst_path)
            stats["files"] += 1
            stats["bytes"] += fpath.stat().st_size

    return stats


def generate_review_context(
    dst_dir: Path,
    *,
    branch_name: str = "",
    pr_branch: str = "",
    review_instructions: str = "",
    source_commit: str = "",
) -> None:
    """Generate REVIEW_CONTEXT.md in the review repo."""
    parts = ["# Code Review Context\n"]
    source_repo_url = public_source_repo_url()

    if branch_name:
        parts.append(f"## Review Branch: `{branch_name}`\n")
        parts.append(f"Created: {datetime.datetime.now().isoformat()}\n")

    if source_commit:
        parts.append(f"\n## Source Commit\n\n- mirrored from source commit `{source_commit}`\n")
        parts.append(f"- source repo: `{source_repo_url}`\n")

    if pr_branch:
        parts.append(f"\n## PR Branch: `{pr_branch}`\n")
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10", pr_branch],
                capture_output=True, text=True, cwd=str(REPO_ROOT),
            )
            if result.stdout.strip():
                parts.append(f"### Recent Commits\n\n```\n{result.stdout.strip()}\n```\n")
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["git", "diff", "--stat", "master", pr_branch],
                capture_output=True, text=True, cwd=str(REPO_ROOT),
            )
            if result.stdout.strip():
                parts.append(f"### Changed Files\n\n```\n{result.stdout.strip()}\n```\n")
        except Exception:
            pass

    if review_instructions:
        parts.append(f"\n## Review Instructions\n\n{review_instructions}\n")

    parts.append("\n## Project Overview\n\n")
    parts.append("ChatgptREST is a REST API + worker system that automates ")
    parts.append("interactions with ChatGPT, Gemini, and Qwen web UIs via ")
    parts.append("browser automation (CDP). It includes:\n\n")
    parts.append("- **MCP Server** — exposes all functionality as MCP tools\n")
    parts.append("- **Advisor** — LangGraph-based intent→route→execute pipeline\n")
    parts.append("- **Worker** — job execution with retry/cooldown/repair\n")
    parts.append("- **EvoMap** — knowledge management with 43K atoms\n")
    parts.append("- **Issue Ledger** — automated issue tracking and resolution\n")

    (dst_dir / "REVIEW_CONTEXT.md").write_text("".join(parts), encoding="utf-8")
    if source_commit:
        (dst_dir / "REVIEW_SOURCE.json").write_text(
            json.dumps(
                {
                    "source_repo": source_repo_url,
                    "source_commit": source_commit,
                    "source_commit_url": f"{source_repo_url}/commit/{source_commit}",
                    "generated_at": datetime.datetime.now().isoformat(),
                    "review_branch": branch_name,
                    "pr_branch": pr_branch,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def create_public_repo(repo_name: str) -> bool:
    """Create a new public GitHub repo."""
    try:
        result = subprocess.run(
            ["gh", "repo", "create", repo_name,
             "--public", "--description",
             "Code review mirror for ChatgptREST (auto-synced, branches auto-deleted after review)"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"[OK] Created public repo: {repo_name}")
            return True
        else:
            print(f"[ERROR] Failed to create repo: {result.stderr}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[ERROR] gh CLI error: {e}", file=sys.stderr)
        return False


def _log_branch(branch_name: str, *, repo_name: str, action: str) -> None:
    """Append a record to the local review branch log (never deleted)."""
    LOCAL_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.datetime.now().isoformat(),
        "epoch": time.time(),
        "branch": branch_name,
        "repo": repo_name,
        "action": action,
    }
    with open(LOCAL_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _reset_worktree(dst: Path) -> None:
    """Delete all worktree content except .git."""
    for item in dst.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def _checkout_clean_orphan_branch(dst: Path, branch_name: str) -> None:
    """Create a clean orphan branch with an empty worktree."""
    subprocess.run(
        ["git", "checkout", "--orphan", branch_name],
        cwd=str(dst), capture_output=True, check=False,
    )
    subprocess.run(
        ["git", "rm", "-rf", "--quiet", "."],
        cwd=str(dst), capture_output=True, check=False,
    )
    _reset_worktree(dst)


def _write_cleared_repo_placeholder(
    dst: Path,
    *,
    repo_name: str,
    import_branch: str,
    finalized_branch: str = "",
) -> None:
    """Write a placeholder-only import branch so the public repo no longer exposes code."""
    ts = datetime.datetime.now().isoformat()
    lines = [
        f"# {repo_name}\n\n",
        f"{DEFAULT_CLEAR_PLACEHOLDER}\n\n",
        f"- import branch: `{import_branch}`\n",
        f"- cleared_at: `{ts}`\n",
    ]
    if finalized_branch:
        lines.append(f"- finalized_review_branch: `{finalized_branch}`\n")
    lines.append(
        "\nNo source code is retained on this branch. Re-run "
        "`python ops/sync_review_repo.py --sync --push` to publish a fresh review bundle.\n"
    )
    (dst / "README.md").write_text("".join(lines), encoding="utf-8")
    (dst / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.env\n*.sqlite3\n*.log\nnode_modules/\n",
        encoding="utf-8",
    )


def _read_review_source_branch(dst: Path) -> str:
    """Best-effort read of the currently mirrored review branch from REVIEW_SOURCE.json."""
    review_source = dst / "REVIEW_SOURCE.json"
    if not review_source.exists():
        return ""
    try:
        data = json.loads(review_source.read_text(encoding="utf-8"))
    except Exception:
        return ""
    branch = str(data.get("review_branch") or "").strip()
    return branch


def _latest_logged_review_branch(*, repo_name: str) -> str:
    """Best-effort resolve the latest pushed review branch from the local lifecycle log."""
    if not LOCAL_LOG_FILE.exists():
        return ""
    try:
        lines = LOCAL_LOG_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    for line in reversed(lines):
        try:
            record = json.loads(line)
        except Exception:
            continue
        if record.get("repo") != repo_name:
            continue
        if record.get("action") not in {"pushed", "synced_local"}:
            continue
        branch = str(record.get("branch") or "").strip()
        if branch.startswith("review-"):
            return branch
    return ""


def _list_remote_review_branches(dst: Path) -> list[str]:
    """Return remote review branch names without the remote prefix."""
    result = subprocess.run(
        ["git", "branch", "-r", "--list", f"{DEFAULT_REVIEW_REMOTE}/review-*"],
        capture_output=True, text=True, cwd=str(dst), check=False,
    )
    branches = [b.strip() for b in result.stdout.strip().splitlines() if b.strip()]
    return [b.replace(f"{DEFAULT_REVIEW_REMOTE}/", "") for b in branches]


def _resolve_review_branch(
    *,
    repo_name: str,
    dst: Path,
    branch_name: str,
    import_branch: str,
) -> str:
    """Resolve the active review branch when the caller did not pass one explicitly."""
    if branch_name:
        return branch_name

    source_branch = _read_review_source_branch(dst)
    remote_branches = set(_list_remote_review_branches(dst))
    if source_branch and source_branch in remote_branches:
        return source_branch

    try:
        current_branch = (
            subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, cwd=str(dst), check=False,
            ).stdout.strip()
        )
    except Exception:
        current_branch = ""
    if current_branch and current_branch != import_branch and current_branch in remote_branches:
        return current_branch

    logged_branch = _latest_logged_review_branch(repo_name=repo_name)
    if logged_branch and logged_branch in remote_branches:
        return logged_branch
    return ""


def clear_import_branch(
    *,
    repo_name: str,
    repo_dir: str,
    import_branch: str = DEFAULT_IMPORT_BRANCH,
    finalized_branch: str = "",
) -> dict:
    """Replace the stable import branch with a placeholder-only commit."""
    dst = Path(repo_dir)
    if not (dst / ".git").exists():
        print("[SKIP] No local clone found, cannot clear import branch")
        return {"cleared": False, "reason": "missing_local_clone"}

    _ensure_review_remote(dst, repo_name)
    temp_branch = "cleanup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    _checkout_clean_orphan_branch(dst, temp_branch)
    _write_cleared_repo_placeholder(
        dst,
        repo_name=repo_name,
        import_branch=import_branch,
        finalized_branch=finalized_branch,
    )
    subprocess.run(["git", "add", "-A"], cwd=str(dst), capture_output=True, check=False)
    subprocess.run(
        ["git", "commit", "-m", f"cleanup: clear {import_branch}"],
        cwd=str(dst), capture_output=True, check=False,
    )
    push_result = subprocess.run(
        ["git", "push", "-f", DEFAULT_REVIEW_REMOTE, f"HEAD:refs/heads/{import_branch}"],
        cwd=str(dst), capture_output=True, text=True, check=False,
    )
    if push_result.returncode == 0:
        _log_branch(import_branch, repo_name=repo_name, action="import_branch_cleared")
        print(f"[OK] Cleared import branch '{import_branch}'")
        return {"cleared": True, "import_branch": import_branch}
    print(f"[ERROR] Failed to clear import branch '{import_branch}': {push_result.stderr}", file=sys.stderr)
    return {"cleared": False, "import_branch": import_branch, "error": push_result.stderr}


def finalize_review_bundle(
    *,
    repo_name: str,
    repo_dir: str,
    branch_name: str = "",
    import_branch: str = DEFAULT_IMPORT_BRANCH,
    clear_import: bool = True,
) -> dict:
    """Delete a reviewed branch and optionally clear the stable import branch."""
    dst = Path(repo_dir)
    if not (dst / ".git").exists():
        print("[SKIP] No local clone found, nothing to finalize")
        return {"finalized": False, "reason": "missing_local_clone"}

    _ensure_review_remote(dst, repo_name)
    resolved_branch = _resolve_review_branch(
        repo_name=repo_name,
        dst=dst,
        branch_name=branch_name,
        import_branch=import_branch,
    )
    result = {
        "finalized": True,
        "branch": resolved_branch,
        "branch_deleted": False,
        "import_branch_cleared": False,
        "import_branch": import_branch,
    }
    if clear_import:
        clear_info = clear_import_branch(
            repo_name=repo_name,
            repo_dir=repo_dir,
            import_branch=import_branch,
            finalized_branch=resolved_branch,
        )
        result["import_branch_cleared"] = bool(clear_info.get("cleared"))

    if resolved_branch and resolved_branch != import_branch:
        del_result = subprocess.run(
            ["git", "push", DEFAULT_REVIEW_REMOTE, "--delete", resolved_branch],
            cwd=str(dst), capture_output=True, text=True, check=False,
        )
        if del_result.returncode == 0:
            print(f"[OK] Deleted review branch '{resolved_branch}'")
            _log_branch(resolved_branch, repo_name=repo_name, action="finalized_deleted")
            result["branch_deleted"] = True
        else:
            print(f"[ERROR] Failed to delete review branch '{resolved_branch}': {del_result.stderr}", file=sys.stderr)
            result["branch_delete_error"] = del_result.stderr

    _log_branch(resolved_branch or import_branch, repo_name=repo_name, action="finalized")
    return result


def purge_review_repo(
    *,
    repo_name: str,
    repo_dir: str,
    import_branch: str = DEFAULT_IMPORT_BRANCH,
) -> dict:
    """Delete all remote review branches and clear the stable import branch."""
    dst = Path(repo_dir)
    if not (dst / ".git").exists():
        print("[SKIP] No local clone found, nothing to purge")
        return {"purged": False, "reason": "missing_local_clone"}

    _ensure_review_remote(dst, repo_name)
    subprocess.run(
        ["git", "fetch", DEFAULT_REVIEW_REMOTE, "--prune"],
        cwd=str(dst), capture_output=True, check=False,
    )
    remote_branches = _list_remote_review_branches(dst)
    deleted = 0
    for branch in remote_branches:
        del_result = subprocess.run(
            ["git", "push", DEFAULT_REVIEW_REMOTE, "--delete", branch],
            cwd=str(dst), capture_output=True, text=True, check=False,
        )
        if del_result.returncode == 0:
            _log_branch(branch, repo_name=repo_name, action="purged_deleted")
            print(f"[OK] Deleted review branch '{branch}'")
            deleted += 1
        else:
            print(f"[ERROR] Failed to delete review branch '{branch}': {del_result.stderr}", file=sys.stderr)

    clear_info = clear_import_branch(
        repo_name=repo_name,
        repo_dir=repo_dir,
        import_branch=import_branch,
        finalized_branch="purge-all",
    )
    _log_branch(import_branch, repo_name=repo_name, action="purged")
    return {
        "purged": True,
        "deleted": deleted,
        "import_branch_cleared": bool(clear_info.get("cleared")),
        "import_branch": import_branch,
    }


def _ensure_review_remote(repo_dir: Path, repo_name: str) -> str:
    """Ensure the review remote is set up. Returns the remote URL."""
    # Get GitHub username
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get GitHub username: {result.stderr}")
    username = result.stdout.strip()
    token_result = subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True
    )
    if token_result.returncode == 0:
        token = token_result.stdout.strip()
        remote_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
    else:
        remote_url = f"https://github.com/{username}/{repo_name}.git"

    # Check if remote exists
    result = subprocess.run(
        ["git", "remote", "get-url", DEFAULT_REVIEW_REMOTE],
        capture_output=True, text=True, cwd=str(repo_dir),
    )
    if result.returncode != 0:
        # Add remote
        subprocess.run(
            ["git", "remote", "add", DEFAULT_REVIEW_REMOTE, remote_url],
            capture_output=True, text=True, cwd=str(repo_dir),
        )
    return remote_url


def _github_username() -> str:
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "haizhouyuan"


def _set_repo_default_branch(*, owner: str, repo_name: str, branch_name: str) -> None:
    subprocess.run(
        [
            "gh",
            "api",
            f"repos/{owner}/{repo_name}",
            "-X",
            "PATCH",
            "-f",
            f"default_branch={branch_name}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def sync_and_push(
    *,
    repo_name: str,
    repo_dir: str,
    branch_name: str,
    pr_branch: str = "",
    review_instructions: str = "",
    include_dirs: list[str] | None = None,
    push: bool = True,
    import_branch: str = DEFAULT_IMPORT_BRANCH,
) -> dict:
    """Sync code and push to a review branch."""
    dst = Path(repo_dir)

    # Init or reuse dir
    if not (dst / ".git").exists():
        dst.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=str(dst), capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=str(dst), capture_output=True,
        )

    # Create orphan branch (clean slate — each review is independent)
    _checkout_clean_orphan_branch(dst, branch_name)

    # Sync files
    stats = sync_source_files(dst, include_dirs=include_dirs)
    source_commit = ""
    try:
        source_commit = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                check=False,
            ).stdout.strip()
        )
    except Exception:
        source_commit = ""

    generate_review_context(
        dst,
        branch_name=branch_name,
        pr_branch=pr_branch,
        review_instructions=review_instructions,
        source_commit=source_commit,
    )

    # Write .gitignore
    (dst / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.env\n*.sqlite3\n*.log\nnode_modules/\n",
        encoding="utf-8",
    )

    size_mb = stats["bytes"] / (1024 * 1024)
    print(f"[OK] Synced {stats['files']} files ({size_mb:.1f}MB), skipped {stats['skipped']}")

    if stats["files"] > 5000:
        print(f"[WARNING] {stats['files']} files exceeds Gemini's 5000-file limit!")
    if size_mb > 100:
        print(f"[WARNING] {size_mb:.1f}MB exceeds Gemini's 100MB limit!")

    result_info = {
        "branch": branch_name,
        "files": stats["files"],
        "size_mb": round(size_mb, 1),
    }

    if push:
        _ensure_review_remote(dst, repo_name)
        subprocess.run(["git", "add", "-A"], cwd=str(dst), capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"review: {branch_name}"],
            cwd=str(dst), capture_output=True,
        )
        push_result = subprocess.run(
            ["git", "push", "-f", DEFAULT_REVIEW_REMOTE, branch_name],
            cwd=str(dst), capture_output=True, text=True,
        )
        if push_result.returncode == 0:
            import_push_result = subprocess.run(
                ["git", "push", "-f", DEFAULT_REVIEW_REMOTE, f"HEAD:refs/heads/{import_branch}"],
                cwd=str(dst), capture_output=True, text=True,
            )
            print(f"[OK] Pushed branch '{branch_name}' to {repo_name}")
            _log_branch(branch_name, repo_name=repo_name, action="pushed")
            result_info["pushed"] = True
            result_info["import_branch"] = import_branch
            result_info["import_branch_pushed"] = import_push_result.returncode == 0

            # Derive repo URL
            username = _github_username()
            if import_push_result.returncode == 0:
                _set_repo_default_branch(owner=username, repo_name=repo_name, branch_name=import_branch)
            repo_url = f"https://github.com/{username}/{repo_name}"
            branch_url = f"{repo_url}/tree/{branch_name}"
            import_branch_url = f"{repo_url}/tree/{import_branch}"
            print(f"\n  Repo URL:   {repo_url}")
            print(f"  Branch URL: {branch_url}")
            print(f"  Import URL: {import_branch_url}")
            print(f"\n  For ChatGPT Pro connector, use: {branch_url}")
            print(f"  For Gemini code import, use:    {repo_url}")
            result_info["repo_url"] = repo_url
            result_info["branch_url"] = branch_url
            result_info["import_branch_url"] = import_branch_url
        else:
            print(f"[ERROR] Push failed: {push_result.stderr}", file=sys.stderr)
            result_info["pushed"] = False
    else:
        _log_branch(branch_name, repo_name=repo_name, action="synced_local")
        result_info["pushed"] = False

    return result_info


def cleanup_remote_branches(
    *,
    repo_name: str,
    repo_dir: str,
    max_age_hours: float = 24,
    import_branch: str = DEFAULT_IMPORT_BRANCH,
    clear_import_when_empty: bool = False,
) -> dict:
    """Delete remote review branches older than max_age_hours.

    Local branches and log records are PRESERVED.
    """
    dst = Path(repo_dir)
    if not (dst / ".git").exists():
        print("[SKIP] No local clone found, nothing to clean")
        return {"deleted": 0, "import_branch_cleared": False}

    _ensure_review_remote(dst, repo_name)

    # Fetch remote branches
    subprocess.run(
        ["git", "fetch", DEFAULT_REVIEW_REMOTE, "--prune"],
        cwd=str(dst), capture_output=True,
    )

    # List remote review branches
    result = subprocess.run(
        ["git", "branch", "-r", "--list", f"{DEFAULT_REVIEW_REMOTE}/review-*"],
        capture_output=True, text=True, cwd=str(dst),
    )
    branches = [b.strip() for b in result.stdout.strip().splitlines() if b.strip()]

    if not branches:
        print("[OK] No remote review branches to clean")
        return {"deleted": 0, "import_branch_cleared": False}

    cutoff = time.time() - (max_age_hours * 3600)
    deleted = 0

    for remote_branch in branches:
        # Extract timestamp from branch name: review-YYYYMMDD-HHMMSS or review-<name>
        local_name = remote_branch.replace(f"{DEFAULT_REVIEW_REMOTE}/", "")

        # Get the commit date for this branch
        date_result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", remote_branch],
            capture_output=True, text=True, cwd=str(dst),
        )
        try:
            commit_epoch = float(date_result.stdout.strip())
        except (ValueError, AttributeError):
            continue

        if commit_epoch < cutoff:
            # Delete REMOTE branch only
            del_result = subprocess.run(
                ["git", "push", DEFAULT_REVIEW_REMOTE, "--delete", local_name],
                capture_output=True, text=True, cwd=str(dst),
            )
            if del_result.returncode == 0:
                age_hours = (time.time() - commit_epoch) / 3600
                print(f"[DELETED] Remote branch '{local_name}' (age: {age_hours:.1f}h)")
                _log_branch(local_name, repo_name=repo_name, action="remote_deleted")
                deleted += 1
            else:
                print(f"[ERROR] Failed to delete '{local_name}': {del_result.stderr}")

    import_cleared = False
    if clear_import_when_empty:
        remaining_result = subprocess.run(
            ["git", "branch", "-r", "--list", f"{DEFAULT_REVIEW_REMOTE}/review-*"],
            capture_output=True, text=True, cwd=str(dst), check=False,
        )
        remaining = [b.strip() for b in remaining_result.stdout.strip().splitlines() if b.strip()]
        if not remaining:
            clear_info = clear_import_branch(
                repo_name=repo_name,
                repo_dir=repo_dir,
                import_branch=import_branch,
            )
            import_cleared = bool(clear_info.get("cleared"))

    print(f"[OK] Deleted {deleted} remote branches, local branches preserved")
    return {"deleted": deleted, "import_branch_cleared": import_cleared}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync code to public review repo (branch-based workflow)"
    )
    parser.add_argument("--create", action="store_true", help="Create the public repo first")
    parser.add_argument("--sync", action="store_true", help="Sync code and create review branch")
    parser.add_argument("--cleanup", action="store_true", help="Delete old remote review branches")
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="Delete a reviewed branch and clear the stable import branch placeholder",
    )
    parser.add_argument(
        "--purge-all",
        action="store_true",
        help="Delete all remote review branches and clear the stable import branch",
    )
    parser.add_argument("--repo-name", default=DEFAULT_REVIEW_REPO, help="GitHub repo name")
    parser.add_argument("--repo-dir", default=DEFAULT_REPO_DIR, help="Local clone dir")
    parser.add_argument(
        "--branch-name", default="",
        help="Custom branch name (default: review-YYYYMMDD-HHMMSS)",
    )
    parser.add_argument("--pr-branch", default="", help="PR branch for review context")
    parser.add_argument("--review-instructions", default="", help="Review instructions text")
    parser.add_argument("--push", action="store_true", help="Push to remote after sync")
    parser.add_argument(
        "--import-branch",
        default=DEFAULT_IMPORT_BRANCH,
        help=f"Stable branch mirrored for Gemini code import (default: {DEFAULT_IMPORT_BRANCH})",
    )
    parser.add_argument(
        "--include-dirs", nargs="*", default=None,
        help=f"Directories to include (default: {' '.join(SOURCE_DIRS)})",
    )
    parser.add_argument(
        "--max-age-hours", type=float, default=24,
        help="Max age in hours for --cleanup (default: 24)",
    )
    parser.add_argument(
        "--clear-import-when-empty",
        action="store_true",
        help="With --cleanup, clear the stable import branch after the last review branch is deleted",
    )

    args = parser.parse_args()

    if args.create:
        create_public_repo(args.repo_name)

    if args.sync:
        branch_name = args.branch_name or (
            "review-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        )
        sync_and_push(
            repo_name=args.repo_name,
            repo_dir=args.repo_dir,
            branch_name=branch_name,
            pr_branch=args.pr_branch,
            review_instructions=args.review_instructions,
            include_dirs=args.include_dirs,
            push=args.push,
            import_branch=args.import_branch,
        )

    if args.cleanup:
        cleanup_remote_branches(
            repo_name=args.repo_name,
            repo_dir=args.repo_dir,
            max_age_hours=args.max_age_hours,
            import_branch=args.import_branch,
            clear_import_when_empty=args.clear_import_when_empty,
        )

    if args.finalize:
        finalize_review_bundle(
            repo_name=args.repo_name,
            repo_dir=args.repo_dir,
            branch_name=args.branch_name,
            import_branch=args.import_branch,
            clear_import=True,
        )

    if args.purge_all:
        purge_review_repo(
            repo_name=args.repo_name,
            repo_dir=args.repo_dir,
            import_branch=args.import_branch,
        )

    if not (args.create or args.sync or args.cleanup or args.finalize or args.purge_all):
        parser.print_help()


if __name__ == "__main__":
    main()
