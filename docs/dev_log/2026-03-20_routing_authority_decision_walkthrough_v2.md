# 2026-03-20 Routing Authority Decision Walkthrough v2

## 1. 任务目标

把 Claude 的核验意见正式吸收到新的 routing 决策文档里，生成：

- [2026-03-20_routing_authority_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v2.md)

这次不是推翻 `v1`，而是修正它对 Layer A 的过度压缩。

## 2. 这次重点复核什么

我围绕 4 个问题补证据：

1. `/v3/agent/turn` 到底是不是 live routing layer，而不是薄 facade
2. controller path 里除了 `route_mapping` 还有哪些活跃 routing authority
3. `route_mapping` 现在是不是确实有双份活跃定义
4. `RoutingFabric` 对 `cc runtime` 到底证到了什么程度

## 3. 这次新增读取的关键代码

- [docs/runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L714)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1258)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1310)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1362)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1423)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L43)
- [ControllerEngine.ask](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L281)
- [ControllerEngine._resolve_execution_kind](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L817)
- [ControllerEngine._plan_async_route](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1677)
- [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py#L187)

## 4. 关键修正

### 4.1 Layer A 不再围着 `/v2/advisor/ask` 写

`v1` 最大的问题是把 ingress/lane authority 近似写成：

- `/v2/advisor/ask`
- `_ROUTE_TO_EXECUTION`
- `ControllerEngine.ask(route_mapping=...)`

这会漏掉当前最重要的公开入口：

- `/v3/agent/turn`

而且 `/v3/agent/turn` 不是薄壳，它会直接分流：

- image
- consultation
- gemini research
- 然后才把剩余流量丢给 controller

所以 `v2` 把 `/v3/agent/turn` 提升成 Layer A 的第一段 authority。

### 4.2 controller path 拆成三段 authority

这次把 controller path 明确拆成：

1. `_plan_async_route()`
2. `_resolve_execution_kind()`
3. `route_mapping -> provider/preset/kind`

这样后续 `front_door_contract_v1` 才不会把 controller path 写成“只要传 route_mapping 就够了”。

### 4.3 duplicated route mapping 明确标成 unresolved

这次不再把 `_ROUTE_TO_EXECUTION` 写成唯一 mapping truth。

当前至少有两份活跃 mapping：

- `routes_advisor_v3._ROUTE_TO_EXECUTION`
- `routes_agent_v3` fallback branch 内联 `route_mapping`

`v2` 把这点明写成 authority duplication，而不是继续美化成单一 source。

### 4.4 `cc_native` 的表述收紧

这次没有再把 `cc runtime` 直接写成 `RoutingFabric` 的 verified provider-policy consumer。

代码当前只明确证明：

- `cc_native` 会向 `RoutingFabric` 回报 execution outcome

但没证明：

- `cc_native` 用 `RoutingFabric` 做 provider selection

所以 `v2` 把表述收紧成：

- verified live consumers = `graph/report`
- `cc_native` = feedback producer

## 5. 最终收下来的口径

`routing_authority_decision_v2` 现在把 routing 讲成三层，但最上层不再压扁：

1. **ingress and lane routing**
   - `/v3/agent/turn`
   - `_plan_async_route()`
   - `_resolve_execution_kind()`
   - duplicated `route_mapping`
2. **provider policy routing**
   - `RoutingFabric`
3. **concrete API model execution**
   - `LLMConnector._select_model()`

## 6. 为什么这版比 v1 更适合作为后续输入

因为下一步要写的是：

- `front_door_contract_v1`

如果继续拿 `v1` 当基础，会自动带入 3 个错误前提：

- 把 `/v2/advisor/ask` 当成主要 lane surface
- 忽略 `/v3/agent/turn` 已经有 live dispatch
- 忽略 duplicated `route_mapping`

`v2` 把这些坑先填掉了。

## 7. 产物

本轮新增：

- [2026-03-20_routing_authority_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v2.md)
- [2026-03-20_routing_authority_decision_walkthrough_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_walkthrough_v2.md)

## 8. 测试说明

这次仍然是文档和代码证据校正任务，没有改代码，也没有跑测试。
