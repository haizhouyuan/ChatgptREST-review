# 2026-03-20 Authority Matrix Walkthrough v2

## 1. 任务目标

在 [2026-03-20_authority_matrix_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_verification_v1.md) 基础上，把 `authority_matrix` 升到一版可以继续支撑下游决策的粒度。

新增产物：

- [2026-03-20_authority_matrix_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v2.md)

## 2. 这次修了什么

这次没有重做全部盘点，只修 4 个被核验明确打穿的 high-risk row：

1. 前门 split
2. EvoMap 双库
3. 模型路由的 live wiring
4. session truth 的账本数

## 3. 新补的关键证据

### 3.1 `/v2/advisor/ask`

直接复核到：

- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1573) 定义了 `POST /v2/advisor/ask`
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1942) 的 `chatgptrest_advisor_ask` 工具实际发到这个入口

所以不能继续把 v2 前门写成只有 `/advise`。

### 3.2 EvoMap signals DB

直接复核到：

- [evomap/paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/paths.py#L9) 默认把 observer runtime state 指向 `~/.openmind/evomap/signals.db`
- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L278) 用它初始化 `EvoMapObserver`
- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L366) 又单独初始化 repo-local knowledge DB

所以 EvoMap 在 runtime 里至少是双库，不是单库。

### 3.3 ModelRouter 没有接进 live advisor runtime

直接复核到：

- [llm_connector.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/llm_connector.py#L88) 的 `model_router` 是可选依赖
- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L281) 构造 live `LLMConnector` 时没有注入 `model_router`
- grep 全仓也没找到当前 advisor runtime 注入 `ModelRouter` 的地方

所以 v1 那句“RoutingFabric + ModelRouter + static fallback”对 live runtime 来说写重了。

### 3.4 `state/agent_sessions`

直接复核到：

- [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L19) 在有 `CHATGPTREST_DB_PATH` 时会把 facade sessions 落到 `state/agent_sessions`
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968) 初始化 store
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L992) 实际写 session
- 当前目录里确实有 `3` 套 `.json + .events.jsonl`

所以 session truth 至少三账本，这一点必须进主矩阵。

## 4. 为什么这次还要同步拉 `knowledge_authority_decision_v2`

因为 `knowledge_authority_decision_v1` 虽然大方向没错，但它把 `EvoMap` 继续写成了单一 canonical plane，没有把 `signals DB` 说清楚。

这不会推翻 split-plane 结论，但会影响：

- telemetry plane
- observer runtime
- team scorecard / team policy 这类 secondary state 的理解

所以 authority matrix 升到 v2 后，knowledge decision 也应该跟着升一版。

## 5. 产物

本轮新增：

- [2026-03-20_authority_matrix_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v2.md)
- [2026-03-20_authority_matrix_walkthrough_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_walkthrough_v2.md)

## 6. 测试与残留

这次仍是文档修订任务，没有代码改动，也没有跑测试。

当前还没被文档修订直接解决的残留是：

- `front door` 三路入口还没有 contract 决策
- `session truth` 三账本还没有收敛决策
- `telemetry` 仍然坏着
