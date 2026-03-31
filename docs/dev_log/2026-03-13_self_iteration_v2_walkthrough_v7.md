# 2026-03-13 Self-Iteration V2 Walkthrough v7

## Scope

- complete the full v2 implementation and validation loop
- integrate multi-agent lane output into one branch
- fix the only regression exposed by full repository validation

## Final implemented surface

### Slice A

- runtime retrieval policy is now explicit and path-scoped
- `USER_HOT_PATH` excludes `STAGED`
- diagnostic/shadow surfaces can still inspect `STAGED`

### Slice B

- execution identity now preserves `logical_task_id`
- telemetry and recall store `identity_confidence`
- run-linked identity has one normalization helper

### Lane C

- existing EvoMap actuators are governable
- `GateAutoTuner`, `CircuitBreaker`, `KBScorer`, `MemoryInjector` expose governance metadata and audit trails
- runtime defaults remain unchanged

### Lane D

- terminal runs write observer-only `execution_outcomes`
- ledger is fail-open and side-table only
- run spine remains authoritative

### Lane E

- `QAInspector` now feeds a normalized evaluator plane
- evaluator outputs include scores, risk label, and failure tags
- human calibration scaffolding exists but does not mutate runtime

### Lane F

- decision plane emits observer-only `promotion_proposal` and `suppression_proposal`
- experiment registry records offline/shadow/canary lifecycle
- canary runs require explicit rollback trigger

## Multi-agent integration notes

- slices A/B/E were implemented on the main integration branch
- Lane C and Lane D were delegated to worker lanes after the contracts stabilized
- worker lanes had to use writable clones because the shared worktree git metadata became read-only for them
- their outputs were reconciled back into this branch and independently regression-tested before commit

## Full validation

### Integrated matrix

Commands run:

```bash
python3 -m py_compile \
  chatgptrest/evomap/knowledge/retrieval.py \
  chatgptrest/cognitive/context_service.py \
  chatgptrest/kernel/context_assembler.py \
  chatgptrest/api/routes_consult.py \
  chatgptrest/cognitive/graph_service.py \
  chatgptrest/telemetry_contract.py \
  chatgptrest/evomap/knowledge/telemetry.py \
  chatgptrest/cognitive/telemetry_service.py \
  chatgptrest/api/routes_cognitive.py \
  chatgptrest/core/advisor_runs.py \
  chatgptrest/evomap/actuators/__init__.py \
  chatgptrest/evomap/actuators/registry.py \
  chatgptrest/evomap/actuators/gate_tuner.py \
  chatgptrest/evomap/actuators/circuit_breaker.py \
  chatgptrest/evomap/actuators/kb_scorer.py \
  chatgptrest/evomap/actuators/memory_injector.py \
  chatgptrest/core/db.py \
  chatgptrest/quality/__init__.py \
  chatgptrest/quality/outcome_ledger.py \
  chatgptrest/advisor/qa_inspector.py \
  chatgptrest/eval/evaluator_service.py \
  chatgptrest/eval/human_labels.py \
  chatgptrest/eval/decision_plane.py \
  chatgptrest/eval/experiment_registry.py \
  tests/test_evomap_runtime_contract.py \
  tests/test_cognitive_api.py \
  tests/test_advisor_consult.py \
  tests/test_execution_identity_contract.py \
  tests/test_advisor_runtime.py \
  tests/test_actuator_governance.py \
  tests/test_outcome_ledger.py \
  tests/test_qa_inspector.py \
  tests/test_evaluator_service.py \
  tests/test_eval_harness.py \
  tests/test_decision_plane.py \
  tests/test_advisor_runs_replay.py \
  tests/test_restart_recovery.py \
  tests/test_evomap_e2e.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_evomap_runtime_contract.py \
  tests/test_cognitive_api.py \
  tests/test_advisor_consult.py \
  tests/test_execution_identity_contract.py \
  tests/test_advisor_runtime.py \
  tests/test_actuator_governance.py \
  tests/test_outcome_ledger.py \
  tests/test_qa_inspector.py \
  tests/test_evaluator_service.py \
  tests/test_eval_harness.py \
  tests/test_decision_plane.py \
  tests/test_advisor_runs_replay.py \
  tests/test_restart_recovery.py \
  tests/test_evomap_e2e.py
```

Result:

- compile passed
- integrated slice matrix passed

### Full repository regression

Command run:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q
```

Result:

- full suite passed
- only warnings remained:
  - `lark_oapi` / `websockets` deprecation warnings
  - `openclaw_orch_agent.py` retired topology warning

## Regression fixed during full validation

Observed failure:

- `tests/test_attachment_contract_preflight.py::test_worker_records_attachment_contract_event_and_issue_family`

Root cause:

- issue metadata could miss `family_id` / `family_label` even when the job had already recorded `attachment_contract_missing_detected`

Fix:

- `chatgptrest/core/client_issues.py`
  - `report_issue()` now backfills attachment-contract metadata from the job's recorded event when the caller does not supply `family_id`

Why this fix is safe:

- it only activates when:
  - `job_id` is present
  - incoming issue metadata lacks `family_id`
- it does not change issue status logic, fingerprints, or job execution behavior

## Final state

- all v2 slices are implemented
- all code changes are committed
- integrated matrix is green
- full repository regression is green
- branch is ready for closeout
