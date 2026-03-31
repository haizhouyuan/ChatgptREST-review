# 2026-03-11 Runner Adapter Contract v1

**Status**: Draft v1  
**Date**: 2026-03-11  
**Scope**: `#115` execution-layer / capability-adapter line  
**Depends on**:
- `chatgptrest/telemetry_contract.py`
- `POST /v2/telemetry/ingest`
- `EventBus`

## 1. Goal

Define the thinnest machine-readable contract that lets execution-side adapters
normalize unstable CLI / lane behavior into a stable shape the main runtime can
consume.

This contract is intentionally **not** a new canonical event system.

It exists to:

- hide CLI-specific stderr / HOME / auth / MCP drift from callers
- give OpenClaw execution-layer a stable adapter surface
- let the main runtime map execution outcomes back into existing telemetry
  canonical

It does **not** exist to:

- replace `TraceEvent`
- replace `/v2/telemetry/ingest`
- introduce a parallel live event bus
- define a full orchestrator platform

## 2. Authority Boundary

### Adapter owns

- lane-specific invocation details
- CLI-specific environment setup
- transport-specific retries / fallback handling
- artifact materialization
- normalized execution status projection

### Main runtime owns

- canonical telemetry identity
- governed ingest into EventBus / EvoMap
- task lifecycle semantics
- downstream policy / recommendation / promotion

## 3. Operations

The minimum adapter surface is:

1. `submit`
2. `status`
3. `result`
4. `cancel`
5. `artifacts`

These operations can be implemented as:

- Python functions
- shell wrappers with JSON stdout
- HTTP endpoints
- OpenClaw adapter calls

The transport is out of scope. The payload shape is the contract.

## 4. Common Envelope

Every adapter response should use this top-level envelope:

```json
{
  "schema_version": "runner_adapter.v1",
  "adapter_id": "codex_batch",
  "lane_id": "codex.batch.clean",
  "operation": "submit",
  "ok": true,
  "time": {
    "started_at": "2026-03-11T03:30:00Z",
    "updated_at": "2026-03-11T03:30:02Z",
    "finished_at": ""
  },
  "identity": {
    "run_id": "run_01",
    "parent_run_id": "",
    "trace_id": "tr_01",
    "session_id": "sess_01",
    "task_ref": "issue-115:runner-contract",
    "source": "openclaw.execution"
  },
  "data": {},
  "diagnostics": [],
  "raw_refs": []
}
```

Rules:

- `schema_version` is required.
- `adapter_id` is required and stable across implementations.
- `lane_id` is required and identifies the configured execution lane.
- `identity` must conform to the execution run identity contract.
- `diagnostics` must be structured; callers must not parse stderr text to
  understand semantic outcome.
- `raw_refs` may point to stdout / stderr / raw JSON logs, but those are audit
  evidence, not semantic contract.

## 5. Submit

### Request

```json
{
  "schema_version": "runner_adapter.v1",
  "identity": {
    "run_id": "run_01",
    "parent_run_id": "",
    "trace_id": "tr_01",
    "session_id": "sess_01",
    "task_ref": "issue-115:runner-contract",
    "source": "openclaw.execution"
  },
  "task": {
    "prompt": "Return exact JSON ...",
    "workdir": "/vol1/maint"
  },
  "profile": {
    "requested_profile": "clean_batch",
    "approval_mode_requested": "never"
  },
  "hints": {
    "interactive": false,
    "allow_fallback": true
  }
}
```

### Response

```json
{
  "schema_version": "runner_adapter.v1",
  "adapter_id": "codex_batch",
  "lane_id": "codex.batch.clean",
  "operation": "submit",
  "ok": true,
  "identity": {
    "run_id": "run_01",
    "trace_id": "tr_01",
    "session_id": "sess_01",
    "task_ref": "issue-115:runner-contract",
    "source": "openclaw.execution"
  },
  "data": {
    "accepted": true,
    "state": "running",
    "ticket_id": "runner-20260311T033000Z",
    "effective_profile": "ambient_clean_fallback",
    "executor_kind": "codex.batch",
    "fallback_used": true,
    "approval_mode_effective": "never"
  },
  "diagnostics": [
    {
      "code": "auth_fallback_applied",
      "severity": "info",
      "message": "isolated auth-only failed; live-home clean fallback applied"
    }
  ]
}
```

### Required submit fields

Inside `data`:

- `accepted`
- `state`
- `ticket_id`
- `effective_profile`
- `executor_kind`
- `fallback_used`
- `approval_mode_effective`

Notes:

- `ticket_id` is adapter-local lookup handle for `status/result/cancel/artifacts`.
- `effective_profile` must reflect what actually ran, not just what was
  requested.
- `executor_kind` should be stable across retries for the same runtime family,
  even when profile fallback changes.
- `fallback_used` is semantic and required because the execution layer must not
  infer fallback from logs.

## 6. Status

### Response shape

```json
{
  "schema_version": "runner_adapter.v1",
  "adapter_id": "codex_batch",
  "lane_id": "codex.batch.clean",
  "operation": "status",
  "ok": true,
  "identity": {
    "run_id": "run_01",
    "trace_id": "tr_01",
    "session_id": "sess_01",
    "task_ref": "issue-115:runner-contract",
    "source": "openclaw.execution"
  },
  "data": {
    "ticket_id": "runner-20260311T033000Z",
    "state": "running",
    "progress": {
      "phase": "exec",
      "message": "awaiting tool completion"
    },
    "executor_kind": "codex.batch",
    "cost": {
      "tokens_used": 14524,
      "currency": "",
      "estimated_cost": ""
    }
  },
  "diagnostics": []
}
```

