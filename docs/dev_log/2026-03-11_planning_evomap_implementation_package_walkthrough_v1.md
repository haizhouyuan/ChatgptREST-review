---
title: Planning EvoMap Implementation Package Walkthrough
version: v1
updated: 2026-03-11
status: completed
artifact_dir: /vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755
---

# 这轮做了什么

我没有继续停在“给方向”，而是把 `planning -> EvoMap` 的下一步收成了一个可执行包。

## 1. 先核了当前实际状态

确认了 3 个事实：

1. `planning` 内容已经大量进 canonical EvoMap
2. 但 `planning lineage graph` 产物本身还没正式进库
3. 现在 `planning` 全部还是 `staged`，不能直接当 service knowledge

## 2. 生成了当前种子包

产物目录：

- `/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755`

其中包括：

- `planning_source_breakdown.tsv`
- `planning_bucket_quality.tsv`
- `planning_review_plane_seed.tsv`
- `planning_service_candidate_seed.tsv`
- `planning_archive_only_seed.tsv`
- `summary.json`

## 3. 写了 4 份主 runbook

- review plane schema
- lineage import runbook
- bootstrap active set runbook
- retrieval cutover plan

## 4. 写了 execution todo

把“这轮做完了什么、还差什么”固定下来，避免上下文压缩后断线。

# 为什么这样做

这轮不是直接开始改代码，因为当前真正缺的是：

- 正式的 review plane contract
- service candidate allowlist
- source-aware cutover 方案

没有这些，直接改 code 只会继续把 `planning` 原文粗放塞进 EvoMap。

# 当前判断

1. `planning` 的高质量吸收路径已经明确。
2. 现阶段最重要的不是“再导更多”，而是“先把 review plane 立起来”。
3. 这套 package 现在已经足够支持下一步进入真正的 importer / gating 实现。

