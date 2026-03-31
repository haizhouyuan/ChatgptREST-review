---
title: Planning Lineage Agent Teams Execution Checkpoint
version: v1
updated: 2026-03-11
status: in_progress
---

# 背景

本轮任务目标：

1. 对 `/vol1/1000/projects/planning` 做历史演进梳理，不只做关键词检索。
2. 先用现有全文索引与目录结构识别高价值文件族。
3. 再抽 `VersionFamily + ReviewPack + ModelRun + LatestOutput` 关系。
4. 先做一个高价值子集的 lineage graph。
5. 再把这张图映射进 EvoMap 的经验层。
6. 额外沉淀：本次使用 Claude Code agent teams 的经验、失败点、最佳实践调研与后续迭代建议。

# 已确认事实

## planning 仓库检索现状

- `planning` 仓库已经有本地全文检索：`_kb/index/index.sqlite`
- 查询脚本 `scripts/kb_query.py` 直接使用 SQLite FTS/BM25
- 建索引脚本 `scripts/kb_build.py` 创建的是 FTS5 虚表，不是向量库/图数据库
- 仓库内没有已落地、可直接使用的本地向量检索或图检索层

## planning 仓库体量与重点区

- `all_files = 28086`
- `text_like_files = 22289`
- 顶层体量最大区：
  - `减速器开发`
  - `机器人代工业务规划`
  - `docs`
  - `aios`
  - `十五五规划`
  - `预算`

## 当前高价值子集判断

优先进入 lineage / EvoMap review plane 的不是全仓，而是：

- `00_入口/`
- `_kb/`
- `docs/记忆治理与跨库归档/`
- `十五五规划/00_现稿/`
- `预算/00_模板与口径/`
- `机器人代工业务规划/*/99_最新产物/`
- `机器人代工业务规划/104关节模组代工_过程记录/`
- `机器人代工业务规划/60系列PEEK模组代工_过程记录/`
- `减速器开发/60关节模组研发_过程记录/`
- `减速器开发/PEEK摆线齿轮图纸/_review_pack/`

# Agent Teams 拆分

## 已废弃的宽切片

以下旧切片过大，执行效果差，已停止继续依赖：

- `slice_b_business_lines`
- `slice_c_reducer_development`

## 当前生效的 team 拆分

### 已有可用结果

- `slice_a_governance_system`
- `slice_d_org_finance_controlled`

### 新的窄切片

- `slice_b1_business_104`
- `slice_b2_business_60`
- `slice_c1_reducer_core`
- `slice_c2_reducer_reviewpack`
- `slice_g_relation_extractor`

## 新切片规模

- `slice_b1_business_104`: `5180` files
- `slice_b2_business_60`: `430` files
- `slice_c1_reducer_core`: `317` files
- `slice_c2_reducer_reviewpack`: `20221` files
  - 但该切片采用 `metadata-first + representative_files`，不做逐文件平均阅读
- `slice_g_relation_extractor`: 关系抽取专用，不做全仓平均通读

# 当前产物位置

## 工作目录

- `/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541`

## 旧结果

- `results/`

## 新 prompts

- `prompts_v2/`

## 新结果

- `results_v2/`

# 已完成的辅助抽取

## 机械候选边

- `results_v2/bootstrap_version_edges.tsv`
  - 当前已生成 `1025` 条 `SUPERSEDES_CANDIDATE`
- `results_v2/bootstrap_latest_output_edges.tsv`
  - 当前已生成 `351` 条 latest/output 候选边
- `results_v2/bootstrap_model_run_edges.tsv`
  - 当前已生成 `321` 条 model run / event log 候选边

## 目录级摘要

- `results_v2/bootstrap_model_run_dir_summary.json`
- `results_v2/bootstrap_latest_output_dir_summary.json`

## team 辅助材料

- `inventory/latest_output_candidates.tsv`
- `inventory/model_run_candidates.tsv`
- `inventory/slice_v2_helper_manifest.json`
- `inventory/slice_*_family_summary.json`
- `inventory/slice_c2_reducer_reviewpack_family_summary.json`
- `inventory/slice_c2_reducer_reviewpack_representative_files.tsv`

# 已有 reviewer 合并结论

已有 reviewer 对 `slice_a` 和 `slice_d` 做了 merge checklist，结论可直接作为后续 graph 汇总规范：

- 统一实体字段：`document_id / title / family_id / version / path / created_at / modified_at / status / source_slice`
- 统一关系类型：`SUPERCEDES / SUPPLEMENTS / PARALLELS / ARCHIVE_OF / DERIVED_FROM / REVIEWED_IN / GENERATES / CORRECTS`
- 统一过程字段：`process_id / process_family / input_artifacts / process_steps / output_artifacts / review_layers`

# 后续执行待办

## P0 继续盯 team 结果

- [ ] 轮询 `results_v2/`，收新切片落盘结果
- [ ] 若 `slice_b2_business_60` 或 `slice_c1_reducer_core` 长时间不落盘，继续收紧 prompt
- [ ] 若 `slice_c2_reducer_reviewpack` 卡住，则进一步只保留前 20 个 family + 代表样本重发

## P1 lineage graph package

- [ ] 汇总 A/F + B1/B2/C1/C2/G
- [ ] 建 `family_registry`
- [ ] 合并 `version/review/model/latest` 边
- [ ] 生成高价值子集的 lineage graph 清单
- [ ] 输出一份可读的 timeline + graph 摘要

## P2 EvoMap 映射

- [ ] 按 `archive_only / review_plane / service_candidate / lesson / procedure / correction` 做映射
- [ ] 明确哪些内容只进 archive，不进 service
- [ ] 明确哪些 version diff 应提炼为 correction/lesson

## P3 本次 teams 经验沉淀

- [ ] 记录 wrapper 失败点
- [ ] 记录直接多开可行点
- [ ] 记录宽切片失败、窄切片更优的证据
- [ ] 记录 `metadata-first` 对 review_pack 的收益
- [ ] 给出下次的标准化 team contract

## P4 外部最佳实践调研

- [ ] 查官方 Claude Code 文档：subagents / common workflows / hooks / slash commands
- [ ] 提炼与本次实践一致或冲突的点
- [ ] 给出后续改进建议：是否需要 worktree、hooks、slash commands、固定 output contract

# 当前判断

1. planning 仓库最值得补的是 lineage graph，不是先补向量库。
2. 对 planning 来说，图检索的价值高于向量检索，因为核心问题是历史谱系与流程关系，不是相似文本召回。
3. 多 agent 并行的正确方式不是“大切片平均分”，而是：
   - domain teams 负责读内容
   - relation extractor 负责横向抽边
   - synthesizer 负责汇总 lineage graph 与 EvoMap 映射
4. review_pack 不能按全量文件平均通读，必须 `metadata-first`。
