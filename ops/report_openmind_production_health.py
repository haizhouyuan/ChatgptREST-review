#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.advisor.runtime import get_advisor_runtime, get_advisor_runtime_if_ready
from chatgptrest.core.openmind_paths import (
    resolve_evomap_knowledge_runtime_db_path,
    resolve_evomap_vector_db_path,
)
from ops.report_crystallized_learning_governance import (
    build_crystallized_learning_governance_report,
    write_crystallized_learning_governance_artifacts,
)
from ops.report_evomap_promotion_inventory import (
    build_promotion_inventory,
    write_promotion_inventory_artifacts,
)
from ops.run_evomap_recall_production_benchmark import (
    DEFAULT_BASELINE_SUMMARY,
    DEFAULT_CASE_FILE,
    run_benchmark,
)
from ops.run_wakeup_packet_batch_harness import _load_cases, run_batch_harness


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "openmind_production_health"
PACKET_THRESHOLD_SUCCESS_RATE = 0.95
PACKET_THRESHOLD_MAX_DEGRADED_RATIO = 0.20
PACKET_THRESHOLD_MIN_MEDIAN_SCORE = 4.0
RECALL_THRESHOLD_MIN_TOP3_GAIN = 0.20
RECALL_THRESHOLD_MAX_MISASSOCIATION = 0.05
PROMOTION_THRESHOLD_MAX_BLANK_REASON_RATIO = 0.10
CRYSTAL_THRESHOLD_MAX_FALSE_POSITIVE_RATE = 0.05


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_memory_db() -> Path:
    raw = os.environ.get("OPENMIND_MEMORY_DB", "").strip() or "~/.openmind/memory.db"
    return Path(raw).expanduser()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _maybe_reexec_under_venv() -> None:
    if not VENV_PYTHON.exists():
        return
    current = Path(sys.executable)
    target = VENV_PYTHON
    if current == target:
        return
    os.execv(str(target), [str(target), str(Path(__file__).resolve()), *sys.argv[1:]])


def _status(pass_ok: bool, warn: bool = False) -> str:
    if not pass_ok:
        return "fail"
    if warn:
        return "warn"
    return "pass"


def _layer_coverage(packet_summary: Mapping[str, Any]) -> dict[str, float]:
    rows = [dict(row) for row in list(packet_summary.get("cases") or []) if isinstance(row, Mapping)]
    denom = max(1, len(rows))
    keys = (
        "l0_authority_accuracy",
        "l1_open_loop_usefulness",
        "l2_retrieval_relevance",
        "l3_next_step_usefulness",
        "provenance_complete",
    )
    return {
        key: round(sum(1 for row in rows if bool(row.get(key))) / denom, 6)
        for key in keys
    }


def _packet_health(packet_summary: Mapping[str, Any]) -> dict[str, Any]:
    thresholds = dict(packet_summary.get("thresholds") or {})
    rows = [dict(row) for row in list(packet_summary.get("cases") or []) if isinstance(row, Mapping)]
    degraded_cases = [
        {
            "project_id": str(row.get("project_id") or "").strip(),
            "query": str(row.get("query") or "").strip(),
            "degraded_sources": list(row.get("degraded_sources") or []),
            "comparison_digest": str(row.get("comparison_digest") or "").strip(),
        }
        for row in rows
        if bool(row.get("adjusted_degraded"))
    ]
    failing_checks = []
    if not bool(thresholds.get("success_rate_ok")):
        failing_checks.append("compile_success_rate")
    if not bool(thresholds.get("degraded_ratio_ok")):
        failing_checks.append("degraded_ratio")
    if not bool(thresholds.get("median_score_ok")):
        failing_checks.append("packet_usefulness")
    return {
        "status": _status(not failing_checks),
        "success_rate": float(packet_summary.get("success_rate") or 0.0),
        "degraded_ratio": float(packet_summary.get("degraded_ratio") or 0.0),
        "adjusted_degraded_ratio": float(packet_summary.get("adjusted_degraded_ratio") or 0.0),
        "degraded_source_distribution": dict(packet_summary.get("degraded_source_distribution") or {}),
        "adjusted_degraded_source_distribution": dict(packet_summary.get("adjusted_degraded_source_distribution") or {}),
        "median_auto_usefulness_score": float(packet_summary.get("median_auto_usefulness_score") or 0.0),
        "thresholds": {
            "min_success_rate": PACKET_THRESHOLD_SUCCESS_RATE,
            "max_adjusted_degraded_ratio": PACKET_THRESHOLD_MAX_DEGRADED_RATIO,
            "min_median_auto_usefulness_score": PACKET_THRESHOLD_MIN_MEDIAN_SCORE,
            "success_rate_ok": bool(thresholds.get("success_rate_ok")),
            "degraded_ratio_ok": bool(thresholds.get("degraded_ratio_ok")),
            "median_score_ok": bool(thresholds.get("median_score_ok")),
        },
        "layer_coverage": _layer_coverage(packet_summary),
        "degraded_cases": degraded_cases,
        "failing_checks": failing_checks,
    }


