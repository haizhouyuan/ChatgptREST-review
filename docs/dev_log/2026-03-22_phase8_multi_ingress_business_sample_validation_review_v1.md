# 2026-03-22 Phase 8 Multi-Ingress Business Sample Validation Review v1

## 1. 评审结论

`Phase 8` 总体方向是对的，而且比 `Phase 7` 的阶段边界更准确。

这轮已经可以成立的判断是：

- `planning / research` 的 7 个代表性业务样本
- 在 `agent_v3/rest`、`standard_entry/codex`、`feishu_ws`、`consult/rest`
- 这 4 条入口形态上
- 已经具备稳定的 **multi-ingress semantic validation**

这和蓝图“先把 planning/research 做成强前门质量门禁，再往下扩验证层级”的方向是一致的。

但这轮还存在 1 个实现 fidelity 问题，意味着它虽然足够作为阶段性质量门禁，却还不能被当成“所有入口 replay 都已经完全等价于 live route”。

## 2. 主要发现

### Finding 1：`consult_rest` 的 replay 还不是 live route 的完全同一路径

[2026-03-22_phase8_multi_ingress_business_sample_validation_pack_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_phase8_multi_ingress_business_sample_validation_pack_v1.md) 把 `consult_rest` 写成：

- `task_intake + scenario_pack + consult model policy`

主结论本身是成立的，但 [multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/multi_ingress_work_sample_validation.py) 对 `consult_rest` 的 replay 仍然不是 route 里的完全同一条 summary path。

当前验证器在 [multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/multi_ingress_work_sample_validation.py#L363) 到 [multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/multi_ingress_work_sample_validation.py#L372) 手工拼了：

- `task_intake_summary = {scenario, ingress_lane, source}`
- `scenario_pack_summary = scenario_pack.to_dict()`

然后再调用 `_select_consult_models(...)`。

但 live `/v1/advisor/consult` route 实际走的是：

- `summarize_task_intake(task_intake)`
- `summarize_scenario_pack(scenario_pack)`
- 再调 `_select_consult_models(...)`

见 [routes_consult.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_consult.py#L469) 到 [routes_consult.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_consult.py#L476)。

这意味着：

- **今天**这套验证结果是可信的，因为当前 `_select_consult_models(...)` 只实际依赖 `scenario / profile / route_hint`
- **但明天**如果 `consult` 模型策略开始依赖更多 summary 字段，这个 eval 可能继续绿，而 live route 已经漂了

所以这不是现成线上 bug，但它是一个真实的 regression-fidelity 缺口。

## 3. 蓝图一致性判断

从蓝图角度，这轮是通过的。

[2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md) 和 [2026-03-20_post_reconciliation_next_phase_plan_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_post_reconciliation_next_phase_plan_v2.md) 的主线都是：

- 先收 front door object
- 再做 planning / research 场景包
- 再做质量门禁
- 不急着扩更重的新执行层

`Phase 8` 正是在这个顺序上往前推进了一步：

- 从 `Phase 7` 的单入口样本回归
- 推进到了多入口语义矩阵

这一点和蓝图没有冲突。

## 4. 总评

我的总评是：

- **作为 Phase 8 multi-ingress semantic validation：通过**
- **作为“所有入口 replay 已经完全等价于 live route”的证明：暂不通过**

换句话说，这轮可以签字作为阶段完成，但它更像：

- `multi-ingress business-sample semantic validated`

还不是：

- `exact multi-ingress live-route replay validated`

## 5. 残留风险

当前最值得记住的残留不是“结果不可信”，而是“验证器 fidelity 还差最后半步”：

1. `consult_rest` 应该改成走和 route 一样的 `summarize_* -> _select_consult_models(...)` 路径
2. `feishu_ws` 当前验证的是 text-message payload path，不是附件/富上下文场景
3. `OpenClaw` TypeScript plugin 仍然没有进入动态 replay

## 6. 下一步建议

如果继续往下做，最自然的顺序是：

1. 先把 `consult_rest` replay 收成和 live route 完全同路径
2. 再补 `OpenClaw plugin` dynamic replay
3. 最后再进入 `route handler / controller / knowledge-runtime` 的 full-chain business-sample validation

这样 Phase 9 往后就不会一边扩验证，一边背着 replay fidelity 债。
