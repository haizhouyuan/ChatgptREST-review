# KB + Planning High-Quality Harness 统一执行计划 Codex方案 V3

Date: 2026-04-08

## 1. 目标

`v3` 继续沿用 [v2](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v2.md) 的主结构，但把执行前仍可能产生歧义的点全部冻结到实施级别。

唯一主线不变：

1. 修复 `KB / EvoMap / vector / promotion / feedback` 的知识治理闭环
2. 加固 `planning / OpenClaw / advisor / coding-agent` 的高质量 harness

本轮原则：

1. 不新增“子系统叙事”
2. 不重建已有执行基础设施
3. 只在现有主链上加策略、门禁、向量通道、反馈接线和验收

## 2. 独立判断

我接受上一轮评审提出的 5 个补充点，并把它们收成 `v3` 的强制执行条件：

1. 明确 `KB Hub`、`EvoMap`、`planning reviewed runtime pack` 的真实子系统边界
2. 冻结 `family-aware groundedness` 权重
3. 定义 dataset assertion schema
4. 写死 `candidate/staged fallback` 风险护栏
5. 显式纳入 `EvoMap active/candidate vectorization`
6. 补上 `answer_feedback + KB scorer event wiring`

## 3. 子系统边界冻结

### 3.1 EvoMap Knowledge

