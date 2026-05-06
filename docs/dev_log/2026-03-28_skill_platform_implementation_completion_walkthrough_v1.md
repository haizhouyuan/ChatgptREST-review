---
title: skill platform implementation completion walkthrough
version: v1
status: completed
updated: 2026-03-28
owner: Codex
references:
  - 2026-03-28_skill_platform_gap_closure_plan_v2.md
  - 2026-03-28_skill_platform_implementation_completion_v1.md
---

# Skill Platform Implementation Completion Walkthrough v1

## 1. 为什么这轮要直接做到代码闭环

这次不是继续写蓝图，而是按已批准的 `v2` 计划把主链做完。

收口标准不是“有一些相关文件”，而是：

1. authority 必须唯一
2. bundle 必须真实接到 OpenClaw
3. resolver 必须真正返回推荐与 unmet，不再只是 preflight
4. EvoMap 必须看到 skill usage
5. capability gap 必须是正式对象
6. market acquisition 必须有 quarantine / evaluate / promote / deprecate 主链

## 2. 实施顺序

### 2.1 先立 canonical authority

先把唯一真相源固定到：

- [skill_platform_registry_v1.json](/vol1/1000/projects/ChatgptREST/ops/policies/skill_platform_registry_v1.json)

同时把 [skill_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/skill_manager.py) 变成真正的 registry/bundle/resolver substrate。

这一步的关键不是“多加字段”，而是让：

- authority
- skills
- bundles
- agent_profiles
- task_profiles
- platform_adapters

都从一个 source-of-truth 出来。

### 2.2 再把 advisor-local registry 降级成 compatibility wrapper

[skill_registry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/skill_registry.py) 现在不再是第二套 truth。

它的职责被收窄成：

1. 兼容已有调用面
2. 调 canonical registry
3. 输出 readiness / skill gap 结果

同时 unknown-agent fail-open 被移除。

### 2.3 再做 bundle-aware OpenClaw 接线

[rebuild_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/scripts/rebuild_openclaw_openmind_stack.py) 被改成：

1. agent 按 bundle 配置
2. `allowBundled` 由 canonical registry 导出
3. OpenClaw 运行时 local `skills` 从 bundle 展开

这一步的意义是：OpenClaw 不再靠零散 skill 名称硬配。

### 2.4 再把 resolver 真正接进 advisor 流

[standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py) 和 [dispatch.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/dispatch.py) 现在都不只是 `skill_gap` 布尔值。

它们会返回：

1. `recommended_skills`
2. `recommended_bundles`
3. `unmet_capabilities`
4. `decision_reasons`
5. `fallback_plan`

这是从“静态预检”变成“平台 resolver”的关键拐点。

### 2.5 再把 EvoMap 和 capability gap 接成主链

[market_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/market_gate.py) 先收了两件事：

1. `unmet_capabilities -> capability_gap`
2. skill usage / resolution / execution 信号回写 EvoMap

然后再补到：

1. `capability.gap.opened`
2. `capability.gap.closed`
3. `skill.promoted`
4. `skill.deprecated`

这样 `Phase 4 + Phase 6` 才不再是两条分裂线。

### 2.6 最后补 market candidate lifecycle

这步是最容易做虚的地方，所以我故意没有做“公网自动抓装”。

真正落地的是：

1. candidate register
2. candidate search/list
3. candidate evaluate
4. candidate promote
5. candidate deprecate
6. linked gap close / reopen
7. resolver skill miss 时带回现存 market candidates

并配了 operator CLI：

- [manage_skill_market_candidates.py](/vol1/1000/projects/ChatgptREST/ops/manage_skill_market_candidates.py)

## 3. 为什么我没有把 Phase 7 做成公网自动爬装

这是有意的。

如果直接做“agent 缺 skill -> 去公网抓一个 -> 自动装”，会同时破坏：

1. canonical authority
2. bundle 治理
3. quarantine gate
4. promotion 审计

所以这次的独立判断是：

**先把 market acquisition 做成受控主链，再考虑 live market search connector。**

也就是说，当前的 `Phase 7` 是：

- controlled acquisition
- not uncontrolled marketplace auto-install

这符合计划，也更符合你之前反复强调的“系统性，不要表面修复”。

## 4. 这轮具体新增的关键能力

### registry / bundle

- canonical authority 固定
- bundle schema 与 agent profile 固定
- OpenClaw bundle 投放打通

### resolver

- advisor / public entry / dispatch 都能返回解释性 resolver 结果
- `unmet_capabilities` 成为显式对象

### EvoMap

- usage signals 已进入 skill 主链
- lifecycle signals 已覆盖 promote/deprecate 与 gap open/close

### adapters

- 可以按前端导出 platform projections
- `codex / claude_code / antigravity / openclaw` 不再只能口头共享

### market

- candidate 可审计
- candidate 可 quarantine
- candidate promote 要求 smoke + compatibility + real-use
- candidate deprecate 可 reopen gap

## 5. 我对“完成”的定义

这次我愿意签“完成”，不是因为它把所有未来想法都做了，而是因为：

1. `v2` 计划里的 Phase 0-7 都已有代码对象
2. 每一阶段都有对应测试
3. 平台已经能做真实治理，不再只是文档分层

## 6. 相关提交

1. `cbf1ada`
2. `5052640`
3. `f92bdd6`
4. `ec9f7a5`
5. `4d7eef7`

## 7. 验证

最终回归使用：

```bash
./.venv/bin/pytest -q \
  tests/test_skill_manager.py \
  tests/test_market_gate.py \
  tests/test_system_optimization.py \
  tests/test_phase3_integration.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_export_skill_platform_projections.py \
  tests/test_manage_skill_market_candidates.py \
  tests/test_evomap_signals.py
```

结果：全部通过。

## 8. 一句话收口

这次完成的不是“给 skill 多加了一层文档”，而是把 `canonical authority -> bundle -> resolver -> EvoMap -> adapters -> capability gap -> market lifecycle` 真正接成了一条平台主链。
