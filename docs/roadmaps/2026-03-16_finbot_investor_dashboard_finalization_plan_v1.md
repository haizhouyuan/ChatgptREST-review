# 2026-03-16 Finbot Investor Dashboard Finalization Plan v1

## Goal

把 `finbot` 从“持续发现机会的 scout + 可读 dashboard”升级成“投资人可以直接消费的研究操作台”。

这里的完成标准不是页面更多，而是投资人打开一个入口就能回答：

- 现在最值得看的主题和机会是什么
- 核心逻辑是什么
- 最优表达是什么
- 为什么还不能投
- 哪些信号会迫使升级或放弃
- 这次和上次相比，判断在朝哪里移动
- 哪些 source / KOL 是 originator，哪些只是 amplifier

## Workstreams

### 1. Stable Claim -> Citation Layer

目标：

- 把 claim 从段落文字升级成稳定对象
- 把 citation 从 source 名字升级成稳定对象
- 在 dashboard 中显式展示 claim 与 citation 的关系

交付：

- `claim_objects`
- `citation_objects`
- `claim_citation_edges`
- `falsification_condition`
- `is_load_bearing`

### 2. Long-Term Source / KOL Feedback Writeback

目标：

- 让 source / KOL 不再只是当前页面里的名单
- 让它们积累长期的贡献、失真与趋势信息

交付：

- source score ledger
- `packages_seen`
- `supported_claim_count`
- `load_bearing_claim_count`
- `lead_support_count`
- `contradicted_claim_count`
- `quality_band / trend_label`
- `information_role`（originator / corroborator / amplifier）

### 3. Thesis / Opportunity / Theme Evolution

目标：

- 不再用普通 changelog
- 改成面向投资动作的语义历史

交付：

- `semantic delta`
- `distance_to_action`
- `goalpost_shifted`
- `blocking_facts`
- `thesis_change_summary`
- theme evolution timeline
- opportunity evolution timeline

### 4. Investor Dashboard IA Upgrade

目标：

- 首页不再只是对象列表，而是研究覆盖面和最新更新的一览表
- 主题、机会、source 三个详情页要能彼此跳转
- 页面只保留投资判断真正需要看的内容

交付：

- Investor home: `Research Coverage Table` + `Latest Research Updates`
- Opportunity page: `Epistemic Tear-Sheet`
- Theme page: `Research Progress` + `Theme Source Map` + `Planning Matches`
- Source page: `Keep / Downgrade Decision` + `Score Timeline`

### 5. Live Hardening

目标：

- 不只是本地模板通过
- live `/v2/dashboard/investor*` 全部可用
- 新 schema 与旧 artifact 共存时页面不炸

交付：

- template backward-compat fallbacks
- live route smoke
- dashboard 500 修复

## Acceptance Criteria

### Investor Home

- 显示当前主题、最优表达、why now、why not yet、latest change、可点击链接
- 显示最新研究更新，而不是原始事件流

### Opportunity Detail

- 顶部必须能在一屏内看到：
  - semantic delta
  - thesis truth
  - expression tradability
  - conviction bottleneck
  - kill box
  - next proving milestone
- 页面下半部分必须能继续展开：
  - claim ledger
  - skeptic lane
  - expression lane
  - citation register
  - source scorecard

### Theme Detail

- 当前 posture / best expression / blockers / evolution 必须可读
- theme 与 source / opportunity / planning 三者关系必须可点击跳转

### Source Detail

- 明确告诉投资人：
  - 这条 source 为什么还值得看
  - 它属于 originator / corroborator / amplifier 哪一类
  - 它的长期质量是在变好还是变差

### Live Runtime

- `/v2/dashboard/investor`
- `/v2/dashboard/investor/themes/{theme_slug}`
- `/v2/dashboard/investor/opportunities/{candidate_id}`
- `/v2/dashboard/investor/sources/{source_id}`
- `/v2/dashboard/api/investor/graph`

以上五个入口都必须 `200`。

## Non-Goals

- 这轮不做完整 valuation engine
- 这轮不做正式 claim graph storage backend
- 这轮不做全局 knowledge graph UI
- 这轮不要求 source score 已经完美校准，只要求结构正确并可持续积累

## Planned Outcome

完成后，`finbot` 不再只是“会发现机会并写研究包”，而是能把：

`发现 -> 证据 -> 反证 -> 表达比较 -> 当前判断 -> 历史变化 -> source 可信度`

压缩到一个投资人能真正使用的入口里。
