#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.extractors.note_section import NoteSectionExtractor
from chatgptrest.evomap.knowledge.ingest_quality import classify_atom_ingest_rejections
from chatgptrest.evomap.knowledge.planning_review_plane import _review_domain
from chatgptrest.evomap.knowledge.retrieval import _planning_query_terms
from chatgptrest.evomap.knowledge.schema import PromotionStatus


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "planning_targeted_reingest"
DEFAULT_PLANNING_ROOT = Path("/vol1/1000/projects/planning")
DEFAULT_QUERIES = (
    "绿源来访准备",
    "钛虎机器人关节模组合作",
    "两轮车车轮市场竞争分析",
)
ENTITY_TERMS = {"绿源", "钛虎", "九号", "新日", "金彭", "雅迪", "爱玛", "小牛", "台铃", "鹿明"}


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text) if text else {}
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def _score_file(path: Path, query: str, terms: list[str]) -> tuple[float, list[str], str]:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0.0, [], ""

    title = _extract_title(content[:4000], path.stem)
    path_text = path.as_posix()
    haystack = "\n".join([path_text, title, content[:40000]])
    matched: list[str] = []
    score = 0.0
    for term in terms:
        if len(term.strip()) < 2:
            continue
        if term not in haystack:
            continue
        matched.append(term)
        if term == query:
            score += 12.0
        elif term in ENTITY_TERMS:
            score += 6.0
        elif len(term) >= 4:
            score += 3.0
        else:
            score += 1.5
        if term in path_text:
            score += 2.0
        if term in title:
            score += 2.0
    return score, matched, title


def discover_target_files(
    *,
    planning_root: Path,
    query: str,
    max_files: int,
) -> list[dict[str, Any]]:
    terms = _planning_query_terms(query)
    candidates: list[dict[str, Any]] = []
    for path in planning_root.rglob("*.md"):
        score, matched, title = _score_file(path, query, terms)
        if score <= 0:
            continue
        candidates.append(
            {
                "query": query,
                "path": path.as_posix(),
                "title": title,
                "score": round(score, 3),
                "matched_terms": matched,
            }
        )
    candidates.sort(key=lambda item: (-float(item["score"]), item["path"]))
    return candidates[:max_files]


def _merge_planning_meta(
    *,
    existing_meta_json: str,
    raw_ref: str,
    query_hits: list[str],
    matched_terms: list[str],
) -> str:
    payload = _load_json(existing_meta_json)
    existing_review = payload.get("planning_review")
    if not isinstance(existing_review, dict):
        existing_review = {}
    payload["targeted_reingest"] = {
        "query_hits": query_hits,
        "matched_terms": matched_terms,
        "wave": "semantic_entity_reingest_20260409",
    }
    payload["planning_review"] = {
        **existing_review,
        "source_bucket": "planning_controlled",
        "review_domain": _review_domain(raw_ref),
        "document_role": "controlled",
        "final_bucket": "planning_controlled",
        "service_readiness": "high",
        "is_latest_output": "0",
    }
    return json.dumps(payload, ensure_ascii=False)


