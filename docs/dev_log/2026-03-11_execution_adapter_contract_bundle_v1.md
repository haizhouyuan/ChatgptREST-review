# 2026-03-11 Execution Adapter Contract Bundle v1

## Context

This work belongs to issue `#115`, which is now explicitly limited to:

- multi-agent execution layer
- capability adapters
- lane control contracts

It is not the lane for:

- planning import
- review-plane ingest
- KB / memory / role-pack expansion
- a second canonical event system

## Delivered

Three draft contracts were added under `docs/contracts/`:

1. `2026-03-11_runner_adapter_contract_v1.md`
2. `2026-03-11_execution_run_identity_contract_v1.md`
3. `2026-03-11_openclaw_lane_adapter_registry_seam_v1.md`

## Why this shape

The mainline Codex feedback on `#115` narrowed the useful next output to three
machine-readable contracts:

1. runner adapter contract
2. execution run identity contract
3. OpenClaw lane adapter registry seam

The key constraint was preserved throughout:

- live canonical remains `TraceEvent + /v2/telemetry/ingest + EventBus`
- execution-side envelopes may exist for normalization, but must map back into
  existing canonical

## Follow-up alignment

After the first contract bundle landed, mainline added `12be414`
`feat: preserve execution telemetry extensions`.

That update does not adopt execution fields into root canonical, but it does
preserve these extensions in the normalized identity view:

- `lane_id`
- `role_id`
- `adapter_id`
- `profile_id`
- `executor_kind`

This contract line now assumes those fields can survive runtime normalization
as extensions, and the next step is example-driven mapping rather than root
schema expansion.

## What was intentionally not changed

No runtime code was changed in this bundle.

Reasons:

- this round was for contract convergence, not runtime cutover
- the repo already contains unrelated in-flight changes in other areas
- mainline explicitly asked for stable contract drafts before platform work

## Expected next step

After review on `#115`, the next implementation slice should start from:

1. projecting current runner outputs into `runner_adapter.v1`
2. aligning execution identity with `telemetry_contract.py`
3. choosing the thinnest OpenClaw registry seam that can emit normalized run
   records via `/v2/telemetry/ingest`
