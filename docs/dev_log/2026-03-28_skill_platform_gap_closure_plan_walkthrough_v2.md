# 2026-03-28 Skill Platform Gap Closure Plan Walkthrough v2

## 为什么出 v2

`v1` 的主方向是对的，但还不够“可直接执行”。这次 `v2` 只收三处关键执行口：

1. 修正了 Phase 3 / Phase 6 的契约错位
2. 把 unknown-agent fail-open 提前列为必须移除的治理目标
3. 在 Phase 0 增加了 canonical registry authority freeze

## 这次具体改了什么

### 1. Phase 3 改成输出 `unmet_capabilities`

`v1` 在 resolver 阶段直接要求输出正式 `capability_gaps`，但真正的 gap schema / recorder / 聚合又放到 Phase 6，存在内在错位。

`v2` 的修正是：

1. Phase 3 只输出：
   - `recommended_skills`
   - `recommended_bundles`
   - `unmet_capabilities`
   - `decision_reasons`
   - `fallback_plan`
2. Phase 6 再把 `unmet_capabilities` 升格成正式 `capability_gap`

这样 resolver 先能工作，gap backlog 再做正式治理，不会出现“先临时发明一套 gap 对象”的问题。

### 2. 把 unknown-agent fail-open 前移成早期治理项

`v1` 没把当前最危险的 fail-open 明确写进收口目标。  
`v2` 现在明确要求：

1. Phase 1 就要处理 unknown-agent fail-open
2. 未知 agent 至少要返回正式结果类型：
   - `unknown_agent`
   - `unregistered_agent`
   - `registry_missing_profile`
3. Milestone A 必须通过这条检查

### 3. 在 Phase 0 写死 canonical authority

`v1` 只有分类合同和 ownership split，但还没指定唯一 authority。  
`v2` 新增：

1. 唯一 owner
2. 唯一路径
3. 唯一版本推进规则
4. 唯一写入责任

目的就是在 Phase 1 前先堵住“第二套静态表继续长出来”的风险。

## 本次保持不变的主判断

以下判断没有变化：

1. 当前只有 substrate，不是平台闭环
2. bundle 要早于 resolver / EvoMap / market acquisition
3. market acquisition 只能后置，且必须走 quarantine / compatibility / trust gate
4. skill platform 的推进顺序仍然是：
   - `authority freeze`
   - `registry`
   - `bundle`
   - `resolver`
   - `EvoMap`
   - `adapters`
   - `capability gap`
   - `market`

## 本次产物

1. `2026-03-28_skill_platform_gap_closure_plan_v2.md`

## 备注

这次仍然只改计划文档，没有改运行代码，没有改 registry / resolver / OpenClaw config。
