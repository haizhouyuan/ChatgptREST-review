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

from chatgptrest.advisor.runtime import get_advisor_runtime, get_advisor_runtime_if_ready
from ops.run_wakeup_packet_harness import run_harness


DEFAULT_OUTPUT_ROOT = Path("artifacts/monitor/wakeup_packet_batch_harness")
DECLARED_EXTERNAL_GAP_SOURCES = {
    "personal_graph_empty",
    "memory_identity_missing",
    "captured_memory_identity_missing",
    "work_memory_identity_partial",
}
DEFAULT_CASES: list[dict[str, Any]] = [
    {
        "project_id": "shortmobility",
        "query": "请概括当前车身业务的权威事实、未决问题和下一步。",
        "trace_id": "packet-canary-shortmobility-1",
        "session_id": "packet-canary-shortmobility-session",
        "account_id": "packet-canary-account",
        "agent_id": "advisor",
        "role_id": "planning",
        "thread_id": "packet-canary-shortmobility-thread",
        "planning_task_type": "planning_general",
        "planning_status": "in_progress",
        "planning_next_step": "freeze the next board-ready shortmobility update",
        "planning_pending_actions": ["align authority anchor", "review promoted planning evidence"],
        "planning_open_questions": ["哪些未决问题必须留在董事长口径里"],
    },
    {
        "project_id": "shortmobility",
        "query": "继续推进 0497 战时管理，当前最关键的 open loops 和下一步是什么？",
        "trace_id": "packet-canary-shortmobility-2",
        "session_id": "packet-canary-shortmobility-session",
        "account_id": "packet-canary-account",
        "agent_id": "advisor",
        "role_id": "planning",
        "thread_id": "packet-canary-shortmobility-thread",
        "planning_task_type": "planning_general",
        "planning_status": "needs_followup",
        "planning_next_step": "turn the current open loops into a board-facing action list",
        "planning_pending_actions": ["clarify unresolved risks", "refresh the latest authority facts"],
        "planning_open_questions": ["哪些问题尚不能冻结为已确认事实"],
    },
    {
        "project_id": "prs",
        "query": "请概括当前行星滚柱丝杠项目的权威事实、待推进动作和下一步。",
        "trace_id": "packet-canary-prs-1",
        "session_id": "packet-canary-prs-session",
        "account_id": "packet-canary-account",
        "agent_id": "advisor",
        "role_id": "planning",
        "thread_id": "packet-canary-prs-thread",
        "planning_task_type": "research_decision",
        "planning_status": "in_progress",
        "planning_next_step": "freeze the next PRS research decision memo",
        "planning_pending_actions": ["review promoted atoms", "align authority anchor"],
        "planning_open_questions": ["哪些合作信号已经足够进入 memo"],
    },
    {
        "project_id": "prs",
        "query": "继续推进 PRS 样机与产业合作，当前最关键的 open loops 是什么？",
        "trace_id": "packet-canary-prs-2",
        "session_id": "packet-canary-prs-session",
        "account_id": "packet-canary-account",
        "agent_id": "advisor",
        "role_id": "planning",
        "thread_id": "packet-canary-prs-thread",
        "planning_task_type": "research_decision",
        "planning_status": "needs_followup",
        "planning_next_step": "turn current PRS open loops into a follow-up brief",
        "planning_pending_actions": ["refresh partner evidence", "review current blockers"],
        "planning_open_questions": ["哪些 open loops 还缺供应链证据"],
    },
]


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _slug(value: str) -> str:
    text = "".join(ch if ch.isalnum() else "-" for ch in str(value or "").strip().lower())
    parts = [part for part in text.split("-") if part]
    return "-".join(parts[:8]) or "case"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_cases(case_file: str | None) -> list[dict[str, Any]]:
    if not case_file:
        return [dict(item) for item in DEFAULT_CASES]
    raw = json.loads(Path(case_file).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("case file must contain a JSON list")
    cases: list[dict[str, Any]] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"case #{idx} must be an object")
        query = str(item.get("query") or "").strip()
        project_id = str(item.get("project_id") or "").strip()
        trace_id = str(item.get("trace_id") or f"packet-batch-{idx}").strip()
        if not query or not project_id:
            raise ValueError(f"case #{idx} must include project_id and query")
        cases.append(
            {
                "project_id": project_id,
                "query": query,
                "trace_id": trace_id,
                "session_id": str(item.get("session_id") or f"packet-session-{project_id}").strip(),
                "account_id": str(item.get("account_id") or "packet-canary-account").strip(),
                "agent_id": str(item.get("agent_id") or "advisor").strip(),
                "role_id": str(item.get("role_id") or "planning").strip(),
                "thread_id": str(item.get("thread_id") or f"packet-thread-{project_id}").strip(),
                "planning_task_type": str(item.get("planning_task_type") or "").strip(),
                "planning_status": str(item.get("planning_status") or "").strip(),
                "planning_next_step": str(item.get("planning_next_step") or "").strip(),
                "planning_pending_actions": [str(v).strip() for v in list(item.get("planning_pending_actions") or []) if str(v).strip()],
                "planning_open_questions": [str(v).strip() for v in list(item.get("planning_open_questions") or []) if str(v).strip()],
            }
        )
    return cases


