## Summary

Added a repository-level EvoMap testing blueprint and a focused runtime contract test suite.

Files:
- `docs/ops/evomap_testing_blueprint_20260311.md`
- `tests/test_evomap_runtime_contract.py`

## Why

The current EvoMap codebase already had ingest-side protections covered by tests:
- upstream event identity preservation
- sqlite inventory redaction
- excluding the canonical target DB from inventory discovery

What was still not explicitly locked was the runtime visibility contract:
- which promotion states are visible to runtime retrieval
- whether consult helper behavior matches retrieval gating
- whether low-groundedness atoms are intentionally hidden from consult recall

## What was added

### 1. EvoMap testing blueprint

Documented a six-layer validation model:
1. path and DB contract
2. ingest contract
3. runtime visibility gate
4. governance and promotion
5. business vertical slices
6. ops and regression

Also documented a default pytest execution order and three live smoke checks.

### 2. Runtime contract tests

Added focused tests for:
- `retrieve()` only exposing runtime-visible promotion states
- `retrieve()` excluding superseded atoms even if FTS still matches
- `routes_consult._evomap_search()` inheriting the runtime visibility gate
- consult helper excluding low-groundedness atoms

## New runtime fact confirmed

During implementation, a new runtime fact was confirmed:

- consult helper does not only rely on retrieval's promotion/status gate
- it also applies an additional groundedness gate:
  - EvoMap hits with `groundedness < 0.5` are hidden

This behavior is now reflected in the testing blueprint and locked in tests.

## Validation run

Targeted contract suite:

```bash
./.venv/bin/pytest -q \
  tests/test_evomap_runtime_contract.py \
  tests/test_openmind_store_paths.py \
  tests/test_activity_ingest.py \
  tests/test_telemetry_contract.py \
  tests/test_sqlite_inventory.py \
  tests/test_advisor_consult.py \
  tests/test_routes_evomap.py
```

Governance + E2E suite:

```bash
./.venv/bin/pytest -q \
  tests/test_promotion_engine.py \
  tests/test_evomap_chain.py \
  tests/test_evomap_review_experiment.py \
  tests/test_evomap_evolution.py \
  tests/test_phase4_evomap.py \
  tests/test_evomap_e2e.py
```

Both passed.

## Takeaway

EvoMap ingest-side hardening is now covered, and runtime retrieval rules are more explicit.

The next meaningful step is not more blueprint work. It is live consumer validation:
- issue-domain canonical reads
- advisor recall/consult source behavior
- telemetry-to-canonical-to-runtime business loop
