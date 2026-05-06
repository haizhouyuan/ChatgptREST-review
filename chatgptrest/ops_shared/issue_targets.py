from __future__ import annotations

import json
import time
from typing import Any

from chatgptrest.core import client_issues, job_store


def is_internal_followup_job_kind(kind: str | None) -> bool:
    kind_l = str(kind or "").strip().lower()
    return kind_l.startswith("sre.") or kind_l.startswith("repair.")


def is_internal_issue_source(source: str | None) -> bool:
    source_l = str(source or "").strip().lower()
    return source_l.startswith("sre.") or source_l.startswith("repair.")


def recent_issue_events(conn: Any, *, issue_id: str, limit: int = 24) -> list[dict[str, Any]]:
    events, _next_after = client_issues.list_issue_events(conn, issue_id=issue_id, limit=max(1, int(limit)))
    out: list[dict[str, Any]] = []
    for event in events:
        out.append(
            {
                "id": event.id,
                "ts": event.ts,
                "type": event.type,
                "payload": event.payload,
            }
        )
    return out


def resolve_issue_external_target(
    conn: Any,
    *,
    issue: client_issues.ClientIssueRecord,
    issue_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    events = list(issue_events or recent_issue_events(conn, issue_id=issue.issue_id))
    candidate_job_ids: list[str] = []

    def _add_candidate(job_id: str | None) -> None:
        value = str(job_id or "").strip()
        if value and value not in candidate_job_ids:
            candidate_job_ids.append(value)

    _add_candidate(issue.latest_job_id)
    for event in reversed(events):
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        _add_candidate(payload.get("job_id"))

    resolved_job: job_store.JobRecord | None = None
    for candidate_id in candidate_job_ids:
        job = job_store.get_job(conn, job_id=candidate_id)
        if job is None:
            continue
        if not is_internal_followup_job_kind(job.kind):
            resolved_job = job
            break

    source_candidates: list[str] = []
    current_source = str(issue.source or "").strip()
    if current_source:
        source_candidates.append(current_source)
    for event in reversed(events):
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        source = str(payload.get("source") or "").strip()
        if source and source not in source_candidates:
            source_candidates.append(source)

    resolved_source = ""
    for source in source_candidates:
        if not is_internal_issue_source(source):
            resolved_source = source
            break
    if not resolved_source and current_source:
        resolved_source = current_source

    return {
        "issue_id": issue.issue_id,
        "candidate_job_ids": candidate_job_ids,
        "resolved_job_id": (resolved_job.job_id if resolved_job is not None else (candidate_job_ids[0] if candidate_job_ids else None)),
        "resolved_job_kind": (resolved_job.kind if resolved_job is not None else None),
        "resolved_source": (resolved_source or None),
    }


def backfill_polluted_issue_targets(
    conn: Any,
    *,
    issue_id: str | None = None,
    limit: int = 200,
    now: float | None = None,
) -> list[dict[str, Any]]:
    now_ts = float(time.time() if now is None else now)
    params: list[Any] = []
    query = """
        SELECT issue_id
        FROM client_issues
        WHERE 1=1
    """
    if issue_id:
        query += " AND issue_id = ?"
        params.append(str(issue_id))
    else:
        query += """
            AND (
                latest_job_id IN (
                    SELECT job_id FROM jobs WHERE kind LIKE 'sre.%' OR kind LIKE 'repair.%'
                )
                OR source LIKE 'sre.%'
                OR source LIKE 'repair.%'
            )
            ORDER BY updated_at DESC
            LIMIT ?
        """
        params.append(max(1, int(limit)))

    rows = conn.execute(query, tuple(params)).fetchall()
    updates: list[dict[str, Any]] = []
    for row in rows:
        issue = client_issues.get_issue(conn, issue_id=str(row["issue_id"]))
        if issue is None:
            continue
        issue_events = recent_issue_events(conn, issue_id=issue.issue_id, limit=48)
        resolved = resolve_issue_external_target(conn, issue=issue, issue_events=issue_events)

        update_job_id = str(resolved.get("resolved_job_id") or "").strip()
        update_source = str(resolved.get("resolved_source") or "").strip()
        changes: dict[str, Any] = {}
        if update_job_id and update_job_id != str(issue.latest_job_id or "").strip():
            changes["latest_job_id"] = update_job_id
        if update_source and is_internal_issue_source(issue.source) and update_source != str(issue.source or "").strip():
            changes["source"] = update_source
        if not changes:
            continue

        conn.execute(
            """
            UPDATE client_issues
            SET updated_at = ?,
                last_seen_at = ?,
                latest_job_id = COALESCE(?, latest_job_id),
                source = COALESCE(?, source)
            WHERE issue_id = ?
            """,
            (
                now_ts,
                now_ts,
                changes.get("latest_job_id"),
                changes.get("source"),
                issue.issue_id,
            ),
        )
        conn.execute(
            "INSERT INTO client_issue_events(issue_id, ts, type, payload_json) VALUES (?,?,?,?)",
            (
                issue.issue_id,
                now_ts,
                "issue_target_backfilled",
                json.dumps(
                    {
                        "before": {
                            "latest_job_id": issue.latest_job_id,
                            "source": issue.source,
                        },
                        "after": changes,
                        "resolution": resolved,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            ),
        )
        updates.append(
            {
                "issue_id": issue.issue_id,
                "before_latest_job_id": issue.latest_job_id,
                "after_latest_job_id": changes.get("latest_job_id", issue.latest_job_id),
                "before_source": issue.source,
                "after_source": changes.get("source", issue.source),
                "candidate_job_ids": resolved.get("candidate_job_ids") or [],
            }
        )
    return updates
