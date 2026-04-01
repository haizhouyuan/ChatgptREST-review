# 2026-03-21 Phase 3 Planning Scenario Pack Review Walkthrough v2

## 目标

这轮不是重复做一次“字段有没有传进去”的核验，而是验证 `aa3ea5b` 是否真正把上一轮评审中的 4 个场景质量问题收掉：

- note-taking ask 缺材料时是否会先 clarify
- 轻量 business planning 是否还会被过度重型化
- `例会纪要` 这类中文短写是否能命中 pack
- `watch_policy / funnel_profile` 是否已经进入 live policy

## 实际做法

### 1. 先按变更点读代码，不倒推文档结论

我先确认了这轮真实改动集中在：

- [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py)
- [ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py)
- [funnel_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py)

随后再对照：

- [2026-03-21_phase3_planning_scenario_pack_completion_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_phase3_planning_scenario_pack_completion_v2.md)

重点不是看字段名，而是看这些字段是否进入了真正的路由、澄清和 gate 判断。

### 2. 做 4 组最小复现

我用 canonical intake -> scenario pack -> contract seed -> strategist 的 live builder 路径复现了：

1. `请总结面试纪要`
2. `请整理今天例会纪要`
3. `请帮我做一个业务规划框架，先给简要版本，不要走复杂流程`
4. `请总结面试纪要` + 附件

复现结果是：

- 面试纪要无材料：`profile=interview_notes`、`route_hint=report`、`clarify_required=True`
- 例会纪要无材料：`profile=meeting_summary`、`route_hint=report`、`clarify_required=True`
- 轻量业务规划：`profile=business_planning`、`route_hint=report`、`clarify_required=False`
- 面试纪要有附件：`clarify_required=False`

这说明低上下文 summary ask 的 clarify gate 已经真正生效，同时 light business planning 也不再被一刀切进 funnel。

### 3. 查 runtime 消费点，确认 policy 不是纸面字段

我额外确认了：

- `watch_policy.checkpoint=delivery_only` 会直接参与 strategist clarify gate
- `funnel_profile` 会直接调整 Funnel Gate A threshold
- `scenario_pack.route_hint` 会覆盖 graph route 决策
- `scenario_pack.execution_preference` 会影响 controller 的 execution kind

也就是说，这轮新增的 pack policy 已经不是 prompt-only metadata。

### 4. 补看 OpenClaw 插件侧

因为你这轮把 OpenClaw 也算进了“Planning Scenario Pack 已稳定的入口”，我额外看了：

- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
- [test_openclaw_cognitive_plugins.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py)

并补跑了整份插件测试，确认：

- plugin 仍然发 `task_intake`
- `planning -> planning_memo`
- `/v3/agent/turn` 仍是唯一公开 ask 正门
- 插件侧没有因为这轮 scenario pack 收口被打坏

## 本轮判断为什么和 v1 不同

`v1` 时的问题是“策略对象存在，但还没真正改变行为”。

`v2` 这次不同的地方在于：

- 纪要/面试 ask 已经会被 gate 到 clarify
- 轻量 business planning 已经会被 gate 到 report
- 词法短写已经进了命中链
- funnel / watch 两类 policy 都已经进入 runtime decision

所以这次不是“继续提同样的问题”，而是确认这些问题确实已经结束。

## 最终定性

我给这轮的定性是：

- Phase 3 主干：完成
- 旧 4 个质量问题：已收口
- 当前状态：可以作为完整阶段签字
- 后续工作性质：优化型，不再是补主干缺口

## 产物

本轮新增：

- [2026-03-21_phase3_planning_scenario_pack_review_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_phase3_planning_scenario_pack_review_v2.md)
- [2026-03-21_phase3_planning_scenario_pack_review_walkthrough_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_phase3_planning_scenario_pack_review_walkthrough_v2.md)
