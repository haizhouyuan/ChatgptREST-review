# 2026-03-11 Planning Runtime Pack Offline Validation v1

## Scope

This is a sidecar launch-readiness preparation step for the already exported planning reviewed runtime pack.

Included:

- a small offline golden-query validation harness
- a default golden-query spec file
- read-only validation artifacts

Excluded:

- runtime retrieval changes
- default runtime cutover
- planning-side maintenance expansion
- execution telemetry changes

## Added

- [ops/run_planning_runtime_pack_offline_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_runtime_pack_offline_validation.py)
- [ops/data/planning_runtime_pack_golden_queries_v1.json](/vol1/1000/projects/ChatgptREST/ops/data/planning_runtime_pack_golden_queries_v1.json)
- [tests/test_run_planning_runtime_pack_offline_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_run_planning_runtime_pack_offline_validation.py)

## Validation

```bash
./.venv/bin/python -m py_compile \
  ops/run_planning_runtime_pack_offline_validation.py \
  tests/test_run_planning_runtime_pack_offline_validation.py

./.venv/bin/pytest -q tests/test_run_planning_runtime_pack_offline_validation.py

./.venv/bin/python ops/run_planning_runtime_pack_offline_validation.py
```

## Notes

This is an offline approximation layer over the runtime pack, not a replacement for a future explicit runtime hook.
