#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import (
    resolve_evomap_knowledge_runtime_db_path,
    resolve_evomap_vector_db_path,
)
from chatgptrest.evomap.knowledge.db import KnowledgeDB
from chatgptrest.evomap.knowledge.retrieval import RetrievalSurface, retrieve, runtime_retrieval_config


DEFAULT_CASE_FILE = REPO_ROOT / "ops" / "data" / "evomap_recall_benchmark_v2.json"
DEFAULT_BASELINE_SUMMARY = REPO_ROOT / "artifacts" / "monitor" / "evomap_semantic_recall_harness" / "20260408T231936Z" / "summary.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "evomap_recall_production_benchmark"
ENTITY_DOSSIER_QUERY_TERMS = (
    "董事长",
    "融资",
    "公司整体情况",
    "产品线",
    "背景",
    "历史",
    "创始人",
    "股东",
)
GENERIC_VISIT_QUERY_TERMS = (
    "来访",
    "拜访",
    "准备",
    "交流",
)
GENERIC_COUNTERPARTY_TERMS = (
    "供应商",
    "客户",
    "合作方",
    "来访方",
)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("benchmark case file must contain a list")
    cases: list[dict[str, Any]] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"benchmark case #{idx} must be an object")
        query = str(item.get("query") or "").strip()
        project_id = str(item.get("project_id") or "").strip()
        keywords = [str(v).strip() for v in list(item.get("expected_keywords") or []) if str(v).strip()]
        if not query or not project_id or not keywords:
            raise ValueError(f"benchmark case #{idx} must include query, project_id, and expected_keywords")
        cases.append(
            {
                "case_id": str(item.get("case_id") or f"case-{idx}").strip(),
                "case_family": str(item.get("case_family") or "legacy").strip(),
                "query": query,
                "project_id": project_id,
                "expected_keywords": keywords,
                "entity_terms": [str(v).strip() for v in list(item.get("entity_terms") or []) if str(v).strip()],
                "expected_posture": str(item.get("expected_posture") or "").strip(),
                "expected_recall_grade": str(item.get("expected_recall_grade") or "").strip(),
                "notes": str(item.get("notes") or "").strip(),
            }
        )
    return cases


def _normalize_text(*values: Any) -> str:
    return " ".join(str(v or "").strip().lower() for v in values if str(v or "").strip())


def _keyword_overlap_score(text: str, keywords: list[str]) -> int:
    haystack = _normalize_text(text)
    return sum(1 for keyword in keywords if keyword.lower() in haystack)


def _entity_exact_overlap(text: str, entity_terms: list[str]) -> int:
    haystack = _normalize_text(text)
    return sum(1 for term in entity_terms if term.lower() in haystack)


def _is_entity_dossier_query(query: str) -> bool:
    normalized = _normalize_text(query)
    return any(term.lower() in normalized for term in ENTITY_DOSSIER_QUERY_TERMS)


def _is_generic_visit_prep_query(query: str, entity_terms: list[str]) -> bool:
    if entity_terms:
        return False
    normalized = _normalize_text(query)
    return any(term.lower() in normalized for term in GENERIC_VISIT_QUERY_TERMS) and any(
        term.lower() in normalized for term in GENERIC_COUNTERPARTY_TERMS
    )


