# KB + Planning High-Quality Harness Execution TODO Master V4

Date: 2026-04-08

## 主计划

- [统一执行计划 Codex方案 V4](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v4.md)

## 总状态

- 状态：`completed`
- Owner：`Codex`
- Sidecar：`claudeminmax`

## 已完成

### Batch A：计划冻结与角色分工

- [x] `v1 -> v2 -> v3 -> v4` 统一计划收敛
- [x] 冻结子系统边界、groundedness 权重、dataset schema、fallback 护栏、EvoMap vector、feedback/scorer 接线
- [x] 显式写入 `claudeminmax` 的 `KB sidecar re-ingest / data-quality` workstream

### Batch B：KB / EvoMap 基线治理

- [x] BaseExtractor 统一入库门禁
- [x] ActivityExtractor family dedup / skip
- [x] archive runner 落地并完成 live-safe apply
- [x] `valid_from` backfill
- [x] `canonical_question` backfill
- [x] `family-aware groundedness` 权重落地
- [x] chain backfill harness

### Batch C：Planning 高质量 harness

- [x] detector registry 落地
- [x] 高频 profile 落地
- [x] interaction learning v1 扩展
- [x] phase10 dataset 扩展到 `10 items / 30 cases`

### Batch D：Retrieval / Provenance / Vector / Feedback

- [x] `PLANNING_EXPLICIT_PATH`
- [x] provenance / layer / source_bucket 标记
- [x] guarded candidate/staged fallback
- [x] EvoMap vector lane + vectorization runner
- [x] `answer_feedback` 写入
- [x] `KB scorer` 事件接线

### Batch E：OpenClaw live vertical

- [x] `visit_cooperation_prep` route/lane/closure vertical
- [x] 修复 generic `planning_general` wrapper default 压制 raw-ingress 强信号的问题
- [x] API service restart + live gate 复验

### Batch F：Acceptance / Sidecar / 收口

- [x] targeted suite 全绿
- [x] unified acceptance pack 全绿
- [x] sidecar artifacts 拷入 acceptance pack
- [x] completion / residual / walkthrough 落盘

## Sidecar 交付物

- [x] `reingest_candidates`
- [x] `final_sidecar_review`
- [x] `family_quality_audit`（前序 sidecar 包）
- [x] `groundedness_sample_review`（前序 sidecar 包）
- [x] `dataset_assertion_extension`（前序 sidecar 包）
- [x] `fallback_provenance_redteam`（前序 sidecar 包）

## 最终验收

1. [x] `USER_HOT_PATH` 未回归
2. [x] `PLANNING_EXPLICIT_PATH` recall/provenance 可解释
3. [x] EvoMap vector lane 可用且 fail-open
4. [x] `answer_feedback` 与 `KB scorer` 事件链可跑
5. [x] phase10 / readiness / live acceptance / unified acceptance 全绿
