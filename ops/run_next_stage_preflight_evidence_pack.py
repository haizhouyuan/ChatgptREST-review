#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.planning_runtime_pack_search import (
    planning_runtime_pack_bundle_status,
)
from chatgptrest.evomap.knowledge.retrieval import retrieve, runtime_retrieval_config
from ops.report_evomap_promotion_inventory import build_promotion_inventory

try:
    import yaml
except Exception:  # pragma: no cover - repo runtime should already have pyyaml
    yaml = None


DEFAULT_CORPUS_PATH = REPO_ROOT / "ops" / "next_stage_project_retrieval_corpus_v1.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "next_stage_preflight"
DEFAULT_PLANNING_ROOT = Path("/vol1/1000/projects/planning")
STALE_DAYS_DEFAULT = 30


def _now() -> datetime:
    return datetime.now(UTC)


def _iso_from_ts(ts: float | int | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(float(ts), UTC).isoformat()


def _age_days_from_ts(ts: float | int | None) -> float | None:
    if not ts:
        return None
    delta = _now() - datetime.fromtimestamp(float(ts), UTC)
    return round(max(delta.total_seconds(), 0.0) / 86400.0, 3)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _query_rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def _query_value(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(query, params).fetchone()
    if row is None:
        return None
    return row[0]


def _safe_systemctl_lines(*args: str) -> list[str]:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:  # pragma: no cover - host-specific fallback
        return [f"error:{type(exc).__name__}:{exc}"]
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    err_lines = [line.strip() for line in proc.stderr.splitlines() if line.strip()]
    if not lines and err_lines:
        return err_lines
    return lines


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path} does not start with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{path} missing closing YAML frontmatter")
    raw = text[4:end]
    if yaml is None:
        raise RuntimeError("pyyaml is required for authority-anchor frontmatter parsing")
    loaded = yaml.safe_load(raw)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} frontmatter is not a mapping")
    return loaded


def _stale_status(*, age_days: float | None, stale_days: int) -> str:
    if age_days is None:
        return "unknown"
    return "stale" if age_days > stale_days else "fresh"


