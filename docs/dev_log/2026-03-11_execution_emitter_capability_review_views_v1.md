# 2026-03-11 Execution Emitter Capability Review Views v1

## Goal

Provide review-oriented views over the capability matrix so mainline can inspect
the current execution emitter surface without scanning the raw matrix row by
row.

This stays in contract supply. It does not change runtime code.

## Artifact files

Artifact root:

- `docs/dev_log/artifacts/execution_emitter_review_bundle_20260311/`

Included grouped views:

1. `capability_by_field_v1.json`
2. `capability_by_emitter_v1.json`

## Why this exists

The raw capability matrix is precise, but review questions usually come in two
shapes:

- “for a given field, which emitters can really provide it?”
- “for a given emitter, what is truly stable vs sparse?”

These grouped views answer those questions directly.

## Review highlights

### Strongest lineage emitter

`controller_lane_wrapper` remains the strongest live execution emitter for:

- `task_ref`
- `trace_id`
- `session_id`
- `run_id`
- `lane_id`
- `role_id`
- `executor_kind`

### Strongest posthoc emitter

`archive envelope` is still the richest posthoc shape for:

- `adapter_id`
- `profile_id`
- optional execution extensions beyond basic lineage

### Sparse emitters

`cc_native` and `cc_executor` are still correctly classified as sparse at raw
emit time. They should not be treated as full-lineage emitters just because the
normalized identity layer can later enrich or preserve additional fields.

## Intended use

- mainline issue review
- future regression consumption if grouped views become useful in tests
- quick human audit of the execution emitter surface
