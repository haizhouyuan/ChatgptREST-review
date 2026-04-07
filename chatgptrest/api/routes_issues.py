from __future__ import annotations

import os
import sqlite3
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from chatgptrest.api.schemas import (
    ClientIssueCanonicalObjectView,
    ClientIssueCanonicalProjectionView,
    ClientIssueCanonicalQueryRequest,
    ClientIssueCanonicalQueryResponse,
    ClientIssueEvidenceLinkRequest,
    ClientIssueEvent,
    ClientIssueEvents,
    ClientIssueGraphEdge,
    ClientIssueGraphNode,
    ClientIssueGraphQueryRequest,
    ClientIssueGraphQueryResponse,
    ClientIssuesList,
    ClientIssueUsageEvidenceList,
    ClientIssueUsageEvidenceRequest,
    ClientIssueUsageEvidenceView,
    ClientIssueReportRequest,
    ClientIssueReportView,
    ClientIssueStatusUpdateRequest,
    ClientIssueVerificationRequest,
    ClientIssueVerificationView,
    ClientIssueVerifications,
    ClientIssueView,
)
from chatgptrest.core import client_issues
from chatgptrest.core import issue_canonical
from chatgptrest.core import issue_graph
from chatgptrest.core.config import AppConfig
from chatgptrest.core.completion_contract import is_authoritative_answer_ready
from chatgptrest.core.db import connect
from chatgptrest.core.env import truthy_env as _truthy_env


def _issue_report_guard_enabled() -> bool:
    # Default on: avoid false-positive open issues for already-completed jobs.
    return _truthy_env("CHATGPTREST_ISSUE_REPORT_REQUIRE_ACTIVE_JOB", True)


def _issue_report_allow_resolved(req: ClientIssueReportRequest) -> bool:
    md = req.metadata if isinstance(req.metadata, dict) else {}
    for key in ("allow_resolved_job", "allow_completed_job", "force", "postmortem"):
        if bool(md.get(key)):
            return True
    tags = req.tags if isinstance(req.tags, list) else []
    tags_l = {str(x or "").strip().lower() for x in tags if str(x or "").strip()}
    return ("postmortem" in tags_l or "allow_resolved_job" in tags_l)


def _issue_report_candidate_job_ids(req: ClientIssueReportRequest) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def _add(v: object) -> None:
        s = str(v or "").strip()
        if not s or s in seen:
            return
        seen.add(s)
        out.append(s)

    _add(req.job_id)
    md = req.metadata if isinstance(req.metadata, dict) else {}
    _add(md.get("job_id"))
    _add(md.get("latest_job_id"))
    raw_ids = md.get("job_ids")
    if isinstance(raw_ids, (list, tuple, set)):
        for x in raw_ids:
            _add(x)
    return out


def _issue_view(issue: client_issues.ClientIssueRecord) -> ClientIssueView:
    return ClientIssueView(
        issue_id=issue.issue_id,
        fingerprint_hash=issue.fingerprint_hash,
        fingerprint_text=issue.fingerprint_text,
        project=issue.project,
        title=issue.title,
        kind=issue.kind,
        severity=issue.severity,
        status=issue.status,
        source=issue.source,
        symptom=issue.symptom,
        raw_error=issue.raw_error,
        tags=list(issue.tags or []),
        metadata=(dict(issue.metadata) if isinstance(issue.metadata, dict) else None),
        count=int(issue.count),
        latest_job_id=issue.latest_job_id,
        latest_conversation_url=issue.latest_conversation_url,
        latest_artifacts_path=issue.latest_artifacts_path,
        created_at=float(issue.created_at),
        updated_at=float(issue.updated_at),
        first_seen_at=float(issue.first_seen_at),
        last_seen_at=float(issue.last_seen_at),
        closed_at=(float(issue.closed_at) if issue.closed_at is not None else None),
    )


def _issue_report_view(
    issue: client_issues.ClientIssueRecord,
    *,
    created: bool,
    reopened: bool,
) -> ClientIssueReportView:
    base = _issue_view(issue).model_dump()
    return ClientIssueReportView(**base, created=bool(created), reopened=bool(reopened))


def _issue_event_view(event: client_issues.ClientIssueEventRecord) -> ClientIssueEvent:
    payload = event.payload if isinstance(event.payload, dict) else None
    return ClientIssueEvent(
        id=int(event.id),
        issue_id=str(event.issue_id),
        ts=float(event.ts),
        type=str(event.type),
        payload=payload,
    )


