# 2026-03-13 Self-Iteration V2 Walkthrough v5

## Scope
- Main-thread implementation of Lane D: observer-only outcome ledger.
- Write set stayed within:
  - new `chatgptrest/quality/`
  - `chatgptrest/core/db.py`
  - `chatgptrest/core/advisor_runs.py`
  - outcome-ledger tests only

## What changed
- Added durable `execution_outcomes` table in `chatgptrest/core/db.py`.
- Added `chatgptrest/quality/outcome_ledger.py` with observer-only upsert/get helpers.
- Added `chatgptrest/quality/__init__.py` export surface.
- Wired `advisor_runs.update_run()` to upsert an outcome row when a run enters a terminal status.
- Added focused tests in `tests/test_outcome_ledger.py`.

## Observer-only guarantees
- The ledger writes to a separate side table.
- Ledger write failures are swallowed so the run spine stays authoritative.
- Upsert is keyed by `run_id`, so terminal repeats and replays do not duplicate rows.
- The hook does not alter run status, retry logic, leases, or event sequencing.
- Non-terminal updates do not write outcome rows.

## Stored fields
- `trace_id`
- `run_id`
- `job_id`
- `task_ref`
- `logical_task_id`
- `identity_confidence`
- `route`
- `provider`
- `channel`
- `session_id`
- `status`
- `degraded`
- `fallback_chain_json`
- `retrieval_refs_json`
- `artifacts_json`
- `metadata_json`

## Blast radius
- GitNexus impact on `update_run` returned `CRITICAL`.
- GitNexus impact on `init_db` also returned `CRITICAL`.
- Because of that, this lane was deliberately constrained to:
  - additive schema only
  - fail-open side-table writes only
  - no runtime mutation
  - no new control-plane dependency on ledger rows

## Verification
- `python3 -m py_compile chatgptrest/core/db.py chatgptrest/core/advisor_runs.py chatgptrest/quality/__init__.py chatgptrest/quality/outcome_ledger.py tests/test_outcome_ledger.py tests/test_advisor_runs_replay.py tests/test_restart_recovery.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_outcome_ledger.py tests/test_advisor_runs_replay.py tests/test_restart_recovery.py`

## Key assertions now locked by tests
- Terminal runs write one durable outcome row.
- Non-terminal updates do not write outcome rows.
- Artifact refs and fallback chain are captured without mutating the run spine.
- Repeated terminal updates stay idempotent via `run_id` uniqueness.
- Replay and restart-recovery suites still pass.
