#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import (
    resolve_evomap_knowledge_runtime_db_path,
    resolve_evomap_vector_db_path,
)
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.retrieval import RetrievalSurface, retrieve, runtime_retrieval_config
from chatgptrest.evomap.knowledge.vector_lane import (
    EvoMapVectorIndex,
    fetch_records_for_vectorization,
    probe_vector_store,
)


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "evomap_vectorization"
DEFAULT_SCOPE_PROJECTS = ("planning",)
DEFAULT_SOURCE_BUCKETS = (
    "planning_review_pack",
    "planning_latest_output",
    "planning_outputs",
    "planning_strategy",
    "planning_budget",
    "planning_controlled",
)
DEFAULT_PROMOTION_STATUSES = ("active", "candidate")


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "# EvoMap Vectorization",
        "",
        f"- `generated_at`: `{summary['generated_at']}`",
        f"- `db_path`: `{summary['db_path']}`",
        f"- `vector_db_path`: `{summary['vector_db_path']}`",
        f"- `records_selected`: `{summary['records_selected']}`",
        f"- `indexed`: `{summary['index_result']['indexed']}`",
        f"- `mode`: `{summary['index_result'].get('mode', '')}`",
        f"- `pre_vector_count`: `{summary['pre_probe']['vector_count']}`",
        f"- `post_vector_count`: `{summary['post_probe']['vector_count']}`",
        f"- `ok`: `{summary['ok']}`",
        "",
        "## Selection",
        "",
        f"- `promotion_statuses`: `{', '.join(summary['selection']['promotion_statuses'])}`",
        f"- `scope_projects`: `{', '.join(summary['selection']['scope_projects'])}`",
        f"- `source_buckets`: `{', '.join(summary['selection']['source_buckets'])}`",
        "",
        "## Query Probe",
        "",
    ]
    query_probe = dict(summary.get("query_probe") or {})
    if query_probe:
        lines.extend(
            [
                f"- `query`: `{query_probe.get('query', '')}`",
                f"- `hit_count`: `{query_probe.get('hit_count', 0)}`",
                f"- `vector_hit_count`: `{query_probe.get('vector_hit_count', 0)}`",
                "",
                "| Atom | Layer | Source | Vector Score | Bucket |",
                "|---|---|---|---:|---|",
            ]
        )
        for item in query_probe.get("hits", []):
            lines.append(
                "| {atom_id} | {retrieval_layer} | {retrieval_source} | {vector_score} | {source_bucket} |".format(
                    atom_id=str(item.get("atom_id", "")).replace("|", "\\|"),
                    retrieval_layer=str(item.get("retrieval_layer", "")).replace("|", "\\|"),
                    retrieval_source=str(item.get("retrieval_source", "")).replace("|", "\\|"),
                    vector_score=item.get("vector_score", 0.0),
                    source_bucket=str(item.get("source_bucket", "")).replace("|", "\\|"),
                )
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def run_vectorization(
    *,
    db_path: str,
    vector_db_path: str,
    output_root: Path,
    query: str,
    top_k: int,
    promotion_statuses: tuple[str, ...] = DEFAULT_PROMOTION_STATUSES,
    scope_projects: tuple[str, ...] = DEFAULT_SCOPE_PROJECTS,
    source_buckets: tuple[str, ...] = DEFAULT_SOURCE_BUCKETS,
    min_quality: float = 0.15,
    limit: int = 0,
    batch_size: int = 256,
    save_every_batches: int = 4,
    require_vectors: bool = True,
) -> dict[str, Any]:
    stamp = _now_stamp()
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    db = KnowledgeDB(db_path)
    pre_probe = probe_vector_store(vector_db_path)
    records = fetch_records_for_vectorization(
        db,
        promotion_statuses=promotion_statuses,
        scope_projects=scope_projects,
        source_buckets=source_buckets,
        min_quality=min_quality,
        limit=limit,
    )
    status_counts = Counter(record.promotion_status for record in records)
    bucket_counts = Counter(record.source_bucket or "unknown" for record in records)

    index = EvoMapVectorIndex(vector_db_path)
    try:
        index_result = index.index_records(
            records,
            batch_size=batch_size,
            save_every_batches=save_every_batches,
        )
    finally:
        index.close()
    post_probe = probe_vector_store(vector_db_path)

    cfg = runtime_retrieval_config(
        surface=RetrievalSurface.PLANNING_EXPLICIT_PATH,
        vector_db_path=str(vector_db_path),
    )
    hits = retrieve(db, query, config=cfg)
    query_probe = {
        "query": query,
        "hit_count": len(hits),
        "vector_hit_count": sum(1 for item in hits if float(item.vector_score or 0.0) > 0.0),
        "hits": [
            {
                "atom_id": item.atom.atom_id,
                "retrieval_layer": item.retrieval_layer,
                "retrieval_source": item.retrieval_source,
                "vector_score": round(float(item.vector_score or 0.0), 6),
                "source_bucket": item.source_bucket,
                "promotion_status": item.atom.promotion_status,
            }
            for item in hits[:top_k]
        ],
    }

    ok = True
    if require_vectors:
        ok = (
            str(index_result.get("mode") or "") == "vector"
            and int(post_probe.get("vector_count") or 0) >= int(pre_probe.get("vector_count") or 0)
            and int(post_probe.get("vector_count") or 0) > 0
        )

    summary = {
        "ok": ok,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "vector_db_path": str(vector_db_path),
        "records_selected": len(records),
        "selection": {
            "promotion_statuses": list(promotion_statuses),
            "scope_projects": list(scope_projects),
            "source_buckets": list(source_buckets),
            "min_quality": min_quality,
            "limit": limit,
            "batch_size": batch_size,
            "save_every_batches": save_every_batches,
        },
        "status_counts": dict(status_counts),
        "bucket_counts": dict(bucket_counts),
        "pre_probe": pre_probe,
        "index_result": index_result,
        "post_probe": post_probe,
        "query_probe": query_probe,
        "artifacts": {
            "summary_json": str(run_dir / "summary.json"),
            "report_md": str(run_dir / "report.md"),
        },
    }
    _write_json(run_dir / "summary.json", summary)
    (run_dir / "report.md").write_text(_markdown_report(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Vectorize the governed EvoMap active/candidate slice and capture probe evidence.")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--vector-db", default=resolve_evomap_vector_db_path())
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--query", default="绿源 来访 准备")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-quality", type=float, default=0.15)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--save-every-batches", type=int, default=4)
    parser.add_argument("--scope-project", action="append", default=[])
    parser.add_argument("--source-bucket", action="append", default=[])
    parser.add_argument("--promotion-status", action="append", default=[])
    parser.add_argument("--allow-fts-only", action="store_true")
    args = parser.parse_args()

    summary = run_vectorization(
        db_path=str(args.db),
        vector_db_path=str(args.vector_db),
        output_root=Path(args.output_root),
        query=str(args.query),
        top_k=int(args.top_k),
        promotion_statuses=tuple(args.promotion_status or DEFAULT_PROMOTION_STATUSES),
        scope_projects=tuple(args.scope_project or DEFAULT_SCOPE_PROJECTS),
        source_buckets=tuple(args.source_bucket or DEFAULT_SOURCE_BUCKETS),
        min_quality=float(args.min_quality),
        limit=int(args.limit),
        batch_size=int(args.batch_size),
        save_every_batches=int(args.save_every_batches),
        require_vectors=not bool(args.allow_fts_only),
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
