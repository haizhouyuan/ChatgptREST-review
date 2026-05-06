# 2026-03-22 Phase 7 Business Work Sample Validation Completion v2

## 1. 为什么要出 v2

`v1` 把这轮样本验证写成了更大的主线实证，这不够精确。

这轮真正完成的是：

- planning/research 的 **front-door semantic validation**

不是：

- 多入口业务样本回归
- full-stack controller/runtime/knowledge 样本实证

## 2. 本轮完成了什么

本轮完成了一个 front-door 业务样本验证 pack：

- 数据集：
  - [phase7_business_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase7_business_work_samples_v1.json)
- 验证模块：
  - [work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/work_sample_validation.py)
- 运行脚本：
  - [run_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_work_sample_validation.py)
- 回归测试：
  - [test_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_work_sample_validation.py)
- 运行产物：
  - [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322/report_v1.json)
  - [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322/report_v1.md)

## 3. 本轮的独立判断

这轮已经足够证明：

- 当前 `agent_v3/rest` 默认前门
- 在 planning/research 代表性样本上
- front-door semantic layer 没有漂

但它还不足以证明：

- OpenClaw / standard_entry / consult / Feishu 同样不漂
- knowledge/runtime 主链已经样本级实证

所以当前最准确的阶段判断是：

- `front-door semantic layer` 已有业务样本回归
- `full-stack mainline` 还没有

## 4. 验收

本阶段的直接验收结果仍然是：

- `dataset=phase7_business_work_samples_v1`
- `items=7`
- `passed=7`
- `failed=0`

并且相关回归测试全部通过。

## 5. 对下一阶段的影响

这轮完成后，下一阶段的自然方向已经更清楚了：

1. 扩成多入口样本矩阵
2. 再决定要不要做 full-chain 样本验证

这比继续在抽象层争论“主线是不是已经完全稳定”更有价值。

## 6. 结论

`Phase 7` 已完成，但修正后的正确口径是：

- **front-door business-sample semantic validated**
- **not yet full-stack business-sample validated**
