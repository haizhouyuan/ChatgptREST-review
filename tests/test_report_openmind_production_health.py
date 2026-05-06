from __future__ import annotations

import json
from pathlib import Path

from ops.report_openmind_production_health import (
    build_openmind_production_health_summary,
    write_openmind_production_health_artifacts,
)


def _packet_summary(*, degraded: bool = False) -> dict:
    return {
        "success_rate": 1.0 if not degraded else 0.5,
        "degraded_ratio": 0.0 if not degraded else 0.5,
        "adjusted_degraded_ratio": 0.0 if not degraded else 0.5,
        "degraded_source_distribution": {} if not degraded else {"authority_anchor_missing": 1},
        "adjusted_degraded_source_distribution": {} if not degraded else {"authority_anchor_missing": 1},
        "median_auto_usefulness_score": 4.4 if not degraded else 3.2,
        "thresholds": {
            "success_rate_ok": not degraded,
            "degraded_ratio_ok": not degraded,
            "median_score_ok": not degraded,
        },
        "cases": [
            {
                "project_id": "shortmobility",
                "query": "当前 open loops 是什么？",
                "l0_authority_accuracy": True,
                "l1_open_loop_usefulness": True,
                "l2_retrieval_relevance": True,
                "l3_next_step_usefulness": True,
                "provenance_complete": True,
                "adjusted_degraded": degraded,
                "degraded_sources": ["authority_anchor_missing"] if degraded else [],
                "comparison_digest": "ok",
            }
        ],
    }


def _recall_summary(*, drifting: bool = False) -> dict:
    return {
        "current": {
            "aggregate": {
                "top3_hit_rate": 0.92 if not drifting else 0.55,
                "misassociation_rate": 0.0 if not drifting else 0.25,
                "clarify_rate": 0.0 if not drifting else 0.5,
                "expected_posture_match_rate": 1.0 if not drifting else 0.5,
                "expected_recall_grade_match_rate": 1.0 if not drifting else 0.5,
                "background_reexplanation_risk_rate": 0.0 if not drifting else 0.5,
            },
            "cases": [
                {
                    "case_id": "case-1",
                    "query": "PRS 最新合作信号",
                    "confidence_posture": "answer" if not drifting else "clarify",
                    "expected_posture": "answer",
                    "expected_posture_match": not drifting,
                    "expected_recall_grade": "bridge",
                    "expected_recall_grade_match": not drifting,
                    "misassociation_count": 0 if not drifting else 1,
                    "background_reexplanation_risk": drifting,
                }
            ],
        },
        "delta": {
            "top3_hit_rate_relative_gain": 0.25 if not drifting else 0.05,
        },
    }


def _promotion_summary(*, blocked: bool = False) -> dict:
    return {
        "counts": {"atoms": 20, "active": 10, "staged": 4},
        "rates": {"active_ratio": 0.5},
        "critical_rollout": {
            "source": "planning",
            "buckets": ["planning_review_pack", "planning_controlled"],
            "counts": {"total": 10, "active": 4, "candidate": 5, "staged": 1, "servable": 9},
            "rates": {"active_ratio": 0.4, "candidate_ratio": 0.5, "staged_ratio": 0.1, "servable_ratio": 0.9},
            "buckets_without_servable_atoms": [] if not blocked else [{"bucket": "planning_controlled", "active_atoms": 0, "candidate_atoms": 0, "staged_atoms": 1}],
            "buckets_without_active_atoms": [] if not blocked else [{"bucket": "planning_controlled", "active_atoms": 0, "candidate_atoms": 0, "staged_atoms": 1}],
            "bounded_to_noncritical_only": not blocked,
        },
        "likely_blockers": {
            "recent_blank_promotion_reason_ratio": 0.05 if not blocked else 0.25,
            "recent_staged_atoms": 4,
            "recent_blank_promotion_reason_staged_atoms": 0 if not blocked else 1,
            "sources_without_active_atoms": ([] if not blocked else [{"source": "planning.turns", "staged_atoms": 3, "candidate_atoms": 0, "active_atoms": 0}]),
            "projects_without_active_atoms": ([] if not blocked else [{"project": "prs", "staged_atoms": 2, "candidate_atoms": 0, "active_atoms": 0}]),
        },
    }


