# 2026-03-11 OpenClaw Lane Adapter Registry Seam v1

**Status**: Draft v1  
**Date**: 2026-03-11  
**Scope**: `#115` execution-layer / capability-adapter line  
**Depends on**:
- `2026-03-11_runner_adapter_contract_v1.md`
- `2026-03-11_execution_run_identity_contract_v1.md`
- `POST /v2/telemetry/ingest`

## 1. Goal

Define the thinnest seam between:

- OpenClaw execution-layer
- execution adapters such as `codex_batch` / `gemini_batch`
- main runtime telemetry ingest

This seam should answer only two questions:

1. Which object decides which lane to use?
2. Which object sends normalized run records back to the main runtime?

It is explicitly **not** a full orchestrator/platform design.

## 2. Minimal Components

The minimum seam has four responsibilities:

1. `LaneRegistry`
2. `LaneAdapter`
3. `LaneSelector`
4. `RunRecordSink`

## 3. Responsibility Split

### 3.1 `LaneRegistry`

Purpose:

- hold the set of available lanes
- map `lane_id -> adapter binding`
- expose capabilities / defaults to the execution-layer

It does not:

- plan the whole task
- own business policy
- own telemetry canonical

### 3.2 `LaneSelector`

Purpose:

- choose one lane given task hints and policy hints

Inputs may include:

- requested lane
- interactivity requirement
- provider preference
- cost sensitivity
- allowed capabilities
- policy hints from main runtime

It returns a `LaneBinding`.

### 3.3 `LaneAdapter`

Purpose:

- implement the runner adapter contract for one lane/backend

It owns:

- submit / status / result / cancel / artifacts

It does not:

- write directly into canonical telemetry tables
- decide global policy

### 3.4 `RunRecordSink`

Purpose:

- take normalized execution-layer records and forward them into main runtime

Initial implementation target:

- `POST /v2/telemetry/ingest`

It does not:

- invent a new event system
- replace EventBus

## 4. Proposed Interfaces

### `LaneBinding`

```json
{
  "lane_id": "codex.batch.clean",
  "adapter_id": "codex_batch",
  "executor_kind": "codex.batch",
  "kind": "batch",
  "capabilities": [
    "prompt_exec",
    "json_result",
    "artifact_logs"
  ],
  "default_profile": "clean_batch",
  "telemetry_source": "openclaw.execution"
}
```

Required fields:

- `lane_id`
- `adapter_id`
- `executor_kind`
- `kind`
- `capabilities`
- `default_profile`
- `telemetry_source`

### `LaneRegistry`

Conceptual methods:

```text
register(binding)
get(lane_id) -> LaneBinding
list() -> LaneBinding[]
```

### `LaneSelector`

Conceptual method:

```text
select(task_context, policy_hints) -> LaneBinding
```

Where:

- `task_context` is execution-side input
- `policy_hints` are read-only recommendations from main runtime / EvoMap

### `LaneAdapter`

Conceptual methods:

```text
submit(request) -> submit_response
status(ticket) -> status_response
result(ticket) -> result_response
cancel(ticket) -> cancel_response
artifacts(ticket) -> artifacts_response
```

All responses must conform to the runner adapter contract.

### `RunRecordSink`

Conceptual method:

```text
emit(event) -> ack
```

Initial `event` transport is expected to be telemetry-ingest compatible rather
than a new bus shape.

## 5. Selection Seam

The selection seam should be minimal:

1. OpenClaw execution-layer gathers task context.
2. `LaneSelector` chooses a `LaneBinding`.
3. OpenClaw invokes the bound adapter.
4. OpenClaw emits normalized lifecycle records through `RunRecordSink`.

No additional registry graph / scheduler graph / approval graph is required in
this draft.

## 6. Run Record Seam

The minimal normalized lifecycle should include:

- `execution.lane.selected`
- `execution.run.submitted`
- `execution.run.updated`
- `execution.run.completed`
- `execution.run.failed`
- `execution.run.canceled`

These are execution-layer event types, not a replacement for `TraceEvent`.

They must be projected into existing canonical telemetry through
`/v2/telemetry/ingest`.

## 7. Example Flow

### Step 1: selection

```json
{
  "event_type": "execution.lane.selected",
  "schema_version": "execution_registry.v1",
  "source": "openclaw.execution",
  "trace_id": "tr_01",
  "session_id": "sess_01",
  "run_id": "run_01",
  "task_ref": "issue-115:runner-contract",
  "extensions": {
    "lane_id": "codex.batch.clean",
    "adapter_id": "codex_batch",
    "role_id": "execution.adapter",
    "profile_id": "clean_batch",
    "executor_kind": "codex.batch"
  }
}
```

### Step 2: submit

OpenClaw calls the adapter `submit` operation and receives a normalized submit
response.

### Step 3: sink

OpenClaw emits:

```json
{
  "event_type": "execution.run.submitted",
  "schema_version": "execution_registry.v1",
  "source": "openclaw.execution",
  "trace_id": "tr_01",
  "session_id": "sess_01",
  "run_id": "run_01",
  "task_ref": "issue-115:runner-contract",
  "extensions": {
    "lane_id": "codex.batch.clean",
    "adapter_id": "codex_batch",
    "executor_kind": "codex.batch",
    "adapter_ticket_id": "runner-20260311T033000Z",
    "effective_profile": "ambient_clean_fallback",
    "fallback_used": true
  }
}
```

### Step 4: completion

OpenClaw polls `status/result`, then emits a completion event through the same
sink.

## 8. Non-Goals

- No full registry database.
- No generalized orchestrator graph.
- No approval workflow redesign.
- No role-pack / memory / KB / planning review-plane design in this document.

## 9. Acceptance Criteria

This draft is acceptable for `#115` if:

1. OpenClaw can choose and invoke a lane without reading lane-specific logs.
2. Main runtime receives normalized run records through existing telemetry
   canonical.
3. The seam stays small enough that it can be implemented incrementally, not as
   a new platform rewrite.
