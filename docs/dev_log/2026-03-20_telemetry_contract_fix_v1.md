# 2026-03-20 Telemetry Contract Fix v1

## 1. 决策目标

这份文档承接：

- [2026-03-20_authority_matrix_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v2.md)
- [2026-03-20_front_door_contract_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_v2.md)
- [2026-03-20_session_truth_decision_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v3.md)
- [2026-03-20_post_reconciliation_next_phase_plan_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_post_reconciliation_next_phase_plan_v1.md)

这次要修的不是“一个 telemetry bug”，而是 4 件被混写的东西：

1. canonical telemetry plane 到底是什么
2. `/v2/telemetry/ingest` 到底是什么
3. 当前 live host 为什么持续失败
4. continuity / facade / execution / payload 这 4 类信号应该怎么分层

如果这 4 件事不拆开，后面所有 runtime recovery、closeout mirror、OpenClaw telemetry、EvoMap signals 都会继续互相误伤。

## 2. 独立判断

我这次独立回到代码、systemd、socket、live config 复核后，结论是：

- `/v2/telemetry/ingest` 的 canonical route 仍然存在
- 但它属于 `chatgptrest-api.service` 这条 FastAPI host，不属于当前 `127.0.0.1:18713`
- 当前 `18713` 的 `404` 不是“telemetry route 不存在”，而是因为 `18713` 现在被别的 Node 服务占着
- OpenClaw `openmind-telemetry` 插件并没有打错地址；它 live config 仍然明确指向 `http://127.0.0.1:18711`
- 所以 gateway 持续刷 `fetch failed` 的根因不是插件 target 错，而是 canonical FastAPI telemetry host 现在停着

更重要的是：

- `telemetry canonical` 不能再被写成“HTTP endpoint”
- 它实际上是：
  - **in-process emitters + HTTP ingest seam**
  - 一起汇入 **EventBus / observer / signals**

## 3. 代码现实

## 3.1 `/v2/telemetry/ingest` 真实属于 FastAPI cognitive router

[routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py#L311)
已经把 cognitive router 固定在：

- `prefix="/v2"`

[routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py#L467)
到 [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py#L503)
则明确：

- route 就是 `POST /v2/telemetry/ingest`
- handler 直接调用 `TelemetryIngestService.ingest(...)`

[app.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L150)
进一步证明：

- 这套路由只在 `chatgptrest.api.app:create_app` 这台 FastAPI app 上挂载

所以 `/v2/telemetry/ingest` 的 canonical HTTP ingress 应冻结成：

- **ChatgptREST FastAPI cognitive ingress**

不是 OpenClaw gateway 路由，也不是任意 `127.0.0.1` 上的某个 `/v2` 端口。

## 3.2 Telemetry canonical plane 不是 HTTP route，而是 EventBus / observer

[telemetry_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/telemetry_service.py#L62)
到 [telemetry_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/telemetry_service.py#L146)
已经说明：

- `/v2/telemetry/ingest` 只是把外部 telemetry 事件接进来
- 真正 ingest 后：
  - 优先写 `event_bus.emit(...)`
  - 若没有 event bus，则 fallback 到 `observer.record_event(...)`

[event_bus.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/event_bus.py#L151)
到 [event_bus.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/event_bus.py#L176)
则说明：

- `EventBus.emit(...)` 会先持久化，再通知 subscribers

所以 telemetry 的 canonical plane 不该再写成：

- “`POST /v2/telemetry/ingest` 就是 telemetry 真相源”

更准确的说法是：

- **canonical telemetry plane = EventBus / observer / signals substrate**
- **`/v2/telemetry/ingest` = out-of-process ingress seam**

## 3.3 当前至少有两类 producer，不应混成一类

### A. In-process emitters

这类 producer 根本不经过 `/v2/telemetry/ingest`。

[advisor/runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L203)
到 [advisor/runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L235)
说明：

- runtime LLM signals 直接写 `event_bus.emit(...)`
- 不通 HTTP route

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L352)
到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L445)
说明：

- premium review / post-review signals 直接写 `TraceEvent`

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L432)
到 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L469)
说明：

- advisor runtime 自己也有 `EventBus + observer fallback` emit path

[cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py#L229)
到 [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py#L257)
说明：

- `cc_native` 既能直接写 `TraceEvent`
- 也能直接写 observer signal

### B. Out-of-process ingress producers

这类 producer 通过 `POST /v2/telemetry/ingest` 把事件送进来。

[openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts#L163)
明确 OpenClaw telemetry plugin 是直接 POST：

- `/v2/telemetry/ingest`

[controller_lane_wrapper.py](/vol1/1000/projects/ChatgptREST/ops/controller_lane_wrapper.py#L77)
到 [controller_lane_wrapper.py](/vol1/1000/projects/ChatgptREST/ops/controller_lane_wrapper.py#L112)
说明 controller lane wrapper 默认打：

- `http://127.0.0.1:18711/v2/telemetry/ingest`

[/vol1/maint/ops/scripts/agent_activity_event.py](/vol1/maint/ops/scripts/agent_activity_event.py#L27)
到 [/vol1/maint/ops/scripts/agent_activity_event.py](/vol1/maint/ops/scripts/agent_activity_event.py#L30)
说明 closeout / git activity mirror 当前默认候选是：

- `http://127.0.0.1:18711/v2/telemetry/ingest`
- `http://127.0.0.1:18713/v2/telemetry/ingest`

这也是当前 `closeout` 会出现 `18711 refused / 18713 404` 的直接来源。

## 3.4 OpenClaw 插件 live target 没打错，当前就是 `18711`

这点必须写清，不然很容易误把 gateway 错误归咎到插件配置。

[openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts#L50)
到 [openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts#L72)
说明源码默认值就是：

- `http://127.0.0.1:18711`

更关键的是，当前 live 安装态配置也明确如此。

[/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json](/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L165)
到 [/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json](/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L220)
显示：

- `openmind-advisor.endpoint.baseUrl = http://127.0.0.1:18711`
- `openmind-graph.endpoint.baseUrl = http://127.0.0.1:18711`
- `openmind-memory.endpoint.baseUrl = http://127.0.0.1:18711`
- `openmind-telemetry.endpoint.baseUrl = http://127.0.0.1:18711`

所以 `openmind-telemetry: flush failed: TypeError: fetch failed` 的正确解读是：

- **canonical FastAPI target 当前不可达**

而不是：

- 插件 secretly 指到了错误 host

## 3.5 当前 `18713` 不是 telemetry host，closeout fallback 假设过时了

这是这次最关键的 live drift。

当前 `ss -ltnp` 实测：

- `127.0.0.1:18713` 的监听进程是
  - `node ... gitnexus/dist/cli/index.js serve --host 127.0.0.1 --port 18713`
- `openclaw-gateway.service` 自己监听的是：
  - `18789`
  - `18791`
  - `18792`

对 `http://127.0.0.1:18713/v2/telemetry/ingest` 的本地 curl 也直接返回：

- `HTTP/1.1 404 Not Found`
- `X-Powered-By: Express`

同时 [app.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L195)
到 [app.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L200)
仍然说明：

- ChatgptREST FastAPI API 默认端口本来就是 `18711`

[systemctl status] 的 live 状态则显示：

- `chatgptrest-api.service` 已在 `2026-03-19 03:57 CST` 停止
- 它停之前对 `POST /v2/telemetry/ingest` 是正常 `200 OK`

所以当前 live failure 的准确说法是：

1. telemetry canonical HTTP target 仍然是 `18711`
2. 它现在停着，所以 OpenClaw plugin 只能报 `fetch failed`
3. `agent_activity_event.py` 默认把 `18713` 当 fallback，这个假设已经过时，因为 `18713` 现在是 GitNexus serve

## 3.6 facade session telemetry 目前还是 contract gap，不应假装已收口

这一点也要写清，否则 telemetry 文档又会把 truth 和 signal 混起来。

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968)
到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1012)
说明：

- `/v3/agent/*` 确实有 facade session ledger
- 并且会写 `session.created`
- `session.status`

但这些事件目前只是写入 `state/agent_sessions/*.events.jsonl`。

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1691)
到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1696)
也说明：

- `session.cancelled` 仍然只是 facade-local session event

也就是说：

- facade session truth 已经有了
- facade session telemetry 还没有统一进入 canonical telemetry plane

这必须在 contract 里标记成：

- **未收口缺口**

## 4. 正式决策

## 4.1 Telemetry canonical plane

当前 canonical owner：

- `EventBus`
- observer / signals substrate

结论：

- **A1 Canonical**

解释：

- HTTP ingress 只是写入入口
- 真正 durable + subscriber fanout 的 telemetry 真相源是 runtime telemetry plane

## 4.2 Canonical HTTP ingest seam

当前 canonical HTTP target：

- `POST http://127.0.0.1:18711/v2/telemetry/ingest`

结论：

- **A1 Canonical HTTP ingest target**

注意：

- 这是 `chatgptrest-api.service` / FastAPI host
- 不是 `18713`
- 也不是 OpenClaw gateway port

## 4.3 Producer split

### A. In-process emitters

owner：

- advisor runtime
- `routes_agent_v3` premium review writeback
- `routes_advisor_v3` runtime events
- `cc_native` / `cc_executor`
- 其他直接写 `TraceEvent` / observer 的 runtime pieces

结论：

- **A1 Canonical in-process producer class**

### B. Out-of-process ingress producers

owner：

- OpenClaw `openmind-telemetry`
- `controller_lane_wrapper`
- maint `agent_activity_event.py`

结论：

- **A1 Canonical external producer class**

注意：

- 这类 producer 的 contract 是打 `18711 /v2/telemetry/ingest`
- 不是直接决定 canonical telemetry plane

## 4.4 Signal families

从现在开始，telemetry 至少分 4 类看：

1. **continuity signals**
   - OpenClaw runtime lifecycle / upstream continuity related
2. **facade session signals**
   - `/v3/agent/*` public facade session events
   - 当前仍是缺口，尚未统一进入 canonical telemetry plane
3. **execution signals**
   - route / llm / workflow / team / tool / controller
4. **payload / delivery signals**
   - payload delivery failure
   - controller delivery ready
   - payload presence / export status

不能再把这 4 类全写成“同一个 telemetry stream”。

## 4.5 Live drift fixes that must follow this contract

基于当前代码和 live 状态，后续 fix 必须按这个方向做：

1. `agent_activity_event.py`
   - 默认 mirror target 不应再把 `18713` 当标准 fallback
   - `18713` 当前是 GitNexus serve，不是 telemetry host
2. OpenClaw plugins
   - 继续统一指向 `18711`
   - 不允许把 plugin target 改去 `18713` 作为“修复”
3. runtime host recovery
   - 要让 `openmind-telemetry` flush 恢复成功，真正要修的是 `chatgptrest-api.service`
   - 不是去改 plugin 或换路由名字
4. facade session telemetry
   - 后续应把 `state/agent_sessions` 里的 `session.*` 事件投影进 canonical telemetry plane
   - 但这一步是新增收口，不是当前已经具备的事实

## 5. 从现在开始不能再写的话

从现在开始，后续文档不能再写：

- “`/v2/telemetry/ingest` 就是 telemetry canonical”
- “`18713` 是 telemetry fallback host”
- “OpenClaw plugin 当前 telemetry target 配错了”
- “gateway `fetch failed` 说明 telemetry route 不存在”
- “facade session telemetry 已经和 facade session truth 完全收口”

## 6. 最终判断

当前系统关于 telemetry 的最准确说法是：

- **canonical telemetry plane = EventBus / observer / signals substrate**
- **canonical HTTP ingest seam = `chatgptrest-api.service` 上的 `POST /v2/telemetry/ingest`**
- **OpenClaw telemetry plugin live target 仍然正确指向 `18711`**
- **当前 gateway flush 失败的真实根因是 `18711` host 停机**
- **closeout 出现 `18713 404` 是因为 maint fallback 还沿用过时假设，而 `18713` 当前实际上是 GitNexus serve**
- **facade session telemetry 仍是缺口，不应假装已收口**

这才是后面继续做 runtime recovery、closeout mirror 修复、telemetry host 恢复时应该使用的准确前提。
