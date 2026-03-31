# 2026-03-11 Execution Extension Fixture Bundle v1

## Goal

Provide a minimal contract artifact bundle for `#115` that stays entirely on
the supply side:

- no runtime adoption
- no new live event standard
- no promotion of execution extensions into root canonical

The bundle is example-driven and anchored to real emitter shapes already
covered by `tests/test_telemetry_contract.py`.

## Artifact files

Artifact root:

- `docs/dev_log/artifacts/execution_extension_fixture_bundle_20260311/`

Included fixtures:

1. `controller_lane_wrapper_minimal_v1.json`
2. `openclaw_plugin_minimal_v1.json`
3. `cc_native_eventbus_minimal_v1.json`
4. `cc_executor_eventbus_minimal_v1.json`
5. `normalization_field_split_v1.json`

## Root canonical vs execution extensions

The bundle keeps the same boundary as the main runtime:

### Root canonical

- `event_type`
- `source`
- `trace_id`
- `session_id`
- `event_id`
- `upstream_event_id`
- `run_id`
- `task_ref`
- `provider`
- `model`
- `repo_name`
- `repo_path`
- `agent_name`
- `agent_source`

### Execution extensions

- `lane_id`
- `role_id`
- `adapter_id`
- `profile_id`
- `executor_kind`

## Why this bundle exists

This is the direct next step after:

- `12be414` `feat: preserve execution telemetry extensions`
- `a569e59` `docs: add execution extension mapping follow-up`

The runtime now preserves execution extensions in the normalized identity view,
so the highest-value supply artifact is no longer an abstract schema diagram. It
is a small fixture bundle that makes the emitter-to-normalization mapping
concrete and reviewable.

## Intended use

- contract review on `#115`
- future fixture-driven tests if mainline later chooses to harden mapping
- adapter example reference for `runner_adapter.v1 -> telemetry ingest`

This bundle is not consumed by runtime code in this round.
