# 2026-03-13 Launch Prep Walkthrough v2

This version supersedes `walkthrough_v1` with actual launch-prep execution
results.

## Baseline

- clean worktree:
  `/tmp/chatgptrest-launch-prep-final-20260313`
- branch:
  `codex/launch-prep-final-20260313`
- launch baseline head before extra prep fixes:
  `3132362`

That baseline already included merged PR `#177`.

## Issue 174 / PR 177 Adjudication

During review, `#177` still had a real bug:

- stale historical `groundedness=1.0` survived reruns for no-anchor planning
  atoms

This was fixed on the PR branch in:

- `abce254` `fix(planning): clear stale groundedness on no-anchor rerun`

`#177` was then merged to `master` as:

- `3132362` `Merge pull request #177 from haizhouyuan/codex/issue174-groundedness-clean-20260313`

## Launch-Prep Fixes Landed On This Branch

### 1. Missing test fix from post-merge validation branch

- `6dae5e7` `test: make evomap memory injector fixture time-relative`

Reason:

- current `master` still failed full `pytest -q` on
  `tests/test_evomap_evolution.py::TestMemoryInjector::test_t6_memory_retrieval_with_data`

### 2. Missing smoke/verifier fixes from post-merge validation branch

- `40e1f8f` `fix: harden evomap launch and telemetry smoke auth`
- `b541f9b` `fix: align openclaw telemetry live smoke with session reuse`
- `4cc5fb2` `fix: align openclaw verifier with retired topology extras`

Reason:

- `run_evomap_launch_smoke.py` still returned `401 unauthorized`
- `verify_openclaw_openmind_stack.py` still reported
  `topology_recognized=false` and `skills_repo_only=false`

## Validation Results

### Full repository regression

- initial run:
  [pytest_q.log](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/full_pytest/pytest_q.log)
- initial blocker:
  `tests/test_evomap_evolution.py::TestMemoryInjector::test_t6_memory_retrieval_with_data`
- rerun after `6dae5e7`:
  - [pytest_q.log](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/full_pytest_rerun1/pytest_q.log)
  - [pytest_q.exit](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/full_pytest_rerun1/pytest_q.exit)
  - result:
    `0`
- final run after all launch-prep fixes:
  - [pytest_q.log](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/final_full_pytest/pytest_q.log)
  - [pytest_q.exit](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/final_full_pytest/pytest_q.exit)
  - result:
    `0`

### Focused issue174 / launch-fix tests

- planning suite:
  - [pytest_q.log](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/planning_suite/pytest_q.log)
  - [pytest_q.exit](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/planning_suite/pytest_q.exit)
- affected smoke/verifier tests:
  - [pytest_q.log](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/affected_tests/pytest_q.log)
  - [pytest_q.exit](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/affected_tests/pytest_q.exit)

### Product smokes

- execution plane parity:
  - [smoke.exit](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/execution_plane_parity/smoke.exit)
- EvoMap launch:
  - initial fail:
    [launch_smoke.json](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/evomap_launch/launch_smoke.json)
  - rerun pass:
    [launch_smoke.json](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/evomap_launch_rerun/launch_smoke.json)
- EvoMap telemetry live smoke:
  - [evomap_telemetry_live_smoke_rerun.json](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/evomap_telemetry_live_smoke_rerun.json)
- OpenClaw telemetry live smoke:
  - [report.json](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/openclaw_telemetry_rerun/report.json)
- OpenClaw/OpenMind verifier:
  - initial fail:
    [verify_openclaw_openmind_stack.json](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/verify_openclaw_openmind/verify_openclaw_openmind_stack.json)
  - rerun pass:
    [verify_openclaw_openmind_stack.json](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/verify_openclaw_openmind_rerun/verify_openclaw_openmind_stack.json)

### Convergence bundle

- [summary.json](/tmp/chatgptrest-launch-prep-final-20260313/artifacts/release_validation/launch_prep_20260313/convergence/summary.json)
- result:
  - `ok=true`
  - `required_ok=true`

## Decision On Post-Merge Validation Branch

Do not wholesale-merge `codex/postmerge-validation-20260313`.

Reason:

- it contains many versioned docs that point to a different temporary worktree
  path
- only the concrete code/test fixes needed for current launch were cherry-picked
  here
- this branch now carries a fresh launch-prep report with current artifact paths

## Net Result

After merging `#177` and landing the missing launch-prep fixes, the current
branch is release-ready:

- no remaining failing repository regression
- no remaining failing launch-critical smoke
- convergence bundle fully green
