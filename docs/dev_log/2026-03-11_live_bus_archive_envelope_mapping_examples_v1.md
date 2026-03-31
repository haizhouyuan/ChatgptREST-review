# 2026-03-11 Live Bus Archive Envelope Mapping Examples v1

## Goal

Provide one concrete example pair that shows how:

- a live bus execution event
- an archive envelope closeout event

can describe the same execution lineage without inventing a second live
standard.

This is still contract supply only.

## Artifact files

Artifact root:

- `docs/dev_log/artifacts/execution_projection_fixture_bundle_20260311/`

Included mapping artifacts:

1. `live_bus_team_run_completed_v1.json`
2. `archive_envelope_agent_task_closeout_v1.json`
3. `live_archive_mapping_split_v1.json`

## Pair choice

The live-side example uses `controller_lane_wrapper` because it is one of the
runtime shapes already covered by `tests/test_telemetry_contract.py`.

The archive-side example uses `agent.task.closeout` in
`openmind-v3-agent-ops-v1` envelope form because that path is already covered
by `tests/test_activity_ingest.py` and the archive-envelope live smoke.

## Mapping boundary

### Shared correlation anchors

- `trace_id`
- `session_id`
- `run_id`
- `task_ref`
- repo identity
- agent identity

### Shared execution extensions

- `lane_id`
- `role_id`
- `executor_kind`

### Archive-only payload details

- `schema_version`
- `ts`
- `closeout.status`
- `closeout.summary`
- `adapter_id`
- `profile_id`

### Live-only payload details

- `event_id`
- `upstream_event_id`
- `provider`
- `model`

## Why this bundle exists

Mainline asked for `live bus vs archive envelope` mapping examples while
keeping all execution fields as extensions and avoiding runtime adoption.

This bundle makes that comparison concrete with a single pair that can be
reviewed field-by-field.
