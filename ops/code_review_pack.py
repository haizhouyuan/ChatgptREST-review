#!/usr/bin/env python3
"""Code Review Pack — pack codebase for AI code review uploads.

Modes:
  gemini  — 10 concatenated .md files optimized for Gemini's 10-file limit
  chatgpt — single .zip with selected source code
  pr      — pack only files changed in a PR/branch + their dependencies
  public  — generate files for the public review repo sync

Usage:
  python ops/code_review_pack.py --mode gemini [--output-dir review_pack]
  python ops/code_review_pack.py --mode chatgpt [--output-dir review_pack]
  python ops/code_review_pack.py --mode pr --base master [--head HEAD]
  python ops/code_review_pack.py --mode public --review-repo /path/to/repo

Limits:
  Gemini consumer app:  10 files/prompt, 100MB each
  Gemini code import:   ≤5000 files, ≤100MB total
  ChatGPT:              zip ok, 128K token context
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "chatgptrest"

# Module grouping for Gemini 10-file budget
MODULE_GROUPS: list[dict[str, Any]] = [
    {
        "name": "01_core",
        "title": "Core — Job Store, DB, State Machine, Issues, Config",
        "patterns": ["core/"],
    },
    {
        "name": "02_mcp_server",
        "title": "MCP Server — All MCP tool definitions",
        "patterns": ["mcp/"],
    },
    {
        "name": "03_advisor",
        "title": "Advisor — LangGraph, Intent, Routing, Report, QA",
        "patterns": ["advisor/"],
    },
    {
        "name": "04_executors",
        "title": "Executors — ChatGPT, Gemini, Qwen, Repair drivers",
        "patterns": ["executors/"],
    },
    {
        "name": "05_worker",
        "title": "Worker — Main job execution pipeline",
        "patterns": ["worker/"],
    },
    {
        "name": "06_api",
        "title": "API — FastAPI routes and schemas",
        "patterns": ["api/"],
    },
    {
        "name": "07_evomap",
        "title": "EvoMap — Knowledge DB, Extractors, Retrieval, Synthesis",
        "patterns": ["evomap/"],
    },
    {
        "name": "08_kernel",
        "title": "Kernel — CC Executor, Routing, Memory, Context, LLM",
        "patterns": ["kernel/"],
    },
    {
        "name": "09_integrations",
        "title": "Integrations, KB, Providers, Workflows",
        "patterns": [
            "integrations/",
            "kb/",
            "providers/",
            "workflows/",
        ],
    },
    {
        "name": "10_misc",
        "title": "Config, CLI, Contracts, Eval, Pipeline, Observability",
        "patterns": [
            "contracts/",
            "eval/",
            "driver/",
            "observability/",
            "cli.py",
            "pipeline.py",
            "__init__.py",
        ],
    },
]

# Files/patterns to always exclude
EXCLUDE_PATTERNS: list[str] = [
    "__pycache__",
    ".pyc",
    ".env",
    "node_modules",
    ".git/",
]

# Sensitive patterns to redact (won't be included at all)
SENSITIVE_PATTERNS: list[str] = [
    r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]+['\"]",
]


# ── Data Classes ─────────────────────────────────────────────────────────

@dataclass
class SourceFile:
    """A source file with its content."""
    rel_path: str       # relative to SRC_DIR
    abs_path: Path
    content: str = ""
    lines: int = 0

    def load(self) -> "SourceFile":
        try:
            self.content = self.abs_path.read_text(encoding="utf-8", errors="replace")
            self.lines = self.content.count("\n")
        except Exception as e:
            self.content = f"# ERROR reading {self.rel_path}: {e}\n"
            self.lines = 1
        return self


@dataclass
class PackGroup:
    """A group of files to be concatenated into one output file."""
    name: str
    title: str
    files: list[SourceFile] = field(default_factory=list)

    @property
    def total_lines(self) -> int:
        return sum(f.lines for f in self.files)

    @property
    def total_bytes(self) -> int:
        return sum(len(f.content.encode("utf-8", errors="replace")) for f in self.files)


# ── File Discovery ───────────────────────────────────────────────────────

def discover_source_files(src_dir: Path = SRC_DIR) -> list[SourceFile]:
    """Find all Python source files under src_dir, excluding noise."""
    files: list[SourceFile] = []
    for root, _dirs, names in os.walk(src_dir):
        root_path = Path(root)
        # Skip excluded dirs
        if any(excl in str(root_path) for excl in EXCLUDE_PATTERNS):
            continue
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            abs_path = root_path / name
            rel_path = str(abs_path.relative_to(src_dir))
            files.append(SourceFile(rel_path=rel_path, abs_path=abs_path).load())
    return files


def classify_files(files: list[SourceFile]) -> list[PackGroup]:
    """Assign files to module groups based on path patterns."""
    groups = [PackGroup(name=g["name"], title=g["title"]) for g in MODULE_GROUPS]
    pattern_map: list[tuple[list[str], PackGroup]] = [
        (g["patterns"], groups[i]) for i, g in enumerate(MODULE_GROUPS)
    ]

    for f in files:
        placed = False
        for patterns, group in pattern_map:
            if any(pat in f.rel_path for pat in patterns):
                group.files.append(f)
                placed = True
                break
        if not placed:
            # Put in last group (misc)
            groups[-1].files.append(f)

    return [g for g in groups if g.files]


# ── PR Diff Mode ─────────────────────────────────────────────────────────

# Directories to include in PR diffs (not just chatgptrest/)
_PR_DIFF_DIRS = [
    "chatgptrest/", "ops/", ".agents/", "tests/",
    "chatgpt_web_mcp/", "docs/",
]

# File extensions to include in PR pack
_PR_EXTENSIONS = {".py", ".md", ".yaml", ".yml", ".toml", ".cfg", ".sh"}


def get_pr_changed_files(base: str = "master", head: str = "HEAD") -> list[str]:
    """Get list of changed files between base and head across all project dirs."""
    all_changed: list[str] = []
    for pr_dir in _PR_DIFF_DIRS:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{base}...{head}", "--", pr_dir],
                capture_output=True, text=True, cwd=str(REPO_ROOT),
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["git", "diff", "--name-only", base, head, "--", pr_dir],
                    capture_output=True, text=True, cwd=str(REPO_ROOT),
                )
            for line in result.stdout.splitlines():
                path = line.strip()
                if path and any(path.endswith(ext) for ext in _PR_EXTENSIONS):
                    if path not in all_changed:
                        all_changed.append(path)
        except Exception as e:
            print(f"[WARNING] git diff for {pr_dir} failed: {e}", file=sys.stderr)
    return all_changed


def get_pr_diff_text(base: str = "master", head: str = "HEAD") -> str:
    """Get the actual diff text for PR review context."""
    parts: list[str] = []
    for pr_dir in _PR_DIFF_DIRS:
        try:
            result = subprocess.run(
                ["git", "diff", base, head, "--", pr_dir],
                capture_output=True, text=True, cwd=str(REPO_ROOT),
            )
            if result.stdout.strip():
                parts.append(result.stdout)
        except Exception:
            pass
    full = "\n".join(parts)
    return full[:200_000]  # cap at 200KB


# ── Output Generators ────────────────────────────────────────────────────

def generate_gemini_pack(
    groups: list[PackGroup],
    output_dir: Path,
    *,
    review_context: str = "",
) -> list[Path]:
    """Generate ≤10 concatenated .md files for Gemini upload."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_files: list[Path] = []

    for group in groups[:10]:  # Hard cap at 10
        out_path = output_dir / f"{group.name}.md"
        parts: list[str] = []

        # Header
        parts.append(f"# {group.title}\n")
        parts.append(f"<!-- Pack: {group.name} | Files: {len(group.files)} | Lines: {group.total_lines} -->\n")
        if review_context and group is groups[0]:
            parts.append(f"\n## Review Context\n\n{review_context}\n")
        parts.append("")

        # Table of contents
        parts.append("## File Index\n")
        offset = 0
        for f in group.files:
            parts.append(f"- `{f.rel_path}` ({f.lines} lines, starting at line ~{offset})")
            offset += f.lines + 5
        parts.append("\n---\n")

        # File contents
        for f in group.files:
            parts.append(f"\n## File: `{f.rel_path}` ({f.lines} lines)\n")
            parts.append(f"```python\n{f.content}\n```\n")
            parts.append("---\n")

        out_path.write_text("\n".join(parts), encoding="utf-8")
        output_files.append(out_path)

    # Summary manifest
    manifest_path = output_dir / "MANIFEST.md"
    manifest_parts = ["# Review Pack Manifest\n"]
    total_files = sum(len(g.files) for g in groups[:10])
    total_lines = sum(g.total_lines for g in groups[:10])
    manifest_parts.append(f"**Total**: {total_files} files, {total_lines} lines\n")
    for g in groups[:10]:
        manifest_parts.append(f"- **{g.name}.md**: {len(g.files)} files, {g.total_lines} lines — {g.title}")
    manifest_path.write_text("\n".join(manifest_parts), encoding="utf-8")

    print(f"[OK] Gemini pack: {len(output_files)} files in {output_dir}/")
    print(f"     Total: {total_files} source files, {total_lines} lines")
    for g in groups[:10]:
        size_kb = g.total_bytes / 1024
        print(f"     {g.name}.md: {len(g.files)} files, {g.total_lines} lines, {size_kb:.0f}KB")

    return output_files


