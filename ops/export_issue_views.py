#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any

from chatgptrest.core import client_issues, issue_canonical
from chatgptrest.core.db import connect
from chatgptrest.ops_shared.infra import atomic_write_json

DEFAULT_DB = "/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3"
DEFAULT_JSON_OUT = "/vol1/1000/projects/ChatgptREST/artifacts/monitor/open_issue_list/latest.json"
DEFAULT_MD_OUT = "/vol1/1000/projects/ChatgptREST/artifacts/monitor/open_issue_list/latest.md"
DEFAULT_HISTORY_JSON_OUT = "/vol1/1000/projects/ChatgptREST/artifacts/monitor/open_issue_list/history_tail.json"
DEFAULT_HISTORY_MD_OUT = "/vol1/1000/projects/ChatgptREST/artifacts/monitor/open_issue_list/history_tail.md"

ACTIVE_STATUSES = (
    client_issues.CLIENT_ISSUE_STATUS_OPEN,
    client_issues.CLIENT_ISSUE_STATUS_IN_PROGRESS,
)
RECENT_STATUSES = (
    client_issues.CLIENT_ISSUE_STATUS_MITIGATED,
    client_issues.CLIENT_ISSUE_STATUS_CLOSED,
)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _fmt_ts(ts: float | None) -> str:
    if not ts:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))


def _record(issue: client_issues.ClientIssueRecord) -> dict[str, Any]:
    return {
        "issue_id": issue.issue_id,
        "project": issue.project,
        "title": issue.title,
        "kind": issue.kind,
        "severity": issue.severity,
        "status": issue.status,
        "source": issue.source,
        "symptom": issue.symptom,
        "count": int(issue.count),
        "created_at": float(issue.created_at),
        "updated_at": float(issue.updated_at),
        "last_seen_at": float(issue.last_seen_at),
        "closed_at": (float(issue.closed_at) if issue.closed_at is not None else None),
        "latest_job_id": issue.latest_job_id,
        "latest_conversation_url": issue.latest_conversation_url,
        "latest_artifacts_path": issue.latest_artifacts_path,
        "tags": list(issue.tags or []),
        "metadata": dict(issue.metadata or {}),
    }


def _view_issue_row(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_id": str(issue.get("issue_id") or ""),
        "project": str(issue.get("project") or ""),
        "title": str(issue.get("title") or ""),
        "kind": (str(issue["kind"]) if issue.get("kind") is not None else None),
        "severity": str(issue.get("severity") or ""),
        "status": str(issue.get("status") or ""),
        "source": (str(issue["source"]) if issue.get("source") is not None else None),
        "symptom": str(issue.get("symptom") or ""),
        "count": int(issue.get("count") or 0),
        "created_at": float(issue.get("created_at") or 0.0),
        "updated_at": float(issue.get("updated_at") or 0.0),
        "last_seen_at": float(issue.get("last_seen_at") or 0.0),
        "closed_at": (float(issue["closed_at"]) if issue.get("closed_at") is not None else None),
        "latest_job_id": (str(issue["latest_job_id"]) if issue.get("latest_job_id") is not None else None),
        "latest_conversation_url": (
            str(issue["latest_conversation_url"]) if issue.get("latest_conversation_url") is not None else None
        ),
        "latest_artifacts_path": (
            str(issue["latest_artifacts_path"]) if issue.get("latest_artifacts_path") is not None else None
        ),
        "tags": list(issue.get("tags") or []),
        "metadata": dict(issue.get("metadata") or {}),
    }


def _severity_sort_key(value: str | None) -> tuple[int, str]:
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    raw = str(value or "").upper()
    return (order.get(raw, 99), raw)


