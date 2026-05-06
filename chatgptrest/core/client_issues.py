from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any


CLIENT_ISSUE_STATUS_OPEN = "open"
CLIENT_ISSUE_STATUS_IN_PROGRESS = "in_progress"
CLIENT_ISSUE_STATUS_MITIGATED = "mitigated"
CLIENT_ISSUE_STATUS_CLOSED = "closed"
CLIENT_ISSUE_STATUSES = {
    CLIENT_ISSUE_STATUS_OPEN,
    CLIENT_ISSUE_STATUS_IN_PROGRESS,
    CLIENT_ISSUE_STATUS_MITIGATED,
    CLIENT_ISSUE_STATUS_CLOSED,
}

_SEVERITY_VALUES = {"P0", "P1", "P2", "P3"}
_WS_RE = re.compile(r"\s+")


def _now() -> float:
    return time.time()


def _normalize_ws(s: str) -> str:
    return _WS_RE.sub(" ", str(s or "").strip())


def _normalize_text_for_fingerprint(s: str, *, max_chars: int = 2000) -> str:
    out = _normalize_ws(str(s or "")).lower()
    if len(out) > max_chars:
        return out[:max_chars]
    return out


def _normalize_status(value: str | None) -> str:
    s = _normalize_ws(str(value or "")).lower()
    if s not in CLIENT_ISSUE_STATUSES:
        raise ValueError(f"invalid issue status: {value!r}")
    return s


def _normalize_severity(value: str | None) -> str:
    raw = _normalize_ws(str(value or "")).upper()
    if not raw:
        return "P2"
    if raw in _SEVERITY_VALUES:
        return raw
    raise ValueError(f"invalid severity: {value!r}; expected one of P0/P1/P2/P3")


def _normalize_project(value: str | None) -> str:
    project = _normalize_ws(str(value or ""))
    if not project:
        raise ValueError("project is required")
    if len(project) > 200:
        project = project[:200]
    return project


def _normalize_title(value: str | None) -> str:
    title = _normalize_ws(str(value or ""))
    if not title:
        raise ValueError("title is required")
    if len(title) > 400:
        title = title[:400]
    return title


def _normalize_optional_text(value: str | None, *, max_chars: int) -> str | None:
    s = _normalize_ws(str(value or ""))
    if not s:
        return None
    if len(s) > max_chars:
        return s[:max_chars]
    return s


