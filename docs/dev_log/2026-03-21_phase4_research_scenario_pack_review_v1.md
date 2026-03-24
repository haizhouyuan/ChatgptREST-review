# Phase 4: Research Scenario Pack Review v1

日期：2026-03-21  
评审对象：`6dc35c3` + `91bb09e`

## 结论

Phase 4 的主链实现已经基本成立：

- `topic_research` / `comparative_research` 已进入 live `scenario_pack`
- `research_report` 已稳定落到 `report` lane，并派生 `analysis` 报告类型
- `/v3/agent/turn` 的低上下文 `research_report` 确实会先走 clarify gate
- `report_graph.web_research` 已改为消费 pack 的 `min_evidence_items`
- `standard_entry` 已与 research pack 语义对齐

但这轮还不能写成“所有 ingress 语义已完全对齐”。我确认存在 1 个实质性质量分叉：

## Findings

### 1. `/v1/advisor/consult` 仍把 `research_report` 默认打到 deep-research 模型组，而不是 report-grade 默认策略

证据链：

- [routes_consult.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_consult.py#L373) 的 `_select_consult_models(...)` 在 [routes_consult.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_consult.py#L389) 把 `research_report` 与 `topic_research`、`comparative_research` 一起并入 `DEEP_RESEARCH_MODELS`
- 但 [preset_recommender.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/preset_recommender.py#L250) 对 `research_report` 的推荐已经改成 `pro_extended`
- 我本地用 `TestClient` 直打 `/v1/advisor/consult` 复现：
  - 请求：`{"question":"请输出一份行星滚柱丝杠行业研究报告","goal_hint":"report","auto_context":false}`
  - 返回：`scenario_pack.profile = research_report`
  - 但 `models = ["chatgpt_dr", "gemini_dr"]`

这会带来两个直接问题：

- 用户会在“写研究报告”场景下落到更偏 evidence collection 的长任务模型组，而不是更偏报告成稿质量的默认组合
- `standard_entry` 与 `/v1/advisor/consult` 对同一 `research_report` 场景产生了不同的质量/时延/成本策略，入口心智不一致

评审判断：

- 这是中优先级问题，不阻断 `Phase 4` 主链成立
- 但它阻止我把这轮签成“research ingress 全面对齐”

建议修法：

- 最直接：在 `_select_consult_models(...)` 中把 `research_report` 从 `DEEP_RESEARCH_MODELS` 分支剥离，单独走 report-grade 默认模型组
- 更稳健：按 `scenario_pack.profile + route_hint + provider_hints.report_type` 做 consult 选择，而不是把所有 research profile 粗暴归入一个 bucket

## 通过项

以下关键点我重新核过，结论成立：

- `topic_research` / `comparative_research` 命中后稳定走 `deep_research`
- `research_report` 命中后稳定走 `report`
- `/v3/agent/turn` 对低上下文 `research_report` 会直接返回 clarify，而不是盲跑
- `report_graph.web_research` 现在按 pack threshold 跳过或补证据，不再固定用旧的 `>= 3`
- `standard_entry_pipeline(...)` 对 `research_report` 的默认推荐已经是 `pro_extended`

## 复核命令

我本轮实际复跑/复现了这些：

```bash
./.venv/bin/pytest -q tests/test_scenario_packs.py tests/test_ask_strategist.py tests/test_report_graph.py tests/test_advisor_consult.py
./.venv/bin/pytest -q tests/test_advisor_graph.py tests/test_openclaw_cognitive_plugins.py tests/test_feishu_ws_gateway.py tests/test_business_flow_advise.py tests/test_advisor_v3_end_to_end.py -k 'research or report or advise or openclaw or feishu'
```

另外做了两条定向复现：

- `standard_entry_pipeline("请输出一份行星滚柱丝杠行业研究报告")`：`research_report` + `pro_extended`
- `/v1/advisor/consult` 同题直打：`research_report` + `["chatgpt_dr", "gemini_dr"]`

## 总评

这轮可以签成：

- `Phase 4 mainline integrated`

还不能签成：

- `research scenario pack fully aligned across ingress surfaces`

下一步最值得补的是 `/v1/advisor/consult` 的 research-report 默认模型策略收口。
