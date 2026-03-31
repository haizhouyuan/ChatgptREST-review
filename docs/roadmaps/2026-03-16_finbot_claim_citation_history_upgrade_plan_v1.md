# 2026-03-16 Finbot Claim/Citation/History Upgrade Plan v1

## Goal

把 `finbot` 从“投资人可读的多 lane dossier”继续升级成“投资人可追溯、可比较、可演化回放”的研究系统，重点一次性补齐三块：

1. `claim -> citation` 从启发式 source 绑定升级成稳定引用对象
2. source/KOL 反馈回写到长期评分，而不是只在单次 dossier 里临时展示
3. thesis / opportunity / expression 的历史 diff 与演化轨迹可见

## Product Standard

达标后的 investor dashboard 需要做到：

- 任何一个机会页都能看到稳定的 `claim ledger`
- 每条 claim 都带稳定 `claim_id`
- 每条 claim 都能点开对应 citation 对象，而不是只展示 source 名称
- source/KOL 页能回答：
  - 它历史上支持过哪些 claim
  - 命中过哪些主题
  - 最近是强化还是降级
- 主题页和机会页都能看到：
  - 上次结论是什么
  - 这次变了什么
  - 是证据变了、表达变了、还是 posture 变了

## Scope

### A. Claim/Citation Object Layer

- 在 research package artifact 内新增稳定对象：
  - `claim_objects`
  - `citation_objects`
  - `claim_citation_edges`
- 支持字段：
  - `claim_id`
  - `claim_text`
  - `claim_kind`
  - `evidence_grade`
  - `status`
  - `citation_id`
  - `source_id`
  - `evidence_snippet`
  - `support_type`
  - `confidence`
- dashboard 页面改成优先渲染这些对象；旧的启发式绑定只保留兜底

### B. Long-Term Source/KOL Scoring

- 引入持久化 scorecard store
- 聚合维度：
  - `supported_claim_count`
  - `anchor_claim_count`
  - `contradicted_claim_count`
  - `theme_hit_count`
  - `validated_case_count`
  - `recent_activity_at`
  - `quality_band`
- 更新路径：
  - 每次 research package 落盘时回写 scorecard
  - 新 package 与旧 package 对同一 source 的贡献度形成增量

### C. History Diff / Thesis Evolution

- 为 theme / opportunity / source 建历史快照索引
- 渲染差异：
  - `decision changed`
  - `best expression changed`
  - `new supporting claim`
  - `new risk`
  - `source upgraded / downgraded`
- investor 页面显示：
  - `What changed since last run`
  - `Thesis evolution`
  - `Why the posture changed`

## Implementation Plan

### Pass 1: Data Contract

- 扩 research package schema
- 增 `claim_objects / citation_objects / claim_citation_edges`
- 增 source score persistence helpers
- 增 history snapshot / diff helpers

### Pass 2: Rendering

- 机会页：
  - `Claim Ledger` 升级成 claim object table
  - `Supporting sources` 升级成 citation list
  - 新增 `What changed`
- 主题页：
  - 新增 `Thesis evolution`
  - 新增 `Expression changes`
- source 页：
  - 新增 `Claim support history`
  - 新增 `Quality trend`

### Pass 3: Validation

- 单元测试：
  - claim/citation object generation
  - scorecard persistence / merge
  - history diff rendering
- live smoke：
  - 至少验证一个 frontier opportunity
  - 至少验证一个成熟主题
  - 至少验证一个 source detail page

## Out of Scope

- 完整图数据库化
- 全量 KB / EvoMap 重构
- 多 agent 长驻拆分
- 完整估值模型平台

## Success Criteria

- investor dashboard 不再依赖启发式 source fallback 才能讲清 claim
- source 页能看到长期贡献，不是单次摘要
- 主题 / 机会页能解释“为什么现在和上次不一样”
- `finbot` 连续跑出来的结果对人类来说不是一堆新报告，而是一个持续演化的研究台账
