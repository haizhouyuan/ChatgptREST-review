#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.groundedness_checker import (
    GroundednessAuditRecord,
    extract_code_symbols,
    extract_paths,
    extract_relpaths,
    extract_units,
    infer_groundedness_weight_profile,
    weighted_groundedness_score,
)
from chatgptrest.evomap.knowledge.planning_review_plane import _has_runtime_grounding_anchors, _source_bucket
from chatgptrest.evomap.knowledge.schema import PromotionStatus
from ops.report_evomap_promotion_inventory import build_promotion_inventory, write_promotion_inventory_artifacts


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_bulk_groundedness_promotion"
DEFAULT_CANDIDATE_BUCKETS = (
    "planning_review_pack",
    "planning_latest_output",
    "planning_outputs",
    "planning_strategy",
    "planning_budget",
    "planning_controlled",
)
DEFAULT_PLANNING_ROOT = Path("/vol1/1000/projects/planning")
DEFAULT_PROJECT_ROOT = REPO_ROOT


@dataclass
class PlanningAtomRow:
    atom_id: str
    doc_id: str
    raw_ref: str
    title: str
    bucket: str
    promotion_status: str
    quality_auto: float
    groundedness: float
    valid_from: float
    canonical_question: str
    answer: str
    has_runtime_anchors: bool


@dataclass
class CachedGroundednessResult:
    path_score: float
    service_score: float
    staleness_score: float
    code_symbol_score: float
    overall_score: float
    weight_profile: str
    evidence: list[str]


@dataclass
class BulkStats:
    scanned: int = 0
    eligible_active: int = 0
    eligible_candidate: int = 0
    skipped_missing_canonical: int = 0
    skipped_non_planning_path: int = 0
    skipped_quality: int = 0
    skipped_bucket: int = 0
    scored: int = 0
    active_promotions: int = 0
    candidate_promotions: int = 0
    active_failures: int = 0
    candidate_retained: int = 0
    groundedness_updates: int = 0
    unchanged: int = 0
    buckets_scanned: Counter[str] = field(default_factory=Counter)
    buckets_active: Counter[str] = field(default_factory=Counter)
    buckets_candidate: Counter[str] = field(default_factory=Counter)


class SymbolIndex:
    def __init__(self, *, project_root: Path):
        self.project_root = project_root
        self.package_root = project_root / "chatgptrest"
        self.found_symbols: set[str] = set()
        self.defined_in: dict[str, str] = {}
        if not self.package_root.is_dir():
            return
        for py_file in self.package_root.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except Exception:
                continue
            for node in ast.walk(tree):
                name = None
                if isinstance(node, ast.ClassDef):
                    name = node.name
                elif isinstance(node, ast.FunctionDef):
                    name = node.name
                elif isinstance(node, ast.AsyncFunctionDef):
                    name = node.name
                if name:
                    self.found_symbols.add(name)
                    self.defined_in[name] = os.path.relpath(py_file, project_root)

    def score(self, symbols: list[str]) -> tuple[float, list[str]]:
        if not symbols:
            return 1.0, ["no_code_symbols_referenced"]
        matched = 0
        evidence: list[str] = []
        for symbol in symbols:
            if symbol in self.found_symbols:
                matched += 1
                evidence.append(f"✓ {symbol} ({self.defined_in.get(symbol, 'unknown')})")
            else:
                evidence.append(f"✗ {symbol}")
        return matched / len(symbols), evidence