def _crystal_summary(*, risky: bool = False) -> dict:
    return {
        "projection_mode": "shadow",
        "support_threshold": 2,
        "crystal_generation": {"active_crystal_count": 1, "shadow_projection_ratio": 1.0},
        "governance": {
            "superseded_candidate_count": 1,
            "denied_preference_occurrences": 0 if not risky else 1,
            "medium_or_higher_risk_crystal_count": 0 if not risky else 1,
        },
        "manual_review": {
            "false_positive_rate": 0.0 if not risky else 0.10,
        },
        "samples": [
            {
                "crystal_id": "cr-1",
                "source_key": "thread.preference.executor",
                "risk_posture": "low" if not risky else "high",
                "winner_margin_min": 2 if not risky else 0,
            }
        ],
    }


def test_build_openmind_production_health_summary_reports_pass_state() -> None:
    summary = build_openmind_production_health_summary(
        packet_summary=_packet_summary(),
        recall_summary=_recall_summary(),
        promotion_summary=_promotion_summary(),
        crystal_summary=_crystal_summary(),
        component_artifacts={"packet": ["artifacts/packet.json"]},
    )
    assert summary["ok"] is True
    assert summary["status"] == "pass"
    assert summary["domains"]["packet"]["status"] == "pass"
    assert summary["domains"]["recall"]["status"] == "pass"
    assert summary["domains"]["promotion"]["status"] == "pass"
    assert summary["domains"]["crystal"]["status"] == "pass"
    assert len(summary["operator_questions"]) == 4


def test_build_openmind_production_health_summary_flags_problem_domains() -> None:
    summary = build_openmind_production_health_summary(
        packet_summary=_packet_summary(degraded=True),
        recall_summary=_recall_summary(drifting=True),
        promotion_summary=_promotion_summary(blocked=True),
        crystal_summary=_crystal_summary(risky=True),
    )
    assert summary["ok"] is False
    assert summary["status"] == "fail"
    assert summary["domains"]["packet"]["status"] == "fail"
    assert summary["domains"]["recall"]["status"] == "fail"
    assert summary["domains"]["promotion"]["status"] == "fail"
    assert summary["domains"]["crystal"]["status"] == "fail"
    assert summary["domains"]["packet"]["degraded_cases"][0]["project_id"] == "shortmobility"


def test_build_openmind_production_health_summary_treats_warn_as_operable() -> None:
    promotion_summary = _promotion_summary()
    promotion_summary["critical_rollout"]["bounded_to_noncritical_only"] = True
    promotion_summary["likely_blockers"]["sources_without_active_atoms"] = [
        {"source": "planning.turns", "staged_atoms": 3, "candidate_atoms": 0, "active_atoms": 0}
    ]
    summary = build_openmind_production_health_summary(
        packet_summary=_packet_summary(),
        recall_summary=_recall_summary(),
        promotion_summary=promotion_summary,
        crystal_summary=_crystal_summary(),
    )
    assert summary["ok"] is True
    assert summary["status"] == "warn"
    assert summary["domains"]["promotion"]["status"] == "warn"


def test_write_openmind_production_health_artifacts_writes_expected_files(tmp_path: Path) -> None:
    summary = build_openmind_production_health_summary(
        packet_summary=_packet_summary(),
        recall_summary=_recall_summary(),
        promotion_summary=_promotion_summary(),
        crystal_summary=_crystal_summary(),
        component_artifacts={"packet": ["artifacts/packet.json"], "recall": ["artifacts/recall.json"]},
    )
    written = write_openmind_production_health_artifacts(summary, tmp_path / "out", "sample")
    assert [path.name for path in written] == [
        "openmind_production_health_sample.json",
        "openmind_production_health_sample.md",
    ]
    payload = json.loads((tmp_path / "out" / "openmind_production_health_sample.json").read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    report = (tmp_path / "out" / "openmind_production_health_sample.md").read_text(encoding="utf-8")
    assert "Operator questions" in report
    assert "fault_domain" not in report
