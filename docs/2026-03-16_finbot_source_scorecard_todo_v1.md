## 已完成

- `source_scorecard` 进入 `research_package`
- source 的 `contribution_role / focus / reason` 自动生成
- investor opportunity page 从 `Suggested Sources` 升级成 `Source Scorecard`
- `TSMC CPO` live 页面已验证

## 下一步

### P0

- 给 `source_scorecard` 增加更稳定的 `source_role` / `confidence` 词表
- 把 `key_sources` 从自由文本进一步压成 source-linked citation
- 给 `source_scorecard` 增加 `why_now` / `why_not_enough` 两类解释

### P1

- 接入真正的 `source contribution ranking`
- 把 `KOL suite` 里的 `ingested_sources / total_claims / consensus_topics` 转成 investor 可读摘要
- 在 theme detail 页展示 `theme-level source map`

### P2

- source / KOL scorecard 与 claim outcome backcheck 联动
- 自动下调长期高噪音 source
- 自动提升持续提供高价值 frontier 候选的 source

## 当前真实限制

- 现在的 source scorecard 仍然基于 dossier 上下文推断，不是完整 citation graph
- `focus` 对 KOL 类 source 仍然偏弱，因为它们的 `latest_viewpoint_summary` 并不总是完整
- GitNexus 对这个 worktree 的变更检测仍不稳定，当前仍以定向测试 + live smoke 为主
