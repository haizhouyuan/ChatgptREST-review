# 2026-03-20 Front Door Contract v2

## 1. 为什么需要 v2

[2026-03-20_front_door_contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_v1.md)
已经把最重要的主结论写对了：

- `/v3/agent/turn` 是公开 live ask 正门
- `/v2/advisor/ask` 是 internal smart-execution 入口
- `/v2/advisor/advise` 是 internal graph/controller 入口

但 Claude 的复核指出，`v1` 还不能直接当“完整 ingress truth”：

1. 还漏了一个仍然活着的 legacy compatibility ingress：`/v1/advisor/advise`
2. 把 webhook 混写进了 `/v2/advisor/advise`

这份 `v2` 建立在下面两份文档之上：

- [2026-03-20_front_door_contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_v1.md)
- [2026-03-20_front_door_contract_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_verification_v1.md)

`v2` 的目标是把 front door 讲完整，但不再把不同类型的 ingress 混成一坨。

## 2. 先说结论

从现在开始，front door 必须分成两类看：

1. **Ask ingress**
   - `/v3/agent/turn`
   - `/v2/advisor/ask`
   - `/v2/advisor/advise`
   - `/v1/advisor/advise`（legacy compatibility）
2. **Channel / control ingress**
   - `/v2/advisor/webhook`

其中真正的主合同只有一句：

- **`/v3/agent/turn` = 当前公开 live ask 正门**

其余入口都不是同权的：

- `/v2/advisor/ask` = internal smart-execution lane
- `/v2/advisor/advise` = internal graph/controller + Feishu WS lane
- `/v1/advisor/advise` = retained legacy compatibility lane
- `/v2/advisor/webhook` = separate channel/control ingress，不是 ask front door

## 3. Ask ingress 分层

## 3.1 `/v3/agent/turn` = public live ask front door

这点继续冻结，不变。

[runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L714) 已经明确写死：

- 真实 live ask 应走 `/v3/agent/turn`
- 或 public MCP `advisor_agent_turn`
- 不应再直接 `POST /v1/jobs kind=chatgpt_web.ask`

对应 live caller 也已经收口：

- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3960)
  - `advisor_agent_turn`
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3992)
  - 实际 POST 到 `/v3/agent/turn`
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L718)
  - public MCP facade
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L788)
  - 实际 POST 到 `/v3/agent/turn`
- [cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py#L636)
  - CLI `agent turn`
- [cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py#L659)
  - 实际 POST 到 `/v3/agent/turn`

所以从现在开始，任何公开 live ask caller 默认都应对齐这里。

## 3.2 `/v3/agent/turn` 不是薄 facade

这点继续冻结，不变。

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1106)
到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1423)
已经证明，它当前自己承担：

- ask contract normalization
- strategy plan / clarify gate
- compiled prompt
- image / consult / gemini_research direct dispatch
- fallback 才进入 controller

所以 `/v3/agent/turn` 当前是：

- **public agent contract surface**
- **high-level ask ingress**
- **live dispatch layer**

## 3.3 `/v2/advisor/ask` = internal smart-execution ingress

这一条也继续冻结。

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1573)
已经明确它是：

- intelligent routing + execution in one call

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1683)
到 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1704)
也已经证明：

- 它创建 `ControllerEngine`
- 它把 `_ROUTE_TO_EXECUTION` 传进 `controller.ask(...)`

同时兼容工具仍然还活着：

- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1943)
  - `chatgptrest_advisor_ask`
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1988)
  - 实际 POST 到 `/v2/advisor/ask`

所以它的 contract 应冻结为：

- **internal smart-execution / compatibility ingress**

它是活跃入口，但不是公开 live ask 正门。

## 3.4 `/v2/advisor/advise` = internal graph/controller + Feishu WS ingress

这一条也继续冻结，但范围要收窄。

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L489)
把它定义成：

- `Run the advisor graph on a user message`

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L533)
到 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L548)
当前实际调用：

- `ControllerEngine.advise(...)`

而 Feishu WS 继续固定打这里：

