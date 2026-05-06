---
title: skill platform gap closure plan
version: v1
status: proposed
updated: 2026-03-28
owner: Codex
---

# Skill Platform Gap Closure Plan

## 1. 结论

按 2026-03-28 当前仓内实现状态评估，`ChatgptREST/OpenMind/OpenClaw` 这条 skill 能力平台：

- **platform foundation**：约 `45%-50%`
- **platform closure**：约 `20%-30%`

更准确的定性是：

1. 已有若干 **platform substrate**
2. 尚未形成 **统一、可推荐、可组合、可进化、可跨前端共享** 的 skill platform

当前系统更像 4 个分散的半成品：

1. repo-local skill 装载
2. advisor-local 静态 skill registry
3. `skill_gap` preflight / reroute
4. EvoMap skill validation / telemetry substrate

还没有形成下面这条闭环：

`canonical catalog -> bundle -> resolver -> usage telemetry -> promotion/deprecation -> cross-platform distribution -> capability gap -> market acquisition`

## 2. 当前完成度评估

### 2.1 已落地能力

1. **repo-local skill load 已存在**
   - OpenClaw 重建脚本已把 repo `skills-src/` 接入 `skills.load.extraDirs`
   - 说明本地 skill 装载链是通的

2. **静态 skill registry 已存在**
   - `chatgptrest/advisor/skill_registry.py` 已有：
     - `SKILL_CATALOG`
     - `TASK_SKILL_REQUIREMENTS`
     - `AgentSkillProfile`
     - `check_skill_readiness()`

3. **skill gap preflight 已接线**
   - `advisor/dispatch.py`
   - `advisor/standard_entry.py`
   - 当前已经会在 dispatch 前做 skill check，并在不满足时返回 `skill_gap`

4. **EvoMap skill 相关 substrate 已存在**
   - `chatgptrest/evomap/signals.py` 中已有 `skill.learned`、`tool.failure`、`tool.recovery`
   - `chatgptrest/evomap/knowledge/skill_suite_review_plane.py` 已能导入 skill validation bundle

5. **OpenMind memory substrate 已存在**
   - `openclaw_extensions/openmind-memory/README.md` 对应的插件已能在 `before_agent_start` / `agent_end` 路径带着 `session/agent/role/thread` 上下文跑 recall/capture

6. **market acquisition 的治理支架不是 0**
   - 已有 compatibility gate / quarantine-style 基础设施
   - 但还没有 skill-specific 的 acquisition 主链

### 2.2 关键缺口

1. 没有 **canonical skill catalog**
2. 没有 **bundle model**
3. 没有 **bundle-aware resolver**
4. 没有 **usage-based EvoMap lifecycle**
5. 没有 **跨 Codex / Claude Code / Antigravity / OpenClaw 的统一分发**
6. 没有 **capability gap recorder + market acquisition mainline**

## 3. 目标形态

最终目标不是“更多 skill”，而是一个统一的 skill platform，至少包含 6 层：

1. **Canonical Catalog**
2. **Bundle Layer**
3. **Resolver**
4. **Usage-based EvoMap Loop**
5. **Cross-platform Adapter Layer**
6. **Capability Gap + Market Acquisition Loop**

## 4. 设计原则

### 4.1 先统一真相源，再做进化闭环

如果没有稳定的：

- `skill_id`
- `version`
- `maturity`
- `owner`
- `bundle`
- `platform_support`

那么任何 `skill.suggested/executed/succeeded/...` 信号都会先变成噪音。

### 4.2 bundle 优先于 skill 漫灌

OpenClaw / Codex / Claude Code / Antigravity 都不应该默认装“全部 skill”。

平台默认投放单元应当是 bundle，而不是单 skill。

### 4.3 先内部 catalog，后 market acquisition

能力不足去市场找 skill 这条 loop 必须建立在：

1. canonical catalog
2. bundle model
3. resolver
4. minimal EvoMap loop

之后。

否则系统会先长出一堆无法治理的第三方能力。

### 4.4 memory substrate 不等于 skill platform

