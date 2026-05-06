---
title: Planning Retrieval Cutover Plan
version: v1
updated: 2026-03-11
status: completed
---

# 目标

让 `planning` 从“默认读 staged 原子”切到“优先读 active / reviewed knowledge”。

# 当前问题

当前 EvoMap retrieval 默认允许：

- `promotion_status in (active, staged)`

这意味着 `planning` 相关的 `40901 staged atoms` 会直接影响回答质量。

# 切换策略

## Phase A: 不改默认 retrieval，全做准备

先完成：

1. review plane 建立
2. bootstrap active set 建立
3. 代表性 query 验收

在这之前，不改 retrieval 默认行为。

## Phase B: 对 planning source 做 source-aware cutover

不是全局一次性切 `active-only`，而是先对 `planning` 做 source-aware 规则：

- `planning_latest_output`
- `planning_outputs`
- `planning_skills`
- `planning_budget`
- `planning_strategy`
  优先只查 active

- `planning_review_pack`
- `planning_kb`
- `planning_aios`
  只作为 fallback，不直接进主答案面

## Phase C: active_then_review_fallback

第一阶段建议逻辑：

1. 先查 `planning active`
2. 若命中不足，再查 `planning review_plane accepted`
3. 最后才允许 `staged fallback`

## Phase D: staged 逐步退出

当下面条件都满足时，再把 planning 的 `staged fallback` 默认关掉：

1. `active docs >= 80`
2. 10 条代表性 query 覆盖率通过
3. reviewer 判定第一批 active 噪声率足够低
4. `planning_review_pack` 已不会误进 service plane

# 代表性 query 验收清单

至少验证这些 query：

1. `104 模组 量产导入`
2. `客户沟通稿 代工规划`
3. `两个月交付 前提条件`
4. `60 PEEK 停止线`
5. `Review Pack 构建方法`
6. `十五五规划 对内领导审阅稿`
7. `预算 模板`
8. `Gate RACI`
9. `STEP 齿廓提取`
10. `双模复核 R8 冻结条件`

验收原则：

- 结果优先命中 active/service candidate
- 不应优先返回 raw answer / request / review_pack 过程文件

# stop conditions

如果出现以下任一情况，停止切换：

1. active 命中明显下降且 fallback 依赖 review_pack
2. 最新输出和历史 review 结果冲突严重
3. query 结果中大量出现 `REQUEST_*` / `answer_*`
4. 受控资料穿透进返回结果

# 建议

实现上优先做 **source-aware gating**，不要直接全局改 retrieval。

对 `planning` 来说，正确顺序是：

`active seed -> source-aware cutover -> review fallback -> staged exit`

