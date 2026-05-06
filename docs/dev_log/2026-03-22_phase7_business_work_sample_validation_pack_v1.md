# 2026-03-22 Phase 7 Business Work Sample Validation Pack v1

## 1. 目标

`Phase 7` 不再继续扩系统层，而是把前六阶段的主线真正压到**真实业务样本**上做验证。

这一阶段只回答一个问题：

**当前已经冻结下来的 front-door + planning/research + knowledge 主链，是否能在代表性业务样本上稳定复现预期语义。**

## 2. 为什么现在做这个

到 `Phase 6` 为止，系统已经明确：

- 不继续扶正新的 `Work Orchestrator`
- 保留 heavy execution 为 gated experimental lane
- 主业务样本仍应站在：
  - `planning`
  - `research`
  - `job/report/funnel`

所以接下来的正确动作不是再画蓝图，而是：

- 选一小组真实业务风格样本
- 固化成数据集
- 用当前 front-door 主链直接重放
- 看语义有没有漂

## 3. 本轮交付

### 3.1 数据集

- [phase7_business_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase7_business_work_samples_v1.json)

当前固化了 7 个代表性样本：

- `planning`
  - 面试纪要总结
  - 例会纪要整理
  - 轻量业务规划框架
  - 人力规划方案
- `research`
  - 主题研究
  - 对比研究
  - 研究报告

### 3.2 验证模块

- [work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/work_sample_validation.py)

它直接复用了当前 live 主链里的 canonical 逻辑：

- `build_task_intake_spec`
- `resolve_scenario_pack`
- `apply_scenario_pack`
- `task_intake_to_contract_seed`
- `normalize_ask_contract`
- `build_strategy_plan`

输出的是 front-door 语义快照，而不是再造一套平行推断器。

### 3.3 运行脚本

- [run_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_work_sample_validation.py)

默认会读取：

- [phase7_business_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase7_business_work_samples_v1.json)

并生成：

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322/report_v1.md)

### 3.4 回归测试

- [test_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_work_sample_validation.py)

这个测试不是只看“模块能跑”，而是要求整份样本数据集 `7/7` 全通过。

## 4. 当前冻结的验证口径

本轮样本验证要求至少稳定验证这些语义：

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

也就是说，经过前面几轮 Phase 1-6 的收敛之后，当前主线在这组代表性 planning/research 样本上已经具备：

- 稳定的 scenario pack 识别
- 稳定的 route hint
- 稳定的 execution preference
- 稳定的 clarify 行为

## 6. 阶段意义

这轮的价值不是“又多一个脚本”，而是第一次把前六阶段的系统收敛结果压到了**业务样本级回归**上。

这样后面如果再动：

- `task_intake`
- `scenario_packs`
- `ask_contract`
- `ask_strategist`

就不再只能靠单个单元测试，而是可以直接回答：

**真实业务样本有没有漂。**

## 7. 结论

`Phase 7` 可以视为完成。

当前主线已经从：

- 契约冻结
- 入口对齐
- planning/research pack
- knowledge runtime
- heavy execution admission

进一步进入到：

- **真实业务样本验证**

这意味着后续如果继续推进，最自然的方向就不再是“再加一层系统”，而是：

- 扩样本集
- 做业务样本级质量门禁
- 或基于这套样本回归继续做产品化收敛
