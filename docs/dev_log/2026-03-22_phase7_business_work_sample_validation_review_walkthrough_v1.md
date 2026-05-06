# 2026-03-22 Phase 7 Business Work Sample Validation Review Walkthrough v1

## 做了什么

这轮我没有顺着阶段文档直接接受“`7/7` 通过 = 主链已被业务样本验证”这个结论，而是回到实现层重新核了一遍：

- 样本数据集到底在验什么
- 验证器到底调用了哪条 live 逻辑
- 产出报告到底证明到了哪一层
- 这件事和前面的蓝图是否一致

## 怎么核的

我做了 4 件事：

1. 重新检查了实现提交 `6b3e7fb` 和文档提交 `4921f6c`
2. 复跑了你给的 `pytest` 子集、`py_compile`、`ops/run_work_sample_validation.py`
3. 逐行检查了：
   - [work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/work_sample_validation.py)
   - [phase7_business_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase7_business_work_samples_v1.json)
   - [test_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_work_sample_validation.py)
   - [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322/report_v1.json)
4. 再拿它和：
   - [2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md)
   - [2026-03-20_post_reconciliation_next_phase_plan_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_post_reconciliation_next_phase_plan_v2.md)
   做了对照

## 核心判断是怎么形成的

最关键的观察有两个。

第一，验证器本身是一个**前门语义快照器**。

它会调用：

- `build_task_intake_spec`
- `resolve_scenario_pack`
- `apply_scenario_pack`
- `task_intake_to_contract_seed`
- `normalize_ask_contract`
- `build_strategy_plan`

这说明它验证的是：

- intake
- scenario pack
- contract
- strategist

而不是：

- route handler
- controller execution
- context/knowledge runtime
- graph 执行闭环

第二，当前样本集全部默认落在：

- `source=rest`
- `ingress_lane=agent_v3`

所以它证明的是公开主入口的 front-door 语义稳定，而不是所有已对齐入口都完成了同等级的业务样本验证。

## 为什么我没有否掉整个 Phase 7

因为这轮方向并没有偏。

蓝图从一开始就要求：

- 不要继续扩更重的执行中心
- 先把 `planning / research` 做成强前门
- 再逐步把质量门禁做实

从这个标准看，`Phase 7` 已经把系统推进到了一个更健康的状态：

- 之前只有单元测试和阶段冻结
- 现在多了一组可回放的业务样本 regression baseline

这是真增量，不是形式工作。

## 为什么我还是给了保留意见

因为当前文档把“前门语义样本回归”写成了更大的东西：

- `front-door + planning/research + knowledge 主链`
- `business-sample validated`

这两个说法如果不加限定，都会让人误以为：

- 真实 controller 路由
- knowledge read/write plane
- 多入口 adapter 对齐

都已经在业务样本上被跑过了。

而当前实现还没有证明到这一步。

## 最后结论

我最后把这轮定成：

- 方向正确
- 实现有效
- 对蓝图是加分项
- 但阶段口径需要收窄

最准确的标签应该是：

- `front-door business-sample semantic validation`

而不是：

- `full business-sample validation`
