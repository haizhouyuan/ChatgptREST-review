# 2026-03-20 Front Door Contract v1

## 1. 决策目标

这份文档承接：

- [2026-03-20_authority_matrix_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v2.md)
- [2026-03-20_routing_authority_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v2.md)

要解决的问题不是“系统里有哪些入口”，而是：

- 当前哪一条才是 **公开 live ask 正门**
- `/v3/agent/turn`、`/v2/advisor/advise`、`/v2/advisor/ask` 分别该服务谁
- 哪些 caller 以后不能再默认打旧入口

如果这个 contract 不冻结，后面所有 `session truth`、`telemetry`、`runtime recovery`、`planning/research scenario pack` 都会继续建立在不同入口各说各话的状态上。

## 2. 先说结论

从现在开始，front door 必须按下面三层理解：

1. **Public live ask front door**
   - `/v3/agent/turn`
   - 面向 OpenClaw、public MCP、CLI、coding agents、外部实时 ask
2. **Internal smart-execution front door**
   - `/v2/advisor/ask`
   - 面向内部/兼容调用方，需要 `route/provider/preset/job/controller` 语义时使用
3. **Internal graph/controller front door**
   - `/v2/advisor/advise`
   - 面向 Feishu WS、webhook、OpenMind graph/controller integration

这三者都还活着，但它们不是同权的。

**正式 contract：**

- 公开 live ask 正门只有一个：`/v3/agent/turn`
- `/v2/advisor/ask` 和 `/v2/advisor/advise` 继续保留，但都降级成内部/兼容 front door

## 3. 代码现实

## 3.1 `/v3/agent/turn` 是公开 live ask 正门

这不是偏好，而是代码和运维文档已经共同建立的事实。

[runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L714) 已经明确写死：

- 真实 live ask 应走 `/v3/agent/turn`
- 或 public MCP `advisor_agent_turn`
- 不应再直接 `POST /v1/jobs kind=chatgpt_web.ask`

MCP 侧也已经统一收口到这里：

- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3960)
  - `advisor_agent_turn`
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3992)
  - 实际 POST 到 `/v3/agent/turn`
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L718)
  - agent MCP facade 暴露同名高层工具
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L788)
  - 同样实际 POST 到 `/v3/agent/turn`
- [cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py#L659)
  - CLI 的 agent turn 子命令也打 `/v3/agent/turn`

所以在 caller contract 上，这一条已经足够清楚：

- **OpenClaw / MCP / CLI / coding-agent surface 的公开正门 = `/v3/agent/turn`**

## 3.2 `/v3/agent/turn` 不是薄 facade

这一点必须明写，否则后面很容易把它误降成“纯 facade”。

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1049)
当前在 `agent_turn` 里自己承担了几段 live ingress logic：

- ask contract synthesis
- strategy plan + clarify gate
- compiled prompt assembly
- goal-hint direct dispatch

尤其在 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1258) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1423) 之间，它直接做：

- `image -> gemini_web.generate_image`
- `consult/dual_review -> consultation fan-out`
- `gemini_research/deep_research -> gemini_web.ask`
- fallback 才进入 `ControllerEngine.ask(...)`

所以 `/v3/agent/turn` 当前不是“只包装 session continuity 的转发器”，而是：

- **public agent ingress + high-level dispatch + agent contract surface**

## 3.3 `/v2/advisor/ask` 仍是 live internal smart-execution entry

`/v2/advisor/ask` 没有废，但它的职责必须重新定位。

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1573)
对它的注释很清楚：

- intelligent routing + execution in one call
- route decision
- map route to provider/preset
- create ask job / controller execution

而 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1683) 到 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1704) 也表明：

- 它直接创建 `ControllerEngine`
- 把 `_ROUTE_TO_EXECUTION` 传进 `controller.ask(...)`

同时旧 MCP 兼容工具仍然打这里：

- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1943)
  - `chatgptrest_advisor_ask`
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1988)
  - 实际 POST 到 `/v2/advisor/ask`

所以 `/v2/advisor/ask` 的准确定位应当是：

- **internal smart-execution ingress**
- **兼容/内部工具入口**
- **保留 route/provider/preset/job/controller 语义的入口**

它不再是公开默认 front door，但仍然是活跃内部入口。

## 3.4 `/v2/advisor/advise` 仍是 live internal graph/controller entry

`/v2/advisor/advise` 也没有废，但它服务的是另一类路径。

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L489)
对它的定义是：

- `Run the advisor graph on a user message`

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L533) 到 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L548)
当前实际调用：

- `ControllerEngine.advise(...)`

也就是说，它更接近：

- graph/controller hot path
- advisor-native envelope
- trace / role / context / degradation aware entry

而 Feishu WS 现在仍绑定它：

