# 2026-03-22 Phase 8 Multi-Ingress Business Sample Validation Completion Walkthrough v1

## 做了什么

1. 新增多入口业务样本验证器：
   - [multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/multi_ingress_work_sample_validation.py)
2. 固化多入口矩阵数据集：
   - [phase8_multi_ingress_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase8_multi_ingress_work_samples_v1.json)
3. 新增运行脚本：
   - [run_multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_multi_ingress_work_sample_validation.py)
4. 新增定向测试：
   - [test_multi_ingress_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_multi_ingress_work_sample_validation.py)
5. 生成阶段产物：
   - [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260322/report_v1.json)
   - [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260322/report_v1.md)

## 为什么这么做

`Phase 7` 之后，最自然的下一步不是立刻跳 full-stack，
而是先验证：

- 同一批业务样本
- 在多个真实入口上
- semantic layer 是否一致

这一步如果不做，后面再做 controller/runtime/knowledge 主链验证时，
一旦出现差异，就很难判断问题到底在：

- 入口 payload
- scenario pack
- strategist
- 还是 runtime/knowledge 链

## 怎么做的

### agent_v3/rest

直接复用了 canonical front-door 语义链：

- `build_task_intake_spec`
- `resolve_scenario_pack`
- `apply_scenario_pack`
- `normalize_ask_contract`
- `build_strategy_plan`

### standard_entry/codex

没有手抄 adapter 逻辑，而是直接复用了：

- `normalize_request(source="codex")`

然后把它产出的 canonical `task_intake` 投到同一条 semantic snapshot。

### feishu_ws

没有手写一份 Feishu payload，而是直接复用了：

- `_build_advisor_api_payload(...)`

再把其中的 `task_intake` 投到同一条 semantic snapshot。

### consult/rest

这条入口不只看 route 语义，还额外验证：

- `_select_consult_models(...)`

所以它既验证 profile/route，也验证 deep research / report-grade 模型策略。

## 跑了什么

```bash
./.venv/bin/pytest -q tests/test_multi_ingress_work_sample_validation.py tests/test_work_sample_validation.py tests/test_system_optimization.py tests/test_feishu_ws_gateway.py tests/test_advisor_consult.py -k 'multi_ingress or work_sample or StandardEntry or build_advisor_api_payload or consult_research_report_defaults_to_report_grade_models or consult_research_defaults_to_deep_research_models'
python3 -m py_compile chatgptrest/eval/multi_ingress_work_sample_validation.py ops/run_multi_ingress_work_sample_validation.py tests/test_multi_ingress_work_sample_validation.py
PYTHONPATH=. ./.venv/bin/python ops/run_multi_ingress_work_sample_validation.py
```

## 结果

运行结果：

- `items=7`
- `cases=28`
- `passed=28`
- `failed=0`

## 边界

这轮没有做：

- OpenClaw plugin TS 动态 replay
- route handler / controller / knowledge runtime 的 full-chain replay

所以阶段口径必须停在：

- **multi-ingress semantic validation**

不能扩大成：

- full-stack business-sample validation
