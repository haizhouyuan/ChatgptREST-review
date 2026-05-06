# 2026-03-20 Routing Authority Decision v1

## 1. 决策目标

这份文档承接：

- [2026-03-20_authority_matrix_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v2.md)

要解决的问题是：

- 当前系统里到底谁在决定“走哪条执行 lane”
- 谁在决定“选哪类 provider”
- 谁在决定“最终打哪个 API model chain”

如果这三层不拆开，后面所有 `front door`、`telemetry`、`runtime recovery` 都会继续把“路由”说成同一件事，最后谁都对不上。

## 2. 先说结论

当前 live runtime 的 routing authority 必须按 **三层** 理解，而不是继续幻想一个已经完全统一的单点：

1. **Ingress lane routing authority**
   - `/v2/advisor/ask` 的 `route -> provider/preset/kind` 映射
   - 当前由 `routes_advisor_v3._ROUTE_TO_EXECUTION` + `ControllerEngine.ask(route_mapping=...)` 决定
2. **Provider policy routing authority**
   - graph/report/cc runtime 里“应该优先尝试哪些 provider”
   - 当前由 `RoutingFabric` 决定
3. **Concrete API model execution authority**
   - 对 API lane，最终到底用哪串 model name 去发请求
   - 当前由 `LLMConnector._select_model()` 决定

这三层里，只有第二层和第三层勉强算“模型路由”；第一层其实是 **执行 lane 选择**，不能再混着叫。

## 3. 代码现实

## 3.1 `RoutingFabric` 确实是 live policy layer

[advisor/runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py) 当前 live advisor runtime 会：

- 初始化 `RoutingFabric.from_config(...)`
- 把 `routing_fabric` 回挂到 `LLMConnector`
- 把 `routing_fabric` 注入 `cc_native`

而 graph/report 也确实优先用它：