def _issue_verification_view(
    verification: client_issues.ClientIssueVerificationRecord,
) -> ClientIssueVerificationView:
    return ClientIssueVerificationView(
        verification_id=verification.verification_id,
        issue_id=verification.issue_id,
        ts=float(verification.ts),
        verification_type=verification.verification_type,
        status=verification.status,
        verifier=verification.verifier,
        note=verification.note,
        job_id=verification.job_id,
        conversation_url=verification.conversation_url,
        artifacts_path=verification.artifacts_path,
        metadata=(dict(verification.metadata) if isinstance(verification.metadata, dict) else None),
    )


def _issue_usage_view(
    usage: client_issues.ClientIssueUsageEvidenceRecord,
) -> ClientIssueUsageEvidenceView:
    return ClientIssueUsageEvidenceView(
        usage_id=usage.usage_id,
        issue_id=usage.issue_id,
        ts=float(usage.ts),
        job_id=usage.job_id,
        client_name=usage.client_name,
        kind=usage.kind,
        status=usage.status,
        answer_chars=usage.answer_chars,
        metadata=(dict(usage.metadata) if isinstance(usage.metadata, dict) else None),
    )


def _issue_graph_response(payload: dict[str, object]) -> ClientIssueGraphQueryResponse:
    return ClientIssueGraphQueryResponse(
        generated_at=float(payload.get("generated_at") or 0.0),
        summary=dict(payload.get("summary") or {}),
        matches=list(payload.get("matches") or []),
        nodes=[
            ClientIssueGraphNode(
                id=str(node.get("id")),
                kind=str(node.get("kind")),
                label=str(node.get("label")),
                attrs=dict(node.get("attrs") or {}),
            )
            for node in list(payload.get("nodes") or [])
            if isinstance(node, dict)
        ],
        edges=[
            ClientIssueGraphEdge(
                source=str(edge.get("source")),
                target=str(edge.get("target")),
                type=str(edge.get("type")),
                attrs=dict(edge.get("attrs") or {}),
            )
            for edge in list(payload.get("edges") or [])
            if isinstance(edge, dict)
        ],
    )


def _issue_canonical_response(payload: dict[str, object]) -> ClientIssueCanonicalQueryResponse:
    return ClientIssueCanonicalQueryResponse(
        generated_at=float(payload.get("generated_at") or 0.0),
        summary=dict(payload.get("summary") or {}),
        matches=list(payload.get("matches") or []),
        objects=[
            ClientIssueCanonicalObjectView(
                object_id=str(obj.get("object_id")),
                canonical_key=str(obj.get("canonical_key")),
                domain=str(obj.get("domain")),
                object_type=str(obj.get("object_type")),
                title=str(obj.get("title")),
                summary=(str(obj.get("summary")) if obj.get("summary") is not None else None),
                status=(str(obj.get("status")) if obj.get("status") is not None else None),
                authority_level=str(obj.get("authority_level")),
                source_ref=(str(obj.get("source_ref")) if obj.get("source_ref") is not None else None),
                source_repo=(str(obj.get("source_repo")) if obj.get("source_repo") is not None else None),
                source_path=(str(obj.get("source_path")) if obj.get("source_path") is not None else None),
                payload=dict(obj.get("payload") or {}),
                projections=[
                    ClientIssueCanonicalProjectionView(
                        projection_name=str(proj.get("projection_name")),
                        projection_state=str(proj.get("projection_state")),
                        projection_reason=str(proj.get("projection_reason")),
                        payload=dict(proj.get("payload") or {}),
                    )
                    for proj in list(obj.get("projections") or [])
                    if isinstance(proj, dict)
                ],
            )
            for obj in list(payload.get("objects") or [])
            if isinstance(obj, dict)
        ],
    )