def _recall_health(recall_summary: Mapping[str, Any]) -> dict[str, Any]:
    current = dict(dict(recall_summary.get("current") or {}).get("aggregate") or {})
    delta = dict(recall_summary.get("delta") or {})
    case_rows = [dict(row) for row in list(dict(recall_summary.get("current") or {}).get("cases") or []) if isinstance(row, Mapping)]
    attention_cases = [
        {
            "case_id": str(row.get("case_id") or "").strip(),
            "query": str(row.get("query") or "").strip(),
            "confidence_posture": str(row.get("confidence_posture") or "").strip(),
            "expected_posture": str(row.get("expected_posture") or "").strip(),
            "expected_posture_match": bool(row.get("expected_posture_match")),
            "expected_recall_grade": str(row.get("expected_recall_grade") or "").strip(),
            "expected_recall_grade_match": bool(row.get("expected_recall_grade_match")),
            "misassociation_count": int(row.get("misassociation_count") or 0),
            "background_reexplanation_risk": bool(row.get("background_reexplanation_risk")),
        }
        for row in case_rows
        if int(row.get("misassociation_count") or 0) > 0
        or (
            bool(str(row.get("expected_posture") or "").strip())
            and not bool(row.get("expected_posture_match"))
        )
        or (
            bool(str(row.get("expected_recall_grade") or "").strip())
            and not bool(row.get("expected_recall_grade_match"))
        )
        or (
            bool(row.get("background_reexplanation_risk"))
            and str(row.get("confidence_posture") or "").strip() != "abstain"
        )
    ]
    top3_gain_ok = float(delta.get("top3_hit_rate_relative_gain") or 0.0) >= RECALL_THRESHOLD_MIN_TOP3_GAIN
    misassociation_ok = float(current.get("misassociation_rate") or 0.0) <= RECALL_THRESHOLD_MAX_MISASSOCIATION
    warn = bool(attention_cases) and top3_gain_ok and misassociation_ok
    failing_checks = []
    if not top3_gain_ok:
        failing_checks.append("top3_gain")
    if not misassociation_ok:
        failing_checks.append("misassociation_rate")
    return {
        "status": _status(not failing_checks, warn=warn),
        "aggregate": current,
        "delta": delta,
        "thresholds": {
            "min_top3_hit_rate_relative_gain": RECALL_THRESHOLD_MIN_TOP3_GAIN,
            "max_misassociation_rate": RECALL_THRESHOLD_MAX_MISASSOCIATION,
            "top3_gain_ok": top3_gain_ok,
            "misassociation_ok": misassociation_ok,
            "expected_posture_match_rate": float(current.get("expected_posture_match_rate") or 0.0),
            "expected_recall_grade_match_rate": float(current.get("expected_recall_grade_match_rate") or 0.0),
        },
        "attention_cases": attention_cases,
        "failing_checks": failing_checks,
    }


