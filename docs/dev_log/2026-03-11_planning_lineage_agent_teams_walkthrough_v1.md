---
title: Planning Lineage Agent Teams Walkthrough
version: v1
updated: 2026-03-11
status: completed
artifact_workspace: /vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541
---

# 做了什么

## 1. 先判断 planning 仓库现状

先确认 `planning` 仓库是否已经有向量/图检索。

结论：

- 已有本地 FTS 检索
- 没有仓内稳定运行的向量检索或图检索
- 所以这轮不去“再造一套检索”，先做 lineage graph

## 2. 先做 inventory，再决定 team 方案

生成了：

- `all_files.tsv`
- `text_like_files.tsv`
- `summary.json`
- `monthly_timeline.json`
- `pattern_counts.json`
- `version_family_candidates.json`

目的：

- 不让 team 在无边界状态下平均通读 2 万多文本文件
- 让后续切片基于真实规模与路径模式

## 3. 第一轮宽切片失败

初始 4 切片里：

- `slice_a_governance_system` 成功
- `slice_d_org_finance_controlled` 成功
- `slice_b_business_lines` 卡住
- `slice_c_reducer_development` 只出半成品

判断：

- 业务线与减速器大切片太宽
- review pack 密度太高，不能按平均内容任务交给模型

## 4. 改成第二轮窄切片

拆成：

- `slice_b1_business_104`
- `slice_b2_business_60`
- `slice_c1_reducer_core`
- `slice_c2_reducer_reviewpack`
- `slice_g_relation_extractor`

同时预生成 helper：

- family summaries
- representative files
- latest output candidates
- model run candidates

## 5. 同步做 deterministic bootstrap

在 teams 运行的同时，机械抽了 3 类边：

- version edges
- latest output edges
- model run edges

这样即使某一条 team 任务失败，graph skeleton 仍然存在。

## 6. 用现有可用结果先做 synthesis

最终采用的证据结构是：

- A / D 旧切片报告
- B1 / B2 / C1 / G 新切片报告
- C2 用 metadata-first 本地梳理，并补发更小 runner
- deterministic bootstrap 边
- 代表文件实读与人工校准

## 7. 生成 bootstrap graph package

输出到：

- `final_v1/planning_lineage_family_registry.tsv`
- `final_v1/planning_lineage_edges.tsv`
- `final_v1/planning_evomap_mapping_candidates.tsv`

这一步把 `planning` 的高价值子集收成了可以继续工程化的中间层。

# 为什么这样做

## planning 的问题不是“找不到内容”，而是“讲不清谱系”

当前仓库的真正难点：

- 哪个版本 supersede 哪个版本
- 哪个 review pack 对应哪轮模型运行
- 哪个是 latest output
- 哪些差异应提炼为经验

所以先做 lineage，而不是先做 embedding。

## teams 的价值在并行理解，不在替代关系抽取

本次最有效的分工是：

- team 负责理解内容
- deterministic logic 负责先抽简单边
- synthesizer 再做统一抽象

# 留下的记录

## 有效产物

- `results/slice_a_governance_system_report.md`
- `results/slice_d_org_finance_controlled_report.md`
- `results_v2/slice_b1_business_104_report.md`
- `results_v2/slice_b2_business_60_report.md`
- `results_v2/slice_c1_reducer_core_report.md`
- `results_v2/slice_g_relation_extractor_report.md`

## 失败与重发记录

- 宽切片 `slice_b_business_lines` 失败
- 宽切片 `slice_c_reducer_development` 半失败
- 窄切片 `slice_c2_reducer_reviewpack` 仍然过大
- 补发小切片 runner：`ccjob_20260311T004710Z_7548ef4b`

# 当前判断

1. 这套方法已经足够把 `planning` 的高价值主链收出来。
2. 若要继续提升质量，下一步不是“多开更多 team”，而是把当前切片 contract 与 graph schema 产品化。
3. `planning` 接 EvoMap 的正确方向已经明确：先 archive/review，再 service，不做全量原文硬入库。

