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
    load_authority_anchor_from_path,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _anchor_rows(planning_root: Path, *, stale_days: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for anchor_path in sorted(planning_root.rglob("_project_context.md")):
        anchor = load_authority_anchor_from_path(anchor_path, stale_days=stale_days)
        metadata = anchor.to_runtime_metadata()
        rows.append(
            {
                "project_id": anchor.project_id,
                "project": anchor.project,
                "alias": anchor.alias,
                "anchor_path": anchor.anchor_path,
                "owner": anchor.owner,
                "last_reviewed_at": anchor.last_reviewed_at,
                "stale_status": anchor.stale_status,
                "schema_gaps": list(anchor.schema_gaps),
                "missing_docs": list(anchor.missing_docs),
                "pinned_authority_inputs": list(anchor.pinned_authority_inputs),
                "current_phase_framing_present": bool(anchor.current_phase_framing.strip()),
                "authority_docs": metadata["authority_docs"],
            }
        )
    return rows


def _markdown_report(*, rows: list[dict[str, Any]], stale_days: int, generated_at: str) -> str:
    lines = [
        "# Authority Governance Scan",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Stale threshold days: `{stale_days}`",
        f"- Anchor count: `{len(rows)}`",
        "",
    ]
    stale = [row for row in rows if row["stale_status"] == "stale"]
    missing = [row for row in rows if row["missing_docs"]]
    schema_partial = [row for row in rows if row["schema_gaps"]]
    lines.extend(
        [
            "## Summary",
            "",
            f"- Stale anchors: `{len(stale)}`",
            f"- Anchors with missing docs: `{len(missing)}`",
            f"- Anchors with schema gaps: `{len(schema_partial)}`",
            "",
            "## Anchors",
            "",
        ]
    )
    for row in rows:
        lines.append(f"### {row['project_id']} / {row['project']}")
        lines.append(f"- Anchor: `{row['anchor_path']}`")
        lines.append(f"- Owner: `{row['owner']}`")
        lines.append(f"- Last reviewed: `{row['last_reviewed_at'] or 'unknown'}`")
        lines.append(f"- Stale status: `{row['stale_status']}`")
        lines.append(f"- Schema gaps: `{', '.join(row['schema_gaps']) if row['schema_gaps'] else 'none'}`")
        lines.append(f"- Missing docs: `{', '.join(row['missing_docs']) if row['missing_docs'] else 'none'}`")
        for doc in row["authority_docs"]:
            lines.append(
                f"  - doc `{doc['path']}` exists={doc['exists']} non_empty={doc['non_empty']} stale={doc['stale_status']}"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the authority-anchor governance integrity scan.")
    parser.add_argument("--planning-root", default=str(DEFAULT_PLANNING_ROOT))
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = _now()
    rows = _anchor_rows(Path(args.planning_root), stale_days=args.stale_days)
    summary = {
        "generated_at": generated_at,
        "planning_root": str(Path(args.planning_root).resolve()),
        "stale_threshold_days": args.stale_days,
        "anchor_count": len(rows),
        "anchors": rows,
    }
    (output_dir / "authority_governance_scan.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "authority_governance_scan.md").write_text(
        _markdown_report(rows=rows, stale_days=args.stale_days, generated_at=generated_at),
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "output_dir": str(output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
