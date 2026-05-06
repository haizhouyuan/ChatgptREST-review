#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.retrieval import RetrievalSurface, retrieve, runtime_retrieval_config


DEFAULT_OUTPUT_ROOT = Path("artifacts/monitor/evomap_semantic_recall_harness")
DEFAULT_QUERIES = (
    "绿源来访准备",
    "钛虎机器人关节模组合作",
    "两轮车车轮市场竞争分析",
)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# EvoMap Semantic Recall Harness",
        "",
        f"- `generated_at`: `{summary['generated_at']}`",
        f"- `db_path`: `{summary['db_path']}`",
        f"- `vector_db_path`: `{summary['vector_db_path']}`",
        f"- `query_count`: `{summary['query_count']}`",
        f"- `ok`: `{summary['ok']}`",
        "",
    ]
    for item in summary.get("queries", []):
        lines.extend(
            [
                f"## {item['query']}",
                "",
                f"- `hit_count`: `{item['hit_count']}`",
                f"- `vector_hit_count`: `{item['vector_hit_count']}`",
                f"- `retrieval_sources`: `{item['retrieval_sources']}`",
                f"- `retrieval_layers`: `{item['retrieval_layers']}`",
                "",
                "| Atom | Status | Source | Layer | Bucket | Question |",
                "|---|---|---|---|---|---|",
            ]
        )
        for hit in item.get("hits", []):
            lines.append(
                "| {atom_id} | {promotion_status} | {retrieval_source} | {retrieval_layer} | {source_bucket} | {question} |".format(
                    atom_id=str(hit.get("atom_id", "")).replace("|", "\\|"),
                    promotion_status=str(hit.get("promotion_status", "")).replace("|", "\\|"),
                    retrieval_source=str(hit.get("retrieval_source", "")).replace("|", "\\|"),
                    retrieval_layer=str(hit.get("retrieval_layer", "")).replace("|", "\\|"),
                    source_bucket=str(hit.get("source_bucket", "")).replace("|", "\\|"),
                    question=str(hit.get("question", "")).replace("|", "\\|"),
                )
            )
        lines.append("")
    return "\n".join(lines)


def run_harness(
    *,
    db_path: str,
    vector_db_path: str,
    output_root: Path,
    queries: list[str],
    result_limit: int = 5,
) -> dict[str, Any]:
    db = KnowledgeDB(db_path)
    run_dir = output_root / _stamp()
    run_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    ok = True
    for query in queries:
        cfg = runtime_retrieval_config(
            surface=RetrievalSurface.PLANNING_EXPLICIT_PATH,
            project_id="planning",
            result_limit=result_limit,
            vector_db_path=vector_db_path,
        )
        hits = retrieve(db, query, config=cfg)
        item = {
            "query": query,
            "hit_count": len(hits),
            "vector_hit_count": sum(1 for hit in hits if float(hit.vector_score or 0.0) > 0.0),
            "retrieval_sources": sorted({str(hit.retrieval_source or "") for hit in hits}),
            "retrieval_layers": sorted({str(hit.retrieval_layer or "") for hit in hits}),
            "hits": [
                {
                    "atom_id": hit.atom.atom_id,
                    "promotion_status": hit.atom.promotion_status,
                    "retrieval_source": hit.retrieval_source,
                    "retrieval_layer": hit.retrieval_layer,
                    "source_bucket": hit.source_bucket,
                    "question": hit.atom.question,
                    "vector_score": float(hit.vector_score or 0.0),
                    "final_score": float(hit.final_score or 0.0),
                }
                for hit in hits
            ],
        }
        if item["hit_count"] <= 0:
            ok = False
        items.append(item)

    summary = {
        "ok": ok,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": db_path,
        "vector_db_path": vector_db_path,
        "query_count": len(queries),
        "queries": items,
        "artifacts": {
            "summary_json": str(run_dir / "summary.json"),
            "report_md": str(run_dir / "report.md"),
        },
    }
    _write_json(run_dir / "summary.json", summary)
    (run_dir / "report.md").write_text(_render_report(summary), encoding="utf-8")
    return summary


def main() -> int:
    from chatgptrest.core.openmind_paths import (
        resolve_evomap_knowledge_runtime_db_path,
        resolve_evomap_vector_db_path,
    )

    parser = argparse.ArgumentParser(description="Run semantic recall probes for real planning queries.")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--vector-db", default=resolve_evomap_vector_db_path())
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--result-limit", type=int, default=5)
    args = parser.parse_args()

    summary = run_harness(
        db_path=str(args.db),
        vector_db_path=str(args.vector_db),
        output_root=Path(args.output_root),
        queries=list(args.query or DEFAULT_QUERIES),
        result_limit=int(args.result_limit),
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