- [graph.py::_get_llm_fn](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py#L135)
  - `RoutingFabric` 先跑，空结果再回退到 API connector
- [report_graph.py::_get_llm](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/report_graph.py#L44)
  - 同样是 `RoutingFabric` 优先，API connector 次级回退
- [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py#L189)
  - 当前至少会把 execution outcome 回报给 `RoutingFabric`

所以当前文档里如果要写“live policy authority”，应该写 `RoutingFabric`，这点没有问题。

## 3.2 但 `RoutingFabric` 还不是 concrete execution source of truth

这一点是这次必须明确写透的。

[routing/fabric.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/routing/fabric.py) 的设计目标是 unified entry point，但它当前对 API provider 的真正执行逻辑是：

- [RoutingFabric._invoke_api](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/routing/fabric.py#L374)
  - 只要 provider type 是 `API/NATIVE_API`
  - 就把 prompt 再丢给 `_llm_connector(prompt, system_msg)`

也就是说：

- `RoutingFabric` 解析出来的 top candidate/provider id
- 并没有在 `_invoke_api()` 里被 provider-aware 地精确执行

这还不是唯一问题。

[routing/types.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/routing/types.py#L120) 的 `ResolvedRoute.api_only()` 当前会：

- 把所有 `API` 类型 candidate 的 `models` 直接平铺成一个 list

而 [llm_connector.py::_select_model](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/llm_connector.py#L291) 又会：

- 先用 `RoutingFabric.resolve(...).api_only()`
- 然后如果失败再静态 fallback

所以今天真实的 API 模型调用语义更像：

- `RoutingFabric` 提供一个 API candidates flatten 结果
- `LLMConnector` 再把它当成 model chain 去尝试

这不等于“RoutingFabric 已经直接决定了具体 API 执行”。

## 3.3 `ModelRouter` 和 `routing_engine` 现在都不是 live authority

这个结论现在已经足够硬。

[llm_connector.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/llm_connector.py#L88) 里 `model_router` 只是可选依赖。

但 [advisor/runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L281) 构造 live `LLMConnector` 时：

- 没有传 `model_router=...`

全仓 grep 也没看到当前 advisor runtime 注入 `ModelRouter` 的地方。

因此：

- `ModelRouter` 目前是 dormant path
- `routing_engine` 也是并行/历史代码，不是当前 live advisor runtime 的权威路径

以后除非把它们真正接入 runtime composition root，否则都不该再写成 live 共治 authority。

## 3.4 `/v2/advisor/ask` 还存在一层 ingress route mapping

这层非常容易和“模型路由”混淆，但它其实是另一件事。

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py) 当前有一张 `_ROUTE_TO_EXECUTION` 映射表，把：

- `quick_ask`
- `deep_research`
- `report`
- `funnel`

这些 route 映射成：

- `provider`
- `preset`
- `kind`

而 [ControllerEngine.ask](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L554) 又会：

- 根据 `route_mapping`
- 选出 execution lane
- 再去创建 job 或 dispatch execution

所以：

- `/v2/advisor/ask` 这一层还有自己的 **lane routing authority**
- 这不是 `RoutingFabric` 的替代，也不是 `LLMConnector` 的替代
- 它负责的是“选哪条外部执行 lane”，不是“选哪个 API model”

## 4. 决策

## 4.1 正式定义三个 authority

### A. Ingress Lane Routing Authority

当前 authority：

- `routes_advisor_v3._ROUTE_TO_EXECUTION`
- `ControllerEngine.ask(route_mapping=...)`

作用：

- 决定 `route -> provider/preset/kind`
- 决定是 job lane、team lane 还是别的 execution kind

边界：

- **它不是模型路由**
- 它只管入口态怎么把任务派进哪条执行 lane

### B. Provider Policy Routing Authority

当前 authority：

- `RoutingFabric`

作用：

- 根据 task profile / intent route / provider health
- 给 graph/report/cc runtime 输出 ranked providers

边界：

- 它是 provider policy authority
- 但还不是 concrete API execution authority

### C. Concrete API Model Execution Authority

当前 authority：

- `LLMConnector._select_model()`

作用：

- 对 API lane 最终生成 model chain
- 处理 `RoutingFabric api_only -> static fallback -> provider fallback`

边界：

- 它只覆盖 API execution
- 不覆盖 MCP web / CLI lane 的执行选择

## 4.2 正式降级的对象

### `ModelRouter`

从现在开始，正式降级为：

- **dormant implementation path**

原因：

- 当前 live advisor runtime 没有注入它

### `routing_engine`

从现在开始，正式降级为：

- **parallel / legacy routing experiment**

原因：

- 当前 live advisor runtime 不依赖它

## 4.3 现在不能再说的话

从这份文档起，后续所有计划和蓝图里都不能再写：

- “模型路由已经统一到 `RoutingFabric`”
- “`ModelRouter` 仍和 `RoutingFabric` 共治当前 runtime”
- “入口 route mapping 就是模型路由”

这些说法今天都不准确。

## 5. 最终口径

从现在开始，路由相关术语必须按下面区分：

### `lane routing`

指：

- 入口把任务派到哪条 execution lane

当前 owner：

- `/v2/advisor/ask` 的 `_ROUTE_TO_EXECUTION`
- `ControllerEngine.ask(...)`

### `provider routing`

指：

- 在 graph/report/cc runtime 里优先尝试哪些 provider

当前 owner：

- `RoutingFabric`

### `model execution routing`

指：

- 对 API lane 最终选哪串 model chain

当前 owner：

- `LLMConnector._select_model()`

## 6. 这份决策的真实含义

这份文档不是在说“当前路由设计很好”，恰恰相反。

它真正定下的是：

- 当前系统不是一个完全统一的 routing kernel
- 当前是一个 **分层路由系统**
- 如果后面要统一，就必须先承认今天到底分了哪几层

## 7. 下一步

基于这份决策，`Phase 0` 后续最合理的顺序是：

1. `front_door_contract_v1`
   - 先把三路入口分工写死
2. `session_truth_decision_v1`
   - 因为 public facade 和 front door 强绑定
3. `telemetry_contract_fix_v1`
   - 因为路由观测目前还不健康
4. 后面如果要实现统一 routing kernel，再开单独设计：
   - 让 `RoutingFabric` 变成真正 provider-aware execution authority
   - 或明确保持“policy vs execution”双层结构

## 8. 最小结论

当前 live runtime 的 routing authority 不是一个点，而是三层：

- 入口 lane routing：`_ROUTE_TO_EXECUTION + ControllerEngine`
- provider policy routing：`RoutingFabric`
- API model execution routing：`LLMConnector`

`ModelRouter` 和 `routing_engine` 当前都不是 live authority。

这才是现在可以继续往后规划的准确前提。