def _score_hits(case: Mapping[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    expected_keywords = list(case.get("expected_keywords") or [])
    entity_terms = list(case.get("entity_terms") or [])
    expected_project = str(case.get("project_id") or "").strip()
    expected_posture = str(case.get("expected_posture") or "").strip()
    expected_recall_grade = str(case.get("expected_recall_grade") or "").strip()
    scored_hits: list[dict[str, Any]] = []
    top3 = list(hits[:3])
    relevant_hits = 0
    misassociated = 0
    entity_exact_hit_count = 0
    for hit in top3:
        question = str(hit.get("question") or "")
        answer_excerpt = str(hit.get("answer_excerpt") or "")
        source_ref = str(hit.get("source_ref") or "")
        scope_project = str(hit.get("scope_project") or "").strip()
        overlap = _keyword_overlap_score(" ".join((question, answer_excerpt, source_ref)), expected_keywords)
        entity_overlap = _entity_exact_overlap(" ".join((question, answer_excerpt, source_ref)), entity_terms)
        relevant = overlap > 0
        if relevant:
            relevant_hits += 1
        if entity_overlap > 0:
            entity_exact_hit_count += 1
        if scope_project and scope_project != expected_project:
            misassociated += 1
        scored_hits.append(
            {
                **dict(hit),
                "keyword_overlap": overlap,
                "entity_overlap": entity_overlap,
                "relevant": relevant,
            }
        )

    top3_hit_rate = round(relevant_hits / max(1, min(3, len(top3))), 6) if top3 else 0.0
    top1_overlap = int(scored_hits[0]["keyword_overlap"]) if scored_hits else 0
    dossier_query = _is_entity_dossier_query(str(case.get("query") or ""))
    generic_visit_query = _is_generic_visit_prep_query(str(case.get("query") or ""), entity_terms)
    if not scored_hits:
        recall_grade = "abstain"
    elif dossier_query and entity_terms and entity_exact_hit_count > 0 and top1_overlap >= 3 and top3_hit_rate >= 0.67:
        recall_grade = "entity"
    elif top1_overlap > 0 or top3_hit_rate > 0.0:
        recall_grade = "bridge"
    else:
        recall_grade = "abstain"
    if not scored_hits:
        confidence_posture = "abstain"
    elif recall_grade == "abstain" and top1_overlap <= 0 and top3_hit_rate < 0.34:
        confidence_posture = "abstain"
    elif dossier_query and recall_grade != "entity":
        confidence_posture = "clarify"
    elif generic_visit_query and recall_grade == "bridge":
        confidence_posture = "clarify"
    elif top1_overlap <= 0 or top3_hit_rate < 0.67:
        confidence_posture = "clarify"
    else:
        confidence_posture = "answer"
    return {
        "case_id": str(case.get("case_id") or "").strip(),
        "case_family": str(case.get("case_family") or "legacy").strip(),
        "query": str(case.get("query") or "").strip(),
        "project_id": expected_project,
        "expected_keywords": expected_keywords,
        "entity_terms": entity_terms,
        "expected_posture": expected_posture,
        "expected_recall_grade": expected_recall_grade,
        "hit_count": len(hits),
        "top3_hit_rate": top3_hit_rate,
        "top1_keyword_overlap": top1_overlap,
        "entity_exact_hit_count": entity_exact_hit_count,
        "misassociation_count": misassociated,
        "confidence_posture": confidence_posture,
        "recall_grade": recall_grade,
        "expected_posture_match": bool(expected_posture) and confidence_posture == expected_posture,
        "expected_recall_grade_match": bool(expected_recall_grade) and recall_grade == expected_recall_grade,
        "background_reexplanation_risk": top1_overlap <= 0,
        "top_hits": scored_hits,
    }


def _hits_from_summary(summary: Mapping[str, Any], query: str) -> list[dict[str, Any]]:
    for item in list(summary.get("queries") or []):
        if str(dict(item).get("query") or "").strip() == query:
            return [dict(hit) for hit in list(dict(item).get("hits") or []) if isinstance(hit, Mapping)]
    return []


def _aggregate(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not case_rows:
        return {
            "case_count": 0,
            "top3_hit_rate": 0.0,
            "top1_keyword_match_rate": 0.0,
            "misassociation_rate": 0.0,
            "clarify_rate": 0.0,
            "abstain_rate": 0.0,
            "bridge_rate": 0.0,
            "entity_rate": 0.0,
            "expected_posture_match_rate": 0.0,
            "expected_recall_grade_match_rate": 0.0,
            "background_reexplanation_risk_rate": 0.0,
        }
    case_count = len(case_rows)
    top3_values = [float(row.get("top3_hit_rate") or 0.0) for row in case_rows]
    top1_match_count = sum(1 for row in case_rows if int(row.get("top1_keyword_overlap") or 0) > 0)
    misassociation_cases = sum(1 for row in case_rows if int(row.get("misassociation_count") or 0) > 0)
    clarify_cases = sum(1 for row in case_rows if str(row.get("confidence_posture") or "") == "clarify")
    abstain_cases = sum(1 for row in case_rows if str(row.get("confidence_posture") or "") == "abstain")
    bridge_cases = sum(1 for row in case_rows if str(row.get("recall_grade") or "") == "bridge")
    entity_cases = sum(1 for row in case_rows if str(row.get("recall_grade") or "") == "entity")
    expected_posture_cases = [row for row in case_rows if str(row.get("expected_posture") or "").strip()]
    expected_recall_cases = [row for row in case_rows if str(row.get("expected_recall_grade") or "").strip()]
    background_cases = sum(1 for row in case_rows if bool(row.get("background_reexplanation_risk")))
    return {
        "case_count": case_count,
        "top3_hit_rate": round(float(statistics.mean(top3_values)), 6),
        "top1_keyword_match_rate": round(top1_match_count / case_count, 6),
        "misassociation_rate": round(misassociation_cases / case_count, 6),
        "clarify_rate": round(clarify_cases / case_count, 6),
        "abstain_rate": round(abstain_cases / case_count, 6),
        "bridge_rate": round(bridge_cases / case_count, 6),
        "entity_rate": round(entity_cases / case_count, 6),
        "expected_posture_match_rate": round(
            sum(1 for row in expected_posture_cases if bool(row.get("expected_posture_match"))) / max(1, len(expected_posture_cases)),
            6,
        ),
        "expected_recall_grade_match_rate": round(
            sum(1 for row in expected_recall_cases if bool(row.get("expected_recall_grade_match"))) / max(1, len(expected_recall_cases)),
            6,
        ),
        "background_reexplanation_risk_rate": round(background_cases / case_count, 6),
    }


def _current_hits(db: KnowledgeDB, cases: list[dict[str, Any]], *, vector_db_path: str, result_limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for case in cases:
        cfg = runtime_retrieval_config(
            surface=RetrievalSurface.PLANNING_EXPLICIT_PATH,
            project_id=str(case["project_id"]),
            result_limit=result_limit,
            vector_db_path=vector_db_path,
        )
        hits = retrieve(db, str(case["query"]), config=cfg)
        items.append(
            {
                "query": case["query"],
                "hits": [
                    {
                        "atom_id": hit.atom.atom_id,
                        "promotion_status": hit.atom.promotion_status,
                        "retrieval_source": hit.retrieval_source,
                        "retrieval_layer": hit.retrieval_layer,
                        "source_bucket": hit.source_bucket,
                        "question": hit.atom.question,
                        "answer_excerpt": str(hit.atom.answer or "")[:240],
                        "source_ref": hit.source_ref,
                        "scope_project": str(hit.atom.scope_project or ""),
                        "vector_score": float(hit.vector_score or 0.0),
                        "final_score": float(hit.final_score or 0.0),
                        "entity_boost": float(hit.entity_boost or 0.0),
                    }
                    for hit in hits
                ],
            }
        )
    return items


def run_benchmark(
    *,
    db_path: str,
    vector_db_path: str,
    cases_path: str | Path,
    baseline_summary_path: str | Path,
    output_root: str | Path,
    result_limit: int = 5,
) -> dict[str, Any]:
    cases = load_cases(cases_path)
    baseline_summary = json.loads(Path(baseline_summary_path).read_text(encoding="utf-8"))
    db = KnowledgeDB(db_path)
    current_queries = _current_hits(db, cases, vector_db_path=vector_db_path, result_limit=result_limit)

    current_case_rows = [_score_hits(case, _hits_from_summary({"queries": current_queries}, case["query"])) for case in cases]
    baseline_case_rows = [_score_hits(case, _hits_from_summary(baseline_summary, case["query"])) for case in cases]
    current_aggregate = _aggregate(current_case_rows)
    baseline_aggregate = _aggregate(baseline_case_rows)

    batch_dir = Path(output_root) / _stamp()
    batch_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": db_path,
        "vector_db_path": vector_db_path,
        "cases_path": str(cases_path),
        "baseline_summary_path": str(baseline_summary_path),
        "baseline": {
            "aggregate": baseline_aggregate,
            "cases": baseline_case_rows,
        },
        "current": {
            "aggregate": current_aggregate,
            "cases": current_case_rows,
            "queries": current_queries,
        },
        "delta": {
            "top3_hit_rate_delta": round(current_aggregate["top3_hit_rate"] - baseline_aggregate["top3_hit_rate"], 6),
            "top3_hit_rate_relative_gain": round(
                (current_aggregate["top3_hit_rate"] - baseline_aggregate["top3_hit_rate"]) / baseline_aggregate["top3_hit_rate"],
                6,
            )
            if baseline_aggregate["top3_hit_rate"] > 0
            else 0.0,
            "misassociation_rate_delta": round(current_aggregate["misassociation_rate"] - baseline_aggregate["misassociation_rate"], 6),
            "background_reexplanation_risk_delta": round(
                current_aggregate["background_reexplanation_risk_rate"] - baseline_aggregate["background_reexplanation_risk_rate"],
                6,
            ),
        },
        "artifacts": {
            "summary_json": str(batch_dir / "summary.json"),
            "report_md": str(batch_dir / "report.md"),
        },
    }
    _write_json(batch_dir / "summary.json", summary)
    (batch_dir / "report.md").write_text(_render_report(summary), encoding="utf-8")
    return summary


def _render_report(summary: Mapping[str, Any]) -> str:
    baseline = dict(summary.get("baseline") or {}).get("aggregate", {})
    current = dict(summary.get("current") or {}).get("aggregate", {})
    delta = dict(summary.get("delta") or {})
    lines = [
        "# EvoMap Recall Production Benchmark",
        "",
        f"- `generated_at`: `{summary['generated_at']}`",
        f"- `baseline_summary_path`: `{summary['baseline_summary_path']}`",
        f"- `cases_path`: `{summary['cases_path']}`",
        "",
        "## Aggregate",
        "",
        "| Metric | Baseline | Current | Delta |",
        "|---|---:|---:|---:|",
        f"| top3_hit_rate | {baseline.get('top3_hit_rate', 0.0)} | {current.get('top3_hit_rate', 0.0)} | {delta.get('top3_hit_rate_delta', 0.0)} |",
        f"| top1_keyword_match_rate | {baseline.get('top1_keyword_match_rate', 0.0)} | {current.get('top1_keyword_match_rate', 0.0)} | {round(float(current.get('top1_keyword_match_rate', 0.0)) - float(baseline.get('top1_keyword_match_rate', 0.0)), 6)} |",
        f"| misassociation_rate | {baseline.get('misassociation_rate', 0.0)} | {current.get('misassociation_rate', 0.0)} | {delta.get('misassociation_rate_delta', 0.0)} |",
        f"| clarify_rate | {baseline.get('clarify_rate', 0.0)} | {current.get('clarify_rate', 0.0)} | {round(float(current.get('clarify_rate', 0.0)) - float(baseline.get('clarify_rate', 0.0)), 6)} |",
        f"| abstain_rate | {baseline.get('abstain_rate', 0.0)} | {current.get('abstain_rate', 0.0)} | {round(float(current.get('abstain_rate', 0.0)) - float(baseline.get('abstain_rate', 0.0)), 6)} |",
        f"| bridge_rate | {baseline.get('bridge_rate', 0.0)} | {current.get('bridge_rate', 0.0)} | {round(float(current.get('bridge_rate', 0.0)) - float(baseline.get('bridge_rate', 0.0)), 6)} |",
        f"| entity_rate | {baseline.get('entity_rate', 0.0)} | {current.get('entity_rate', 0.0)} | {round(float(current.get('entity_rate', 0.0)) - float(baseline.get('entity_rate', 0.0)), 6)} |",
        f"| expected_posture_match_rate | {baseline.get('expected_posture_match_rate', 0.0)} | {current.get('expected_posture_match_rate', 0.0)} | {round(float(current.get('expected_posture_match_rate', 0.0)) - float(baseline.get('expected_posture_match_rate', 0.0)), 6)} |",
        f"| expected_recall_grade_match_rate | {baseline.get('expected_recall_grade_match_rate', 0.0)} | {current.get('expected_recall_grade_match_rate', 0.0)} | {round(float(current.get('expected_recall_grade_match_rate', 0.0)) - float(baseline.get('expected_recall_grade_match_rate', 0.0)), 6)} |",
        f"| background_reexplanation_risk_rate | {baseline.get('background_reexplanation_risk_rate', 0.0)} | {current.get('background_reexplanation_risk_rate', 0.0)} | {delta.get('background_reexplanation_risk_delta', 0.0)} |",
        "",
    ]
    for row in list(dict(summary.get("current") or {}).get("cases") or []):
        lines.extend(
            [
                f"## {row['case_id']}",
                "",
                f"- case_family: `{row.get('case_family', '')}`",
                f"- Query: `{row['query']}`",
                f"- top3_hit_rate: `{row['top3_hit_rate']}`",
                f"- top1_keyword_overlap: `{row['top1_keyword_overlap']}`",
                f"- entity_exact_hit_count: `{row.get('entity_exact_hit_count', 0)}`",
                f"- misassociation_count: `{row['misassociation_count']}`",
                f"- confidence_posture: `{row['confidence_posture']}`",
                f"- recall_grade: `{row.get('recall_grade', '')}`",
                f"- expected_posture: `{row.get('expected_posture', '')}` / match=`{row.get('expected_posture_match', False)}`",
                f"- expected_recall_grade: `{row.get('expected_recall_grade', '')}` / match=`{row.get('expected_recall_grade_match', False)}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the production recall benchmark against the frozen semantic baseline.")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--vector-db", default=resolve_evomap_vector_db_path())
    parser.add_argument("--cases", default=str(DEFAULT_CASE_FILE))
    parser.add_argument("--baseline-summary", default=str(DEFAULT_BASELINE_SUMMARY))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--result-limit", type=int, default=5)
    args = parser.parse_args()

    summary = run_benchmark(
        db_path=str(args.db),
        vector_db_path=str(args.vector_db),
        cases_path=str(args.cases),
        baseline_summary_path=str(args.baseline_summary),
        output_root=str(args.output_root),
        result_limit=int(args.result_limit),
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
