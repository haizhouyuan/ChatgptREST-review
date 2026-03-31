# 2026-03-11 Planning Reviewed Runtime Pack v1

## Scope

This round upgrades the planning workstream from maintenance-only into an **opt-in runtime slice export**.

Included:

- a reviewed planning runtime pack / manifest
- runtime-readable docs/atoms export for the reviewed allowlist slice
- explicit opt-in retrieval pack metadata
- smoke preparation metadata for later mainline runtime hookup

Excluded:

- runtime retrieval defaults
- planning full staged content in the default runtime surface
- execution telemetry contract changes
- active knowledge promotion expansion
- planning-side reviewer/orchestration platform work

## Added

- [ops/export_planning_reviewed_runtime_pack.py](/vol1/1000/projects/ChatgptREST/ops/export_planning_reviewed_runtime_pack.py)

The exporter:

- reads the current planning allowlist
- requires clean allowlist/bootstrap alignment by default
- exports only allowlist docs with live `active/candidate` atoms
- excludes staged-only atoms from the runtime pack
- writes:
  - `manifest.json`
  - `docs.tsv`
  - `atoms.tsv`
  - `retrieval_pack.json`
  - `smoke_manifest.json`
  - `README.md`

## Validation

### Tests

```bash
./.venv/bin/python -m py_compile \
  ops/export_planning_reviewed_runtime_pack.py \
  tests/test_export_planning_reviewed_runtime_pack.py

./.venv/bin/pytest -q tests/test_export_planning_reviewed_runtime_pack.py
```

### Live Read-Only Export

```bash
./.venv/bin/python ops/export_planning_reviewed_runtime_pack.py
```

## Boundaries

This pack is **opt-in only**.

It is prepared for later explicit consumption by the mainline runtime hook, but it does **not**:

- alter default retrieval behavior
- add planning staged content to the default runtime surface
- change promotion behavior
- create a planning-side orchestration layer
