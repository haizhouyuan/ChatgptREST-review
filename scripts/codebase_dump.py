#!/usr/bin/env python3
"""codebase_dump.py — Generate a Markdown snapshot of a code repository for LLM consumption.

Usage:
    python3 scripts/codebase_dump.py /path/to/repo                    # default: stdout
    python3 scripts/codebase_dump.py /path/to/repo -o snapshot.md     # write to file
    python3 scripts/codebase_dump.py /path/to/repo --max-kb 500       # cap total size
    python3 scripts/codebase_dump.py /path/to/repo --include '*.py'   # only Python files
    python3 scripts/codebase_dump.py /path/to/repo --tree-only        # directory tree only

Design rationale (from A/B testing 2026-03-02):
  Markdown with ## headings + fenced code blocks produces 10x better LLM comprehension
  than JSON format when uploaded to ChatGPT/Gemini Web.
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SKIP_DIRS: set[str] = {
    ".git", ".hg", ".svn",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "node_modules", ".next", "dist", "build", "target",
    ".venv", "venv", "env",
    ".cache", ".tox",
    "Codereview",       # ChatgptREST specific: large review dumps
    "logs", "tmp", "temp",
}

SKIP_FILES: set[str] = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    ".DS_Store", "Thumbs.db",
}

BINARY_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp",
    ".mp3", ".mp4", ".wav", ".ogg", ".webm",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".whl", ".egg", ".pyc", ".pyo", ".so", ".dll", ".exe",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".db", ".sqlite", ".sqlite3",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
}

LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".fish": "fish",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".lua": "lua",
    ".vim": "vim",
    ".el": "emacs-lisp",
    ".r": "r",
    ".R": "r",
    ".dockerfile": "dockerfile",
    ".tf": "hcl",
    ".xml": "xml",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "nginx",
    ".env": "bash",
    ".gitignore": "gitignore",
    ".editorconfig": "ini",
    "Makefile": "make",
    "Dockerfile": "dockerfile",
    "Justfile": "just",
}

DEFAULT_MAX_FILE_KB = 50
DEFAULT_MAX_TOTAL_KB = 500

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def detect_lang(path: Path) -> str:
    """Return fenced code block language hint for a file."""
    name = path.name
    if name in LANG_MAP:
        return LANG_MAP[name]
    return LANG_MAP.get(path.suffix.lower(), "")


def is_binary(path: Path) -> bool:
    """Quick heuristic: check extension + first 8KB for null bytes."""
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        chunk = path.read_bytes()[:8192]
        return b"\x00" in chunk
    except Exception:
        return True


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")


def should_skip_file(name: str) -> bool:
    return name in SKIP_FILES


def collect_files(
    root: Path,
    *,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
    max_file_kb: int = DEFAULT_MAX_FILE_KB,
    max_total_kb: int = DEFAULT_MAX_TOTAL_KB,
) -> list[tuple[Path, str, int]]:
    """Walk the repo and collect (abs_path, rel_path_str, size_bytes).

    Files are sorted by: config files first, then by path alphabetically.
    Returns up to max_total_kb of content.
    """
    candidates: list[tuple[Path, str, int]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune directories in-place
        dirnames[:] = sorted(d for d in dirnames if not should_skip_dir(d))

        dp = Path(dirpath)
        for fn in sorted(filenames):
            fp = dp / fn
            if should_skip_file(fn):
                continue
            if is_binary(fp):
                continue

            rel = str(fp.relative_to(root))

            # Apply include globs
            if include_globs:
                if not any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(fn, g) for g in include_globs):
                    continue

            # Apply exclude globs
            if exclude_globs:
                if any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(fn, g) for g in exclude_globs):
                    continue

            try:
                sz = fp.stat().st_size
            except OSError:
                continue

            if sz > max_file_kb * 1024:
                continue

            candidates.append((fp, rel, sz))

    # Sort: important files first (README, config, entry points), then alpha
    def sort_key(item: tuple[Path, str, int]) -> tuple[int, str]:
        _, rel, _ = item
        name = Path(rel).name.lower()
        # Priority buckets
        if name in ("readme.md", "readme.rst", "readme.txt", "readme"):
            return (0, rel)
        if name in ("pyproject.toml", "setup.py", "setup.cfg", "package.json", "cargo.toml", "go.mod"):
            return (1, rel)
        if name in ("agents.md", "contributing.md", "changelog.md"):
            return (2, rel)
        if name.startswith("__init__"):
            return (3, rel)
        return (5, rel)

    candidates.sort(key=sort_key)

    # Enforce total size cap
    result: list[tuple[Path, str, int]] = []
    total = 0
    for fp, rel, sz in candidates:
        if total + sz > max_total_kb * 1024:
            continue  # skip individual large files to fit more smaller ones
        result.append((fp, rel, sz))
        total += sz

    return result


def build_tree(files: list[tuple[Path, str, int]], root: Path) -> str:
    """Build a compact directory tree string from the collected files."""
    dirs: dict[str, list[str]] = {}
    for _, rel, sz in files:
        parts = Path(rel).parts
        if len(parts) == 1:
            dirs.setdefault(".", []).append(f"{parts[0]} ({sz // 1024}KB)" if sz > 1024 else parts[0])
        else:
            d = "/".join(parts[:-1])
            dirs.setdefault(d, []).append(parts[-1])

    lines: list[str] = []
    for d in sorted(dirs.keys()):
        if d == ".":
            for f in dirs[d]:
                lines.append(f"  {f}")
        else:
            lines.append(f"  {d}/")
            for f in sorted(dirs[d]):
                lines.append(f"    {f}")

    return "\n".join(lines)


def generate_snapshot(
    root: Path,
    files: list[tuple[Path, str, int]],
    *,
    tree_only: bool = False,
) -> str:
    """Generate the full Markdown snapshot."""
    project_name = root.name
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_size = sum(sz for _, _, sz in files)

    parts: list[str] = [
        f"# {project_name} 代码库快照\n",
        f"> 生成时间: {now} | 文件数: {len(files)} | 总大小: {total_size / 1024:.1f} KB\n",
        "## 目录结构\n",
        "```",
        build_tree(files, root),
        "```\n",
    ]

    if tree_only:
        return "\n".join(parts)

    # File contents
    for fp, rel, sz in files:
        lang = detect_lang(fp)
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            content = f"[读取失败: {exc}]"

        # Trim trailing whitespace per line
        content = "\n".join(line.rstrip() for line in content.splitlines())

        parts.append(f"## `{rel}`\n")
        parts.append(f"```{lang}")
        parts.append(content)
        parts.append("```\n")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Markdown snapshot of a code repository for LLM consumption."
    )
    parser.add_argument("repo", type=Path, help="Path to the repository root")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output file (default: stdout)")
    parser.add_argument("--max-kb", type=int, default=DEFAULT_MAX_TOTAL_KB, help=f"Max total KB (default: {DEFAULT_MAX_TOTAL_KB})")
    parser.add_argument("--max-file-kb", type=int, default=DEFAULT_MAX_FILE_KB, help=f"Max per-file KB (default: {DEFAULT_MAX_FILE_KB})")
    parser.add_argument("--include", nargs="*", default=None, help="Include globs (e.g. '*.py' '*.md')")
    parser.add_argument("--exclude", nargs="*", default=None, help="Exclude globs (e.g. 'tests/*')")
    parser.add_argument("--tree-only", action="store_true", help="Only output directory tree, no file contents")

    args = parser.parse_args()

    root = args.repo.resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        return 1

    files = collect_files(
        root,
        include_globs=args.include,
        exclude_globs=args.exclude,
        max_file_kb=args.max_file_kb,
        max_total_kb=args.max_kb,
    )

    if not files:
        print("Warning: no files collected", file=sys.stderr)
        return 1

    snapshot = generate_snapshot(root, files, tree_only=args.tree_only)

    if args.output:
        args.output.write_text(snapshot, encoding="utf-8")
        total_kb = sum(sz for _, _, sz in files) / 1024
        print(f"Wrote {args.output} ({len(snapshot) / 1024:.1f} KB, {len(files)} files, content {total_kb:.1f} KB)", file=sys.stderr)
    else:
        sys.stdout.write(snapshot)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
