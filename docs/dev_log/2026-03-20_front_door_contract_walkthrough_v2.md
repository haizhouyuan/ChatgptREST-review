# 2026-03-20 Front Door Contract Walkthrough v2

## 1. 任务目标

把 Claude 的核验结果正式吸收到新的 front-door 决策文档里，生成：

- [2026-03-20_front_door_contract_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_v2.md)

这次不是推翻 `v1` 的主判断，而是把遗漏和混写补齐。

## 2. 这次重点修正什么

我围绕 3 个点修正：

1. 把仍然存活的 `/v1/advisor/advise` 明确补回 ingress truth
2. 把 Feishu webhook 从 `/v2/advisor/advise` 里拆出去
3. 把 front door 结构改成：
   - ask ingress
   - channel/control ingress

## 3. 这次新增核对的关键证据

- [routes_advisor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L1232)
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1895)
- [cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py#L616)
- [antigravity_router_e2e.py](/vol1/1000/projects/ChatgptREST/ops/antigravity_router_e2e.py#L333)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L625)
- [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py#L49)

## 4. 关键修正

### 4.1 `/v1/advisor/advise` 不再被漏掉

`v1` 的问题不是主结论错，而是把 ingress inventory 写得太干净了。

这次把 `/v1/advisor/advise` 明确补回来了，而且直接降级为：

- legacy compatibility ingress

这样后续文档既不会错漏，也不会误把它重新扶正。

### 4.2 webhook 和 WS 正式拆开

这次最重要的概念修正是：

- Feishu WS -> `/v2/advisor/advise`
- Feishu webhook -> `/v2/advisor/webhook`

`v1` 把两者混写进 `/v2/advisor/advise`，这会直接污染后续 `session_truth` 和 `telemetry`。

### 4.3 front door 改成两类 ingress

`v2` 不再把所有入口都写成同一种 front door，而是拆成：

1. ask ingress
2. channel/control ingress

这样结构更贴近代码实际，也更利于下一步继续做 ledger 和 telemetry 对账。

## 5. 最终收下来的 contract

从 `v2` 开始，front door 的正式口径是：

### Ask ingress

- `/v3/agent/turn`
- `/v2/advisor/ask`
- `/v2/advisor/advise`
- `/v1/advisor/advise`

### Channel / control ingress

- `/v2/advisor/webhook`

其中主次关系仍然不变：

- `/v3/agent/turn` 是公开 live ask 正门
- `/v2/*` 是 internal lanes
- `/v1/advisor/advise` 是 legacy compatibility

## 6. 为什么这版比 v1 更适合作为下一步输入

因为下一步是：

- `session_truth_decision_v1`

如果还拿 `v1` 当基础，会继续带入两个错误前提：

- 忽略 `/v1/advisor/advise` 这个仍然活着的 legacy ingress
- 把 webhook 和 WS 混成同一路 front door

`v2` 先把这两个坑补平了。

## 7. 产物

本轮新增：

- [2026-03-20_front_door_contract_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_v2.md)
- [2026-03-20_front_door_contract_walkthrough_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_contract_walkthrough_v2.md)

## 8. 测试说明

这次仍然是文档和代码证据校正任务，没有改代码，也没有跑测试。
