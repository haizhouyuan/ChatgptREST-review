# 2026-03-22 Phase 8 Multi-Ingress Business Sample Validation Completion v1

## 1. 本轮完成了什么

本轮把 `Phase 7` 的单入口业务样本验证，扩成了真正的多入口语义矩阵。

新增交付物：

- 验证模块：
  - [multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/multi_ingress_work_sample_validation.py)
- 数据集：
  - [phase8_multi_ingress_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase8_multi_ingress_work_samples_v1.json)
- 运行脚本：
  - [run_multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_multi_ingress_work_sample_validation.py)
- 回归测试：
  - [test_multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_multi_ingress_work_sample_validation.py)
- 运行产物：
  - [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260322/report_v1.json)
  - [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260322/report_v1.md)

## 2. 本轮验收范围

这轮验收的范围是：

- `agent_v3/rest`
- `standard_entry/codex`
- `feishu_ws`
- `consult/rest`

在同一批 `planning/research` 样本下，
这些入口都要稳定落到同样的 semantic outcome：

- source / ingress_lane
- scenario pack profile
- route hint
- clarify requirement
- task template
- acceptance profile
- consult models

## 3. 验收结果

本轮实际跑出的结果是：

- `dataset=phase8_multi_ingress_work_samples_v1`
- `items=7`
- `ingress_profiles=4`
- `cases=28`
- `passed=28`
- `failed=0`

## 4. 当前能成立的结论

现在已经可以成立的结论是：

- 当前 `planning/research` 代表性业务样本
- 在 4 个 callable ingress 形态上
- semantic layer 没有漂

这比 `Phase 7` 更进一步，因为它已经不再只证明：

- `agent_v3/rest` 单入口是稳定的

而是证明：

- 至少当前这 4 条实际入口语义是一致的

## 5. 当前还不能成立的结论

这轮仍然不能写成：

- OpenClaw plugin 动态 replay 已验证
- full-stack controller/runtime/knowledge 主链已样本级跑通

所以它不是最终“全链路业务样本验证”，而是：

- **multi-ingress semantic validation**

## 6. 结论

`Phase 8` 已完成。

修正后的最准确阶段结论是：

- **multi-ingress business-sample semantic validated**
- **not yet OpenClaw dynamic replay validated**
- **not yet full-stack business-sample validated**
