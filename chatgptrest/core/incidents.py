from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from chatgptrest.core.db import meta_get, meta_set


INCIDENT_STATUS_OPEN = "open"
INCIDENT_STATUS_INVESTIGATING = "investigating"
INCIDENT_STATUS_FIXING = "fixing"
INCIDENT_STATUS_RESOLVED = "resolved"
INCIDENT_STATUS_ESCALATED = "escalated"
INCIDENT_STATUS_FLAPPING = "flapping"

ACTION_STATUS_PENDING = "pending"
ACTION_STATUS_RUNNING = "running"
ACTION_STATUS_COMPLETED = "completed"
ACTION_STATUS_FAILED = "failed"
ACTION_STATUS_SKIPPED = "skipped"


def fingerprint_hash(signature: str) -> str:
    return hashlib.sha256(str(signature or "").encode("utf-8", errors="replace")).hexdigest()


def fingerprint_short(signature: str) -> str:
    return fingerprint_hash(signature)[:12]


def _now() -> float:
    return time.time()


def _normalize_severity(value: str | None) -> str:
    s = str(value or "").strip().upper() or "P2"
    return s if s in {"P0", "P1", "P2"} else "P2"


def _loads_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        obj = json.loads(raw)
    except Exception:
        return []
    if not isinstance(obj, list):
        return []
    out: list[str] = []
    for x in obj:
        sx = str(x or "").strip()
        if sx:
            out.append(sx)
    return out


