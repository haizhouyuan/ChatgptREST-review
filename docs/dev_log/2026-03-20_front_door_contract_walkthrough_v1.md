# 2026-03-20 Front Door Contract Walkthrough v1

## 1. 任务目标

完成 `Phase 0` 的下一份正式决策文档：

- [2026-03-20_front_door_contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_v1.md)

这份文档的目标不是再做盘点，而是把三路入口的 caller contract 写死。

## 2. 这次重点核对的问题

我围绕 5 个问题收证据：

1. 当前公开 live ask 正门到底是不是 `/v3/agent/turn`
2. `/v3/agent/turn` 是不是已经自己承担高层 dispatch，而不是薄 facade
3. `/v2/advisor/ask` 当前真实服务的是哪类 caller
4. `/v2/advisor/advise` 当前真实服务的是哪类 caller
5. Feishu WS 现在为什么仍然绑定 `/v2/advisor/advise`

## 3. 这次读取的关键对象

- [runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L714)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1049)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1258)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L489)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1573)
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3960)
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1943)
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L718)
- [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py#L41)
- [ops/systemd/chatgptrest-feishu-ws.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-feishu-ws.service#L11)

## 4. 最关键的判断

### 4.1 `/v3/agent/turn` 被正式收为公开正门

这次把一个经常口头说、但文档里容易被冲淡的事实写硬了：

- runbook 已经明确要求真实 live ask 走 `/v3/agent/turn`
- public MCP `advisor_agent_turn` 也已经打这里
- CLI agent turn 也已经打这里

所以从 caller contract 角度，它就是当前公开 live ask 正门。

### 4.2 `/v3/agent/turn` 不是薄转发

这次没有把它写成“public facade only”。

代码非常清楚，它自己就承担：

- ask contract
- strategy / clarify gate
- compiled prompt
- image / consult / gemini_research 的 direct dispatch

所以后面任何文档如果再把它写成“只是 facade”，都会再次误导设计。

### 4.3 `/v2/advisor/ask` 与 `/v2/advisor/advise` 被拆成两类 internal entry

这次把两个 `/v2` 入口的角色拆开了：

- `/v2/advisor/ask`
  - internal smart-execution ingress
  - 兼容 route/provider/preset/job/controller 语义
- `/v2/advisor/advise`
  - internal graph/controller ingress
  - 更贴近 controller/advisor-native path

这样后面写 `session_truth` 和 `telemetry` 时，才不会把两个 `/v2` 入口又混在一起。

### 4.4 Feishu 这次不强行改线，只明写现状

Feishu WS 当前的默认 URL、systemd unit、runbook 全部仍指向 `/v2/advisor/advise`。

这次 contract 冻结不假装它已经收进 `/v3/agent/turn`，而是把它明确记为：

- current internal Feishu ingress contract

这样后面如果真要迁移，变更范围才可控。

## 5. 最终收下来的 contract

从 `v1` 开始，front door 的固定口径是：

1. `/v3/agent/turn`
   - public live ask front door
2. `/v2/advisor/ask`
   - internal smart-execution front door
3. `/v2/advisor/advise`
   - internal graph/controller / Feishu front door

## 6. 为什么这份文档现在必须先写

因为如果 front door contract 不先冻结，后面两份文档都会继续漂：

- `session_truth_decision_v1`
- `telemetry_contract_fix_v1`

它们都依赖先搞清楚“不同 caller 到底应该从哪一扇门进”。

## 7. 产物

本轮新增：

- [2026-03-20_front_door_contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_v1.md)
- [2026-03-20_front_door_contract_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_walkthrough_v1.md)

## 8. 测试说明

这次仍然是文档决策任务，没有改代码，也没有跑测试。
