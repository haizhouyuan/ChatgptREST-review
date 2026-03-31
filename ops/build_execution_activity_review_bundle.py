#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from ops.export_execution_activity_review_queue import build_review_queue


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Execution Activity Review Bundle",
        "",
        "## Summary",
        "",
        f"- `db_path`: `{report['db_path']}`",
        f"- `selected_atoms`: `{report['selected_atoms']}`",
        "",
        "## Sources",
        "",
    ]
    for key, value in sorted(report["sources"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Episode Types", ""])
    for key, value in sorted(report["episode_types"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Atom Types", ""])
    for key, value in sorted(report["atom_types"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Rows", ""])
    for row in report["rows"][:20]:
        lines.extend(
            [
                f"- `{row['atom_id']}` `{row['episode_type']}` `{row['task_ref']}`",
                f"  - question: `{row['canonical_question']}`",
                f"  - trace: `{row['trace_id']}`",
                f"  - answer preview: `{row['answer_preview']}`",
            ]
        )
    return "\n".join(lines) + "\n"


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    from ops.export_execution_activity_review_queue import _write_tsv as _queue_write_tsv

    _queue_write_tsv(path, rows)


def build_bundle(*, db_path: str | Path, output_dir: str | Path, limit: int = 1000) -> dict[str, Any]:
    report = build_review_queue(db_path=db_path, limit=limit)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "review_queue.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_tsv(out / "review_queue.tsv", report["rows"])
    (out / "summary.json").write_text(
        json.dumps(
            {
                "db_path": report["db_path"],
                "selected_atoms": report["selected_atoms"],
                "sources": report["sources"],
                "episode_types": report["episode_types"],
                "atom_types": report["atom_types"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "README.md").write_text(_render_markdown(report), encoding="utf-8")
    return {
        "ok": True,
        "output_dir": str(out),
        "selected_atoms": report["selected_atoms"],
        "files": [
            str(out / "review_queue.json"),
            str(out / "review_queue.tsv"),
            str(out / "summary.json"),
            str(out / "README.md"),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a review bundle for the lineage-ready execution activity slice."
    )
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    report = build_bundle(db_path=args.db, output_dir=args.output_dir, limit=args.limit)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
