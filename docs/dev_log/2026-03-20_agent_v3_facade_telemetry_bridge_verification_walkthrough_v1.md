# 2026-03-20 Agent v3 Facade Telemetry Bridge Verification Walkthrough v1

## 1. 任务目标

核验 [2026-03-20_agent_v3_facade_telemetry_bridge_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_agent_v3_facade_telemetry_bridge_v1.md) 是否已经把 `/v3/agent/*` facade telemetry gap 真正收口，并确认这次实现有没有带来行为回归。

## 2. 这次核验重点

这次我重点复核了 4 件事：

1. `_emit_runtime_event(...)` 是否真的不再是 no-op
2. `session.*` 事件是否已从 facade ledger 桥进 canonical telemetry plane
3. `agent_turn.completed` 是否在 sync/deferred 两条路径都被桥接
4. 这次实现是否改坏了原有 session state machine 或 response schema

## 3. 重新核对的对象

- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L101)
- [telemetry_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/telemetry_service.py#L62)
- [tests/test_routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3.py)
- [tests/test_agent_v3_routes.py](/vol1/1000/projects/ChatgptREST/tests/test_agent_v3_routes.py)
- 本地 `pytest -q tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py`

同时我还看了 GitNexus 对 `make_v3_agent_router` 的 impact，确认这次改动落在 `CRITICAL` hot path，但 direct callers 仍然集中在 `create_app` 和测试入口。

## 4. 这次确认成立的部分

我确认这次实现不是“文档说桥接”，而是代码真的桥接了：

- `_emit_runtime_event(...)` 已经改成真实走 `TelemetryIngestService`
- `_append_session_event(...)` 在保持本地 durable ledger 的同时，会把 `session.*` 再投进 canonical telemetry plane
- sync/deferred 两条 `agent_turn.completed` 路径都已补齐

同时我也确认这次改动没有重写 session 结构：

- `state/agent_sessions` 还是原 truth
- `/v3/agent/session/*` schema 没有被扩大
- cancel/job/controller 语义没被重构

## 5. 这次没有发现什么问题

这次没有发现需要回滚或继续升版修复的实质性问题。

原因是：

- 核心桥接链路已经有直接代码证据
- 新增回归测试覆盖了最关键的 `session.created / session.status / session.cancelled / agent_turn.completed`
- 我本地跑的定向 pytest 通过

## 6. 残留 coverage gap

这次保留的不是 finding，而是测试缺口：

- `session.error` 没有单独测试
- `observer fallback` 没有单独测试

这两点值得后续补，但现在还不足以推翻这版实现。

## 7. 最终判断

所以这轮核验的最终判断是：

- `6b20962` 这版实现成立
- facade telemetry gap 已经被真实收口
- 下一步应回到运行面，把 `18713` fallback 清掉并恢复 `chatgptrest-api.service`

## 8. 产物

本轮新增：

- [2026-03-20_agent_v3_facade_telemetry_bridge_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_agent_v3_facade_telemetry_bridge_verification_v1.md)
- [2026-03-20_agent_v3_facade_telemetry_bridge_verification_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_agent_v3_facade_telemetry_bridge_verification_walkthrough_v1.md)

## 9. 测试说明

这轮核验没有改代码，但补跑了：

```bash
./.venv/bin/pytest -q tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py
```
