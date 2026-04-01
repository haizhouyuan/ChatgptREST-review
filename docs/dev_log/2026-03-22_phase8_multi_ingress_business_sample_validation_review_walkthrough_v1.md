# 2026-03-22 Phase 8 Multi-Ingress Business Sample Validation Review Walkthrough v1

## 做了什么

这轮我不是只核 `28/28` 有没有通过，而是重新回到实现层看了三件事：

1. 这套多入口矩阵到底是不是按蓝图该做的那一步
2. 它是不是确实复用了 live ingress builder，而不是另造并行逻辑
3. 这套 replay 到底有没有做到“足够像 live route”

## 怎么核的

我重新检查了：

- [multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/multi_ingress_work_sample_validation.py)
- [phase8_multi_ingress_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase8_multi_ingress_work_samples_v1.json)
- [test_multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_multi_ingress_work_sample_validation.py)
- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260322/report_v1.json)
- [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py)
- [standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py)
- [routes_consult.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_consult.py)

同时我复跑了你给的：

- `pytest` 子集
- `py_compile`
- `ops/run_multi_ingress_work_sample_validation.py`

## 为什么我判断这轮方向是对的

因为这轮不是往系统里再塞一个新层，而是把：

- 单入口样本回归

推进到了：

- 多入口语义矩阵

这正好卡在蓝图最需要的那一步。

如果没有这一步，后面一旦做 full-chain replay 出现差异，就很难判断问题到底在：

- 入口适配
- scenario pack
- strategist
- 还是 runtime / knowledge 主链

所以从架构节奏看，这轮是合理且必要的。

## 为什么我还是留了一个 finding

因为 `consult_rest` 这条 replay 还没做到“完全等价于 live route”。

它今天能通过，是因为：

- 当前 `_select_consult_models(...)` 实际只看 `scenario / profile / route_hint`

所以即使验证器手工拼的 summary 比 live route 更窄，结果还是一致。

但从回归门禁质量看，这还不够严。

真正更稳的做法应该是：

- 验证器直接走和 route 一样的 `summarize_task_intake(...)`
- 以及 `summarize_scenario_pack(...)`

这样后面 consult 模型策略就算继续演化，Phase 8 的绿灯仍然可信。

## 为什么我没有把整个 Phase 8 否掉

因为这个问题不是线上行为已经错了，而是验证器 fidelity 差半步。

当前它仍然证明了最重要的一点：

- 这 4 条入口在当前这 7 个 planning/research 样本上，semantic layer 没有漂

所以阶段结论本身仍然站得住，只是不能再往上夸大成：

- 所有入口已经被 exact live-route replay 验证

## 最后结论

我把这轮定成：

- 阶段方向正确
- 结果可信
- 可以签字通过
- 但要把 `consult_rest replay fidelity` 记成下阶段前置收口项

这样 Phase 8 作为阶段完成是成立的，同时也不会把验证质量说得过头。
