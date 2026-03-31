# 2026-03-11 Planning Runtime Pack Observability Samples v1

## Scope

This is sidecar launch-readiness preparation for the planning reviewed runtime pack.

Included:

- offline usage evidence sample events
- observability schema hints
- incident/debug template

Excluded:

- live telemetry contract changes
- runtime hook implementation
- default retrieval changes

## Added

- [ops/build_planning_runtime_pack_observability_samples.py](/vol1/1000/projects/ChatgptREST/ops/build_planning_runtime_pack_observability_samples.py)
- [tests/test_build_planning_runtime_pack_observability_samples.py](/vol1/1000/projects/ChatgptREST/tests/test_build_planning_runtime_pack_observability_samples.py)

Outputs:

- `usage_event_samples.jsonl`
- `event_schema.json`
- `incident_template.md`

## Validation

```bash
./.venv/bin/python -m py_compile \
  ops/build_planning_runtime_pack_observability_samples.py \
  tests/test_build_planning_runtime_pack_observability_samples.py

./.venv/bin/pytest -q tests/test_build_planning_runtime_pack_observability_samples.py

./.venv/bin/python ops/build_planning_runtime_pack_observability_samples.py
```

## Note

This is an offline observability preparation slice only. It does not modify the live telemetry contract.
