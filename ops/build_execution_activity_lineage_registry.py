#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _hash16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _lineage_status(task_ref: str, trace_id: str) -> str:
    if task_ref and trace_id:
        return "complete"
    if task_ref:
        return "task_only"
    if trace_id:
        return "trace_only"
    return "missing_core"


def _family_id(task_ref: str, trace_id: str, atom_id: str) -> str:
    if task_ref:
        return f"execfam_task_{_hash16(task_ref)}"
    if trace_id:
        return f"execfam_trace_{_hash16(trace_id)}"
    return f"execfam_missing_{_hash16(atom_id)}"


def _lineage_action(status: str, episode_type: str) -> str:
    if status == "complete":
        return "keep_lineage"
    if status in {"task_only", "trace_only"}:
        return "backfill_missing_anchor"
    if episode_type in {"agent.git.commit", "agent.task.closeout"}:
        return "archive_only_until_anchor_available"
    return "manual_lineage_review"


def _suggested_bucket(atom_type: str, episode_type: str) -> str:
    normalized = atom_type.strip().lower()
    if normalized in {"lesson", "procedure", "correction"}:
        return normalized
    if episode_type == "workflow.failed":
        return "correction"
    return "review_only"


def _json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def build_lineage_registry(*, db_path: str | Path, limit: int = 1000) -> dict[str, Any]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
              a.atom_id,
              a.atom_type,
              a.status,
              a.promotion_status,
              a.canonical_question,
              a.answer,
              a.valid_from,
              d.source,
              e.episode_type,
              e.source_ext,
              json_extract(a.applicability, '$.task_ref') AS task_ref,
              json_extract(a.applicability, '$.trace_id') AS trace_id,
              json_extract(a.applicability, '$.lane_id') AS lane_id,
              json_extract(a.applicability, '$.role_id') AS role_id,
              json_extract(a.applicability, '$.adapter_id') AS adapter_id,
              json_extract(a.applicability, '$.profile_id') AS profile_id,
              json_extract(a.applicability, '$.executor_kind') AS executor_kind
            FROM atoms a
            JOIN episodes e ON e.episode_id = a.episode_id
            JOIN documents d ON d.doc_id = e.doc_id
            WHERE a.promotion_reason = 'activity_ingest'
            ORDER BY a.valid_from DESC, a.atom_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    atom_rows: list[dict[str, Any]] = []
    family_index: dict[str, dict[str, Any]] = {}
    trace_index: dict[tuple[str, str], dict[str, Any]] = {}
    gap_rows: list[dict[str, Any]] = []

    for row in rows:
        task_ref = str(row["task_ref"] or "")
        trace_id = str(row["trace_id"] or "")
        atom_id = str(row["atom_id"])
        episode_type = str(row["episode_type"] or "")
        atom_type = str(row["atom_type"] or "")
        lineage_status = _lineage_status(task_ref, trace_id)
        family_id = _family_id(task_ref, trace_id, atom_id)
        source_ext = _json_loads(row["source_ext"])
        provider = str(source_ext.get("provider") or "")
        model = str(source_ext.get("model") or "")

        atom_payload = {
            "atom_id": atom_id,
            "source": str(row["source"] or ""),
            "episode_type": episode_type,
            "atom_type": atom_type,
            "status": str(row["status"] or ""),
            "promotion_status": str(row["promotion_status"] or ""),
            "task_ref": task_ref,
            "trace_id": trace_id,
            "lane_id": str(row["lane_id"] or ""),
            "role_id": str(row["role_id"] or ""),
            "adapter_id": str(row["adapter_id"] or ""),
            "profile_id": str(row["profile_id"] or ""),
            "executor_kind": str(row["executor_kind"] or ""),
            "provider": provider,
            "model": model,
            "lineage_family_id": family_id,
            "lineage_status": lineage_status,
            "lineage_action": _lineage_action(lineage_status, episode_type),
            "suggested_bucket": _suggested_bucket(atom_type, episode_type),
            "canonical_question": str(row["canonical_question"] or ""),
            "answer_preview": str(row["answer"] or "")[:200],
            "valid_from": float(row["valid_from"] or 0.0),
        }
        atom_rows.append(atom_payload)

        family = family_index.setdefault(
            family_id,
            {
                "lineage_family_id": family_id,
                "task_ref": task_ref,
                "lineage_status": lineage_status,
                "atom_count": 0,
                "review_ready_atoms": 0,
                "trace_ids": set(),
                "sources": Counter(),
                "episode_types": Counter(),
                "first_valid_from": None,
                "last_valid_from": None,
            },
        )
        family["atom_count"] += 1
        if task_ref and trace_id and atom_payload["canonical_question"]:
            family["review_ready_atoms"] += 1
        if trace_id:
            family["trace_ids"].add(trace_id)
        family["sources"][atom_payload["source"]] += 1
        family["episode_types"][episode_type] += 1
        valid_from = atom_payload["valid_from"]
        if family["first_valid_from"] is None or valid_from < family["first_valid_from"]:
            family["first_valid_from"] = valid_from
        if family["last_valid_from"] is None or valid_from > family["last_valid_from"]:
            family["last_valid_from"] = valid_from

        if trace_id:
            trace = trace_index.setdefault(
                (family_id, trace_id),
                {
                    "lineage_family_id": family_id,
                    "trace_id": trace_id,
                    "task_ref": task_ref,
                    "lineage_status": lineage_status,
                    "atom_count": 0,
                    "episode_types": Counter(),
                    "first_valid_from": None,
                    "last_valid_from": None,
                },
            )
            trace["atom_count"] += 1
            trace["episode_types"][episode_type] += 1
            if trace["first_valid_from"] is None or valid_from < trace["first_valid_from"]:
                trace["first_valid_from"] = valid_from
            if trace["last_valid_from"] is None or valid_from > trace["last_valid_from"]:
                trace["last_valid_from"] = valid_from

        if lineage_status != "complete":
            missing_fields = []
            if not task_ref:
                missing_fields.append("task_ref")
            if not trace_id:
                missing_fields.append("trace_id")
            gap_rows.append(
                {
                    "atom_id": atom_id,
                    "source": atom_payload["source"],
                    "episode_type": episode_type,
                    "atom_type": atom_type,
                    "task_ref": task_ref,
                    "trace_id": trace_id,
                    "missing_fields": ",".join(missing_fields),
                    "lineage_status": lineage_status,
                    "lineage_action": atom_payload["lineage_action"],
                    "provider": provider,
                    "model": model,
                    "canonical_question": atom_payload["canonical_question"],
                    "answer_preview": atom_payload["answer_preview"],
                    "valid_from": valid_from,
                }
            )

    family_rows = []
    for family in sorted(family_index.values(), key=lambda item: (-item["review_ready_atoms"], -item["atom_count"], item["lineage_family_id"])):
        family_rows.append(
            {
                "lineage_family_id": family["lineage_family_id"],
                "task_ref": family["task_ref"],
                "lineage_status": family["lineage_status"],
                "atom_count": family["atom_count"],
                "review_ready_atoms": family["review_ready_atoms"],
                "trace_count": len(family["trace_ids"]),
                "sources": json.dumps(dict(sorted(family["sources"].items())), ensure_ascii=False, sort_keys=True),
                "episode_types": json.dumps(dict(sorted(family["episode_types"].items())), ensure_ascii=False, sort_keys=True),
                "first_valid_from": float(family["first_valid_from"] or 0.0),
                "last_valid_from": float(family["last_valid_from"] or 0.0),
            }
        )

    trace_rows = []
    for trace in sorted(trace_index.values(), key=lambda item: (-item["atom_count"], item["lineage_family_id"], item["trace_id"])):
        trace_rows.append(
            {
                "lineage_family_id": trace["lineage_family_id"],
                "trace_id": trace["trace_id"],
                "task_ref": trace["task_ref"],
                "lineage_status": trace["lineage_status"],
                "atom_count": trace["atom_count"],
                "episode_types": json.dumps(dict(sorted(trace["episode_types"].items())), ensure_ascii=False, sort_keys=True),
                "first_valid_from": float(trace["first_valid_from"] or 0.0),
                "last_valid_from": float(trace["last_valid_from"] or 0.0),
            }
        )

    summary = {
        "db_path": str(db_path),
        "selected_atoms": len(atom_rows),
        "lineage_families": len(family_rows),
        "trace_runs": len(trace_rows),
        "review_ready_atoms": sum(1 for row in atom_rows if row["lineage_status"] == "complete" and row["canonical_question"]),
        "gap_atoms": len(gap_rows),
        "status_counts": dict(Counter(row["lineage_status"] for row in atom_rows)),
        "suggested_bucket_counts": dict(Counter(row["suggested_bucket"] for row in atom_rows)),
    }
    return {
        "summary": summary,
        "families": family_rows,
        "traces": trace_rows,
        "gaps": gap_rows,
        "atoms": atom_rows,
    }


