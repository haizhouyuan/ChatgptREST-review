# 2026-03-20 Telemetry Contract Fix Verification v1

## 1. 核验对象

本次核验针对：

- [2026-03-20_telemetry_contract_fix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_telemetry_contract_fix_v1.md)
- [2026-03-20_telemetry_contract_fix_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_telemetry_contract_fix_walkthrough_v1.md)

被核验提交：

- `89e286ddb5d4a439ac28249e218cd61aeb88599e`

## 2. 核验结论

这次核验没有发现新的实质性问题。

`telemetry_contract_fix_v1` 这版已经把 telemetry 线的 5 个关键边界拆清了，而且代码与 live 状态都支持这些判断：

1. canonical telemetry plane 不是单一 HTTP endpoint，而是 `EventBus / observer / signals` substrate
2. canonical HTTP ingest seam 仍然是 FastAPI 上的 `POST /v2/telemetry/ingest`
3. OpenClaw 四个 OpenMind 插件当前 live target 确实都还是 `http://127.0.0.1:18711`
4. 当前 `127.0.0.1:18713` 的 `404` 来自 GitNexus Node/Express 服务，不是 telemetry route 消失
5. `/v3/agent/*` 的 facade session telemetry 目前仍然没有桥进 canonical plane，这条 gap 被正确保留了

当前可以把这版当成 telemetry contract 这条线的 freeze 文档。

## 3. 已核实成立的部分

## 3.1 `/v2/telemetry/ingest` 的 canonical HTTP ingress 仍然属于 FastAPI cognitive router

[routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py#L311) 到 [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py#L315) 把 cognitive router 固定在 `prefix="/v2"`。

[routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py#L467) 到 [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py#L503) 明确注册了 `POST /v2/telemetry/ingest`。

[app.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L150) 到 [app.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L151) 说明 cognitive router 是挂在 `chatgptrest.api.app:create_app` 这台 FastAPI app 上的。

[app.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L195) 到 [app.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L200) 则说明这台 app 的默认监听端口仍然是 `18711`。

所以文档把 canonical HTTP seam 定成 `chatgptrest-api.service` 上的 `POST /v2/telemetry/ingest`，是成立的。

## 3.2 canonical telemetry plane 不是 route，而是 EventBus / observer substrate

[telemetry_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/telemetry_service.py#L62) 到 [telemetry_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/telemetry_service.py#L146) 说明 ingest handler 的真正动作是：

- 优先 `event_bus.emit(...)`
- 否则 fallback 到 `observer.record_event(...)`

[event_bus.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/event_bus.py#L151) 到 [event_bus.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/event_bus.py#L176) 则说明 `EventBus.emit(...)` 会先持久化，再 fanout 给 subscribers。

同时 repo 内还有明确不走 HTTP seam 的 in-process emitters：

- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L203) 到 [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L235)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L344) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L450)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L432) 到 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L469)
- [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py#L229) 到 [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py#L259)

所以文档把 canonical telemetry 写成 runtime plane，而不是单一 route，也成立。

## 3.3 OpenClaw 四个 OpenMind 插件 live target 确实都还是 `18711`

[openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts#L50) 到 [openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts#L72) 说明 telemetry 插件源码默认 baseUrl 就是 `http://127.0.0.1:18711`。

[openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts#L161) 到 [openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts#L180) 说明它实际 POST 的 path 仍是 `/v2/telemetry/ingest`。

当前 live 安装态配置也直接坐实 4 个插件都指向 `18711`：

- [openclaw.json](/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L165)
- [openclaw.json](/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L175)
- [openclaw.json](/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L189)
- [openclaw.json](/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L210)

因此 `openmind-telemetry: flush failed: TypeError: fetch failed` 的正确归因仍然是 `18711` host down，而不是 plugin baseUrl drift。

## 3.4 当前 `18713` 的 404 来自 GitNexus Node/Express，而不是 telemetry route 消失

live 端口和进程状态直接支持这一点：

- `ss -ltnp` 当前显示 `127.0.0.1:18713` 监听者是 `node`
- `ps -fp 2939905` 进一步确认它是 `gitnexus/dist/cli/index.js serve --host 127.0.0.1 --port 18713`

对 `18713` 的实际请求也支持这一结论：

- `POST http://127.0.0.1:18713/v2/telemetry/ingest` 返回 `HTTP/1.1 404 Not Found`
- 响应头包含 `X-Powered-By: Express`
- body 是 `Cannot POST /v2/telemetry/ingest`

同时 FastAPI canonical host 的 live service 状态是：

- `chatgptrest-api.service` 自 `2026-03-19 03:57:01 CST` 起处于 `inactive (dead)`
- 它停前日志中仍有 `POST /v2/telemetry/ingest HTTP/1.1" 200 OK`

这说明文档把 `18713 404` 定性为“过时 fallback 假设命中错误服务”，是对的。

## 3.5 `/v3/agent/*` facade session telemetry 仍然只是本地 ledger event，gap 判断成立

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1012) 说明：

- `session.created`
- `session.status`

都只是通过 `_append_session_event(...)` 写入 `AgentSessionStore`。

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1691) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1696) 说明 `session.cancelled` 也是同一条 facade-local event path。

repo 搜索也只找到这些事件定义出现在 `routes_agent_v3.py` 里，没有发现把这些 `session.*` 事件投进 `EventBus` 或 `observer` 的桥接代码。

当前 live `state/agent_sessions/*.events.jsonl` 也确实直接包含：

- `session.created`
- `session.status`

所以文档把 `/v3/agent/*` facade session telemetry 继续标成 contract gap，是成立的。

## 4. 边界说明

这版还需要保留两个表述边界，但都不是 findings：

1. `18713 = GitNexus serve` 是当前 live drift，不是抽象 contract
2. `18711 = canonical HTTP ingest seam` 是当前 FastAPI runtime/service target；更抽象的 contract 仍然应该优先写“FastAPI cognitive ingress”

## 5. 最终结论

我的最终判断是：

- `89e286d` 这版 `telemetry_contract_fix_v1` 没有新的结构性问题
- 它已经把 telemetry plane、HTTP seam、producer split、live host drift、facade gap 这 5 件事拆到了当前足够稳定的状态
- 当前可以把它当成 telemetry contract 这条线的 freeze 文档

基于这个结论，后续直接进入这 3 个实现面是合理的：

1. 清理 maint 侧 telemetry mirror 的 `18713` 默认 fallback
2. 恢复 `chatgptrest-api.service`
3. 给 `/v3/agent/*` 补 facade session 到 canonical telemetry plane 的桥接
