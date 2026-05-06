# 2026-03-13 Self-Iteration V2 Todo v5

## Current State

- [x] Create clean implementation branch/worktree.
- [x] Write full execution plan and initial todo.
- [x] Implement Slice A runtime knowledge policy.
- [x] Implement Slice B execution identity contract.
- [x] Implement Lane C actuator governance.
- [x] Implement Lane D observer-only outcome ledger.
- [x] Implement Lane E evaluator plane seed.
- [x] Implement Lane F decision plane and experiment registry seed.
- [ ] Run integrated validation matrix across slices A-F.
- [ ] Run full repository `pytest -q`.
- [ ] Fix any regressions found by integrated/full validation.
- [ ] Write final completion walkthrough.
- [ ] Run closeout.

## Commit Ledger

- `b04ab34` `docs: add self-iteration v2 execution plan`
- `53b31e6` `feat: add explicit runtime knowledge policy surfaces`
- `4acb701` `feat: add execution identity contract for telemetry`
- `b69174d` `docs: add self-iteration v2 parallel lane specs`
- `42ba93b` `feat: add evaluator plane seed from qa inspector`
- `d3c2f17` `feat: add actuator governance metadata and audit trails`
- `102aaee` `feat: add observer-only outcome ledger`
- `9e09954` `feat: add observer-only decision plane scaffolding`

## Guardrails

- `update_run` / `init_db` remain the highest-risk touchpoints. Outcome ledger must stay side-table only and fail-open.
- `user_hot_path` must remain `ACTIVE`-only. `STAGED` visibility is diagnostic/shadow only.
- Decision plane and experiment registry remain observer-only. No runtime mutation is permitted in v2 completion.
- Actuator governance remains metadata/audit only. Default actuator modes remain `active`.

## Validation Matrix To Run

1. `python3 -m py_compile` over all touched modules and tests.
2. Focused pytest suite for slices A-F:
   - `tests/test_evomap_runtime_contract.py`
   - `tests/test_cognitive_api.py`
   - `tests/test_advisor_consult.py`
   - `tests/test_execution_identity_contract.py`
   - `tests/test_advisor_runtime.py`
   - `tests/test_actuator_governance.py`
   - `tests/test_outcome_ledger.py`
   - `tests/test_qa_inspector.py`
   - `tests/test_evaluator_service.py`
   - `tests/test_eval_harness.py`
   - `tests/test_decision_plane.py`
   - `tests/test_advisor_runs_replay.py`
   - `tests/test_restart_recovery.py`
   - `tests/test_evomap_e2e.py`
3. Full repository regression:
   - `./.venv/bin/pytest -q`
4. Post-test review:
   - inspect failures
   - patch regressions
   - rerun affected focused suites
   - rerun full suite if any code changes land

## Notes

- GitNexus `impact`/`detect_changes` calls timed out repeatedly at 120s during this run. Lane integration was therefore kept on strict write sets and backed by focused regression suites before each commit.
- Lane C and Lane D were executed with subagents on separate writable clones because the shared worktree git metadata became read-only for those workers.
