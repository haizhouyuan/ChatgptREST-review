# 2026-03-22 Phase 7 Business Work Sample Validation Completion Walkthrough v1

## 做了什么

这轮没有去扩新服务，也没有再去画“下一层大架构”。

我把下一阶段直接定义成：

- `business work sample validation`

也就是把当前已经冻结下来的主链，压到一组代表性 planning/research 样本上做回放。

## 为什么这样做

到 `Phase 6` 为止，最关键的系统判断已经定了：

- 不继续扶正新的 Work Orchestrator
- 主业务样本继续站在 job/report/funnel 主线
- planning/research 是真正的高价值场景

在这个前提下，最自然的下一步不是再加层，而是：

- 用真实业务风格样本验证这条主线到底稳不稳

仓里本来就已经有：

- `eval harness`
- fixture-driven tests
- scenario pack / strategist / intake 的 deterministic logic

所以这轮最合理的做法就是把这些拼成一个真正的 work-sample validation pack。

## 这轮具体加了什么

### 1. 样本数据集

加了一份 versioned 数据集：

- [phase7_business_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase7_business_work_samples_v1.json)

里面不是 toy inputs，而是贴近你前面明确主战场的样本：

- 面试纪要
- 例会纪要
- 轻量业务规划框架
- 人力规划方案
- 主题研究
- 对比研究
- 研究报告

### 2. 前门语义快照器

加了：

- [work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/work_sample_validation.py)

它不是另造一套规则，而是直接调用当前 live 主链：

- `build_task_intake_spec`
- `resolve_scenario_pack`
- `apply_scenario_pack`
- `normalize_ask_contract`
- `build_strategy_plan`

最后产出：

- profile
- route
- execution_preference
- task_template
- clarify_required

这种 front-door 语义快照。

### 3. 运行脚本和产物

加了：

- [run_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_work_sample_validation.py)

并实际跑出了：

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322/report_v1.md)

结果是 `7/7` 全通过。

## 关键发现

这轮最重要的发现不是“样本都过了”这么简单，而是：

1. 当前 planning/research 主线已经足够稳定，能在业务样本级回放。
2. heavy execution 不需要马上上桌，因为这组样本已经能在 job/report/funnel 主线里稳定落语义。
3. 后面如果再动 intake / scenario pack / strategist，就终于有一组更接近业务现实的 regression baseline 了。

## 为什么这是一个真正的阶段

因为这轮把系统状态从：

- 代码级别稳定
- 文档级别冻结

推进到了：

- 样本级别可验证

这个变化是实质性的，不是“又多一份报告”。

## 最后结论

`Phase 7` 的意义是：

- 把前六阶段的收敛结果真正变成了可回放的业务样本回归

后面无论是继续扩样本，还是做产品化收敛，起点都会比之前更稳。