def build_scope_project_audit(conn: sqlite3.Connection) -> dict[str, Any]:
    counts = {
        "atoms_total": int(_query_value(conn, "SELECT COUNT(*) FROM atoms") or 0),
        "atoms_scope_project_nonblank": int(
            _query_value(conn, "SELECT COUNT(*) FROM atoms WHERE trim(ifnull(scope_project, '')) != ''") or 0
        ),
        "documents_total": int(_query_value(conn, "SELECT COUNT(*) FROM documents") or 0),
        "documents_project_nonblank": int(
            _query_value(conn, "SELECT COUNT(*) FROM documents WHERE trim(ifnull(project, '')) != ''") or 0
        ),
    }

    mismatches = _query_rows(
        conn,
        """
        SELECT
          a.scope_project AS atom_scope_project,
          d.project AS document_project,
          COUNT(*) AS atom_count
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE trim(ifnull(a.scope_project, '')) != ''
          AND trim(ifnull(d.project, '')) != ''
          AND trim(a.scope_project) != trim(d.project)
        GROUP BY atom_scope_project, document_project
        ORDER BY atom_count DESC, atom_scope_project, document_project
        """,
    )
    orphan_atoms = int(
        _query_value(
            conn,
            "SELECT COUNT(*) FROM atoms a LEFT JOIN episodes e ON e.episode_id = a.episode_id WHERE e.episode_id IS NULL",
        )
        or 0
    )
    orphan_episodes = int(
        _query_value(
            conn,
            "SELECT COUNT(*) FROM episodes e LEFT JOIN documents d ON d.doc_id = e.doc_id WHERE d.doc_id IS NULL",
        )
        or 0
    )
    documents_without_episodes = int(
        _query_value(
            conn,
            "SELECT COUNT(*) FROM documents d LEFT JOIN episodes e ON e.doc_id = d.doc_id WHERE e.episode_id IS NULL",
        )
        or 0
    )

    project_rows = _query_rows(
        conn,
        "SELECT trim(project) AS project, COUNT(*) AS doc_count FROM documents GROUP BY trim(project) ORDER BY doc_count DESC, project"
    )
    noisy_candidates: list[dict[str, Any]] = []
    for row in project_rows:
        project = str(row.get("project") or "")
        doc_count = int(row.get("doc_count") or 0)
        reasons: list[str] = []
        lowered = project.lower()
        if not project:
            reasons.append("blank")
        if project.startswith("/"):
            reasons.append("path_like")
        if "test" in lowered or lowered in {"unknown", "multi"}:
            reasons.append("generic_or_test_like")
        if doc_count <= 2 and re.search(r"20\d{6}", project):
            reasons.append("dated_low_volume_project")
        if doc_count <= 2 and len(project) > 40:
            reasons.append("long_low_volume_project")
        if reasons:
            noisy_candidates.append(
                {
                    "project": project,
                    "doc_count": doc_count,
                    "reasons": reasons,
                }
            )

    status = "safe"
    if orphan_atoms > 0 or orphan_episodes > 0:
        status = "conditional"
    if mismatches:
        status = "conditional"
    return {
        "counts": counts,
        "orphan_counts": {
            "orphan_atoms": orphan_atoms,
            "orphan_episodes": orphan_episodes,
            "documents_without_episodes": documents_without_episodes,
        },
        "mismatch_count": len(mismatches),
        "top_mismatches": mismatches[:25],
        "noisy_project_candidates": noisy_candidates[:50],
        "migration_safety": {
            "status": status,
            "note": (
                "safe only if backfill/update logic preserves existing nonblank scope_project values"
                if status == "safe"
                else "conditional: investigate mismatches/orphans before any broad write-back"
            ),
        },
    }


