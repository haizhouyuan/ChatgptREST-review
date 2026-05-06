# KB + Planning High-Quality Harness 统一执行计划 Codex方案 Walkthrough V2

Date: 2026-04-08

## 本次输出

在 [v1 统一执行计划](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v1.md) 的基础上，新建：

- [2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v2.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v2.md)

## 为什么升级到 V2

上一版 `v1` 已经把 `KB 治理` 和 `planning harness` 收成一个统一计划，但对执行来说还有 6 个模糊点：

1. `plane` 与真实检索子系统边界写得不够细
2. `family-aware groundedness` 只有方向，没有冻结数值
3. dataset 扩展说了数量，没有写 assertion schema
4. `candidate/staged fallback` 的风险护栏不够硬
5. `EvoMap` 向量化没有被写成显式步骤
6. `answer_feedback` 与 `KB scorer` 的接线没有被纳入主计划

另外，用户明确同意把 `claudeminmax` 正式纳入 `KB 治理 / 重新入库 / 数据质检` 的 sidecar workstream，这件事也需要从“原则性分工”升级成“明确工作包”。

## 这次做了什么

### 1. 把 plane 概念和真实子系统拆开

`v2` 明确区分：

1. `EvoMap Knowledge`
2. `KB Hub`
3. `planning reviewed runtime pack`

每个子系统都写了：

1. DB 路径
2. 检索入口
3. 主要消费方
4. 对应 plane 定位

### 2. 冻结 groundedness 数字权重

`v2` 直接把首版 `family-aware groundedness` 写成数值表，不再留实现时口头解释空间：

1. `planning family`
2. `code / procedure family`

同时明确本轮禁止：

1. `code_symbol = 0`
2. `quality_auto = groundedness`

### 3. 把 dataset assertion schema 写实

`v2` 不只要求扩 case 数量，还强制每个 case 带：

1. `expected_profile`
2. `expected_not_profile`
3. `expected_route_hint`
4. `expected_execution_preference`
5. `expected_clarify_required`
6. `expected_closure_sections`
7. `expected_normalization_signals`

### 4. 把 fallback 风险边界写死

`v2` 明确规定：

1. 只在 `planning explicit surface`
2. 不改 `USER_HOT_PATH`
3. 只允许 allowlist bucket
4. `quality_auto >= 0.7`
5. 最多 3 条 fallback
6. 必须显式标记 provenance

### 5. 补上 EvoMap 向量化

`v2` 新增 `P5.3`：

1. 先只做 `active + candidate + reviewed planning slice`
2. 禁止直接全量向量化 `104K` atoms
3. 要让 EvoMap retrieval 从“纯 FTS5”升级成“promoted slice 有基础语义召回”

### 6. 把 `claudeminmax` 的 KB sidecar 包写实

`v2` 显式加了 `P1.2`：

1. re-ingest 候选清单
2. family 级数据质检
3. approval / rollback 说明
4. before/after 指标模板

这意味着：

- `claudeminmax` 不再只是“帮忙做评测”
- 而是对 KB 治理的 sidecar 审计与 re-ingest 质检有明确 owner 身份

## 独立判断

我这次接受了外部评审的主体意见，但没有改成另一份全新战略文档。

我保留的判断是：

1. `v1` 的统一结构是对的，不需要推翻
2. 需要修的是执行前的模糊空间
3. 主链 owner 仍然必须是 Codex
4. `claudeminmax` 适合 sidecar，不适合主链语义 owner

## 备注

这次输出仍然只是计划升级，不是执行完成报告。

后续如果真正启动执行，仍按仓库纪律：

1. 每个有意义改动独立提交
2. 每个批次有 walkthrough
3. 最后做 scoped closeout
