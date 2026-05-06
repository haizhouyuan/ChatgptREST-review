# 2026-03-22 Phase 7 Business Work Sample Validation Review v1

## 1. 评审结论

`Phase 7` 的方向是对的，而且和蓝图一致：

- 它确实把 `planning / research` 主场景推进成了一套更接近真实业务输入的回归基线
- 它也符合“不要继续扩新层，先把强前门和高价值场景做实”的路线

但这轮**不能被写成整条 `front-door + planning/research + knowledge` 主链已经被业务样本完整验证**。

更准确的定性应该是：

- **当前已成立的是：front-door semantic regression pack**
- **当前还没有被这套 pack 证明的是：controller / knowledge runtime / multi-ingress 的业务样本级实证**

## 2. 主要发现

### Finding 1：验证模块实际只覆盖前门语义层，不是整条 knowledge/runtime 主链

[work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/work_sample_validation.py) 当前直接复用的是：

- `build_task_intake_spec`
- `resolve_scenario_pack`
- `apply_scenario_pack`
- `task_intake_to_contract_seed`
- `normalize_ask_contract`
- `build_strategy_plan`

也就是说，它验证的是：

- intake 归一
- scenario pack 命中
- AskContract 派生
- strategist clarify / route hint

它**没有**直接进入：

- `routes_agent_v3` / `routes_advisor_v3`
- `ControllerEngine`
- `context_service`
- `ingest_service`
- `advisor graph / report graph` 的真实执行链

所以 [2026-03-22_phase7_business_work_sample_validation_pack_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_phase7_business_work_sample_validation_pack_v1.md) 里把目标写成“`front-door + planning/research + knowledge 主链` 在代表性业务样本上稳定复现预期语义”，这个表述偏强。

更准确的说法应是：

- 这轮验证了 `front-door planning/research semantics`
- 但没有验证 `knowledge runtime` 的读写闭环是否在这些业务样本上被真实跑通

### Finding 2：当前样本集只验证了 `agent_v3/rest` 主入口，不是多入口业务样本回归

当前数据集 [phase7_business_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase7_business_work_samples_v1.json) 没有显式覆盖多入口来源；验证代码也默认把未指定样本落到：

- `ingress_lane = agent_v3`
- `default_source = rest`
- `raw_source = ""`

而实际跑出的 [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase7_business_work_sample_validation_20260322/report_v1.json) 里，7 个样本也全部是：

- `source = rest`
- `ingress_lane = agent_v3`

这意味着当前 pack 证明的是：

- 公开主入口的 canonical front-door 语义是稳定的

但它**没有**证明：

- `OpenClaw plugin`
- `standard_entry`
- `/v1/advisor/consult`
- `Feishu`

这些已对齐入口在相同业务样本下也稳定不漂。

## 3. 与蓝图的一致性判断

从蓝图角度，这轮总体是**符合方向**的。

[2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md) 强调了两件事：

- `OpenMind` 负责 `intake / clarify / scope`、`planning / research` 场景策略、`evidence threshold / acceptance policy`
- 近期只对 `planning / research` 做强前门，而不是继续扶正更重的执行中心

`Phase 7` 做出来的正是这条线上的样本回归基线，所以它作为**蓝图后的质量门禁雏形**是合理的。

问题不在“方向跑偏”，而在“验证口径写大了半步”。

## 4. 总评

我会给这轮一个明确判断：

- **作为 Phase 7 front-door business-sample semantic validation pack：通过**
- **作为“planning/research + knowledge 主链已被业务样本完整验证”的证明：不通过**

因此，当前最准确的阶段结论应该是：

- 系统已经进入 `business-sample validated (front-door semantics)` 状态
- 但还没有进入 `full-stack business-sample validated` 状态

## 5. 下一步建议

如果下一轮要继续收口，而不是只做措辞修正，最值得补的是两类样本：

1. **多入口样本**
   - 至少补 `OpenClaw`、`standard_entry`、`consult` 三类 business samples
2. **执行/知识闭环样本**
   - 至少补 `controller effective execution kind`
   - 至少补 `context source_planes / retrieval_plan`
   - 至少补 `knowledge ingest write_path / accepted / success`

这样下一次才有资格把阶段口径升级成更接近“full-stack business-sample validation”。
