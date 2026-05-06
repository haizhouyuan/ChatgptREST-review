# 2026-04-03 Maxwell Redteam Walkthrough: Planning Agent 未完成部分全量实施计划 v1

## 做了什么

这次让 Maxwell 对 `planning agent 未完成部分全量实施计划` 做了一轮严格红队，并把有效批评吸收到 `v6` 版本里。

涉及文档：

- [2026-04-03_planning_agent_full_unfinished_implementation_plan_v6.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-03_planning_agent_full_unfinished_implementation_plan_v6.md)
- [2026-04-03_maxwell_redteam_planning_agent_full_unfinished_implementation_plan_v6.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-03_maxwell_redteam_planning_agent_full_unfinished_implementation_plan_v6.md)

## 红队指出的关键问题

1. 计划文档把一些已经完成的 evidence 还写成“未完成”。
2. 第一阶段 gate 太松，会让后续开发基于错误 baseline 推进。
3. `W1/W2/W3/W4/W6` 各工作包之间还有顺序和 ownership 重叠问题。

## 这轮怎么处理

我没有顺从红队，而是先独立核对 evidence，再做修正。

最后采纳的关键修正包括：

1. 更新当前状态冻结
2. 收紧第一阶段完成定义
3. 把 `W1` 改成“稳态化与 provider coverage”
4. 把 `task_contract` 明确纳入 `W2`
5. 把 `OpenClawBot owner path` 写死为 `W3` 证据链
6. 把 `W4-S1` 前移并行
7. 把 `Anthropic harness / EvoMap` 明确排除出 phase-1 完成判定

## 结果

这轮之后，`v6` 才能作为当前 authoritative execution plan 继续往下推进。