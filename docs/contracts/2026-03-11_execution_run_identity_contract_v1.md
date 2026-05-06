# 2026-03-11 Execution Run Identity Contract v1

**Status**: Draft v1  
**Date**: 2026-03-11  
**Scope**: `#115` execution-layer / capability-adapter line  
**Depends on**:
- `chatgptrest/telemetry_contract.py`
- `POST /v2/telemetry/ingest`
- archive envelope ingest

## 1. Goal

Define the minimum execution identity fields required to correlate:

- runner adapter operations
- OpenClaw execution-layer run records
- existing live telemetry canonical
- posthoc archive envelopes such as `agent.task.closeout`

This contract does not redefine telemetry canonical. It clarifies how execution
side identities map into it.

## 2. Existing Canonical Baseline

`chatgptrest/telemetry_contract.py` already normalizes these root identity
fields:

- `event_type`
- `schema_version`
- `source`
- `trace_id`
- `session_id`
- `event_id`
- `upstream_event_id`
- `run_id`
- `parent_run_id`
- `job_id`
- `issue_id`
- `task_ref`
- `provider`
- `model`
- `repo_name`
- `repo_path`
- `repo_branch`
- `repo_head`
- `repo_upstream`
- `agent_name`
- `agent_source`
- `commit_sha`

This draft keeps those root fields authoritative.

## 3. Identity Layers

### 3.1 Core canonical identity

These fields should remain root-level canonical:

- `trace_id`
- `session_id`
- `run_id`
- `parent_run_id`
- `task_ref`
- `source`
- `provider`
- `model`
- `repo_name`
- `repo_path`
- `repo_branch`
- `repo_head`
- `agent_name`
- `agent_source`
- `commit_sha`

### 3.2 Execution-layer extensions

These fields are required by `#115`, but should initially live as payload
extensions until the main runtime explicitly promotes them:

- `lane_id`
- `role_id`
- `adapter_id`
- `profile_id`
- `executor_kind`

This avoids inventing a second root canonical without mainline agreement.

## 4. Field Definitions

| Field | Required | Meaning |
|---|---|---|
| `trace_id` | yes | Correlation id for one logical execution trace across telemetry and archive events |
| `session_id` | yes | Conversation / execution session boundary |
| `run_id` | yes | Unique id for one execution attempt |
| `parent_run_id` | no | Previous execution attempt or supervising run |
| `task_ref` | yes | Stable human/business task reference |
| `source` | yes | Producer of the event, such as `openclaw.execution` |
| `provider` | no | Model/provider family actually used |
| `model` | no | Concrete model identifier actually used |
| `repo_name` | no | Logical repo name |
| `repo_path` | no | Absolute repo path |
| `repo_branch` | no | Branch seen by execution layer |
| `repo_head` | no | Commit / head seen by execution layer |
| `agent_name` | no | Agent identity, such as `education codex` |
| `agent_source` | no | Agent runtime source, such as `codex-cli` or `openclaw` |
| `commit_sha` | no | Commit associated with the action, if any |
| `lane_id` | extension | Selected execution lane |
| `role_id` | extension | Selected execution role/profile pack |
| `adapter_id` | extension | Adapter implementation id |
| `profile_id` | extension | Execution profile/effective profile id |
| `executor_kind` | extension | Stable runtime/executor category such as `codex.batch` or `openclaw.agent` |

## 5. Correlation Rules

### Rule 1: `trace_id` is the top-level join key

All telemetry emitted for one logical execution should share the same
`trace_id`, including:

- lane selection
- adapter submit / status / result
- runtime policy hints
- closeout / archive envelope if tied to the same task

### Rule 2: `run_id` identifies one execution attempt

Every new execution attempt gets a fresh `run_id`.

Examples:

- first try: `run_001`
- retry after auth repair: `run_002`, `parent_run_id=run_001`
- delegated child lane: `run_003`, `parent_run_id=run_001`

### Rule 3: `task_ref` is stable across retries

Retries, followups, and lane changes should not change `task_ref`.

`task_ref` is the business/task lineage anchor, while `run_id` is the execution
attempt anchor.

### Rule 4: `session_id` scopes execution to a conversation or control-plane thread

`session_id` must remain stable for all execution attempts that belong to the
same controlling conversation or orchestration session.

## 6. Required Payload Shape

```json
{
  "event_type": "execution.run.result",
  "schema_version": "execution_identity.v1",
  "source": "openclaw.execution",
  "trace_id": "tr_01",
  "session_id": "sess_01",
  "run_id": "run_02",
  "parent_run_id": "run_01",
  "task_ref": "issue-115:runner-contract",
  "provider": "openai-codex",
  "model": "gpt-5-codex",
  "repo_name": "maint",
  "repo_path": "/vol1/maint",
  "repo_branch": "main",
  "repo_head": "9a230ad5b3359852e072df54ae905adf6f852a19",
  "agent_name": "education codex",
  "agent_source": "codex-cli",
  "commit_sha": "",
  "extensions": {
    "lane_id": "codex.batch.clean",
    "role_id": "execution.adapter",
    "adapter_id": "codex_batch",
    "profile_id": "ambient_clean_fallback",
    "executor_kind": "codex.batch"
  }
}
```

## 7. Mapping to Existing Root Canonical

The following mapping is required:

| Execution identity | Existing canonical |
|---|---|
| `trace_id` | root field |
| `session_id` | root field |
| `run_id` | root field |
| `parent_run_id` | root field |
| `task_ref` | root field |
| `provider` | root field |
| `model` | root field |
| `repo_name` | root field |
| `repo_path` | root field |
| `repo_branch` | root field |
| `repo_head` | root field |
| `agent_name` | root field |
| `agent_source` | root field |
| `commit_sha` | root field |
| `lane_id` | payload extension for now |
| `role_id` | payload extension for now |
| `adapter_id` | payload extension for now |
| `profile_id` | payload extension for now |
| `executor_kind` | payload extension for now |

## 8. Archive Envelope Alignment

This identity contract must be rich enough to align:

- `agent.task.closeout`
- `agent.git.commit`
- `agent.git.head_change`
- runner adapter results
- OpenClaw execution-layer result events

Minimum expectations:

- `task_ref` ties closeout to execution result
- `trace_id` ties live telemetry to archive envelope
- `commit_sha` is populated when a run results in a commit-producing action

## 9. Non-Goals

- No implicit generation of new canonical root fields without mainline approval.
- No replacement of issue / job identity semantics already used elsewhere.
- No requirement that every event populate every optional field.

## 10. Acceptance Criteria

This draft is acceptable for `#115` if:

1. adapter outputs can always provide `trace_id/session_id/run_id/task_ref/source`
2. retries and delegated runs can be represented without ambiguity
3. main runtime can map the payload into current canonical fields plus a small
   extension block