def _normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in tags:
        tag = _normalize_ws(str(item or "")).lower()
        if not tag:
            continue
        if len(tag) > 64:
            tag = tag[:64]
        if tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_loads_dict(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        obj = json.loads(str(raw))
    except Exception:
        return {}
    if isinstance(obj, dict):
        return obj
    return {}


def _json_loads_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        obj = json.loads(str(raw))
    except Exception:
        return []
    if not isinstance(obj, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in obj:
        tag = _normalize_ws(str(item or "")).lower()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out


def _issue_fingerprint_text(
    *,
    project: str,
    title: str,
    kind: str | None,
    symptom: str | None,
    raw_error: str | None,
    source: str | None,
    explicit_fingerprint: str | None,
) -> str:
    explicit = _normalize_optional_text(explicit_fingerprint, max_chars=2000)
    if explicit:
        return f"manual:{_normalize_text_for_fingerprint(explicit, max_chars=2000)}"

    payload = {
        "project": _normalize_text_for_fingerprint(project, max_chars=200),
        "title": _normalize_text_for_fingerprint(title, max_chars=400),
        "kind": _normalize_text_for_fingerprint(kind or "", max_chars=200),
        "symptom": _normalize_text_for_fingerprint(symptom or "", max_chars=1000),
        "raw_error": _normalize_text_for_fingerprint(raw_error or "", max_chars=1000),
        "source": _normalize_text_for_fingerprint(source or "", max_chars=120),
    }
    return _json_dumps(payload)


def _fingerprint_hash(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8", errors="replace")).hexdigest()


def _new_issue_id() -> str:
    return f"iss_{uuid.uuid4().hex}"


def _parse_json_payload(raw: Any | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        obj = json.loads(str(raw))
    except Exception:
        return {"_raw": str(raw)}
    if isinstance(obj, dict):
        return obj
    return {"_raw": obj}


@dataclass(frozen=True)
class ClientIssueRecord:
    issue_id: str
    fingerprint_hash: str
    fingerprint_text: str
    project: str
    title: str
    kind: str | None
    severity: str
    status: str
    source: str | None
    symptom: str | None
    raw_error: str | None
    tags: list[str]
    metadata: dict[str, Any] | None
    count: int
    latest_job_id: str | None
    latest_conversation_url: str | None
    latest_artifacts_path: str | None
    created_at: float
    updated_at: float
    first_seen_at: float
    last_seen_at: float
    closed_at: float | None


@dataclass(frozen=True)
class ClientIssueEventRecord:
    id: int
    issue_id: str
    ts: float
    type: str
    payload: dict[str, Any] | None


@dataclass(frozen=True)
class ClientIssueVerificationRecord:
    verification_id: str
    issue_id: str
    ts: float
    verification_type: str
    status: str
    verifier: str | None
    note: str | None
    job_id: str | None
    conversation_url: str | None
    artifacts_path: str | None
    metadata: dict[str, Any] | None


@dataclass(frozen=True)
class ClientIssueUsageEvidenceRecord:
    usage_id: str
    issue_id: str
    ts: float
    job_id: str
    client_name: str | None
    kind: str | None
    status: str
    answer_chars: int | None
    metadata: dict[str, Any] | None


def _row_to_issue(row: Any) -> ClientIssueRecord:
    return ClientIssueRecord(
        issue_id=str(row["issue_id"]),
        fingerprint_hash=str(row["fingerprint_hash"]),
        fingerprint_text=str(row["fingerprint_text"]),
        project=str(row["project"]),
        title=str(row["title"]),
        kind=_normalize_optional_text((str(row["kind"]) if row["kind"] is not None else None), max_chars=200),
        severity=str(row["severity"]),
        status=str(row["status"]),
        source=_normalize_optional_text((str(row["source"]) if row["source"] is not None else None), max_chars=120),
        symptom=_normalize_optional_text((str(row["symptom"]) if row["symptom"] is not None else None), max_chars=4000),
        raw_error=_normalize_optional_text((str(row["raw_error"]) if row["raw_error"] is not None else None), max_chars=8000),
        tags=_json_loads_list(str(row["tags_json"]) if row["tags_json"] is not None else None),
        metadata=_json_loads_dict(str(row["metadata_json"]) if row["metadata_json"] is not None else None) or None,
        count=int(row["count"] or 0),
        latest_job_id=_normalize_optional_text((str(row["latest_job_id"]) if row["latest_job_id"] is not None else None), max_chars=128),
        latest_conversation_url=_normalize_optional_text(
            (str(row["latest_conversation_url"]) if row["latest_conversation_url"] is not None else None),
            max_chars=2000,
        ),
        latest_artifacts_path=_normalize_optional_text(
            (str(row["latest_artifacts_path"]) if row["latest_artifacts_path"] is not None else None),
            max_chars=2000,
        ),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        first_seen_at=float(row["first_seen_at"]),
        last_seen_at=float(row["last_seen_at"]),
        closed_at=(float(row["closed_at"]) if row["closed_at"] is not None else None),
    )


def _row_to_issue_event(row: Any) -> ClientIssueEventRecord:
    return ClientIssueEventRecord(
        id=int(row["id"]),
        issue_id=str(row["issue_id"]),
        ts=float(row["ts"]),
        type=str(row["type"]),
        payload=_parse_json_payload(row["payload_json"]),
    )


def _row_to_issue_verification(row: Any) -> ClientIssueVerificationRecord:
    return ClientIssueVerificationRecord(
        verification_id=str(row["verification_id"]),
        issue_id=str(row["issue_id"]),
        ts=float(row["ts"]),
        verification_type=str(row["verification_type"]),
        status=str(row["status"]),
        verifier=_normalize_optional_text((str(row["verifier"]) if row["verifier"] is not None else None), max_chars=200),
        note=_normalize_optional_text((str(row["note"]) if row["note"] is not None else None), max_chars=2000),
        job_id=_normalize_optional_text((str(row["job_id"]) if row["job_id"] is not None else None), max_chars=128),
        conversation_url=_normalize_optional_text(
            (str(row["conversation_url"]) if row["conversation_url"] is not None else None),
            max_chars=2000,
        ),
        artifacts_path=_normalize_optional_text(
            (str(row["artifacts_path"]) if row["artifacts_path"] is not None else None),
            max_chars=2000,
        ),
        metadata=_json_loads_dict(str(row["metadata_json"]) if row["metadata_json"] is not None else None) or None,
    )


def _row_to_usage_evidence(row: Any) -> ClientIssueUsageEvidenceRecord:
    return ClientIssueUsageEvidenceRecord(
        usage_id=str(row["usage_id"]),
        issue_id=str(row["issue_id"]),
        ts=float(row["ts"]),
        job_id=str(row["job_id"]),
        client_name=_normalize_optional_text(
            (str(row["client_name"]) if row["client_name"] is not None else None),
            max_chars=200,
        ),
        kind=_normalize_optional_text((str(row["kind"]) if row["kind"] is not None else None), max_chars=200),
        status=str(row["status"] or "completed"),
        answer_chars=(int(row["answer_chars"]) if row["answer_chars"] is not None else None),
        metadata=_json_loads_dict(str(row["metadata_json"]) if row["metadata_json"] is not None else None) or None,
    )


def _insert_issue_event(
    conn: Any,
    *,
    issue_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    now: float | None = None,
) -> None:
    conn.execute(
        "INSERT INTO client_issue_events(issue_id, ts, type, payload_json) VALUES (?,?,?,?)",
        (
            str(issue_id),
            float(_now() if now is None else now),
            str(event_type),
            (_json_dumps(payload) if payload is not None else None),
        ),
    )


def _new_verification_id() -> str:
    return f"ver_{uuid.uuid4().hex}"


def _new_usage_id() -> str:
    return f"use_{uuid.uuid4().hex}"


def get_issue(conn: Any, *, issue_id: str) -> ClientIssueRecord | None:
    row = conn.execute("SELECT * FROM client_issues WHERE issue_id = ?", (str(issue_id),)).fetchone()
    if row is None:
        return None
    return _row_to_issue(row)


def _attachment_contract_issue_metadata(
    conn: Any,
    *,
    job_id: str | None,
) -> dict[str, Any]:
    job_id_n = _normalize_optional_text(job_id, max_chars=128)
    if not job_id_n:
        return {}
    try:
        row = conn.execute(
            """
            SELECT payload_json
            FROM job_events
            WHERE job_id = ? AND type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (job_id_n, "attachment_contract_missing_detected"),
        ).fetchone()
    except Exception:
        return {}
    if row is None:
        return {}
    payload = _parse_json_payload(row["payload_json"])
    if not isinstance(payload, dict):
        return {}
    metadata: dict[str, Any] = {}
    family_id = _normalize_optional_text(payload.get("family_id"), max_chars=120)
    family_label = _normalize_optional_text(payload.get("family_label"), max_chars=200)
    if family_id:
        metadata["family_id"] = family_id
    if family_label:
        metadata["family_label"] = family_label
    if payload:
        metadata["attachment_contract"] = payload
    return metadata


def report_issue(
    conn: Any,
    *,
    project: str,
    title: str,
    severity: str | None = None,
    kind: str | None = None,
    symptom: str | None = None,
    raw_error: str | None = None,
    job_id: str | None = None,
    conversation_url: str | None = None,
    artifacts_path: str | None = None,
    source: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    fingerprint: str | None = None,
    now: float | None = None,
) -> tuple[ClientIssueRecord, bool, dict[str, Any]]:
    now_ts = float(_now() if now is None else now)
    project_n = _normalize_project(project)
    title_n = _normalize_title(title)
    severity_n = _normalize_severity(severity)
    kind_n = _normalize_optional_text(kind, max_chars=200)
    symptom_n = _normalize_optional_text(symptom, max_chars=4000)
    raw_error_n = _normalize_optional_text(raw_error, max_chars=8000)
    job_id_n = _normalize_optional_text(job_id, max_chars=128)
    conversation_url_n = _normalize_optional_text(conversation_url, max_chars=2000)
    artifacts_path_n = _normalize_optional_text(artifacts_path, max_chars=2000)
    source_n = _normalize_optional_text(source, max_chars=120)
    tags_n = _normalize_tags(tags)
    metadata_n = dict(metadata or {}) if isinstance(metadata, dict) else {}
    if not str(metadata_n.get("family_id") or "").strip():
        metadata_n.update(
            {
                key: value
                for key, value in _attachment_contract_issue_metadata(
                    conn,
                    job_id=job_id,
                ).items()
                if key not in metadata_n or metadata_n.get(key) in (None, "", {}, [], ())
            }
        )

    fingerprint_text = _issue_fingerprint_text(
        project=project_n,
        title=title_n,
        kind=kind_n,
        symptom=symptom_n,
        raw_error=raw_error_n,
        source=source_n,
        explicit_fingerprint=fingerprint,
    )
    fingerprint_hash = _fingerprint_hash(fingerprint_text)

    row = conn.execute(
        """
        SELECT * FROM client_issues
        WHERE fingerprint_hash = ?
          AND status != ?
        ORDER BY updated_at DESC, issue_id DESC
        LIMIT 1
        """,
        (fingerprint_hash, CLIENT_ISSUE_STATUS_CLOSED),
    ).fetchone()

    if row is None:
        issue_id = _new_issue_id()
        conn.execute(
            """
            INSERT INTO client_issues(
              issue_id, fingerprint_hash, fingerprint_text, project, title, kind, severity, status,
              source, symptom, raw_error, tags_json, metadata_json,
              created_at, updated_at, first_seen_at, last_seen_at, closed_at,
              count, latest_job_id, latest_conversation_url, latest_artifacts_path
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                issue_id,
                fingerprint_hash,
                fingerprint_text,
                project_n,
                title_n,
                kind_n,
                severity_n,
                CLIENT_ISSUE_STATUS_OPEN,
                source_n,
                symptom_n,
                raw_error_n,
                _json_dumps(tags_n),
                (_json_dumps(metadata_n) if metadata_n else None),
                now_ts,
                now_ts,
                now_ts,
                now_ts,
                None,
                1,
                job_id_n,
                conversation_url_n,
                artifacts_path_n,
            ),
        )
        _insert_issue_event(
            conn,
            issue_id=issue_id,
            event_type="issue_reported",
            payload={
                "created": True,
                "project": project_n,
                "title": title_n,
                "severity": severity_n,
                "kind": kind_n,
                "fingerprint_hash": fingerprint_hash,
                "job_id": job_id_n,
                "conversation_url": conversation_url_n,
                "artifacts_path": artifacts_path_n,
            },
            now=now_ts,
        )
        created = get_issue(conn, issue_id=issue_id)
        assert created is not None
        return created, True, {"created": True, "reopened": False}

    current = _row_to_issue(row)
    merged_tags = _normalize_tags([*(current.tags or []), *tags_n])
    merged_metadata = dict(current.metadata or {})
    merged_metadata.update(metadata_n)

    next_status = str(current.status)
    reopened = False
    if next_status == CLIENT_ISSUE_STATUS_MITIGATED:
        next_status = CLIENT_ISSUE_STATUS_OPEN
        reopened = True

    conn.execute(
        """
        UPDATE client_issues
        SET project = ?,
            title = ?,
            kind = COALESCE(?, kind),
            severity = ?,
            status = ?,
            source = COALESCE(?, source),
            symptom = COALESCE(?, symptom),
            raw_error = COALESCE(?, raw_error),
            tags_json = ?,
            metadata_json = ?,
            updated_at = ?,
            last_seen_at = ?,
            closed_at = ?,
            count = count + 1,
            latest_job_id = COALESCE(?, latest_job_id),
            latest_conversation_url = COALESCE(?, latest_conversation_url),
            latest_artifacts_path = COALESCE(?, latest_artifacts_path)
        WHERE issue_id = ?
        """,
        (
            project_n,
            title_n,
            kind_n,
            severity_n,
            next_status,
            source_n,
            symptom_n,
            raw_error_n,
            _json_dumps(merged_tags),
            (_json_dumps(merged_metadata) if merged_metadata else None),
            now_ts,
            now_ts,
            (None if next_status != CLIENT_ISSUE_STATUS_CLOSED else now_ts),
            job_id_n,
            conversation_url_n,
            artifacts_path_n,
            current.issue_id,
        ),
    )
    _insert_issue_event(
        conn,
        issue_id=current.issue_id,
        event_type="issue_reported",
        payload={
            "created": False,
            "reopened": reopened,
            "project": project_n,
            "title": title_n,
            "severity": severity_n,
            "kind": kind_n,
            "fingerprint_hash": fingerprint_hash,
            "job_id": job_id_n,
            "conversation_url": conversation_url_n,
            "artifacts_path": artifacts_path_n,
        },
        now=now_ts,
    )
    updated = get_issue(conn, issue_id=current.issue_id)
    assert updated is not None
    return updated, False, {"created": False, "reopened": reopened}


def update_issue_status(
    conn: Any,
    *,
    issue_id: str,
    status: str,
    note: str | None = None,
    actor: str | None = None,
    metadata: dict[str, Any] | None = None,
    linked_job_id: str | None = None,
    now: float | None = None,
) -> ClientIssueRecord:
    now_ts = float(_now() if now is None else now)
    target_status = _normalize_status(status)
    issue = get_issue(conn, issue_id=issue_id)
    if issue is None:
        raise KeyError(f"issue not found: {issue_id}")

    note_n = _normalize_optional_text(note, max_chars=2000)
    actor_n = _normalize_optional_text(actor, max_chars=200)
    linked_job_id_n = _normalize_optional_text(linked_job_id, max_chars=128)
    metadata_n = dict(metadata or {}) if isinstance(metadata, dict) else {}

    closed_at = now_ts if target_status == CLIENT_ISSUE_STATUS_CLOSED else None
    conn.execute(
        """
        UPDATE client_issues
        SET status = ?,
            updated_at = ?,
            closed_at = ?,
            latest_job_id = COALESCE(?, latest_job_id)
        WHERE issue_id = ?
        """,
        (target_status, now_ts, closed_at, linked_job_id_n, str(issue_id)),
    )
    _insert_issue_event(
        conn,
        issue_id=str(issue_id),
        event_type="issue_status_updated",
        payload={
            "from": issue.status,
            "to": target_status,
            "note": note_n,
            "actor": actor_n,
            "linked_job_id": linked_job_id_n,
            "metadata": metadata_n or None,
        },
        now=now_ts,
    )
    updated = get_issue(conn, issue_id=issue_id)
    assert updated is not None

    if target_status == CLIENT_ISSUE_STATUS_MITIGATED:
        verification_payload = metadata_n.get("verification") if isinstance(metadata_n.get("verification"), dict) else {}
        verification_type = _normalize_optional_text(
            verification_payload.get("type") or metadata_n.get("verification_type"),
            max_chars=64,
        ) or "status_transition"
        verification_status = _normalize_optional_text(
            verification_payload.get("status") or metadata_n.get("verification_status"),
            max_chars=32,
        ) or "passed"
        record_issue_verification(
            conn,
            issue_id=issue_id,
            verification_type=verification_type,
            status=verification_status,
            verifier=(
                verification_payload.get("verifier")
                or verification_payload.get("actor")
                or actor_n
            ),
            note=(verification_payload.get("note") if verification_payload else None) or note_n,
            job_id=(verification_payload.get("job_id") if verification_payload else None) or linked_job_id_n or issue.latest_job_id,
            conversation_url=(
                verification_payload.get("conversation_url")
                if verification_payload
                else None
            ) or issue.latest_conversation_url,
            artifacts_path=(
                verification_payload.get("artifacts_path")
                if verification_payload
                else None
            ) or issue.latest_artifacts_path,
            metadata=(verification_payload.get("metadata") if verification_payload else None) or metadata_n or None,
            now=now_ts,
        )

    qualifying_successes = metadata_n.get("qualifying_successes")
    qualifying_success_job_ids = metadata_n.get("qualifying_success_job_ids")
    if target_status == CLIENT_ISSUE_STATUS_CLOSED:
        success_rows: list[dict[str, Any]] = []
        if isinstance(qualifying_successes, list):
            for raw in qualifying_successes:
                if isinstance(raw, dict):
                    success_rows.append(dict(raw))
        elif isinstance(qualifying_success_job_ids, list):
            for raw in qualifying_success_job_ids:
                if raw is None:
                    continue
                success_rows.append({"job_id": str(raw)})
        for success in success_rows:
            record_issue_usage_evidence(
                conn,
                issue_id=issue_id,
                job_id=str(success.get("job_id") or ""),
                client_name=(success.get("client_name") if isinstance(success, dict) else None),
                kind=(success.get("kind") if isinstance(success, dict) else None) or issue.kind,
                status=(success.get("status") if isinstance(success, dict) else None) or "completed",
                answer_chars=(
                    int(success["answer_chars"])
                    if isinstance(success, dict) and success.get("answer_chars") is not None
                    else None
                ),
                metadata=(success.get("metadata") if isinstance(success, dict) else None),
                now=(
                    float(success["created_at"])
                    if isinstance(success, dict) and success.get("created_at") is not None
                    else now_ts
                ),
            )

    # ── Sink resolution knowledge to EvoMap when issue is closed ─────────
    if target_status == CLIENT_ISSUE_STATUS_CLOSED and note_n:
        try:
            from chatgptrest.evomap.knowledge.db import KnowledgeDB
            from chatgptrest.evomap.knowledge.schema import Atom, AtomType, AtomStatus
            kb = KnowledgeDB()
            kb.connect()
            atom = Atom(
                atom_type=AtomType.QA.value,
                question=f"Issue: {issue.title}",
                answer=(
                    f"Root cause / fix: {note_n}\n"
                    f"Symptom: {issue.symptom or 'N/A'}\n"
                    f"Error: {(issue.raw_error or 'N/A')[:500]}\n"
                    f"Occurrences: {issue.count}\n"
                    f"Issue ID: {issue.issue_id}"
                ),
                canonical_question=f"issue resolution: {issue.title}",
                applicability=_json_dumps({
                    "project": issue.project,
                    "kind": issue.kind or "general",
                    "tags": [*(issue.tags or []), "issue_resolution", "auto_sunk"],
                }),
                status=AtomStatus.CANDIDATE.value,
                confidence=0.8,
                source_quality=0.7,
            )
            atom.compute_hash()
            if not kb.atom_exists_by_hash(atom.hash):
                kb.put_atom(atom)
                kb.commit()
            kb.close()
        except Exception:
            import logging
            logging.getLogger("chatgptrest.core.client_issues").debug(
                "EvoMap sink failed for issue %s", issue_id, exc_info=True,
            )

    return updated


def link_issue_evidence(
    conn: Any,
    *,
    issue_id: str,
    job_id: str | None = None,
    conversation_url: str | None = None,
    artifacts_path: str | None = None,
    note: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
    now: float | None = None,
) -> ClientIssueRecord:
    now_ts = float(_now() if now is None else now)
    issue = get_issue(conn, issue_id=issue_id)
    if issue is None:
        raise KeyError(f"issue not found: {issue_id}")

    job_id_n = _normalize_optional_text(job_id, max_chars=128)
    conversation_url_n = _normalize_optional_text(conversation_url, max_chars=2000)
    artifacts_path_n = _normalize_optional_text(artifacts_path, max_chars=2000)
    note_n = _normalize_optional_text(note, max_chars=2000)
    source_n = _normalize_optional_text(source, max_chars=120)
    metadata_n = dict(metadata or {}) if isinstance(metadata, dict) else {}

    conn.execute(
        """
        UPDATE client_issues
        SET updated_at = ?,
            last_seen_at = ?,
            source = COALESCE(?, source),
            latest_job_id = COALESCE(?, latest_job_id),
            latest_conversation_url = COALESCE(?, latest_conversation_url),
            latest_artifacts_path = COALESCE(?, latest_artifacts_path)
        WHERE issue_id = ?
        """,
        (
            now_ts,
            now_ts,
            source_n,
            job_id_n,
            conversation_url_n,
            artifacts_path_n,
            str(issue_id),
        ),
    )

    _insert_issue_event(
        conn,
        issue_id=str(issue_id),
        event_type="issue_evidence_linked",
        payload={
            "job_id": job_id_n,
            "conversation_url": conversation_url_n,
            "artifacts_path": artifacts_path_n,
            "note": note_n,
            "source": source_n,
            "metadata": metadata_n or None,
        },
        now=now_ts,
    )
    updated = get_issue(conn, issue_id=issue_id)
    assert updated is not None
    return updated


def record_issue_verification(
    conn: Any,
    *,
    issue_id: str,
    verification_type: str,
    status: str = "passed",
    verifier: str | None = None,
    note: str | None = None,
    job_id: str | None = None,
    conversation_url: str | None = None,
    artifacts_path: str | None = None,
    metadata: dict[str, Any] | None = None,
    now: float | None = None,
) -> ClientIssueVerificationRecord:
    issue = get_issue(conn, issue_id=issue_id)
    if issue is None:
        raise KeyError(f"issue not found: {issue_id}")
    now_ts = float(_now() if now is None else now)
    verification_type_n = _normalize_optional_text(verification_type, max_chars=64)
    if not verification_type_n:
        raise ValueError("verification_type is required")
    status_n = _normalize_optional_text(status, max_chars=32) or "passed"
    verifier_n = _normalize_optional_text(verifier, max_chars=200)
    note_n = _normalize_optional_text(note, max_chars=2000)
    job_id_n = _normalize_optional_text(job_id, max_chars=128)
    conversation_url_n = _normalize_optional_text(conversation_url, max_chars=2000)
    artifacts_path_n = _normalize_optional_text(artifacts_path, max_chars=2000)
    metadata_n = dict(metadata or {}) if isinstance(metadata, dict) else {}
    verification_id = _new_verification_id()
    conn.execute(
        """
        INSERT INTO client_issue_verifications(
          verification_id, issue_id, ts, verification_type, status, verifier,
          note, job_id, conversation_url, artifacts_path, metadata_json
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            verification_id,
            str(issue_id),
            now_ts,
            verification_type_n,
            status_n,
            verifier_n,
            note_n,
            job_id_n,
            conversation_url_n,
            artifacts_path_n,
            (_json_dumps(metadata_n) if metadata_n else None),
        ),
    )
    _insert_issue_event(
        conn,
        issue_id=str(issue_id),
        event_type="issue_verification_recorded",
        payload={
            "verification_id": verification_id,
            "verification_type": verification_type_n,
            "status": status_n,
            "verifier": verifier_n,
            "job_id": job_id_n,
            "conversation_url": conversation_url_n,
            "artifacts_path": artifacts_path_n,
            "note": note_n,
            "metadata": metadata_n or None,
        },
        now=now_ts,
    )
    row = conn.execute(
        "SELECT * FROM client_issue_verifications WHERE verification_id = ?",
        (verification_id,),
    ).fetchone()
    assert row is not None
    return _row_to_issue_verification(row)


def _job_usage_context(conn: Any, *, job_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT kind, status, client_json, answer_chars, conversation_url
        FROM jobs
        WHERE job_id = ?
        """,
        (str(job_id),),
    ).fetchone()
    if row is None:
        return {}
    payload = _json_loads_dict(str(row["client_json"]) if row["client_json"] is not None else None)
    client_name = _normalize_optional_text(
        payload.get("name") or payload.get("project") or payload.get("client_name"),
        max_chars=200,
    )
    return {
        "kind": _normalize_optional_text((str(row["kind"]) if row["kind"] is not None else None), max_chars=200),
        "status": _normalize_optional_text((str(row["status"]) if row["status"] is not None else None), max_chars=32),
        "client_name": client_name,
        "answer_chars": (int(row["answer_chars"]) if row["answer_chars"] is not None else None),
        "conversation_url": _normalize_optional_text(
            (str(row["conversation_url"]) if row["conversation_url"] is not None else None),
            max_chars=2000,
        ),
    }


def record_issue_usage_evidence(
    conn: Any,
    *,
    issue_id: str,
    job_id: str,
    client_name: str | None = None,
    kind: str | None = None,
    status: str = "completed",
    answer_chars: int | None = None,
    metadata: dict[str, Any] | None = None,
    now: float | None = None,
) -> ClientIssueUsageEvidenceRecord:
    issue = get_issue(conn, issue_id=issue_id)
    if issue is None:
        raise KeyError(f"issue not found: {issue_id}")
    job_id_n = _normalize_optional_text(job_id, max_chars=128)
    if not job_id_n:
        raise ValueError("job_id is required")
    existing = conn.execute(
        """
        SELECT *
        FROM client_issue_usage_evidence
        WHERE issue_id = ? AND job_id = ?
        LIMIT 1
        """,
        (str(issue_id), job_id_n),
    ).fetchone()
    if existing is not None:
        return _row_to_usage_evidence(existing)

    now_ts = float(_now() if now is None else now)
    metadata_n = dict(metadata or {}) if isinstance(metadata, dict) else {}
    job_ctx = _job_usage_context(conn, job_id=job_id_n)
    client_name_n = _normalize_optional_text(client_name, max_chars=200) or _normalize_optional_text(
        job_ctx.get("client_name"),
        max_chars=200,
    )
    kind_n = _normalize_optional_text(kind, max_chars=200) or _normalize_optional_text(job_ctx.get("kind"), max_chars=200) or issue.kind
    status_n = _normalize_optional_text(status, max_chars=32) or _normalize_optional_text(job_ctx.get("status"), max_chars=32) or "completed"
    answer_chars_n = answer_chars if answer_chars is not None else job_ctx.get("answer_chars")
    usage_id = _new_usage_id()
    conn.execute(
        """
        INSERT INTO client_issue_usage_evidence(
          usage_id, issue_id, ts, job_id, client_name, kind, status, answer_chars, metadata_json
        )
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            usage_id,
            str(issue_id),
            now_ts,
            job_id_n,
            client_name_n,
            kind_n,
            status_n,
            (int(answer_chars_n) if answer_chars_n is not None else None),
            (_json_dumps(metadata_n) if metadata_n else None),
        ),
    )
    _insert_issue_event(
        conn,
        issue_id=str(issue_id),
        event_type="issue_usage_evidence_recorded",
        payload={
            "usage_id": usage_id,
            "job_id": job_id_n,
            "client_name": client_name_n,
            "kind": kind_n,
            "status": status_n,
            "answer_chars": answer_chars_n,
            "metadata": metadata_n or None,
        },
        now=now_ts,
    )
    row = conn.execute(
        "SELECT * FROM client_issue_usage_evidence WHERE usage_id = ?",
        (usage_id,),
    ).fetchone()
    assert row is not None
    return _row_to_usage_evidence(row)


def list_issues(
    conn: Any,
    *,
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
) -> tuple[list[ClientIssueRecord], float | None, str | None]:
    clauses: list[str] = []
    params: list[Any] = []
    if project and _normalize_ws(project):
        clauses.append("LOWER(project) = LOWER(?)")
        params.append(_normalize_ws(project))

    if kind and _normalize_ws(kind):
        clauses.append("LOWER(kind) = LOWER(?)")
        params.append(_normalize_ws(kind))

    if source and _normalize_ws(source):
        clauses.append("LOWER(source) = LOWER(?)")
        params.append(_normalize_ws(source))

    status_values: list[str] = []
    if status and _normalize_ws(status):
        for part in str(status).split(","):
            s = _normalize_ws(part).lower()
            if not s:
                continue
            if s not in CLIENT_ISSUE_STATUSES:
                raise ValueError(f"invalid issue status filter: {s}")
            status_values.append(s)
    if status_values:
        placeholders = ",".join(["?"] * len(status_values))
        clauses.append(f"LOWER(status) IN ({placeholders})")
        params.extend(status_values)

    if severity and _normalize_ws(severity):
        sev = _normalize_severity(severity)
        clauses.append("UPPER(severity) = ?")
        params.append(sev)

    if fingerprint_hash and _normalize_ws(fingerprint_hash):
        fh = _normalize_ws(fingerprint_hash).lower()
        clauses.append("fingerprint_hash = ?")
        params.append(fh)

    if fingerprint_text and _normalize_ws(fingerprint_text):
        ft = _normalize_ws(fingerprint_text).lower()
        clauses.append("LOWER(fingerprint_text) LIKE ?")
        params.append(f"%{ft}%")

    if since_ts is not None:
        clauses.append("updated_at >= ?")
        params.append(float(since_ts))

    if until_ts is not None:
        clauses.append("updated_at <= ?")
        params.append(float(until_ts))

    if before_ts is not None:
        if before_issue_id and _normalize_ws(before_issue_id):
            clauses.append("(updated_at < ? OR (updated_at = ? AND issue_id < ?))")
            params.extend([float(before_ts), float(before_ts), _normalize_ws(before_issue_id)])
        else:
            clauses.append("updated_at < ?")
            params.append(float(before_ts))

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    lim = max(1, min(1000, int(limit)))
    rows = conn.execute(
        f"""
        SELECT *
        FROM client_issues
        {where_sql}
        ORDER BY updated_at DESC, issue_id DESC
        LIMIT ?
        """,
        (*params, lim),
    ).fetchall()

    out = [_row_to_issue(r) for r in rows]
    if not out:
        return out, None, None
    last = out[-1]
    return out, float(last.updated_at), str(last.issue_id)


def list_issue_events(
    conn: Any,
    *,
    issue_id: str,
    after_id: int = 0,
    limit: int = 200,
) -> tuple[list[ClientIssueEventRecord], int]:
    aid = max(0, int(after_id))
    lim = max(1, min(5000, int(limit)))
    rows = conn.execute(
        """
        SELECT id, issue_id, ts, type, payload_json
        FROM client_issue_events
        WHERE issue_id = ?
          AND id > ?
        ORDER BY id ASC
        LIMIT ?
        """,
        (str(issue_id), aid, lim),
    ).fetchall()
    events = [_row_to_issue_event(r) for r in rows]
    next_after = int(events[-1].id) if events else aid
    return events, next_after


def list_issue_verifications(
    conn: Any,
    *,
    issue_id: str,
    after_ts: float = 0.0,
    limit: int = 200,
) -> list[ClientIssueVerificationRecord]:
    rows = conn.execute(
        """
        SELECT *
        FROM client_issue_verifications
        WHERE issue_id = ?
          AND ts >= ?
        ORDER BY ts DESC, verification_id DESC
        LIMIT ?
        """,
        (str(issue_id), float(after_ts), max(1, min(5000, int(limit)))),
    ).fetchall()
    return [_row_to_issue_verification(row) for row in rows]


def list_issue_usage_evidence(
    conn: Any,
    *,
    issue_id: str,
    after_ts: float = 0.0,
    limit: int = 200,
) -> list[ClientIssueUsageEvidenceRecord]:
    rows = conn.execute(
        """
        SELECT *
        FROM client_issue_usage_evidence
        WHERE issue_id = ?
          AND ts >= ?
        ORDER BY ts DESC, usage_id DESC
        LIMIT ?
        """,
        (str(issue_id), float(after_ts), max(1, min(5000, int(limit)))),
    ).fetchall()
    return [_row_to_usage_evidence(row) for row in rows]
