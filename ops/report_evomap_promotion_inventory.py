#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path

DEFAULT_CRITICAL_ROLLOUT_SOURCE = "planning"
DEFAULT_CRITICAL_ROLLOUT_BUCKETS = (
    "planning_review_pack",
    "planning_latest_output",
    "planning_outputs",
    "planning_strategy",
    "planning_controlled",
    "planning_budget",
)


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def _critical_rollout_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    placeholders = ",".join("?" for _ in DEFAULT_CRITICAL_ROLLOUT_BUCKETS)
    params: tuple[Any, ...] = (DEFAULT_CRITICAL_ROLLOUT_SOURCE, *DEFAULT_CRITICAL_ROLLOUT_BUCKETS)
    bucket_status = _rows(
        conn,
        f"""
        select
          coalesce(json_extract(d.meta_json, '$.planning_review.source_bucket'), '') as bucket,
          sum(case when a.promotion_status='active' then 1 else 0 end) as active_atoms,
          sum(case when a.promotion_status='candidate' then 1 else 0 end) as candidate_atoms,
          sum(case when a.promotion_status='staged' then 1 else 0 end) as staged_atoms
        from atoms a
        join episodes e on e.episode_id = a.episode_id
        join documents d on d.doc_id = e.doc_id
        where d.source = ?
          and coalesce(json_extract(d.meta_json, '$.planning_review.source_bucket'), '') in ({placeholders})
        group by bucket
        order by staged_atoms desc, bucket
        """,
        params,
    )
    total = sum(int(row["active_atoms"] or 0) + int(row["candidate_atoms"] or 0) + int(row["staged_atoms"] or 0) for row in bucket_status)
    active = sum(int(row["active_atoms"] or 0) for row in bucket_status)
    candidate = sum(int(row["candidate_atoms"] or 0) for row in bucket_status)
    staged = sum(int(row["staged_atoms"] or 0) for row in bucket_status)
    buckets_without_servable = [
        row for row in bucket_status if int(row["staged_atoms"] or 0) > 0 and int(row["active_atoms"] or 0) + int(row["candidate_atoms"] or 0) == 0
    ]
    buckets_without_active = [
        row for row in bucket_status if int(row["staged_atoms"] or 0) > 0 and int(row["active_atoms"] or 0) == 0
    ]
    return {
        "source": DEFAULT_CRITICAL_ROLLOUT_SOURCE,
        "buckets": list(DEFAULT_CRITICAL_ROLLOUT_BUCKETS),
        "counts": {
            "total": total,
            "active": active,
            "candidate": candidate,
            "staged": staged,
            "servable": active + candidate,
        },
        "rates": {
            "active_ratio": round(active / total, 6) if total else 0.0,
            "candidate_ratio": round(candidate / total, 6) if total else 0.0,
            "staged_ratio": round(staged / total, 6) if total else 0.0,
            "servable_ratio": round((active + candidate) / total, 6) if total else 0.0,
        },
        "bucket_status": bucket_status,
        "buckets_without_servable_atoms": buckets_without_servable,
        "buckets_without_active_atoms": buckets_without_active,
        "bounded_to_noncritical_only": not buckets_without_servable and not buckets_without_active,
    }


