# KB + Planning High-Quality Harness Execution TODO Master V1

Date: 2026-04-08

## 目标

本 TODO 文档是当前执行锚点，用来防止长链任务在上下文压缩后丢主线。

本轮只以 [统一执行计划 Codex方案 V2](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v2.md) 为唯一主计划，不再另起 superseding strategy docs。

## 总状态

- 状态：`in_progress`
- Owner：`Codex`
- Sidecar：`claudeminmax`

## 执行清单

### Batch A：执行锚点与计划冻结

- [x] 生成 `v2` 主计划与 `walkthrough v2`
- [x] 明确 `Codex / claudeminmax` 分工
- [x] 明确 KB sidecar workstream
- [x] 把本 TODO 文档落盘并作为执行锚点

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
- [ ] 给 ActivityExtractor 加 family dedup / low-signal skip
- [x] 为垃圾 family 增加 dry-run / archive runner
- [x] 对 `low_signal_tool_completed + path_blacklist` 做 live apply 归档并补后态证据
- [ ] 回填 / 生成 `valid_from`
- [ ] 回填 / 生成 `canonical_question`
- [ ] 实现 family-aware groundedness 权重
- [ ] 更新 groundedness / promotion 相关测试
- [ ] 跑 chain builder backfill 能力并补测试

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

## 执行原则

1. 每个有意义改动独立提交
2. 不覆盖旧版文档
3. 不碰与本轮无关的既有脏改
4. 主链实现由 Codex 收口，sidecar 只做辅助审计/评测/红队
