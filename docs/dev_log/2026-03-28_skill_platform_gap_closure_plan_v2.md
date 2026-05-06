---
title: skill platform gap closure plan
version: v2
status: proposed
updated: 2026-03-28
owner: Codex
supersedes: 2026-03-28_skill_platform_gap_closure_plan_v1.md
---

# Skill Platform Gap Closure Plan v2

## 1. 本版修正目的

`v1` 的大方向是对的，但还不能按“可直接开工”签字。`v2` 只补三件关键收口：

1. **解决 Phase 3 / Phase 6 契约错位**
   - Phase 3 不再直接输出正式 `capability_gaps`
   - 改为输出临时、可解释的 `unmet_capabilities`
   - Phase 6 再把它们升格成正式 `capability_gap` 账本对象

2. **把 unknown-agent fail-open 明确列为必须消除的早期目标**
   - 当前 `skill_registry.py` 对未知 agent 仍是 `passed=True`
   - 这不能进入平台真相源阶段

3. **在 Phase 0 冻结 canonical authority**
   - 明确唯一 registry authority 的 owner / path / 版本推进规则
   - 防止 Phase 1 再长出第二套静态表

## 2. 当前状态判断

按 2026-03-28 当前仓内实现状态评估：

- `platform foundation`: 约 `45%-50%`
- `platform closure`: 约 `20%-30%`

当前已存在的是 **platform substrate**，不是 **platform closure**。

### 2.1 已存在的 substrate

1. repo-local skill load
2. advisor-local 静态 skill registry
3. `skill_gap` preflight / reroute
4. EvoMap skill validation / telemetry substrate
5. OpenMind memory / identity substrate
6. compatibility / quarantine 治理支架

### 2.2 尚未形成主链的能力

1. canonical catalog
2. bundle model
3. bundle-aware resolver
4. usage-based EvoMap lifecycle
5. cross-platform shared distribution
6. capability gap mainline
7. market acquisition mainline

## 3. 目标形态

目标不是“多几个 skill”，而是一个统一的 skill platform，至少要形成这 7 层：

1. `canonical catalog`
2. `bundle layer`
3. `resolver`
4. `usage-based EvoMap loop`
5. `cross-platform adapter layer`
6. `capability gap recorder`
7. `market acquisition loop`

## 4. 总原则

### 4.1 先真相源，后进化

先稳定：

- `skill_id`
- `version`
- `maturity`
- `owner`
- `bundle`
- `platform_support`

再谈 `skill.suggested/executed/succeeded/...`

### 4.2 先 bundle，后 agent 漫灌

OpenClaw / Codex / Claude Code / Antigravity 不应默认装全部 skill。  
默认投放单元必须是 bundle。

### 4.3 先内部 catalog，后 market acquisition

去市场找 skill 只能在内部 resolver miss 后触发，而且必须先走 quarantine。

### 4.4 memory substrate 不等于 skill platform

OpenMind memory 是相关底座，但不是 catalog、resolver、bundle、promotion 的替代品。

## 5. Phase 0 — Canonicalization And Authority Freeze

### 目标

冻结 skill 分类语义，同时指定 canonical registry 的唯一 authority。

### 交付物

1. `skill classification contract`
   - `canonical`
   - `local`
   - `infra`
   - `legacy`
2. `skill metadata minimum schema`
3. `platform ownership split`
4. `canonical registry authority contract`

### authority contract 必须写死的内容

1. **唯一 owner**
   - `ChatgptREST/OpenMind` 负责 canonical registry authority
2. **唯一路径**
   - 先落在单一 authority 文件或 authority 目录
   - 不允许 `advisor/skill_registry.py`、OpenClaw config、前端仓文档各自再维护第二套 canonical truth
3. **唯一版本推进规则**
   - 新增/升级/废弃 skill 必须走版本号推进
   - deprecated skill 不得原地覆盖
4. **唯一写入责任**
   - 只有指定 owner / pipeline 能写 canonical registry
   - 其他前端只能读或生成 projection

### 验收标准

1. 所有现存 skill 都能归入四类之一
2. 新增 skill 若无分类，不得进入 canonical 主链
3. 已明确唯一 authority path / owner / version rule
4. 现有 repo-local skill 与 canonical skill 的边界不再模糊

### 不做

1. 不落市场 acquisition 主链
2. 不加 EvoMap 新 usage 信号
3. 不扩 agent bundles

## 6. Phase 1 — Registry Schema And Governance Gate

### 目标

落平台级 registry schema，并把当前最危险的 fail-open 治理掉。

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

### 额外必须处理的治理项

1. **unknown-agent fail-open 移除**
   - 当前 `check_skill_readiness()` 对未知 agent `passed=True` 必须废除
2. **unknown identity 的正式结果类型**
   - 至少返回：
     - `unknown_agent`
     - `unregistered_agent`
     - `registry_missing_profile`
   - 不能再“带 warning 继续跑”

### 交付物

1. canonical registry schema 文档
2. registry authority 文件/目录
3. 现有静态 registry 的迁移映射
4. unknown-agent fail-open removal 设计与实现计划

