## 已完成

- `claim_ledger` schema + fallback generation
- `risk_register` schema + fallback generation
- `valuation_frame` schema + fallback generation
- investor opportunity page 渲染：
  - `Claim ledger`
  - `Risk register`
  - `Valuation frame`
- 定向测试覆盖：
  - `test_finbot.py`
  - `test_dashboard_routes.py`

## 下一步

### P0

- 把 `claim_ledger` 从“数组字段”升级成真正可追踪的 claim object，支持 `claim_id`
- 给 `skeptic` 的风险项增加更稳定的 `severity` 规范，不只依赖 prompt 大小写
- 给 `expression` 的 scenario 增加更清晰的 `what must happen` 触发条件

### P1

- source / KOL scorecard 接入 dossier
- opportunity dossier 显示 source 贡献排序，而不只是 key sources
- best expression 加 peer comparison excerpt

### P2

- claim outcome backcheck
- theme/base-rate ledger
- 自动把 repeated weak source 降权

## 当前真实限制

- provider 长任务偶尔会让 live dossier 刷新慢于模板与测试
- 本轮 `claim_ledger / risk_register / valuation_frame` 已完成 live 验证，下一步重点应转向更细的 claim object 与 source scorecard
- GitNexus 对本 worktree 的 staged change detection 仍不稳定，当前仍以定向测试 + live smoke 为主