class GroundednessCaches:
    def __init__(self, *, project_root: Path):
        self.project_root = project_root
        self.symbol_index = SymbolIndex(project_root=project_root)
        self.path_exists: dict[str, bool] = {}
        self.unit_exists: dict[str, bool] = {}
        self.file_mtime: dict[str, float | None] = {}

    def check_paths(self, paths: list[str]) -> tuple[float, list[str]]:
        if not paths:
            return 1.0, ["no_paths_referenced"]
        found = 0
        evidence: list[str] = []
        for path in paths:
            exists = self.path_exists.get(path)
            if exists is None:
                exists = os.path.exists(path)
                self.path_exists[path] = exists
            if exists:
                found += 1
                evidence.append(f"✓ {path}")
            else:
                evidence.append(f"✗ {path}")
        return found / len(paths), evidence

    def check_units(self, units: list[str]) -> tuple[float, list[str]]:
        if not units:
            return 1.0, ["no_units_referenced"]
        found = 0
        evidence: list[str] = []
        for unit in units:
            exists = self.unit_exists.get(unit)
            if exists is None:
                exists = False
                try:
                    user_result = subprocess.run(
                        ["systemctl", "--user", "list-unit-files", unit],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if unit in user_result.stdout:
                        exists = True
                    else:
                        system_result = subprocess.run(
                            ["systemctl", "list-unit-files", unit],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        exists = unit in system_result.stdout
                except Exception:
                    exists = False
                self.unit_exists[unit] = exists
            if exists:
                found += 1
                evidence.append(f"✓ {unit}")
            else:
                evidence.append(f"✗ {unit}")
        return found / len(units), evidence

    def check_staleness(self, paths: list[str], valid_from: float) -> tuple[float, list[str]]:
        if not paths or valid_from <= 0:
            return 1.0, ["no_staleness_check_needed"]
        checked = 0
        stale = 0
        evidence: list[str] = []
        for path in paths:
            if not os.path.isfile(path):
                continue
            mtime = self.file_mtime.get(path)
            if path not in self.file_mtime:
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    mtime = None
                self.file_mtime[path] = mtime
            if mtime is None:
                continue
            checked += 1
            if mtime > valid_from:
                stale += 1
                evidence.append(f"⚠ {path} modified after atom creation")
            else:
                evidence.append(f"✓ {path} unchanged")
        if checked == 0:
            return 1.0, ["no_checkable_files"]
        score = 1.0 - (stale / checked * 0.5)
        return max(0.0, score), evidence

    def score_atom(self, *, atom_id: str, answer: str, valid_from: float) -> CachedGroundednessResult:
        abs_paths = extract_paths(answer)
        rel_paths = extract_relpaths(answer, str(self.project_root))
        all_paths = sorted(set(abs_paths + rel_paths))
        units = extract_units(answer)
        code_symbols = extract_code_symbols(answer)
        path_score, path_ev = self.check_paths(all_paths)
        service_score, unit_ev = self.check_units(units)
        staleness_score, stale_ev = self.check_staleness(all_paths, valid_from)
        code_symbol_score, code_ev = self.symbol_index.score(code_symbols)
        weight_profile = infer_groundedness_weight_profile(
            scope_project="planning",
            doc_source="planning",
            atom_type="procedure",
            explicit_profile="planning",
        )
        overall, _ = weighted_groundedness_score(
            path_score=path_score,
            service_score=service_score,
            staleness_score=staleness_score,
            code_symbol_score=code_symbol_score,
            profile_name=weight_profile,
            has_paths=bool(all_paths),
            has_units=bool(units),
            has_valid_from=valid_from > 0,
            has_code_symbols=bool(code_symbols),
        )
        return CachedGroundednessResult(
            path_score=path_score,
            service_score=service_score,
            staleness_score=staleness_score,
            code_symbol_score=code_symbol_score,
            overall_score=overall,
            weight_profile=weight_profile,
            evidence=path_ev + unit_ev + stale_ev + code_ev,
        )


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _read_rows(
    *,
    db_path: str | Path,
    planning_root: Path,
    max_atoms: int,
    include_candidate: bool,
) -> list[PlanningAtomRow]:
    statuses = ["staged"]
    if include_candidate:
        statuses.append("candidate")
    placeholders = ",".join("?" for _ in statuses)
    limit_clause = ""
    params: list[Any] = [*statuses, f"{planning_root.as_posix()}/%"]
    if max_atoms > 0:
        limit_clause = "LIMIT ?"
        params.append(max_atoms)
    conn = _connect(db_path)
    rows = conn.execute(
        f"""
        SELECT
          a.atom_id,
          e.doc_id,
          d.raw_ref,
          d.title,
          COALESCE(json_extract(d.meta_json, '$.planning_review.source_bucket'), '') AS review_bucket,
          a.promotion_status,
          a.quality_auto,
          a.groundedness,
          a.valid_from,
          a.canonical_question,
          a.answer
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE d.source = 'planning'
          AND a.promotion_status IN ({placeholders})
          AND d.raw_ref LIKE ?
          AND COALESCE(a.canonical_question, '') != ''
        ORDER BY COALESCE(a.quality_auto, 0) DESC, a.atom_id
        {limit_clause}
        """,
        tuple(params),
    ).fetchall()
    conn.close()
    payload: list[PlanningAtomRow] = []
    for row in rows:
        bucket = str(row["review_bucket"] or "").strip() or _source_bucket(str(row["raw_ref"] or ""))
        answer = str(row["answer"] or "")
        payload.append(
            PlanningAtomRow(
                atom_id=str(row["atom_id"]),
                doc_id=str(row["doc_id"]),
                raw_ref=str(row["raw_ref"] or ""),
                title=str(row["title"] or ""),
                bucket=bucket,
                promotion_status=str(row["promotion_status"] or PromotionStatus.STAGED.value),
                quality_auto=float(row["quality_auto"] or 0.0),
                groundedness=float(row["groundedness"] or 0.0),
                valid_from=float(row["valid_from"] or 0.0),
                canonical_question=str(row["canonical_question"] or ""),
                answer=answer,
                has_runtime_anchors=_has_runtime_grounding_anchors(answer),
            )
        )
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _planning_counts(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN a.promotion_status='active' THEN 1 ELSE 0 END) AS active,
          SUM(CASE WHEN a.promotion_status='candidate' THEN 1 ELSE 0 END) AS candidate,
          SUM(CASE WHEN a.promotion_status='staged' THEN 1 ELSE 0 END) AS staged
        FROM atoms a
        JOIN episodes e ON e.episode_id = a.episode_id
        JOIN documents d ON d.doc_id = e.doc_id
        WHERE d.source='planning'
        """
    ).fetchone()
    return {
        "total": int(row["total"] or 0),
        "active": int(row["active"] or 0),
        "candidate": int(row["candidate"] or 0),
        "staged": int(row["staged"] or 0),
    }


def _insert_groundedness_audit(conn: sqlite3.Connection, record: GroundednessAuditRecord) -> None:
    row = record.to_row()
    conn.execute(
        """INSERT OR REPLACE INTO groundedness_audit
           (audit_id, atom_id, timestamp, passed, overall_score, path_score, service_score,
            staleness_score, code_symbol_score, evidence_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            row["audit_id"],
            row["atom_id"],
            row["timestamp"],
            row["passed"],
            row["overall_score"],
            row["path_score"],
            row["service_score"],
            row["staleness_score"],
            row["code_symbol_score"],
            row["evidence_json"],
        ),
    )


def _insert_promotion_audit(
    conn: sqlite3.Connection,
    *,
    atom_id: str,
    from_status: str,
    to_status: str,
    reason: str,
    groundedness_result: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO promotion_audit
        (audit_id, atom_id, from_status, to_status, reason, actor, groundedness_result, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"pa_{uuid.uuid4().hex[:12]}",
            atom_id,
            from_status,
            to_status,
            reason,
            "planning_bulk_runner",
            json.dumps(groundedness_result, ensure_ascii=False) if groundedness_result is not None else "",
            time.time(),
        ),
    )


def run_bulk_cycle(
    *,
    db_path: str | Path,
    output_root: Path,
    live: bool,
    max_atoms: int,
    batch_size: int,
    planning_root: Path,
    project_root: Path,
    min_quality_active: float,
    min_quality_candidate: float,
    groundedness_threshold: float,
    candidate_buckets: tuple[str, ...],
    include_candidate: bool,
    top_n: int = 20,
) -> dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    pre_inventory = build_promotion_inventory(db_path=db_path, top_n=top_n)
    pre_artifacts = write_promotion_inventory_artifacts(pre_inventory, run_dir / "pre_inventory", "pre")
    rows = _read_rows(
        db_path=db_path,
        planning_root=planning_root,
        max_atoms=max_atoms,
        include_candidate=include_candidate,
    )
    stats = BulkStats()
    active_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    caches = GroundednessCaches(project_root=project_root)
    conn = _connect(db_path)
    before_counts = _planning_counts(conn)
    writes_since_commit = 0

    for row in rows:
        stats.scanned += 1
        stats.buckets_scanned[row.bucket] += 1
        if not row.canonical_question.strip():
            stats.skipped_missing_canonical += 1
            continue
        if not row.raw_ref.startswith(f"{planning_root.as_posix()}/"):
            stats.skipped_non_planning_path += 1
            skipped_rows.append(
                {"atom_id": row.atom_id, "bucket": row.bucket, "reason": "non_planning_path", "raw_ref": row.raw_ref}
            )
            continue
        if row.has_runtime_anchors:
            if row.quality_auto < min_quality_active:
                stats.skipped_quality += 1
                continue
            stats.eligible_active += 1
            score = caches.score_atom(atom_id=row.atom_id, answer=row.answer, valid_from=row.valid_from)
            stats.scored += 1
            passed = score.overall_score >= groundedness_threshold
            audit_record = GroundednessAuditRecord(
                atom_id=row.atom_id,
                passed=passed,
                overall_score=score.overall_score,
                path_score=score.path_score,
                service_score=score.service_score,
                staleness_score=score.staleness_score,
                code_symbol_score=score.code_symbol_score,
                evidence_json=json.dumps(score.evidence, ensure_ascii=False),
            )
            active_rows.append(
                {
                    "atom_id": row.atom_id,
                    "doc_id": row.doc_id,
                    "bucket": row.bucket,
                    "quality_auto": f"{row.quality_auto:.3f}",
                    "weight_profile": score.weight_profile,
                    "overall_score": f"{score.overall_score:.3f}",
                    "passed": int(passed),
                    "raw_ref": row.raw_ref,
                }
            )
            if live:
                _insert_groundedness_audit(conn, audit_record)
                conn.execute("UPDATE atoms SET groundedness = ? WHERE atom_id = ?", (score.overall_score, row.atom_id))
                stats.groundedness_updates += 1
                writes_since_commit += 2
            if not passed:
                stats.active_failures += 1
                failure_rows.append(
                    {
                        "atom_id": row.atom_id,
                        "bucket": row.bucket,
                        "quality_auto": f"{row.quality_auto:.3f}",
                        "weight_profile": score.weight_profile,
                        "overall_score": f"{score.overall_score:.3f}",
                        "reason": f"groundedness<{groundedness_threshold:.2f}",
                        "raw_ref": row.raw_ref,
                    }
                )
            elif live and row.promotion_status != PromotionStatus.ACTIVE.value:
                conn.execute(
                    "UPDATE atoms SET promotion_status = ?, promotion_reason = ? WHERE atom_id = ?",
                    (
                        PromotionStatus.ACTIVE.value,
                        f"planning_bulk_active:{row.bucket}",
                        row.atom_id,
                    ),
                )
                _insert_promotion_audit(
                    conn,
                    atom_id=row.atom_id,
                    from_status=row.promotion_status,
                    to_status=PromotionStatus.ACTIVE.value,
                    reason=f"planning_bulk_active:{row.bucket}",
                    groundedness_result={"overall_score": score.overall_score, "threshold": groundedness_threshold},
                )
                stats.active_promotions += 1
                stats.buckets_active[row.bucket] += 1
                writes_since_commit += 2
            elif passed:
                stats.unchanged += 1
        else:
            if row.quality_auto < min_quality_candidate:
                stats.skipped_quality += 1
                continue
            if row.bucket not in set(candidate_buckets):
                stats.skipped_bucket += 1
                skipped_rows.append(
                    {"atom_id": row.atom_id, "bucket": row.bucket, "reason": "bucket_not_candidate_allowlist", "raw_ref": row.raw_ref}
                )
                continue
            stats.eligible_candidate += 1
            candidate_rows.append(
                {
                    "atom_id": row.atom_id,
                    "doc_id": row.doc_id,
                    "bucket": row.bucket,
                    "quality_auto": f"{row.quality_auto:.3f}",
                    "raw_ref": row.raw_ref,
                    "promotion_status": row.promotion_status,
                }
            )
            if live and row.promotion_status == PromotionStatus.STAGED.value:
                conn.execute(
                    "UPDATE atoms SET promotion_status = ?, promotion_reason = ? WHERE atom_id = ?",
                    (
                        PromotionStatus.CANDIDATE.value,
                        f"planning_bulk_candidate:{row.bucket}",
                        row.atom_id,
                    ),
                )
                _insert_promotion_audit(
                    conn,
                    atom_id=row.atom_id,
                    from_status=row.promotion_status,
                    to_status=PromotionStatus.CANDIDATE.value,
                    reason=f"planning_bulk_candidate:{row.bucket}",
                )
                stats.candidate_promotions += 1
                stats.buckets_candidate[row.bucket] += 1
                writes_since_commit += 2
            elif row.promotion_status == PromotionStatus.CANDIDATE.value:
                stats.candidate_retained += 1
            else:
                stats.unchanged += 1

        if live and writes_since_commit >= max(batch_size, 1):
            conn.commit()
            writes_since_commit = 0

    if live and writes_since_commit:
        conn.commit()

    after_counts = _planning_counts(conn)
    conn.close()

    post_inventory = build_promotion_inventory(db_path=db_path, top_n=top_n)
    post_artifacts = write_promotion_inventory_artifacts(post_inventory, run_dir / "post_inventory", "post")

    _write_tsv(
        run_dir / "active_evaluations.tsv",
        ["atom_id", "doc_id", "bucket", "quality_auto", "weight_profile", "overall_score", "passed", "raw_ref"],
        active_rows,
    )
    _write_tsv(
        run_dir / "candidate_eligibility.tsv",
        ["atom_id", "doc_id", "bucket", "quality_auto", "raw_ref", "promotion_status"],
        candidate_rows,
    )
    _write_tsv(
        run_dir / "active_failures.tsv",
        ["atom_id", "bucket", "quality_auto", "weight_profile", "overall_score", "reason", "raw_ref"],
        failure_rows,
    )
    _write_tsv(
        run_dir / "skipped_samples.tsv",
        ["atom_id", "bucket", "reason", "raw_ref"],
        skipped_rows[:500],
    )

    summary = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if live else "dry_run",
        "db_path": str(db_path),
        "run_dir": str(run_dir),
        "planning_root": str(planning_root),
        "project_root": str(project_root),
        "config": {
            "max_atoms": max_atoms,
            "batch_size": batch_size,
            "min_quality_active": min_quality_active,
            "min_quality_candidate": min_quality_candidate,
            "groundedness_threshold": groundedness_threshold,
            "candidate_buckets": list(candidate_buckets),
            "include_candidate": include_candidate,
        },
        "planning_counts_before": before_counts,
        "planning_counts_after": after_counts,
        "delta": {
            "active": after_counts["active"] - before_counts["active"],
            "candidate": after_counts["candidate"] - before_counts["candidate"],
            "staged": after_counts["staged"] - before_counts["staged"],
        },
        "stats": {
            "scanned": stats.scanned,
            "eligible_active": stats.eligible_active,
            "eligible_candidate": stats.eligible_candidate,
            "scored": stats.scored,
            "groundedness_updates": stats.groundedness_updates,
            "active_promotions": stats.active_promotions,
            "candidate_promotions": stats.candidate_promotions,
            "candidate_retained": stats.candidate_retained,
            "active_failures": stats.active_failures,
            "unchanged": stats.unchanged,
            "skipped_missing_canonical": stats.skipped_missing_canonical,
            "skipped_non_planning_path": stats.skipped_non_planning_path,
            "skipped_quality": stats.skipped_quality,
            "skipped_bucket": stats.skipped_bucket,
        },
        "bucket_breakdown": {
            "scanned": dict(stats.buckets_scanned),
            "active_promoted": dict(stats.buckets_active),
            "candidate_promoted": dict(stats.buckets_candidate),
        },
        "artifacts": {
            "pre_inventory": [str(path) for path in pre_artifacts],
            "post_inventory": [str(path) for path in post_artifacts],
            "active_evaluations": str(run_dir / "active_evaluations.tsv"),
            "candidate_eligibility": str(run_dir / "candidate_eligibility.tsv"),
            "active_failures": str(run_dir / "active_failures.tsv"),
            "skipped_samples": str(run_dir / "skipped_samples.tsv"),
        },
    }
    _write_json(run_dir / "summary.json", summary)
    readme_lines = [
        "# Planning Bulk Groundedness / Promotion",
        "",
        f"- `mode`: `{summary['mode']}`",
        f"- `planning_counts_before`: `{before_counts}`",
        f"- `planning_counts_after`: `{after_counts}`",
        f"- `delta.active`: `{summary['delta']['active']}`",
        f"- `delta.candidate`: `{summary['delta']['candidate']}`",
        f"- `eligible_active`: `{stats.eligible_active}`",
        f"- `eligible_candidate`: `{stats.eligible_candidate}`",
        f"- `active_promotions`: `{stats.active_promotions}`",
        f"- `candidate_promotions`: `{stats.candidate_promotions}`",
        f"- `active_failures`: `{stats.active_failures}`",
        "",
        "## Candidate Buckets",
        "",
        *(f"- `{bucket}`" for bucket in candidate_buckets),
    ]
    (run_dir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run planning-only bulk groundedness scoring and promotion with cached runtime checks.")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--planning-root", default=str(DEFAULT_PLANNING_ROOT))
    parser.add_argument("--project-root", default=str(DEFAULT_PROJECT_ROOT))
    parser.add_argument("--max-atoms", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--min-quality-active", type=float, default=0.6)
    parser.add_argument("--min-quality-candidate", type=float, default=0.7)
    parser.add_argument("--groundedness-threshold", type=float, default=0.6)
    parser.add_argument("--candidate-bucket", action="append", default=[], help="Repeat to extend/override the candidate bucket allowlist.")
    parser.add_argument("--live", action="store_true", help="Apply DB writes; dry-run is the default.")
    parser.add_argument("--no-candidate-scan", action="store_true", help="Ignore existing candidate atoms during scanning.")
    args = parser.parse_args()

    candidate_buckets = tuple(args.candidate_bucket) if args.candidate_bucket else DEFAULT_CANDIDATE_BUCKETS
    payload = run_bulk_cycle(
        db_path=args.db,
        output_root=Path(args.output_root),
        live=args.live,
        max_atoms=args.max_atoms,
        batch_size=args.batch_size,
        planning_root=Path(args.planning_root),
        project_root=Path(args.project_root),
        min_quality_active=args.min_quality_active,
        min_quality_candidate=args.min_quality_candidate,
        groundedness_threshold=args.groundedness_threshold,
        candidate_buckets=candidate_buckets,
        include_candidate=not args.no_candidate_scan,
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
