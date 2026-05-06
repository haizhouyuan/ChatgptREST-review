# 2026-03-20 Telemetry Contract Fix Walkthrough v1

## 1. 任务目标

完成：

- [2026-03-20_telemetry_contract_fix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_telemetry_contract_fix_v1.md)

这次目标不是直接修某一个 `404`，而是把 telemetry 的：

- canonical plane
- HTTP ingest seam
- live host drift
- signal family split

一次写清。

## 2. 这次重点核对的问题

我这次围绕 5 个问题收证据：

1. `/v2/telemetry/ingest` 到底挂在哪个 app 上
2. telemetry canonical 到底是 HTTP endpoint 还是 EventBus/observer
3. OpenClaw plugin 现在实际指向哪个 baseUrl
4. `18713 404` 到底是谁返回的
5. `/v3/agent/*` 的 facade session telemetry 到底有没有真正并入 canonical plane

## 3. 这次读取的关键对象

- [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py#L467)
- [app.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L150)
- [telemetry_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/telemetry_service.py#L62)
- [event_bus.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/event_bus.py#L151)
- [openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts#L163)
- [/vol1/maint/ops/scripts/agent_activity_event.py](/vol1/maint/ops/scripts/agent_activity_event.py#L27)
- [/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json](/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L165)

同时我还核了 live systemd/socket：

- `chatgptrest-api.service`
- `openclaw-gateway.service`
- `ss -ltnp`
- 本地 `curl http://127.0.0.1:18713/v2/telemetry/ingest`

## 4. 这次最关键的发现

### 4.1 `18713` 不是 telemetry host

这次最大的 live drift 是：

- `18713` 当前不是 FastAPI telemetry host
- 也不是 `openclaw-gateway.service` 主监听端口
- 它现在实际是 `gitnexus serve`

所以 closeout 的：

- `18711 refused`
- `18713 404`

不是“同一个服务一会儿通一会儿不通”，而是：

- canonical target 停着
- fallback target 本来就错了

### 4.2 gateway plugin 并没有打错 target

当前 OpenClaw 安装态里：

- `openmind-advisor`
- `openmind-memory`
- `openmind-graph`
- `openmind-telemetry`

全都明确配置为：

- `http://127.0.0.1:18711`

所以 `openmind-telemetry: flush failed: TypeError: fetch failed` 的正确含义是：

- `18711` host 当前不可达

而不是：

- plugin baseUrl drift

### 4.3 telemetry canonical 不是 HTTP endpoint

代码里已经很清楚：

- out-of-process producer 通过 `/v2/telemetry/ingest` 进来
- 但真正 canonical telemetry plane 是 `EventBus / observer / signals`

这点如果不冻结，后面所有 host/fallback 讨论都会再次把 route 和 ledger 混成一件事。

### 4.4 facade session telemetry 还是缺口

`/v3/agent/*` 已经有：

- facade session truth
- facade session event log

但这些还只是写在 `state/agent_sessions/*.events.jsonl`，没有统一投影进 canonical telemetry plane。

这说明：

- facade session truth 已经有了
- facade session telemetry 还没有完全收口

## 5. 最终收下来的 contract

我最后冻结成 4 条：

1. canonical telemetry plane
   - `EventBus / observer / signals substrate`
2. canonical HTTP ingest seam
   - `chatgptrest-api.service` 上的 `POST /v2/telemetry/ingest`
3. external producer target
   - 统一指向 `18711`
4. signal family split
   - continuity
   - facade session
   - execution
   - payload/delivery

## 6. 这版为什么重要

因为后面不管做：

- runtime recovery
- closeout telemetry mirror 修复
- OpenClaw plugin 恢复
- facade telemetry 补齐

都必须先接受一个事实：

**telemetry 不是单一 HTTP endpoint，而是 producer class + ingest seam + canonical plane 的组合。**

## 7. 产物

本轮新增：

- [2026-03-20_telemetry_contract_fix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_telemetry_contract_fix_v1.md)
- [2026-03-20_telemetry_contract_fix_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_telemetry_contract_fix_walkthrough_v1.md)

## 8. 测试说明

这次仍然是文档与代码证据决策任务，没有改代码，也没有跑测试。
