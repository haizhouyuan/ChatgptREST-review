# 2026-04-09 OpenMind Canary Scorecard And Rollout Launch Walkthrough v1

## Purpose

Close production-readiness PR-8 by freezing the canary cohort and turning the latest health + regression evidence into a rollout decision artifact.

## What changed

Rollout mechanics:

- added `ops/data/openmind_canary_cohort_v1.json`
- added `ops/report_openmind_canary_scorecard.py`
- the scorecard consumes:
  - the latest production health rollup
  - the latest production regression summary
  - the frozen canary cohort file

Artifacts:

- canary scorecard JSON / Markdown
- rollout decision log
- post-rollout watch checklist

Contracts and runbook:

- added `docs/contracts/2026-04-09_openmind_canary_rollout_contract_v1.md`
- extended `docs/runbook.md` with the canary rollout command and interpretation

Tests:

- added `tests/test_report_openmind_canary_scorecard.py`

## Rollout posture

PR-8 does not pretend that wall-clock time has already elapsed.

The scorecard distinguishes between:

- `launch_canary_watch`
- `go_live`
- `hold`

This lets the implementation close with an explicit canary launch and a defined watch window, while still making the full go-live gate visible and auditable.

## Verification

- `pytest -q tests/test_report_openmind_canary_scorecard.py`
- `python3 ops/report_openmind_canary_scorecard.py --output-root artifacts/monitor/openmind_canary_scorecard`
- live scorecard artifact:
  - `artifacts/monitor/openmind_canary_scorecard/20260409T063012Z/openmind_canary_scorecard_20260409T063012Z.json`
  - `artifacts/monitor/openmind_canary_scorecard/20260409T063012Z/openmind_canary_scorecard_20260409T063012Z.md`
  - `artifacts/monitor/openmind_canary_scorecard/20260409T063012Z/openmind_rollout_decision_log_20260409T063012Z.md`
  - `artifacts/monitor/openmind_canary_scorecard/20260409T063012Z/openmind_post_rollout_watch_checklist_20260409T063012Z.md`
- live rollout decision:
  - `decision=launch_canary_watch`
  - `fail_domains=[]`
  - `warn_domains=[\"promotion\"]`
  - `go_live_ready=false`
