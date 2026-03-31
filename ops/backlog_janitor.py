#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DB = "/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3"
DEFAULT_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_ARTIFACTS_DIR = "/vol1/1000/projects/ChatgptREST/artifacts"
DEFAULT_REPORT = "/vol1/1000/projects/ChatgptREST/artifacts/monitor/reports/backlog_janitor/latest.json"


def _http_json_request(
    *,
    method: str,
    url: str,
    timeout_seconds: float,
    body: dict[str, Any] | None = None,
) -> tuple[bool, Any, int | None]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status = int(getattr(resp, "status", 200))
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw.strip() else {}
            except Exception:
                payload = {"raw": raw}
            return True, payload, status
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw = str(exc)
        try:
            payload = json.loads(raw) if raw.strip() else {"error": f"HTTP {int(exc.code)}"}
        except Exception:
            payload = {"error": f"HTTP {int(exc.code)}", "raw": raw}
        return False, payload, int(exc.code)
    except Exception as exc:
        return False, {"error": f"{type(exc).__name__}: {exc}"}, None


def _parse_csv_set(raw: str, *, default: list[str]) -> list[str]:
    parts = [x.strip() for x in str(raw or "").split(",") if x.strip()]
    return parts or list(default)


def _query_stale_jobs(
    *,
    db_path: Path,
    statuses: list[str],
    cutoff_ts: float,
    limit: int,
) -> list[dict[str, Any]]:
    placeholders = ",".join(["?"] * len(statuses))
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"""
            SELECT job_id, kind, status, phase, created_at, updated_at,
                   attempts, max_attempts, last_error_type, last_error
            FROM jobs
            WHERE status IN ({placeholders})
              AND updated_at <= ?
            ORDER BY updated_at ASC
            LIMIT ?
            """,
            (*statuses, float(cutoff_ts), int(max(1, limit))),
        ).fetchall()
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "job_id": str(r["job_id"]),
                "kind": str(r["kind"]),
                "status": str(r["status"]),
                "phase": str(r["phase"] or ""),
                "created_at": float(r["created_at"] or 0.0),
                "updated_at": float(r["updated_at"] or 0.0),
                "attempts": int(r["attempts"] or 0),
                "max_attempts": int(r["max_attempts"] or 0),
                "last_error_type": (str(r["last_error_type"] or "").strip() or None),
                "last_error": (str(r["last_error"] or "").strip() or None),
            }
        )
    return out


