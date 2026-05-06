---
title: Planning Review Plane Schema
version: v1
updated: 2026-03-11
status: completed
artifact_dir: /vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755
---

# 目标

为 `planning` 仓库建立一层 **review plane**，把当前“原始文档直接入 EvoMap”的状态升级成“原始文档、谱系关系、review 决策、服务候选分层存在”的状态。

这层不是替代原始文档，也不是直接服务回答，而是承接：

- `Document`
- `VersionFamily`
- `ReviewPack`
- `ModelRun`
- `LatestOutput`
- `ReviewDecision`
- `LessonLink`

# 设计原则

1. `planning` 原始文件仍是 archive truth，不移动、不改写。
2. EvoMap 中现有 `documents / episodes / atoms` 继续保留，作为 raw capture。
3. 新增的 review plane 只保存：
   - 文档角色
   - family 归属
   - supersede / supplement / latest 关系
   - review verdict
   - lesson/procedure/correction 提取结论
4. service plane 只从 review plane 的 `accepted_service` 与 `extracted_lesson/procedure/correction` 派生。

# 对象模型

## 1. DocumentRole

每个 `planning` 文档在 review plane 必须有一个角色：

- `archive_only`
- `review_plane`
- `service_candidate`
- `controlled`
- `noise_reject`

说明：

- `archive_only`：保留追溯，但永不直接进服务面
- `review_plane`：需要进一步做 family / diff / review 判定
- `service_candidate`：有资格进入 bootstrap active 评审
- `controlled`：受控资料，默认不进入服务面
- `noise_reject`：已判断为噪声或冗余，不再继续审核

## 2. VersionFamily

建议字段：

- `family_id`
- `family_name`
- `domain`
- `canonical_topic`
- `top_level`
- `source_slice`
- `first_seen_at`
- `last_seen_at`
- `doc_count`
- `current_latest_doc_id`
- `notes`

建议 ID 规则：

- `plfam_<stable_slug>`

样例：

- `plfam_b104_exec_report`
- `plfam_fifteen_plan_current_drafts`
- `plfam_peek_dual_confirm`

## 3. ReviewPack

建议字段：

- `review_pack_id`
- `doc_id`
- `family_id`
- `pack_name`
- `round_label`
- `started_at`
- `ended_at`
- `input_kind`
- `contains_request`
- `contains_summary`
- `contains_result`
- `contains_model_records`
- `status`

建议 ID 规则：

- `plpack_<path_hash>`

## 4. ModelRun

建议字段：

- `model_run_id`
- `doc_id`
- `family_id`
- `provider`
- `model`
- `job_ref`
- `request_path`
- `answer_path`
- `conversation_path`
- `events_path`
- `run_meta_path`
- `started_at`
- `ended_at`
- `status`

说明：

- 没必要复制 conversation 全文
- 只需要建立“哪个文档/pack 对应哪轮模型运行”的映射

## 5. LatestOutput

建议字段：

- `latest_output_id`
- `doc_id`
- `family_id`
- `release_label`
- `is_current`
- `supersedes_doc_id`
- `published_at`
- `release_path`

说明：

- `99_最新产物` 和稳定 `outputs/` 都走这类对象

## 6. ReviewDecision

这是 review plane 最关键的对象。

建议字段：

- `decision_id`
- `doc_id`
- `family_id`
- `reviewer`
- `reviewed_at`
- `verdict`
- `reason_codes`
- `notes`
- `sensitivity_level`
- `extract_lesson`
- `extract_procedure`
- `extract_correction`
- `service_readiness`

允许的 `verdict`：

- `accept_review_only`
- `accept_service_candidate`
- `extract_lesson`
- `extract_procedure`
- `extract_correction`
- `archive_only`
- `controlled`
- `reject_noise`
- `needs_human_review`

## 7. LessonLink

用于把 review decision 和派生经验条目关联起来。

建议字段：

- `lesson_link_id`
- `source_doc_id`
- `family_id`
- `decision_id`
- `derived_atom_kind`
- `derived_atom_id`
- `link_reason`

# 关系模型

## 必须支持的边

- `BELONGS_TO_FAMILY`
- `SUPERCEDES`
- `SUPPLEMENTS`
- `PARALLELS`
- `REVIEWED_IN`
- `GENERATED_BY_MODEL_RUN`
- `IS_LATEST_OF`
- `GUIDES_REVISION_OF`
- `CORRECTS`

## 优先级

先做：

- `BELONGS_TO_FAMILY`
- `SUPERCEDES`
- `REVIEWED_IN`
- `GENERATED_BY_MODEL_RUN`
- `IS_LATEST_OF`

后做：

- `GUIDES_REVISION_OF`
- `CORRECTS`
- `SUPPLEMENTS`
- `PARALLELS`

# source re-bucketing 规则

当前 canonical DB 里 `source='planning'` 混了太多东西。review plane 必须重分桶。

建议重分：

- `planning_latest_output`
- `planning_outputs`
- `planning_review_pack`
- `planning_kb`
- `planning_skills`
- `planning_aios`
- `planning_strategy`
- `planning_budget`
- `planning_controlled`

按路径判定：

- `*/99_最新产物/*` -> `planning_latest_output`
- `*/outputs/*` -> `planning_outputs`
- `*/_review_pack/*` -> `planning_review_pack`
- `/_kb/*` -> `planning_kb`
- `/skills-src/*` -> `planning_skills`
- `/aios/*` -> `planning_aios`
- `/十五五规划/*` -> `planning_strategy`
- `/预算/*` -> `planning_budget`
- `/受控资料/*` -> `planning_controlled`

# service candidate 的最低门槛

只有同时满足下面条件，才允许 `accept_service_candidate`：

1. 不在 `_review_pack`
2. 不在 `conversation/events/debug`
3. 不属于 `controlled`
4. 有明确 family
5. 有明确 latest / stable 语义
6. 可以脱离原上下文独立理解
7. 被判定为模板、流程、冻结口径、总结稿之一

# 当前种子输入

本次已生成的种子清单：

- [planning_source_breakdown.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755/planning_source_breakdown.tsv)
- [planning_bucket_quality.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755/planning_bucket_quality.tsv)
- [planning_review_plane_seed.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755/planning_review_plane_seed.tsv)
- [planning_service_candidate_seed.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755/planning_service_candidate_seed.tsv)
- [planning_archive_only_seed.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755/planning_archive_only_seed.tsv)

# 验收标准

review plane 建成后，至少要满足：

1. 每个 `planning` 文档都能落到 `DocumentRole`
2. 高价值文档有 family 归属
3. `_review_pack` 能映射到 `ReviewPack`
4. 模型运行记录能映射到 `ModelRun`
5. `99_最新产物` 能映射到 `LatestOutput`
6. 至少 1 批 review decision 能产出 `service_candidate` 与 `lesson/procedure/correction`

