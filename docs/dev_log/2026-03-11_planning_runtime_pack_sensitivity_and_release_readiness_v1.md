# 2026-03-11 Planning Runtime Pack Sensitivity And Release Readiness v1

## Scope

This is sidecar launch-readiness work for the planning reviewed runtime pack.

Included:

- sensitivity/content-safety audit
- release/freshness readiness checker
- read-only artifacts and runbook guidance

Excluded:

- default runtime retrieval changes
- runtime cutover
- promotion changes
- planning-side maintenance expansion

## Added

- [ops/audit_planning_runtime_pack_sensitivity.py](/vol1/1000/projects/ChatgptREST/ops/audit_planning_runtime_pack_sensitivity.py)
- [ops/check_planning_runtime_pack_release_readiness.py](/vol1/1000/projects/ChatgptREST/ops/check_planning_runtime_pack_release_readiness.py)
- [tests/test_audit_planning_runtime_pack_sensitivity.py](/vol1/1000/projects/ChatgptREST/tests/test_audit_planning_runtime_pack_sensitivity.py)
- [tests/test_check_planning_runtime_pack_release_readiness.py](/vol1/1000/projects/ChatgptREST/tests/test_check_planning_runtime_pack_release_readiness.py)

## Validation

```bash
./.venv/bin/python -m py_compile \
  ops/audit_planning_runtime_pack_sensitivity.py \
  ops/check_planning_runtime_pack_release_readiness.py \
  tests/test_audit_planning_runtime_pack_sensitivity.py \
  tests/test_check_planning_runtime_pack_release_readiness.py

./.venv/bin/pytest -q \
  tests/test_audit_planning_runtime_pack_sensitivity.py \
  tests/test_check_planning_runtime_pack_release_readiness.py
```

### Live Read-Only Checks

```bash
./.venv/bin/python ops/audit_planning_runtime_pack_sensitivity.py
./.venv/bin/python ops/check_planning_runtime_pack_release_readiness.py --max-age-hours 72
```

## Rollback / Freshness Guidance

- do not consume a pack older than the configured freshness window
- keep runtime hookup pinned to a specific pack directory or approved pointer
- rollback means switching the explicit hook back to the previous approved pack, not changing default retrieval