def _promotion_health(promotion_summary: Mapping[str, Any]) -> dict[str, Any]:
    counts = dict(promotion_summary.get("counts") or {})
    rates = dict(promotion_summary.get("rates") or {})
    blockers = dict(promotion_summary.get("likely_blockers") or {})
    critical = dict(promotion_summary.get("critical_rollout") or {})
    blank_ratio = float(blockers.get("recent_blank_promotion_reason_ratio") or 0.0)
    blank_ratio_ok = blank_ratio < PROMOTION_THRESHOLD_MAX_BLANK_REASON_RATIO
    critical_without_servable = list(critical.get("buckets_without_servable_atoms") or [])
    critical_without_active = list(critical.get("buckets_without_active_atoms") or [])
    noncritical_attention = bool(list(blockers.get("sources_without_active_atoms") or [])) or bool(list(blockers.get("projects_without_active_atoms") or []))
    failing_checks = []
    if not blank_ratio_ok:
        failing_checks.append("blank_promotion_reason_ratio")
    if critical_without_servable:
        failing_checks.append("critical_buckets_without_servable_atoms")
    attention = bool(critical_without_active) or noncritical_attention
    return {
        "status": _status(not failing_checks, warn=attention and not failing_checks),
        "counts": counts,
        "rates": rates,
        "critical_rollout": {
            "source": str(critical.get("source") or "").strip(),
            "buckets": list(critical.get("buckets") or []),
            "counts": dict(critical.get("counts") or {}),
            "rates": dict(critical.get("rates") or {}),
            "buckets_without_servable_atoms": critical_without_servable[:10],
            "buckets_without_active_atoms": critical_without_active[:10],
            "bounded_to_noncritical_only": bool(critical.get("bounded_to_noncritical_only")),
        },
        "likely_blockers": {
            "recent_blank_promotion_reason_ratio": blank_ratio,
            "recent_staged_atoms": int(blockers.get("recent_staged_atoms") or 0),
            "recent_blank_promotion_reason_staged_atoms": int(blockers.get("recent_blank_promotion_reason_staged_atoms") or 0),
            "sources_without_active_atoms": list(blockers.get("sources_without_active_atoms") or [])[:5],
            "projects_without_active_atoms": list(blockers.get("projects_without_active_atoms") or [])[:5],
        },
        "thresholds": {
            "max_recent_blank_promotion_reason_ratio": PROMOTION_THRESHOLD_MAX_BLANK_REASON_RATIO,
            "blank_ratio_ok": blank_ratio_ok,
            "critical_buckets_without_servable_atoms_ok": not critical_without_servable,
        },
        "failing_checks": failing_checks,
    }


def _crystal_health(crystal_summary: Mapping[str, Any]) -> dict[str, Any]:
    governance = dict(crystal_summary.get("governance") or {})
    manual_review = dict(crystal_summary.get("manual_review") or {})
    generation = dict(crystal_summary.get("crystal_generation") or {})
    false_positive_rate = float(manual_review.get("false_positive_rate") or 0.0)
    denied_count = int(governance.get("denied_preference_occurrences") or 0)
    medium_or_higher = int(governance.get("medium_or_higher_risk_crystal_count") or 0)
    projection_shadow = str(crystal_summary.get("projection_mode") or "").strip() == "shadow"
    failing_checks = []
    if false_positive_rate > CRYSTAL_THRESHOLD_MAX_FALSE_POSITIVE_RATE:
        failing_checks.append("false_positive_rate")
    if denied_count > 0:
        failing_checks.append("denied_preference_occurrences")
    if not projection_shadow:
        failing_checks.append("projection_mode")
    return {
        "status": _status(not failing_checks, warn=medium_or_higher > 0 and not failing_checks),
        "projection_mode": str(crystal_summary.get("projection_mode") or "").strip(),
        "support_threshold": int(crystal_summary.get("support_threshold") or 0),
        "active_crystal_count": int(generation.get("active_crystal_count") or 0),
        "shadow_projection_ratio": float(generation.get("shadow_projection_ratio") or 0.0),
        "superseded_candidate_count": int(governance.get("superseded_candidate_count") or 0),
        "denied_preference_occurrences": denied_count,
        "medium_or_higher_risk_crystal_count": medium_or_higher,
        "false_positive_rate": false_positive_rate,
        "high_risk_samples": [
            {
                "crystal_id": str(sample.get("crystal_id") or "").strip(),
                "source_key": str(sample.get("source_key") or "").strip(),
                "risk_posture": str(sample.get("risk_posture") or "").strip(),
                "winner_margin_min": int(sample.get("winner_margin_min") or 0),
            }
            for sample in list(crystal_summary.get("samples") or [])
            if str(dict(sample).get("risk_posture") or "").strip() == "high"
        ],
        "thresholds": {
            "max_false_positive_rate": CRYSTAL_THRESHOLD_MAX_FALSE_POSITIVE_RATE,
            "false_positive_rate_ok": false_positive_rate <= CRYSTAL_THRESHOLD_MAX_FALSE_POSITIVE_RATE,
            "projection_mode_ok": projection_shadow,
            "denied_preference_occurrences_ok": denied_count == 0,
        },
        "failing_checks": failing_checks,
    }