def _layer_map(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    layers = {}
    for raw in list(payload.get("layers") or []):
        if isinstance(raw, Mapping):
            layer_id = str(raw.get("layer_id") or "").strip()
            if layer_id:
                layers[layer_id] = dict(raw)
    return layers


def _is_fallback_summary(text: str, *, layer_id: str) -> bool:
    normalized = " ".join(str(text or "").strip().lower().split())
    if not normalized:
        return True
    fallbacks = {
        "L0": ("no project authority anchor resolved",),
        "L1": ("no active project memory or open-loop handoff resolved",),
        "L2": ("no retrieved project knowledge or entity context resolved",),
        "L3": ("no explicit runtime handoff resolved",),
    }
    return any(marker in normalized for marker in fallbacks.get(layer_id, ()))


def _score_packet(payload: Mapping[str, Any], *, expected_project_id: str, query: str) -> dict[str, Any]:
    layers = _layer_map(payload)
    l0_ok = bool(layers.get("L0")) and not _is_fallback_summary(str(layers["L0"].get("summary") or ""), layer_id="L0")
    l1_ok = bool(layers.get("L1")) and not _is_fallback_summary(str(layers["L1"].get("summary") or ""), layer_id="L1")
    l2_ok = bool(layers.get("L2")) and not _is_fallback_summary(str(layers["L2"].get("summary") or ""), layer_id="L2")
    l3_ok = bool(layers.get("L3")) and not _is_fallback_summary(str(layers["L3"].get("summary") or ""), layer_id="L3")
    project_match = str(payload.get("project_id") or "").strip() == expected_project_id
    provenance_summary = dict(payload.get("provenance_summary") or {})
    provenance_ok = all(key in provenance_summary for key in ("authority_governance", "retrieval_plan", "promotion_audit"))
    degraded_sources = [str(item).strip() for item in list(payload.get("degraded_sources") or []) if str(item).strip()]
    adjusted_degraded = bool(payload.get("degraded")) and any(item not in DECLARED_EXTERNAL_GAP_SOURCES for item in degraded_sources)
    base = sum(1 for flag in (l0_ok, l1_ok, l2_ok, l3_ok, provenance_ok) if flag)
    score = 1.0 + (base / 5.0) * 4.0
    if not project_match:
        score = min(score, 2.0)
    if adjusted_degraded:
        score = max(1.0, score - 0.5)
    score = round(score, 2)
    quality_receipt = dict(payload.get("quality_receipt") or {})
    return {
        "query": query,
        "expected_project_id": expected_project_id,
        "project_match": project_match,
        "l0_authority_accuracy": l0_ok and project_match,
        "l1_open_loop_usefulness": l1_ok,
        "l2_retrieval_relevance": l2_ok,
        "l3_next_step_usefulness": l3_ok,
        "provenance_complete": provenance_ok,
        "degraded": bool(payload.get("degraded")),
        "adjusted_degraded": adjusted_degraded,
        "degraded_sources": degraded_sources,
        "auto_usefulness_score": score,
        "comparison_digest": str(quality_receipt.get("comparison_digest") or "").strip(),
        "truncation_count": int(quality_receipt.get("truncation_count") or 0),
        "omission_count": int(quality_receipt.get("omission_count") or 0),
    }


def _render_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Wake-Up Packet Batch Harness",
        "",
        f"- `generated_at`: `{summary['generated_at']}`",
        f"- `case_count`: `{summary['case_count']}`",
        f"- `success_rate`: `{summary['success_rate']}`",
        f"- `degraded_ratio`: `{summary['degraded_ratio']}`",
        f"- `adjusted_degraded_ratio`: `{summary['adjusted_degraded_ratio']}`",
        f"- `median_auto_usefulness_score`: `{summary['median_auto_usefulness_score']}`",
        "",
        "## Degraded-source distribution",
        "",
        f"- `raw`: `{json.dumps(summary['degraded_source_distribution'], ensure_ascii=False, sort_keys=True)}`",
        f"- `adjusted`: `{json.dumps(summary['adjusted_degraded_source_distribution'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "| Project | Query | Score | Degraded | Project match | Digest |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in list(summary.get("cases") or []):
        lines.append(
            "| {project_id} | {query} | {score} | {degraded} | {project_match} | {digest} |".format(
                project_id=str(row.get("project_id") or "").replace("|", "\\|"),
                query=str(row.get("query") or "").replace("|", "\\|"),
                score=str(row.get("auto_usefulness_score") or ""),
                degraded="yes" if row.get("adjusted_degraded") else "no",
                project_match="yes" if row.get("project_match") else "no",
                digest=str(row.get("comparison_digest") or "").replace("|", "\\|"),
            )
        )
    lines.extend(
        [
            "",
            "## Threshold check",
            "",
            f"- `min_success_rate_ok`: `{summary['thresholds']['success_rate_ok']}`",
            f"- `max_degraded_ratio_ok`: `{summary['thresholds']['degraded_ratio_ok']}`",
            f"- `min_median_score_ok`: `{summary['thresholds']['median_score_ok']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_manual_review_sample(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Wake-Up Packet Review Sample",
        "",
        "Use this file for bounded secondary review against the PR-2 packet rubric.",
        "",
    ]
    for idx, row in enumerate(list(summary.get("cases") or []), start=1):
        lines.extend(
            [
                f"## Case {idx}: {row['project_id']}",
                "",
                f"- Query: `{row['query']}`",
                f"- Auto usefulness score: `{row['auto_usefulness_score']}`",
                f"- Comparison digest: `{row['comparison_digest']}`",
                f"- L0 authority accuracy: `{row['l0_authority_accuracy']}`",
                f"- L1 open-loop usefulness: `{row['l1_open_loop_usefulness']}`",
                f"- L2 retrieval relevance: `{row['l2_retrieval_relevance']}`",
                f"- L3 next-step usefulness: `{row['l3_next_step_usefulness']}`",
                f"- Provenance complete: `{row['provenance_complete']}`",
                f"- Adjusted degraded: `{row['adjusted_degraded']}`",
                "",
                "Reviewer notes:",
                "- ",
                "",
            ]
        )
    return "\n".join(lines)


def _source_distribution(rows: list[dict[str, Any]], *, adjusted: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    flag_name = "adjusted_degraded" if adjusted else "degraded"
    for row in rows:
        if not bool(row.get(flag_name)):
            continue
        for source in [str(item).strip() for item in list(row.get("degraded_sources") or []) if str(item).strip()]:
            counts[source] = counts.get(source, 0) + 1
    return dict(sorted(counts.items()))


def run_batch_harness(
    *,
    runtime: Any,
    output_root: Path,
    cases: list[dict[str, Any]],
    min_success_rate: float = 0.95,
    max_degraded_ratio: float = 0.20,
    min_median_score: float = 4.0,
) -> dict[str, Any]:
    batch_dir = output_root / _stamp()
    batch_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    success_count = 0
    degraded_count = 0
    adjusted_degraded_count = 0
    scores: list[float] = []

    for idx, case in enumerate(cases, start=1):
        case_dir = batch_dir / f"case_{idx:02d}_{_slug(case['project_id'])}"
        harness_summary = run_harness(
            runtime=runtime,
            output_root=output_root,
            run_dir=case_dir,
            query=case["query"],
            project_id=case["project_id"],
            trace_id=case["trace_id"],
            session_id=case.get("session_id", ""),
            account_id=case.get("account_id", ""),
            agent_id=case.get("agent_id", ""),
            role_id=case.get("role_id", ""),
            thread_id=case.get("thread_id", ""),
            planning_task_layer=_planning_task_layer(case),
        )
        packet_payload = json.loads(Path(harness_summary["artifacts"]["packet_json"]).read_text(encoding="utf-8"))
        scored = _score_packet(packet_payload, expected_project_id=case["project_id"], query=case["query"])
        row = {
            "project_id": case["project_id"],
            "query": case["query"],
            "trace_id": case["trace_id"],
            "ok": bool(harness_summary.get("ok")),
            **scored,
            "artifacts": harness_summary["artifacts"],
        }
        rows.append(row)
        if row["ok"]:
            success_count += 1
        if row["degraded"]:
            degraded_count += 1
        if row["adjusted_degraded"]:
            adjusted_degraded_count += 1
        scores.append(float(row["auto_usefulness_score"]))

    case_count = len(rows)
    success_rate = round(success_count / case_count, 6) if case_count else 0.0
    degraded_ratio = round(degraded_count / case_count, 6) if case_count else 0.0
    adjusted_degraded_ratio = round(adjusted_degraded_count / case_count, 6) if case_count else 0.0
    median_score = round(float(statistics.median(scores)) if scores else 0.0, 3)
    summary = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": case_count,
        "success_rate": success_rate,
        "degraded_ratio": degraded_ratio,
        "adjusted_degraded_ratio": adjusted_degraded_ratio,
        "degraded_source_distribution": _source_distribution(rows, adjusted=False),
        "adjusted_degraded_source_distribution": _source_distribution(rows, adjusted=True),
        "median_auto_usefulness_score": median_score,
        "declared_external_gap_sources": sorted(DECLARED_EXTERNAL_GAP_SOURCES),
        "thresholds": {
            "min_success_rate": float(min_success_rate),
            "max_degraded_ratio": float(max_degraded_ratio),
            "min_median_score": float(min_median_score),
            "success_rate_ok": success_rate >= float(min_success_rate),
            "degraded_ratio_ok": adjusted_degraded_ratio <= float(max_degraded_ratio),
            "median_score_ok": median_score >= float(min_median_score),
        },
        "cases": rows,
        "artifacts": {
            "batch_summary_json": str(batch_dir / "batch_summary.json"),
            "batch_summary_md": str(batch_dir / "batch_summary.md"),
            "manual_review_sample_md": str(batch_dir / "packet_review_sample.md"),
        },
    }
    _write_json(batch_dir / "batch_summary.json", summary)
    (batch_dir / "batch_summary.md").write_text(_render_report(summary), encoding="utf-8")
    (batch_dir / "packet_review_sample.md").write_text(_render_manual_review_sample(summary), encoding="utf-8")
    return summary


def _planning_task_layer(case: Mapping[str, Any]) -> dict[str, Any] | None:
    task_type = str(case.get("planning_task_type") or "").strip()
    status = str(case.get("planning_status") or "").strip()
    next_step = str(case.get("planning_next_step") or "").strip()
    pending_actions = [str(item).strip() for item in list(case.get("planning_pending_actions") or []) if str(item).strip()]
    open_questions = [str(item).strip() for item in list(case.get("planning_open_questions") or []) if str(item).strip()]
    if not any((task_type, status, next_step, pending_actions, open_questions)):
        return None
    return {
        "task_id": str(case.get("trace_id") or "").strip() or f"packet-{str(case.get('project_id') or '').strip()}",
        "task_type": task_type or "planning_general",
        "checkpoint": {
            "current_status": status,
            "pending_actions": pending_actions,
            "open_questions": open_questions,
        },
        "handoff": {
            "next_recommended_step": next_step,
            "pending_actions": pending_actions,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run wake-up packet canary evaluation across multiple project/query cases.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--case-file", default="")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--min-success-rate", type=float, default=0.95)
    parser.add_argument("--max-degraded-ratio", type=float, default=0.20)
    parser.add_argument("--min-median-score", type=float, default=4.0)
    args = parser.parse_args()

    runtime = get_advisor_runtime_if_ready() or get_advisor_runtime()
    summary = run_batch_harness(
        runtime=runtime,
        output_root=Path(args.output_root),
        cases=_load_cases(str(args.case_file or "").strip() or None),
        min_success_rate=float(args.min_success_rate),
        max_degraded_ratio=float(args.max_degraded_ratio),
        min_median_score=float(args.min_median_score),
    )
    print(json.dumps(summary, ensure_ascii=False))
    if bool(args.strict):
        checks = dict(summary.get("thresholds") or {})
        if not (checks.get("success_rate_ok") and checks.get("degraded_ratio_ok") and checks.get("median_score_ok")):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
