# 2026-04-09 OpenMind Release Flags And Regression Walkthrough v1

## Purpose

Close production-readiness PR-6 by adding reversible runtime flags and a fixed broader-regression bundle.

## What changed

Runtime:

- added `CHATGPTREST_ENABLE_WAKEUP_PACKET_PROJECTION`
- added `CHATGPTREST_ENABLE_CRYSTALLIZED_LEARNING_PACKET_PROJECTION`
- `/v3/agent/turn` now records the active packet/crystal flag state inside `wake_up_packet_receipt.feature_flags`

Regression harness:

- added `ops/run_openmind_production_regression.py`
- frozen bundle groups:
  - `public_agent_packet_plane`
  - `memory_bridge_and_plugin_surface`
  - `openclaw_business_flow`

Tests:

- expanded `tests/test_routes_agent_v3.py`
- added `tests/test_run_openmind_production_regression.py`
- hardened `tests/test_openclaw_orch_agent.py` so the UI canary failure-path fixture uses a recent relative timestamp instead of a date that can age past the stale threshold

## Rollback posture

Rollback order:

1. disable crystal projection
2. disable packet projection if needed
3. restart ChatgptREST services
4. confirm receipts and regression summary reflect the disabled flags

## Canonical docs

- `docs/contracts/2026-04-09_openmind_release_flag_matrix_v1.md`
- `docs/runbook.md`

## Verification

- `pytest -q tests/test_routes_agent_v3.py tests/test_run_openmind_production_regression.py tests/test_openclaw_orch_agent.py`
- `python3 ops/run_openmind_production_regression.py --output-dir artifacts/monitor/openmind_production_regression/20260409T060343Z`
- clean regression artifact:
  - `artifacts/monitor/openmind_production_regression/20260409T060343Z/openmind_production_regression_20260409T060408Z.json`
  - `artifacts/monitor/openmind_production_regression/20260409T060343Z/openmind_production_regression_20260409T060408Z.md`
