# 2026-03-20 Agent v3 Facade Telemetry Bridge Walkthrough v1

## 做了什么

- 读取并核对了 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)、[telemetry_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/telemetry_service.py)、相关测试文件。
- 先跑 GitNexus impact：
  - `_append_session_event` = `CRITICAL`
  - `_upsert_session` = `CRITICAL`
  - `_emit_runtime_event` = `CRITICAL`
  - `agent_turn` = `LOW`
- 在 `routes_agent_v3.py` 中只收窄改这条链：
  - `_emit_runtime_event`
  - `_append_session_event`
  - `_upsert_session`
  - `agent_turn` 初始 `trace_id` 透传
- 在 [tests/test_routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3.py) 新增 facade telemetry 回归用例。

## 为什么这样改

这次不重写 session 结构，也不引入新 service，原因很简单：

- canonical telemetry plane 已经存在，继续复用 `TelemetryIngestService`
- facade-local ledger 也已经是 live truth，不能改动它的 durable 语义
- 缺口只是“没有桥”

所以最小正确解不是另起一套 telemetry writer，而是：

- 继续本地写 `AgentSessionStore`
- 同时把 `session.*` 和 `agent_turn.completed` 送进 runtime telemetry

## 验证

执行：

```bash
./.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py
```

结果：

- `33 passed`

## 影响面说明

虽然 GitNexus 把 `_append_session_event` / `_upsert_session` / `_emit_runtime_event` 标成了 `CRITICAL`，但这次实际改动没有扩大 session state machine：

- 没改 SSE 协议
- 没改 `state/agent_sessions` 文件格式
- 没改 `/v3/agent/session/*` response schema
- 没改底层 controller / job cancel 语义

变化只在于：

- canonical telemetry 现在终于能看见 facade session 生命周期