def _load_job_result_payload(*, artifacts_dir: str | Path, job_id: str) -> dict[str, object]:
    result_path = Path(artifacts_dir) / "jobs" / str(job_id) / "result.json"
    try:
        parsed = json.loads(result_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _issue_report_job_is_clean_completion(*, cfg: AppConfig, row: sqlite3.Row) -> bool:
    status = str(row["status"] or "").strip().lower()
    has_error = bool(str(row["last_error_type"] or "").strip() or str(row["last_error"] or "").strip())
    if status != "completed" or has_error:
        return False
    job_like: dict[str, object] = {
        "job_id": str(row["job_id"] or "").strip(),
        "status": status,
        "answer_path": (str(row["answer_path"] or "").strip() or None),
    }
    result_payload = _load_job_result_payload(
        artifacts_dir=cfg.artifacts_dir,
        job_id=str(row["job_id"] or "").strip(),
    )
    if result_payload:
        job_like.update(result_payload)
    return is_authoritative_answer_ready(job_like)


def make_issues_router(cfg: AppConfig) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/issues/report", response_model=ClientIssueReportView)
    def issues_report(req: ClientIssueReportRequest) -> ClientIssueReportView:
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                candidate_job_ids = _issue_report_candidate_job_ids(req)
                if (
                    _issue_report_guard_enabled()
                    and candidate_job_ids
                    and str(req.source or "").strip().lower() != "worker_auto"
                    and (not _issue_report_allow_resolved(req))
                ):
                    job_ids = candidate_job_ids
                    placeholders = ",".join("?" for _ in job_ids)
                    rows = conn.execute(
                        f"""
                        SELECT job_id, status, answer_path, last_error_type, last_error
                        FROM jobs
                        WHERE job_id IN ({placeholders})
                        """,
                        tuple(job_ids),
                    ).fetchall()
                    if rows:
                        rows_by_job_id = {str(x["job_id"]): x for x in rows if x is not None and str(x["job_id"] or "").strip()}
                        # Block only when every referenced/known job is already a clean completion.
                        all_completed_success = True
                        missing = False
                        for jid in job_ids:
                            row = rows_by_job_id.get(jid)
                            if row is None:
                                missing = True
                                all_completed_success = False
                                continue
                            if not _issue_report_job_is_clean_completion(cfg=cfg, row=row):
                                all_completed_success = False
                        if all_completed_success and (not missing):
                            conn.rollback()
                            raise HTTPException(
                                status_code=409,
                                detail={
                                    "error": "IssueReportJobAlreadyCompleted",
                                    "job_id": (str(req.job_id) if req.job_id else None),
                                    "job_ids": list(job_ids),
                                    "job_status": "completed",
                                    "hint": (
                                        "Referenced job(s) already completed successfully; skip open issue report. "
                                        "Use issue evidence link or set metadata.allow_resolved_job=true for postmortem."
                                    ),
                                },
                            )
                report_job_id = (str(req.job_id).strip() if req.job_id else "")
                if not report_job_id and candidate_job_ids:
                    report_job_id = str(candidate_job_ids[-1]).strip()
                issue, created, info = client_issues.report_issue(
                    conn,
                    project=req.project,
                    title=req.title,
                    severity=req.severity,
                    kind=req.kind,
                    symptom=req.symptom,
                    raw_error=req.raw_error,
                    job_id=(report_job_id or None),
                    conversation_url=req.conversation_url,
                    artifacts_path=req.artifacts_path,
                    source=req.source,
                    tags=list(req.tags or []),
                    metadata=(dict(req.metadata) if isinstance(req.metadata, dict) else None),
                    fingerprint=req.fingerprint,
                )
                conn.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _issue_report_view(issue, created=bool(created), reopened=bool(info.get("reopened")))

    @router.get("/v1/issues", response_model=ClientIssuesList)
    def issues_list(
        project: str | None = None,
        kind: str | None = None,
        source: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        fingerprint_hash: str | None = None,
        fingerprint_text: str | None = None,
        since_ts: float | None = None,
        until_ts: float | None = None,
        before_ts: float | None = None,
        before_issue_id: str | None = None,
        limit: int = 200,
    ) -> ClientIssuesList:
        try:
            with connect(cfg.db_path) as conn:
                issues, next_before_ts, next_before_issue_id = client_issues.list_issues(
                    conn,
                    project=project,
                    kind=kind,
                    source=source,
                    status=status,
                    severity=severity,
                    fingerprint_hash=fingerprint_hash,
                    fingerprint_text=fingerprint_text,
                    since_ts=since_ts,
                    until_ts=until_ts,
                    before_ts=before_ts,
                    before_issue_id=before_issue_id,
                    limit=int(limit),
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return ClientIssuesList(
            next_before_ts=next_before_ts,
            next_before_issue_id=next_before_issue_id,
            issues=[_issue_view(x) for x in issues],
        )

    @router.post("/v1/issues/graph/query", response_model=ClientIssueGraphQueryResponse)
    def issues_graph_query(req: ClientIssueGraphQueryRequest) -> ClientIssueGraphQueryResponse:
        try:
            with connect(cfg.db_path) as conn:
                try:
                    payload = issue_canonical.query_issue_graph_preferred(
                        authoritative_conn=conn,
                        issue_id=req.issue_id,
                        family_id=req.family_id,
                        q=req.q,
                        status=req.status,
                        include_closed=bool(req.include_closed),
                        limit=int(req.limit),
                        neighbor_depth=int(req.neighbor_depth),
                    )
                except (issue_canonical.IssueCanonicalUnavailable, sqlite3.Error, OSError):
                    snapshot = issue_graph.build_issue_graph_snapshot(
                        conn,
                        include_closed=bool(req.include_closed),
                        max_issues=max(50, int(req.limit) * 20),
                        include_docs=True,
                    )
                    payload = issue_graph.query_issue_graph(
                        snapshot,
                        issue_id=req.issue_id,
                        family_id=req.family_id,
                        q=req.q,
                        status=req.status,
                        include_closed=bool(req.include_closed),
                        limit=int(req.limit),
                        neighbor_depth=int(req.neighbor_depth),
                    )
                    payload.setdefault("summary", {})
                    payload["summary"]["read_plane"] = "legacy_fallback"
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _issue_graph_response(payload)

    @router.post("/v1/issues/canonical/query", response_model=ClientIssueCanonicalQueryResponse)
    def issues_canonical_query(req: ClientIssueCanonicalQueryRequest) -> ClientIssueCanonicalQueryResponse:
        try:
            with connect(cfg.db_path) as conn:
                payload = issue_canonical.query_issue_canonical(
                    authoritative_conn=conn,
                    issue_id=req.issue_id,
                    q=req.q,
                    status=req.status,
                    limit=int(req.limit),
                    ensure_fresh=True,
                )
        except issue_canonical.IssueCanonicalUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _issue_canonical_response(payload)

    @router.get("/v1/issues/canonical/export", response_model=ClientIssueCanonicalQueryResponse)
    def issues_canonical_export(
        status: str | None = None,
        limit: int = 200,
    ) -> ClientIssueCanonicalQueryResponse:
        try:
            with connect(cfg.db_path) as conn:
                payload = issue_canonical.export_issue_canonical_snapshot(
                    authoritative_conn=conn,
                    status=status,
                    limit=int(limit),
                    ensure_fresh=True,
                )
        except issue_canonical.IssueCanonicalUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _issue_canonical_response(payload)

    @router.get("/v1/issues/graph/snapshot", response_model=ClientIssueGraphQueryResponse)
    def issues_graph_snapshot(
        include_closed: bool = True,
        limit: int = 200,
    ) -> ClientIssueGraphQueryResponse:
        with connect(cfg.db_path) as conn:
            try:
                snapshot = issue_canonical.export_issue_graph_snapshot(
                    authoritative_conn=conn,
                    include_closed=bool(include_closed),
                    max_issues=max(50, int(limit)),
                )
            except (issue_canonical.IssueCanonicalUnavailable, sqlite3.Error, OSError):
                snapshot = issue_graph.build_issue_graph_snapshot(
                    conn,
                    include_closed=bool(include_closed),
                    max_issues=max(50, int(limit)),
                    include_docs=True,
                )
                snapshot.setdefault("summary", {})
                snapshot["summary"]["read_plane"] = "legacy_fallback"
        payload = {
            "generated_at": snapshot.get("generated_at"),
            "summary": snapshot.get("summary") or {},
            "matches": list(snapshot.get("issues") or []),
            "nodes": list(snapshot.get("nodes") or []),
            "edges": list(snapshot.get("edges") or []),
        }
        return _issue_graph_response(payload)

    @router.get("/v1/issues/{issue_id}", response_model=ClientIssueView)
    def issues_get(issue_id: str) -> ClientIssueView:
        with connect(cfg.db_path) as conn:
            issue = client_issues.get_issue(conn, issue_id=issue_id)
        if issue is None:
            raise HTTPException(status_code=404, detail="issue not found")
        return _issue_view(issue)

    @router.post("/v1/issues/{issue_id}/status", response_model=ClientIssueView)
    def issues_update_status(issue_id: str, req: ClientIssueStatusUpdateRequest) -> ClientIssueView:
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                issue = client_issues.update_issue_status(
                    conn,
                    issue_id=issue_id,
                    status=req.status,
                    note=req.note,
                    actor=req.actor,
                    metadata=(dict(req.metadata) if isinstance(req.metadata, dict) else None),
                    linked_job_id=req.linked_job_id,
                )
                conn.commit()
        except KeyError:
            raise HTTPException(status_code=404, detail="issue not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _issue_view(issue)

    @router.post("/v1/issues/{issue_id}/verification", response_model=ClientIssueVerificationView)
    def issues_record_verification(
        issue_id: str,
        req: ClientIssueVerificationRequest,
    ) -> ClientIssueVerificationView:
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                verification = client_issues.record_issue_verification(
                    conn,
                    issue_id=issue_id,
                    verification_type=req.verification_type,
                    status=req.status,
                    verifier=req.verifier,
                    note=req.note,
                    job_id=req.job_id,
                    conversation_url=req.conversation_url,
                    artifacts_path=req.artifacts_path,
                    metadata=(dict(req.metadata) if isinstance(req.metadata, dict) else None),
                )
                conn.commit()
        except KeyError:
            raise HTTPException(status_code=404, detail="issue not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _issue_verification_view(verification)

    @router.get("/v1/issues/{issue_id}/verification", response_model=ClientIssueVerifications)
    def issues_list_verifications(issue_id: str, after_ts: float = 0.0, limit: int = 200) -> ClientIssueVerifications:
        with connect(cfg.db_path) as conn:
            issue = client_issues.get_issue(conn, issue_id=issue_id)
            if issue is None:
                raise HTTPException(status_code=404, detail="issue not found")
            verifications = client_issues.list_issue_verifications(
                conn,
                issue_id=issue_id,
                after_ts=after_ts,
                limit=int(limit),
            )
        return ClientIssueVerifications(
            issue_id=str(issue_id),
            verifications=[_issue_verification_view(row) for row in verifications],
        )

    @router.post("/v1/issues/{issue_id}/usage", response_model=ClientIssueUsageEvidenceView)
    def issues_record_usage(issue_id: str, req: ClientIssueUsageEvidenceRequest) -> ClientIssueUsageEvidenceView:
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                usage = client_issues.record_issue_usage_evidence(
                    conn,
                    issue_id=issue_id,
                    job_id=req.job_id,
                    client_name=req.client_name,
                    kind=req.kind,
                    status=req.status,
                    answer_chars=req.answer_chars,
                    metadata=(dict(req.metadata) if isinstance(req.metadata, dict) else None),
                )
                conn.commit()
        except KeyError:
            raise HTTPException(status_code=404, detail="issue not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _issue_usage_view(usage)

    @router.get("/v1/issues/{issue_id}/usage", response_model=ClientIssueUsageEvidenceList)
    def issues_list_usage(issue_id: str, after_ts: float = 0.0, limit: int = 200) -> ClientIssueUsageEvidenceList:
        with connect(cfg.db_path) as conn:
            issue = client_issues.get_issue(conn, issue_id=issue_id)
            if issue is None:
                raise HTTPException(status_code=404, detail="issue not found")
            usage_rows = client_issues.list_issue_usage_evidence(
                conn,
                issue_id=issue_id,
                after_ts=after_ts,
                limit=int(limit),
            )
        return ClientIssueUsageEvidenceList(
            issue_id=str(issue_id),
            usage=[_issue_usage_view(row) for row in usage_rows],
        )

    @router.post("/v1/issues/{issue_id}/evidence", response_model=ClientIssueView)
    def issues_link_evidence(issue_id: str, req: ClientIssueEvidenceLinkRequest) -> ClientIssueView:
        try:
            with connect(cfg.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                issue = client_issues.link_issue_evidence(
                    conn,
                    issue_id=issue_id,
                    job_id=req.job_id,
                    conversation_url=req.conversation_url,
                    artifacts_path=req.artifacts_path,
                    note=req.note,
                    source=req.source,
                    metadata=(dict(req.metadata) if isinstance(req.metadata, dict) else None),
                )
                conn.commit()
        except KeyError:
            raise HTTPException(status_code=404, detail="issue not found")
        return _issue_view(issue)

    @router.get("/v1/issues/{issue_id}/events", response_model=ClientIssueEvents)
    def issues_events(issue_id: str, after_id: int = 0, limit: int = 200) -> ClientIssueEvents:
        with connect(cfg.db_path) as conn:
            issue = client_issues.get_issue(conn, issue_id=issue_id)
            if issue is None:
                raise HTTPException(status_code=404, detail="issue not found")
            events, next_after = client_issues.list_issue_events(
                conn,
                issue_id=issue_id,
                after_id=int(after_id),
                limit=int(limit),
            )
        return ClientIssueEvents(
            issue_id=str(issue_id),
            after_id=max(0, int(after_id)),
            next_after_id=int(next_after),
            events=[_issue_event_view(x) for x in events],
        )

    return router