def _apply_stale_job_cleanup(
    *,
    db_path: Path,
    artifacts_dir: Path,
    jobs: list[dict[str, Any]],
    max_updates: int,
    actor: str,
    note_prefix: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    from chatgptrest.core import artifacts
    from chatgptrest.core.db import connect, insert_event

    updated_ids: list[str] = []
    failures: list[dict[str, Any]] = []
    now = time.time()

    for row in jobs[: int(max(0, max_updates))]:
        job_id = str(row.get("job_id") or "").strip()
        status = str(row.get("status") or "").strip()
        if not job_id or status not in {"needs_followup", "blocked", "cooldown"}:
            continue
        try:
            idle_hours = max(0.0, (now - float(row.get("updated_at") or 0.0)) / 3600.0)
        except Exception:
            idle_hours = 0.0
        error_type = "BacklogJanitorStale"
        error_text = f"{note_prefix}; previous_status={status}; quiet_hours={idle_hours:.1f}; actor={actor}"
        try:
            with connect(db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                current = conn.execute(
                    "SELECT status, phase, conversation_url, conversation_id FROM jobs WHERE job_id = ?",
                    (job_id,),
                ).fetchone()
                if current is None:
                    raise RuntimeError("job not found")
                current_status = str(current["status"] or "").strip()
                if current_status not in {"needs_followup", "blocked", "cooldown"}:
                    raise RuntimeError(f"job no longer eligible: {current_status}")
                changed = conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'error',
                        updated_at = ?,
                        last_error_type = ?,
                        last_error = ?,
                        lease_owner = NULL,
                        lease_expires_at = NULL,
                        lease_token = NULL
                    WHERE job_id = ?
                      AND status = ?
                    """,
                    (now, error_type, error_text, job_id, current_status),
                ).rowcount
                if not changed:
                    raise RuntimeError("stale job update lost")
                insert_event(
                    conn,
                    job_id=job_id,
                    type="status_changed",
                    payload={"from": current_status, "to": "error"},
                )
                insert_event(
                    conn,
                    job_id=job_id,
                    type="stale_job_finalized",
                    payload={
                        "actor": actor,
                        "previous_status": current_status,
                        "error_type": error_type,
                        "error": error_text,
                    },
                )
                conn.commit()
            artifacts.append_event(
                artifacts_dir,
                job_id,
                type="status_changed",
                payload={"from": current_status, "to": "error"},
            )
            artifacts.append_event(
                artifacts_dir,
                job_id,
                type="stale_job_finalized",
                payload={
                    "actor": actor,
                    "previous_status": current_status,
                    "error_type": error_type,
                    "error": error_text,
                },
            )
            artifacts.write_result(
                artifacts_dir,
                job_id,
                {
                    "ok": False,
                    "job_id": job_id,
                    "status": "error",
                    "phase": str(row.get("phase") or ""),
                    "conversation_url": (str(current["conversation_url"] or "").strip() or None),
                    "conversation_id": (str(current["conversation_id"] or "").strip() or None),
                    "error_type": error_type,
                    "error": error_text,
                },
            )
            updated_ids.append(job_id)
        except Exception as exc:
            failures.append({"job_id": job_id, "error": f"{type(exc).__name__}: {exc}"})

    return updated_ids, failures


def _iter_client_issues(
    *,
    base_url: str,
    statuses: list[str],
    source: str | None,
    page_limit: int,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    base = base_url.rstrip("/")
    out: list[dict[str, Any]] = []
    before_ts: float | None = None
    before_issue_id: str | None = None

    for _ in range(30):
        query: dict[str, str] = {
            "status": ",".join(statuses),
            "limit": str(int(max(1, page_limit))),
        }
        src = str(source or "").strip()
        if src:
            query["source"] = src
        if before_ts is not None:
            query["before_ts"] = str(float(before_ts))
        if before_issue_id:
            query["before_issue_id"] = str(before_issue_id)

        qs = urllib.parse.urlencode(query)
        ok, payload, _status = _http_json_request(
            method="GET",
            url=f"{base}/v1/issues?{qs}",
            timeout_seconds=timeout_seconds,
        )
        if not ok or not isinstance(payload, dict):
            break

        rows = payload.get("issues")
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            if isinstance(row, dict):
                out.append(row)

        nbt = payload.get("next_before_ts")
        nbi = payload.get("next_before_issue_id")
        if nbt is None or nbi is None:
            break
        try:
            before_ts = float(nbt)
        except Exception:
            break
        before_issue_id = str(nbi)
    return out


def _filter_stale_issues(*, issues: list[dict[str, Any]], cutoff_ts: float) -> list[dict[str, Any]]:
    stale: list[dict[str, Any]] = []
    for issue in issues:
        try:
            last_seen = float(issue.get("last_seen_at") or issue.get("updated_at") or 0.0)
        except Exception:
            last_seen = 0.0
        if last_seen <= cutoff_ts:
            stale.append(issue)
    stale.sort(key=lambda x: float(x.get("last_seen_at") or x.get("updated_at") or 0.0))
    return stale


def _apply_issue_mitigations(
    *,
    base_url: str,
    issues: list[dict[str, Any]],
    max_updates: int,
    actor: str,
    note_prefix: str,
    timeout_seconds: float,
) -> tuple[list[str], list[dict[str, Any]]]:
    updated_ids: list[str] = []
    failures: list[dict[str, Any]] = []
    now = time.time()

    for issue in issues[: int(max(0, max_updates))]:
        issue_id = str(issue.get("issue_id") or "").strip()
        if not issue_id:
            continue

        try:
            last_seen = float(issue.get("last_seen_at") or issue.get("updated_at") or 0.0)
        except Exception:
            last_seen = 0.0
        quiet_hours = max(0.0, (now - last_seen) / 3600.0)

        body = {
            "status": "mitigated",
            "actor": str(actor),
            "note": f"{note_prefix}; quiet_hours={quiet_hours:.1f}",
            "linked_job_id": issue.get("latest_job_id"),
            "metadata": {
                "auto": True,
                "source": "backlog_janitor",
                "quiet_hours": round(quiet_hours, 3),
            },
        }

        ok, payload, status_code = _http_json_request(
            method="POST",
            url=f"{base_url.rstrip('/')}/v1/issues/{urllib.parse.quote(issue_id)}/status",
            body=body,
            timeout_seconds=timeout_seconds,
        )
        if ok:
            updated_ids.append(issue_id)
        else:
            failures.append({"issue_id": issue_id, "status": status_code, "payload": payload})

    return updated_ids, failures


def _count_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        k = str(row.get(key) or "")
        out[k] = int(out.get(k, 0)) + 1
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Backlog janitor: identify stale jobs/issues and optionally finalize stale jobs + mitigate stale issues")
    p.add_argument("--db-path", default=DEFAULT_DB)
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--artifacts-dir", default=DEFAULT_ARTIFACTS_DIR)
    p.add_argument("--report-out", default=DEFAULT_REPORT)

    p.add_argument("--job-statuses", default="needs_followup,blocked,cooldown")
    p.add_argument("--job-stale-hours", type=int, default=24 * 7)
    p.add_argument("--job-limit", type=int, default=500)
    p.add_argument("--job-max-updates", type=int, default=500)
    p.add_argument("--job-actor", default="backlog_janitor")
    p.add_argument("--job-note-prefix", default="backlog janitor finalized stale job")

    p.add_argument("--issue-statuses", default="open")
    p.add_argument("--issue-source", default="ops_backfill_2026-02-17")
    p.add_argument("--issue-stale-hours", type=int, default=24 * 7)
    p.add_argument("--issue-page-limit", type=int, default=200)
    p.add_argument("--issue-max-updates", type=int, default=200)
    p.add_argument("--issue-actor", default="backlog_janitor")
    p.add_argument("--issue-note-prefix", default="backlog janitor auto-mitigated stale issue")

    p.add_argument("--timeout-seconds", type=float, default=8.0)
    p.add_argument("--apply", action="store_true", help="Finalize stale jobs and mitigate stale issues")
    return p


def main() -> int:
    args = build_parser().parse_args()
    now = time.time()

    db_path = Path(str(args.db_path)).expanduser()
    if not db_path.exists():
        print(json.dumps({"ok": False, "error": f"db not found: {db_path}"}, ensure_ascii=False, indent=2))
        return 2

    job_statuses = _parse_csv_set(str(args.job_statuses), default=["needs_followup", "blocked", "cooldown"])
    issue_statuses = _parse_csv_set(str(args.issue_statuses), default=["open"])

    job_cutoff = now - float(max(1, int(args.job_stale_hours))) * 3600.0
    issue_cutoff = now - float(max(1, int(args.issue_stale_hours))) * 3600.0

    stale_jobs = _query_stale_jobs(
        db_path=db_path,
        statuses=job_statuses,
        cutoff_ts=job_cutoff,
        limit=int(max(1, args.job_limit)),
    )

    listed_issues = _iter_client_issues(
        base_url=str(args.base_url),
        statuses=issue_statuses,
        source=(str(args.issue_source).strip() or None),
        page_limit=int(max(1, args.issue_page_limit)),
        timeout_seconds=float(max(1.0, args.timeout_seconds)),
    )
    stale_issues = _filter_stale_issues(issues=listed_issues, cutoff_ts=issue_cutoff)

    updated_job_ids: list[str] = []
    job_failures: list[dict[str, Any]] = []
    updated_ids: list[str] = []
    failures: list[dict[str, Any]] = []
    if bool(args.apply):
        updated_job_ids, job_failures = _apply_stale_job_cleanup(
            db_path=db_path,
            artifacts_dir=Path(str(args.artifacts_dir)).expanduser(),
            jobs=stale_jobs,
            max_updates=int(max(0, args.job_max_updates)),
            actor=str(args.job_actor),
            note_prefix=str(args.job_note_prefix),
        )
        updated_ids, failures = _apply_issue_mitigations(
            base_url=str(args.base_url),
            issues=stale_issues,
            max_updates=int(max(0, args.issue_max_updates)),
            actor=str(args.issue_actor),
            note_prefix=str(args.issue_note_prefix),
            timeout_seconds=float(max(1.0, args.timeout_seconds)),
        )

    report = {
        "ok": len(failures) == 0 and len(job_failures) == 0,
        "mode": "apply" if bool(args.apply) else "dry_run",
        "generated_at": now,
        "job_candidates": {
            "cutoff_ts": job_cutoff,
            "cutoff_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(job_cutoff)),
            "statuses": job_statuses,
            "count": len(stale_jobs),
            "by_status": _count_by_key(stale_jobs, "status"),
            "oldest_updated_at": min([x["updated_at"] for x in stale_jobs], default=None),
            "sample_job_ids": [x["job_id"] for x in stale_jobs[:20]],
            "updated": len(updated_job_ids),
            "updated_job_ids": updated_job_ids[:50],
            "failures": job_failures[:50],
        },
        "issue_candidates": {
            "source": (str(args.issue_source).strip() or None),
            "statuses": issue_statuses,
            "cutoff_ts": issue_cutoff,
            "cutoff_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(issue_cutoff)),
            "listed": len(listed_issues),
            "stale": len(stale_issues),
            "by_project": _count_by_key(stale_issues, "project"),
            "by_kind": _count_by_key(stale_issues, "kind"),
            "sample_issue_ids": [str(x.get("issue_id") or "") for x in stale_issues[:20]],
            "updated": len(updated_ids),
            "updated_issue_ids": updated_ids[:50],
            "failures": failures[:50],
        },
    }

    report_path = Path(str(args.report_out)).expanduser()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({"ok": report["ok"], "report_path": str(report_path), "summary": report}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
