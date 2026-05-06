# 2026-03-20 Agent v3 Facade Telemetry Bridge v1

## 背景

前面的 `telemetry_contract_fix_v1` 已经把 telemetry 线的 authority 冻结清楚：

- canonical telemetry plane = `EventBus / observer / signals`
- canonical HTTP ingress seam = `POST /v2/telemetry/ingest`
- `/v3/agent/*` 的 facade session 事件仍然只写本地 `state/agent_sessions/*.events.jsonl`

这意味着 public agent facade 自己的 session 生命周期虽然在本地 durable ledger 里存在，但没有桥进 canonical telemetry plane，导致：

- EvoMap / EventBus 看不到 `session.created`
- 看不到 facade status 变迁
- 看不到 `session.cancelled`
- `agent_turn.completed` 也没有真正写进 runtime telemetry

## 实现

本次只做最小实现面收口，不改 session truth，也不碰 HTTP telemetry host：

1. 在 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py) 里把 `_emit_runtime_event(...)` 从 no-op 占位实现改成真正走 `TelemetryIngestService(runtime)` 的 runtime telemetry bridge。
2. 在同文件的 `_append_session_event(...)` 里，对 `session.*` 事件增加 canonical telemetry bridge：
   - `session.created`
   - `session.status`
   - `session.cancelled`
   - `session.error`
3. 初始 session upsert 现在显式保存 `trace_id`，保证后续 status/cancel 事件能沿用同一 trace。
4. 保持原有 facade-local durable ledger 不变，仍继续写 `state/agent_sessions/*.json + *.events.jsonl`。

## 结果

现在 `/v3/agent/*` 的 facade session 链已经具备双写：

- local facade ledger：继续作为 public session truth
- canonical telemetry plane：进入 `EventBus / observer / signals`

具体表现：

- `POST /v3/agent/turn`
  - 产生 `session.created`
  - 当底层 run 从 `running -> completed/failed/...` 变化时产生 `session.status`
  - 完成时产生 `agent_turn.completed`
- `POST /v3/agent/cancel`
  - 产生 `session.cancelled`

## 验证

定向回归通过：

```bash
./.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py
```

新增断言覆盖：

- facade session 事件进入 fake runtime `event_bus`
- `session.created` / `session.status` / `agent_turn.completed` 带 trace continuity
- `session.cancelled` 带取消 job 列表

## 未覆盖

这次没有处理以下两项：

- maint 侧 telemetry mirror 仍然保留 `18713` 的过时 fallback 假设
- `chatgptrest-api.service` 当前仍未恢复运行，`18711` 还是 connection refused

这两项属于后续运行面修复，不属于本次 facade bridge 代码收口。