def generate_chatgpt_zip(
    files: list[SourceFile],
    output_dir: Path,
    *,
    review_context: str = "",
) -> Path:
    """Generate a single .zip for ChatGPT upload."""
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "chatgptrest_review.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add review context
        if review_context:
            zf.writestr("REVIEW_CONTEXT.md", review_context)

        # Add all source files
        for f in files:
            zf.writestr(f"chatgptrest/{f.rel_path}", f.content)

        # Add key non-Python files
        for extra in ["docs/contract_v1.md", ".agents/rules.md", "README.md"]:
            extra_path = REPO_ROOT / extra
            if extra_path.exists():
                try:
                    zf.writestr(extra, extra_path.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    pass

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"[OK] ChatGPT zip: {zip_path} ({size_mb:.1f}MB, {len(files)} files)")
    return zip_path


def generate_pr_pack(
    base: str,
    head: str,
    output_dir: Path,
) -> list[Path]:
    """Generate a review pack for PR-changed files only."""
    changed_paths = get_pr_changed_files(base, head)
    if not changed_paths:
        print("[WARNING] No changed .py files found", file=sys.stderr)
        return []

    diff_text = get_pr_diff_text(base, head)

    # Load changed files
    changed_files: list[SourceFile] = []
    for rel in changed_paths:
        abs_path = REPO_ROOT / rel
        if abs_path.exists():
            src_rel = str(abs_path.relative_to(SRC_DIR)) if str(abs_path).startswith(str(SRC_DIR)) else rel
            changed_files.append(SourceFile(rel_path=src_rel, abs_path=abs_path).load())

    review_context = (
        f"# PR Review: {base} → {head}\n\n"
        f"**Changed files**: {len(changed_files)}\n\n"
        f"## Diff Summary\n\n```diff\n{diff_text[:50_000]}\n```\n"
    )

    # For small PRs (≤10 files), one file per changed file
    if len(changed_files) <= 10:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_files: list[Path] = []

        # Context file
        ctx_path = output_dir / "00_pr_context.md"
        ctx_path.write_text(review_context, encoding="utf-8")
        output_files.append(ctx_path)

        for i, f in enumerate(changed_files, 1):
            safe_name = f.rel_path.replace("/", "_").replace("\\", "_")
            out_path = output_dir / f"{i:02d}_{safe_name}.md"
            content = (
                f"# Changed: `{f.rel_path}` ({f.lines} lines)\n\n"
                f"```python\n{f.content}\n```\n"
            )
            out_path.write_text(content, encoding="utf-8")
            output_files.append(out_path)

        print(f"[OK] PR pack: {len(output_files)} files for {len(changed_files)} changed files")
        return output_files[:10]

    # For large PRs, use the same grouping as gemini mode
    groups = classify_files(changed_files)
    return generate_gemini_pack(groups, output_dir, review_context=review_context)