def build_promotion_inventory(*, db_path: str | Path, top_n: int = 20, recent_window_days: int = 7) -> dict[str, Any]:
    conn = _connect(db_path)
    recent_cutoff = float(time.time() - max(1, int(recent_window_days)) * 86400)
    counts_row = conn.execute(
        """
        select
          count(*) as atoms,
          sum(case when promotion_status='active' then 1 else 0 end) as active,
          sum(case when promotion_status='candidate' then 1 else 0 end) as candidate,
          sum(case when promotion_status='staged' then 1 else 0 end) as staged,
          sum(case when promotion_status='archived' then 1 else 0 end) as archived,
          sum(case when promotion_status='superseded' then 1 else 0 end) as superseded
        from atoms
        """
    ).fetchone()
    document_count = conn.execute("select count(*) from documents").fetchone()[0]
    promotion_audit_count = conn.execute("select count(*) from promotion_audit").fetchone()[0]
    groundedness_audit_count = conn.execute("select count(*) from groundedness_audit").fetchone()[0]
    distinct_projects = conn.execute(
        """
        select count(distinct nullif(trim(coalesce(a.scope_project, d.project)), ''))
        from atoms a
        join episodes e on e.episode_id = a.episode_id
        join documents d on d.doc_id = e.doc_id
        """
    ).fetchone()[0]

    by_source_status = _rows(
        conn,
        """
        select
          d.source as source,
          a.promotion_status as promotion_status,
          count(*) as atom_count
        from atoms a
        join episodes e on e.episode_id = a.episode_id
        join documents d on d.doc_id = e.doc_id
        group by d.source, a.promotion_status
        order by atom_count desc, source, promotion_status
        """,
    )
    by_project_status = _rows(
        conn,
        """
        select
          coalesce(nullif(trim(a.scope_project), ''), d.project, '') as project,
          a.promotion_status as promotion_status,
          count(*) as atom_count
        from atoms a
        join episodes e on e.episode_id = a.episode_id
        join documents d on d.doc_id = e.doc_id
        group by project, a.promotion_status
        order by atom_count desc, project, promotion_status
        """,
    )
    by_source_reason = _rows(
        conn,
        """
        select
          d.source as source,
          coalesce(a.promotion_reason, '') as promotion_reason,
          count(*) as atom_count
        from atoms a
        join episodes e on e.episode_id = a.episode_id
        join documents d on d.doc_id = e.doc_id
        group by d.source, coalesce(a.promotion_reason, '')
        order by atom_count desc, source, promotion_reason
        limit ?
        """,
        (top_n * 5,),
    )
    sources_without_active = _rows(
        conn,
        """
        select
          d.source as source,
          sum(case when a.promotion_status='active' then 1 else 0 end) as active_atoms,
          sum(case when a.promotion_status='candidate' then 1 else 0 end) as candidate_atoms,
          sum(case when a.promotion_status='staged' then 1 else 0 end) as staged_atoms
        from atoms a
        join episodes e on e.episode_id = a.episode_id
        join documents d on d.doc_id = e.doc_id
        group by d.source
        having staged_atoms > 0 and active_atoms = 0
        order by staged_atoms desc, source
        limit ?
        """,
        (top_n,),
    )
    projects_without_active = _rows(
        conn,
        """
        select
          coalesce(nullif(trim(a.scope_project), ''), d.project, '') as project,
          sum(case when a.promotion_status='active' then 1 else 0 end) as active_atoms,
          sum(case when a.promotion_status='candidate' then 1 else 0 end) as candidate_atoms,
          sum(case when a.promotion_status='staged' then 1 else 0 end) as staged_atoms
        from atoms a
        join episodes e on e.episode_id = a.episode_id
        join documents d on d.doc_id = e.doc_id
        group by project
        having staged_atoms > 0 and active_atoms = 0
        order by staged_atoms desc, project
        limit ?
        """,
        (top_n,),
    )
    blank_reason_staged = conn.execute(
        """
        select count(*)
        from atoms
        where promotion_status='staged'
          and trim(coalesce(promotion_reason, '')) = ''
        """
    ).fetchone()[0]
    recent_row = conn.execute(
        """
        select
          sum(case when promotion_status='staged' and valid_from>=? then 1 else 0 end) as recent_staged,
          sum(case when promotion_status='staged' and valid_from>=? and trim(coalesce(promotion_reason, '')) = '' then 1 else 0 end) as recent_blank,
          sum(case when promotion_status='staged' and valid_from>=? and trim(coalesce(promotion_reason, '')) <> '' then 1 else 0 end) as recent_nonblank
        from atoms
        """,
        (recent_cutoff, recent_cutoff, recent_cutoff),
    ).fetchone()
    recent_sources = _rows(
        conn,
        """
        select
          d.source as source,
          count(*) as recent_staged_atoms,
          sum(case when trim(coalesce(a.promotion_reason, '')) = '' then 1 else 0 end) as recent_blank_reason_atoms
        from atoms a
        join episodes e on e.episode_id = a.episode_id
        join documents d on d.doc_id = e.doc_id
        where a.promotion_status='staged'
          and a.valid_from>=?
        group by d.source
        order by recent_staged_atoms desc, source
        limit ?
        """,
        (recent_cutoff, top_n),
    )
    active_atoms = int(counts_row["active"] or 0)
    total_atoms = int(counts_row["atoms"] or 0)
    recent_staged = int(recent_row[0] or 0)
    recent_blank = int(recent_row[1] or 0)
    summary = {
        "db_path": str(db_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "documents": int(document_count or 0),
            "atoms": total_atoms,
            "active": active_atoms,
            "candidate": int(counts_row["candidate"] or 0),
            "staged": int(counts_row["staged"] or 0),
            "archived": int(counts_row["archived"] or 0),
            "superseded": int(counts_row["superseded"] or 0),
            "promotion_audit": int(promotion_audit_count or 0),
            "groundedness_audit": int(groundedness_audit_count or 0),
            "projects": int(distinct_projects or 0),
        },
        "rates": {
            "active_ratio": round(active_atoms / total_atoms, 6) if total_atoms else 0.0,
            "candidate_ratio": round(float(counts_row["candidate"] or 0) / total_atoms, 6) if total_atoms else 0.0,
            "staged_ratio": round(float(counts_row["staged"] or 0) / total_atoms, 6) if total_atoms else 0.0,
            "recent_blank_promotion_reason_ratio": round(recent_blank / recent_staged, 6) if recent_staged else 0.0,
        },
        "by_source_status": by_source_status,
        "by_project_status": by_project_status,
        "by_source_reason": by_source_reason,
        "critical_rollout": _critical_rollout_summary(conn),
        "likely_blockers": {
            "blank_promotion_reason_staged_atoms": int(blank_reason_staged or 0),
            "recent_window_days": int(recent_window_days),
            "recent_staged_atoms": recent_staged,
            "recent_blank_promotion_reason_staged_atoms": recent_blank,
            "recent_nonblank_promotion_reason_staged_atoms": int(recent_row[2] or 0),
            "recent_blank_promotion_reason_ratio": round(recent_blank / recent_staged, 6) if recent_staged else 0.0,
            "recent_sources": recent_sources,
            "sources_without_active_atoms": sources_without_active,
            "projects_without_active_atoms": projects_without_active,
            "promotion_audit_count": int(promotion_audit_count or 0),
            "groundedness_audit_count": int(groundedness_audit_count or 0),
        },
    }
    conn.close()
    return summary


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_promotion_inventory_artifacts(summary: dict[str, Any], output_dir: str | Path, stamp: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / f"promotion_inventory_{stamp}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    source_status_path = out / f"promotion_source_status_{stamp}.csv"
    _write_csv(source_status_path, ["source", "promotion_status", "atom_count"], summary["by_source_status"])

    project_status_path = out / f"promotion_project_status_{stamp}.csv"
    _write_csv(project_status_path, ["project", "promotion_status", "atom_count"], summary["by_project_status"])

    source_reason_path = out / f"promotion_source_reason_{stamp}.csv"
    _write_csv(source_reason_path, ["source", "promotion_reason", "atom_count"], summary["by_source_reason"])

    blockers_path = out / f"promotion_blockers_{stamp}.md"
    blockers = summary["likely_blockers"]
    critical = summary["critical_rollout"]
    blockers_lines = [
        "# EvoMap Promotion Inventory",
        "",
        f"- `db_path`: `{summary['db_path']}`",
        f"- `atoms`: `{summary['counts']['atoms']}`",
        f"- `active`: `{summary['counts']['active']}`",
        f"- `candidate`: `{summary['counts']['candidate']}`",
        f"- `staged`: `{summary['counts']['staged']}`",
        f"- `active_ratio`: `{summary['rates']['active_ratio']}`",
        f"- `blank_promotion_reason_staged_atoms`: `{blockers['blank_promotion_reason_staged_atoms']}`",
        f"- `recent_window_days`: `{blockers['recent_window_days']}`",
        f"- `recent_staged_atoms`: `{blockers['recent_staged_atoms']}`",
        f"- `recent_blank_promotion_reason_staged_atoms`: `{blockers['recent_blank_promotion_reason_staged_atoms']}`",
        f"- `recent_blank_promotion_reason_ratio`: `{blockers['recent_blank_promotion_reason_ratio']}`",
        f"- `promotion_audit_count`: `{blockers['promotion_audit_count']}`",
        "",
        "## Critical Rollout Buckets",
        "",
        f"- `critical_source`: `{critical['source']}`",
        f"- `critical_buckets`: `{', '.join(critical['buckets'])}`",
        f"- `critical_total`: `{critical['counts']['total']}`",
        f"- `critical_servable`: `{critical['counts']['servable']}`",
        f"- `critical_active`: `{critical['counts']['active']}`",
        f"- `critical_candidate`: `{critical['counts']['candidate']}`",
        f"- `critical_staged`: `{critical['counts']['staged']}`",
        f"- `critical_servable_ratio`: `{critical['rates']['servable_ratio']}`",
        "",
        "### Critical buckets without servable atoms",
        "",
    ]
    if critical["buckets_without_servable_atoms"]:
        blockers_lines.extend(
            f"- `{row['bucket']}` staged={row['staged_atoms']} candidate={row['candidate_atoms']} active={row['active_atoms']}"
            for row in critical["buckets_without_servable_atoms"]
        )
    else:
        blockers_lines.append("- none")
    blockers_lines.extend(
        [
            "",
            "### Critical buckets without active atoms",
            "",
        ]
    )
    if critical["buckets_without_active_atoms"]:
        blockers_lines.extend(
            f"- `{row['bucket']}` staged={row['staged_atoms']} candidate={row['candidate_atoms']} active={row['active_atoms']}"
            for row in critical["buckets_without_active_atoms"]
        )
    else:
        blockers_lines.append("- none")
    blockers_lines.extend(
        [
            "",
            "## Recent Sources",
            "",
        ]
    )
    if blockers["recent_sources"]:
        blockers_lines.extend(
            f"- `{row['source']}` recent_staged={row['recent_staged_atoms']} recent_blank_reason={row['recent_blank_reason_atoms']}"
            for row in blockers["recent_sources"]
        )
    else:
        blockers_lines.append("- none")
    blockers_lines.extend(
        [
            "",
            "## Sources Without Active Atoms",
            "",
        ]
    )
    if blockers["sources_without_active_atoms"]:
        blockers_lines.extend(
            f"- `{row['source']}` staged={row['staged_atoms']} candidate={row['candidate_atoms']} active={row['active_atoms']}"
            for row in blockers["sources_without_active_atoms"]
        )
    else:
        blockers_lines.append("- none")
    blockers_lines.extend(["", "## Projects Without Active Atoms", ""])
    if blockers["projects_without_active_atoms"]:
        blockers_lines.extend(
            f"- `{row['project']}` staged={row['staged_atoms']} candidate={row['candidate_atoms']} active={row['active_atoms']}"
            for row in blockers["projects_without_active_atoms"]
        )
    else:
        blockers_lines.append("- none")
    blockers_path.write_text("\n".join(blockers_lines) + "\n", encoding="utf-8")

    return [summary_path, source_status_path, project_status_path, source_reason_path, blockers_path]


def main() -> int:
    parser = argparse.ArgumentParser(description="Report EvoMap promotion inventory with source/project/status breakdowns.")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--stamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--recent-window-days", type=int, default=7)
    args = parser.parse_args()

    summary = build_promotion_inventory(
        db_path=args.db,
        top_n=args.top_n,
        recent_window_days=int(args.recent_window_days),
    )
    payload: dict[str, Any] = {"ok": True, "summary": summary}
    if args.output_dir:
        payload["artifacts"] = [str(path) for path in write_promotion_inventory_artifacts(summary, args.output_dir, args.stamp)]
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