def _dumps_json_list(values: Iterable[str]) -> str:
    uniq: list[str] = []
    seen: set[str] = set()
    for v in values:
        s = str(v or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    return json.dumps(uniq, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class IncidentRecord:
    incident_id: str
    fingerprint_hash: str
    signature: str
    category: str | None
    severity: str
    status: str
    created_at: float
    updated_at: float
    last_seen_at: float
    count: int
    job_ids: list[str]
    evidence_dir: str | None = None
    repair_job_id: str | None = None
    codex_input_hash: str | None = None
    codex_last_run_ts: float | None = None
    codex_run_count: int = 0
    codex_last_ok: bool | None = None
    codex_last_error: str | None = None
    codex_autofix_last_ts: float | None = None
    codex_autofix_run_count: int = 0


def _row_to_incident(row: Any) -> IncidentRecord:
    codex_last_ok: bool | None = None
    raw_ok = row["codex_last_ok"]
    if raw_ok is None:
        codex_last_ok = None
    elif isinstance(raw_ok, bool):
        codex_last_ok = raw_ok
    else:
        try:
            codex_last_ok = bool(int(raw_ok))
        except Exception:
            codex_last_ok = bool(raw_ok)
    return IncidentRecord(
        incident_id=str(row["incident_id"]),
        fingerprint_hash=str(row["fingerprint_hash"]),
        signature=str(row["signature"]),
        category=(str(row["category"]).strip() if row["category"] is not None else None) or None,
        severity=_normalize_severity(row["severity"]),
        status=str(row["status"]),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        last_seen_at=float(row["last_seen_at"]),
        count=int(row["count"] or 0),
        job_ids=_loads_json_list(row["job_ids_json"] if "job_ids_json" in row.keys() else None),
        evidence_dir=(str(row["evidence_dir"]).strip() if row["evidence_dir"] is not None else None) or None,
        repair_job_id=(str(row["repair_job_id"]).strip() if row["repair_job_id"] is not None else None) or None,
        codex_input_hash=(str(row["codex_input_hash"]).strip() if row["codex_input_hash"] is not None else None) or None,
        codex_last_run_ts=(float(row["codex_last_run_ts"]) if row["codex_last_run_ts"] is not None else None),
        codex_run_count=int(row["codex_run_count"] or 0),
        codex_last_ok=codex_last_ok,
        codex_last_error=(str(row["codex_last_error"]).strip() if row["codex_last_error"] is not None else None) or None,
        codex_autofix_last_ts=(float(row["codex_autofix_last_ts"]) if row["codex_autofix_last_ts"] is not None else None),
        codex_autofix_run_count=int(row["codex_autofix_run_count"] or 0),
    )


def find_active_incident(
    conn,
    *,
    fingerprint: str,
    now: float | None = None,
    dedupe_seconds: float = 1800.0,
) -> IncidentRecord | None:
    now_ts = _now() if now is None else float(now)
    min_last_seen = now_ts - float(max(0.0, dedupe_seconds))
    row = conn.execute(
        """
        SELECT *
        FROM incidents
        WHERE fingerprint_hash = ?
          AND status != ?
          AND last_seen_at >= ?
        ORDER BY last_seen_at DESC
        LIMIT 1
        """,
        (str(fingerprint), INCIDENT_STATUS_RESOLVED, float(min_last_seen)),
    ).fetchone()
    return _row_to_incident(row) if row is not None else None


def create_incident(
    conn,
    *,
    incident_id: str,
    fingerprint: str,
    signature: str,
    category: str | None,
    severity: str | None,
    now: float | None = None,
    job_ids: list[str] | None = None,
    evidence_dir: str | None = None,
) -> IncidentRecord:
    now_ts = _now() if now is None else float(now)
    job_ids_json = _dumps_json_list(job_ids or [])
    conn.execute(
        """
        INSERT INTO incidents(
          incident_id, fingerprint_hash, signature, category, severity, status,
          created_at, updated_at, last_seen_at, count, job_ids_json, evidence_dir
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            str(incident_id),
            str(fingerprint),
            str(signature),
            (str(category).strip() if category else None),
            _normalize_severity(severity),
            INCIDENT_STATUS_OPEN,
            float(now_ts),
            float(now_ts),
            float(now_ts),
            0,
            job_ids_json,
            (str(evidence_dir).strip() if evidence_dir else None),
        ),
    )
    row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (str(incident_id),)).fetchone()
    assert row is not None
    return _row_to_incident(row)


def touch_incident(
    conn,
    *,
    incident_id: str,
    now: float | None = None,
    add_job_id: str | None = None,
    repair_job_id: str | None = None,
    evidence_dir: str | None = None,
) -> IncidentRecord:
    now_ts = _now() if now is None else float(now)
    row = conn.execute("SELECT job_ids_json FROM incidents WHERE incident_id = ?", (str(incident_id),)).fetchone()
    existing_jobs = _loads_json_list(str(row["job_ids_json"]) if row is not None and row["job_ids_json"] is not None else None)
    if add_job_id:
        existing_jobs.append(str(add_job_id))
    job_ids_json = _dumps_json_list(existing_jobs)

    conn.execute(
        """
        UPDATE incidents
        SET updated_at = ?,
            last_seen_at = ?,
            count = count + 1,
            job_ids_json = ?,
            repair_job_id = COALESCE(?, repair_job_id),
            evidence_dir = COALESCE(?, evidence_dir)
        WHERE incident_id = ?
        """,
        (
            float(now_ts),
            float(now_ts),
            job_ids_json,
            (str(repair_job_id).strip() if repair_job_id else None),
            (str(evidence_dir).strip() if evidence_dir else None),
            str(incident_id),
        ),
    )
    row2 = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (str(incident_id),)).fetchone()
    assert row2 is not None
    return _row_to_incident(row2)


def set_repair_job_id(conn, *, incident_id: str, repair_job_id: str, now: float | None = None) -> IncidentRecord:
    now_ts = _now() if now is None else float(now)
    conn.execute(
        "UPDATE incidents SET updated_at = ?, repair_job_id = ? WHERE incident_id = ?",
        (float(now_ts), str(repair_job_id), str(incident_id)),
    )
    row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (str(incident_id),)).fetchone()
    assert row is not None
    return _row_to_incident(row)


def set_evidence_dir(conn, *, incident_id: str, evidence_dir: str, now: float | None = None) -> IncidentRecord:
    now_ts = _now() if now is None else float(now)
    conn.execute(
        "UPDATE incidents SET updated_at = ?, evidence_dir = ? WHERE incident_id = ?",
        (float(now_ts), (str(evidence_dir).strip() or None), str(incident_id)),
    )
    row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (str(incident_id),)).fetchone()
    assert row is not None
    return _row_to_incident(row)


def update_codex_state(
    conn,
    *,
    incident_id: str,
    codex_input_hash: str | None,
    codex_last_run_ts: float | None,
    codex_run_count: int,
    codex_last_ok: bool | None,
    codex_last_error: str | None,
    now: float | None = None,
) -> IncidentRecord:
    now_ts = _now() if now is None else float(now)
    codex_last_ok_int: int | None
    if codex_last_ok is None:
        codex_last_ok_int = None
    else:
        codex_last_ok_int = 1 if bool(codex_last_ok) else 0
    conn.execute(
        """
        UPDATE incidents
        SET updated_at = ?,
            codex_input_hash = ?,
            codex_last_run_ts = ?,
            codex_run_count = ?,
            codex_last_ok = ?,
            codex_last_error = ?
        WHERE incident_id = ?
        """,
        (
            float(now_ts),
            (str(codex_input_hash).strip() if codex_input_hash else None),
            (float(codex_last_run_ts) if codex_last_run_ts is not None else None),
            int(codex_run_count),
            codex_last_ok_int,
            (str(codex_last_error).strip() if codex_last_error else None),
            str(incident_id),
        ),
    )
    row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (str(incident_id),)).fetchone()
    assert row is not None
    return _row_to_incident(row)


def update_codex_autofix_state(conn, *, incident_id: str, codex_autofix_last_ts: float, codex_autofix_run_count: int) -> IncidentRecord:
    conn.execute(
        """
        UPDATE incidents
        SET updated_at = ?,
            codex_autofix_last_ts = ?,
            codex_autofix_run_count = ?
        WHERE incident_id = ?
        """,
        (float(codex_autofix_last_ts), float(codex_autofix_last_ts), int(codex_autofix_run_count), str(incident_id)),
    )
    row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (str(incident_id),)).fetchone()
    assert row is not None
    return _row_to_incident(row)


def set_incident_status(conn, *, incident_id: str, status: str, now: float | None = None) -> IncidentRecord:
    now_ts = _now() if now is None else float(now)
    conn.execute(
        "UPDATE incidents SET status = ?, updated_at = ? WHERE incident_id = ?",
        (str(status), float(now_ts), str(incident_id)),
    )
    row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (str(incident_id),)).fetchone()
    assert row is not None
    return _row_to_incident(row)



def resolve_stale_incidents(
    conn,
    *,
    stale_before_ts: float,
    now: float | None = None,
    limit: int = 1000,
) -> list[IncidentRecord]:
    """Mark incidents as resolved when they have not been seen recently.

    This is primarily used by `ops/maint_daemon.py` to keep the incident table
    actionable by auto-resolving entries that have not been observed for a
    configurable TTL.
    """
    now_ts = _now() if now is None else float(now)
    rows = conn.execute(
        """
        SELECT incident_id
        FROM incidents
        WHERE status != ?
          AND last_seen_at < ?
        ORDER BY last_seen_at ASC
        LIMIT ?
        """,
        (INCIDENT_STATUS_RESOLVED, float(stale_before_ts), int(max(0, int(limit)))),
    ).fetchall()

    resolved: list[IncidentRecord] = []
    for r in rows:
        try:
            incident_id = str(r["incident_id"] or "").strip()
        except Exception:
            incident_id = str(r[0] or "").strip() if r else ""
        if not incident_id:
            continue
        resolved.append(set_incident_status(conn, incident_id=incident_id, status=INCIDENT_STATUS_RESOLVED, now=now_ts))
    return resolved


def resolve_duplicate_open_incidents(
    conn,
    *,
    now: float | None = None,
    limit: int = 10_000,
) -> list[IncidentRecord]:
    """Resolve duplicate open incidents for the same fingerprint_hash.

    ChatgptREST historically allowed multiple rows with the same fingerprint_hash
    (e.g. after process restarts or when incidents "roll over" to a new incident_id).

    This helper keeps only the newest row (by last_seen_at/updated_at) per
    fingerprint_hash and marks all older duplicates as resolved.

    It is intended to keep the incidents table actionable for operators.
    """
    now_ts = _now() if now is None else float(now)

    try:
        rows = conn.execute(
            """
            SELECT incident_id, fingerprint_hash
            FROM incidents
            WHERE status != ?
            ORDER BY fingerprint_hash ASC, last_seen_at DESC, updated_at DESC
            LIMIT ?
            """,
            (INCIDENT_STATUS_RESOLVED, int(max(0, int(limit)))),
        ).fetchall()
    except Exception:
        return []

    seen: set[str] = set()
    to_resolve: list[str] = []
    for r in rows:
        try:
            sig_hash = str(r["fingerprint_hash"] or "").strip()
            incident_id = str(r["incident_id"] or "").strip()
        except Exception:
            continue
        if not sig_hash or not incident_id:
            continue
        if sig_hash in seen:
            to_resolve.append(incident_id)
        else:
            seen.add(sig_hash)

    resolved: list[IncidentRecord] = []
    for incident_id in to_resolve:
        try:
            resolved.append(
                set_incident_status(
                    conn,
                    incident_id=str(incident_id),
                    status=INCIDENT_STATUS_RESOLVED,
                    now=now_ts,
                )
            )
        except Exception:
            continue

    return resolved



def create_action(
    conn,
    *,
    incident_id: str,
    action_type: str,
    status: str,
    risk_level: str = "low",
    now: float | None = None,
    result: dict[str, Any] | None = None,
    error_type: str | None = None,
    error: str | None = None,
    action_id: str | None = None,
) -> str:
    now_ts = _now() if now is None else float(now)
    act_id = str(action_id or uuid.uuid4().hex)
    conn.execute(
        """
        INSERT INTO remediation_actions(
          action_id, incident_id, action_type, status, risk_level,
          created_at, started_at, completed_at, result_json, error_type, error
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            act_id,
            str(incident_id),
            str(action_type),
            str(status),
            str(risk_level),
            float(now_ts),
            (float(now_ts) if status == ACTION_STATUS_RUNNING else None),
            (float(now_ts) if status in {ACTION_STATUS_COMPLETED, ACTION_STATUS_FAILED, ACTION_STATUS_SKIPPED} else None),
            (json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True) if isinstance(result, dict) else None),
            (str(error_type) if error_type else None),
            (str(error)[:2000] if error else None),
        ),
    )
    return act_id


def count_actions(
    conn,
    *,
    action_type: str,
    since_ts: float,
    incident_id: str | None = None,
) -> int:
    if incident_id:
        row = conn.execute(
            "SELECT COUNT(1) AS n FROM remediation_actions WHERE incident_id = ? AND action_type = ? AND created_at >= ?",
            (str(incident_id), str(action_type), float(since_ts)),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(1) AS n FROM remediation_actions WHERE action_type = ? AND created_at >= ?",
            (str(action_type), float(since_ts)),
        ).fetchone()
    if row is None:
        return 0
    try:
        return int(row["n"] or 0)
    except Exception:
        return 0


def last_action_ts(
    conn,
    *,
    action_type: str,
    incident_id: str | None = None,
) -> float | None:
    if incident_id:
        row = conn.execute(
            "SELECT MAX(created_at) AS ts FROM remediation_actions WHERE incident_id = ? AND action_type = ?",
            (str(incident_id), str(action_type)),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT MAX(created_at) AS ts FROM remediation_actions WHERE action_type = ?",
            (str(action_type),),
        ).fetchone()
    if row is None:
        return None
    ts = row["ts"]
    if ts is None:
        return None
    try:
        v = float(ts)
    except Exception:
        return None
    return v if v > 0 else None


def load_daemon_state(conn, *, key: str = "maint_daemon_state_v1") -> dict[str, Any]:
    raw = meta_get(conn, key=key)
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def save_daemon_state(conn, state: dict[str, Any], *, key: str = "maint_daemon_state_v1") -> None:
    meta_set(conn, key=key, value=json.dumps(state, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
