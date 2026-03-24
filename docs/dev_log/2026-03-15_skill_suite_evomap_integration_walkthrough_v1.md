# 2026-03-15 Skill Suite EvoMap Integration Walkthrough v1

## Goal

Connect the audited skill-suite validation bundle into the current EvoMap stack with three linked layers:

1. telemetry ingest for live operational signals
2. experiment registry for replayable evaluation history
3. staged review-plane import for durable knowledge objects

This closes the gap left after `skill_suite_validation_bundle` was made auditable but still lived only as an artifact tree.

## Scope

New implementation:

- `chatgptrest/evomap/knowledge/skill_suite_review_plane.py`
- `ops/ingest_skill_suite_validation_to_evomap.py`
- `tests/test_skill_suite_review_plane.py`
- `tests/test_ingest_skill_suite_validation_to_evomap.py`

Adjusted behavior:

- telemetry emitted by skill-suite bundle ingest now uses EvoMap live-ingest-supported event types:
  - bundle -> `workflow.completed` / `workflow.failed`
  - case -> `tool.completed` / `tool.failed`
- original skill-suite semantics remain preserved in payload as `validation_signal`

## Design

### Layer 1: Telemetry

`ops/ingest_skill_suite_validation_to_evomap.py` builds a compact event stream from the bundle:

- one bundle-level workflow event
- one per-case tool event

Each event carries:

- `validation_id`
- `case_id`
- `suite`
- `variant`
- `checks_ok`
- `verdict_matches_expectation`
- repo identity
- agent identity
- original semantic label in `validation_signal`

The mapping to `workflow.*` and `tool.*` is deliberate. EvoMap live activity ingest already subscribes to those canonical event families, so this route lands both in telemetry and in activity atoms without patching the runtime.

### Layer 2: Experiment Registry

`register_bundle_experiment(...)` writes a file-backed registry record:

- candidate id: `skill_suite_validation::<validation_id>`
- run stage: default `offline_replay`
- run outcome: `passed` when all cases matched expectation, else `failed`

Run evidence includes:

- `validation_id`
- `case_count`
- `cases_matching_expectation`
- `cases_with_missing_paths`
- `git_head`

### Layer 3: Review Plane

`chatgptrest/evomap/knowledge/skill_suite_review_plane.py` imports the bundle as staged knowledge:

- one bundle document + episode + atom
- one case document + episode + atom per validation case
- one suite entity per suite name
- capture documents for `tool_versions.json.captures`
- evidence rows for bundle files and case inputs/artifacts
- edges linking:
  - bundle -> suite (`COVERS_SUITE`)
  - case -> bundle (`PART_OF_VALIDATION_BUNDLE`)
  - case -> suite (`VALIDATES_SUITE`)
  - capture -> bundle (`CAPTURED_IN_VALIDATION_BUNDLE`)

Promotion status is deliberately `staged`, not `active`.

## Test Coverage

Executed:

```bash
./.venv/bin/pytest -q \
  tests/test_skill_suite_review_plane.py \
  tests/test_ingest_skill_suite_validation_to_evomap.py \
  tests/test_build_skill_suite_validation_bundle.py \
  tests/test_validate_skill_suite_validation_bundle.py
```

Result: `6 passed`

What is covered:

- review-plane import materializes bundle, case, capture, entity, edge, and evidence rows
- repeated import is idempotent at the row-count level
- ingest path writes telemetry + registry + review-plane artifacts together
- live runtime receives supported telemetry event families and turns them into EvoMap activity atoms

## Real Bundle Ingest

Command executed:

```bash
./.venv/bin/python ops/ingest_skill_suite_validation_to_evomap.py \
  --bundle-dir artifacts/skill_suite_validation_bundles/20260315T091900Z_skill_suite_validation_matrix_v1 \
  --owner codex \
  --stage offline_replay \
  --agent-name codex
```

Output directory:

- `artifacts/monitor/skill_suite_evomap_ingest/20260315T015437Z_skill_suite_validation_matrix_v1`

Key outputs:

- [summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/skill_suite_evomap_ingest/20260315T015437Z_skill_suite_validation_matrix_v1/summary.json)
- [registry_result.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/skill_suite_evomap_ingest/20260315T015437Z_skill_suite_validation_matrix_v1/registry_result.json)
- [telemetry_result.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/skill_suite_evomap_ingest/20260315T015437Z_skill_suite_validation_matrix_v1/telemetry_result.json)
- [review_plane_import.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/skill_suite_evomap_ingest/20260315T015437Z_skill_suite_validation_matrix_v1/review_plane_import.json)

Registry file:

- [skill_suite_experiment_registry.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/skill_suite_experiment_registry.json)

## Verification Results

Bundle-level verification from `summary.json`:

- `validation_id = skill_suite_validation_matrix_v1`
- `telemetry.recorded = 7`
- `telemetry.signal_types = [workflow.completed, tool.completed x6]`
- `review_plane_import.case_docs = 6`
- `review_plane_import.suite_entities = 3`
- `review_plane_import.evidence_rows = 210`
- registry run outcome = `passed`

Direct SQLite checks against `data/evomap_knowledge.db`:

- bundle document count for `skill-suite://bundle/skill_suite_validation_matrix_v1` = `1`
- case document count for `skill-suite://case/skill_suite_validation_matrix_v1/*` = `6`
- review-plane bundle atom count for `skill suite validation bundle skill_suite_validation_matrix_v1` = `1`
- live activity atom count for `activity: workflow.completed` with this validation id in applicability = `1`
- live activity atom count for `activity: tool.completed` with this validation id in applicability = `6`

## Notes

- `skill_suite_review_plane` deliberately keeps imported atoms in `staged` promotion status. This is a knowledge intake path, not an automatic promotion path.
- The ingest script uses the canonical EvoMap runtime DB path unless `--db` overrides it. In this run it wrote to `data/evomap_knowledge.db`.
- `FeishuApiClient unavailable` appeared during runtime bootstrap. This did not block telemetry, registry, or review-plane ingest.

## Outcome

The skill-suite audit bundle is now connected to EvoMap as a first-class artifact:

- observable as live activity signals
- replayable as an experiment run
- queryable as staged durable knowledge

This turns the existing bundle from “versioned evidence on disk” into a tracked evaluation object inside the current OpenMind/EvoMap runtime.
