# KB + Planning High-Quality Harness Execution TODO Master V2

Date: 2026-04-08

## 目标

本 TODO 文档继续作为执行锚点，用于防止剩余主链在长上下文里丢失。

唯一主计划仍然是：

- [统一执行计划 Codex方案 V2](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v2.md)

## 总状态

- 状态：`in_progress`
- Owner：`Codex`
- Sidecar：`claudeminmax`

## 已完成

### Batch A：执行锚点与计划冻结

- [x] 生成 `v2` 主计划与 `walkthrough v2`
- [x] 明确 `Codex / claudeminmax` 分工
- [x] 明确 KB sidecar workstream
- [x] 把执行 TODO 落盘

### Batch B：planning harness engineering

- [x] 扩 phase10 数据集到 10-15 个 case
- [x] 定义并落地 dataset assertion schema
- [x] interaction_learning 扩 marker 与 signal 维度
- [x] interaction_learning 增加负例测试
- [x] interaction_learning 增加衰减 / 冲突解决
- [x] detector framework 从 visit-only 特例升级为 registry
- [x] 扩 2-3 个新任务族 profile
- [ ] 增加 visit/cooperation prep 的更强 E2E / acceptance 覆盖

### Batch C：KB / EvoMap 治理

- [x] 给 BaseExtractor 加统一入库门禁
- [x] 给 ActivityExtractor 加 family dedup / low-signal skip
- [x] 为垃圾 family 增加 dry-run / archive runner
- [x] 对 `low_signal_tool_completed + path_blacklist` 做 live apply 归档并补后态证据
- [x] 回填 / 生成 `valid_from`
- [x] 回填 / 生成 `canonical_question`
- [x] 实现 family-aware groundedness 权重
- [x] 更新 groundedness / promotion 相关测试
- [x] 跑 chain builder backfill 能力并补测试
- [x] 完成 live-safe metadata backfill
- [x] 暴露 full-scope chain build 风险，不直接 live apply

## 进行中

### Batch D：knowledge-aware retrieval

- [ ] planning explicit surface 的 fallback 护栏落地
- [ ] fallback provenance / layer 标记落地
- [ ] KB hybrid 运行时一致性加固
- [ ] EvoMap active/candidate vector table 与索引落地
- [ ] EvoMap retrieval 增加 vector lane
- [ ] 对 active/candidate/reviewed slice 建立向量化 runner

### Batch E：feedback / scorer / observability

- [ ] 把 advisor followup / correction 写入 `answer_feedback`
- [ ] 为 KB scorer 发出可消费事件
- [ ] 增加 telemetry / feedback 测试
- [ ] 增加 before/after acceptance ledger

### Batch F：最终验收

- [ ] unit / contract / integration / live 目标套件通过
- [ ] 生成执行 walkthrough
- [ ] 生成 completion summary
- [ ] 生成 residual risk note
- [ ] 提交全部变更并执行 scoped closeout

## 当前判断

1. metadata 基线已经补平到可继续做 retrieval / vector / feedback
2. full-scope chain build 仍然风险过大，后续必须做 controlled scope
3. planning bulk promotion 当前 top slice 还被 `planning_aios / planning_misc` 主导，说明 fallback 与 activation 仍需 guardrail

