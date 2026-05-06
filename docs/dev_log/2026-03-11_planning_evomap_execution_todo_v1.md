---
title: Planning EvoMap Execution Todo
version: v1
updated: 2026-03-11
status: in_progress
artifact_dir: /vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_evomap_package/20260311T093755
---

# Todo

## T0 冻结 authoritative contract

- [x] 确认 `planning raw repo` 是 archive truth
- [x] 确认 EvoMap 只消费派生产物，不直接把全量原文当 service
- [x] 写出完整路径文档

## T1 生成当前种子产物

- [x] 生成 `planning_source_breakdown.tsv`
- [x] 生成 `planning_bucket_quality.tsv`
- [x] 生成 `planning_review_plane_seed.tsv`
- [x] 生成 `planning_service_candidate_seed.tsv`
- [x] 生成 `planning_archive_only_seed.tsv`

## T2 固化 lineage import package

- [x] 梳理 `family_registry`
- [x] 梳理 `curated_edges`
- [x] 梳理 `mapping_candidates`
- [ ] 生成 review-plane import snapshot
- [ ] 写正式 importer 或等价 SQL/TSV pipeline

## T3 source re-bucketing

- [x] 定义重分桶规则
- [ ] 生成 `document_role.tsv`
- [ ] 给全量 planning docs 打 role

## T4 bootstrap active set

- [x] 定义第一批 active 范围
- [ ] 生成 `bootstrap_active_allow_candidates.tsv`
- [ ] reviewer 审核第一批 120 docs
- [ ] 输出 `bootstrap_active_allowlist.tsv`
- [ ] 文档 -> atoms 映射

## T5 retrieval cutover

- [x] 写 cutover plan
- [ ] 准备 10 条代表性 query 验收集
- [ ] active_then_review_fallback 验收
- [ ] staged fallback 退出条件检查

## T6 teams / reviewer 提效

- [x] 明确大切片失败、metadata-first 更优
- [x] 记录 cc runner stale status 失败模式
- [ ] 对 `planning_service_candidate_seed.tsv` 跑 reviewer 审查
- [ ] 形成 keep/drop 规则

## T7 后续代码实现

- [ ] review-plane importer
- [ ] source-aware retrieval gating
- [ ] bootstrap promotion helper