def build_openmind_production_health_summary(
    *,
    packet_summary: Mapping[str, Any],
    recall_summary: Mapping[str, Any],
    promotion_summary: Mapping[str, Any],
    crystal_summary: Mapping[str, Any],
    component_artifacts: Mapping[str, list[str]] | None = None,
) -> dict[str, Any]:
    packet = _packet_health(packet_summary)
    recall = _recall_health(recall_summary)
    promotion = _promotion_health(promotion_summary)
    crystal = _crystal_health(crystal_summary)
    domains = {
        "packet": packet,
        "recall": recall,
        "promotion": promotion,
        "crystal": crystal,
    }
    overall_ok = all(str(payload.get("status") or "") != "fail" for payload in domains.values())
    overall_attention = any(str(payload.get("status") or "") == "warn" for payload in domains.values())
    operator_questions = [
        {
            "fault_domain": "packet",
            "question": "Are wake-up packets compiling cleanly, and which canary cases are degraded?",
            "status": packet["status"],
            "primary_signal": {
                "success_rate": packet["success_rate"],
                "adjusted_degraded_ratio": packet["adjusted_degraded_ratio"],
                "degraded_case_count": len(packet["degraded_cases"]),
            },
            "first_response_path": "Run ops/report_openmind_production_health.py and inspect the packet sub-artifacts plus docs/runbook.md#OpenMind Production Health.",
        },
        {
            "fault_domain": "recall",
            "question": "Is recall drifting away from the frozen benchmark or mis-associating projects?",
            "status": recall["status"],
            "primary_signal": {
                "top3_hit_rate_relative_gain": float(recall["delta"].get("top3_hit_rate_relative_gain") or 0.0),
                "misassociation_rate": float(recall["aggregate"].get("misassociation_rate") or 0.0),
                "attention_case_count": len(recall["attention_cases"]),
            },
            "first_response_path": "Inspect the recall benchmark report and follow docs/runbook.md#OpenMind Production Health for clarify/abstain and project-misassociation handling.",
        },
        {
            "fault_domain": "promotion",
            "question": "Is promotion blocked by blank reasons or sources/projects without active atoms?",
            "status": promotion["status"],
            "primary_signal": {
                "recent_blank_promotion_reason_ratio": promotion["likely_blockers"]["recent_blank_promotion_reason_ratio"],
                "sources_without_active_atoms": len(promotion["likely_blockers"]["sources_without_active_atoms"]),
                "projects_without_active_atoms": len(promotion["likely_blockers"]["projects_without_active_atoms"]),
            },
            "first_response_path": "Inspect the promotion blockers report and follow docs/runbook.md#OpenMind Production Health for promotion blockage triage.",
        },
        {
            "fault_domain": "crystal",
            "question": "Are shadow crystals churning or conflicting in a way that threatens advisory safety?",
            "status": crystal["status"],
            "primary_signal": {
                "active_crystal_count": crystal["active_crystal_count"],
                "medium_or_higher_risk_crystal_count": crystal["medium_or_higher_risk_crystal_count"],
                "false_positive_rate": crystal["false_positive_rate"],
            },
            "first_response_path": "Inspect the crystal governance report and follow docs/runbook.md#OpenMind Production Health for crystal conflict triage.",
        },
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "warn" if overall_ok and overall_attention else ("pass" if overall_ok else "fail"),
        "ok": overall_ok,
        "domains": domains,
        "operator_questions": operator_questions,
        "component_artifacts": dict(component_artifacts or {}),
    }