def _recent_event_rows(conn: sqlite3.Connection, *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          e.id,
          e.issue_id,
          e.ts,
          e.type,
          e.payload_json,
          i.title,
          i.status,
          i.severity,
          i.kind,
          i.source
        FROM client_issue_events e
        JOIN client_issues i ON i.issue_id = e.issue_id
        WHERE e.type IN (
          'issue_reported',
          'issue_status_updated',
          'issue_evidence_linked',
          'issue_verification_recorded',
          'issue_usage_evidence_recorded'
        )
        ORDER BY e.id DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = None
        try:
            payload = json.loads(str(row["payload_json"])) if row["payload_json"] is not None else None
        except Exception:
            payload = {"_raw": str(row["payload_json"])}
        out.append(
            {
                "id": int(row["id"]),
                "issue_id": str(row["issue_id"]),
                "ts": float(row["ts"]),
                "type": str(row["type"]),
                "title": str(row["title"] or ""),
                "status": str(row["status"] or ""),
                "severity": str(row["severity"] or ""),
                "kind": (str(row["kind"]) if row["kind"] is not None else None),
                "source": (str(row["source"]) if row["source"] is not None else None),
                "payload": payload,
            }
        )
    return out


def build_snapshot(
    *,
    db_path: Path,
    active_limit: int,
    recent_limit: int,
    history_limit: int,
) -> tuple[dict[str, Any], str, dict[str, Any], str]:
    generated_at = time.time()
    with connect(db_path) as conn:
        recent_events = _recent_event_rows(conn, limit=max(1, int(history_limit)))
        try:
            canonical_snapshot = issue_canonical.build_issue_views_snapshot_from_canonical(
                authoritative_conn=conn,
                active_statuses=ACTIVE_STATUSES,
                recent_statuses=RECENT_STATUSES,
                active_limit=max(1, int(active_limit)),
                recent_limit=max(1, int(recent_limit)),
                ensure_fresh=True,
            )
        except (issue_canonical.IssueCanonicalUnavailable, sqlite3.Error, OSError):
            canonical_snapshot = None

        if canonical_snapshot:
            active_rows = [_view_issue_row(issue) for issue in canonical_snapshot.get("active_issues") or []]
            recent_rows = [_view_issue_row(issue) for issue in canonical_snapshot.get("recently_settled") or []]
            all_issue_rows = active_rows + recent_rows
            status_counts = Counter(str(row.get("status") or "") for row in all_issue_rows)
            severity_counts = Counter(str(row.get("severity") or "") for row in all_issue_rows)
            source_counts = Counter(str(row.get("source") or "unknown") for row in all_issue_rows)
            snapshot = {
                "generated_at": float(generated_at),
                "db_path": str(db_path),
                "summary": {
                    **dict(canonical_snapshot.get("summary") or {}),
                    "total_issues": int(len(all_issue_rows)),
                    "active_issues": int(len(active_rows)),
                    "recently_settled": int(len(recent_rows)),
                    "status_counts": dict(sorted(status_counts.items())),
                    "severity_counts": dict(sorted(severity_counts.items())),
                    "source_counts": dict(sorted(source_counts.items())),
                },
                "active_issues": active_rows,
                "recently_settled": recent_rows,
            }
            active_issues = active_rows
            recent_issues = recent_rows
        else:
            active_issue_records, _, _ = client_issues.list_issues(
                conn,
                status=",".join(ACTIVE_STATUSES),
                limit=max(1, int(active_limit)),
            )
            recent_issue_records, _, _ = client_issues.list_issues(
                conn,
                status=",".join(RECENT_STATUSES),
                limit=max(1, int(recent_limit)),
            )
            all_rows = conn.execute(
                """
                SELECT status, severity, source
                FROM client_issues
                """
            ).fetchall()
            status_counts = Counter(str(row["status"] or "") for row in all_rows)
            severity_counts = Counter(str(row["severity"] or "") for row in all_rows)
            source_counts = Counter(str(row["source"] or "unknown") for row in all_rows)
            active_issue_records = sorted(
                active_issue_records,
                key=lambda issue: (_severity_sort_key(issue.severity), -float(issue.updated_at), issue.issue_id),
            )
            recent_issue_records = sorted(
                recent_issue_records,
                key=lambda issue: (-float(issue.updated_at), issue.issue_id),
            )
            active_issues = [_record(issue) for issue in active_issue_records]
            recent_issues = [_record(issue) for issue in recent_issue_records]
            snapshot = {
                "generated_at": float(generated_at),
                "db_path": str(db_path),
                "summary": {
                    "read_plane": "legacy_fallback",
                    "total_issues": int(len(all_rows)),
                    "active_issues": int(len(active_issues)),
                    "recently_settled": int(len(recent_issues)),
                    "status_counts": dict(sorted(status_counts.items())),
                    "severity_counts": dict(sorted(severity_counts.items())),
                    "source_counts": dict(sorted(source_counts.items())),
                },
                "active_issues": active_issues,
                "recently_settled": recent_issues,
            }

    history = {
        "generated_at": float(generated_at),
        "db_path": str(db_path),
        "event_count": int(len(recent_events)),
        "events": recent_events,
    }

    md_lines: list[str] = [
        "# Open Issue List",
        "",
        f"Generated at: `{_fmt_ts(generated_at)}`",
        "",
        "## Summary",
        "",
        f"- total issues: `{snapshot['summary']['total_issues']}`",
        f"- active issues: `{snapshot['summary']['active_issues']}`",
        f"- recently settled: `{snapshot['summary']['recently_settled']}`",
        "",
        "### Status Counts",
        "",
    ]
    for status, count in snapshot["summary"]["status_counts"].items():
        md_lines.append(f"- `{status}`: `{count}`")
    md_lines.extend(["", "## Active Issues", ""])
    if not active_issues:
        md_lines.append("- none")
    for issue in active_issues:
        md_lines.extend(
            [
                f"- `{issue['issue_id']}` [{issue['severity']}] `{issue['status']}` {issue['title']}",
                f"  project=`{issue['project']}` source=`{issue.get('source') or 'unknown'}` kind=`{issue.get('kind') or '-'}` count=`{issue['count']}`",
                f"  last_seen=`{_fmt_ts(issue.get('last_seen_at'))}` latest_job=`{issue.get('latest_job_id') or '-'}`",
                f"  artifacts=`{issue.get('latest_artifacts_path') or '-'}`",
            ]
        )
    md_lines.extend(["", "## Recently Mitigated / Closed", ""])
    if not recent_issues:
        md_lines.append("- none")
    for issue in recent_issues[:20]:
        md_lines.extend(
            [
                f"- `{issue['issue_id']}` [{issue['severity']}] `{issue['status']}` {issue['title']}",
                f"  updated=`{_fmt_ts(issue.get('updated_at'))}` closed=`{_fmt_ts(issue.get('closed_at')) if issue.get('closed_at') else '-'}`",
            ]
        )

    history_lines: list[str] = [
        "# Issue History Evolution Snapshot",
        "",
        f"Generated at: `{_fmt_ts(generated_at)}`",
        "",
        f"- recent events: `{len(recent_events)}`",
        "",
        "## Recent Events",
        "",
    ]
    if not recent_events:
        history_lines.append("- none")
    for event in recent_events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        note = ""
        if event["type"] == "issue_status_updated":
            note = f"{payload.get('from') or '-'} -> {payload.get('to') or '-'}"
            if payload.get("note"):
                note = f"{note}; {payload.get('note')}"
        elif event["type"] == "issue_reported":
            note = "reported"
            if payload.get("reopened"):
                note = "reported; reopened"
        elif event["type"] == "issue_evidence_linked":
            note = payload.get("note") or "evidence linked"
        elif event["type"] == "issue_verification_recorded":
            note = f"verification {payload.get('verification_type') or '-'}"
            if payload.get("job_id"):
                note = f"{note}; job={payload.get('job_id')}"
        elif event["type"] == "issue_usage_evidence_recorded":
            note = f"usage {payload.get('job_id') or '-'}"
            if payload.get("client_name"):
                note = f"{note}; client={payload.get('client_name')}"
        history_lines.append(
            f"- `{_fmt_ts(event['ts'])}` `{event['issue_id']}` `{event['type']}` {event['title']} :: {note}"
        )

    return snapshot, "\n".join(md_lines).rstrip() + "\n", history, "\n".join(history_lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Export ChatgptREST issue ledger views")
    p.add_argument("--db-path", default=DEFAULT_DB)
    p.add_argument("--json-out", default=DEFAULT_JSON_OUT)
    p.add_argument("--md-out", default=DEFAULT_MD_OUT)
    p.add_argument("--history-json-out", default=DEFAULT_HISTORY_JSON_OUT)
    p.add_argument("--history-md-out", default=DEFAULT_HISTORY_MD_OUT)
    p.add_argument("--active-limit", type=int, default=200)
    p.add_argument("--recent-limit", type=int, default=50)
    p.add_argument("--history-limit", type=int, default=200)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = Path(str(args.db_path)).expanduser()
    json_out = Path(str(args.json_out)).expanduser()
    md_out = Path(str(args.md_out)).expanduser()
    history_json_out = Path(str(args.history_json_out)).expanduser()
    history_md_out = Path(str(args.history_md_out)).expanduser()

    snapshot, markdown, history, history_markdown = build_snapshot(
        db_path=db_path,
        active_limit=int(args.active_limit),
        recent_limit=int(args.recent_limit),
        history_limit=int(args.history_limit),
    )
    atomic_write_json(json_out, snapshot)
    _atomic_write_text(md_out, markdown)
    atomic_write_json(history_json_out, history)
    _atomic_write_text(history_md_out, history_markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
