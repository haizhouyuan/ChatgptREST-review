# 2026-03-16 Finbot Claim/Citation/History Review Packet v1

## Context

当前 `finbot` 已经具备：

- 单 ingress、单 `finbot`、内部多 lane
- `Claim / Skeptic / Expression / Decision` 四条 lane
- investor dashboard 已有：
  - 首页
  - 主题页
  - 机会页
  - source 页
- 当前机会页已有：
  - `Claim ledger`
  - `Risk register`
  - `Valuation frame`
  - `Source scorecard`

## Current Limitation

虽然 investor 页面已经“可读”，但还没有达到“可追溯、可比较、可复盘”的理想状态，主要缺口是：

1. `claim -> citation` 仍然带启发式 fallback
2. source/KOL 评分还主要停在单次 dossier 层，不够长期
3. 主题 / 机会 / source 的历史演化轨迹不够强

## What We Want To Build

我们计划一次性补齐：

- 稳定 `claim object / citation object / edge` 结构
- source/KOL 长期评分写回
- 主题 / 机会 / 表达的历史 diff 和 evolution view

## Open Questions For Review

请从“投资研究工作台”和“长期运行的 research agent”视角，开放式评审下面的问题：

1. 如果目标是让一个持续运行的投资研究 agent 真正达到“专业分析师可用”，`claim -> citation -> source score -> history diff` 这条链最容易被忽略的设计错误是什么？
2. 在 investor dashboard 里，什么样的 `claim / citation / source / thesis evolution` 组织方式最能帮助人类快速理解，而不是制造更多噪音？
3. source/KOL 的长期评分，应该更像：
   - 研究证据贡献系统
   - track record / 命中率系统
   - 还是“主题吸收价值”系统？
   为什么？
4. thesis/history diff 最应该突出哪些变化，才能帮助投资人做决策，而不是变成 changelog？
5. 如果只能追加少数几个高价值对象/字段，你会优先加什么，为什么？
6. 对于持续运行的 `finbot`，怎样避免历史越积越多，最后 investor 页面反而更难读？

## Relevant Code / Artifacts

### Runtime Code

- `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/chatgptrest/finbot.py`
- `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/chatgptrest/dashboard/service.py`
- `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/chatgptrest/dashboard/templates/investor_opportunity_detail.html`
- `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/chatgptrest/dashboard/templates/investor_theme_detail.html`
- `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/chatgptrest/dashboard/templates/investor_source_detail.html`

### Existing Outputs

- `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/artifacts/finbot/opportunities/tsmc-cpo-cpo-d519030bd1/latest.json`
- `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/artifacts/finbot/opportunities/tsmc-cpo-cpo-d519030bd1/latest.md`
- `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/docs/2026-03-16_finbot_structured_research_upgrade_walkthrough_v1.md`
- `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/docs/2026-03-16_finbot_source_scorecard_upgrade_walkthrough_v2.md`
- `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/docs/2026-03-16_investor_dashboard_home_and_source_upgrade_walkthrough_v1.md`

### Current Plan

- `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316/docs/roadmaps/2026-03-16_finbot_claim_citation_history_upgrade_plan_v1.md`

## Review Request

请不要把问题理解成“某个字段怎么命名更漂亮”，而是从整体方法论评审：

- 这条能力链是否足以把 `finbot` 从 scout 升级成高质量投资分析师？
- 哪些地方还会导致“看起来更复杂，但投资人并没有更容易判断”？
- 如果要追求最理想的效果，下一轮最该强化什么？