def build_promotion_diagnosis(conn: sqlite3.Connection, *, db_path: Path, top_n: int) -> dict[str, Any]:
    inventory = build_promotion_inventory(db_path=db_path, top_n=top_n)
    audit_counts = _query_rows(
        conn,
        """
        SELECT from_status, to_status, actor, COUNT(*) AS audit_count
        FROM promotion_audit
        GROUP BY from_status, to_status, actor
        ORDER BY audit_count DESC, actor, from_status, to_status
        """,
    )
    audit_window = _query_rows(
        conn,
        """
        SELECT
          MIN(created_at) AS first_created_at,
          MAX(created_at) AS last_created_at
        FROM promotion_audit
        """,
    )[0]
    groundedness_modes = _query_rows(
        conn,
        """
        SELECT
          CASE
            WHEN json_valid(groundedness_result) THEN COALESCE(json_extract(groundedness_result, '$.mode'), '')
            ELSE ''
          END AS mode,
          COUNT(*) AS audit_count
        FROM promotion_audit
        GROUP BY mode
        ORDER BY audit_count DESC, mode
        """,
    )
    groundedness_scores = _query_rows(
        conn,
        """
        SELECT
          CASE
            WHEN NOT json_valid(groundedness_result) THEN 'malformed'
            WHEN json_extract(groundedness_result, '$.overall_score') IS NULL THEN 'missing'
            WHEN CAST(json_extract(groundedness_result, '$.overall_score') AS REAL) < 0.5 THEN '<0.5'
            WHEN CAST(json_extract(groundedness_result, '$.overall_score') AS REAL) < 0.7 THEN '0.5-0.69'
            WHEN CAST(json_extract(groundedness_result, '$.overall_score') AS REAL) < 0.9 THEN '0.7-0.89'
            ELSE '>=0.9'
          END AS band,
          COUNT(*) AS audit_count
        FROM promotion_audit
        GROUP BY band
        ORDER BY audit_count DESC, band
        """,
    )
    staged_age = _query_rows(
        conn,
        """
        SELECT
          CASE
            WHEN d.updated_at = 0 THEN 'missing_timestamp'
            WHEN (strftime('%s','now') - d.updated_at) < 86400 THEN '<1d'
            WHEN (strftime('%s','now') - d.updated_at) < 7*86400 THEN '1-7d'
            WHEN (strftime('%s','now') - d.updated_at) < 30*86400 THEN '7-30d'
            WHEN (strftime('%s','now') - d.updated_at) < 90*86400 THEN '30-90d'
            ELSE '>=90d'
          END AS age_band,
          COUNT(*) AS atom_count
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE a.promotion_status = 'staged'
        GROUP BY age_band
        ORDER BY atom_count DESC, age_band
        """,
    )

    timer_name = "chatgptrest-planning-review-maintenance.timer"
    scheduling = {
        "is_enabled": _safe_systemctl_lines("is-enabled", timer_name),
        "is_active": _safe_systemctl_lines("is-active", timer_name),
        "list_timers": _safe_systemctl_lines("list-timers", "--all", timer_name, "--no-pager"),
    }

    dominant_failure_mode = "mixed_or_unknown"
    rationale = "promotion inventory needs both operational and content review"
    last_created_at = audit_window.get("last_created_at") or 0
    if float(last_created_at or 0) > 0:
        age_days = _age_days_from_ts(float(last_created_at))
    else:
        age_days = None
    enabled_text = " ".join(scheduling["is_enabled"]).lower()
    listed = any("timer" in line.lower() for line in scheduling["list_timers"])
    if (age_days is None or age_days > 7) and ("no such file" in enabled_text or not listed):
        dominant_failure_mode = "scheduling_absence"
        rationale = "promotion/maintenance timer is not installed or not scheduled, and promotion_audit has not advanced recently"
    elif inventory["counts"]["active"] <= 0 or inventory["rates"]["active_ratio"] < 0.005:
        dominant_failure_mode = "low_activation_coverage"
        rationale = "active coverage remains extremely low even though staged atoms are abundant"

    return {
        "inventory": inventory,
        "audit_transition_counts": audit_counts,
        "groundedness_modes": groundedness_modes,
        "groundedness_score_bands": groundedness_scores,
        "staged_age_distribution": staged_age,
        "audit_window": {
            "first_created_at": _iso_from_ts(audit_window.get("first_created_at")),
            "last_created_at": _iso_from_ts(audit_window.get("last_created_at")),
            "last_audit_age_days": age_days,
        },
        "scheduling_observation": scheduling,
        "dominant_failure_mode": dominant_failure_mode,
        "dominant_failure_rationale": rationale,
        "safe_stage_recommendations": [
            "treat promotion maintenance scheduling as a release-shape requirement before attempting any throughput optimization",
            "keep reviewed/maintenance paths observable and rerunnable before changing groundedness gates",
            "do not launch broad cleanup or score-threshold tuning from this report alone",
        ],
    }


@dataclass
class AuthorityDocStatus:
    path: str
    exists: bool
    non_empty: bool
    size_bytes: int
    modified_at: str
    age_days: float | None
    stale_status: str


