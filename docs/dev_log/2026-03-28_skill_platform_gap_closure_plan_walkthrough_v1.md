# 2026-03-28 Skill Platform Gap Closure Plan Walkthrough

## 本次做了什么

1. 基于仓内已实现代码重新评估了 skill 平台完成度
2. 对照 `planning` 侧 handoff 文档，重新校准了 platform foundation vs platform closure 的口径
3. 把“全量补齐方案”收成了正式阶段计划，明确了：
   - 当前完成度
   - 哪些是 substrate
   - 哪些是平台主链缺口
   - 分阶段交付顺序
   - 每阶段验收标准

## 为什么要重写这个计划

前面的讨论里，容易出现两种偏差：

1. **说重**
   - 把 memory substrate、validation plane、compatibility gate 直接算成 skill platform 已闭环
2. **说轻**
   - 把 market acquisition / compatibility / quarantine 基础设施一概算成 0

这次计划的目标是把两种偏差都收掉：

- 承认已有 platform substrate
- 但不把 substrate 误判成 platform closure

## 本次采用的判断口径

### 认为已存在的

1. repo-local skill 装载
2. advisor-local 静态 registry
3. skill gap preflight
4. EvoMap skill validation / telemetry substrate
5. OpenMind memory substrate
6. market acquisition 的治理支架

### 认为尚未形成主链的

1. canonical catalog
2. bundle model
3. bundle-aware resolver
4. usage-based EvoMap loop
5. cross-platform adapters
6. capability gap recorder
7. market acquisition loop

## 本次最重要的结论

### 1. 现在不是空白，但也绝不是完成态

最准确的说法是：

- `platform foundation` 中低完成度
- `platform closure` 低完成度

### 2. 顺序必须收紧

不应该先做：

- 大而全 EvoMap lifecycle
- 自动 market acquisition

应该先做：

1. canonicalization
2. registry
3. bundle
4. resolver

### 3. market acquisition 不能直接自动接入生产

必须先：

1. internal miss
2. quarantine install
3. compatibility/trust gate
4. smoke / evaluate
5. promotion

## 形成的正式产物

1. `2026-03-28_skill_platform_gap_closure_plan_v1.md`

## 备注

这次只产出了正式计划文档，没有改运行代码，也没有改 skill registry / resolver / OpenClaw config。
