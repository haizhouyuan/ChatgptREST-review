# 2026-03-20 Agent v3 Facade Telemetry Bridge Verification v1

## 1. 核验对象

本次核验针对：

- [2026-03-20_agent_v3_facade_telemetry_bridge_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_agent_v3_facade_telemetry_bridge_v1.md)
- [2026-03-20_agent_v3_facade_telemetry_bridge_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_agent_v3_facade_telemetry_bridge_walkthrough_v1.md)

被核验提交：

- `6b20962d63c39aa0d2c71f4a24087b1c809a92fd`

## 2. 核验结论

这次核验没有发现新的实质性回归问题。

`agent_v3_facade_telemetry_bridge_v1` 这版实现与前面的 telemetry contract 是一致的，主结论成立：

1. facade-local durable ledger 仍然保留在 `state/agent_sessions`
2. `session.created / session.status / session.cancelled` 现在确实会桥进 canonical telemetry plane
3. `agent_turn.completed` 也已经不再是 no-op
4. 这次改动没有扩大 `/v3/agent/*` 的 session state machine 或 response schema

当前可以把这版当成 facade telemetry bridge 这条实现线的正确收口。

## 3. 已核实成立的部分

## 3.1 `_emit_runtime_event(...)` 已从占位 no-op 变成真实 bridge

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L101) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L180) 已经不再是空函数，而是通过 `TelemetryIngestService(runtime)` 把事件送进 canonical telemetry plane。

这和 [telemetry_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/telemetry_service.py#L62) 到 [telemetry_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/telemetry_service.py#L146) 的既有 contract 对齐：

- 优先 `event_bus.emit(...)`
- 否则 fallback 到 `observer.record_event(...)`

所以这次没有另起一套 telemetry writer，而是复用了已有 canonical plane。

## 3.2 facade session 事件已经被桥接

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1055) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1092) 说明：

- `_append_session_event(...)` 仍然先写 `AgentSessionStore`
- 但对 `session.*` 事件新增了 telemetry bridge

桥接 payload 里带了：

- `status`
- `route`
- `run_id`
- `job_id`
- `consultation_id`
- `answer_chars`
- `event_seq`
- `event_ts`

同时 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1116) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1124) 说明 `trace_id` 已被纳入 `_upsert_session(...)` 的 event payload，后续 status bridge 可以沿用同一 trace continuity。

## 3.3 `agent_turn.completed` 也已经桥进 runtime telemetry

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1666) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1677) 说明 deferred 路径完成时会 emit `agent_turn.completed`。

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1695) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1706) 说明 sync 路径完成时也会 emit 同样的 event。

这与文档中的实现目标一致。

## 3.4 state machine / durable truth 没有被改坏

本次改动虽然触到 high-risk hot path，但代码层面没有改坏原有 session truth：

- `AgentSessionStore` 的写法没有被替换掉
- `session.created` / `session.status` 仍然来源于原有 `_upsert_session(...)`
- `session.cancelled` 仍然来源于原有 cancel flow
- `/v3/agent/session/*` 的 response schema 没有新增 breaking 字段

这点与 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L956) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L980) 的 session response 构造和现有 session ledger 语义保持一致。

## 3.5 定向回归在本地通过

我本地执行了文档里声明的定向回归：

```bash
./.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py
```

结果通过。

新增测试至少已经覆盖：

- facade session 事件进入 fake runtime `event_bus`
- `session.created / session.status / agent_turn.completed` 的 trace continuity
- `session.cancelled` 的 bridge payload

## 4. 残留测试缺口

这次没有发现实质性 bug，但仍有 2 个 coverage gap 没被直接测到：

1. `session.error` bridge 没有单独的回归用例
2. `observer` fallback path 没有单独的回归用例

这两点目前更像测试缺口，不是现成 bug，因为实现路径与 `TelemetryIngestService` 现有 contract 一致。

## 5. 最终结论

我的最终判断是：

- `6b20962` 这版实现没有发现新的行为回归
- facade session telemetry gap 已经被真实收口
- 当前可以把它当成 `agent_v3_facade_telemetry_bridge` 这条实现线的正确版本

下一步如果继续推进，最合理的顺序仍然是：

1. 清理 maint 侧 telemetry mirror 的 `18713` fallback
2. 恢复 `chatgptrest-api.service`
3. 视需要补 `session.error` 和 `observer fallback` 的测试覆盖
