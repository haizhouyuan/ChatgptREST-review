from __future__ import annotations

import json
import re
import os
import sqlite3
import time
import hashlib
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

from chatgptrest.core import client_issues
from chatgptrest.core.issue_family_registry import match_issue_family

_TOKEN_SPLIT_RE = re.compile(r"[^0-9a-z]+")


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _collapsed_text(value: Any) -> str:
    return "".join(ch for ch in _normalize_text(value) if ch.isalnum())


def _tokenize_text(value: Any) -> set[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return set()
    tokens = {part for part in _TOKEN_SPLIT_RE.split(normalized) if part}
    collapsed = _collapsed_text(normalized)
    if collapsed:
        tokens.add(collapsed)
    return tokens


def _short_text(value: Any, *, max_chars: int = 160) -> str:
    raw = " ".join(str(value or "").strip().split())
    if len(raw) <= max_chars:
        return raw
    return raw[: max_chars - 1] + "…"


def _issue_family_id(issue: client_issues.ClientIssueRecord) -> str:
    metadata = dict(issue.metadata or {})
    explicit = str(metadata.get("family_id") or "").strip()
    if explicit:
        return explicit
    matched_id, _matched_label = match_issue_family(
        {
            "title": issue.title,
            "kind": issue.kind,
            "symptom": issue.symptom,
            "raw_error": issue.raw_error,
            "tags": list(issue.tags or []),
            "metadata": metadata,
        }
    )
    if matched_id:
        return matched_id
    return f"fp:{issue.fingerprint_hash}"


def _issue_family_label(issue: client_issues.ClientIssueRecord) -> str:
    metadata = dict(issue.metadata or {})
    explicit = str(metadata.get("family_label") or "").strip()
    if explicit:
        return explicit
    matched_id, matched_label = match_issue_family(
        {
            "title": issue.title,
            "kind": issue.kind,
            "symptom": issue.symptom,
            "raw_error": issue.raw_error,
            "tags": list(issue.tags or []),
            "metadata": metadata,
        }
    )
    if matched_id and matched_label:
        return matched_label
    kind = str(issue.kind or "issue").strip()
    symptom = _short_text(issue.symptom or issue.raw_error or issue.title, max_chars=96)
    return f"{kind}: {symptom}" if symptom else kind


def _issue_record(issue: client_issues.ClientIssueRecord) -> dict[str, Any]:
    return {
        "issue_id": issue.issue_id,
        "project": issue.project,
        "title": issue.title,
        "kind": issue.kind,
        "severity": issue.severity,
        "status": issue.status,
        "source": issue.source,
        "symptom": issue.symptom,
        "raw_error": issue.raw_error,
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
        "family_id": _issue_family_id(issue),
        "family_label": _issue_family_label(issue),
    }


def _verification_record(row: client_issues.ClientIssueVerificationRecord) -> dict[str, Any]:
    return {
        "verification_id": row.verification_id,
        "issue_id": row.issue_id,
        "ts": float(row.ts),
        "verification_type": row.verification_type,
        "status": row.status,
        "verifier": row.verifier,
        "note": row.note,
        "job_id": row.job_id,
        "conversation_url": row.conversation_url,
        "artifacts_path": row.artifacts_path,
        "metadata": dict(row.metadata or {}),
    }


def _usage_record(row: client_issues.ClientIssueUsageEvidenceRecord) -> dict[str, Any]:
    return {
        "usage_id": row.usage_id,
        "issue_id": row.issue_id,
        "ts": float(row.ts),
        "job_id": row.job_id,
        "client_name": row.client_name,
        "kind": row.kind,
        "status": row.status,
        "answer_chars": row.answer_chars,
        "metadata": dict(row.metadata or {}),
    }


def _event_payload_dict(event: client_issues.ClientIssueEventRecord) -> dict[str, Any]:
    return event.payload if isinstance(event.payload, dict) else {}


def _synthesized_verifications(
    *,
    issue: client_issues.ClientIssueRecord,
    events: list[client_issues.ClientIssueEventRecord],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for event in events:
        payload = _event_payload_dict(event)
        if str(event.type) != "issue_status_updated":
            continue
        if _normalize_text(payload.get("to")) != client_issues.CLIENT_ISSUE_STATUS_MITIGATED:
            continue
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        verification = metadata.get("verification") if isinstance(metadata.get("verification"), dict) else {}
        out.append(
            {
                "verification_id": f"legacy-ver:{issue.issue_id}:{event.id}",
                "issue_id": issue.issue_id,
                "ts": float(event.ts),
                "verification_type": str(
                    verification.get("type")
                    or metadata.get("verification_type")
                    or "status_transition"
                ),
                "status": str(
                    verification.get("status")
                    or metadata.get("verification_status")
                    or "passed"
                ),
                "verifier": (
                    verification.get("verifier")
                    or verification.get("actor")
                    or payload.get("actor")
                ),
                "note": verification.get("note") or payload.get("note"),
                "job_id": verification.get("job_id") or payload.get("linked_job_id") or issue.latest_job_id,
                "conversation_url": verification.get("conversation_url") or issue.latest_conversation_url,
                "artifacts_path": verification.get("artifacts_path") or issue.latest_artifacts_path,
                "metadata": {
                    "synthetic": True,
                    "source_event_id": int(event.id),
                    "source_event_type": str(event.type),
                    **(verification.get("metadata") if isinstance(verification.get("metadata"), dict) else {}),
                },
            }
        )
    return out


def _synthesized_usage(
    *,
    issue: client_issues.ClientIssueRecord,
    events: list[client_issues.ClientIssueEventRecord],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_job_ids: set[str] = set()
    for event in events:
        payload = _event_payload_dict(event)
        if str(event.type) != "issue_status_updated":
            continue
        if _normalize_text(payload.get("to")) != client_issues.CLIENT_ISSUE_STATUS_CLOSED:
            continue
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        success_rows = metadata.get("qualifying_successes")
        success_job_ids = metadata.get("qualifying_success_job_ids")
        synthesized_rows: list[dict[str, Any]] = []
        if isinstance(success_rows, list):
            for idx, raw in enumerate(success_rows):
                if isinstance(raw, dict) and str(raw.get("job_id") or "").strip():
                    synthesized_rows.append(
                        {
                            "usage_id": f"legacy-use:{issue.issue_id}:{event.id}:{idx}",
                            "issue_id": issue.issue_id,
                            "ts": float(raw.get("created_at") or event.ts),
                            "job_id": str(raw.get("job_id")).strip(),
                            "client_name": raw.get("client_name"),
                            "kind": raw.get("kind") or issue.kind,
                            "status": raw.get("status") or "completed",
                            "answer_chars": raw.get("answer_chars"),
                            "metadata": {
                                "synthetic": True,
                                "source_event_id": int(event.id),
                                "source_event_type": str(event.type),
                                **(raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}),
                            },
                        }
                    )
        elif isinstance(success_job_ids, list):
            for idx, raw in enumerate(success_job_ids):
                job_id = str(raw or "").strip()
                if not job_id:
                    continue
                synthesized_rows.append(
                    {
                        "usage_id": f"legacy-use:{issue.issue_id}:{event.id}:{idx}",
                        "issue_id": issue.issue_id,
                        "ts": float(event.ts),
                        "job_id": job_id,
                        "client_name": None,
                        "kind": issue.kind,
                        "status": "completed",
                        "answer_chars": None,
                        "metadata": {
                            "synthetic": True,
                            "source_event_id": int(event.id),
                            "source_event_type": str(event.type),
                        },
                    }
                )
        elif payload.get("linked_job_id"):
            job_id = str(payload.get("linked_job_id") or "").strip()
            if job_id:
                synthesized_rows.append(
                    {
                        "usage_id": f"legacy-use:{issue.issue_id}:{event.id}:0",
                        "issue_id": issue.issue_id,
                        "ts": float(event.ts),
                        "job_id": job_id,
                        "client_name": None,
                        "kind": issue.kind,
                        "status": "completed",
                        "answer_chars": None,
                        "metadata": {
                            "synthetic": True,
                            "source_event_id": int(event.id),
                            "source_event_type": str(event.type),
                        },
                    }
                )
        for row in synthesized_rows:
            job_id = str(row.get("job_id") or "").strip()
            if not job_id or job_id in seen_job_ids:
                continue
            seen_job_ids.add(job_id)
            out.append(row)
    return out


def _matches_query(issue: dict[str, Any], query_text: str) -> bool:
    if not query_text:
        return True
    haystack_text = " ".join(
        [
            str(issue.get("issue_id") or ""),
            str(issue.get("title") or ""),
            str(issue.get("symptom") or ""),
            str(issue.get("raw_error") or ""),
            str(issue.get("project") or ""),
            str(issue.get("kind") or ""),
            str(issue.get("family_label") or ""),
            " ".join(str(x) for x in issue.get("tags") or []),
        ]
    )
    haystack_tokens = _tokenize_text(haystack_text)
    query_tokens = _tokenize_text(query_text)
    if not query_tokens:
        return True
    if query_tokens.issubset(haystack_tokens):
        return True
    haystack_collapsed = _collapsed_text(haystack_text)
    query_collapsed = _collapsed_text(query_text)
    if query_collapsed and query_collapsed in haystack_collapsed:
        return True
    simple_query_tokens = [
        token for token in _TOKEN_SPLIT_RE.split(_normalize_text(query_text)) if token
    ]
    return bool(simple_query_tokens) and all(token in haystack_collapsed for token in simple_query_tokens)


def _job_record(conn: sqlite3.Connection, *, job_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not job_ids:
        return {}
    placeholders = ",".join("?" for _ in job_ids)
    rows = conn.execute(
        f"""
        SELECT job_id, kind, status, phase, created_at, updated_at,
               client_json, answer_chars, conversation_url
        FROM jobs
        WHERE job_id IN ({placeholders})
        """,
        tuple(sorted(job_ids)),
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        client_payload: dict[str, Any] = {}
        try:
            client_payload = json.loads(str(row["client_json"] or "{}"))
            if not isinstance(client_payload, dict):
                client_payload = {}
        except Exception:
            client_payload = {}
        client_name = (
            str(client_payload.get("name") or client_payload.get("project") or client_payload.get("client_name") or "").strip()
            or None
        )
        out[str(row["job_id"])] = {
            "job_id": str(row["job_id"]),
            "kind": (str(row["kind"]) if row["kind"] is not None else None),
            "status": (str(row["status"]) if row["status"] is not None else None),
            "phase": (str(row["phase"]) if row["phase"] is not None else None),
            "created_at": float(row["created_at"] or 0.0),
            "updated_at": float(row["updated_at"] or 0.0),
            "client_name": client_name,
            "answer_chars": (int(row["answer_chars"]) if row["answer_chars"] is not None else None),
            "conversation_url": (
                str(row["conversation_url"]).strip() if row["conversation_url"] is not None and str(row["conversation_url"]).strip() else None
            ),
        }
    return out


def _incident_records(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT incident_id, fingerprint_hash, signature, category, severity, status,
               created_at, updated_at, last_seen_at, count, job_ids_json, evidence_dir, repair_job_id
        FROM incidents
        ORDER BY updated_at DESC, incident_id DESC
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            job_ids = json.loads(str(row["job_ids_json"] or "[]"))
            if not isinstance(job_ids, list):
                job_ids = []
        except Exception:
            job_ids = []
        out.append(
            {
                "incident_id": str(row["incident_id"]),
                "fingerprint_hash": str(row["fingerprint_hash"]),
                "signature": str(row["signature"]),
                "category": (str(row["category"]) if row["category"] is not None else None),
                "severity": str(row["severity"]),
                "status": str(row["status"]),
                "created_at": float(row["created_at"]),
                "updated_at": float(row["updated_at"]),
                "last_seen_at": float(row["last_seen_at"]),
                "count": int(row["count"] or 0),
                "job_ids": [str(x).strip() for x in job_ids if str(x).strip()],
                "evidence_dir": (str(row["evidence_dir"]) if row["evidence_dir"] is not None else None),
                "repair_job_id": (str(row["repair_job_id"]) if row["repair_job_id"] is not None else None),
            }
        )
    return out


def _docs_root() -> Path:
    raw = str(os.environ.get("CHATGPTREST_DOCS_ROOT") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path("/vol1/1000/projects/ChatgptREST/docs")


def _first_doc_locator(path: Path, terms: list[str]) -> dict[str, Any] | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None
    lowered_terms = [str(term or "").strip().lower() for term in terms if str(term or "").strip()]
    if not lowered_terms:
        return None
    for line_no, line in enumerate(lines, start=1):
        lowered_line = line.lower()
        for term in lowered_terms:
            if term and term in lowered_line:
                excerpt = _short_text(line.strip(), max_chars=240)
                return {
                    "locator": f"L{line_no}",
                    "excerpt": excerpt,
                    "match_term": term,
                    "content_hash": hashlib.sha1(excerpt.encode("utf-8", errors="replace")).hexdigest(),
                }
    return None


def _doc_refs(issues: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    docs_root = _docs_root()
    if not docs_root.exists():
        return {}
    needles: dict[str, list[str]] = {}
    for issue in issues:
        issue_id = str(issue["issue_id"])
        family_id = str(issue.get("family_id") or "")
        title = str(issue.get("title") or "")
        tags = [str(x) for x in issue.get("tags") or [] if str(x).strip()]
        search_terms = [issue_id]
        if family_id:
            search_terms.append(family_id)
        family_label = str(issue.get("family_label") or "")
        if family_label:
            search_terms.append(family_label)
        if title:
            search_terms.append(title)
        search_terms.extend(tags[:3])
        needles[issue_id] = [x for x in search_terms if x]

    refs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    candidates = list(docs_root.rglob("*.md")) + list(docs_root.rglob("*.yaml"))
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for issue in issues:
            issue_id = str(issue["issue_id"])
            terms = needles.get(issue_id) or []
            if any(term and term in text for term in terms):
                locator = _first_doc_locator(path, terms)
                refs[issue_id].append(
                    {
                        "path": str(path.relative_to(docs_root.parent)),
                        "name": path.name,
                        "locator": (locator or {}).get("locator"),
                        "excerpt": (locator or {}).get("excerpt"),
                        "match_term": (locator or {}).get("match_term"),
                        "content_hash": (locator or {}).get("content_hash"),
                    }
                )
    return refs


def build_issue_graph_snapshot(
    conn: sqlite3.Connection,
    *,
    include_closed: bool = True,
    max_issues: int = 1000,
    include_docs: bool = True,
) -> dict[str, Any]:
    issue_status = None if include_closed else "open,in_progress,mitigated"
    issues, _, _ = client_issues.list_issues(
        conn,
        status=issue_status,
        limit=max(1, int(max_issues)),
    )
    issue_rows = [_issue_record(issue) for issue in issues]
    doc_refs = _doc_refs(issue_rows) if include_docs else {}

    verifications_by_issue: dict[str, list[dict[str, Any]]] = {}
    usage_by_issue: dict[str, list[dict[str, Any]]] = {}
    related_job_ids: set[str] = set()
    issue_events_by_issue: dict[str, list[client_issues.ClientIssueEventRecord]] = {}
    for issue in issues:
        issue_id = issue.issue_id
        events, _next = client_issues.list_issue_events(conn, issue_id=issue_id, after_id=0, limit=500)
        issue_events_by_issue[issue_id] = list(events)
        verifications = [_verification_record(row) for row in client_issues.list_issue_verifications(conn, issue_id=issue_id, limit=500)]
        usage = [_usage_record(row) for row in client_issues.list_issue_usage_evidence(conn, issue_id=issue_id, limit=500)]
        if not verifications:
            verifications = _synthesized_verifications(issue=issue, events=list(events))
        if not usage:
            usage = _synthesized_usage(issue=issue, events=list(events))
        verifications_by_issue[issue_id] = verifications
        usage_by_issue[issue_id] = usage
        if issue.latest_job_id:
            related_job_ids.add(issue.latest_job_id)
        for row in verifications:
            if row.get("job_id"):
                related_job_ids.add(str(row["job_id"]))
        for row in usage:
            if row.get("job_id"):
                related_job_ids.add(str(row["job_id"]))

        for event in events:
            payload = event.payload if isinstance(event.payload, dict) else {}
            for key in ("job_id", "linked_job_id"):
                if payload.get(key):
                    related_job_ids.add(str(payload[key]))
            if isinstance(payload.get("job_ids"), list):
                for raw in payload["job_ids"]:
                    if raw:
                        related_job_ids.add(str(raw))

    jobs_by_id = _job_record(conn, job_ids=related_job_ids)
    incidents = _incident_records(conn)
    incidents_by_issue: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for incident in incidents:
        incident_jobs = {str(job_id) for job_id in incident.get("job_ids") or [] if str(job_id).strip()}
        for issue in issue_rows:
            issue_id = str(issue["issue_id"])
            issue_jobs = {
                str(issue.get("latest_job_id") or ""),
                *[str(row.get("job_id") or "") for row in verifications_by_issue.get(issue_id) or []],
                *[str(row.get("job_id") or "") for row in usage_by_issue.get(issue_id) or []],
            }
            issue_jobs = {x for x in issue_jobs if x}
            if incident_jobs.intersection(issue_jobs):
                incidents_by_issue[issue_id].append(incident)

    family_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issue_rows:
        family_members[str(issue["family_id"])].append(issue)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_ids: set[str] = set()

    def add_node(node_id: str, kind: str, label: str, attrs: dict[str, Any]) -> None:
        if node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append({"id": node_id, "kind": kind, "label": label, "attrs": attrs})

    def add_edge(source: str, target: str, edge_type: str, attrs: dict[str, Any] | None = None) -> None:
        edges.append({"source": source, "target": target, "type": edge_type, "attrs": attrs or {}})

    for family_id, members in family_members.items():
        severity_counts = Counter(str(member.get("severity") or "") for member in members)
        add_node(
            f"family:{family_id}",
            "family",
            str(members[0].get("family_label") or family_id),
            {
                "family_id": family_id,
                "issue_ids": [member["issue_id"] for member in members],
                "issue_count": len(members),
                "severity_counts": dict(sorted(severity_counts.items())),
            },
        )

    for issue in issue_rows:
        issue_node = f"issue:{issue['issue_id']}"
        add_node(issue_node, "issue", issue["title"], issue)
        add_edge(issue_node, f"family:{issue['family_id']}", "belongs_to_family")

        for verification in verifications_by_issue.get(str(issue["issue_id"])) or []:
            verification_node = f"verification:{verification['verification_id']}"
            add_node(
                verification_node,
                "verification",
                f"{verification['verification_type']} ({verification['status']})",
                verification,
            )
            add_edge(issue_node, verification_node, "validated_by")
            if verification.get("job_id"):
                job_id = str(verification["job_id"])
                job = jobs_by_id.get(job_id) or {"job_id": job_id}
                add_node(f"job:{job_id}", "job", job_id, job)
                add_edge(verification_node, f"job:{job_id}", "uses_job")

        for usage in usage_by_issue.get(str(issue["issue_id"])) or []:
            usage_node = f"usage:{usage['usage_id']}"
            add_node(
                usage_node,
                "usage",
                f"{usage.get('client_name') or 'client'} -> {usage['job_id']}",
                usage,
            )
            add_edge(issue_node, usage_node, "proven_by_usage")
            job_id = str(usage["job_id"])
            job = jobs_by_id.get(job_id) or {"job_id": job_id}
            add_node(f"job:{job_id}", "job", job_id, job)
            add_edge(usage_node, f"job:{job_id}", "uses_job")

        if issue.get("latest_job_id"):
            job_id = str(issue["latest_job_id"])
            job = jobs_by_id.get(job_id) or {"job_id": job_id}
            add_node(f"job:{job_id}", "job", job_id, job)
            add_edge(issue_node, f"job:{job_id}", "latest_job")

        for incident in incidents_by_issue.get(str(issue["issue_id"])) or []:
            incident_id = str(incident["incident_id"])
            add_node(f"incident:{incident_id}", "incident", incident["signature"], incident)
            add_edge(issue_node, f"incident:{incident_id}", "linked_incident")

        for doc in doc_refs.get(str(issue["issue_id"])) or []:
            doc_id = f"doc:{doc['path']}"
            add_node(doc_id, "document", doc["name"], doc)
            add_edge(issue_node, doc_id, "documented_in")

    return {
        "generated_at": float(time.time()),
        "summary": {
            "issue_count": len(issue_rows),
            "family_count": len(family_members),
            "verification_count": sum(len(rows) for rows in verifications_by_issue.values()),
            "usage_evidence_count": sum(len(rows) for rows in usage_by_issue.values()),
            "job_count": len(jobs_by_id),
            "incident_count": len({incident["incident_id"] for rows in incidents_by_issue.values() for incident in rows}),
            "document_count": len({doc["path"] for rows in doc_refs.values() for doc in rows}),
        },
        "issues": issue_rows,
        "nodes": nodes,
        "edges": edges,
    }


def build_issue_graph_markdown(snapshot: dict[str, Any]) -> str:
    summary = dict(snapshot.get("summary") or {})
    issues = list(snapshot.get("issues") or [])
    lines = [
        "# Issue Knowledge Graph Snapshot",
        "",
        f"Generated at: `{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(snapshot.get('generated_at') or time.time())))}`",
        "",
        "## Summary",
        "",
        f"- issues: `{summary.get('issue_count', 0)}`",
        f"- families: `{summary.get('family_count', 0)}`",
        f"- verifications: `{summary.get('verification_count', 0)}`",
        f"- usage evidence: `{summary.get('usage_evidence_count', 0)}`",
        f"- jobs: `{summary.get('job_count', 0)}`",
        f"- incidents: `{summary.get('incident_count', 0)}`",
        "",
        "## Issues",
        "",
    ]
    if not issues:
        lines.append("- none")
    for issue in issues[:50]:
        lines.extend(
            [
                f"- `{issue['issue_id']}` [{issue['severity']}] `{issue['status']}` {issue['title']}",
                f"  family=`{issue['family_id']}` project=`{issue['project']}` kind=`{issue['kind'] or '-'}`",
                f"  latest_job=`{issue['latest_job_id'] or '-'}` artifacts=`{issue['latest_artifacts_path'] or '-'}`",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def query_issue_graph(
    snapshot: dict[str, Any],
    *,
    issue_id: str | None = None,
    family_id: str | None = None,
    q: str | None = None,
    status: str | None = None,
    include_closed: bool = True,
    limit: int = 20,
    neighbor_depth: int = 1,
) -> dict[str, Any]:
    issues = list(snapshot.get("issues") or [])
    query_text = _normalize_text(q)
    status_values = {
        _normalize_text(part)
        for part in str(status or "").split(",")
        if _normalize_text(part)
    }

    matches: list[dict[str, Any]] = []
    for issue in issues:
        if not include_closed and str(issue.get("status") or "").strip().lower() == "closed":
            continue
        if issue_id and str(issue.get("issue_id")) != str(issue_id):
            continue
        if family_id and str(issue.get("family_id")) != str(family_id):
            continue
        if status_values and _normalize_text(issue.get("status")) not in status_values:
            continue
        if query_text and not _matches_query(issue, query_text):
            continue
        matches.append(issue)
    matches = sorted(matches, key=lambda row: (-float(row.get("updated_at") or 0.0), str(row.get("issue_id") or "")))[: max(1, int(limit))]

    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    nodes_by_id = {str(node["id"]): node for node in snapshot.get("nodes") or []}
    edges = list(snapshot.get("edges") or [])
    for edge in edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        adjacency[source].append((target, edge))
        adjacency[target].append((source, edge))

    seed_ids = [f"issue:{row['issue_id']}" for row in matches]
    seen: set[str] = set()
    queue: deque[tuple[str, int]] = deque((seed, 0) for seed in seed_ids)
    while queue:
        node_id, depth = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)
        if depth >= max(0, int(neighbor_depth)):
            continue
        for neighbor_id, _edge in adjacency.get(node_id, []):
            if neighbor_id not in seen:
                queue.append((neighbor_id, depth + 1))

    result_edges = [
        edge
        for edge in edges
        if str(edge.get("source")) in seen and str(edge.get("target")) in seen
    ]
    result_nodes = [nodes_by_id[node_id] for node_id in sorted(seen) if node_id in nodes_by_id]
    return {
        "generated_at": float(snapshot.get("generated_at") or time.time()),
        "summary": {
            **dict(snapshot.get("summary") or {}),
            "match_count": len(matches),
            "result_node_count": len(result_nodes),
            "result_edge_count": len(result_edges),
        },
        "matches": matches,
        "nodes": result_nodes,
        "edges": result_edges,
    }