def _targeted_signal_boost(match_info: dict[str, Any]) -> float:
    matched_terms = {
        str(term).strip()
        for term in match_info.get("matched_terms") or []
        if str(term).strip()
    }
    if not matched_terms:
        return 0.0
    entity_hits = matched_terms & ENTITY_TERMS
    if entity_hits and len(matched_terms) >= 2:
        return 0.10
    if entity_hits:
        return 0.08
    if len(matched_terms) >= 3:
        return 0.05
    return 0.0


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_targeted_reingest(
    *,
    db_path: str,
    planning_root: Path,
    queries: tuple[str, ...],
    output_root: Path,
    max_files_per_query: int,
    candidate_min_quality: float,
    live: bool,
) -> dict[str, Any]:
    stamp = _now_stamp()
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    query_matches: dict[str, list[dict[str, Any]]] = {}
    query_terms: dict[str, list[str]] = {}
    selected_paths: dict[str, dict[str, Any]] = {}
    for query in queries:
        matches = discover_target_files(
            planning_root=planning_root,
            query=query,
            max_files=max_files_per_query,
        )
        query_matches[query] = matches
        query_terms[query] = _planning_query_terms(query)
        for item in matches:
            slot = selected_paths.setdefault(
                item["path"],
                {
                    "title": item["title"],
                    "queries": [],
                    "matched_terms": [],
                    "score": 0.0,
                },
            )
            slot["queries"].append(query)
            slot["matched_terms"] = list(dict.fromkeys([*slot["matched_terms"], *item["matched_terms"]]))
            slot["score"] = max(float(slot["score"]), float(item["score"]))

    path_allowlist = sorted(selected_paths)
    db = KnowledgeDB(db_path)
    extractor = NoteSectionExtractor(
        db,
        source_dirs=[str(planning_root)],
        source_label="planning",
        min_content_len=40,
        path_allowlist=path_allowlist,
    )

    stats = {
        "docs_written": 0,
        "episodes_written": 0,
        "atoms_written": 0,
        "candidate_seeded": 0,
        "staged_seeded": 0,
        "skipped_atoms": 0,
    }
    skip_reasons = Counter()
    doc_atom_counts: dict[str, int] = defaultdict(int)
    doc_status_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for doc in extractor.extract_documents():
        match_info = selected_paths.get(doc.raw_ref)
        if match_info is None:
            continue
        doc.meta_json = _merge_planning_meta(
            existing_meta_json=doc.meta_json,
            raw_ref=doc.raw_ref,
            query_hits=match_info["queries"],
            matched_terms=match_info["matched_terms"],
        )
        stats["docs_written"] += 1
        if live:
            db.put_document(doc, commit=False)

        for episode in extractor.extract_episodes(doc):
            stats["episodes_written"] += 1
            if live:
                db.put_episode(episode, commit=False)

            for atom in extractor.extract_atoms(episode):
                rejection_reasons = classify_atom_ingest_rejections(atom)
                if rejection_reasons:
                    stats["skipped_atoms"] += 1
                    for reason in rejection_reasons:
                        skip_reasons[reason] += 1
                    continue

                atom.scope_project = "planning"
                quality_gate_score = float(atom.quality_auto or 0.0) + _targeted_signal_boost(match_info)
                atom.promotion_status = (
                    PromotionStatus.CANDIDATE.value
                    if quality_gate_score >= candidate_min_quality
                    else PromotionStatus.STAGED.value
                )
                atom.promotion_reason = f"targeted_reingest:planning_controlled:{'|'.join(match_info['queries'])}"
                doc_atom_counts[doc.raw_ref] += 1
                doc_status_counts[doc.raw_ref][atom.promotion_status] += 1
                stats["atoms_written"] += 1
                if atom.promotion_status == PromotionStatus.CANDIDATE.value:
                    stats["candidate_seeded"] += 1
                else:
                    stats["staged_seeded"] += 1
                if live:
                    db.put_atom(atom, commit=False)
                    for evidence in extractor.extract_evidence(atom, episode):
                        db.put_evidence(evidence, commit=False)
        if live:
            db.commit()

    summary = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if live else "dry_run",
        "db_path": str(db_path),
        "planning_root": str(planning_root),
        "queries": list(queries),
        "max_files_per_query": max_files_per_query,
        "candidate_min_quality": candidate_min_quality,
        "selected_file_count": len(path_allowlist),
        "selected_files": [
            {
                "path": path,
                "title": selected_paths[path]["title"],
                "queries": selected_paths[path]["queries"],
                "matched_terms": selected_paths[path]["matched_terms"],
                "score": selected_paths[path]["score"],
                "atoms_written": doc_atom_counts.get(path, 0),
                "status_counts": dict(doc_status_counts.get(path, Counter())),
            }
            for path in path_allowlist
        ],
        "query_matches": query_matches,
        "stats": stats,
        "skip_reasons": dict(skip_reasons),
        "artifacts": {
            "summary_json": str(run_dir / "summary.json"),
            "report_md": str(run_dir / "report.md"),
        },
    }
    _write_json(run_dir / "summary.json", summary)

    report_lines = [
        "# Planning Targeted Re-Ingest",
        "",
        f"- `mode`: `{summary['mode']}`",
        f"- `selected_file_count`: `{summary['selected_file_count']}`",
        f"- `docs_written`: `{stats['docs_written']}`",
        f"- `atoms_written`: `{stats['atoms_written']}`",
        f"- `candidate_seeded`: `{stats['candidate_seeded']}`",
        f"- `staged_seeded`: `{stats['staged_seeded']}`",
        "",
        "## Queries",
        "",
    ]
    for query, matches in query_matches.items():
        report_lines.append(f"### {query}")
        if not matches:
            report_lines.append("- no matched files")
            report_lines.append("")
            continue
        for item in matches:
            report_lines.append(
                f"- `{item['score']}` [{item['title']}]({item['path']}) terms={','.join(item['matched_terms'])}"
            )
        report_lines.append("")
    (run_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run targeted planning re-ingest for entity-centric semantic recall gaps.")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--planning-root", default=str(DEFAULT_PLANNING_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--max-files-per-query", type=int, default=8)
    parser.add_argument("--candidate-min-quality", type=float, default=0.7)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    summary = run_targeted_reingest(
        db_path=str(args.db),
        planning_root=Path(args.planning_root),
        queries=tuple(args.query or DEFAULT_QUERIES),
        output_root=Path(args.output_root),
        max_files_per_query=int(args.max_files_per_query),
        candidate_min_quality=float(args.candidate_min_quality),
        live=bool(args.live),
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
