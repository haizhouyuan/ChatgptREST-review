# 2026-03-11 Planning Review Bundle Validator And Fixture Bundle v1

## Scope

This round stays inside `planning review-plane / bootstrap maintenance`.

Included:

- a validator for portable planning review bundles
- a small reusable maintenance fixture bundle for drift scenarios

Excluded:

- runtime retrieval defaults
- planning runtime cutover
- execution telemetry contract changes
- active knowledge promotion changes

## Added

- [ops/validate_planning_review_bundle.py](/vol1/1000/projects/ChatgptREST/ops/validate_planning_review_bundle.py)
  - validates bundle file presence
  - validates queue/scaffold field contracts
  - validates queue/scaffold doc-id alignment
  - validates `selected_docs` count consistency across `review_queue.json`, `review_queue.tsv`, `summary.json`, and `review_decisions_template.tsv`
- [ops/build_planning_review_maintenance_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/ops/build_planning_review_maintenance_fixture_bundle.py)
  - emits a small stable fixture set for maintenance drift scenarios
  - scenarios:
    - allowlist missing live atom
    - stale bootstrap outside allowlist
    - latest-output backlog hotspot
    - archive-only excluded from candidate pool

## Tests

- [tests/test_validate_planning_review_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_validate_planning_review_bundle.py)
- [tests/test_build_planning_review_maintenance_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_build_planning_review_maintenance_fixture_bundle.py)

## Validation

```bash
./.venv/bin/python -m py_compile \
  ops/validate_planning_review_bundle.py \
  ops/build_planning_review_maintenance_fixture_bundle.py \
  tests/test_validate_planning_review_bundle.py \
  tests/test_build_planning_review_maintenance_fixture_bundle.py

./.venv/bin/pytest -q \
  tests/test_validate_planning_review_bundle.py \
  tests/test_build_planning_review_maintenance_fixture_bundle.py
```

### Live Read-Only Validation

```bash
./.venv/bin/python ops/validate_planning_review_bundle.py \
  --bundle-dir artifacts/monitor/planning_review_priority_cycle/20260311T065947Z/bundle
```

Validator result on the latest planning maintenance bundle:

- `ok = true`
- `selected_docs = 50`
- queue/scaffold counts aligned
- queue/scaffold doc ids aligned

## Outcome

Planning maintenance now has:

- a portable bundle validator for reviewer handoff artifacts
- a stable fixture bundle for future maintenance regression work
