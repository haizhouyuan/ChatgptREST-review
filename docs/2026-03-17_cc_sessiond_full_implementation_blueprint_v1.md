# CC-Sessiond Full Implementation Blueprint v1

Date: 2026-03-17

## Executive Summary

当前 `cc-sessiond` 草稿版不具备可上线条件。它的问题不是“少几个修补”，而是还没有形成一个真正可执行、可恢复、可观测、可集成的 session service。

这次要交给 Claude Code 的目标，不是继续堆一个薄壳，而是把它做成一个真正的后台执行层：

- 提供 durable session registry
- 提供 restart-safe scheduler
- 提供真实可调用的 HTTP API
- 提供事件流、结果落盘、取消、继续、等待
- 复用现有 `CcExecutor` / `CcNativeExecutor` / official Claude Agent SDK 能力
- 支持 MiniMax-backed SDK path 和现有 headless runner fallback path

一句话：**把“Claude Code 执行”从若干脚本和内核碎片，收敛成一个统一的 session service。**

## Why The Current Draft Is Not Enough

当前草稿版暴露出的关键缺口：

1. API route 不能正确 import，也没有挂进 `create_app()`
2. session 创建后不会自动执行，scheduler loop 没启动
3. `cancel()` 在 async context 中会直接报 `event loop is already running`
4. `/continue` 只是记录 `continue_from`，没有真正续接 SDK conversation
5. `wait(timeout=...)` 没有真正执行 timeout
6. `claude-agent-sdk` 没有写进项目依赖，测试也没覆盖真实 SDK 路径

所以接下来的目标不是修单点 bug，而是把它重做成完整系统。

## Product Goal

对上层客户端，`cc-sessiond` 要提供一个统一 contract：

- `create session`
- `observe progress`
- `wait`
- `continue`
- `cancel`
- `get final result`
- `tail event stream`

对下层执行器，`cc-sessiond` 要提供一个统一 backend adapter 层：

- `sdk_official`
- `cc_executor_headless`
- `cc_native`

默认优先：

1. `sdk_official`
2. `cc_executor_headless`
3. `cc_native` 仅作为后续扩展，不要求首批默认启用

## Non-Goals For This Batch

这次不做：

- 直接替换所有现有 `CcExecutor` 调用方
- 直接移除现有 shell runner
- 直接改 OpenClaw / Antigravity 的所有调用链去依赖 `cc-sessiond`
- 做一个新的独立 systemd 服务单元

这些都可以后续接，但不应阻塞 `cc-sessiond` 首个全量版。

## Architecture

```text
Clients
- Codex / orchestration
- OpenClaw / OpenMind
- Antigravity
- manual CLI / scripts

          |
          v
cc-sessiond service layer
- API router
- session registry
- event log
- result/artifact store
- scheduler
- backend adapters
- auth / admission control

          |
          +--> backend: sdk_official
          |    - official Claude Agent SDK
          |    - MiniMax via ANTHROPIC_BASE_URL / ANTHROPIC_API_KEY
          |
          +--> backend: cc_executor_headless
          |    - existing CcExecutor dispatch_headless / dispatch_conversation
          |
          +--> backend: cc_native (optional lane)
               - existing CcNativeExecutor
```

## Implementation Principles

### 1. Do Not Create A Fourth Execution Stack

仓里已经有：

- `CcExecutor`
- `CcNativeExecutor`
- official Claude Agent SDK feasibility research

`cc-sessiond` 应该是 **service/orchestration layer**，不是第四套完全孤立执行器。

### 2. Backend Adapters Must Be Explicit

不要在 service 内部写死一种执行路径。要有 adapter boundary：

- `SessionBackend.create_run(...)`
- `SessionBackend.continue_run(...)`
- `SessionBackend.cancel_run(...)`
- `SessionBackend.poll_run(...)`
- `SessionBackend.result_from_run(...)`

### 3. Session State Must Be Durable

session registry 至少要记录：

- `session_id`
- `backend`
- `backend_run_id`
- `state`
- `prompt`
- `options`
- `created_at`
- `updated_at`
- `started_at`
- `completed_at`
- `result_ref`
- `error`
- `cost_usd`
- `tokens_in`
- `tokens_out`
- `parent_session_id`
- `continue_mode`

### 4. Event Stream Must Be First-Class

不能只保存最终结果。每个 session 需要：

- normalized event rows in SQLite
- raw NDJSON event stream on disk
- API tail endpoint
- optional SSE endpoint

### 5. Async Contract Must Be Real

所有 API route 都必须符合 async model：

- 不在 async route 里 `run_until_complete`
- `cancel()` 提供 async API
- `wait()` 真正尊重 timeout
- session worker loop 在 app lifespan 中启动和停止

### 6. Dependency Story Must Be Reproducible

如果首批就引入 official SDK：

- `pyproject.toml` 必须声明依赖
- `uv.lock` 必须更新
- 测试环境必须能导入

## Canonical Session Lifecycle

```text
created -> queued -> admitted -> running -> completed
                             \-> failed
                             \-> cancelled
                             \-> timed_out
```

补充语义：

- `queued`: 已写 registry，尚未被 scheduler 拉起
- `admitted`: 已通过 budget/concurrency 检查，即将执行
- `running`: backend 已确认开始
- `completed`: 有 final result
- `failed`: 有 terminal error
- `cancelled`: 调用方取消且 backend 已确认停止或被强制终止
- `timed_out`: wait/service timeout reached

## Canonical APIs

首批必须提供：

