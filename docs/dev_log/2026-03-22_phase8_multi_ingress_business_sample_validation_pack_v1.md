# 2026-03-22 Phase 8 Multi-Ingress Business Sample Validation Pack v1

## 1. 目标

在 `Phase 7` 已经证明 `agent_v3/rest` 默认前门语义稳定之后，
这一阶段继续把同一批 `planning/research` 业务样本扩成**多入口语义矩阵**。

这轮要回答的问题不是：

- full-stack runtime 是否已经样本级跑通

而是：

- 同一批业务样本从多个 live ingress 进入时，
  front-door semantic layer 是否仍然稳定不漂

## 2. 本轮覆盖的入口

这轮纳入了 4 个**可直接调用并可回放的 ingress 形态**：

- `agent_v3_rest`
  - 对应 `/v3/agent/turn` 的默认 `rest` 前门
- `standard_entry_codex`
  - 对应 `standard_entry` 适配器的 `codex -> cli` 归一化路径
- `feishu_ws`
  - 对应 `Feishu WS -> /v2/advisor/advise` 的 payload 构造路径
- `consult_rest`
  - 对应 `/v1/advisor/consult` 的 `task_intake + scenario_pack + consult model policy`

## 3. 本轮明确不覆盖的部分

为了把阶段边界说准，这轮仍然**不宣称**完成了下面这些事：

- `OpenClaw` TypeScript 插件的动态 replay
- `routes_*` / `ControllerEngine` 的 full route replay
- `context_service / ingest_service` 的 full-chain 读写主链实跑
- `advisor graph / report graph / funnel graph` 的 end-to-end 样本级验证

也就是说，这轮仍然是：

- **multi-ingress semantic validation**

不是：

- full-stack business-sample validation

## 4. 数据集

- [phase8_multi_ingress_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase8_multi_ingress_work_samples_v1.json)

这版数据集继续沿用 7 个代表性 `planning/research` 样本，
但把每个样本的验收从“单入口期望”扩成了“按 ingress profile 的期望矩阵”。

矩阵当前冻结了这些字段：

- `expected_source`
- `expected_ingress_lane`
- `expected_profile`
- `expected_route_hint`
- `expected_execution_preference`
- `expected_clarify_required`
- `expected_task_template`
- `expected_acceptance_profile`
- `expected_consult_models`

## 5. 验证器

- [multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/multi_ingress_work_sample_validation.py)

它不是直接打 API，而是复用当前 live ingress 的构造函数和策略函数，
去重放每条入口的语义快照：

- `agent_v3_rest`
  - `build_task_intake_spec`
  - `resolve_scenario_pack`
  - `apply_scenario_pack`
  - `normalize_ask_contract`
  - `build_strategy_plan`
- `standard_entry_codex`
  - `normalize_request`
  - 后续统一进入同一套 semantic snapshot
- `feishu_ws`
  - `_build_advisor_api_payload`
  - 后续统一进入同一套 semantic snapshot
- `consult_rest`
  - `build_task_intake_spec`
  - `resolve_scenario_pack`
  - `apply_scenario_pack`
  - `_select_consult_models`
  - 再补齐同一套 semantic snapshot

## 6. 运行脚本与测试

- 运行脚本：
  - [run_multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_multi_ingress_work_sample_validation.py)
- 回归测试：
  - [test_multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_multi_ingress_work_sample_validation.py)

## 7. 当前产物

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260322/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260322/report_v1.md)

## 8. 本轮最重要的结论

这轮最重要的不是 “又多了一个 eval 脚本”，而是：

- 同一批 `planning/research` 业务样本
- 在 `agent_v3/rest`、`standard_entry/codex`、`feishu_ws`、`consult_rest`
- 这 4 种入口形态下
- front-door semantic layer 现在能保持一致

当前已经被矩阵钉住的关键信号包括：

- `meeting_summary / interview_notes`
  - `feishu_ws` 不再漂成 `general`
- `topic_research / comparative_research`
  - `consult_rest` 会稳定选到 `chatgpt_dr + gemini_dr`
- `research_report`
  - `consult_rest` 会稳定选到 `chatgpt_pro + gemini_deepthink`
- `standard_entry_codex`
  - source 会稳定归一成 `cli`

## 9. 下一步

在 `Phase 8` 之后，下一步才值得继续往下扩两类验证：

1. **OpenClaw plugin dynamic replay**
   - 不是静态源代码契约，而是真正把 TS payload builder 跑起来

2. **full-chain business-sample validation**
   - route handler
   - controller
   - knowledge/runtime read/write path

## 10. 结论

`Phase 8` 当前最准确的定义是：

- **multi-ingress business-sample semantic validation 已完成**
- **OpenClaw dynamic replay 与 full-stack 主链样本验证仍未完成**