def generate_public_repo_sync(
    files: list[SourceFile],
    output_dir: Path,
    *,
    review_context: str = "",
) -> None:
    """Generate files for public review repo sync."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write source files (preserving directory structure)
    for f in files:
        out_path = output_dir / "chatgptrest" / f.rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(f.content, encoding="utf-8")

    # Write review context
    if review_context:
        (output_dir / "REVIEW_CONTEXT.md").write_text(review_context, encoding="utf-8")

    # Write .gitignore
    gitignore = (
        "__pycache__/\n*.pyc\n.env\n*.sqlite3\n"
        "*.log\nnode_modules/\n.cache/\n"
    )
    (output_dir / ".gitignore").write_text(gitignore, encoding="utf-8")

    # Copy key docs
    for extra in ["docs/contract_v1.md", ".agents/rules.md", "README.md"]:
        src_path = REPO_ROOT / extra
        if src_path.exists():
            dst = output_dir / extra
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                dst.write_text(src_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            except Exception:
                pass

    file_count = len(files)
    total_size = sum(len(f.content.encode()) for f in files) / (1024 * 1024)
    print(f"[OK] Public repo sync: {file_count} files, {total_size:.1f}MB in {output_dir}/")

    # Gemini limit check
    if file_count > 5000:
        print(f"[WARNING] {file_count} files exceeds Gemini's 5000-file limit!", file=sys.stderr)
    if total_size > 100:
        print(f"[WARNING] {total_size:.1f}MB exceeds Gemini's 100MB limit!", file=sys.stderr)


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pack codebase for AI code review uploads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode", required=True,
        choices=["gemini", "chatgpt", "pr", "public"],
        help="Output mode",
    )
    parser.add_argument(
        "--output-dir", default="review_pack",
        help="Output directory (default: review_pack/)",
    )
    parser.add_argument(
        "--base", default="master",
        help="Base branch for PR mode (default: master)",
    )
    parser.add_argument(
        "--head", default="HEAD",
        help="Head ref for PR mode (default: HEAD)",
    )
    parser.add_argument(
        "--review-context", default="",
        help="Extra review context text to include",
    )
    parser.add_argument(
        "--include-tests", action="store_true",
        help="Include test files in the pack",
    )

    args = parser.parse_args()
    output_dir = Path(args.output_dir)

    # Discover files
    all_files = discover_source_files()
    if not args.include_tests:
        all_files = [f for f in all_files if "/test" not in f.rel_path and "test_" not in f.rel_path]

    print(f"[INFO] Found {len(all_files)} source files ({sum(f.lines for f in all_files)} lines)")

    if args.mode == "gemini":
        groups = classify_files(all_files)
        generate_gemini_pack(groups, output_dir, review_context=args.review_context)

    elif args.mode == "chatgpt":
        generate_chatgpt_zip(all_files, output_dir, review_context=args.review_context)

    elif args.mode == "pr":
        generate_pr_pack(args.base, args.head, output_dir)

    elif args.mode == "public":
        generate_public_repo_sync(all_files, output_dir, review_context=args.review_context)

    print(f"\n[DONE] Output in: {output_dir}/")


if __name__ == "__main__":
    main()
