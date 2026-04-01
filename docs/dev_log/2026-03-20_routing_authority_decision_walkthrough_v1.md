# 2026-03-20 Routing Authority Decision Walkthrough v1

## 1. 任务目标

完成 `Phase 0` 的下一份正式决策文档：

- [2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md)

目标是把“路由”拆开，不再把：

- lane 选择
- provider 选择
- API model chain 选择

混成同一个词。

## 2. 这次怎么收判断

这次没有继续做泛盘点，只围绕 5 个问题收证据：

1. `RoutingFabric` 在 live runtime 里到底有没有被真正初始化
2. graph/report/cc 到底是不是优先调用它
3. `LLMConnector` 到底是不是当前 API model chain 的真实执行层
4. `ModelRouter` 有没有被接进 live advisor runtime
5. `/v2/advisor/ask` 这一层自己是不是还在做 route-to-lane mapping

## 3. 重点读取对象

- [routing/fabric.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/routing/fabric.py)
- [routing/types.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/routing/types.py)
- [llm_connector.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/llm_connector.py)
- [advisor/runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py)
- [advisor/graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)
- [advisor/report_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/report_graph.py)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)
- [controller/engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py)
- [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py)

## 4. 关键发现

### 4.1 `RoutingFabric` 是 live policy layer，不是假想层

`advisor/runtime.py` 当前确实会初始化 `RoutingFabric`，并把它挂回：

- graph
- report
- cc runtime
- LLMConnector

所以它不是 dead code。

### 4.2 但 `RoutingFabric` 还不是 concrete API execution truth

这是这次最重要的细节。

`RoutingFabric` 在 `_invoke_api()` 里并没有 provider-aware 地真正执行“某个具体 API provider”，而是把请求再交给 `LLMConnector`。

同时 `LLMConnector._select_model()` 又会用 `route.api_only()` 拿一串 API models。

所以今天真实情况不是：

- `RoutingFabric` 直接决定了 concrete model

而是：

- `RoutingFabric` 提供 provider policy / API candidates
- `LLMConnector` 再把它变成实际 model chain

### 4.3 `ModelRouter` 现在不是 live authority

这次把这个点钉实了：

- `model_router` 在 `LLMConnector` 里只是 optional
- live advisor runtime 构造 connector 时没有注入它

所以它当前只能算 dormant path。

### 4.4 `/v2/advisor/ask` 还有一层入口态 lane routing

`routes_advisor_v3._ROUTE_TO_EXECUTION` + `ControllerEngine.ask(route_mapping=...)` 这一层仍在实际运行。

它的作用不是 model routing，而是：

- 决定 route 用哪个 provider/preset/kind 组合
- 决定进哪条 execution lane

这是单独的一层 authority，不能继续和模型路由混写。

## 5. 这次最终定下来的口径

从现在开始，routing 相关口径必须分三层：

1. `lane routing`
2. `provider routing`
3. `model execution routing`

对应 owner 分别是：

1. `_ROUTE_TO_EXECUTION + ControllerEngine`
2. `RoutingFabric`
3. `LLMConnector._select_model()`

## 6. 为什么这个决定重要

因为如果不先把这三层拆开，后续几份文档都会继续带错：

- `front_door_contract_v1`
- `telemetry_contract_fix_v1`
- 以后真正想做统一 routing kernel 的设计

## 7. 产物

本轮新增：

- [2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md)
- [2026-03-20_routing_authority_decision_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_walkthrough_v1.md)

## 8. 测试与残留

这次仍然是文档决策任务，没有代码改动，也没有跑测试。

目前还没解决的不是“文档说不清”，而是代码结构本身还没统一：

- `RoutingFabric` 还不是 provider-aware concrete execution layer
- `/v2/advisor/ask` 入口层还保留 route-to-lane mapping

这些已经被转成后续设计输入，不再是模糊问题。
