# Phase 3: Planning Scenario Pack v1

## 目标

把 `planning` 从抽象 scenario 收成稳定的 slow-path pack，使其在以下层面有固定语义：

- intake
- clarify
- route
- prompt assembly
- acceptance
- watch policy

本版只收 `planning`，不扩到 `research`。

## 冻结对象

新增模块：

- [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py)

核心对象：

- `ScenarioPack`
  - `scenario`
  - `profile`
  - `intent_top`
  - `route_hint`
  - `output_shape`
  - `execution_preference`
  - `prompt_template_override`
  - `acceptance`
  - `evidence_required`
  - `clarify_questions`
  - `review_rubric`
  - `watch_policy`

## 固定 deliverable profiles

本版冻结 5 个 planning profiles：

1. `implementation_plan`
2. `business_planning`
3. `workforce_planning`
4. `meeting_summary`
5. `interview_notes`

其中：

- `implementation_plan / business_planning / workforce_planning`
  - `intent_top=BUILD_FEATURE`
  - `route_hint=funnel`
  - `execution_preference=job`
  - `output_shape=planning_memo`
- `meeting_summary / interview_notes`
  - `intent_top=WRITE_REPORT`
  - `route_hint=report`
  - `execution_preference=job`
  - `output_shape=meeting_summary`

## 触发规则

`ScenarioPack` 不再只依赖 caller 显式传 `scenario=planning`。

当前允许两类触发：

1. 显式 planning
   - `task_intake.scenario=planning`
   - 或 OpenClaw `/v3/agent/turn` 带 `goal_hint=planning|implementation_planning`
2. 窄语义检测
   - 会议纪要/会议总结
   - 面试/访谈/调查纪要
   - 人力规划/headcount/staffing/hiring
   - 业务规划/business plan
   - 实施规划/rollout/migration/上线/技术规划

但 pack 不会覆盖这些已明确的非 planning scenario：

- `report`
- `research`
- `code_review`
- `image`
- `repair`

也就是说：

- `“业务规划备忘录” + goal_hint=report` 仍是 `report`
- `“人力规划方案” + 无显式 route` 会进入 `planning`

## 代码接入点

### Ingress

- [/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)

两条入口现在都会：

1. build canonical `task_intake`
2. resolve/apply `scenario_pack`
3. 将 `task_intake` 与 `scenario_pack` 写入 context / stable_context
4. 将 `task_intake` 与 `scenario_pack` summary 写入 `request_metadata`

### Strategist

- [/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py)

planning pack 现在能驱动：

- `route_hint`
- `output_contract.required_sections`
- `evidence_requirements`
- `review_rubric`
- `clarify_questions`
- `prompt_template_override`

### Prompt Builder

- [/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/prompt_builder.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/prompt_builder.py)

当 `ScenarioPack` 提供 `prompt_template_override` 时：

- `meeting_summary / interview_notes` 走 `report_generation` prompt template
- 其它 planning profiles 继续走 `implementation_planning`

同时会把 `Scenario Pack` block 注入 compiled prompt。

### Controller

- [/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py)

controller 现在对 planning pack 有两个固定动作：

1. `_plan_async_route(...)` 吃 `scenario_pack`
   - graph state 带入 `task_intake` / `scenario_pack`
   - route decision 后允许 `ScenarioPack` 窄覆盖 route
2. `_resolve_execution_kind(...)` 尊重 `execution_preference`
   - planning pack 当前一律固定成 `job`
   - 避免 `funnel` 因 `cc_native` 存在而直接跌入 team lane

### Advisor Graph / Funnel

- [/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)
- [/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py)

现在：

- `analyze_intent(...)` 会尊重 `scenario_pack.intent_top`
- `execute_funnel(...)` 会把 `scenario_pack` 带入 subgraph
- `funnel_graph` 会按 planning profile 改写 prompt hint
- `project_card` 会记录 `planning_profile`

## 边界

本版没有做的事：

- 没有新建 orchestrator daemon
- 没有把 `research` pack 一起收掉
- 没有重写通用 `task_intake` 推断器
- 没有让 `meeting_summary / interview_notes` 走 funnel

## 当前结论

Phase 3 的系统语义现在是：

- `planning` 不再只是一个 scenario 名字
- 它已经有固定 profile、固定 route、固定 acceptance、固定 prompt contract
- ingress / strategist / controller / graph / funnel 五层已接通
