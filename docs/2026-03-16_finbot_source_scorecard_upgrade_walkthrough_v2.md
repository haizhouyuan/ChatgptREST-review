## 背景

`source_scorecard` 已经进入 dossier 和 investor 页面，但还差最后一公里：

- 投资人不是只想看“有哪些 source”
- 更想看“这条 claim 主要靠哪条 source 站住”

如果这层不补，source scorecard 仍然更像扩展阅读，而不是分析链的一部分。

## 本轮改动

### 1. Claim -> Source support

在 `claim_ledger` 上增加了 source support 结构：

- `supporting_sources`
- `support_note`

并在 dossier 生成时对 claim 做 source enrichment：

- 优先挂 `anchor`
- 其次 `corroborating`
- 最后 `derived`

即使模型没有显式给出 claim citation，系统也会先用当前 `source_scorecard` 做最小支撑绑定。

### 2. Investor page fallback

考虑到真实 provider rerun 可能慢于页面刷新，这轮同时在 investor 页面补了 fallback：

- 如果 claim row 自己还没有 `supporting_sources`
- 页面会先用 `source_scorecard` 里的第一条 anchor source 展示

这样 live 页面不会因为 dossier 尚未重写完成而丢掉 claim-source 关系。

## live 验证

真实页面：

- `/v2/dashboard/investor/opportunities/candidate_tsmc_cpo_cpo_d519030bd1`

当前已经能看到：

- `Supporting sources:`
- `Broadcom/TSMC CPO (anchor)`
- `当前 dossier 直接引用了这条 source。`

这说明 investor 页面已经从：

- claim
- source scorecard

进一步走到了：

- claim-linked supporting source

## 测试

这轮跑过：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_finbot.py -k opportunity_deepen

PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_dashboard_routes.py -k investor_pages_and_reader_routes
```

结果：通过。

## 结论

到这一步，`finbot` 的 dossier 已经不只是：

- 结论
- 风险
- 估值
- source list

而是开始具备：

- `claim -> source -> why this source`

这更接近投资分析师的工作底稿，而不是 research portal 的导航页。
