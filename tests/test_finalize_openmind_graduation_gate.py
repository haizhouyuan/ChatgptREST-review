from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ops.finalize_openmind_graduation_gate import (
    build_openmind_graduation_decision,
    run_openmind_graduation_gate,
)


def _cohort() -> dict:
    return {"cohort_id": "openmind-production-canary-v1"}


def _scorecard(*, state: str = "launch_canary_watch", complete: bool = False) -> dict:
    return {
        "_source_path": "artifacts/monitor/openmind_canary_scorecard/sample.json",
        "decision": {"state": state, "reason": "sample"},
        "gates": {
            "fail_domains": [],
            "unapproved_warn_domains": [],
            "go_live_ready": state == "go_live" and complete,
        },
        "watch_window": {
            "started_at": "2026-04-09T06:30:12+00:00",
            "ends_at": "2026-04-16T06:30:12+00:00",
            "complete": complete,
            "required_days": 7,
            "elapsed_days": 7.1 if complete else 0.5,
        },
        "health_summary_path": "artifacts/monitor/openmind_production_health/sample.json",
        "regression_summary_path": "artifacts/monitor/openmind_production_regression/sample.json",
    }


def _health() -> dict:
    return {"generated_at": "2026-04-09T06:24:05+00:00"}


def _regression(*, ok: bool = True) -> dict:
    return {"generated_at": "2026-04-09T06:04:08+00:00", "ok": ok}


def test_build_openmind_graduation_decision_holds_when_watch_window_incomplete() -> None:
    summary = build_openmind_graduation_decision(
        cohort=_cohort(),
        scorecard=_scorecard(),
        health_summary=_health(),
        regression_summary=_regression(),
        ledger_entries=[],
        now=datetime(2026, 4, 9, 8, 0, tzinfo=timezone.utc),
    )
    assert summary["decision"]["state"] == "hold"
    assert summary["watch_window"]["complete"] is False


def test_build_openmind_graduation_decision_goes_live_when_window_complete_and_clean() -> None:
    summary = build_openmind_graduation_decision(
        cohort=_cohort(),
        scorecard=_scorecard(state="go_live", complete=True),
        health_summary=_health(),
        regression_summary=_regression(),
        ledger_entries=[{"watch_window": {"day_index": 1}}, {"watch_window": {"day_index": 7}}],
        now=datetime(2026, 4, 16, 7, 0, tzinfo=timezone.utc),
    )
    assert summary["decision"]["state"] == "go_live"
    assert summary["watch_window"]["ledger_days_seen"] == [1, 7]


def test_run_openmind_graduation_gate_reads_latest_artifacts(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger" / "20260409T070000Z"
    scorecard_root = tmp_path / "scorecard" / "20260409T063012Z"
    health_root = tmp_path / "health" / "20260409T062405Z"
    regression_root = tmp_path / "regression" / "20260409T060343Z"
    ledger_root.mkdir(parents=True)
    scorecard_root.mkdir(parents=True)
    health_root.mkdir(parents=True)
    regression_root.mkdir(parents=True)
    (ledger_root / "openmind_watch_window_ledger_20260409T070000Z.json").write_text(
        json.dumps({"watch_window": {"day_index": 1}}),
        encoding="utf-8",
    )
    (scorecard_root / "openmind_canary_scorecard_20260409T063012Z.json").write_text(
        json.dumps(_scorecard()),
        encoding="utf-8",
    )
    (health_root / "openmind_production_health_20260409T062405Z.json").write_text(json.dumps(_health()), encoding="utf-8")
    (regression_root / "openmind_production_regression_20260409T060343Z.json").write_text(json.dumps(_regression()), encoding="utf-8")
    cohort_file = tmp_path / "cohort.json"
    cohort_file.write_text(json.dumps(_cohort()), encoding="utf-8")

    result = run_openmind_graduation_gate(
        output_root=tmp_path / "graduation",
        ledger_root=ledger_root.parent,
        scorecard_root=scorecard_root.parent,
        health_root=health_root.parent,
        regression_root=regression_root.parent,
        cohort_file=cohort_file,
    )

    assert result["decision"] == "hold"
    payload = json.loads(Path(result["artifacts"][0]).read_text(encoding="utf-8"))
    assert payload["inputs"]["latest_ledger_path"].endswith(".json")
