# 2026-03-11 Execution Emitter Capability Matrix v1

## Goal

Document which execution-lineage and execution-extension fields each current
emitter can *stably* provide today, without guessing from idealized examples.

This matrix is contract supply only. It does not change runtime behavior.

## Scope

Emitters covered:

- `controller_lane_wrapper`
- `openclaw plugin`
- `cc_native`
- `cc_executor`
- `archive envelope`

Fields covered:

- root lineage: `task_ref`, `trace_id`, `session_id`, `run_id`
- execution extensions: `lane_id`, `role_id`, `adapter_id`, `profile_id`, `executor_kind`
- optional provider/model: `provider`, `model`

Status vocabulary:

- `stable`
- `optional`
- `not_available`

Assessment basis:

- only current emitter-authored payload/transport behavior
- no future registry/adoption assumptions
- no promotion of execution extensions into root canonical

## Notes on interpretation

### `stable`

The emitter or its fixed transport path provides the field consistently enough
to treat it as part of the emitter's current contract surface.

### `optional`

The field is emitted only when a caller/configuration/path supplies it, or only
for some event families.

### `not_available`

The current emitter path does not stably provide the field today. A downstream
normalizer might infer or preserve something richer later, but that is outside
this matrix.

## Artifact files

Artifact root:

- `docs/dev_log/artifacts/execution_emitter_capability_bundle_20260311/`

Included artifacts:

1. `capability_matrix_v1.json`
2. `capability_matrix_v1.tsv`
3. `degraded_task_ref_trace_only_v1.json`
4. `degraded_trace_only_v1.json`
5. `degraded_agent_source_only_v1.json`
6. `degraded_provider_model_without_lane_role_v1.json`
7. `degraded_examples_expectations_v1.json`

## Summary

High-signal takeaways:

- `controller_lane_wrapper` is the strongest live execution emitter for lineage plus
  lane/role/executor metadata.
- `openclaw plugin` is strong on `task_ref/run_id/role_id/executor_kind`, but `trace_id`
  is not an emitter-authored stable field in its current transport shape.
- `cc_native` and `cc_executor` are materially weaker at raw emitter time than some
  normalized examples might suggest; they should be treated as sparse emitters.
- `archive envelope` is the richest posthoc shape and the only emitter in this set
  that currently stably carries both `adapter_id` and `profile_id`.

## Why this bundle exists

The earlier `#115` work established:

- extension preservation
- example-driven mappings
- projection/mapping fixture bundles

The next missing layer is capability truth: which emitters can really supply
which fields without downstream guesswork. This matrix and degraded bundle are
intended to close that gap.