def scan_authority_anchors(planning_root: Path, *, stale_days: int) -> dict[str, Any]:
    anchors = sorted(planning_root.rglob("_project_context.md"))
    results: list[dict[str, Any]] = []
    stale_or_missing: list[dict[str, Any]] = []
    for anchor in anchors:
        stat = anchor.stat()
        fm = _parse_frontmatter(anchor)
        authority_docs = [str(item).strip() for item in (fm.get("authority_docs") or []) if str(item).strip()]
        doc_statuses: list[dict[str, Any]] = []
        for raw in authority_docs:
            doc_path = Path(raw)
            exists = doc_path.exists()
            size_bytes = doc_path.stat().st_size if exists else 0
            modified_ts = doc_path.stat().st_mtime if exists else None
            status = AuthorityDocStatus(
                path=str(doc_path),
                exists=exists,
                non_empty=size_bytes > 0,
                size_bytes=size_bytes,
                modified_at=_iso_from_ts(modified_ts),
                age_days=_age_days_from_ts(modified_ts),
                stale_status=_stale_status(age_days=_age_days_from_ts(modified_ts), stale_days=stale_days),
            )
            doc_status = status.__dict__.copy()
            doc_statuses.append(doc_status)
            if not exists or not status.non_empty or status.stale_status == "stale":
                stale_or_missing.append(
                    {
                        "anchor": str(anchor),
                        "anchor_project": str(fm.get("project") or ""),
                        "authority_doc": status.path,
                        "exists": status.exists,
                        "non_empty": status.non_empty,
                        "stale_status": status.stale_status,
                        "age_days": status.age_days,
                    }
                )
        results.append(
            {
                "anchor_path": str(anchor),
                "project": str(fm.get("project") or ""),
                "alias": str(fm.get("alias") or ""),
                "project_id": str(fm.get("project_id") or ""),
                "updated": str(fm.get("updated") or ""),
                "anchor_modified_at": _iso_from_ts(stat.st_mtime),
                "anchor_age_days": _age_days_from_ts(stat.st_mtime),
                "authority_doc_count": len(doc_statuses),
                "authority_docs": doc_statuses,
            }
        )
    return {
        "stale_threshold_days": stale_days,
        "anchor_count": len(results),
        "anchors": results,
        "stale_or_missing": stale_or_missing,
    }


