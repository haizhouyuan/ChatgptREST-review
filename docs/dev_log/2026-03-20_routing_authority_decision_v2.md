# 2026-03-20 Routing Authority Decision v2

## 1. 为什么需要 v2

[2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md)
已经把两个关键误区纠正了：

- `RoutingFabric` 不是当前 concrete API execution truth
- `ModelRouter` / `routing_engine` 不是当前 live advisor runtime authority

但 Claude 的复核证明，`v1` 仍然把最上层的 ingress/lane authority 压得过窄了。

这份 `v2` 建立在下面两份文档之上：

- [2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md)
- [2026-03-20_routing_authority_decision_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_verification_v1.md)

`v2` 的目标不是推翻 `v1`，而是把 routing authority 补回代码真实结构：

1. `/v3/agent/turn` 本身就是 live front-door dispatch authority
2. controller lane routing 不只是 `route_mapping`
3. `route_mapping` 现在还有两份活跃拷贝
4. `RoutingFabric` 的 live consumer 目前只应保守写到 `graph/report`

## 2. 先说结论

当前 live runtime 的 routing authority，仍然应该按三层理解，但 **Layer A 必须展开**：

1. **Ingress and lane routing authority**
   - public front door dispatch
   - controller route planning
   - controller execution-kind selection
   - route-to-provider/preset/kind mapping
2. **Provider policy routing authority**
   - 当前由 `RoutingFabric` 承担
   - 已被代码明确验证的 live consumer 是 `graph/report`
3. **Concrete API model execution authority**
   - 当前由 `LLMConnector._select_model()` 承担

所以今天系统不是“一个统一 routing kernel”，而是：

- 上层 lane routing 仍是多段 authority
- 中层 provider policy 由 `RoutingFabric` 承担
- 下层 API model execution 由 `LLMConnector` 执行

## 3. Layer A: Ingress and Lane Routing Authority

`v1` 最大的问题，是把这一层压成了：

- `/v2/advisor/ask`
- `_ROUTE_TO_EXECUTION`
- `ControllerEngine.ask(route_mapping=...)`

这不符合当前 live code reality。

### 3.1 Public front door dispatch authority

当前公开 live ask 正门不是 `/v2/advisor/ask`，而是：

- `/v3/agent/turn`
- public MCP tool `advisor_agent_turn`

这点在 [runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L714) 已经写死：

- 真实 live ask 应走 `/v3/agent/turn`
- 不应走直接低层 `POST /v1/jobs kind=chatgpt_web.ask`

更关键的是，`/v3/agent/turn` 不是薄转发，而是已经自己做 live dispatch：

- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1258)
  - `goal_hint=image` 直接进 `gemini_web.generate_image`
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1310)
  - `consult` / `dual_review` 直接进 consultation fan-out
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1362)
  - `gemini_research` / `gemini_deep_research` 直接进 `gemini_web.ask`
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1423)
  - 只有 fallback branch 才进入 `ControllerEngine.ask(...)`

所以 Layer A 第一条必须明确写成：

- **public ingress dispatch authority = `/v3/agent/turn`**

它已经在决定“是不是直接走 image / consult / gemini_research lane”，不是单纯把请求交给 controller。

### 3.2 Controller route-planning authority

当请求进入 controller path 后，第一段 live authority 不是 `route_mapping`，而是：

- [ControllerEngine._plan_async_route](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1677)

[ControllerEngine.ask](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L281)
当前明确先调用 `_plan_async_route()`，这一步会执行：

- `normalize`
- `kb_probe`
- `analyze_intent`
- `route_decision`

并产出：

- `route`
- `executor_lane`
- `kb_used`
- `kb_hit_count`
- `rationale`

所以 controller path 里真正最上游的 lane/route authority，是：

- **graph-based route planning authority = `ControllerEngine._plan_async_route()`**

### 3.3 Controller execution-kind authority

在 route plan 之后，controller 还有第二段独立 authority：

- [ControllerEngine._resolve_execution_kind](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L817)

这一步决定：

- `effect`
- `team`
- `job`

它的依据不只是 `route`，还包括：

- `stable_context.team`
- `stable_context.topology_id`
- `cc_native` 是否存在
- `executor_lane == "team"`

所以 Layer A 不能只写“lane routing”，还必须显式包含：

- **execution-kind authority = `ControllerEngine._resolve_execution_kind()`**

否则会把 `team/effect/job` 的分流误写成 `_ROUTE_TO_EXECUTION` 的职责。

### 3.4 Route-to-provider/preset/kind mapping authority

只有在上述两步之后，controller path 才真正落到：

- [ControllerEngine.ask](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L554)
  - `exec_config = dict(route_mapping.get(route, ...))`

这一步的职责只是：

- 把已经选好的 `route`
- 转成 `provider/preset/kind`

这里 `v1` 说得不够准确的地方是：它把这一层写成了单一 authority。

当前代码里其实有 **双份活跃 mapping**：

- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L43)
  - module-level `_ROUTE_TO_EXECUTION`
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1424)
  - `/v3/agent/turn` fallback branch 内联了一份 `route_mapping`

所以今天准确写法应该是：

- **route-to-execution mapping authority = duplicated between `routes_advisor_v3._ROUTE_TO_EXECUTION` and `routes_agent_v3` inline `route_mapping`**

这不是 freeze 结果，而是 **已确认的 unresolved duplication**。

### 3.5 Layer A 的正式口径

