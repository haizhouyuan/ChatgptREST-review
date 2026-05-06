# KB + Planning High-Quality Harness 统一执行计划 Codex方案 V2

Date: 2026-04-08

## 1. 结论

这版 `v2` 不推翻 [v1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v1.md)，而是在其结构上吸收最新评审结论，把执行前必须冻结的模糊点写成明确合同。

本轮统一计划继续只维护一条主线：

1. `KB / EvoMap / vector / promotion / feedback` 的知识治理
2. `planning / OpenClaw / advisor / coding-agent` 的高质量 harness

目标仍然不是扩系统概念，而是让这两条线按依赖关系推进：

1. 先修知识底座与 metadata
2. 再加固 harness 质量
3. 再做 knowledge-aware 联动与 live acceptance

## 2. 独立判断

我接受上一轮统一计划的主体结构，也接受最新评审提出的 5 个补充点，并额外补一条反馈接线要求。

### 2.1 接受的评审点

1. `P0.2` 需要明确 `KB Hub`、`EvoMap`、`planning reviewed runtime pack` 的真实边界，不能只用抽象 `plane` 名称概括。
2. `P2.1` 必须冻结 `family-aware groundedness` 的数值权重，不留实现时自由发挥空间。
3. `P3.1` 必须定义 dataset case 的 assertion schema，而不是只说“扩 10-15 个 case”。
4. `P5.1` 对 `candidate/staged fallback` 的风险边界必须明确写死。
5. `P5` 必须新增显式的 `EvoMap active/candidate vectorization` 步骤。

### 2.2 额外补充

除了上述 5 点，这版 `v2` 还明确补充：

1. `answer_feedback` 回写和 `KB scorer` 事件触发
2. `claudeminmax` 的 KB sidecar workstream，从“概念性 sidecar”升级成可分派执行包
3. 文档写作规则：不再新增高层 superseding strategy docs，统一在主计划的版本演进里收口

## 3. 系统边界冻结

### 3.1 三条 plane 与两套检索子系统

为避免 `plane` 概念掩盖真实运行结构，这里明确同时冻结：

