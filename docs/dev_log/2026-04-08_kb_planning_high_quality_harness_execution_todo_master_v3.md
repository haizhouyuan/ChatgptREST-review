# KB + Planning High-Quality Harness Execution TODO Master V3

Date: 2026-04-08

## 主计划

- [统一执行计划 Codex方案 V3](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v3.md)

## 总状态

- 状态：`in_progress`
- Owner：`Codex`
- Sidecar：`claudeminmax`

## 已完成

### Batch A：基线与主计划

- [x] `v1 -> v2` 统一计划收敛
- [x] `v3` 计划冻结：子系统边界、groundedness 权重、dataset schema、fallback 护栏、EvoMap vector 子阶段、feedback/scorer 接线

### Batch B：planning harness vertical

- [x] detector registry 落地
- [x] `visit_cooperation_prep` 等高频 profile 落地
- [x] interaction learning 第一版扩展
- [x] phase10 基础 validation 落地

### Batch C：KB / EvoMap 基线治理

- [x] BaseExtractor 统一入库门禁
- [x] ActivityExtractor 低信号 family dedup/skip
- [x] archive runner 落地
- [x] safe families live archive apply
- [x] `valid_from` live-safe backfill
- [x] `canonical_question` live-safe backfill
- [x] family-aware groundedness 权重落地
- [x] chain backfill 能力验证

## 进行中

### Batch D：Retrieval / Provenance

- [ ] 新增 `PLANNING_EXPLICIT_PATH`
- [ ] 给 `ScoredAtom` 增加 provenance/layer/source_bucket 标记
- [ ] planning explicit fallback 护栏落地
- [ ] `context_service` planning explicit surface 切换
- [ ] `context_assembler` provenance / formatting 对齐

### Batch E：EvoMap Vector Lane

- [ ] 增加 EvoMap vector path helper
- [ ] 增加 EvoMap vector store/table
- [ ] 增加 active/candidate/reviewed slice 向量化 runner
- [ ] 在 EvoMap retrieval 增加 vector lane + RRF 融合
- [ ] 跑 runtime vector probe

### Batch F：Feedback / Scorer

- [ ] advisor followup/correction -> `answer_feedback`
- [ ] atom usage -> telemetry
- [ ] KB scorer event emission
- [ ] telemetry / scorer tests

### Batch G：Dataset / Acceptance / Sidecar

- [ ] `claudeminmax` dataset assertion 扩展包
- [ ] `claudeminmax` KB 垃圾 / groundedness 抽样包
- [ ] negative / boundary eval
- [ ] live E2E acceptance

### Batch H：收口

- [ ] integrated targeted suite 全绿
- [ ] evidence artifacts 落盘
- [ ] completion / residual / walkthrough 落盘
- [ ] GitNexus detect_changes scoped 验证
- [ ] 提交并 closeout

## Sidecar 交付物

- [ ] `reingest_candidates`
- [ ] `family_quality_audit`
- [ ] `groundedness_sample_review`
- [ ] `dataset_assertion_extension`
- [ ] `fallback_provenance_redteam`

## 强制验收

1. `USER_HOT_PATH` 无回归
2. `PLANNING_EXPLICIT_PATH` recall/provenance 可解释
3. EvoMap vector lane 可用且 fail-open
4. `answer_feedback` 不再为 0 的静态路径
5. dataset/negative/live acceptance 通过