- DB: [evomap_knowledge.db](/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db)
- 检索入口: [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py)
- 注入入口:
  - [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
  - [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
- 默认定位: `Promoted plane`
- 目标内容: `active / candidate` 的结构化 atoms

### 3.2 KB Hub

- DB:
  - [kb_search.db](/home/yuanhaizhou/.openmind/kb_search.db)
  - [kb_vectors.db](/home/yuanhaizhou/.openmind/kb_vectors.db)
  - [kb_registry.db](/home/yuanhaizhou/.openmind/kb_registry.db)
- 检索入口: [hub.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/hub.py)
- 默认定位: `Evidence plane`
- 目标内容: 文档级 evidence、artifact、registered docs

### 3.3 Planning Reviewed Runtime Pack

- 生成入口:
  - [planning_review_plane.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_review_plane.py)
  - [run_planning_review_maintenance.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_maintenance.py)
- 消费入口:
  - [planning_runtime_pack_search.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_runtime_pack_search.py)
  - [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
- 默认定位: `Curated plane`
- 目标内容: reviewed、显式发布、可直接注入的 planning slice

## 4. Retrieval Surface 冻结

### 4.1 `USER_HOT_PATH`

- 仍然是 EvoMap `active-only`
- 本轮禁止改成 staged-open

### 4.2 `PLANNING_EXPLICIT_PATH`

- 这是本轮新增显式 surface
- 只给 planning 显式任务使用
- 可消费：
  - reviewed runtime pack
  - EvoMap `active`
  - 受控 `candidate/staged fallback`

### 4.3 `KB evidence surface`

- 继续由 KB Hub 提供
- 用于宽召回、证据补强、语义扩展
- 不冒充 `active` 级可信度

## 5. 角色与并行

### 5.1 Codex 主链 owner

我自己负责：

1. plan/TODO `v3`
2. retrieval surface / provenance / fallback 主链
3. EvoMap 向量表、向量化 runner、retrieval vector lane
4. `answer_feedback` 与 `KB scorer` 接线
5. planning harness 与最终验收

### 5.2 `claudeminmax` sidecar owner

`claudeminmax` 负责可并行、边界清晰的 sidecar：

1. dataset 扩展：正例 / 负例 / 边界例
2. KB 垃圾 family 抽样与 dry-run review
3. groundedness sample review
4. fallback / provenance 红队复核
5. before/after 评测汇总

### 5.3 并行批次

#### Batch A：立即并行

- Codex：`v3` 计划冻结
- `claudeminmax`：dataset assertion schema 草案 + KB family 抽样

#### Batch B：主链实现 + sidecar 复核

- Codex：retrieval / vector / feedback 实现
- `claudeminmax`：负例/边界例验证 + fallback/provenance review

#### Batch C：集成验收

- Codex：集成测试、live probe、closeout
- `claudeminmax`：独立终态 review

## 6. 冻结的数值与 schema

### 6.1 groundedness 权重

#### `planning family`

- `path = 0.40`
- `staleness = 0.30`
- `service = 0.15`
- `code_symbol = 0.15`

#### `code / procedure family`

- `path = 0.40`
- `service = 0.20`
- `staleness = 0.15`
- `code_symbol = 0.25`

规则：

1. 本轮禁止 `code_symbol = 0`
2. 本轮禁止 `quality_auto = groundedness`
3. 后续权重变更只能落在新版本文档，不允许实现中即兴漂移

### 6.2 dataset case assertion schema

所有新的 harness dataset case 必须包含：

1. `expected_profile`
2. `expected_not_profile`
3. `expected_route_hint`
4. `expected_execution_preference`
5. `expected_clarify_required`
6. `expected_closure_sections`
7. `expected_normalization_signals`

### 6.3 fallback guardrails

本轮只允许在 `PLANNING_EXPLICIT_PATH` 开放受控 fallback。

强制条件：

1. 不修改 `USER_HOT_PATH`
2. fallback 只允许 planning 显式任务
3. 只允许 allowlist bucket
4. `quality_auto >= 0.7`
5. 结果必须显式标记：
   - `retrieval_layer`
   - `retrieval_source`
   - `promotion_status`
   - `source_bucket`
6. fallback 最多混入 `3` 条

## 7. Phase 1：retrieval / provenance / planning explicit surface

Owner:

- Codex 主责
- `claudeminmax` 做 negative/boundary review

动作：

1. 在 [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py) 新增 `PLANNING_EXPLICIT_PATH`
2. 给 `ScoredAtom` 增加 provenance / layer / source bucket 元数据
3. 只在 planning explicit surface 上启用受控 fallback
4. 更新：
   - [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
   - [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
5. 保持 consult/default hot path 现有语义不变

测试：

1. retrieval surface unit tests
2. provenance markers tests
3. planning explicit fallback negative tests
4. harness dataset 扩展验证

验收：

1. planning explicit surface 可命中 active + 受控 fallback
2. default hot path 不受影响
3. 输出 provenance 可区分 `active / candidate / staged_fallback / planning_pack`

## 8. Phase 2：EvoMap 向量化与 vector lane

Owner:

- Codex 主责
- `claudeminmax` 做 corpus/命中质量 sidecar review

动作：

1. 在 [openmind_paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/openmind_paths.py) 增加 EvoMap vector path helper
2. 新增 EvoMap vector store / vectorization runner
3. 首批只向量化：
   - EvoMap `active`
   - EvoMap `candidate`
   - reviewed planning slice
4. 在 EvoMap retrieval 里增加可选 vector lane + RRF 融合
5. vector lane fail-open，不影响 FTS 主路

测试：

1. vector table CRUD / persistence tests
2. retrieval fusion tests
3. runtime probe

验收：

1. EvoMap 不再是 `0 vectors`
2. active/candidate slice 有稳定向量覆盖
3. vector lane 不影响 default FTS fail-open 行为

## 9. Phase 3：feedback / scorer / observability

Owner:

- Codex 主责
- `claudeminmax` 做 event/red-team review

动作：

1. advisor followup / correction 写入 `answer_feedback`
2. 将 atom usage 显式写回 telemetry
3. 为 `KB scorer` 发出可消费事件，不和 `interaction_learning` 混用
4. 生成 before/after ledger

测试：

1. `answer_feedback` API / runtime tests
2. scorer event emission tests
3. negative tests：正常对话不应误记 corrected/followup

验收：

1. `answer_feedback` 不再停在 `0`
2. followup/correction 能驱动 telemetry 留痕
3. KB scorer 能收到事件，不再空转

## 10. Phase 4：planning harness engineering 收口

Owner:

- Codex 主责
- `claudeminmax` 做 dataset / red-team

动作：

1. 扩 phase10 / 后续 harness dataset 到 `10-15+` case
2. 补正例 / 负例 / 边界例
3. 增加真正的 live E2E acceptance

验收：

1. 单 profile vertical 不再只靠 2 个样本
2. end-to-end 路由到 `advisor -> coding_agent -> codex -> closure` 的链路可验证

## 11. 最终验收标准

### 11.1 单元 / 合同 / 集成

必须全部通过：

1. retrieval / vector / telemetry / context 相关 targeted suites
2. planning harness targeted suites
3. dataset validation runners

### 11.2 运行时 acceptance

必须生成并保留：

1. retrieval before/after evidence
2. vector runtime probe
3. fallback provenance evidence
4. feedback/scorer evidence
5. planning harness readiness pack

### 11.3 终态判断

只有同时满足以下条件才可宣告这一波完成：

1. default hot path 未被回归
2. planning explicit surface 有明显 recall 改善
3. EvoMap vector lane 已可用
4. feedback/scorer 路径已接通
5. dataset / negative / live acceptance 都过

## 12. 写作规则

1. 继续使用主计划版本演进，不再开 superseding strategy doc
2. sidecar 只产出审计包 / review packet / dataset 补充，不重写 master plan
3. 每个有意义的主链改动继续单独 commit