### Allowed `state` values

- `queued`
- `running`
- `succeeded`
- `failed`
- `canceled`
- `blocked`

No additional live states should be invented here. If an adapter has richer
internals, project them into:

- `state`
- `progress.phase`
- structured `diagnostics`

## 7. Result

### Response shape

```json
{
  "schema_version": "runner_adapter.v1",
  "adapter_id": "codex_batch",
  "lane_id": "codex.batch.clean",
  "operation": "result",
  "ok": true,
  "identity": {
    "run_id": "run_01",
    "trace_id": "tr_01",
    "session_id": "sess_01",
    "task_ref": "issue-115:runner-contract",
    "source": "openclaw.execution"
  },
  "data": {
    "ticket_id": "runner-20260311T033000Z",
    "state": "succeeded",
    "result_type": "json",
    "output_ref": "/abs/path/result.json",
    "effective_profile": "ambient_clean_fallback",
    "executor_kind": "codex.batch",
    "fallback_used": true,
    "approval_mode_effective": "never",
    "cost": {
      "tokens_used": 14524,
      "currency": "",
      "estimated_cost": ""
    },
    "artifacts_available": true
  },
  "diagnostics": []
}
```

### Required result fields

- `ticket_id`
- `state`
- `result_type`
- `output_ref`
- `effective_profile`
- `executor_kind`
- `fallback_used`
- `approval_mode_effective`
- `cost`
- `artifacts_available`

## 8. Cancel

### Response shape

```json
{
  "schema_version": "runner_adapter.v1",
  "adapter_id": "codex_batch",
  "lane_id": "codex.batch.clean",
  "operation": "cancel",
  "ok": true,
  "identity": {
    "run_id": "run_01",
    "trace_id": "tr_01",
    "session_id": "sess_01",
    "task_ref": "issue-115:runner-contract",
    "source": "openclaw.execution"
  },
  "data": {
    "ticket_id": "runner-20260311T033000Z",
    "cancel_requested": true,
    "state": "canceled"
  },
  "diagnostics": []
}
```

## 9. Artifacts

### Response shape

```json
{
  "schema_version": "runner_adapter.v1",
  "adapter_id": "codex_batch",
  "lane_id": "codex.batch.clean",
  "operation": "artifacts",
  "ok": true,
  "identity": {
    "run_id": "run_01",
    "trace_id": "tr_01",
    "session_id": "sess_01",
    "task_ref": "issue-115:runner-contract",
    "source": "openclaw.execution"
  },
  "data": {
    "ticket_id": "runner-20260311T033000Z",
    "artifacts": [
      {
        "kind": "stdout",
        "path": "/abs/path/stdout.log",
        "mime_type": "text/plain"
      },
      {
        "kind": "stderr",
        "path": "/abs/path/stderr.log",
        "mime_type": "text/plain"
      },
      {
        "kind": "result",
        "path": "/abs/path/result.json",
        "mime_type": "application/json"
      }
    ]
  },
  "diagnostics": []
}
```

Artifacts are audit outputs. Their presence does not replace required semantic
fields in `submit/status/result`.

## 10. Diagnostics Contract

Each diagnostic entry should use:

```json
{
  "code": "auth_fallback_applied",
  "severity": "info",
  "message": "human-readable summary",
  "source": "codex_batch",
  "raw_ref": "/abs/path/stderr.log"
}
```

Required fields:

- `code`
- `severity`
- `message`

Allowed severities:

- `info`
- `warning`
- `error`

## 11. Mapping to Main Runtime Canonical

This adapter contract must map into existing canonical telemetry rather than
replace it.

| Adapter field | Canonical target |
|---|---|
| `identity.trace_id` | `TraceEvent.trace_id` |
| `identity.session_id` | `TraceEvent.session_id` |
| `identity.run_id` | telemetry payload `run_id` |
| `identity.parent_run_id` | telemetry payload `parent_run_id` |
| `identity.task_ref` | telemetry payload `task_ref` |
| `identity.source` | telemetry payload `source` |
| `data.ticket_id` | telemetry payload extension `adapter_ticket_id` |
| `lane_id` | telemetry payload extension `lane_id` |
| `adapter_id` | telemetry payload extension `adapter_id` |
| `data.effective_profile` | telemetry payload extension `effective_profile` |
| `data.executor_kind` | telemetry payload extension `executor_kind` |
| `data.fallback_used` | telemetry payload extension `fallback_used` |
| `data.approval_mode_effective` | telemetry payload extension `approval_mode_effective` |
| `data.cost` | telemetry payload extension `cost` |

## 12. Non-Goals

- No stderr parsing in callers.
- No adapter-specific states beyond the normalized state set.
- No requirement that adapters expose identical implementation internals.
- No new live event bus.

## 13. Acceptance Criteria

This draft is acceptable for `#115` if:

1. `codex_batch`, `gemini_batch`, and future delegated lanes can all project
   into this shape.
2. Main runtime can ingest adapter outcomes without inventing a second
   canonical plane.
3. OpenClaw execution-layer can call adapters without reading CLI-private logs.
