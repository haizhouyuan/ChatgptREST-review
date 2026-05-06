#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from chatgptrest.core import issue_canonical, issue_graph
from chatgptrest.core.db import connect
from chatgptrest.ops_shared.infra import atomic_write_json

DEFAULT_DB = "/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3"
DEFAULT_JSON_OUT = "/vol1/1000/projects/ChatgptREST/artifacts/monitor/issue_graph/latest.json"
DEFAULT_MD_OUT = "/vol1/1000/projects/ChatgptREST/artifacts/monitor/issue_graph/latest.md"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export ChatgptREST issue graph snapshot")
    parser.add_argument("--db-path", default=DEFAULT_DB)
    parser.add_argument("--json-out", default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", default=DEFAULT_MD_OUT)
    parser.add_argument("--max-issues", type=int, default=1000)
    parser.add_argument("--include-closed", action="store_true", default=True)
    parser.add_argument("--no-include-closed", dest="include_closed", action="store_false")
    parser.add_argument("--include-docs", action="store_true", default=True)
    parser.add_argument("--no-include-docs", dest="include_docs", action="store_false")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = Path(args.db_path).expanduser()
    json_out = Path(args.json_out).expanduser()
    md_out = Path(args.md_out).expanduser()

    with connect(db_path) as conn:
        try:
            snapshot = issue_canonical.export_issue_graph_snapshot(
                authoritative_conn=conn,
                include_closed=bool(args.include_closed),
                max_issues=max(1, int(args.max_issues)),
            )
        except (issue_canonical.IssueCanonicalUnavailable, sqlite3.Error, OSError):
            snapshot = issue_graph.build_issue_graph_snapshot(
                conn,
                include_closed=bool(args.include_closed),
                max_issues=max(1, int(args.max_issues)),
                include_docs=bool(args.include_docs),
            )
            snapshot.setdefault("summary", {})
            snapshot["summary"]["read_plane"] = "legacy_fallback"
    atomic_write_json(json_out, snapshot)
    _atomic_write_text(md_out, issue_graph.build_issue_graph_markdown(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
