from __future__ import annotations

from collections import Counter, defaultdict, deque
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from chatgptrest.core import client_issues

REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CANONICAL_CANDIDATES = (
    REPO_ROOT / "state" / "knowledge_v2" / "canonical.sqlite3",
    REPO_ROOT / "state" / "knowledge_v2.sqlite3",
)
_ISSUE_DOMAIN = "issue_domain"
_ALLOWED_PROJECTIONS = ("graph", "ledger_ref")
_CANONICAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS canonical_objects (
  object_id TEXT PRIMARY KEY,
  canonical_key TEXT NOT NULL,
  domain TEXT NOT NULL,
  object_type TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT,
  authority_level TEXT NOT NULL,
  ingest_priority TEXT NOT NULL,
  ingest_action TEXT NOT NULL,
  disposition TEXT NOT NULL,
  disposition_reason TEXT NOT NULL,
  projection_hint TEXT NOT NULL,
  quality_signal TEXT NOT NULL,
  evidence_count INTEGER NOT NULL DEFAULT 0,
  source_repo TEXT,
  source_path TEXT,
  source_ref TEXT,
  source_locator TEXT,
  semantic_key TEXT,
  status TEXT,
  promotion_state TEXT,
  verification_state TEXT,
  freshness_ts TEXT,
  created_at TEXT,
  updated_at TEXT,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_canonical_objects_domain_key
  ON canonical_objects(domain, canonical_key);
CREATE INDEX IF NOT EXISTS idx_canonical_objects_domain_type
  ON canonical_objects(domain, object_type);

CREATE TABLE IF NOT EXISTS object_sources (
  object_id TEXT NOT NULL,
  candidate_id TEXT NOT NULL UNIQUE,
  source_db TEXT NOT NULL,
  source_table TEXT NOT NULL,
  source_pk TEXT NOT NULL,
  authority_level TEXT NOT NULL,
  ingest_priority TEXT NOT NULL,
  ingest_action TEXT NOT NULL,
  quality_signal TEXT NOT NULL,
  evidence_count INTEGER NOT NULL DEFAULT 0,
  payload_json TEXT NOT NULL,
  PRIMARY KEY(object_id, candidate_id)
);
CREATE INDEX IF NOT EXISTS idx_object_sources_object_id
  ON object_sources(object_id);

CREATE TABLE IF NOT EXISTS projection_targets (
  object_id TEXT NOT NULL,
  projection_name TEXT NOT NULL,
  projection_state TEXT NOT NULL,
  projection_reason TEXT NOT NULL,
  PRIMARY KEY(object_id, projection_name)
);
CREATE INDEX IF NOT EXISTS idx_projection_targets_object_id
  ON projection_targets(object_id);

CREATE TABLE IF NOT EXISTS canonical_relations (
  relation_id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  edge_type TEXT NOT NULL,
  from_object_id TEXT NOT NULL,
  to_object_id TEXT NOT NULL,
  source_path TEXT,
  confidence REAL,
  status TEXT,
  evidence_refs_json TEXT,
  attrs_json TEXT,
  extractor_version TEXT
);
CREATE INDEX IF NOT EXISTS idx_canonical_relations_domain_from
  ON canonical_relations(domain, from_object_id);
CREATE INDEX IF NOT EXISTS idx_canonical_relations_domain_to
  ON canonical_relations(domain, to_object_id);

CREATE TABLE IF NOT EXISTS canonical_meta (
  domain TEXT NOT NULL,
  meta_key TEXT NOT NULL,
  meta_value TEXT,
  PRIMARY KEY(domain, meta_key)
);
"""


class IssueCanonicalUnavailable(RuntimeError):
    """Raised when the canonical plane is not configured or unreadable."""


def _expand(raw: str) -> str:
    return os.path.expanduser(raw.strip())


def _is_readable_sqlite(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _canonical_write_candidates(raw: str = "") -> list[Path]:
    candidates: list[Path] = []
    if raw.strip():
        candidates.append(Path(_expand(raw)))
    env_path = os.environ.get("CHATGPTREST_CANONICAL_DB_PATH", "").strip()
    if env_path:
        candidates.append(Path(_expand(env_path)))
    candidates.extend(_DEFAULT_CANONICAL_CANDIDATES)
    seen: set[str] = set()
    out: list[Path] = []
    for candidate in candidates:
        resolved = str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(candidate)
    return out


def resolve_issue_canonical_db_path(raw: str = "") -> str | None:
    for candidate in _canonical_write_candidates(raw):
        if _is_readable_sqlite(candidate):
            return str(candidate)
    return None


def _connect_read_only(path: str) -> sqlite3.Connection:
    resolved = Path(path).expanduser().resolve()
    conn = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_rw(path: str) -> sqlite3.Connection:
    resolved = Path(path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _parse_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _placeholders(size: int) -> str:
    return ",".join("?" for _ in range(max(1, int(size))))


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_CANONICAL_SCHEMA)


def _meta_get(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT meta_value FROM canonical_meta WHERE domain = ? AND meta_key = ?",
        (_ISSUE_DOMAIN, str(key)),
    ).fetchone()
    if row is None:
        return None
    return str(row["meta_value"]) if row["meta_value"] is not None else None


def _meta_set(conn: sqlite3.Connection, key: str, value: str | None) -> None:
    conn.execute(
        """
        INSERT INTO canonical_meta(domain, meta_key, meta_value)
        VALUES (?,?,?)
        ON CONFLICT(domain, meta_key) DO UPDATE SET meta_value = excluded.meta_value
        """,
        (_ISSUE_DOMAIN, str(key), value),
    )


def _query_issue_rows(
    conn: sqlite3.Connection,
    *,
    issue_id: str | None,
    q: str | None,
    status: str | None,
    limit: int,
) -> list[sqlite3.Row]:
    clauses = [
        "co.domain = ?",
        "EXISTS (SELECT 1 FROM projection_targets pt WHERE pt.object_id = co.object_id AND pt.projection_name = 'graph')",
        "EXISTS (SELECT 1 FROM projection_targets pt WHERE pt.object_id = co.object_id AND pt.projection_name = 'ledger_ref')",
    ]
    params: list[Any] = [_ISSUE_DOMAIN]
    normalized_issue_id = str(issue_id or "").strip()
    if normalized_issue_id:
        object_id = normalized_issue_id if normalized_issue_id.startswith("issue:") else f"issue:{normalized_issue_id}"
        clauses.append("(co.canonical_key = ? OR co.object_id = ?)")
        params.extend([normalized_issue_id, object_id])
    normalized_status = str(status or "").strip().lower()
    if normalized_status:
        clauses.append("LOWER(COALESCE(co.status, '')) = ?")
        params.append(normalized_status)
    normalized_q = str(q or "").strip().lower()
    if normalized_q:
        clauses.append(
            "LOWER(COALESCE(co.canonical_key, '') || ' ' || COALESCE(co.title, '') || ' ' || COALESCE(co.summary, '') || ' ' || COALESCE(co.payload_json, '')) LIKE ?"
        )
        params.append(f"%{normalized_q}%")
    sql = f"""
        SELECT
          co.object_id,
          co.canonical_key,
          co.domain,
          co.object_type,
          co.title,
          co.summary,
          co.authority_level,
          co.status,
          co.source_ref,
          co.source_repo,
          co.source_path,
          co.payload_json
        FROM canonical_objects co
        WHERE {' AND '.join(clauses)}
        ORDER BY COALESCE(co.updated_at, co.created_at, '') DESC, co.object_id DESC
        LIMIT ?
    """
    params.append(max(1, min(int(limit), 200)))
    return list(conn.execute(sql, tuple(params)).fetchall())


def _query_issue_object_rows(
    conn: sqlite3.Connection,
    *,
    issue_id: str | None,
    family_id: str | None = None,
    q: str | None,
    status: str | None,
    include_closed: bool,
    limit: int,
) -> list[sqlite3.Row]:
    clauses = [
        "co.domain = ?",
        "LOWER(COALESCE(co.object_type, '')) = 'issue'",
        "EXISTS (SELECT 1 FROM projection_targets pt WHERE pt.object_id = co.object_id AND pt.projection_name = 'graph')",
        "EXISTS (SELECT 1 FROM projection_targets pt WHERE pt.object_id = co.object_id AND pt.projection_name = 'ledger_ref')",
    ]
    params: list[Any] = [_ISSUE_DOMAIN]
    normalized_issue_id = str(issue_id or "").strip()
    if normalized_issue_id:
        object_id = normalized_issue_id if normalized_issue_id.startswith("issue:") else f"issue:{normalized_issue_id}"
        clauses.append("(co.canonical_key = ? OR co.object_id = ?)")
        params.extend([normalized_issue_id, object_id])
    normalized_status = str(status or "").strip().lower()
    if normalized_status:
        status_values = [part.strip().lower() for part in normalized_status.split(",") if part.strip()]
        clauses.append(f"LOWER(COALESCE(co.status, '')) IN ({_placeholders(len(status_values))})")
        params.extend(status_values)
    elif not include_closed:
        clauses.append("LOWER(COALESCE(co.status, '')) != 'closed'")
    normalized_q = str(q or "").strip().lower()
    if normalized_q:
        clauses.append(
            "LOWER(COALESCE(co.canonical_key, '') || ' ' || COALESCE(co.title, '') || ' ' || COALESCE(co.summary, '') || ' ' || COALESCE(co.payload_json, '')) LIKE ?"
        )
        params.append(f"%{normalized_q}%")
    rows = list(
        conn.execute(
            f"""
            SELECT
              co.object_id,
              co.canonical_key,
              co.domain,
              co.object_type,
              co.title,
              co.summary,
              co.authority_level,
              co.status,
              co.source_ref,
              co.source_repo,
              co.source_path,
              co.payload_json
            FROM canonical_objects co
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(co.updated_at, co.created_at, '') DESC, co.object_id DESC
            LIMIT ?
            """,
            (*params, max(1, min(int(limit), 500))),
        ).fetchall()
    )
    normalized_family_id = str(family_id or "").strip()
    if not normalized_family_id:
        return rows
    family_matches: list[sqlite3.Row] = []
    for row in rows:
        payload = _parse_json(row["payload_json"])
        if str(payload.get("family_id") or "").strip() == normalized_family_id:
            family_matches.append(row)
    if family_matches:
        return family_matches
    fallback_rows = list(
        conn.execute(
            """
            SELECT
              co.object_id,
              co.canonical_key,
              co.domain,
              co.object_type,
              co.title,
              co.summary,
              co.authority_level,
              co.status,
              co.source_ref,
              co.source_repo,
              co.source_path,
              co.payload_json
            FROM canonical_objects co
            WHERE co.domain = ?
              AND LOWER(COALESCE(co.object_type, '')) = 'issue'
            ORDER BY COALESCE(co.updated_at, co.created_at, '') DESC, co.object_id DESC
            LIMIT ?
            """,
            (_ISSUE_DOMAIN, max(1, min(int(limit) * 20, 5000))),
        ).fetchall()
    )
    return [
        row
        for row in fallback_rows
        if str(_parse_json(row["payload_json"]).get("family_id") or "").strip() == normalized_family_id
    ][: max(1, min(int(limit), 500))]


def _read_object_sources(conn: sqlite3.Connection, object_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not object_ids:
        return {}
    rows = conn.execute(
        f"""
        SELECT object_id, source_db, source_table, source_pk,
               authority_level, ingest_priority, ingest_action,
               quality_signal, payload_json
        FROM object_sources
        WHERE object_id IN ({_placeholders(len(object_ids))})
        ORDER BY object_id ASC, CASE authority_level
            WHEN 'authoritative' THEN 0
            WHEN 'runtime' THEN 1
            ELSE 9
          END ASC, candidate_id ASC
        """,
        tuple(object_ids),
    ).fetchall()
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row["object_id"]), []).append(
            {
                "source_db": str(row["source_db"]),
                "source_table": str(row["source_table"]),
                "source_pk": str(row["source_pk"]),
                "authority_level": str(row["authority_level"]),
                "ingest_priority": str(row["ingest_priority"]),
                "ingest_action": str(row["ingest_action"]),
                "quality_signal": str(row["quality_signal"]),
                "payload": _parse_json(row["payload_json"]),
            }
        )
    return out


def _read_projection_targets(
    conn: sqlite3.Connection,
    object_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if not object_ids:
        return {}
    rows = conn.execute(
        f"""
        SELECT object_id, projection_name, projection_state, projection_reason
        FROM projection_targets
        WHERE object_id IN ({_placeholders(len(object_ids))})
          AND projection_name IN ({_placeholders(len(_ALLOWED_PROJECTIONS))})
        ORDER BY object_id ASC, projection_name ASC
        """,
        tuple(object_ids) + _ALLOWED_PROJECTIONS,
    ).fetchall()
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row["object_id"]), []).append(
            {
                "projection_name": str(row["projection_name"]),
                "projection_state": str(row["projection_state"]),
                "projection_reason": str(row["projection_reason"]),
            }
        )
    return out


def _read_relation_stats(
    conn: sqlite3.Connection,
    object_ids: list[str],
) -> tuple[dict[str, int], dict[str, list[str]]]:
    if not object_ids:
        return {}, {}
    rows = conn.execute(
        f"""
        SELECT from_object_id, to_object_id, edge_type
        FROM canonical_relations
        WHERE domain = ?
          AND (from_object_id IN ({_placeholders(len(object_ids))})
               OR to_object_id IN ({_placeholders(len(object_ids))}))
        """,
        (_ISSUE_DOMAIN, *object_ids, *object_ids),
    ).fetchall()
    relation_counts: dict[str, int] = {}
    relation_types: dict[str, set[str]] = {}
    for row in rows:
        from_object_id = str(row["from_object_id"])
        to_object_id = str(row["to_object_id"])
        edge_type = str(row["edge_type"])
        for object_id in (from_object_id, to_object_id):
            if object_id not in object_ids:
                continue
            relation_counts[object_id] = relation_counts.get(object_id, 0) + 1
            relation_types.setdefault(object_id, set()).add(edge_type)
    return relation_counts, {
        object_id: sorted(edge_types) for object_id, edge_types in relation_types.items()
    }


def _graph_kind(object_type: str) -> str:
    normalized = str(object_type or "").strip().lower()
    if normalized == "usageevidence":
        return "usage"
    if normalized == "docevidence":
        return "document_evidence"
    return normalized


def _build_object_view(
    row: sqlite3.Row,
    *,
    sources_by_object: dict[str, list[dict[str, Any]]],
    projections_by_object: dict[str, list[dict[str, Any]]],
    relation_counts: dict[str, int],
    relation_types: dict[str, list[str]],
) -> dict[str, Any]:
    object_id = str(row["object_id"])
    payload = _parse_json(row["payload_json"])
    source_rows = list(sources_by_object.get(object_id) or [])
    authoritative_source = source_rows[0] if source_rows else {}
    projection_views: list[dict[str, Any]] = []
    for projection in projections_by_object.get(object_id) or []:
        projection_name = str(projection["projection_name"])
        projection_payload: dict[str, Any]
        if projection_name == "ledger_ref":
            projection_payload = {
                "source_db": authoritative_source.get("source_db"),
                "source_table": authoritative_source.get("source_table"),
                "source_pk": authoritative_source.get("source_pk"),
                "authority_level": authoritative_source.get("authority_level"),
                "ingest_priority": authoritative_source.get("ingest_priority"),
                "ingest_action": authoritative_source.get("ingest_action"),
                "quality_signal": authoritative_source.get("quality_signal"),
            }
        else:
            projection_payload = {
                "node_id": object_id,
                "kind": _graph_kind(str(row["object_type"])),
                "label": str(row["title"]),
                "attrs": {
                    "canonical_key": str(row["canonical_key"]),
                    "status": (str(row["status"]) if row["status"] is not None else None),
                    "project": payload.get("project"),
                    "kind": payload.get("kind"),
                    "severity": payload.get("severity"),
                    "latest_job_id": payload.get("latest_job_id"),
                },
                "relation_count": int(relation_counts.get(object_id, 0)),
                "relation_types": list(relation_types.get(object_id) or []),
                "derived": True,
            }
        projection_views.append(
            {
                "projection_name": projection_name,
                "projection_state": str(projection["projection_state"]),
                "projection_reason": str(projection["projection_reason"]),
                "payload": projection_payload,
            }
        )
    return {
        "object_id": object_id,
        "canonical_key": str(row["canonical_key"]),
        "domain": str(row["domain"]),
        "object_type": str(row["object_type"]),
        "title": str(row["title"]),
        "summary": (str(row["summary"]) if row["summary"] is not None else None),
        "status": (str(row["status"]) if row["status"] is not None else None),
        "authority_level": str(row["authority_level"]),
        "source_ref": (str(row["source_ref"]) if row["source_ref"] is not None else None),
        "source_repo": (str(row["source_repo"]) if row["source_repo"] is not None else None),
        "source_path": (str(row["source_path"]) if row["source_path"] is not None else None),
        "payload": payload,
        "projections": projection_views,
    }


def _build_response(rows: list[sqlite3.Row], conn: sqlite3.Connection) -> dict[str, Any]:
    object_ids = [str(row["object_id"]) for row in rows]
    sources_by_object = _read_object_sources(conn, object_ids)
    projections_by_object = _read_projection_targets(conn, object_ids)
    relation_counts, relation_types = _read_relation_stats(conn, object_ids)
    objects = [
        _build_object_view(
            row,
            sources_by_object=sources_by_object,
            projections_by_object=projections_by_object,
            relation_counts=relation_counts,
            relation_types=relation_types,
        )
        for row in rows
    ]
    projection_counts: dict[str, int] = {}
    for obj in objects:
        for projection in obj["projections"]:
            name = str(projection["projection_name"])
            projection_counts[name] = projection_counts.get(name, 0) + 1
    matches = [
        {
            "issue_id": obj["canonical_key"],
            "object_id": obj["object_id"],
            "title": obj["title"],
            "status": obj["status"],
            "projection_names": [str(proj["projection_name"]) for proj in obj["projections"]],
        }
        for obj in objects
    ]
    return {
        "generated_at": time.time(),
        "summary": {
            "domain": _ISSUE_DOMAIN,
            "object_count": len(objects),
            "match_count": len(matches),
            "projection_counts": dict(sorted(projection_counts.items())),
        },
        "matches": matches,
        "objects": objects,
    }


def _canonical_write_path(raw: str = "") -> str:
    candidates = _canonical_write_candidates(raw)
    if not candidates:
        raise IssueCanonicalUnavailable("canonical issue plane not configured")
    return str(candidates[0].expanduser())


def _authoritative_db_path(conn: sqlite3.Connection) -> str:
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        if str(row[1]) == "main" and row[2]:
            return str(row[2])
    return str(REPO_ROOT / "state" / "jobdb.sqlite3")


def _ts_text(value: Any | None) -> str | None:
    if value is None:
        return None
    return str(float(value))


def _relation_id(edge_type: str, from_object_id: str, to_object_id: str) -> str:
    raw = f"{edge_type}|{from_object_id}|{to_object_id}"
    return f"rel_{hashlib.sha1(raw.encode('utf-8', errors='replace')).hexdigest()}"


def _sync_source_watermark(authoritative_conn: sqlite3.Connection) -> str:
    row = authoritative_conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM client_issue_events"
    ).fetchone()
    return str(int(row[0] or 0))


def _issue_status_scope(include_closed: bool) -> str | None:
    return None if include_closed else "open,in_progress,mitigated"


def _list_all_issues(
    authoritative_conn: sqlite3.Connection,
    *,
    include_closed: bool,
) -> list[client_issues.ClientIssueRecord]:
    out: list[client_issues.ClientIssueRecord] = []
    before_ts: float | None = None
    before_issue_id: str | None = None
    seen_issue_ids: set[str] = set()
    while True:
        issues, next_before_ts, next_before_issue_id = client_issues.list_issues(
            authoritative_conn,
            status=_issue_status_scope(include_closed),
            before_ts=before_ts,
            before_issue_id=before_issue_id,
            limit=1000,
        )
        if not issues:
            break
        batch_new = 0
        for issue in issues:
            if issue.issue_id in seen_issue_ids:
                continue
            seen_issue_ids.add(issue.issue_id)
            out.append(issue)
            batch_new += 1
        if batch_new == 0:
            break
        if next_before_ts is None or not next_before_issue_id:
            break
        before_ts = float(next_before_ts)
        before_issue_id = str(next_before_issue_id)
    return out


def _coverage_snapshot(
    authoritative_conn: sqlite3.Connection,
    canonical_conn: sqlite3.Connection,
    *,
    include_closed: bool,
) -> dict[str, Any]:
    authoritative_issue_ids = [
        issue.issue_id for issue in _list_all_issues(authoritative_conn, include_closed=include_closed)
    ]
    canonical_issue_ids = [
        str(row["canonical_key"])
        for row in canonical_conn.execute(
            """
            SELECT canonical_key
            FROM canonical_objects
            WHERE domain = ?
              AND object_type = 'Issue'
            ORDER BY canonical_key ASC
            """,
            (_ISSUE_DOMAIN,),
        ).fetchall()
    ]
    canonical_issue_set = set(canonical_issue_ids)
    missing_issue_ids = [issue_id for issue_id in authoritative_issue_ids if issue_id not in canonical_issue_set]
    return {
        "authoritative_issue_count": len(authoritative_issue_ids),
        "canonical_issue_count": len(canonical_issue_ids),
        "coverage_gap_count": len(missing_issue_ids),
        "missing_issue_ids": missing_issue_ids,
    }


def _read_coverage_meta(conn: sqlite3.Connection) -> dict[str, Any]:
    authoritative_issue_count = int(_meta_get(conn, "authoritative_issue_count") or "0")
    canonical_issue_count = int(_meta_get(conn, "canonical_issue_count") or "0")
    coverage_gap_count = int(_meta_get(conn, "coverage_gap_count") or "0")
    missing_issue_ids_raw = _meta_get(conn, "missing_issue_ids") or "[]"
    try:
        missing_issue_ids = json.loads(missing_issue_ids_raw)
        if not isinstance(missing_issue_ids, list):
            missing_issue_ids = []
    except Exception:
        missing_issue_ids = []
    return {
        "authoritative_issue_count": authoritative_issue_count,
        "canonical_issue_count": canonical_issue_count,
        "coverage_gap_count": coverage_gap_count,
        "missing_issue_ids": [str(x) for x in missing_issue_ids if str(x).strip()],
    }


def _evidence_provenance(
    row: dict[str, Any],
    *,
    object_type: str,
) -> dict[str, Any]:
    metadata = dict(row.get("metadata") or {})
    synthetic = bool(metadata.get("synthetic"))
    source_event_id = metadata.get("source_event_id")
    source_event_type = metadata.get("source_event_type")
    if synthetic and source_event_id is not None:
        return {
            "synthetic": True,
            "authority_level": "derived",
            "source_table": "client_issue_events",
            "source_pk": str(int(source_event_id)),
            "source_ref": f"{source_event_type or 'issue_status_updated'}:{int(source_event_id)}",
            "source_path": "state/jobdb.sqlite3",
            "derived_from": {
                "event_id": int(source_event_id),
                "event_type": str(source_event_type or "issue_status_updated"),
                "object_type": object_type,
            },
        }
    if object_type == "Verification":
        source_pk = str(row.get("verification_id") or "")
        source_table = "client_issue_verifications"
    else:
        source_pk = str(row.get("usage_id") or "")
        source_table = "client_issue_usage_evidence"
    return {
        "synthetic": False,
        "authority_level": "authoritative",
        "source_table": source_table,
        "source_pk": source_pk,
        "source_ref": source_pk,
        "source_path": "state/jobdb.sqlite3",
        "derived_from": None,
    }


def _build_issue_domain_projection(
    authoritative_conn: sqlite3.Connection,
    *,
    include_closed: bool,
    include_docs: bool,
) -> tuple[list[dict[str, Any]], list[tuple[Any, ...]], list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    from chatgptrest.core import issue_graph as legacy_graph

    issues = _list_all_issues(authoritative_conn, include_closed=include_closed)
    issue_rows = [legacy_graph._issue_record(issue) for issue in issues]
    doc_refs = legacy_graph._doc_refs(issue_rows) if include_docs else {}

    verifications_by_issue: dict[str, list[dict[str, Any]]] = {}
    usage_by_issue: dict[str, list[dict[str, Any]]] = {}
    related_job_ids: set[str] = set()
    for issue in issues:
        issue_id = issue.issue_id
        events, _next = client_issues.list_issue_events(authoritative_conn, issue_id=issue_id, after_id=0, limit=500)
        verifications = [
            legacy_graph._verification_record(row)
            for row in client_issues.list_issue_verifications(authoritative_conn, issue_id=issue_id, limit=500)
        ]
        usage = [
            legacy_graph._usage_record(row)
            for row in client_issues.list_issue_usage_evidence(authoritative_conn, issue_id=issue_id, limit=500)
        ]
        if not verifications:
            verifications = legacy_graph._synthesized_verifications(issue=issue, events=list(events))
        if not usage:
            usage = legacy_graph._synthesized_usage(issue=issue, events=list(events))
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

    jobs_by_id = legacy_graph._job_record(authoritative_conn, job_ids=related_job_ids)
    incidents = legacy_graph._incident_records(authoritative_conn)
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

    source_db = _authoritative_db_path(authoritative_conn)
    source_repo = "ChatgptREST"
    now_text = _ts_text(time.time())
    objects: list[tuple[Any, ...]] = []
    sources: list[tuple[Any, ...]] = []
    projections: list[tuple[Any, ...]] = []
    relations: list[tuple[Any, ...]] = []

    def add_object(
        *,
        object_id: str,
        canonical_key: str,
        object_type: str,
        title: str,
        summary: str | None,
        authority_level: str,
        status: str | None,
        payload: dict[str, Any],
        source_table: str,
        source_pk: str,
        source_path: str | None,
        source_ref: str | None,
        source_locator: str | None = None,
        projection_names: list[str],
        evidence_count: int = 0,
    ) -> None:
        objects.append(
            (
                object_id,
                canonical_key,
                _ISSUE_DOMAIN,
                object_type,
                title,
                summary,
                authority_level,
                "p1" if authority_level == "authoritative" else "p2",
                "issue_projection_history",
                "promote",
                "issue_domain_projection",
                "graph",
                "history_only" if authority_level != "authoritative" else "verified",
                int(evidence_count),
                source_repo,
                source_path,
                source_ref,
                source_locator,
                canonical_key,
                status,
                None,
                ("verified" if authority_level == "authoritative" else None),
                now_text,
                now_text,
                now_text,
                _json_dumps(payload),
            )
        )
        sources.append(
            (
                object_id,
                f"src:{object_id}:{source_table}:{source_pk}",
                source_db,
                source_table,
                source_pk,
                authority_level,
                "p1" if authority_level == "authoritative" else "p2",
                "issue_projection_history",
                "history_only" if authority_level != "authoritative" else "verified",
                int(evidence_count),
                _json_dumps(payload),
            )
        )
        for projection_name in projection_names:
            projections.append(
                (
                    object_id,
                    projection_name,
                    "ready",
                    "issue_domain canonical projection",
                )
            )

    def add_relation(
        from_object_id: str,
        to_object_id: str,
        edge_type: str,
        attrs: dict[str, Any] | None = None,
        *,
        source_path: str | None = None,
    ) -> None:
        relations.append(
            (
                _relation_id(edge_type, from_object_id, to_object_id),
                _ISSUE_DOMAIN,
                edge_type,
                from_object_id,
                to_object_id,
                source_path,
                1.0,
                "ready",
                None,
                _json_dumps(attrs or {}),
                "issue_canonical_v1",
            )
        )

    for family_id, members in family_members.items():
        severity_counts = Counter(str(member.get("severity") or "") for member in members)
        add_object(
            object_id=f"family:{family_id}",
            canonical_key=family_id,
            object_type="Family",
            title=str(members[0].get("family_label") or family_id),
            summary=f"{len(members)} issue(s) in family",
            authority_level="derived",
            status=None,
            payload={
                "family_id": family_id,
                "issue_ids": [member["issue_id"] for member in members],
                "issue_count": len(members),
                "severity_counts": dict(sorted(severity_counts.items())),
            },
            source_table="derived.issue_family",
            source_pk=family_id,
            source_path=None,
            source_ref=family_id,
            source_locator=None,
            projection_names=["graph"],
        )

    for issue in issue_rows:
        issue_id = str(issue["issue_id"])
        issue_node = f"issue:{issue_id}"
        issue_verifications = list(verifications_by_issue.get(issue_id) or [])
        issue_usage = list(usage_by_issue.get(issue_id) or [])
        latest_verification = issue_verifications[0] if issue_verifications else None
        latest_usage = issue_usage[0] if issue_usage else None
        issue_payload = {
            **issue,
            "verification_count": len(issue_verifications),
            "usage_count": len(issue_usage),
            "latest_verification": latest_verification,
            "latest_usage": latest_usage,
            "incident_count": len(incidents_by_issue.get(issue_id) or []),
            "document_count": len(doc_refs.get(issue_id) or []),
        }
        add_object(
            object_id=issue_node,
            canonical_key=issue_id,
            object_type="Issue",
            title=str(issue["title"]),
            summary=str(issue.get("symptom") or issue.get("raw_error") or issue["title"]),
            authority_level="authoritative",
            status=str(issue.get("status") or ""),
            payload=issue_payload,
            source_table="client_issues",
            source_pk=issue_id,
            source_path="state/jobdb.sqlite3",
            source_ref=issue_id,
            source_locator=None,
            projection_names=["graph", "ledger_ref"],
            evidence_count=len(issue_verifications) + len(issue_usage),
        )
        add_relation(issue_node, f"family:{issue['family_id']}", "belongs_to_family")

        if issue.get("latest_job_id"):
            job_id = str(issue["latest_job_id"])
            job = jobs_by_id.get(job_id) or {"job_id": job_id}
            add_object(
                object_id=f"job:{job_id}",
                canonical_key=job_id,
                object_type="Job",
                title=job_id,
                summary=str(job.get("kind") or "job"),
                authority_level="runtime",
                status=(str(job.get("status")) if job.get("status") is not None else None),
                payload=job,
                source_table="jobs",
                source_pk=job_id,
                source_path="state/jobdb.sqlite3",
                source_ref=job_id,
                source_locator=None,
                projection_names=["graph"],
            )
            add_relation(issue_node, f"job:{job_id}", "latest_job")

        for verification in issue_verifications:
            verification_id = str(verification["verification_id"])
            verification_node = f"verification:{verification_id}"
            provenance = _evidence_provenance(verification, object_type="Verification")
            add_object(
                object_id=verification_node,
                canonical_key=verification_id,
                object_type="Verification",
                title=f"{verification['verification_type']} ({verification['status']})",
                summary=str(verification.get("note") or verification.get("verification_type") or verification_id),
                authority_level=str(provenance["authority_level"]),
                status=str(verification.get("status") or "passed"),
                payload={
                    **verification,
                    "evidence_provenance": {
                        "synthetic": bool(provenance["synthetic"]),
                        "derived_from": provenance["derived_from"],
                    },
                },
                source_table=str(provenance["source_table"]),
                source_pk=str(provenance["source_pk"]),
                source_path=str(provenance["source_path"]),
                source_ref=str(provenance["source_ref"]),
                source_locator=None,
                projection_names=["graph"],
            )
            add_relation(issue_node, verification_node, "validated_by")
            if verification.get("job_id"):
                job_id = str(verification["job_id"])
                job = jobs_by_id.get(job_id) or {"job_id": job_id}
                add_object(
                    object_id=f"job:{job_id}",
                    canonical_key=job_id,
                    object_type="Job",
                    title=job_id,
                    summary=str(job.get("kind") or "job"),
                    authority_level="runtime",
                    status=(str(job.get("status")) if job.get("status") is not None else None),
                    payload=job,
                    source_table="jobs",
                    source_pk=job_id,
                    source_path="state/jobdb.sqlite3",
                    source_ref=job_id,
                    source_locator=None,
                    projection_names=["graph"],
                )
                add_relation(verification_node, f"job:{job_id}", "uses_job")

        for usage in issue_usage:
            usage_id = str(usage["usage_id"])
            usage_node = f"usage:{usage_id}"
            provenance = _evidence_provenance(usage, object_type="UsageEvidence")
            add_object(
                object_id=usage_node,
                canonical_key=usage_id,
                object_type="UsageEvidence",
                title=f"{usage.get('client_name') or 'client'} -> {usage['job_id']}",
                summary=str(usage.get("kind") or usage["job_id"]),
                authority_level=str(provenance["authority_level"]),
                status=str(usage.get("status") or "completed"),
                payload={
                    **usage,
                    "evidence_provenance": {
                        "synthetic": bool(provenance["synthetic"]),
                        "derived_from": provenance["derived_from"],
                    },
                },
                source_table=str(provenance["source_table"]),
                source_pk=str(provenance["source_pk"]),
                source_path=str(provenance["source_path"]),
                source_ref=str(provenance["source_ref"]),
                source_locator=None,
                projection_names=["graph"],
            )
            add_relation(issue_node, usage_node, "proven_by_usage")
            job_id = str(usage["job_id"])
            job = jobs_by_id.get(job_id) or {"job_id": job_id}
            add_object(
                object_id=f"job:{job_id}",
                canonical_key=job_id,
                object_type="Job",
                title=job_id,
                summary=str(job.get("kind") or "job"),
                authority_level="runtime",
                status=(str(job.get("status")) if job.get("status") is not None else None),
                payload=job,
                source_table="jobs",
                source_pk=job_id,
                source_path="state/jobdb.sqlite3",
                source_ref=job_id,
                source_locator=None,
                projection_names=["graph"],
            )
            add_relation(usage_node, f"job:{job_id}", "uses_job")

        for incident in incidents_by_issue.get(issue_id) or []:
            incident_id = str(incident["incident_id"])
            add_object(
                object_id=f"incident:{incident_id}",
                canonical_key=incident_id,
                object_type="Incident",
                title=str(incident["signature"]),
                summary=str(incident.get("category") or incident.get("severity") or incident_id),
                authority_level="runtime",
                status=str(incident.get("status") or "open"),
                payload=incident,
                source_table="incidents",
                source_pk=incident_id,
                source_path="state/jobdb.sqlite3",
                source_ref=incident_id,
                source_locator=None,
                projection_names=["graph"],
            )
            add_relation(issue_node, f"incident:{incident_id}", "linked_incident")

        for doc in doc_refs.get(issue_id) or []:
            doc_path = str(doc["path"])
            locator = str(doc.get("locator") or "").strip()
            excerpt = str(doc.get("excerpt") or "").strip()
            match_term = str(doc.get("match_term") or "").strip()
            content_hash = str(doc.get("content_hash") or "").strip()
            canonical_key = f"{doc_path}#{locator}" if locator else doc_path
            doc_node = f"doc:{hashlib.sha1(canonical_key.encode('utf-8', errors='replace')).hexdigest()}"
            add_object(
                object_id=doc_node,
                canonical_key=canonical_key,
                object_type="DocEvidence",
                title=(f"{doc['name']}:{locator}" if locator else str(doc["name"])),
                summary=excerpt or doc_path,
                authority_level="derived",
                status=None,
                payload={
                    **doc,
                    "canonical_key": canonical_key,
                    "source_ref": doc_path,
                    "source_locator": locator or None,
                    "excerpt": excerpt or None,
                    "match_term": match_term or None,
                    "content_hash": content_hash or None,
                },
                source_table="docs",
                source_pk=canonical_key,
                source_path=doc_path,
                source_ref=doc_path,
                source_locator=locator or None,
                projection_names=["graph"],
            )
            add_relation(issue_node, doc_node, "documented_in", source_path=doc_path)

    return issue_rows, objects, sources, projections, relations


def sync_issue_canonical(
    authoritative_conn: sqlite3.Connection,
    *,
    canonical_db_path: str | None = None,
    include_closed: bool = True,
    max_issues: int = 1000,
    include_docs: bool = True,
    force: bool = False,
) -> str:
    if authoritative_conn is None:
        raise IssueCanonicalUnavailable("authoritative issue ledger connection is required")
    target_path = _canonical_write_path(canonical_db_path or "")
    watermark = _sync_source_watermark(authoritative_conn)
    with _connect_rw(target_path) as canonical_conn:
        canonical_conn.execute("BEGIN IMMEDIATE")
        _ensure_schema(canonical_conn)
        previous = _meta_get(canonical_conn, "last_issue_event_id")
        row = canonical_conn.execute(
            "SELECT COUNT(*) FROM canonical_objects WHERE domain = ? AND object_type = 'Issue'",
            (_ISSUE_DOMAIN,),
        ).fetchone()
        existing_issue_count = int(row[0] or 0)
        if (not force) and previous == watermark and existing_issue_count > 0:
            canonical_conn.commit()
            return target_path

        issue_rows, objects, sources, projections, relations = _build_issue_domain_projection(
            authoritative_conn,
            include_closed=True,
            include_docs=include_docs,
        )
        object_ids = [str(row[0]) for row in objects]
        canonical_conn.execute("DELETE FROM canonical_relations WHERE domain = ?", (_ISSUE_DOMAIN,))
        if object_ids:
            canonical_conn.execute(
                f"DELETE FROM projection_targets WHERE object_id IN ({_placeholders(len(object_ids))})",
                tuple(object_ids),
            )
            canonical_conn.execute(
                f"DELETE FROM object_sources WHERE object_id IN ({_placeholders(len(object_ids))})",
                tuple(object_ids),
            )
        canonical_conn.execute("DELETE FROM canonical_objects WHERE domain = ?", (_ISSUE_DOMAIN,))
        canonical_conn.executemany(
            """
            INSERT OR REPLACE INTO canonical_objects(
              object_id, canonical_key, domain, object_type, title, summary,
              authority_level, ingest_priority, ingest_action, disposition,
              disposition_reason, projection_hint, quality_signal, evidence_count,
              source_repo, source_path, source_ref, source_locator, semantic_key,
              status, promotion_state, verification_state, freshness_ts,
              created_at, updated_at, payload_json
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            objects,
        )
        canonical_conn.executemany(
            """
            INSERT OR REPLACE INTO object_sources(
              object_id, candidate_id, source_db, source_table, source_pk,
              authority_level, ingest_priority, ingest_action, quality_signal,
              evidence_count, payload_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            sources,
        )
        canonical_conn.executemany(
            """
            INSERT OR REPLACE INTO projection_targets(
              object_id, projection_name, projection_state, projection_reason
            ) VALUES (?,?,?,?)
            """,
            projections,
        )
        canonical_conn.executemany(
            """
            INSERT OR REPLACE INTO canonical_relations(
              relation_id, domain, edge_type, from_object_id, to_object_id,
              source_path, confidence, status, evidence_refs_json, attrs_json,
              extractor_version
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            relations,
        )
        _meta_set(canonical_conn, "last_issue_event_id", watermark)
        _meta_set(canonical_conn, "last_sync_issue_count", str(len(issue_rows)))
        _meta_set(canonical_conn, "last_synced_at", _ts_text(time.time()))
        coverage = _coverage_snapshot(authoritative_conn, canonical_conn, include_closed=True)
        _meta_set(canonical_conn, "authoritative_issue_count", str(int(coverage["authoritative_issue_count"])))
        _meta_set(canonical_conn, "canonical_issue_count", str(int(coverage["canonical_issue_count"])))
        _meta_set(canonical_conn, "coverage_gap_count", str(int(coverage["coverage_gap_count"])))
        _meta_set(canonical_conn, "missing_issue_ids", _json_dumps(list(coverage["missing_issue_ids"])))
        canonical_conn.commit()
    return target_path


def build_issue_views_snapshot_from_canonical(
    *,
    canonical_db_path: str | None = None,
    authoritative_conn: sqlite3.Connection | None = None,
    active_statuses: tuple[str, ...] = ("open", "in_progress"),
    recent_statuses: tuple[str, ...] = ("mitigated", "closed"),
    active_limit: int = 200,
    recent_limit: int = 200,
    ensure_fresh: bool = False,
) -> dict[str, Any]:
    resolved = resolve_issue_canonical_db_path(canonical_db_path or "")
    if ensure_fresh and authoritative_conn is not None:
        max_issues = max(int(active_limit), int(recent_limit), 200)
        resolved = sync_issue_canonical(
            authoritative_conn,
            canonical_db_path=canonical_db_path,
            include_closed=True,
            max_issues=max_issues,
            include_docs=True,
        )
    if not resolved:
        raise IssueCanonicalUnavailable("canonical issue plane not configured")
    with _connect_read_only(resolved) as conn:
        active_rows = _query_issue_object_rows(
            conn,
            issue_id=None,
            q=None,
            status=",".join(str(x).strip() for x in active_statuses if str(x).strip()),
            include_closed=True,
            limit=max(1, int(active_limit)),
        )
        recent_rows = _query_issue_object_rows(
            conn,
            issue_id=None,
            q=None,
            status=",".join(str(x).strip() for x in recent_statuses if str(x).strip()),
            include_closed=True,
            limit=max(1, int(recent_limit)),
        )
        active_objects = _build_response(active_rows, conn)["objects"]
        recent_objects = _build_response(recent_rows, conn)["objects"]
        coverage = _read_coverage_meta(conn)
    active_issues = [_issue_payload_from_object(obj) for obj in active_objects]
    recently_settled = [_issue_payload_from_object(obj) for obj in recent_objects]
    return {
        "generated_at": time.time(),
        "summary": {
            "domain": _ISSUE_DOMAIN,
            "read_plane": "canonical",
            "canonical_db_path": resolved,
            "active_count": len(active_issues),
            "recent_count": len(recently_settled),
            **coverage,
        },
        "active_issues": active_issues,
        "recently_settled": recently_settled,
    }


def _read_graph_nodes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT object_id, canonical_key, object_type, title, status, payload_json
        FROM canonical_objects
        WHERE domain = ?
        ORDER BY object_id ASC
        """,
        (_ISSUE_DOMAIN,),
    ).fetchall()
    nodes: list[dict[str, Any]] = []
    for row in rows:
        payload = _parse_json(row["payload_json"])
        nodes.append(
            {
                "id": str(row["object_id"]),
                "kind": _graph_kind(str(row["object_type"])),
                "label": str(row["title"]),
                "attrs": {
                    **payload,
                    "canonical_key": str(row["canonical_key"]),
                    "status": (str(row["status"]) if row["status"] is not None else None),
                },
            }
        )
    return nodes


def _read_graph_edges(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT relation_id, edge_type, from_object_id, to_object_id, attrs_json
        FROM canonical_relations
        WHERE domain = ?
        ORDER BY relation_id ASC
        """,
        (_ISSUE_DOMAIN,),
    ).fetchall()
    return [
        {
            "source": str(row["from_object_id"]),
            "target": str(row["to_object_id"]),
            "type": str(row["edge_type"]),
            "attrs": _parse_json(row["attrs_json"]),
        }
        for row in rows
    ]


def _issue_payload_from_object(obj: dict[str, Any]) -> dict[str, Any]:
    payload = dict(obj.get("payload") or {})
    payload.setdefault("issue_id", str(obj.get("canonical_key") or ""))
    payload.setdefault("title", str(obj.get("title") or ""))
    payload.setdefault("status", obj.get("status"))
    payload.setdefault("family_id", payload.get("family_id"))
    payload.setdefault("family_label", payload.get("family_label"))
    return payload


def build_issue_graph_snapshot_from_canonical(
    *,
    canonical_db_path: str | None = None,
    authoritative_conn: sqlite3.Connection | None = None,
    include_closed: bool = True,
    max_issues: int = 1000,
    include_docs: bool = True,
    ensure_fresh: bool = False,
) -> dict[str, Any]:
    resolved = resolve_issue_canonical_db_path(canonical_db_path or "")
    if ensure_fresh and authoritative_conn is not None:
        resolved = sync_issue_canonical(
            authoritative_conn,
            canonical_db_path=canonical_db_path,
            include_closed=include_closed,
            max_issues=max_issues,
            include_docs=include_docs,
        )
    if not resolved:
        raise IssueCanonicalUnavailable("canonical issue plane not configured")
    with _connect_read_only(resolved) as conn:
        issue_rows = _query_issue_object_rows(
            conn,
            issue_id=None,
            q=None,
            status=(None if include_closed else "open,in_progress,mitigated"),
            include_closed=include_closed,
            limit=max_issues,
        )
        object_ids = [str(row["object_id"]) for row in issue_rows]
        objects = _build_response(issue_rows, conn)["objects"]
        nodes = _read_graph_nodes(conn)
        edges = _read_graph_edges(conn)
        coverage = _read_coverage_meta(conn)
    issue_payloads = [_issue_payload_from_object(obj) for obj in objects]
    family_ids = {str(issue.get("family_id") or "") for issue in issue_payloads if str(issue.get("family_id") or "").strip()}
    node_kind_counts = Counter(str(node.get("kind") or "") for node in nodes)
    summary = {
        "issue_count": len(issue_payloads),
        "family_count": len(family_ids),
        "verification_count": int(node_kind_counts.get("verification", 0)),
        "usage_evidence_count": int(node_kind_counts.get("usage", 0)),
        "job_count": int(node_kind_counts.get("job", 0)),
        "incident_count": int(node_kind_counts.get("incident", 0)),
        "document_count": int(node_kind_counts.get("document", 0)) + int(node_kind_counts.get("document_evidence", 0)),
        "doc_evidence_count": int(node_kind_counts.get("document_evidence", 0)),
        "read_plane": "canonical",
        "canonical_db_path": resolved,
        **coverage,
    }
    return {
        "generated_at": time.time(),
        "summary": summary,
        "issues": issue_payloads,
        "nodes": nodes,
        "edges": edges,
    }


def _query_issue_graph_canonical(
    *,
    canonical_db_path: str | None = None,
    authoritative_conn: sqlite3.Connection | None = None,
    issue_id: str | None = None,
    family_id: str | None = None,
    q: str | None = None,
    status: str | None = None,
    include_closed: bool = True,
    limit: int = 20,
    neighbor_depth: int = 1,
    ensure_fresh: bool = False,
) -> dict[str, Any]:
    resolved = resolve_issue_canonical_db_path(canonical_db_path or "")
    if ensure_fresh and authoritative_conn is not None:
        resolved = sync_issue_canonical(
            authoritative_conn,
            canonical_db_path=canonical_db_path,
            include_closed=include_closed,
            max_issues=max(50, int(limit) * 20),
            include_docs=True,
        )
    if not resolved:
        raise IssueCanonicalUnavailable("canonical issue plane not configured")
    with _connect_read_only(resolved) as conn:
        matched_rows = _query_issue_object_rows(
            conn,
            issue_id=issue_id,
            family_id=family_id,
            q=q,
            status=status,
            include_closed=include_closed,
            limit=limit,
        )
        matched_ids = [str(row["object_id"]) for row in matched_rows]
        all_nodes = _read_graph_nodes(conn)
        all_edges = _read_graph_edges(conn)
    nodes_by_id = {str(node["id"]): node for node in all_nodes}
    adjacency: dict[str, list[str]] = defaultdict(list)
    edge_lookup: list[dict[str, Any]] = []
    for edge in all_edges:
        src = str(edge["source"])
        dst = str(edge["target"])
        adjacency[src].append(dst)
        adjacency[dst].append(src)
        edge_lookup.append(edge)
    visited: set[str] = set(matched_ids)
    frontier: deque[tuple[str, int]] = deque((node_id, 0) for node_id in matched_ids)
    max_depth = max(0, int(neighbor_depth))
    while frontier:
        node_id, depth = frontier.popleft()
        if depth >= max_depth:
            continue
        for nxt in adjacency.get(node_id) or []:
            if nxt in visited:
                continue
            visited.add(nxt)
            frontier.append((nxt, depth + 1))
    result_nodes = [nodes_by_id[node_id] for node_id in visited if node_id in nodes_by_id]
    result_edges = [
        edge for edge in edge_lookup
        if str(edge["source"]) in visited and str(edge["target"]) in visited
    ]
    matches = []
    for row in matched_rows:
        payload = _parse_json(row["payload_json"])
        matches.append(
            {
                "issue_id": str(row["canonical_key"]),
                "object_id": str(row["object_id"]),
                "title": str(row["title"]),
                "status": (str(row["status"]) if row["status"] is not None else None),
                "family_id": str(payload.get("family_id") or ""),
            }
        )
    return {
        "generated_at": time.time(),
        "summary": {
            "match_count": len(matches),
            "node_count": len(result_nodes),
            "edge_count": len(result_edges),
            "read_plane": "canonical",
            "canonical_db_path": resolved,
        },
        "matches": matches,
        "nodes": result_nodes,
        "edges": result_edges,
    }


def query_issue_canonical(
    *,
    canonical_db_path: str | None = None,
    authoritative_conn: sqlite3.Connection | None = None,
    issue_id: str | None = None,
    q: str | None = None,
    status: str | None = None,
    limit: int = 20,
    ensure_fresh: bool = False,
) -> dict[str, Any]:
    resolved = resolve_issue_canonical_db_path(canonical_db_path or "")
    if ensure_fresh and authoritative_conn is not None:
        resolved = sync_issue_canonical(
            authoritative_conn,
            canonical_db_path=canonical_db_path,
            include_closed=True,
            max_issues=max(50, int(limit) * 20),
            include_docs=True,
        )
    if not resolved:
        raise IssueCanonicalUnavailable("canonical issue plane not configured")
    with _connect_read_only(resolved) as conn:
        rows = _query_issue_rows(conn, issue_id=issue_id, q=q, status=status, limit=limit)
        payload = _build_response(rows, conn)
        payload["summary"]["read_plane"] = "canonical"
        payload["summary"]["canonical_db_path"] = resolved
        payload["summary"].update(_read_coverage_meta(conn))
        return payload


def export_issue_canonical_snapshot(
    *,
    canonical_db_path: str | None = None,
    authoritative_conn: sqlite3.Connection | None = None,
    status: str | None = None,
    limit: int = 200,
    ensure_fresh: bool = False,
) -> dict[str, Any]:
    return query_issue_canonical(
        canonical_db_path=canonical_db_path,
        authoritative_conn=authoritative_conn,
        status=status,
        limit=limit,
        ensure_fresh=ensure_fresh,
    )


def query_issue_graph_preferred(
    *,
    authoritative_conn: sqlite3.Connection | None,
    canonical_db_path: str | None = None,
    issue_id: str | None = None,
    family_id: str | None = None,
    q: str | None = None,
    status: str | None = None,
    include_closed: bool = True,
    limit: int = 20,
    neighbor_depth: int = 1,
) -> dict[str, Any]:
    return _query_issue_graph_canonical(
        canonical_db_path=canonical_db_path,
        authoritative_conn=authoritative_conn,
        issue_id=issue_id,
        family_id=family_id,
        q=q,
        status=status,
        include_closed=include_closed,
        limit=limit,
        neighbor_depth=neighbor_depth,
        ensure_fresh=True,
    )


def export_issue_graph_snapshot(
    *,
    authoritative_conn: sqlite3.Connection | None,
    canonical_db_path: str | None = None,
    include_closed: bool = True,
    max_issues: int = 1000,
) -> dict[str, Any]:
    return build_issue_graph_snapshot_from_canonical(
        canonical_db_path=canonical_db_path,
        authoritative_conn=authoritative_conn,
        include_closed=include_closed,
        max_issues=max_issues,
        include_docs=True,
        ensure_fresh=True,
    )