def write_lineage_registry(report: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    summary_path = out / "lineage_summary.json"
    families_json = out / "lineage_family_registry.json"
    traces_json = out / "lineage_trace_registry.json"
    gaps_json = out / "lineage_gap_queue.json"
    atoms_json = out / "lineage_atoms.json"

    summary_path.write_text(json.dumps(report["summary"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    families_json.write_text(json.dumps(report["families"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    traces_json.write_text(json.dumps(report["traces"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gaps_json.write_text(json.dumps(report["gaps"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    atoms_json.write_text(json.dumps(report["atoms"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _write_tsv(
        out / "lineage_family_registry.tsv",
        report["families"],
        [
            "lineage_family_id",
            "task_ref",
            "lineage_status",
            "atom_count",
            "review_ready_atoms",
            "trace_count",
            "sources",
            "episode_types",
            "first_valid_from",
            "last_valid_from",
        ],
    )
    _write_tsv(
        out / "lineage_trace_registry.tsv",
        report["traces"],
        [
            "lineage_family_id",
            "trace_id",
            "task_ref",
            "lineage_status",
            "atom_count",
            "episode_types",
            "first_valid_from",
            "last_valid_from",
        ],
    )
    _write_tsv(
        out / "lineage_gap_queue.tsv",
        report["gaps"],
        [
            "atom_id",
            "source",
            "episode_type",
            "atom_type",
            "task_ref",
            "trace_id",
            "missing_fields",
            "lineage_status",
            "lineage_action",
            "provider",
            "model",
            "canonical_question",
            "answer_preview",
            "valid_from",
        ],
    )

    return {
        "ok": True,
        "output_dir": str(out),
        "summary_path": str(summary_path),
        "files": [
            str(summary_path),
            str(families_json),
            str(traces_json),
            str(gaps_json),
            str(atoms_json),
            str(out / "lineage_family_registry.tsv"),
            str(out / "lineage_trace_registry.tsv"),
            str(out / "lineage_gap_queue.tsv"),
        ],
        "lineage_families": report["summary"]["lineage_families"],
        "gap_atoms": report["summary"]["gap_atoms"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a posthoc lineage registry for the execution activity slice."
    )
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    report = build_lineage_registry(db_path=args.db, limit=args.limit)
    result = write_lineage_registry(report, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
