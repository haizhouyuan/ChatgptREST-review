---
title: Planning Bootstrap Active Set Runbook
version: v1
updated: 2026-03-11
status: completed
artifact_dir: /vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755
---

# 目标

为 `planning` 从当前 `40901 staged atoms / 0 active` 的状态，收敛出第一批可服务的 `bootstrap active set`。

# 当前事实

当前 canonical DB 中：

- `planning/service_candidate_seed` 已生成：`300` 行
- `planning/review_plane_seed` 已生成：`1423` 行
- `planning/archive_only_seed` 已生成：`500` 行

但注意：

- 这些只是 seeds，不等于都能直接升 active
- 当前很多高质量项仍混有：
  - `Pro回答_*`
  - `REQUEST_*`
  - `_review_pack` 材料
  - `_kb` 抽取文本

# 第一批 active 的目标范围

只从下面 6 类里选：

1. `104` 的稳定执行稿 / 客户稿 / 可研主文档
2. `60` 的四阶段流程 / 领导版汇总稿
3. `reducer_core` 的 M0 / Gate / StopLine / 总报告稳定版
4. `十五五规划` 当前冻结稿
5. `预算` 模板与预算概览/明细
6. `skills-src` / `_kb` 的稳定模板和方法稿

第一批不要升：

- `_review_pack`
- `REQUEST_*`
- `answer_*`
- `conversation_*`
- `events_*`
- `debug_*`
- `_kb/index/extracted/*`
- 受控资料

# 执行步骤

## Step 1: 基于 seed 做 auto-drop

从 [planning_service_candidate_seed.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755/planning_service_candidate_seed.tsv) 自动剔除：

- `title=answer`
- `title LIKE 'REQUEST%'`
- `raw_ref LIKE '%/_review_pack/%'`
- `raw_ref LIKE '%/conversation_%'`
- `raw_ref LIKE '%/events_%'`
- `raw_ref LIKE '%/debug_%'`
- `raw_ref LIKE '/vol1/1000/projects/planning/_kb/index/extracted/%'`

输出：

- `bootstrap_active_allow_candidates.tsv`
- `bootstrap_active_drop_candidates.tsv`

## Step 2: 人工 / reviewer 审一轮

对 `allow_candidates` 做 reviewer pass，目标只回答两件事：

1. 这条是不是“可复用、稳定、脱离上下文可理解”
2. 它更像：
   - `service_candidate`
   - `lesson`
   - `procedure`
   - `correction`
   - `review_only`

建议 reviewer 输入规模：

- 第一轮最多 `120` docs
- 不要一口气审 `300`

## Step 3: 形成 bootstrap allowlist

建议输出表：

```text
doc_id  title  raw_ref  final_bucket  reviewer  note
```

允许的 `final_bucket`：

- `service_candidate`
- `lesson`
- `procedure`
- `correction`

## Step 4: 从 doc 映射到 atoms

把 allowlist 文档对应的 atoms 取出，形成：

- `bootstrap_active_atom_candidates.tsv`

最少字段：

- `atom_id`
- `doc_id`
- `title`
- `atom_type`
- `avg_quality`
- `raw_ref`
- `target_bucket`

## Step 5: staged -> candidate

第一轮只做：

- `staged -> candidate`

不直接 `active`。

原因：

- 当前 `groundedness/confidence/reusability` 还没审
- 直接 active 风险太高

## Step 6: candidate -> active

只允许下面 4 类进入 active：

1. `procedure`
2. `lesson`
3. `correction`
4. 已明确属于 stable current output 的 `service_candidate`

进入 active 的最低条件：

- 经过 reviewer pass
- 不含 `_review_pack / answer / request / conversation / debug`
- 有 family 与 latest 归属
- 可以脱离上下文独立理解

# 推荐配额

第一批 bootstrap active 目标不要大。

建议：

- `104`: 25 docs
- `60`: 12 docs
- `reducer_core`: 12 docs
- `十五五规划`: 10 docs
- `预算`: 8 docs
- `skills/_kb`: 13 docs

合计：

- `80` docs 左右

这比“大量 staged 伪活跃”更可控。

# 成功标准

第一批 active 形成后，至少做到：

1. `planning active docs >= 80`
2. 不包含 `_review_pack / answer / request / conversation / debug`
3. 覆盖 6 条主线
4. 能支持 10 条代表性 query 的 retrieval 验收

