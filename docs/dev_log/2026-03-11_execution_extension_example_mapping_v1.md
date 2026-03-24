# 2026-03-11 Execution Extension Example Mapping v1

## Goal

Turn the `#115` contract line into example-driven mappings that match real
runtime shapes already present in ChatgptREST.

This document does not add new live event types. It shows how existing shapes
should preserve execution-layer extensions while still mapping back into:

- `TraceEvent`
- `/v2/telemetry/ingest`
- `EventBus`

## Confirmed runtime boundary

Mainline commit `12be414` preserves these execution-layer extensions in the
normalized identity view:

- `lane_id`
- `role_id`
- `adapter_id`
- `profile_id`
- `executor_kind`

They are still extensions, not root canonical identity fields.

## Artifact bundle

The example mappings in this document are now backed by a minimal fixture
bundle:

- [2026-03-11_execution_extension_fixture_bundle_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_extension_fixture_bundle_v1.md)
- `docs/dev_log/artifacts/execution_extension_fixture_bundle_20260311/`
- [2026-03-11_runner_adapter_projection_fixture_bundle_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_runner_adapter_projection_fixture_bundle_v1.md)
- [2026-03-11_live_bus_archive_envelope_mapping_examples_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_live_bus_archive_envelope_mapping_examples_v1.md)
- [2026-03-11_execution_emitter_capability_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_emitter_capability_matrix_v1.md)
- [2026-03-11_execution_emitter_degraded_example_bundle_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_emitter_degraded_example_bundle_v1.md)
- `docs/dev_log/artifacts/execution_emitter_capability_bundle_20260311/`
- [2026-03-11_execution_emitter_capability_review_views_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_emitter_capability_review_views_v1.md)
- [2026-03-11_execution_sparse_lineage_pairs_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_sparse_lineage_pairs_v1.md)
- [2026-03-11_execution_commit_sparse_archive_examples_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_execution_commit_sparse_archive_examples_v1.md)
- `docs/dev_log/artifacts/execution_emitter_review_bundle_20260311/`
- `docs/dev_log/artifacts/execution_commit_sparse_bundle_20260311/`
- `docs/dev_log/artifacts/execution_projection_fixture_bundle_20260311/`

## Example 1: controller lane wrapper

### Source payload shape

```json
{
  "source": "controller_lane_wrapper",
  "session_id": "sess-main",
  "run_id": "run-main-1",
  "task_ref": "issue-115",
  "agent_name": "main",
  "agent_source": "controller_lane_wrapper",
  "provider": "openai",
  "model": "gpt-5",
  "lane_id": "main",
  "role_id": "devops",
  "executor_kind": "codex.controller"
}
```

### Normalized identity expectations

| Field | Expectation |
|---|---|
| `source` | `controller_lane_wrapper` |
| `session_id` | preserved |
| `run_id` | preserved |
| `task_ref` | preserved |
| `agent_name/agent_source` | preserved |
| `provider/model` | preserved |
| `lane_id` | preserved as extension |
| `role_id` | preserved as extension |
| `executor_kind` | preserved as extension |

## Example 2: OpenClaw plugin emitter

### Source payload shape

```json
{
  "source": "openclaw.execution",
  "session_id": "sess-openclaw",
  "run_id": "run-openclaw-1",
  "task_ref": "openclaw:main:abc123",
  "agent_source": "openclaw.plugin",
  "provider": "openai",
  "model": "gpt-5",
  "role_id": "research",
  "executor_kind": "openclaw.agent"
}
```

### Normalized identity expectations

| Field | Expectation |
|---|---|
| `source` | `openclaw.execution` |
| `session_id` | preserved |
| `run_id` | preserved |
| `task_ref` | preserved |
| `agent_source` | preserved |
| `provider/model` | preserved |
| `role_id` | preserved as extension |
| `executor_kind` | preserved as extension |

## Example 3: `cc_native` EventBus payload

### Source payload shape

```json
{
  "event_type": "dispatch.task.started",
  "source": "cc_native",
  "session_id": "sess-cc-native",
  "run_id": "run-cc-native-1",
  "task_ref": "cc-review-001",
  "repo_name": "ChatgptREST",
  "repo_path": "/vol1/1000/projects/ChatgptREST"
}
```

### Normalized identity expectations

| Field | Expectation |
|---|---|
| `source` | `cc_native` |
| `session_id` | preserved |
| `run_id` | preserved |
| `task_ref` | preserved |
| `repo_name/repo_path` | preserved |
| execution extensions | absent is valid |

## Example 4: `cc_executor` EventBus payload

### Source payload shape

```json
{
  "event_type": "task.completed",
  "source": "cc_executor",
  "session_id": "sess-cc-exec",
  "run_id": "run-cc-exec-1",
  "task_ref": "cc-review-002",
  "repo_name": "ChatgptREST",
  "repo_path": "/vol1/1000/projects/ChatgptREST",
  "adapter_id": "codex_batch",
  "profile_id": "ambient_clean_fallback"
}
```

### Normalized identity expectations

| Field | Expectation |
|---|---|
| `source` | `cc_executor` |
| `session_id` | preserved |
| `run_id` | preserved |
| `task_ref` | preserved |
| `repo_name/repo_path` | preserved |
| `adapter_id` | preserved as extension |
| `profile_id` | preserved as extension |

## Example 5: `runner_adapter.v1` to telemetry ingest

### Adapter result shape

```json
{
  "schema_version": "runner_adapter.v1",
  "adapter_id": "codex_batch",
  "lane_id": "codex.batch.clean",
  "operation": "result",
  "identity": {
    "trace_id": "tr_01",
    "session_id": "sess_01",
    "run_id": "run_01",
    "task_ref": "issue-115:runner-contract",
    "source": "openclaw.execution"
  },
  "data": {
    "effective_profile": "ambient_clean_fallback",
    "executor_kind": "codex.batch",
    "fallback_used": true
  }
}
```

### Telemetry ingest projection

```json
{
  "event_type": "execution.run.completed",
  "source": "openclaw.execution",
  "trace_id": "tr_01",
  "session_id": "sess_01",
  "run_id": "run_01",
  "task_ref": "issue-115:runner-contract",
  "lane_id": "codex.batch.clean",
  "adapter_id": "codex_batch",
  "profile_id": "ambient_clean_fallback",
  "executor_kind": "codex.batch"
}
```

### Mapping notes

- `lane_id / adapter_id / profile_id / executor_kind` should remain extensions.
- `effective_profile` may map to `profile_id` when the runtime only keeps one
  normalized profile field.
- `fallback_used` remains event payload metadata, not identity.
- This mapping does not require adding a new live canonical vocabulary.

## Acceptance criteria

This example set is acceptable for `#115` if:

1. each real emitter family can be described without inventing new root fields
2. preserved execution extensions stay visible after normalization
3. runner adapter outputs can be projected into telemetry ingest using the same
   extension language
4. sparse archive commit envelopes remain representable without inventing
   runtime execution identity