def load_retrieval_corpus(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError(f"invalid retrieval corpus at {path}")
    return payload


def build_retrieval_baseline(db_path: Path, corpus_path: Path) -> dict[str, Any]:
    db = KnowledgeDB(db_path=str(db_path))
    corpus = load_retrieval_corpus(corpus_path)
    cases_out: list[dict[str, Any]] = []
    for case in corpus["cases"]:
        project_id = str(case["project_id"])
        query = str(case["query"])
        scoped_hits = retrieve(
            db,
            query,
            config=runtime_retrieval_config(surface="diagnostic_path", project_id=project_id, result_limit=5),
        )
        unscoped_hits = retrieve(
            db,
            query,
            config=runtime_retrieval_config(surface="diagnostic_path", result_limit=5),
        )
        cases_out.append(
            {
                **case,
                "scoped_hit_count": len(scoped_hits),
                "unscoped_hit_count": len(unscoped_hits),
                "scoped_top_hits": [item.to_context_dict() | {"scope_project": item.atom.scope_project} for item in scoped_hits[:5]],
                "unscoped_top_hits": [item.to_context_dict() | {"scope_project": item.atom.scope_project} for item in unscoped_hits[:5]],
                "unscoped_project_mix": Counter(
                    str(item.atom.scope_project or "") or "unknown" for item in unscoped_hits[:5]
                ),
            }
        )
    return {
        "corpus_path": str(corpus_path),
        "cases": cases_out,
        "notes": corpus.get("notes") or [],
        "runner_reference": "ops/run_next_stage_preflight_evidence_pack.py --section retrieval",
    }


def build_documents_audit(conn: sqlite3.Connection) -> dict[str, Any]:
    low_volume_projects = _query_rows(
        conn,
        """
        SELECT project, COUNT(*) AS doc_count
        FROM documents
        GROUP BY project
        HAVING COUNT(*) <= 2
        ORDER BY doc_count ASC, project
        """,
    )
    duplicate_hash_same_project = _query_rows(
        conn,
        """
        SELECT project, hash, COUNT(*) AS doc_count
        FROM documents
        WHERE trim(hash) != ''
        GROUP BY project, hash
        HAVING COUNT(*) > 1
        ORDER BY doc_count DESC, project
        LIMIT 50
        """,
    )
    duplicate_hash_cross_project = _query_rows(
        conn,
        """
        SELECT hash, COUNT(DISTINCT project) AS project_count, COUNT(*) AS doc_count
        FROM documents
        WHERE trim(hash) != ''
        GROUP BY hash
        HAVING COUNT(DISTINCT project) > 1
        ORDER BY project_count DESC, doc_count DESC
        LIMIT 50
        """,
    )
    documents_without_episodes = _query_rows(
        conn,
        """
        SELECT d.project, d.doc_id, d.title, d.raw_ref
        FROM documents d
        LEFT JOIN episodes e ON e.doc_id = d.doc_id
        WHERE e.episode_id IS NULL
        ORDER BY d.project, d.doc_id
        LIMIT 100
        """,
    )
    return {
        "low_volume_projects": low_volume_projects,
        "duplicate_hash_same_project": duplicate_hash_same_project,
        "duplicate_hash_cross_project": duplicate_hash_cross_project,
        "documents_without_episodes": documents_without_episodes,
        "notes": [
            "This audit is read-only in the next-stage plan.",
            "It is intended to surface noise and duplication risk, not to trigger cleanup execution inside this release.",
        ],
    }


def build_planning_runtime_pack_audit() -> dict[str, Any]:
    status = planning_runtime_pack_bundle_status()
    pack_dir = Path(str(status.get("pack_dir") or ""))
    bundle_dir = Path(str(status.get("bundle_dir") or ""))
    manifest_ok = bundle_dir.joinpath("release_bundle_manifest.json").exists()
    files_present = {}
    pack_counts: dict[str, Any] = {}
    if pack_dir.exists():
        for name in ("manifest.json", "docs.tsv", "atoms.tsv", "retrieval_pack.json", "README.md", "smoke_manifest.json"):
            files_present[name] = pack_dir.joinpath(name).exists()
        try:
            with (pack_dir / "docs.tsv").open("r", encoding="utf-8", newline="") as fh:
                doc_count = sum(1 for _ in csv.DictReader(fh, delimiter="\t"))
        except Exception:
            doc_count = None
        try:
            with (pack_dir / "atoms.tsv").open("r", encoding="utf-8", newline="") as fh:
                atom_count = sum(1 for _ in csv.DictReader(fh, delimiter="\t"))
        except Exception:
            atom_count = None
        try:
            retrieval_pack = json.loads((pack_dir / "retrieval_pack.json").read_text(encoding="utf-8"))
            retrieval_atom_count = len(retrieval_pack.get("atom_ids") or [])
        except Exception:
            retrieval_atom_count = None
        pack_counts = {
            "docs_tsv_rows": doc_count,
            "atoms_tsv_rows": atom_count,
            "retrieval_pack_atom_ids": retrieval_atom_count,
        }
    return {
        "bundle_status": status,
        "release_bundle_manifest_exists": manifest_ok,
        "pack_files_present": files_present,
        "pack_counts": pack_counts,
        "notes": [
            "This is a read-only audit.",
            "Semantic freshness of planning decisions still requires manual review even when bundle structure is healthy.",
        ],
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_reports(output_dir: Path, summary: dict[str, Any]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "preflight_summary.json"
    _write_json(json_path, summary)

    md_lines = [
        "# Next-Stage Preflight Evidence Pack",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- db_path: `{summary['db_path']}`",
        "",
        "## Scope Project Audit",
        "",
        f"- atoms_total: `{summary['scope_project_audit']['counts']['atoms_total']}`",
        f"- scope_project_nonblank: `{summary['scope_project_audit']['counts']['atoms_scope_project_nonblank']}`",
        f"- mismatch_count: `{summary['scope_project_audit']['mismatch_count']}`",
        f"- orphan_atoms: `{summary['scope_project_audit']['orphan_counts']['orphan_atoms']}`",
        f"- migration_safety: `{summary['scope_project_audit']['migration_safety']['status']}`",
        "",
        "## Promotion Diagnosis",
        "",
        f"- dominant_failure_mode: `{summary['promotion_diagnosis']['dominant_failure_mode']}`",
        f"- active_ratio: `{summary['promotion_diagnosis']['inventory']['rates']['active_ratio']}`",
        f"- last_audit_age_days: `{summary['promotion_diagnosis']['audit_window']['last_audit_age_days']}`",
        "",
        "## Authority Anchors",
        "",
        f"- anchor_count: `{summary['authority_integrity']['anchor_count']}`",
        f"- stale_or_missing_count: `{len(summary['authority_integrity']['stale_or_missing'])}`",
        "",
        "## Retrieval Baseline",
        "",
    ]
    for case in summary["retrieval_baseline"]["cases"]:
        md_lines.append(
            f"- `{case['case_id']}` scoped_hits={case['scoped_hit_count']} "
            f"unscoped_hits={case['unscoped_hit_count']} expected_project=`{case['expected_primary_project']}`"
        )
    md_lines.extend(
        [
            "",
            "## Planning Runtime Pack Audit",
            "",
            f"- bundle_available: `{summary['planning_runtime_pack_audit']['bundle_status']['available']}`",
            f"- ready_for_explicit_consumption: `{summary['planning_runtime_pack_audit']['bundle_status']['ready_for_explicit_consumption']}`",
            f"- bundle_freshness: `{summary['planning_runtime_pack_audit']['bundle_status']['bundle_freshness']}`",
        ]
    )
    md_path = output_dir / "preflight_summary.md"
    _write_markdown(md_path, md_lines)
    return {"json": str(json_path), "markdown": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the next-stage preflight evidence pack.")
    parser.add_argument("--db", default=str(resolve_evomap_knowledge_runtime_db_path()))
    parser.add_argument("--planning-root", default=str(DEFAULT_PLANNING_ROOT))
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS_PATH))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--stale-days", type=int, default=STALE_DAYS_DEFAULT)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--section", choices=["all", "scope", "promotion", "authority", "retrieval", "documents", "planning-pack"], default="all")
    args = parser.parse_args()

    stamp = _now().strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_ROOT / stamp
    db_path = Path(args.db).expanduser().resolve()
    conn = _connect(db_path)
    try:
        summary: dict[str, Any] = {
            "generated_at": _now().isoformat(),
            "db_path": str(db_path),
            "sections": {},
        }
        if args.section in {"all", "scope"}:
            summary["scope_project_audit"] = build_scope_project_audit(conn)
            summary["sections"]["scope_project_audit"] = "included"
        if args.section in {"all", "promotion"}:
            summary["promotion_diagnosis"] = build_promotion_diagnosis(conn, db_path=db_path, top_n=args.top_n)
            summary["sections"]["promotion_diagnosis"] = "included"
        if args.section in {"all", "authority"}:
            summary["authority_integrity"] = scan_authority_anchors(Path(args.planning_root), stale_days=args.stale_days)
            summary["sections"]["authority_integrity"] = "included"
        if args.section in {"all", "retrieval"}:
            summary["retrieval_baseline"] = build_retrieval_baseline(db_path, Path(args.corpus))
            summary["sections"]["retrieval_baseline"] = "included"
        if args.section in {"all", "documents"}:
            summary["documents_audit"] = build_documents_audit(conn)
            summary["sections"]["documents_audit"] = "included"
        if args.section in {"all", "planning-pack"}:
            summary["planning_runtime_pack_audit"] = build_planning_runtime_pack_audit()
            summary["sections"]["planning_runtime_pack_audit"] = "included"
    finally:
        conn.close()

    artifact_paths = write_reports(output_dir, summary)
    payload = {
        "ok": True,
        "output_dir": str(output_dir),
        "artifact_paths": artifact_paths,
        "summary": summary,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