OpenMind memory 是相关底座，但不能被算成“skill 平台闭环已经存在”。

它只解决：

- identity
- context recall
- capture substrate

不解决：

- catalog
- resolver
- bundle distribution
- promotion/deprecation

## 5. 分阶段补齐方案

## Phase 0 — Canonicalization Freeze

### 目标

先把 skill 体系里的语义口径冻结下来，避免一边落库一边继续改分类。

### 交付物

1. `skill classification contract`
   - `canonical`
   - `local`
   - `infra`
   - `legacy`
2. `skill metadata minimum schema`
3. `platform ownership split`
   - ChatgptREST/OpenMind
   - OpenClaw
   - external frontends

### 验收标准

1. 任何现存 skill 都能被归入上述四类之一
2. 新增 skill 若无分类，禁止进入 canonical 主链
3. 现有 repo-local skill 与 canonical skill 不再混淆

### 不做

1. 不落市场 acquisition
2. 不加 EvoMap 新信号
3. 不扩 agent bundles

## Phase 1 — Registry Schema

### 目标

落一套真正的平台级 registry schema，替换目前 advisor-local 的轻量 registry 角色。

### 最低字段

1. `skill_id`
2. `version`
3. `maturity`
4. `owner`
5. `source_of_truth`
6. `platform_support`
7. `bundle_membership`
8. `dependencies`
9. `failure_modes`
10. `telemetry_keys`
11. `deprecation_status`

### 交付物

1. canonical registry schema 文档
2. registry 存储载体
   - 可先 JSON/YAML
   - 后续可再演化成 DB-backed
3. 现有静态 registry 的迁移映射

### 验收标准

1. `skill_registry.py` 不再承担 canonical truth 角色
2. 至少 1 批现存核心 skill 能完整落入新 schema
3. 不同前端对同一 skill 的解释不再分叉

## Phase 2 — Bundle Model

### 目标

把 skill platform 的默认投放单元从单 skill 提升到 bundle。

### 建议首批 bundle

1. `general_core`
2. `maint_core`
3. `research_core`
4. `planning_delivery`
5. `planning_review`
6. `market_scan_quarantine`

### OpenClaw 首批 agent bundle

1. `main`
   - `general_core`
2. `maintagent`
   - `maint_core`
3. `finbot`
   - `research_core`

### 交付物

1. bundle schema
2. bundle membership manifests
3. OpenClaw build script 对 bundle 的真正接线
4. `allowBundled` 不再为空

### 验收标准

1. OpenClaw agent 不再依赖零散 `skills=("chatgptrest-call",)` 式配置
2. agent 至少能按 bundle 安装与审计
3. bundle 与 canonical registry 之间能互相回指

## Phase 3 — Bundle-aware Resolver

### 目标

把当前 `skill preflight` 升级成真正的平台级 resolver。

### resolver 输入

1. `task`
2. `repo`
3. `platform`
4. `role_id`
5. `agent_id`
6. `recent_failures`
7. `allowed_tools`
8. `identity_scope`
9. `available_bundles`

### resolver 输出

1. `recommended_skills`
2. `recommended_bundles`
3. `capability_gaps`
4. `decision_reasons`
5. `fallback_plan`

### 交付物

1. resolver contract
2. resolver implementation
3. advisor / public agent / OpenClaw adapter 接线

### 验收标准

1. 不能只返回 `skill_gap`
2. 必须给出推荐 skill/bundle 与理由
3. 必须能输出 fallback plan
4. 同一任务在不同前端的推荐结果保持可解释的一致性

## Phase 4 — Minimal EvoMap Skill Loop

### 目标

只上最小且有用的 skill usage lifecycle，不做大而全信号泛滥。

### 首批信号

1. `skill.suggested`
2. `skill.selected`
3. `skill.executed`
4. `skill.succeeded`
5. `skill.failed`
6. `skill.helpful`
7. `skill.unhelpful`

### 后置的信号

1. `skill.promoted`
2. `skill.deprecated`
3. `capability.gap.opened`
4. `capability.gap.closed`

