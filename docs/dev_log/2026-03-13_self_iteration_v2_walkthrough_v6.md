# 2026-03-13 Self-Iteration V2 Walkthrough v6

## Scope

- Integrate all v2 slices on one branch:
  - Slice A: runtime knowledge policy
  - Slice B: execution identity contract
  - Lane C: actuator governance
  - Lane D: observer-only outcome ledger
  - Lane E: evaluator plane seed
  - Lane F: decision plane + experiment registry seed
- Freeze the integrated state before running broader validation.

## What is now true

### 1. Retrieval policy is path-scoped

- `USER_HOT_PATH` is `ACTIVE`-only.
- `DIAGNOSTIC_PATH` and `SHADOW_EXPERIMENT_PATH` can observe `STAGED`.
- the cognitive hot path, consult path, and legacy context assembly are now explicit about their retrieval surface.

### 2. Execution identity is explicit

- telemetry now carries `logical_task_id` and `identity_confidence`.
- recall and telemetry ingest preserve execution identity instead of silently collapsing onto partial fields.
- `advisor_runs.execution_identity_for_run()` gives one normalization point for run-linked identity.

### 3. Existing runtime actuators are now governable

- `GateAutoTuner`, `CircuitBreaker`, `KBScorer`, and `MemoryInjector` expose:
  - governance metadata
  - audit trail
  - governance update surface
- observer payloads now include governance and audit event context.
- default runtime behavior is unchanged.

### 4. Terminal runs now produce an observer-only durable outcome row

- `execution_outcomes` is a side table keyed by `run_id`.
- writes happen only on terminal run transitions.
- failures are swallowed so the run spine remains authoritative.

### 5. Evaluator output is normalized

- `QAInspector` can now emit normalized evaluator results.
- evaluator results expose:
  - quality score
  - grounding score
  - usefulness score
  - risk label
  - failure tags
- human-label comparison scaffolding exists for future meta-eval.

### 6. The decision plane exists but stays observer-only

- high-quality evaluated outcomes can emit `promotion_proposal`.
- weak-grounding / kb-underused outcomes with noisy retrieval evidence can emit `suppression_proposal`.
- experiment lifecycle can be registered without changing runtime defaults.
- canary runs require explicit rollback evidence.

## Multi-agent implementation notes

- Lane C and Lane D were delegated to separate worker lanes because their write sets were independent after slices A/B stabilized.
- the shared worktree became read-only for worker git metadata, so both lanes were validated against writable clones and then reconciled into this main integration branch.
- the integrated branch was checked against those lane clones before acceptance.

## Why this is the correct v2 cut

- It solves the immediate hot-path problem first.
- It stabilizes identity before introducing observer ledgers or proposals.
- It governs existing runtime adaptors before adding any new self-improvement loop.
- It keeps all new quality/eval/decision machinery observer-only, which is the safe boundary for v2.

## Remaining work after this checkpoint

- run integrated focused regression across slices A-F
- run full repository regression
- patch any fallout
- only then mark v2 complete and close out