- [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py#L49)
  - 默认 URL 指向 `/v2/advisor/advise`
- [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py#L304)
  - 业务消息实际 POST 到它
- [ops/systemd/chatgptrest-feishu-ws.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-feishu-ws.service#L11)
  - systemd unit 固定到这条 route
- [runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L658)
  - 运维文档同样固定到这条 route

所以准确口径必须写成：

- **`/v2/advisor/advise` = internal graph/controller ingress**
- **当前也承接 Feishu WS ingress**

不能再把 webhook 一并写进来。

## 3.5 `/v1/advisor/advise` = retained legacy compatibility ingress

这是 `v1` 漏掉的点，`v2` 明确补回。

它现在仍然是 live compatibility surface：

- [routes_advisor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L1232)
  - 仍定义 `POST /v1/advisor/advise`
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1895)
  - `chatgptrest_advisor_advise`
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1935)
  - 实际 POST 到 `/v1/advisor/advise`
- [cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py#L616)
  - `advisor advise`
- [cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py#L631)
  - 实际 POST 到 `/v1/advisor/advise`
- [antigravity_router_e2e.py](/vol1/1000/projects/ChatgptREST/ops/antigravity_router_e2e.py#L333)
  - ops/e2e flow 仍然还在用它

所以它不能从 ingress truth 里消失，但它的定位必须明确降级为：

- **legacy compatibility ingress**

它不是当前主三路的一部分，更不该影响新的公开 caller 设计。

## 4. Channel / Control ingress

## 4.1 `/v2/advisor/webhook` = separate webhook ingress

这也是 `v1` 写错的地方，`v2` 明确拆出来。

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L625)
明确存在：

- `POST /v2/advisor/webhook`

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L627)
到 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L633)
当前就是：

- 读取原始 body / JSON / headers
- 直接交给 `feishu.handle_webhook(...)`

所以 webhook 不能再被挂到 `/v2/advisor/advise`。

从现在开始，准确口径只能写：

- **Feishu WS ingress -> `/v2/advisor/advise`**
- **Feishu webhook ingress -> `/v2/advisor/webhook`**

这是两条不同的 channel ingress。

## 5. 正式 contract

## 5.1 Ask ingress contract

| Route | 定位 | 调用方 |
| --- | --- | --- |
| `/v3/agent/turn` | public live ask front door | OpenClaw、public MCP、CLI `agent turn`、coding agents、外部实时 ask |
| `/v2/advisor/ask` | internal smart-execution ingress | 内部/兼容工具、保留 route/provider/preset/job/controller 语义的调用方 |
| `/v2/advisor/advise` | internal graph/controller + Feishu WS ingress | Feishu WS、advisor-native controller path |
| `/v1/advisor/advise` | legacy compatibility ingress | legacy MCP、legacy CLI、ops/e2e residual |

## 5.2 Channel / control ingress contract

| Route | 定位 | 调用方 |
| --- | --- | --- |
| `/v2/advisor/webhook` | webhook/control ingress | Feishu webhook callbacks |

## 5.3 默认 caller 绑定

从现在开始，调用方 contract 应写成：

- OpenClaw live bridge -> `/v3/agent/turn`
- public MCP `advisor_agent_turn` -> `/v3/agent/turn`
- CLI `agent turn` -> `/v3/agent/turn`
- coding agents / external live ask -> `/v3/agent/turn`
- legacy MCP `chatgptrest_advisor_ask` -> `/v2/advisor/ask`
- Feishu WS -> `/v2/advisor/advise`
- Feishu webhook -> `/v2/advisor/webhook`
- legacy MCP `chatgptrest_advisor_advise` / legacy CLI `advisor advise` / ops residual -> `/v1/advisor/advise`

## 6. Freeze 与残留

## 6.1 现在就冻结的

1. `/v3/agent/turn` 是当前公开 live ask 正门
2. `/v2/advisor/ask` 是 internal smart-execution ingress
3. `/v2/advisor/advise` 是 internal graph/controller + Feishu WS ingress
4. `/v1/advisor/advise` 仍是 live legacy compatibility ingress
5. `/v2/advisor/webhook` 是 separate webhook ingress

## 6.2 现在明确保留的残留

下面这些问题这次不假装解决：

1. `/v3/agent/turn` 仍然内含自己的 live dispatch logic
2. `/v2/advisor/ask` 和 `/v3/agent/turn` 仍有 duplicated route mapping
3. Feishu WS 仍未迁到 `/v3/agent/turn`
4. `/v1/advisor/advise` 仍在 legacy MCP / CLI / ops 路径中存活

这些是后续收敛问题，不是本轮 contract freeze 的输出。

## 7. 从现在开始不能再说的话

后续文档里不能再写：

- “当前 front door 只有三路 live ingress”
- “`/v2/advisor/advise` 同时就是 webhook route”
- “`/v1/advisor/advise` 已经可以忽略不计”

这些说法都和当前代码实际不符。

## 8. 对后续计划的影响

基于 `v2`，后续顺序应当是：

1. `session_truth_decision_v1`
   - 先按新的 ask/channel split 做 ledger 对账
2. `telemetry_contract_fix_v1`
   - 因为 ask ingress 与 webhook/WS ingress 的 telemetry 也要分开看
3. 如要继续收敛 ingress，再单开设计：
   - `/v1/advisor/advise` 何时彻底降级或移除
   - Feishu WS 是否迁入 `/v3/agent/turn`
   - `/v2/advisor/ask` 是否最终只留 internal compat role

## 9. 最小结论

从 `v2` 开始，front door 不能再只写成主三路 ask split，也不能把 webhook 和 WS 混写。

准确口径是：

- **公开 live ask 正门：`/v3/agent/turn`**
- **internal ask lanes：`/v2/advisor/ask`、`/v2/advisor/advise`**
- **legacy compatibility ingress：`/v1/advisor/advise`**
- **separate channel/control ingress：`/v2/advisor/webhook`**

后续 planning 和 authority 文档必须建立在这个更完整的 ingress truth 之上。
