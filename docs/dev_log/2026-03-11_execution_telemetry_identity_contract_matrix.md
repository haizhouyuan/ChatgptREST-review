# 2026-03-11 execution telemetry identity contract matrix

## Why

主线 `telemetry -> canonical EvoMap` 已经打通多条 emitter：

- 手工 `/v2/telemetry/ingest`
- `controller_lane_wrapper`
- OpenClaw `openmind-telemetry` plugin
- archive envelope (`agent.task.closeout` / `agent.git.commit`)
- `cc_native dispatch.task.*`
- `cc_executor task.*`

这时最容易出现的新风险，不是缺入口，而是不同 emitter
开始各自漂移 identity 字段，导致：

- dedup 口径不一致
- `task_ref/run_id/provider/model/agent_name` 丢失
- archive/live 不再说同一种 identity 语言

## What changed

文件：

- `tests/test_telemetry_contract.py`

新增 contract tests，锁住 4 类真实 emitter shape：

- `controller_lane_wrapper`
- OpenClaw `openmind-telemetry` plugin
- `cc_native` EventBus payload
- `cc_executor` EventBus payload

## Contract focus

这轮不改 root canonical schema，但把一小组 execution-layer extension
透传进统一 identity 视图，避免这些字段在 live/runtime 里白白丢失：

- `lane_id`
- `role_id`
- `adapter_id`
- `profile_id`
- `executor_kind`

同时继续验证当前主线已成立的 root identity 视图不漂移：

- `source`
- `session_id`
- `event_id`
- `upstream_event_id`
- `run_id`
- `task_ref`
- `repo_name/repo_path`
- `agent_name/agent_source`
- `provider/model`

这些 extension 目前只是被保留在 normalized identity view 里，
**不是** root canonical 的升级，也**不是**对 `#115` contract 线的抢跑。

## Boundary

这轮不做：

- 新增 live event type
- 改 `TraceEvent` schema
- 改 `ActivityIngestService`
- 改 execution-layer contract

目标只是把主线当前已经成立的 emitter mapping 用测试固定住，
避免后续再出现 archive/live/plugin/wrapper/cc_* 重新分叉。