- [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py#L41)
  - 默认 `ADVISOR_API_URL=http://127.0.0.1:18711/v2/advisor/advise`
- [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py#L304)
  - 业务消息直接 POST 到该 URL
- [ops/systemd/chatgptrest-feishu-ws.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-feishu-ws.service#L11)
  - systemd unit 也固定到了 `/v2/advisor/advise`
- [runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L658)
  - runbook 同样把 Feishu WS ingress 固定成 `/v2/advisor/advise`

所以 `/v2/advisor/advise` 的准确定位应当是：

- **internal graph/controller ingress**
- **Feishu WS / webhook / OpenMind-style controller path**

## 4. 正式 contract

## 4.1 三路入口的职责边界

### A. `/v3/agent/turn`

定位：

- public live ask front door

服务对象：

- OpenClaw live bridge
- public MCP `advisor_agent_turn`
- CLI `agent turn`
- coding agents / automation clients

应该承载：

- session continuity
- high-level goal-hint dispatch
- agent-shaped response
- public ask / review / research / image / consult

不应该再被描述成：

- 纯 facade
- 单纯转发到 `/v2/advisor/ask`

### B. `/v2/advisor/ask`

定位：

- internal smart-execution front door

服务对象：

- 兼容 MCP 工具
- 内部脚本 / ops / targeted integrations
- 需要直接拿 route/provider/preset/job/controller 语义的调用方

应该承载：

- route decision + execution in one call
- controller ask path
- 兼容已有 `_ROUTE_TO_EXECUTION` contract 的调用方

不应该再被视为：

- 公开默认 ask 正门

### C. `/v2/advisor/advise`

定位：

- internal graph/controller front door

服务对象：

- Feishu WS
- webhook-style advisor integrations
- OpenMind graph/controller native path

应该承载：

- advisor/controller graph hot path
- richer trace/context/degradation envelope
- channel-driven assistant flows

不应该再被当成：

- OpenClaw/public MCP 的主入口

## 4.2 调用方绑定 contract

从现在开始，调用方 contract 明确如下：

| Caller / Surface | 必须/默认目标 | 说明 |
| --- | --- | --- |
| OpenClaw live bridge | `/v3/agent/turn` | 公开 live ask 正门 |
| public MCP `advisor_agent_turn` | `/v3/agent/turn` | 高层 agent surface |
| CLI `agent turn` | `/v3/agent/turn` | 与 public agent surface 对齐 |
| coding agents / external live ask | `/v3/agent/turn` | 不再默认走 `/v2/*` |
| legacy MCP `chatgptrest_advisor_ask` | `/v2/advisor/ask` | 兼容路径，后续可再收敛 |
| Feishu WS gateway | `/v2/advisor/advise` | 当前已固定，不在本决策里强行改线 |
| webhook / advisor-native integrations | `/v2/advisor/advise` | controller/graph native path |

## 4.3 明确禁止的默认用法

从现在开始，后续文档和新调用方不能再默认做这些事：

- 把真实 live ask 默认打到 `/v2/advisor/ask`
- 把 OpenClaw / public MCP / coding-agent 正门写成 `/v2/advisor/advise`
- 把 `/v3/agent/turn` 描述成只是 facade
- 把 `POST /v1/jobs kind=chatgpt_web.ask` 当成正常 live ask 路径

## 5. Freeze 与残留

## 5.1 现在就冻结的

1. **公开正门只有一个：`/v3/agent/turn`**
2. `/v2/advisor/ask` 是 internal smart-execution ingress
3. `/v2/advisor/advise` 是 internal graph/controller ingress
4. Feishu WS 当前继续绑定 `/v2/advisor/advise`
5. public MCP / OpenClaw / CLI 当前都应对齐 `/v3/agent/turn`

## 5.2 现在明确保留的残留

下面这些问题这次不假装解决：

1. `/v3/agent/turn` 仍然内含自己的 live dispatch logic
2. `/v2/advisor/ask` 和 `/v3/agent/turn` 仍然存在 duplicated route mapping
3. Feishu WS 仍未迁到 `/v3/agent/turn`
4. `/v2/advisor/ask` 与 `/v2/advisor/advise` 仍并存，没有彻底统一成一个 internal entry

这些都属于后续设计/实现问题，不是这次 contract freeze 能消掉的。

## 6. 对后续计划的影响

基于这份 contract，后续顺序应该是：

1. `session_truth_decision_v1`
   - 因为 `/v3/agent/turn` 的 public facade 和 session ledger 强绑定
2. `telemetry_contract_fix_v1`
   - 因为现在三路 front door 的 telemetry 没有统一收口
3. 如要继续统一 ingress，再单开设计：
   - `/v3/agent/turn` 是否继续持有高层 dispatch
   - Feishu 是否迁入 `/v3/agent/turn`
   - `/v2/advisor/ask` 是否最终变成纯 internal lane

## 7. 最小结论

从现在开始，front door 不能再写成“多个差不多的入口”。

准确口径只有这一句：

- **`/v3/agent/turn` = 公开 live ask 正门**
- **`/v2/advisor/ask` = internal smart-execution 兼容入口**
- **`/v2/advisor/advise` = internal graph/controller / Feishu 入口**

后续 planning 必须建立在这个分工上，而不是再把三者混成“advisor front door”的同义词。