这些要等 registry/bundle/resolver 稳定后再开。

### 交付物

1. 最小 skill telemetry contract
2. resolver/use path 埋点
3. 基本 dashboard / query slice

### 验收标准

1. 能回答“哪个 bundle 被推荐/执行最多”
2. 能回答“哪个 skill 在哪个前端/agent 上失败最多”
3. 不引入大规模脏信号或匿名信号

## Phase 5 — Cross-platform Adapter Layer

### 目标

让 canonical skill platform 被 4 类前端共享，而不是各自维护一套解释层。

### 目标前端

1. `Codex`
2. `Claude Code`
3. `Antigravity`
4. `OpenClaw`

### 交付物

1. adapter contract
2. frontend-specific projection rules
3. 每个平台对 skill/bundle 的支持矩阵

### 验收标准

1. skill 内容不再在多个前端仓里重复维护
2. 各平台只维护 adapter，不维护第二套 registry
3. 同一 bundle 能跨至少 2 个前端一致投放

## Phase 6 — Capability Gap Recorder

### 目标

把“缺能力”从临时异常变成正式 backlog。

### 交付物

1. `capability_gap` schema
2. gap recorder
3. resolver 对 gap 的读取/回写

### 验收标准

1. resolver 未命中时能稳定生成 gap
2. gap 有 owner、优先级、来源前端、来源任务
3. 相同 gap 可以聚合，不会无限重复建档

## Phase 7 — Market Acquisition Loop

### 目标

让系统在内部 catalog 未命中时，能受控地去外部市场找 skill。

### 设计原则

1. 只能在内部 resolver miss 后触发
2. 只能先进 quarantine
3. 必须经过 smoke / compatibility / trust gate
4. 不允许直接进入生产 bundle

### 建议子链

1. `skill_market_search`
2. `skill_install_quarantine`
3. `skill_evaluate`
4. `skill_promote`
5. `skill_deprecate`

### 验收标准

1. market acquisition 必须可审计
2. quarantine 未通过的 skill 不得进入 canonical registry
3. 提升为 canonical 的 market skill 必须有 smoke + real-use 证据

## 6. 可实施顺序

严格建议按下面顺序推进：

1. `Phase 0 canonicalization freeze`
2. `Phase 1 registry schema`
3. `Phase 2 bundle model`
4. `Phase 3 bundle-aware resolver`
5. `Phase 4 minimal EvoMap loop`
6. `Phase 5 cross-platform adapters`
7. `Phase 6 capability gap recorder`
8. `Phase 7 market acquisition loop`

## 7. 里程碑验收

### Milestone A — 平台真相源建立

必须完成：

1. Phase 0
2. Phase 1

通过标准：

1. skill 不再只有 advisor-local registry
2. 有唯一 canonical schema
3. 有清晰 canonical/local/infra/legacy 归类

### Milestone B — 平台可推荐

必须完成：

1. Phase 2
2. Phase 3

通过标准：

1. OpenClaw 有真实 bundle
2. resolver 能输出 recommended bundles / reasons / gaps

### Milestone C — 平台可进化

必须完成：

1. Phase 4
2. Phase 6

通过标准：

1. skill usage 被 EvoMap 记录
2. capability gaps 有 backlog 闭环

### Milestone D — 平台可扩能力

必须完成：

1. Phase 5
2. Phase 7

通过标准：

1. skill 能跨前端共享
2. 市场采买可 quarantine / evaluate / promote

## 8. 这轮不应误判为“已完成”的项

以下能力当前都**不能**被视为已完成：

1. canonical skill platform
2. bundle-aware resolver
3. usage-based EvoMap skill evolution
4. cross-platform shared distribution
5. capability gap mainline
6. market acquisition mainline

## 9. 一句话收口

当前不是没有地基，而是 **地基多、主链少**。

正确补齐方式不是继续堆 skill，而是按：

`canonicalize -> registry -> bundle -> resolver -> EvoMap -> adapters -> gap -> market`

把 skill 从“若干单点能力”收成真正的平台。
