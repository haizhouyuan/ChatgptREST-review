## 背景

机会页已经能讲清：

- thesis
- claim
- risk
- valuation
- source

但如果主题页仍然只是 `Decision Card + Expression Layer`，投资人仍然看不清：

- 这条主题整体研究推进到哪一步
- 当前最该追的 source 是什么
- 它在总规划里处于什么位置

这轮的目标是把主题页从“策略卡片页”升级成“主题工作页”。

## 本轮改动

### 1. Research Progress

主题页新增：

- `run_root`
- `summary_excerpt`
- tracked mix（core / option / competitor / alternative）

这让投资人能先判断：当前主题到底已经研究到哪一层，而不是只看到 posture。

### 2. Theme Source Map

主题页新增：

- `Theme Source Map`

直接展示主题级别的 `related_sources`：

- source name
- source type / trust / track record
- accepted / validated

这样主题页能回答：这条逻辑现在主要靠哪些 source 在供血。

### 3. Planning Matches

主题页新增：

- `Planning Matches`

直接展示：

- 规划优先级
- 核心逻辑
- expressions
- sources
- why

这让主题页能够连回总规划，而不是孤立存在。

## live 验证

真实页面：

- `/v2/dashboard/investor/themes/silicon_photonics`

当前已经能看到：

- `Research Progress`
- `Theme Source Map`
- `Planning Matches`
- `Open Run Report`
- `TSMC IR / Broadcom/TSMC CPO / Bernstein / SemiAnalysis`

说明这条主题的：

- 研究进展
- source map
- 规划位置

已经能在同一页里读完。

## 测试

这轮跑过：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_dashboard_routes.py -k investor_pages_and_reader_routes
```

结果：通过。

## 结论

这轮之后，主题页不再只是“当前建议动作是什么”，而是开始真正展示：

- 这条主题研究到哪
- 靠什么 source
- 在总规划中为什么重要

这更接近投资人真正会反复打开的主题工作台。
