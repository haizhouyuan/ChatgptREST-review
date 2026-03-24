# 2026-03-21 Phase 3 Planning Scenario Pack Review v2

## 总评

这轮 `aa3ea5b` 可以签字通过。

上一轮评审指出的 4 个影响场景质量的问题，这次都已经进入 live decision path，而不只是停在 pack schema 或 prompt 元数据层：

- `meeting_summary / interview_notes` 在缺少 grounding inputs 时会先 clarify，不再“知道缺信息但继续跑”
- `business_planning` 已分出 light / outline 分支，轻量规划会稳定走 `report`
- 中文高频短写如 `例会纪要` 现在能稳定命中 `meeting_summary`
- `watch_policy` 与 `funnel_profile` 都已经有明确的 runtime 消费点

从用户体验角度看，这一轮已经把 `planning` 从“技术上接通”推进到了“基本符合真实场景使用”。

## Findings

未发现新的阻断性问题。

### 1. 纪要 / 面试笔记类低上下文请求现在会先澄清，质量风险已明显下降

关键消费点已经进入 live strategist gate：

- [ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py#L166)
- [ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py#L182)
- [ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py#L197)
- [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py#L292)
- [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py#L334)

我本地按 live builder 路径复现确认：

- `请总结面试纪要` -> `profile=interview_notes`、`route_hint=report`、`clarify_required=True`
- `请整理今天例会纪要` -> `profile=meeting_summary`、`route_hint=report`、`clarify_required=True`
- 同样的面试纪要请求一旦补上附件 -> `clarify_required=False`

这次已经不是“能问出 clarify questions 但不真正拦住”，而是会把低上下文 note-taking ask 收到 `clarify`。

### 2. 轻量 business planning 不再被一刀切压进 funnel

轻量分支已经在 pack resolver 中稳定存在，并且会影响实际 route：

- [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py#L431)
- [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py#L436)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1273)
- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1745)

我本地复现：

- `请帮我做一个业务规划框架，先给简要版本，不要走复杂流程`
- 命中 `profile=business_planning`
- `scenario_pack.route_hint=report`
- strategist 最终 `route_hint=report`
- `clarify_required=False`

这一点已经回到更符合用户心智的行为，不再默认重型化。

### 3. 中文高频短写覆盖已补齐

高频短写词法已经进入 pack 识别词表：

- [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py#L58)
- [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py#L64)
- [tests/test_scenario_packs.py](/vol1/1000/projects/ChatgptREST/tests/test_scenario_packs.py#L37)
- [tests/test_routes_advisor_v3_task_intake.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_advisor_v3_task_intake.py#L227)

`请整理今天例会纪要` 现在在本地复现里会稳定命中 `meeting_summary`，不再掉回 base planning/general path。

### 4. `watch_policy` 与 `funnel_profile` 现在已经是 live policy，而不是仅用于说明

两者的 runtime 消费点已成立：

- `watch_policy -> clarify gate`
  - [ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py#L177)
  - [ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py#L183)
- `funnel_profile -> Gate A threshold`
  - [funnel_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py#L212)
  - [funnel_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py#L399)
  - [funnel_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py#L406)
  - [tests/test_funnel_graph.py](/vol1/1000/projects/ChatgptREST/tests/test_funnel_graph.py#L104)

此外，`scenario_pack.route_hint` 和 `execution_preference` 也都继续被 controller 实际消费：

- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L827)
- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L831)
- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1745)

## 剩余风险

这轮没有新的功能性问题，但还有两个非阻断风险值得记录：

- `meeting_summary / interview_notes / light business planning` 在 `AskContract` 层仍然统一落成 `task_template=implementation_planning`，真实的 report-like 差异主要靠 `scenario_pack.route_hint` 与 `prompt_template_override` 收回来。当前 live path 已能正确消费，所以这更像内部语义不够干净，而不是用户面 bug。
- OpenClaw 这边当前覆盖到的是插件契约与 payload 构造测试，不是完整远端 planning E2E。现有结果足以说明 adapter 没退化，但若后面继续扩 planning profile，仍建议补一条真正从插件 payload 到 `/v3/agent/turn` 的 planning smoke。

## 评审判断

如果标准是“Phase 3 是否已经完成一个可交付的 planning scenario pack 阶段”，我的判断是通过。

如果标准是“以后完全不需要再调 planning 质量策略”，那还不是。现在更准确的定性是：

- 架构方向：正确
- live integration：完成
- 场景质量：已达到可交付水平
- 后续工作：进入增量优化，而不是继续修主干缺口

## 本轮复跑

我重新执行并通过了以下回归：

```bash
./.venv/bin/pytest -q \
  tests/test_scenario_packs.py \
  tests/test_ask_strategist.py \
  tests/test_funnel_graph.py \
  tests/test_routes_agent_v3.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_controller_engine_planning_pack.py

./.venv/bin/pytest -q \
  tests/test_prompt_builder.py \
  tests/test_advisor_v3_end_to_end.py \
  tests/test_business_flow_advise.py \
  -k 'planning or advise or v3_ask or strategy or prompt'

./.venv/bin/pytest -q tests/test_openclaw_cognitive_plugins.py

python3 -m py_compile \
  chatgptrest/advisor/scenario_packs.py \
  chatgptrest/advisor/ask_strategist.py \
  chatgptrest/advisor/funnel_graph.py \
  tests/test_scenario_packs.py \
  tests/test_ask_strategist.py \
  tests/test_funnel_graph.py \
  tests/test_routes_agent_v3.py \
  tests/test_routes_advisor_v3_task_intake.py
```

## 结论

`Phase 3: Planning Scenario Pack` 现在已经从“可用但未调顺”收到了“可交付”。下一步不需要再围绕这 4 个旧问题打补丁，可以转向新的 scenario pack 或更细的 planning quality 优化。
