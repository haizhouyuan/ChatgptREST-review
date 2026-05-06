# Phase 4: Research Scenario Pack Review Walkthrough v1

日期：2026-03-21

## 我做了什么

1. 先确认 `HEAD` 在 `91bb09e`，并核对 Phase 4 文档与实现提交范围
2. 逐段检查了这些 live 文件：
   - `chatgptrest/advisor/scenario_packs.py`
   - `chatgptrest/advisor/ask_strategist.py`
   - `chatgptrest/advisor/graph.py`
   - `chatgptrest/advisor/report_graph.py`
   - `chatgptrest/advisor/preset_recommender.py`
   - `chatgptrest/advisor/standard_entry.py`
   - `chatgptrest/api/routes_consult.py`
3. 抽样复跑了 Phase 4 相关测试
4. 额外做了两类直接复现：
   - `standard_entry` 对 `research_report` 的 preset 推荐
   - `/v1/advisor/consult` 对 `research_report` 的实际默认模型选择

## 关键核验结果

### 主链成立

- `topic_research` / `comparative_research` 的 route 仍是 `deep_research`
- `research_report` 的 route 仍是 `report`
- `/v3/agent/turn` 对低上下文 `research_report` 会在入口直接 clarify
- `report_graph.web_research(...)` 已使用 `scenario_pack.acceptance.min_evidence_items`
- `standard_entry_pipeline(...)` 对 `research_report` 已推荐 `pro_extended`

### 发现的问题

`/v1/advisor/consult` 仍把 `research_report` 放进 deep-research 模型选择逻辑：

- `_select_consult_models(...)` 里 `research_report` 仍与 `topic_research` / `comparative_research` 同桶
- 本地请求返回 `scenario_pack.profile = research_report`，但默认 `models = ["chatgpt_dr", "gemini_dr"]`
- 这与 `standard_entry` 的 `pro_extended` 默认策略不一致

## 复跑记录

```bash
./.venv/bin/pytest -q tests/test_scenario_packs.py tests/test_ask_strategist.py tests/test_report_graph.py tests/test_advisor_consult.py
./.venv/bin/pytest -q tests/test_advisor_graph.py tests/test_openclaw_cognitive_plugins.py tests/test_feishu_ws_gateway.py tests/test_business_flow_advise.py tests/test_advisor_v3_end_to_end.py -k 'research or report or advise or openclaw or feishu'
```

结果：

- 两组 `pytest` 均通过
- 第二组有来自 `websockets` / `lark_oapi` 的现存 `DeprecationWarning`
- 未见新的失败或回归

## 定向复现摘要

### `standard_entry`

输入：

- `请输出一份行星滚柱丝杠行业研究报告`

结果：

- `scenario_pack.profile = research_report`
- `applied_preset = pro_extended`

### `/v1/advisor/consult`

输入：

- `POST /v1/advisor/consult`
- body: `{"question":"请输出一份行星滚柱丝杠行业研究报告","goal_hint":"report","auto_context":false}`

结果：

- `scenario_pack.profile = research_report`
- `models = ["chatgpt_dr", "gemini_dr"]`

## 落盘原因

这轮不是代码修复，而是阶段性核验与质量评审。需要把“主链已通过，但 consult 仍有 ingress alignment gap” 单独落档，避免后续把 Phase 4 误认成已经全入口收口。
