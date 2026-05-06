from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ops.report_openmind_watch_window_ledger import (
    build_openmind_watch_window_ledger_entry,
    run_openmind_watch_window_ledger,
    write_openmind_watch_window_ledger_artifacts,
)


def _cohort() -> dict:
    return {
        "cohort_id": "openmind-production-canary-v1",
        "watch_window_days": 7,
    }


def _health() -> dict:
    return {"generated_at": "2026-04-09T06:24:05+00:00"}


def _regression() -> dict:
    return {"generated_at": "2026-04-09T06:04:08+00:00", "ok": True}


def _scorecard(*, state: str = "launch_canary_watch") -> dict:
    return {
        "generated_at": "2026-04-09T06:30:12+00:00",
        "_source_path": "artifacts/monitor/openmind_canary_scorecard/sample.json",
        "decision": {"state": state, "reason": "watch in progress"},
        "posture": {
            "launch_posture": "canary-ready" if state != "hold" else "not-ready",
            "rollout_posture": "watch-window active" if state == "launch_canary_watch" else ("go-live ready" if state == "go_live" else "hold"),
        },
        "domain_status": {
            "packet": "pass",
            "recall": "pass",
            "promotion": "warn",
            "crystal": "pass",
        },
        "watch_window": {
            "started_at": "2026-04-09T06:30:12+00:00",
            "ends_at": "2026-04-16T06:30:12+00:00",
            "complete": False,
            "required_days": 7,
            "elapsed_days": 0.1,
        },
        "health_summary_path": "artifacts/monitor/openmind_production_health/sample.json",
        "regression_summary_path": "artifacts/monitor/openmind_production_regression/sample.json",
    }


def test_build_openmind_watch_window_ledger_entry_tracks_transitions() -> None:
    previous = {
        "decision": {"state": "hold"},
        "domain_status": {"packet": "pass", "promotion": "pass"},
        "watch_window": {"day_index": 1},
    }
    entry = build_openmind_watch_window_ledger_entry(
        cohort=_cohort(),
        health_summary=_health(),
        regression_summary=_regression(),
        scorecard=_scorecard(),
        previous_entry=previous,
        now=datetime(2026, 4, 10, 6, 45, tzinfo=timezone.utc),
    )
    assert entry["decision"]["state"] == "launch_canary_watch"
    assert entry["watch_window"]["day_index"] == 2
    assert entry["transitions"]["decision_changed"] is True
    assert {"domain": "promotion", "from": "pass", "to": "warn"} in entry["transitions"]["domain_transitions"]


def test_write_openmind_watch_window_ledger_artifacts_writes_expected_files(tmp_path: Path) -> None:
    entry = build_openmind_watch_window_ledger_entry(
        cohort=_cohort(),
        health_summary=_health(),
        regression_summary=_regression(),
        scorecard=_scorecard(),
        now=datetime(2026, 4, 9, 7, 0, tzinfo=timezone.utc),
    )
    written = write_openmind_watch_window_ledger_artifacts(entry, tmp_path / "out", "sample")
    assert [path.name for path in written] == [
        "openmind_watch_window_ledger_sample.json",
        "openmind_watch_window_ledger_sample.md",
    ]


def test_run_openmind_watch_window_ledger_uses_latest_artifacts(tmp_path: Path) -> None:
    health_root = tmp_path / "health" / "20260409T062405Z"
    regression_root = tmp_path / "regression" / "20260409T060343Z"
    scorecard_root = tmp_path / "scorecard" / "20260409T063012Z"
    health_root.mkdir(parents=True)
    regression_root.mkdir(parents=True)
    scorecard_root.mkdir(parents=True)
    (health_root / "openmind_production_health_20260409T062405Z.json").write_text(json.dumps(_health()), encoding="utf-8")
    (regression_root / "openmind_production_regression_20260409T060343Z.json").write_text(json.dumps(_regression()), encoding="utf-8")
    (scorecard_root / "openmind_canary_scorecard_20260409T063012Z.json").write_text(json.dumps(_scorecard()), encoding="utf-8")
    cohort_file = tmp_path / "cohort.json"
    cohort_file.write_text(json.dumps(_cohort()), encoding="utf-8")

    result = run_openmind_watch_window_ledger(
        output_root=tmp_path / "ledger",
        health_root=health_root.parent,
        regression_root=regression_root.parent,
        scorecard_root=scorecard_root.parent,
        cohort_file=cohort_file,
    )

    assert result["ok"] is True
    assert result["decision"] == "launch_canary_watch"
    summary_path = Path(result["artifacts"][0])
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["inputs"]["scorecard_path"].endswith(".json")
