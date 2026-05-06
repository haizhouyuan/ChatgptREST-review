# Phase 3 Completion: Planning Scenario Pack v1

## 完成范围

本轮完成了 `Phase 3: Planning Scenario Pack` 的实现面，不只是文档冻结。

### 新增

- [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py)
- [test_scenario_packs.py](/vol1/1000/projects/ChatgptREST/tests/test_scenario_packs.py)
- [test_controller_engine_planning_pack.py](/vol1/1000/projects/ChatgptREST/tests/test_controller_engine_planning_pack.py)
- [planning_scenario_pack_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_planning_scenario_pack_v1.md)
- [planning_acceptance_profiles_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_planning_acceptance_profiles_v1.json)

### 修改

- [ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py)
- [prompt_builder.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/prompt_builder.py)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)
- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py)
- [graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)
- [funnel_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py)

## 这轮真正收住的点

1. `planning` 已经有稳定 pack，不再只是一个 scenario label。
2. ingress 会把 `scenario_pack` 和 canonical `task_intake` 一起带下游。
3. strategist/prompt 已经按 planning profile 变成不同 deliverable。
4. controller 已经能用 `scenario_pack` 决定 route，并强制 planning 当前走 `job` 而不是 team lane。
5. advisor graph / funnel 已经能消费 `scenario_pack`，不再只按通用 heuristic。

## 回归

通过的定向回归：

```bash
./.venv/bin/pytest -q \
  tests/test_scenario_packs.py \
  tests/test_ask_strategist.py \
  tests/test_prompt_builder.py \
  tests/test_routes_agent_v3.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_advisor_graph.py \
  tests/test_funnel_graph.py \
  tests/test_controller_engine_planning_pack.py

./.venv/bin/pytest -q \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_feishu_ws_gateway.py \
  tests/test_agent_v3_routes.py \
  tests/test_advisor_v3_end_to_end.py \
  tests/test_business_flow_advise.py \
  -k 'openclaw or feishu or advise or v3 or agent_turn'

python3 -m py_compile \
  chatgptrest/advisor/scenario_packs.py \
  chatgptrest/advisor/ask_strategist.py \
  chatgptrest/advisor/prompt_builder.py \
  chatgptrest/advisor/graph.py \
  chatgptrest/advisor/funnel_graph.py \
  chatgptrest/api/routes_agent_v3.py \
  chatgptrest/api/routes_advisor_v3.py \
  chatgptrest/controller/engine.py \
  chatgptrest/advisor/feishu_ws_gateway.py \
  tests/test_scenario_packs.py \
  tests/test_ask_strategist.py \
  tests/test_prompt_builder.py \
  tests/test_routes_agent_v3.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_advisor_graph.py \
  tests/test_funnel_graph.py \
  tests/test_controller_engine_planning_pack.py \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_feishu_ws_gateway.py \
  tests/test_agent_v3_routes.py \
  tests/test_advisor_v3_end_to_end.py \
  tests/test_business_flow_advise.py
```

## 当前阶段判断

`Phase 3` 现在可以按“已完成并可核验”处理。

更准确地说：

- `planning` 的 front-door semantics 已冻结
- `planning` 的 route/prompt/acceptance 已冻结
- `planning` 的 pack 已经真正进入 live ingress 和 runtime path

还没做的，是下一阶段的事：

- `Phase 4: Research Scenario Pack`
- 更严格的 live soak / shadow traffic 验证
- compatibility surface 的继续收口
