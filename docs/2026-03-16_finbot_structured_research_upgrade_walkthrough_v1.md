## 背景

`finbot` 的多 lane 原型已经跑通，但仍偏“lane 摘要”。投资人真正需要的是：

- claim 是否结构化
- 反方风险是否可登记
- 表达比较是否带估值 / 情景框架

这轮的目标不是再加更多 narrative，而是把多 lane 结果推进成更接近分析师工作底稿的结构。

## 本轮改动

### 1. Claim lane

新增 `claim_ledger` 结构，目标字段：

- `claim`
- `evidence_grade`
- `importance`
- `why_it_matters`
- `next_check`

并增加后备生成逻辑：

- 如果模型没有显式产出 `claim_ledger`
- 系统会从 `core_claims / supporting_evidence / critical_unknowns`
- 或至少从 `thesis_name`
- 自动生成一版基础 ledger

### 2. Skeptic lane

新增 `risk_register` 结构，目标字段：

- `risk`
- `severity`
- `horizon`
- `what_confirms`
- `what_refutes`

并增加后备生成逻辑：

- 如果模型没有显式产出 `risk_register`
- 系统会从 `thesis_breakers / timing_risks / disconfirming_signals`
- 自动合成最小风险登记

### 3. Expression lane

新增 `valuation_frame` 和 richer ranking row：

- `valuation_frame`
  - `current_view`
  - `base_case`
  - `bull_case`
  - `bear_case`
  - `key_variable`
- `ranked_expressions[*]`
  - `valuation_anchor`
  - `scenario_base`
  - `scenario_bull`
  - `scenario_bear`

同样增加后备生成逻辑：

- 如果模型没有显式给 valuation frame
- 系统会从 leader / comparison logic / ranking rows 自动生成基础版本

### 4. Investor dashboard

机会详情页新增并已渲染：

- `Claim ledger`
- `Risk register`
- `Valuation frame`

对应模板：

- `chatgptrest/dashboard/templates/investor_opportunity_detail.html`

## 定向回归

这轮跑过的定向测试：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_finbot.py -k opportunity_deepen

PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_dashboard_routes.py -k investor_pages_and_reader_routes
```

结果：通过。

## live 状态

### 已确认

live investor 页面已经能看到：

- `Claim ledger`
- `Risk register`
- `Valuation frame`

并且真实 `TSMC CPO` 最新 dossier 已经带出首条 claim：`TSMC以专用CoWoS产线提升CPO封装产能`。
这说明 richer structured payload 已经进入真实机会详情页，不再只是测试里存在。

### 已验证的 live 结果

最新 `latest.json` 已确认：

- `claim_ledger = true`
- `risk_register = true`
- `valuation_frame = true`

也就是说，这轮结构化研究升级已经完成从代码 -> 测试 -> live dossier 的闭环。

## 结论

这一轮后，`finbot` 的机会深挖已经从：

- lane narrative

进一步升级成：

- claim ledger
- risk register
- valuation/scenario frame

也就是说，研究包不再只是“观点摘要”，而开始具有分析师工作底稿的骨架。
