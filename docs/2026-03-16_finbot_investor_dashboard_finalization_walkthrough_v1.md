# 2026-03-16 Finbot Investor Dashboard Finalization Walkthrough v1

## What Changed

这轮把 `finbot` 的 investor dashboard 从“结构化研究展示页”继续推进成“投资人可消费的研究操作台”。

### 1. Opportunity Page

机会页新增或强化了这些层：

- `Epistemic Tear-Sheet`
- `thesis truth`
- `expression tradability`
- `conviction bottleneck`
- `kill box`
- `blocking facts`
- `thesis change summary`
- `dynamic intelligence requirements`
- `Citation Register`
- `Source Scorecard`

### 2. Theme Page

主题页强化了：

- `Research Progress`
- `Theme Source Map`
- `Planning Matches`
- `Theme Evolution Timeline`

并修复了 live 下因 schema 漂移导致的 500。

### 3. Source Page

source 页强化了：

- `Keep / Downgrade Decision`
- `Score Timeline`
- `Claim Support History`
- `information role`

### 4. Runtime Contract

`finbot` research package 在这一轮里继续扩成：

- stable claim objects
- stable citation objects
- claim -> citation edges
- source score writeback
- action-distance history
- intelligence requirements

## Files Touched

- `chatgptrest/finbot.py`
- `chatgptrest/dashboard/service.py`
- `chatgptrest/dashboard/templates/investor.html`
- `chatgptrest/dashboard/templates/investor_opportunity_detail.html`
- `chatgptrest/dashboard/templates/investor_theme_detail.html`
- `chatgptrest/dashboard/templates/investor_source_detail.html`
- `tests/test_finbot.py`
- `tests/test_dashboard_routes.py`

## Validation

### Tests

执行：

```bash
cd /vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_finbot.py \
  tests/test_dashboard_routes.py \
  tests/test_executor_factory.py \
  tests/test_coding_plan_executor.py
```

结果：

- `21 passed`

### Live HTTP Smoke

执行：

```bash
GET /v2/dashboard/investor
GET /v2/dashboard/investor/opportunities/candidate_tsmc_cpo_cpo_d519030bd1
GET /v2/dashboard/investor/sources/src_broadcom_ir
GET /v2/dashboard/investor/themes/silicon_photonics
GET /v2/dashboard/api/investor/graph
```

结果：

- 全部 `200`

### Live Artifact Check

检查 `TSMC CPO` 最新 dossier：

- schema 已升级到 `3.0`
- 包含：
  - `claim_objects`
  - `citation_objects`
  - `history`
  - `distance_to_action`
  - `intelligence_requirements`

## Known Runtime Caveat

手动：

```bash
ops/openclaw_finbot.py opportunity-deepen --candidate-id ... --force
```

仍然是长任务。原因不是页面慢，而是它会串行跑多条内部 lane，并且等待 `coding_plan` provider 返回。

这意味着：

- dashboard / live 页面已经可用，不依赖这条命令秒级完成
- 新字段上线后，artifact 的“最新一次刷新”可能慢于页面模板升级
- 读时推导（例如 `information_role` fallback）仍然是有价值的保护层

## Problems Found During This Pass

### 1. Theme Detail Live 500

根因：

- template 还在读旧字段 `theme_state.history`
- service 已经拆成 `theme_evolution`

修复：

- template 改成优先读 `theme_evolution`
- 旧数据回退到 `theme_state.history`

### 2. Opportunity Page Naming Drift

根因：

- 页面语义升级成 `Epistemic Tear-Sheet`
- 测试和一部分阅读语义仍期待 `Decision Card`

修复：

- 页面保留 `Epistemic Tear-Sheet`
- 同时显式写出 `Decision Card` 语义

### 3. Old Artifact Missing `information_role`

根因：

- 新字段上线后，旧 artifact 不会自动补齐

修复：

- dashboard 在读取时按 contribution/trust/source type 推导 `information_role`
- 不依赖 artifact 已经刷新

## Outcome

这一轮完成后，`finbot` 已经可以稳定回答：

- 这个机会为什么值得继续
- 现在为什么还不能投
- 哪条 expression 最优
- 哪些 source 值得长期信任
- 这次和上次相比判断往哪里移动

## Remaining Next-Phase Items

这轮之后还剩的东西，已经不是 blocker，而是下一阶段增强：

- formal claim/citation graph backend
- stronger valuation / scenario layer
- longer-horizon source/KOL score calibration
