## 已完成

- `source_scorecard` 进入 dossier 和 investor 页面
- `claim_ledger` 支持 `supporting_sources / support_note`
- investor 页面在 provider rerun 未完成时，也能 fallback 展示 claim 支撑 source

## 下一步

### P0

- 把 `supporting_sources` 从当前启发式绑定升级成真正的 citation link
- 给 claim row 增加稳定 `claim_id`
- 把 `source_scorecard` 和 `claim_ledger` 之间的关系写入 artifact，而不只在页面 fallback

### P1

- source / KOL 的贡献度进入 decision lane
- 对同一 claim 呈现正反两边 source，而不只是正面 anchor
- theme detail 页补 `theme-level source map`

### P2

- source quality feedback 回写
- claim outcome backcheck 驱动 source 权重调整
- theme radar promotion 参考 source reliability

## 当前真实限制

- 当前 `claim -> source` 仍以启发式规则和 fallback 为主，不是完整 citation graph
- provider 长任务有时会慢于页面刷新，所以页面 fallback 仍然有保留价值
- GitNexus 对该 worktree 的 staged detection 依然不稳定，本轮继续以定向测试 + live smoke 为主