从现在开始，Layer A 不得再压成单行。

当前真实结构应写成：

1. **public ingress dispatch**
   - `/v3/agent/turn`
2. **controller route planning**
   - `ControllerEngine._plan_async_route()`
3. **controller execution-kind selection**
   - `ControllerEngine._resolve_execution_kind()`
4. **route-to-provider/preset/kind mapping**
   - `routes_advisor_v3._ROUTE_TO_EXECUTION`
   - `routes_agent_v3` inline `route_mapping`

## 4. Layer B: Provider Policy Routing Authority

这一层 `v1` 的主方向是对的，但 consumer 范围写大了。

### 4.1 当前 live authority

当前 provider policy routing authority 仍然是：

- `RoutingFabric`

证据链继续成立：

- [advisor/runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L417)
  - live runtime 初始化 `RoutingFabric`
- [advisor/runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L422)
  - 回挂到 `LLMConnector`
- [graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py#L148)
  - graph 优先用 `routing_fabric.get_llm_fn(...)`
- [report_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/report_graph.py#L62)
  - report 同样优先走 `RoutingFabric`

### 4.2 当前被验证的 live consumers

这次必须收紧表述。

当前代码明确支持的 live consumer 是：

- `advisor graph`
- `report graph`

而 `cc_native` 当前仅能确认：

- [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py#L167)
  - 持有 `routing_fabric`
- [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py#L187)
  - 把 execution outcome 回报给 `RoutingFabric`

但目前没有足够代码证据证明：

- `cc_native` 用 `RoutingFabric.resolve(...)`
- 或 `get_llm_fn(...)`
- 来做 provider selection

所以从现在开始，准确口径只能写：

- **`RoutingFabric` 是 graph/report 的 live provider-policy authority**
- **`cc_native` 目前是 routing outcome feedback producer，不足以证明它是 provider-policy consumer**

## 5. Layer C: Concrete API Model Execution Authority

这一层 `v1` 继续成立。

当前 concrete API model execution authority 仍然是：

- `LLMConnector._select_model()`

原因不变：

- [llm_connector.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/llm_connector.py#L304)
  - `RoutingFabric.resolve(...).api_only()` 产出 API candidates
- 然后 `LLMConnector` 自己再做：
  - route-derived API model chain
  - static route map fallback
  - provider fallback

所以今天真正的 concrete API execution truth 依然不是 `RoutingFabric`。

## 6. 降级对象

### 6.1 `ModelRouter`

继续正式降级为：

- **dormant implementation path**

因为：

- [advisor/runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L281)
  - live `LLMConnector` 初始化时没有注入 `model_router`

### 6.2 `routing_engine`

继续正式降级为：

- **parallel / legacy routing experiment**

因为当前 live advisor runtime composition root 不依赖它。

## 7. v2 Freeze Decisions

### 7.1 现在可以冻结的

1. `RoutingFabric` 不是 concrete API execution truth
2. `LLMConnector._select_model()` 是当前 concrete API model execution authority
3. `ModelRouter` / `routing_engine` 不是当前 live runtime authority
4. `/v3/agent/turn` 必须被视为 live ingress dispatch authority
5. controller path 内部至少有三段活跃 authority：
   - `_plan_async_route()`
   - `_resolve_execution_kind()`
   - `route_mapping -> provider/preset/kind`

### 7.2 现在必须明写 unresolved 的

1. Layer A 还没有单一 source of truth
2. `route_mapping` 当前存在双份活跃定义：
   - `routes_advisor_v3._ROUTE_TO_EXECUTION`
   - `routes_agent_v3` inline `route_mapping`
3. `RoutingFabric` 对 `cc runtime` 的作用当前只证到 feedback，不应过度延伸成 provider selector

## 8. 从现在开始不能再说的话

后续文档里不能再写：

- “当前 lane routing 主要就是 `/v2/advisor/ask + _ROUTE_TO_EXECUTION`”
- “Layer A 已经有单一 authority”
- “`RoutingFabric` 已经是 graph/report/cc runtime 的统一 provider selector”
- “`/v3/agent/turn` 只是薄 facade”

这些说法都和当前 live code reality 不符。

## 9. 下一步

基于 `v2`，后续顺序应当是：

1. `front_door_contract_v1`
   - 先把 `/v3/agent/turn`、`/v2/advisor/advise`、`/v2/advisor/ask` 的职责边界写死
2. `session_truth_decision_v1`
   - 因为 public facade 和 front door 强绑定
3. `telemetry_contract_fix_v1`
   - 因为 front door split 和 routing observability 绑在一起
4. 后面如果要统一 routing kernel，再单开设计：
   - 收敛 Layer A duplication
   - 明确 `RoutingFabric` 和 execution authority 的长期关系

## 10. 最小结论

当前 live runtime 的 routing authority 仍然是三层，但 Layer A 必须展开：

- **Layer A: ingress and lane routing**
  - `/v3/agent/turn`
  - `ControllerEngine._plan_async_route()`
  - `ControllerEngine._resolve_execution_kind()`
  - duplicated `route_mapping`
- **Layer B: provider policy**
  - `RoutingFabric`
  - verified live consumers: `graph/report`
- **Layer C: concrete API execution**
  - `LLMConnector._select_model()`

`routing_authority_decision_v1` 可以保留为中间修正版，但从 `v2` 开始，后续 planning 必须建立在这份更完整的结构上。