1. **EvoMap Knowledge 子系统**
   - DB: [evomap_knowledge.db](/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db)
   - 检索入口: [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py)
   - 主要消费方: [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
   - 默认定位: `Promoted plane`
   - 目标内容: `active / candidate` 的结构化 atoms

2. **KB Hub 子系统**
   - DB: [kb_search.db](/home/yuanhaizhou/.openmind/kb_search.db)
   - 向量 DB: [kb_vectors.db](/home/yuanhaizhou/.openmind/kb_vectors.db)
   - Registry DB: [kb_registry.db](/home/yuanhaizhou/.openmind/kb_registry.db)
   - 检索入口: [hub.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kb/hub.py)
   - 默认定位: `Evidence plane`
   - 目标内容: 文档级 evidence、artifact、registered docs

3. **Planning Reviewed Runtime Pack**
   - fresh bundle 与 manifest 由 reviewed maintenance 生成
   - 默认定位: `Curated plane`
   - 目标内容: reviewed、显式发布、可直接注入的 planning slice

### 3.2 retrieval surface 冻结

1. `USER_HOT_PATH`
   - 仍然以 EvoMap `active` 为主
   - 本轮禁止直接改成 staged-open

2. `planning explicit surface`
   - 可以消费 `Curated plane`
   - 可以在受控条件下接入 `Promoted plane`
   - 只在本轮显式 planning 任务上讨论 fallback

3. `KB evidence surface`
   - 只作为 `Evidence plane`
   - 不冒充 `active` 级可信度

## 4. 角色与分工

### 4.1 Codex 主链 owner

以下工作必须由我主导：

1. `EvoMap / KB Hub / runtime pack` 的边界冻结
2. groundedness / promotion / chain / fallback 主链语义
3. EvoMap 向量化与 retrieval 改造
4. `answer_feedback` 与 `KB scorer` 事件接线
5. OpenClaw / planning harness 主链改动
6. 最终集成、验收、提交与 closeout

### 4.2 `claudeminmax` sidecar owner

`claudeminmax` 负责边界清晰、可并行、可核验的 sidecar 工作：

1. KB 垃圾家族抽样与归档候选报告
2. re-ingest 前数据质检与 family 级审计
3. groundedness sample review 与 failure taxonomy
4. dataset 扩展：正例 / 负例 / 边界例
5. closure / provenance / fallback 的 red-team review
6. before/after 评测汇总与独立复核

### 4.3 写作方案

文档写作也按主链 / sidecar 分开：

1. **Codex**
   - 维护主计划 `v2+`
   - 维护每个 phase 的 walkthrough
   - 维护最终 completion / residual risk 文档

2. **`claudeminmax`**
   - 只产出 sidecar 审计包、数据集草案、review packet
   - 不产出 superseding master plan
   - 不重写主计划

## 5. Phase 0：冻结基线与合同

### P0.1 当前基线冻结

Owner:

- Codex

动作：

1. 冻结 atoms / promotion_status / chain / metadata 覆盖
2. 冻结 KB FTS / vectors / registry 覆盖
3. 冻结 planning harness 的当前基线

验收：

- 每个后续 phase 都能做 before/after 对比

### P0.2 子系统边界与 plane 合同冻结

Owner:

- Codex

动作：

1. 文档化 `EvoMap`、`KB Hub`、`runtime pack` 的 DB、入口、消费方
2. 为三条 plane 冻结：
   - source family allowlist
   - retrieval surface
   - prompt 注入上限
   - freshness / quality 指标

验收：

- `plane` 不再掩盖真实子系统边界
- 后续实现不再混淆 `runtime pack`、`EvoMap promoted plane`、`KB evidence plane`

## 6. Phase 1：止血与 KB sidecar 审计

### P1.1 垃圾家族治理

Owner:

- Codex：策略、门禁、归档 runner
- `claudeminmax`：家族清单、误伤审计、dry-run 报告

动作：

1. 抽样识别垃圾 family：
   - `tool.completed` / 低信号 activity events
   - 通用标题：`结论`、`Files`、`Test Results`
   - `.venv` / 路径噪音 / 纯命令残片
2. 生成 dry-run 报告
3. 做可逆 `archive`
4. 在 extractor 层加门禁：
   - min content length
   - title specificity
   - 路径黑名单
   - family / content hash dedup

验收：

- 新一轮 ingest 后垃圾家族新增量接近 0
- dry-run 可解释、可回滚

### P1.2 KB sidecar 重新入库 / 质检包

Owner:

- `claudeminmax`：主责 sidecar 审计
- Codex：确认审批门槛与执行切换条件

动作：

1. 输出 family 级 re-ingest 候选清单
2. 输出 source family / bucket 级数据质检报表
3. 输出 dry-run -> approval -> execute 的切换条件
4. 输出 re-ingest 前后指标对比模板

交付物：

1. `reingest_candidates`
2. `family_quality_audit`
3. `rollback_and_approval_notes`
4. `before_after_metric_template`

验收：

- KB 治理 / 重新入库 / 数据质检不再只是 sidecar 概念，而是明确工作包

### P1.3 metadata 回填

Owner:

- Codex
- `claudeminmax`：只读 mismatch 审核

动作：

1. 回填 `valid_from`
2. 生成 / 回填 `canonical_question`
3. 保持 `scope_project` 风险边界，不做 blind write

验收：

- `valid_from` 缺失率显著下降
- `canonical_question` 缺失率显著下降

## 7. Phase 2：promotion / groundedness / chain 疏通

### P2.1 family-aware groundedness 权重冻结

Owner:

- Codex

冻结首版权重：

1. `planning family`
   - `path = 0.40`
   - `staleness = 0.30`
   - `service = 0.15`
   - `code_symbol = 0.15`

2. `code / procedure family`
   - `path = 0.40`
   - `service = 0.20`
   - `staleness = 0.15`
   - `code_symbol = 0.25`

规则：

1. 本轮禁止 `code_symbol = 0`
2. 本轮禁止 `quality_auto = groundedness`
3. 样本运行后只能在 `v3+` 文档里调整，不允许实现时临场改口

测试：

1. groundedness checker unit tests
2. planning vs code family score expectation tests
3. sampled audit diff

验收：

- planning 高质量 atoms 不再因 `code_symbol` 被系统性误伤
- code/procedure atoms 仍保留严格校验

### P2.2 bulk scoring / promotion runner

Owner:

- Codex：runner、scheduler、movement accounting
- `claudeminmax`：failure taxonomy、throughput review

动作：

1. 把 planning bulk scoring / promotion 做成稳定运行面
2. 记录：
   - scanned
   - scored
   - candidate promotions
   - active promotions
   - failure reasons
3. 区分 reviewed maintenance 与 bulk promotion

验收：

- `candidate + active` 有持续移动
- `groundedness_audit` 不再停滞

### P2.3 chain_builder backfill

Owner:

- Codex

动作：

1. 在 metadata 回填后运行 chain backfill
2. 建立 supersession / chain 关系
3. 让旧版本可降级、可解释

验收：

- `chain_id_nonempty` 不再为 0
- 能观察到 superseded/version family

## 8. Phase 3：planning 高质量 harness 加固

### P3.1 dataset 扩展与 assertion schema

Owner:

- `claudeminmax`：case 设计主责
- Codex：最终筛选、接入 harness

case 数量：

- 至少 10-15 个 case

case 类别：

1. 正例
   - 来访准备
   - 合作洽谈
   - 供应商交流
   - 资本牵线会前准备
2. 负例
   - 内部周会准备
   - 纯项目诊断
   - 普通研究请求
3. 边界例
   - 投诉处理 vs visit prep
   - 质量问题来访 vs project diagnosis

每个 case 必须包含：

1. `expected_profile`
2. `expected_not_profile`
3. `expected_route_hint`
4. `expected_execution_preference`
5. `expected_clarify_required`
6. `expected_closure_sections`
7. `expected_normalization_signals`

验收：

- phase10 不再只有 2 个样本
- 正例 / 负例 / 边界例都有明确 assertion

### P3.2 interaction learning 加固

Owner:

- Codex：实现
- `claudeminmax`：marker / signal coverage review

动作：

1. 扩 correction markers：
   - 太长了
   - 太短了
   - 重点不对
   - 先告诉我怎么回对方
   - 我要的不是这个
   - 质量不够高
2. 扩 signal 维度：
   - brevity preference
   - reply-first preference
   - focus correction
3. 增加 negative tests
4. 增加衰减 / 冲突解决
5. 预留 user-scoped 演进点

验收：

- 高频纠正信号不再大量漏掉
- 正常对话不会误触发 correction

### P3.3 live E2E harness

Owner:

- Codex
- `claudeminmax`：red-team prompts 与结果复核

动作：

1. 新增 `visit/cooperation prep` live E2E gate
2. 实走：
   - ingress
   - normalization
   - route
   - execution lane
   - closure

验收：

- 至少 1 条 live 主链稳定通过
- 验证完整闭环输出，不只是 contract fields

## 9. Phase 4：框架泛化

### P4.1 detector framework

Owner:

- Codex

动作：

1. 把 `_derive_ingress_normalization()` 升级成 detector registry
2. 支持：
   - detector 接口
   - 优先级
   - 冲突解决
   - explainability

第一批 detectors：

1. `visit_cooperation_prep`
2. `internal_meeting_prep`
3. `competitor_scan`
4. `customer_issue_response`

验收：

- 新任务族不再必须手改核心 if-else

### P4.2 新任务族 profile

Owner:

- Codex：主实现
- `claudeminmax`：样本与 closure review

动作：

1. 新增 2-3 个高频 profile
2. 每个 profile 都有：
   - normalization signals
   - clarify policy
   - route / execution preference
   - closure sections
   - acceptance cases

验收：

- 不再只有单一 `visit_cooperation_prep` vertical

## 10. Phase 5：KB / planning / OpenClaw 联动

### P5.1 retrieval surface 与 fallback 风险护栏

Owner:

- Codex

动作：

1. 让 planning harness 真正吃到治理后的知识 plane
2. 增加 diagnostics：
   - plane 来源
   - promotion 层级
   - fallback provenance

受控 fallback 规则：

1. 只在 `planning explicit surface`
2. 不影响 `USER_HOT_PATH`
3. 只允许 allowlist bucket
4. 只允许 `quality_auto >= 0.7`
5. 最多混入 3 条 fallback
6. 结果必须显式标记：
   - `candidate_fallback` 或 `staged_fallback`
   - `plane`
   - `bucket`

验收：

- harness 成功时能解释知识来源
- fallback 不会淹没 `active`

### P5.2 KB hybrid 稳定化

Owner:

- Codex：运行时统一、检索合同
- `claudeminmax`：probe case 与质量 review

动作：

1. 统一 `.venv` 与普通脚本运行时的 embedding 行为
2. 扩高价值 KB vectors：
   - reviewed planning docs
   - high-value evidence docs
3. 提高 provenance 完整率

验收：

- 向量不再只是偶尔可用
- 命中不再主要是泛 research 噪音

### P5.3 EvoMap active/candidate 向量化

Owner:

- Codex

动作：

1. 为 EvoMap 新增显式向量表 / 通道
2. 第一阶段仅向量化：
   - `active`
   - `candidate`
   - reviewed planning slice
3. EvoMap retrieval 增加 vector lane，但保留 promotion gate

本轮禁止：

1. 直接全量向量化 104K atoms
2. 在 metadata / groundedness 未收敛前做全量向量扩张

验收：

- EvoMap 不再是纯 FTS5
- promoted slice 具备基础语义召回能力

### P5.4 answer_feedback 与 KB scorer 接线

Owner:

- Codex
- `claudeminmax`：feedback case review

动作：

1. 把 advisor followup / correction 写入 `answer_feedback`
2. 记录：
   - query
   - retrieved ids
   - used_in_answer
   - followup/correction type
3. 为 KB artifact scorer 发出可消费事件

验收：

- `answer_feedback` 不再长期为 0
- interaction learning 与知识质量改进不再完全脱钩

## 11. Phase 6：统一验收

### 6.1 测试矩阵

必须同时跑：

1. unit
   - extractor / groundedness / detector / interaction learning / scenario pack
2. contract
   - task intake / route / readiness / multi-ingress validation
3. integration
   - promotion runner / runtime pack refresh / kb probe / telemetry writeback
4. live
   - 至少 1 条 visit prep E2E
   - 至少 1 条 planning explicit knowledge E2E

### 6.2 验收标准

#### A. 知识治理

1. 垃圾家族新增量明显下降
2. `valid_from` / `canonical_question` 缺失率下降
3. `groundedness_audit` 覆盖增长
4. `candidate + active` 有持续移动
5. `chain_id` 不再为 0
6. `answer_feedback` 不再为 0

#### B. planning harness

1. phase10 扩展数据集通过
2. negative / boundary cases 不误判
3. interaction learning 覆盖提升
4. live E2E 稳定通过

#### C. 联动效果

1. planning query 的 context 质量提升可解释
2. OpenClaw 输入到 closure 的完整链路稳定
3. 失败时能解释卡在 ingress、route、executor、knowledge plane 哪一层
4. EvoMap promoted slice 具备基础向量召回

## 12. 并行执行建议

### 批次 1：立即并行

- Codex：
  - `P0.2` 边界与合同冻结
  - `P1.1` 门禁与归档 runner
  - `P1.3` metadata 回填设计
- `claudeminmax`：
  - `P1.2` KB sidecar re-ingest / 质检包
  - `P3.1` dataset 草案
  - 垃圾 family / groundedness 抽样审计

### 批次 2：主链落地 + sidecar 复核

- Codex：
  - `P2.1` 权重实现
  - `P2.2` promotion runner
  - `P3.2` interaction learning
  - `P4.1` detector framework
- `claudeminmax`：
  - groundedness review
  - marker / signal coverage review
  - closure / provenance red-team review

### 批次 3：集成联动

- Codex：
  - `P5.1` fallback 与 surface 对齐
  - `P5.2` KB hybrid 稳定化
  - `P5.3` EvoMap 向量化
  - `P5.4` feedback / scorer 接线
- `claudeminmax`：
  - probe case review
  - fallback visibility review
  - telemetry sanity review

### 批次 4：最终验收

- Codex：
  - 统一 acceptance pack
  - final closeout
- `claudeminmax`：
  - 独立 review packet
  - post-run critique

## 13. 最终冻结

一句话：

> 这轮最正确的路径不是再重写一套战略叙事，而是在现有统一计划上补齐执行前的模糊空间：明确 KB 与 EvoMap 边界、冻结 groundedness 权重、把 `claudeminmax` 的 KB sidecar 包写实、收紧 fallback 风险、补上 EvoMap 向量化和 `answer_feedback` 接线，然后由 Codex 主导主链、`claudeminmax` 并行做 sidecar 审计与评测。
