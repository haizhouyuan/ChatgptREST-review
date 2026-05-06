# 2026-04-03 Planning Agent 未完成部分全量实施计划 Walkthrough v6

## 做了什么

这次把“还没完成的部分”重新收成了一份可直接执行的 `v6` 全量实施计划：

- [2026-04-03_planning_agent_full_unfinished_implementation_plan_v6.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-03_planning_agent_full_unfinished_implementation_plan_v6.md)

同时补了一份红队吸收记录：

- [2026-04-03_maxwell_redteam_planning_agent_full_unfinished_implementation_plan_v6.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-03_maxwell_redteam_planning_agent_full_unfinished_implementation_plan_v6.md)

## 为什么现在要做这件事

前面连续做了多轮 phase-1 开发后，旧版未完成计划已经落后于当前代码现实，主要落后在 4 个地方：

1. `W3` 已经不是纯规划，而是已有 preflight metadata、checkpoint snapshot persistence、advisory material-action posture 这 3 个真实代码切片。
2. `OpenClawBot` 主链已经有一条 `gemini-requested` live green，acceptance pack 也已经 7/7 全绿，不能再按“尚未打通”写现状。
3. 第一阶段 gate 太松，按旧写法会出现“明明还不稳却看起来已经通过”的问题。
4. `W2/W3/W4/W6` 在 owner boundary、顺序和 scope 上还有重叠，必须先重新切清楚。

## 这版 v6 相比旧版的关键变化

1. 把“当前状态冻结”改成与最新 evidence 对齐。
2. 把 `W1` 从“打通主链”改成“稳态化与 provider coverage”。
3. 收紧第一阶段 gate：
   - 连续 3 次 live green
   - 1 次 live fail
   - 1 次 live cancel
   - 7/7 acceptance pack 持续绿
   - 3/3 continuity pack 持续绿
4. 把 `task_contract + checkpoint query CLI` 明确纳入 `W2`。
5. 把 `W4-S1` 前移到与 policy 层并行，不再完全后置。
6. 把 `Anthropic harness / EvoMap` 明确排除出 phase-1 完成判定。

## 这版文档的用途

后续继续开发时，这份 `v6` 应作为：

1. 当前 authoritative execution plan
2. 每批代码改动的对照表
3. 阶段 gate 的统一口径
4. 用户侧说明“现在做到哪、后面怎么做”的主基线
