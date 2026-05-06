#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.governance.authority_anchor import (  # noqa: E402
    DEFAULT_PLANNING_ROOT,
    DEFAULT_STALE_DAYS,
    inspect_authority_anchor_path,
    load_authority_anchor,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _select_anchor_paths(
    *,
    planning_root: Path,
    project_ids: list[str],
    stale_days: int,
) -> tuple[list[Path], list[str]]:
    if not project_ids:
        return sorted(planning_root.rglob("_project_context.md")), []
    selected: list[Path] = []
    missing: list[str] = []
    seen: set[str] = set()
    for project_id in project_ids:
        anchor = load_authority_anchor(project_id, planning_root=planning_root, stale_days=stale_days)
        if anchor is None:
            missing.append(project_id)
            continue
        anchor_path = str(Path(anchor.anchor_path).resolve())
        if anchor_path in seen:
            continue
        seen.add(anchor_path)
        selected.append(Path(anchor.anchor_path))
    return selected, missing


def build_project_context_harness(
    *,
    planning_root: Path,
    project_ids: list[str],
    stale_days: int,
) -> dict[str, Any]:
    anchor_paths, missing_projects = _select_anchor_paths(
        planning_root=planning_root,
        project_ids=project_ids,
        stale_days=stale_days,
    )
    rows = [
        inspect_authority_anchor_path(anchor_path, stale_days=stale_days)
        for anchor_path in anchor_paths
    ]
    lint_failed = [row for row in rows if row["lint_status"] == "fail"]
    lint_warn = [row for row in rows if row["lint_status"] == "warn"]
    stale = [row for row in rows if row["stale_status"] == "stale"]
    return {
        "generated_at": _now(),
        "planning_root": str(planning_root.resolve()),
        "requested_project_ids": list(project_ids),
        "missing_project_ids": missing_projects,
        "stale_threshold_days": stale_days,
        "summary": {
            "anchor_count": len(rows),
            "lint_pass_count": sum(1 for row in rows if row["lint_status"] == "pass"),
            "lint_warn_count": len(lint_warn),
            "lint_fail_count": len(lint_failed),
            "stale_anchor_count": len(stale),
            "missing_project_id_count": len(missing_projects),
        },
        "anchors": rows,
        "ok": not lint_failed and not missing_projects,
    }


def _markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Project Context Harness",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Planning root: `{payload['planning_root']}`",
        f"- Requested project IDs: `{', '.join(payload['requested_project_ids']) if payload['requested_project_ids'] else 'all anchors'}`",
        f"- Missing project IDs: `{', '.join(payload['missing_project_ids']) if payload['missing_project_ids'] else 'none'}`",
        f"- Anchor count: `{summary['anchor_count']}`",
        f"- Lint pass / warn / fail: `{summary['lint_pass_count']} / {summary['lint_warn_count']} / {summary['lint_fail_count']}`",
        f"- Stale anchors: `{summary['stale_anchor_count']}`",
        "",
        "## Anchors",
        "",
    ]
    for row in payload["anchors"]:
        lines.append(f"### {row['project_id']} / {row['project']}")
        lines.append(f"- Anchor: `{row['anchor_path']}`")
        lines.append(f"- Owner: `{row['owner']}`")
        lines.append(f"- Last reviewed: `{row['last_reviewed_at'] or 'unknown'}`")
        lines.append(f"- Review age days: `{row['review_age_days']}`")
        lines.append(f"- Stale status: `{row['stale_status']}`")
        lines.append(f"- Lint status: `{row['lint_status']}`")
        lines.append(f"- Schema gaps: `{', '.join(row['schema_gaps']) if row['schema_gaps'] else 'none'}`")
        lines.append(f"- Missing docs: `{', '.join(row['missing_docs']) if row['missing_docs'] else 'none'}`")
        lines.append(
            f"- Required frontmatter present: `{', '.join(key for key, ok in row['required_frontmatter'].items() if ok)}`"
        )
        lines.append(
            f"- Required body sections present: `{', '.join(key for key, ok in row['required_sections'].items() if ok)}`"
        )
        lines.append(f"- Errors: `{', '.join(row['errors']) if row['errors'] else 'none'}`")
        lines.append(f"- Warnings: `{', '.join(row['warnings']) if row['warnings'] else 'none'}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run project-context lint and freshness harness.")
    parser.add_argument("--planning-root", default=str(DEFAULT_PLANNING_ROOT))
    parser.add_argument("--project-id", action="append", default=[])
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = build_project_context_harness(
        planning_root=Path(args.planning_root),
        project_ids=[str(item).strip() for item in args.project_id if str(item).strip()],
        stale_days=args.stale_days,
    )
    (output_dir / "project_context_harness.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "project_context_harness.md").write_text(
        _markdown_report(payload),
        encoding="utf-8",
    )
    print(json.dumps({"ok": payload["ok"], "output_dir": str(output_dir)}, ensure_ascii=False))
    if args.strict and not payload["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