- `POST /v1/cc-sessions`
- `GET /v1/cc-sessions/{session_id}`
- `GET /v1/cc-sessions`
- `POST /v1/cc-sessions/{session_id}/continue`
- `POST /v1/cc-sessions/{session_id}/cancel`
- `GET /v1/cc-sessions/{session_id}/events`
- `GET /v1/cc-sessions/{session_id}/result`
- `GET /v1/cc-sessions/{session_id}/wait`

建议同时提供：

- `GET /v1/cc-sessions/{session_id}/stream` as SSE
- `GET /v1/cc-sessions/scheduler/status`

## Storage Layout

建议落到：

```text
state/cc_sessiond/
  registry.sqlite3
  events.sqlite3

artifacts/cc_sessions/<session_id>/
  request.json
  status.json
  result.json
  error.json
  events.jsonl
  backend_meta.json
  raw/
```

## Backend Design

### Backend A: `sdk_official`

首批主路径。

要求：

- 使用 official Claude Agent SDK
- 不使用 `cli_path=claudeminmax`
- 使用兼容 CLI 路径
- 通过 env 注入：
  - `ANTHROPIC_BASE_URL`
  - `ANTHROPIC_API_KEY`
- 支持：
  - create
  - continue
  - cancel
  - progress/event capture
  - final result capture

如果 SDK 本身不提供强 cancel，则必须在 service 层提供 task cancellation + terminal state discipline。

### Backend B: `cc_executor_headless`

首批 fallback path。

要求：

- 复用现有 `CcExecutor`
- 支持 single-shot run
- 支持 conversation-style continue when possible
- 标准化结果投影到 session result schema

### Backend C: `cc_native`

作为可选 lane。

要求：

- 复用现有 `CcNativeExecutor`
- 不要求首批默认路由
- 只要求 adapter boundary 预留

## Continue Semantics

`/continue` 必须区分两种模式：

1. `resume_same_session`
   - 继续同一 backend conversation / run

2. `fork_from_session`
   - 以原 session 为父，创建新的 session 继续

session registry 里要明确记录：

- `parent_session_id`
- `continue_mode`
- `backend_run_id`

不能只在 options 里塞一个 `continue_from` 然后没人消费。

## Cancellation Semantics

取消分三层：

1. queue cancellation
   - job 还没开始，直接移除队列
2. task cancellation
   - 本进程 task 正在跑，cancel asyncio task
3. backend cancellation
   - 如果 backend 提供 native cancel，向下取消

最终必须保证：

- registry state terminalized
- event log 记录 cancel 轨迹
- artifact `status.json` 同步更新

## Admission Control

首批必须有：

- `max_concurrent`
- `budget_per_hour`
- `budget_total`

增强建议：

- `max_sessions_per_client`
- `max_sessions_per_repo`
- `priority`

## Startup / Lifespan Integration

这是当前草稿版最大的缺口之一。正确做法：

- 在 FastAPI lifespan 中启动 scheduler loop
- 在 shutdown 中优雅停止
- 应用内 singleton client 只负责资源复用
- 不能指望 route 调用时临时手工触发

## Result Contract

统一结果格式至少要有：

- `ok`
- `session_id`
- `backend`
- `backend_run_id`
- `state`
- `output_text`
- `structured_output`
- `quality_score`
- `cost_usd`
- `tokens_in`
- `tokens_out`
- `started_at`
- `completed_at`
- `error`

## Test Strategy

### Unit

- registry CRUD
- state transition validation
- event log append/query/subscribe
- scheduler admission/cancel/timeout
- backend adapter projection

### Integration

- create -> queued -> running -> completed
- create -> cancel before start
- create -> cancel while running
- continue using parent session
- wait timeout behavior
- SSE/events tail
- app startup route registration

### Environment

- dependency import smoke
- SDK backend mocked flow
- fallback backend flow via `CcExecutor`

### Regression

- `create_app()` includes `cc-sessiond` router
- async cancel does not use `run_until_complete`
- no route remains stuck in `pending` without worker startup

## Required Batches For Claude Code

### Batch 0: Repair The Broken Scaffold

Must fix:

- route import path
- router registration in `create_app()`
- app lifespan startup / shutdown wiring
- async `cancel`
- real `wait(timeout=...)`
- dependency declaration

### Batch 1: Introduce Backend Adapter Layer

Add:

- backend protocol/interface
- `sdk_official` adapter
- `cc_executor_headless` adapter
- adapter result normalization

### Batch 2: Make Continue / Cancel Real

Add:

- parent/child session model
- continue mode semantics
- backend run id tracking
- cancel propagation

### Batch 3: Artifacts And Event Stream

Add:

- artifact directory layout
- `request.json/status.json/result.json/events.jsonl`
- SSE or tailable stream endpoint

### Batch 4: Full Test Matrix

Must add direct tests for:

- route import
- app registration
- lifecycle startup
- create/continue/cancel/wait/result
- backend adapter behaviors
- dependency import smoke

## Acceptance Criteria

Only merge when all of the following are true:

1. `/v1/cc-sessions` routes are present in `create_app()`
2. Creating a session in integration tests eventually leaves `pending`
3. `cancel` works from async route context
4. `continue` uses a real backend continuation contract
5. `wait(timeout=...)` returns or times out deterministically
6. `claude-agent-sdk` dependency is declared and locked if used
7. fallback path through `CcExecutor` is covered
8. walkthrough and contract docs are updated

## Merge Strategy

Do not merge as one giant ambiguous blob. Preferred order:

1. scaffold repair + route wiring + tests
2. backend adapters
3. continue/cancel semantics
4. artifact/event streaming
5. docs and rollout notes

If Claude Code still prefers one PR, it must still commit in these logical slices.
