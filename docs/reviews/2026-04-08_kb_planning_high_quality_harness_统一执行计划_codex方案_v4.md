# KB + Planning High-Quality Harness 统一执行计划 Codex方案 V4

Date: 2026-04-08

## 1. 结论

`v4` 是这条统一计划的执行完成版。

相对 [v3](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v3.md)，本版不再增加新叙事，只做三件事：

1. 把 `claudeminmax` 的 `KB 治理 / 重新入库前质检 / red-team review` workstream 显式写成已执行分工
2. 把最终 live blocker 收口成一条明确修复：`generic planning_general wrapper default` 不再压过 `visit_cooperation_prep` raw-ingress 强信号
3. 冻结最终验收口径与证据目录，作为后续实测的唯一 mouthpiece

## 2. 最终分工

### 2.1 Codex 主链 owner

我自己负责并已完成：

1. `BaseExtractor / ActivityExtractor` 入库门禁与 archive runner
2. `valid_from / canonical_question / chain backfill` 主链治理
3. `family-aware groundedness` 权重实现
4. `PLANNING_EXPLICIT_PATH`、retrieval provenance、guarded fallback
5. `EvoMap vector lane` 与 vectorization runner
6. `answer_feedback + KB scorer` 事件接线
7. `visit_cooperation_prep` ingress/profile/route/lane/live gate 主链修复
8. 最终集成验收与 closeout

### 2.2 `claudeminmax` sidecar owner

`claudeminmax` 负责并已交付：

1. dataset assertion extension
2. KB family / re-ingest candidates 抽样审计
3. groundedness sample review
4. fallback provenance red-team review
5. final sidecar review

本轮 sidecar 最新交付已复制进 acceptance pack：

- [reingest_candidates.md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/kb_planning_high_quality_harness_acceptance/20260408T123704Z/sidecar/reingest_candidates.md)
- [final_sidecar_review.md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/kb_planning_high_quality_harness_acceptance/20260408T123704Z/sidecar/final_sidecar_review.md)

## 3. 最终冻结的系统边界

### 3.1 EvoMap Knowledge

- DB: [evomap_knowledge.db](/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db)
- 热路径入口: [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py)
- 定位: `Promoted plane`
- 内容: `active / candidate / controlled staged_fallback`

### 3.2 KB Hub

- DB:
  - [kb_search.db](/home/yuanhaizhou/.openmind/kb_search.db)
  - [kb_vectors.db](/home/yuanhaizhou/.openmind/kb_vectors.db)
  - [kb_registry.db](/home/yuanhaizhou/.openmind/kb_registry.db)
- 检索入口: [hub.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/hub.py)
- 定位: `Evidence plane`
- 内容: 文档级 evidence / registry artifact / hybrid probe

### 3.3 Planning Reviewed Runtime Pack

- 生成与发布:
  - [planning_review_plane.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_review_plane.py)
  - [run_planning_review_maintenance.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_maintenance.py)
- 定位: `Curated plane`
- 内容: reviewed、显式发布、可直接注入的 planning slice

## 4. 最终执行项与完成状态

### 4.1 KB / EvoMap 治理

已完成：

1. extractor 入库质量门禁
2. activity family 低信号 dedup / skip
3. archive runner 与 live-safe archive apply
4. `valid_from` backfill
5. `canonical_question` backfill
6. `family-aware groundedness` 权重冻结与实现
7. chain backfill harness

### 4.2 Planning 高质量 harness

已完成：

1. detector registry
2. `visit_cooperation_prep / internal_meeting_prep / competitor_scan / customer_issue_response`
3. interaction learning v1 扩展
4. phase10 dataset 扩展到 `10 items / 30 cases`
5. `visit_cooperation_prep` live gate

### 4.3 Retrieval / Vector / Feedback

已完成：

1. `PLANNING_EXPLICIT_PATH`
2. provenance / retrieval layer / source bucket 标记
3. planning explicit guarded fallback
4. EvoMap vector lane 与 vectorization runner
5. `answer_feedback` 写入
6. `KB scorer` 事件接线与 smoke

### 4.4 Live blocker 修复

已完成：

1. `generic planning_general wrapper default` 不再压过 `visit_cooperation_prep`
2. API service 已重启并用 live gate 复验

关键代码：

- [scenario_packs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py)
- [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py)
- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
- [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [run_evomap_vectorization.py](/vol1/1000/projects/ChatgptREST/ops/run_evomap_vectorization.py)
- [run_evomap_feedback_event_smoke.py](/vol1/1000/projects/ChatgptREST/ops/run_evomap_feedback_event_smoke.py)
- [run_visit_cooperation_prep_live_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_visit_cooperation_prep_live_gate.py)
- [run_kb_planning_high_quality_harness_acceptance.py](/vol1/1000/projects/ChatgptREST/ops/run_kb_planning_high_quality_harness_acceptance.py)

## 5. 最终验收标准

本轮最终以以下门槛作为 `harness engineering` 完成判定：

1. `USER_HOT_PATH` 不回归
2. `PLANNING_EXPLICIT_PATH` 可解释且 provenance 可见
3. EvoMap vector lane 可用且 fail-open
4. `answer_feedback` 与 `KB scorer` 事件链能跑通
5. phase10 / readiness / live gate / unified acceptance 全绿
6. sidecar 质检 / re-ingest 候选包已纳入同一 acceptance pack

## 6. 最终证据

### 6.1 统一 acceptance pack

- [manifest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/kb_planning_high_quality_harness_acceptance/20260408T123704Z/manifest.json)
- [summary.md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/kb_planning_high_quality_harness_acceptance/20260408T123704Z/summary.md)

### 6.2 live route / lane / closure

- [visit live gate report.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/visit_cooperation_prep_live_gate/20260408T123656Z/report.json)
- [visit live gate report.md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/visit_cooperation_prep_live_gate/20260408T123656Z/report.md)

### 6.3 vector / feedback

- [vector summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/kb_planning_high_quality_harness_acceptance/20260408T123704Z/evomap_vectorization/20260408T123708Z/summary.json)
- [feedback smoke summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/kb_planning_high_quality_harness_acceptance/20260408T123704Z/feedback_smoke/20260408T123911Z/summary.json)

### 6.4 planning harness / phase10

- [phase10 report_v1.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/kb_planning_high_quality_harness_acceptance/20260408T123704Z/ingress_validation/report_v1.json)
- [planning readiness manifest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/kb_planning_high_quality_harness_acceptance/20260408T123704Z/planning_readiness/manifest.json)

## 7. 非目标

本轮完成的不是“全仓库一切问题都已解决”，而是：

1. `KB / planning harness` 这条统一主线达到当前阶段的 production-grade acceptance
2. `visit/cooperation prep` 这一条 OpenClaw 高质量 vertical 达到 live 可验状态

仍不在本轮范围内：

1. 全域 task family 泛化
2. 全量 EvoMap 104K atoms 向量化
3. repo 全量历史回归债清零
