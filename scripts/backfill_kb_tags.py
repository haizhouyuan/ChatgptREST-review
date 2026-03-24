#!/usr/bin/env python3
"""Backfill KB FTS5 documents with tags from a controlled vocabulary.

Uses title + first 500 chars of content for keyword-based matching.
No LLM required — purely heuristic.

Usage:
    python scripts/backfill_kb_tags.py --dry-run   # preview changes
    python scripts/backfill_kb_tags.py              # apply changes
    python scripts/backfill_kb_tags.py --stats      # show tag distribution
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

# ── Controlled vocabulary ────────────────────────────────────────
# Aligned with config/agent_roles.yaml kb_scope_tags

TAG_RULES: dict[str, list[str]] = {
    # devops scope
    "chatgptrest": [
        "chatgptrest", "chatgpt_web", "chatgpt_driver", "chatgptmcp",
        "rest api", "rest 作业", "job queue", "worker",
    ],
    "ops": [
        "ops/", "运维", "monitor", "soak", "maint_daemon", "systemd",
        "guardian", "watchdog", "incident", "repair", "autofix",
    ],
    "infra": [
        "chrome", "cdp", "proxy", "mihomo", "docker", "systemctl",
        "yogas2", "homepc",
    ],
    "driver": [
        "driver", "chatgpt_web_ask", "chatgpt_web_wait", "gemini_web",
        "qwen_web", "send_stage", "wait_stage", "conversation_export",
    ],
    "mcp": [
        "mcp", "mcp_server", "mcp_bridge", "stdio", "gitnexus",
    ],
    "runbook": [
        "runbook", "playbook", "troubleshoot", "how-to", "checklist",
        "rollout", "deploy",
    ],
    # research scope
    "research": [
        "research", "deep_research", "thesis", "analysis",
        "研究", "深度研究", "分析",
    ],
    "finagent": [
        "finagent", "investment", "portfolio", "market", "stock",
        "fund", "quant", "策略", "投资",
    ],
    "education": [
        "education", "教育", "consulting", "咨询", "课程",
        "培训", "学习",
    ],
    "analysis": [
        "report", "report_graph", "funnel", "analysis", "分析报告",
        "evaluation", "assessment",
    ],
    "market": [
        "market", "sector", "economy", "gdp", "macro",
        "行业", "市场", "经济",
    ],
}


def _match_tags(title: str, content_preview: str) -> list[str]:
    """Match tags based on title + first 500 chars of content."""
    text = f"{title} {content_preview[:500]}".lower()
    matched: list[str] = []
    for tag, keywords in TAG_RULES.items():
        for kw in keywords:
            if kw.lower() in text:
                matched.append(tag)
                break
    return sorted(set(matched))


def backfill(*, db_path: str, dry_run: bool = True) -> dict[str, int]:
    """Backfill tags for all documents in the KB.

    Returns:
        Dict with counts: total, updated, skipped, already_tagged
    """
    conn = sqlite3.connect(db_path, timeout=10)

    # Migrate: ensure tags column exists in meta
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(kb_fts_meta)").fetchall()}
        if "tags" not in cols:
            conn.execute("ALTER TABLE kb_fts_meta ADD COLUMN tags TEXT NOT NULL DEFAULT ''")
            conn.commit()
    except Exception as e:
        print(f"Migration warning: {e}", file=sys.stderr)

    # FTS5 content table uses c0=artifact_id, c1=title, c2=content, c3=source_path, c4=tags
    rows_raw = conn.execute("""
        SELECT c0, c1, substr(c2, 1, 500)
        FROM kb_fts_content
    """).fetchall()

    # Get current meta tags
    meta_tags = {}
    try:
        for row in conn.execute("SELECT artifact_id, tags FROM kb_fts_meta").fetchall():
            meta_tags[row[0]] = row[1]
    except sqlite3.OperationalError:
        pass

    stats = {"total": len(rows_raw), "updated": 0, "skipped": 0, "already_tagged": 0}

    for artifact_id, title, preview in rows_raw:
        current = meta_tags.get(artifact_id, "")
        if current.strip():
            stats["already_tagged"] += 1
            continue

        new_tags = _match_tags(title or "", preview or "")
        if not new_tags:
            stats["skipped"] += 1
            continue

        tags_str = " ".join(new_tags)
        if dry_run:
            print(f"  [dry-run] {artifact_id}: {title[:60]}  →  {tags_str}")
        else:
            # Update meta table
            conn.execute(
                "UPDATE kb_fts_meta SET tags = ? WHERE artifact_id = ?",
                (tags_str, artifact_id),
            )
            # Update FTS5 content — need to delete and re-insert
            fts_row = conn.execute(
                "SELECT c0, c1, c2, c3, c4 FROM kb_fts_content WHERE c0 = ?",
                (artifact_id,),
            ).fetchone()
            if fts_row:
                conn.execute("DELETE FROM kb_fts WHERE artifact_id = ?", (artifact_id,))
                conn.execute(
                    "INSERT INTO kb_fts (artifact_id, title, content, source_path, tags) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (fts_row[0], fts_row[1], fts_row[2], fts_row[3], tags_str),
                )
        stats["updated"] += 1

    if not dry_run:
        conn.commit()
    conn.close()
    return stats


def show_stats(db_path: str) -> None:
    """Show tag distribution across KB documents."""
    conn = sqlite3.connect(db_path, timeout=10)
    total = conn.execute("SELECT count(*) FROM kb_fts_content").fetchone()[0]

    try:
        tagged = conn.execute(
            "SELECT count(*) FROM kb_fts_meta WHERE tags != ''"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        tagged = 0

    print(f"Total docs: {total}")
    print(f"Tagged: {tagged}/{total} ({tagged/total*100:.1f}%)" if total else "No docs")

    if tagged > 0:
        # Tag frequency
        freq: dict[str, int] = {}
        rows = conn.execute("SELECT tags FROM kb_fts_meta WHERE tags != ''").fetchall()
        for (tags_str,) in rows:
            for tag in tags_str.split():
                freq[tag] = freq.get(tag, 0) + 1
        print("\nTag distribution:")
        for tag, count in sorted(freq.items(), key=lambda x: -x[1]):
            print(f"  {tag}: {count}")

    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill KB tags from controlled vocabulary")
    parser.add_argument(
        "--db-path",
        default=str(Path("~/.openmind/kb_search.db").expanduser()),
        help="Path to kb_search.db",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--stats", action="store_true", help="Show tag distribution only")
    args = parser.parse_args()

    if args.stats:
        show_stats(args.db_path)
        return 0

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"=== KB Tag Backfill ({mode}) ===")
    print(f"DB: {args.db_path}")

    result = backfill(db_path=args.db_path, dry_run=args.dry_run)

    print(f"\nResults:")
    print(f"  Total docs:      {result['total']}")
    print(f"  Updated:         {result['updated']}")
    print(f"  Skipped (no match): {result['skipped']}")
    print(f"  Already tagged:  {result['already_tagged']}")

    if args.dry_run and result["updated"] > 0:
        print(f"\nRun without --dry-run to apply {result['updated']} tag updates.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
