# 2026-03-22 Phase 7 Business Work Sample Validation Pack v2

## 1. 为什么要出 v2

`v1` 的方向是对的，但把验证范围写大了。

独立复核代码后，更准确的事实是：

- 这轮验证器只重放了 front-door 语义链：
  - `build_task_intake_spec`
  - `resolve_scenario_pack`
  - `apply_scenario_pack`
  - `task_intake_to_contract_seed`
  - `normalize_ask_contract`
  - `build_strategy_plan`
- 它**没有**进入：
  - `routes_*`
  - `ControllerEngine`
  - `context_service`
  - `ingest_service`
  - `advisor/report/funnel graph`
- 它当前也只验证了：
  - `agent_v3`
  - `rest`
 这一个默认 ingress 形态

所以这一阶段的正确命名应该是：

- **front-door business-sample semantic validation**

而不是：

- full-stack business-sample validation

## 2. 这轮到底验证了什么

### 2.1 已验证范围

这轮真正验证的是：

- canonical task intake normalization
- scenario pack resolution
- scenario pack application
- ask contract seed / normalization
- strategist clarify / route semantics

也就是：

- **front-door semantic layer**

### 2.2 未验证范围

这轮没有验证：

- route handler request/response surfaces
- controller lane execution
- knowledge read/write runtime
- graph/report/funnel execution path
- multi-ingress consistency

因此不能把它写成：

- `front-door + planning/research + knowledge 主链` 已经业务样本实证

## 3. 本轮交付

### 3.1 数据集

- [phase7_business_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase7_business_work_samples_v1.json)

当前固化了 7 个 planning/research 代表性样本。

### 3.2 验证模块

- [work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/work_sample_validation.py)

它的作用是做 front-door 语义快照，不是做 controller/runtime replay。

### 3.3 运行脚本

- [run_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_work_sample_validation.py)

### 3.4 回归测试

- [test_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_work_sample_validation.py)

### 3.5 当前产物

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322/report_v1.md)

## 4. 当前冻结的验证口径

本轮样本验证要求稳定验证这些 front-door 语义：

- `请总结面试纪要`
  - `interview_notes`
  - `route=report`
  - `clarify_required=True`
- `请整理今天例会纪要`
  - `meeting_summary`
  - `route=report`
  - `clarify_required=True`
- `请帮我做一个业务规划框架，先给简要版本，不要走复杂流程`
  - `business_planning`
  - `route=report`
  - `clarify_required=False`
- `请做未来两个季度的人力规划方案，含招聘节奏和岗位编制建议`
  - `workforce_planning`
  - `route=funnel`
- `调研行星滚柱丝杠产业链关键玩家和国产替代进展`
  - `topic_research`
  - `route=deep_research`
- `对比 PEEK 齿轮和金属齿轮在机器人减速器里的优劣与应用边界`
  - `comparative_research`
  - `route=deep_research`
- `请输出一份行星滚柱丝杠行业研究报告`
  - `research_report`
  - `route=report`
  - `clarify_required=True`

## 5. 结果

当前样本验证结果是：

- `items=7`
- `passed=7`
- `failed=0`

因此现在能成立的最强结论是：

- 当前 `agent_v3/rest` 默认前门上的 planning/research 代表性样本，
  在 front-door semantic layer 上是稳定的。

## 6. 阶段意义

这轮的价值仍然很高，但要把边界说准：

- 它第一次把前六阶段冻结下来的前门语义，
  压到了业务样本级回归上
- 它还没有证明：
  - 多入口一致
  - controller/runtime 一致
  - knowledge 主链的 full-stack 样本实证

## 7. 下一步

最自然的下一步不是回去争论大架构，而是继续扩这套 validation pack：

1. **多入口样本扩展**
   - `OpenClaw`
   - `standard_entry`
   - `/v1/advisor/consult`
   - `Feishu`

2. **full-chain 样本扩展**
   - route handler
   - controller
   - knowledge/runtime write/read path

## 8. 结论

`Phase 7` 继续成立，但修正后的正确口径是：

- **front-door business-sample semantic validation 已完成**
- **full-stack business-sample validation 还没有完成**
