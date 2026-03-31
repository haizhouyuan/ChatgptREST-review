## 背景

上一轮已经把 `finbot` 的机会 dossier 从 narrative 升成了：

- `claim_ledger`
- `risk_register`
- `valuation_frame`

但对投资人来说，`key_sources` 仍然太像原始字符串，无法回答两个更关键的问题：

- 当前 thesis 到底是靠哪些 source 站住的
- 哪些 source 是 anchor，哪些只是 derived / corroborating

这轮的目标是把 source 层升级成投资人可读的 `source scorecard`，而不是继续堆更多 source 名字。

## 本轮改动

### 1. Source scorecard 结构

在 `research_package` 里新增：

- `source_scorecard`

每个 source 行包含：

- `name`
- `detail_href`
- `source_type`
- `source_trust_tier`
- `source_priority_label`
- `track_record_label`
- `accepted_route_count`
- `validated_case_count`
- `contribution_role`
- `focus`
- `reason`

### 2. 自动归因逻辑

这轮没有引入新的数据库表，而是先用现有 dossier 上下文做最小但可用的归因：

- `anchor`
  - 优先给官方披露 / 高 validated 的 source
- `derived`
  - 优先给 KOL / derived source
- `corroborating`
  - 介于两者之间的补充 source

并根据：

- `key_sources`
- `latest_viewpoint_summary`
- `source_trust_tier`
- `source_type`

自动生成：

- `focus`
- `reason`

这样 investor 页面就能直接解释“为什么它在这里”，而不是只列一个 source name。

### 3. Investor dashboard

机会详情页的 source 区块从：

- `Suggested Sources`

升级成：

- `Source Scorecard`

页面现在会显示：

- source 角色
- trust / track record
- 当前在 thesis 里的作用
- 当前 dossier 为什么引用它

## live 验证

真实 `TSMC CPO` 最新 dossier 已确认带上：

- `source_scorecard`
- `related_sources`

live 页面：

- `/v2/dashboard/investor/opportunities/candidate_tsmc_cpo_cpo_d519030bd1`

已经能看到：

- `Source Scorecard`
- `Broadcom/TSMC CPO`
- `福总_半导体AI`
- `当前 dossier 直接引用了这条 source。`

这说明 source 层已经从 artifact 进入 live investor page。

## 测试

这轮跑过：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_finbot.py -k "theme_radar_scout_writes_pending_inbox_item or opportunity_deepen"

PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_dashboard_routes.py -k investor_pages_and_reader_routes
```

结果：通过。

## 结论

这轮之后，`finbot` 的机会 dossier 不再只是：

- 结论
- 风险
- 估值

而是开始带上：

- 哪些 source 真在支撑当前判断
- 哪些 source 只是补充或预期差来源

这让 investor dashboard 更接近“分析师的 source map”，而不是“多看几个链接”。
