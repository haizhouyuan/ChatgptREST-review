# 2026-03-11 Execution Emitter Degraded Example Bundle v1

## Goal

Provide realistic sparse examples for execution-lineage payloads, so mainline
review does not overfit to ideal full-field fixtures.

The degraded examples in this bundle are intentionally incomplete.

## Included degraded shapes

1. `task_ref + trace_id`
2. `trace_id` only
3. `agent/source` only
4. `provider/model` without lane/role

These examples are not tied to one runtime implementation. They are contract
artifacts that express realistic low-information cases the normalizer may still
encounter.

## Why this matters

Without degraded examples, the contract line can accidentally assume:

- every execution payload has a full lineage tuple
- every execution emitter knows lane/role/profile identity
- provider/model implies a richer execution identity than the emitter really has

This bundle makes the opposite explicit: sparse cases are normal and must remain
representable without inventing fields.

## Artifact linkage

The degraded examples are backed by:

- [2026-03-11_execution_emitter_capability_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_emitter_capability_matrix_v1.md)
- `docs/dev_log/artifacts/execution_emitter_capability_bundle_20260311/`

## Review intent

This bundle is meant to support:

- contract review on `#115`
- future fixture-driven regressions
- downstream decisions about which fields are truly stable vs merely optional

It is not a request to widen runtime schema.