### 验收标准

1. `advisor/skill_registry.py` 不再承担 canonical truth 角色
2. 至少 1 批核心 skill 能完整落入新 schema
3. 对未知 agent 不再 fail-open
4. 前端对同一 skill 的解释不再分叉

## 7. Phase 2 — Bundle Model

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
3. OpenClaw build script 对 bundle 的接线
4. `allowBundled` 不再为空

### 验收标准

1. OpenClaw agent 不再依赖零散 `skills=("chatgptrest-call",)` 式配置
2. agent 至少能按 bundle 安装与审计
3. bundle 与 canonical registry 之间能互相回指

## 8. Phase 3 — Bundle-aware Resolver

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
3. `unmet_capabilities`
4. `decision_reasons`
5. `fallback_plan`

### 为什么这里不用 `capability_gaps`

当前阶段 resolver 只需要表达：

- 这次任务缺了什么
- 为什么没命中
- 应该怎么退

这还不是正式 backlog 对象。  
正式 `capability_gap` 的 owner / priority / aggregation / status，要到 Phase 6 才成立。

### 交付物

1. resolver contract
2. resolver implementation
3. advisor / public agent / OpenClaw adapter 接线
4. `unmet_capabilities` 的最小结构定义

### 验收标准

1. 不能只返回 `skill_gap`
2. 必须给出推荐 skill/bundle 与理由
3. 必须能输出 fallback plan
4. 必须能输出可解释的 `unmet_capabilities`
5. 同一任务在不同前端的推荐结果保持可解释的一致性

## 9. Phase 4 — Minimal EvoMap Skill Loop

### 目标

只上最小且有用的 usage lifecycle，不做大而全信号泛滥。

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

### 交付物

1. 最小 skill telemetry contract
2. resolver/use path 埋点
3. 基本 dashboard / query slice

### 验收标准

1. 能回答“哪个 bundle 被推荐/执行最多”
2. 能回答“哪个 skill 在哪个前端/agent 上失败最多”
3. 不引入大规模脏信号或匿名信号

## 10. Phase 5 — Cross-platform Adapter Layer

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

## 11. Phase 6 — Capability Gap Recorder

### 目标

把 Phase 3 的 `unmet_capabilities` 升格成正式 backlog 对象。

### 升格规则

1. `unmet_capabilities` 是一次 resolver 结果里的即时诊断
2. `capability_gap` 是可聚合、可跟踪、可关闭的正式对象

### 交付物

1. `capability_gap` schema
2. gap recorder
3. `unmet_capabilities -> capability_gap` promotion rule
4. resolver 对 gap 的读取/回写

### 验收标准

1. resolver miss 时能稳定生成 `unmet_capabilities`
2. 相同 unmet 项能聚合成单一 `capability_gap`
3. gap 有 owner、优先级、来源前端、来源任务
4. 相同 gap 不会无限重复建档

## 12. Phase 7 — Market Acquisition Loop

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

## 13. 可实施顺序

严格建议按下面顺序推进：

1. `Phase 0 canonicalization and authority freeze`
2. `Phase 1 registry schema and governance gate`
3. `Phase 2 bundle model`
4. `Phase 3 bundle-aware resolver`
5. `Phase 4 minimal EvoMap loop`
6. `Phase 5 cross-platform adapters`
7. `Phase 6 capability gap recorder`
8. `Phase 7 market acquisition loop`

## 14. 里程碑验收

### Milestone A — 真相源建立

必须完成：

1. Phase 0
2. Phase 1

通过标准：

1. skill 不再只有 advisor-local 静态表
2. 有唯一 canonical authority
3. unknown-agent fail-open 已移除
4. canonical/local/infra/legacy 分类被冻结

### Milestone B — 平台可推荐

必须完成：

1. Phase 2
2. Phase 3

通过标准：

1. OpenClaw 有真实 bundle
2. resolver 能输出 recommended bundles / reasons / unmet_capabilities
3. resolver 不再只是 preflight block / reroute

### Milestone C — 平台可进化

必须完成：

1. Phase 4
2. Phase 6

通过标准：

1. skill usage 被 EvoMap 记录
2. unmet 项能沉淀成 capability gap backlog

### Milestone D — 平台可扩能力

必须完成：

1. Phase 5
2. Phase 7

通过标准：

1. skill 能跨前端共享
2. 市场采买可 quarantine / evaluate / promote

## 15. 这轮仍不能误判为“已完成”的项

以下能力当前都**不能**被视为已完成：

1. canonical skill platform
2. bundle-aware resolver
3. usage-based EvoMap skill evolution
4. cross-platform shared distribution
5. capability gap mainline
6. market acquisition mainline

## 16. 一句话收口

当前不是没有地基，而是 **地基多、authority 与主链不足**。

`v2` 的执行主线已经收紧为：

`authority freeze -> registry governance -> bundle -> resolver(unmet_capabilities) -> EvoMap -> adapters -> capability_gap -> market`

这版才是可直接开工的项目计划。
