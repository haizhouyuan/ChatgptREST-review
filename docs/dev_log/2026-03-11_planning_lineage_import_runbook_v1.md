---
title: Planning Lineage Import Runbook
version: v1
updated: 2026-03-11
status: completed
artifact_dir: /vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755
---

# 目标

把 `planning` 的 lineage 结果从 artifact package 导入到 EvoMap review plane，而不是直接把原始文档硬升为 service knowledge。

# 输入

## 已有 lineage 产物

- [planning_lineage_family_registry.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541/final_v1/planning_lineage_family_registry.tsv)
- [planning_lineage_edges.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541/final_v1/planning_lineage_edges.tsv)
- [planning_evomap_mapping_candidates.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541/final_v1/planning_evomap_mapping_candidates.tsv)

## 已有 DB 审计产物

- [planning_source_breakdown.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755/planning_source_breakdown.tsv)
- [planning_bucket_quality.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755/planning_bucket_quality.tsv)
- [planning_review_plane_seed.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755/planning_review_plane_seed.tsv)

# 目标输出

导入后至少应得到 5 张 review-plane 表或其等价对象：

1. `planning_document_role`
2. `planning_version_family`
3. `planning_lineage_edge`
4. `planning_review_pack`
5. `planning_model_run`

如果先不写正式表，也至少要先产出 5 个规范 TSV：

- `document_role.tsv`
- `version_family.tsv`
- `lineage_edge.tsv`
- `review_pack.tsv`
- `model_run.tsv`

# 执行步骤

## Step 1: 冻结输入快照

确认当前种子包：

```bash
cat /vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755/summary.json
```

确认 lineage package：

```bash
ls -l /vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541/final_v1
```

## Step 2: 为所有 planning 文档分配 role

规则来源：

- `planning_evomap_mapping_candidates.tsv`
- `planning_review_plane_seed.tsv`
- `planning_archive_only_seed.tsv`
- `planning_service_candidate_seed.tsv`

优先级：

1. `controlled`
2. `archive_only`
3. `service_candidate`
4. `review_plane`

建议输出：

```text
doc_id  raw_ref  title  role  source_bucket  reason
```

## Step 3: 导入 family registry

直接使用：

- `planning_lineage_family_registry.tsv`

最少保留字段：

- `family_id`
- `family_name`
- `domain`
- `current_latest_doc_id`
- `notes`

## Step 4: 导入 curated lineage edges

先导入手工 curated edges：

- `planning_lineage_edges.tsv`

只导以下几类：

- `SUPERCEDES`
- `DERIVED_FROM`
- `IS_LATEST_OF`
- `REVIEWED_IN`
- `GENERATED_BY_MODEL_RUN`

不要一开始就把 `1025` 条 bootstrap version edges 全量写死为真值。
那些应该先进入 `candidate_edge`，再人工/模型核验。

## Step 5: 抽 ReviewPack 对象

从 `planning_review_plane_seed.tsv` 中抽取：

- `_review_pack/` 路径
- `REQUEST_*`
- `SUMMARY_*`
- `RESULT_*`
- `MODEL_SPEC_*`
- `README_*`

建议聚合规则：

- 以 review pack 根目录为一个 `review_pack_id`
- pack 下的 `REQUEST/SUMMARY/RESULT/MODEL_SPEC` 作为子材料
- `job_*`、`conversation.json`、`events.jsonl` 作为 `model_run` 证据，不复制原文

## Step 6: 抽 ModelRun 对象

从这些路径抽：

- `request.json`
- `answer.md`
- `conversation.json`
- `events.jsonl`
- `run_meta.json`
- `result.json`

建议聚合规则：

- 以 job 目录或 job id 为 `model_run_id`
- 存 provider/model/job_ref/path，不存大段正文

## Step 7: 标 LatestOutput

直接从：

- `/99_最新产物/`
- 稳定 `outputs/`

建立 `LatestOutput`

建议保留字段：

- `doc_id`
- `family_id`
- `release_label`
- `is_current`
- `published_at`

## Step 8: 生成 review-plane import snapshot

在正式写入 EvoMap 前，先导出一次中间 snapshot：

```text
planning_review_plane_import_snapshot/
  document_role.tsv
  version_family.tsv
  lineage_edge.tsv
  review_pack.tsv
  model_run.tsv
  latest_output.tsv
```

只有 snapshot 检查通过，才写正式 review plane。

# 验收检查

导入 snapshot 后，检查：

1. `service_candidate` 数量是否显著小于 raw planning docs
2. `_review_pack` 是否全部被标成 `archive_only` 或 `review_plane`
3. `99_最新产物` 是否全部带上 `LatestOutput`
4. 每个主线 family 是否至少有一条 `SUPERCEDES` 或 `IS_LATEST_OF`
5. `ModelRun` 是否能关联到对应的 `ReviewPack`

# 当前建议

先导入 6 条主线：

1. `104`
2. `60`
3. `reducer_core`
4. `peek_reviewpack`
5. `fifteen_plan`
6. `budget`

不要第一轮就覆盖全 `planning`。