def write_openmind_production_health_artifacts(
    summary: Mapping[str, Any],
    output_dir: str | Path,
    stamp: str,
) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / f"openmind_production_health_{stamp}.json"
    _write_json(summary_path, summary)

    lines = [
        "# OpenMind Production Health",
        "",
        f"- `status`: `{summary['status']}`",
        f"- `ok`: `{summary['ok']}`",
        "",
        "## Domain status",
        "",
    ]
    for name, payload in dict(summary.get("domains") or {}).items():
        lines.append(f"- `{name}`: `{payload['status']}`")
    lines.extend(["", "## Operator questions", ""])
    for item in list(summary.get("operator_questions") or []):
        signal_json = json.dumps(item.get("primary_signal") or {}, ensure_ascii=False, sort_keys=True)
        lines.extend(
            [
                f"### {item['fault_domain']}",
                "",
                f"- question: {item['question']}",
                f"- status: `{item['status']}`",
                f"- primary_signal: `{signal_json}`",
                f"- first_response_path: {item['first_response_path']}",
                "",
            ]
        )
    lines.extend(["## Component artifacts", ""])
    for name, artifacts in dict(summary.get("component_artifacts") or {}).items():
        lines.append(f"- `{name}`:")
        for path in list(artifacts or []):
            lines.append(f"  - `{path}`")
    report_path = out / f"openmind_production_health_{stamp}.md"
    report_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return [summary_path, report_path]


def run_openmind_production_health(
    *,
    output_root: str | Path,
    memory_db: str | Path,
    sample_size: int = 10,
) -> dict[str, Any]:
    stamp = _stamp()
    batch_dir = Path(output_root) / stamp
    batch_dir.mkdir(parents=True, exist_ok=True)

    runtime = get_advisor_runtime_if_ready() or get_advisor_runtime()
    packet_summary = run_batch_harness(
        runtime=runtime,
        output_root=batch_dir / "packet",
        cases=_load_cases(None),
    )

    recall_summary = run_benchmark(
        db_path=resolve_evomap_knowledge_runtime_db_path(),
        vector_db_path=resolve_evomap_vector_db_path(),
        cases_path=DEFAULT_CASE_FILE,
        baseline_summary_path=DEFAULT_BASELINE_SUMMARY,
        output_root=batch_dir / "recall",
    )

    promotion_summary = build_promotion_inventory(db_path=resolve_evomap_knowledge_runtime_db_path())
    promotion_artifacts = write_promotion_inventory_artifacts(promotion_summary, batch_dir / "promotion", stamp)

    crystal_summary = build_crystallized_learning_governance_report(
        db_path=memory_db,
        sample_size=max(1, int(sample_size or 1)),
    )
    crystal_artifacts = write_crystallized_learning_governance_artifacts(crystal_summary, batch_dir / "crystal", stamp)

    summary = build_openmind_production_health_summary(
        packet_summary=packet_summary,
        recall_summary=recall_summary,
        promotion_summary=promotion_summary,
        crystal_summary=crystal_summary,
        component_artifacts={
            "packet": [str(path) for path in packet_summary.get("artifacts", {}).values()],
            "recall": [str(path) for path in dict(recall_summary.get("artifacts") or {}).values()],
            "promotion": [str(path) for path in promotion_artifacts],
            "crystal": [str(path) for path in crystal_artifacts],
        },
    )
    written = write_openmind_production_health_artifacts(summary, batch_dir, stamp)
    return {
        "ok": bool(summary.get("ok")),
        "status": str(summary.get("status") or ""),
        "summary": summary,
        "artifacts": [str(path) for path in written],
        "component_artifacts": dict(summary.get("component_artifacts") or {}),
        "output_dir": str(batch_dir),
    }


def main() -> int:
    _maybe_reexec_under_venv()
    parser = argparse.ArgumentParser(description="Generate a production health rollup for OpenMind/ChatgptREST observability.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--memory-db", default=str(_default_memory_db()))
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    result = run_openmind_production_health(
        output_root=args.output_root,
        memory_db=args.memory_db,
        sample_size=max(1, int(args.sample_size or 1)),
    )
    print(json.dumps({k: v for k, v in result.items() if k != "summary"}, ensure_ascii=False))
    if args.strict and not bool(result.get("ok")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
