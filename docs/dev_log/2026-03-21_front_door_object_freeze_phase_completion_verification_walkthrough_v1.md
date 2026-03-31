# 2026-03-21 Front Door Object Freeze Phase Completion Verification Walkthrough v1

## 目标

独立核验 `Phase 1: Front Door Object Freeze` 的实现完成度，不直接沿用阶段完成文档的结论，而是重新回到代码、测试与最小复现来判断：

- live ingress 是否已经统一到 canonical `Task Intake Spec`
- legacy adapter 是否已经降级
- `task_spec.py` 是否真的只剩 compatibility bridge

## 本轮实际做的事

### 1. 先核对阶段完成文档与当前 HEAD

读取：

- `docs/dev_log/2026-03-21_front_door_object_freeze_phase_completion_v1.md`

并确认当前阶段完成提交位于：

- `8572693`

### 2. 重新检查 4 个关键代码面

逐个复核了：

- `chatgptrest/advisor/task_intake.py`
- `chatgptrest/api/routes_agent_v3.py`
- `chatgptrest/api/routes_advisor_v3.py`
- `chatgptrest/advisor/standard_entry.py`
- `chatgptrest/advisor/task_spec.py`

复核重点不是“有没有 shared normalizer”，而是：

- live 入口是否真正共用 canonical intake
- compatibility 对象是否还能绕开 canonical intake 自己长
- canonical 字段在 bridge 过程中是否有丢失

### 3. 确认 live ingress 主链已经收敛

确认成立的点：

- `routes_agent_v3.py` 会先构造 canonical `task_intake`，再派生 seed 给 `AskContract`
- `routes_advisor_v3.py` 会把 canonical `task_intake` 注入 `stable_context`
- `standard_entry.py` 已收敛成 legacy adapter，并附着 canonical `task_intake`
- `task_intake.spec_version` 错误会在 live 入口 fail-closed 成 `400`

### 4. 发现 compatibility bridge 仍有两个残余精度问题

第一处：

- `TaskSpec` 仍允许直接实例化
- `task_intake` 仍是可选字段
- 测试仍明确保留这条直接构造路径

这说明 `task_spec.py` 已经“以 canonical intake 为主”，但还没有完全收成“只能从 canonical intake 派生”。

第二处：

- `task_intake_to_task_spec(...)` 没有把 canonical `priority` 传给 `TaskSpec.priority`

我额外跑了最小复现，确认：

- canonical `priority=1`
- bridge 后 `TaskSpec.priority` 回到默认 `5`

### 5. 复跑回归与语法检查

本轮重新执行并通过：

```bash
./.venv/bin/pytest -q \
  tests/test_task_intake.py \
  tests/test_routes_agent_v3.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_agent_v3_routes.py \
  tests/test_system_optimization_v2.py

./.venv/bin/pytest -q tests/test_system_optimization.py -k 'StandardEntry'

python3 -m py_compile \
  chatgptrest/advisor/task_intake.py \
  chatgptrest/advisor/standard_entry.py \
  chatgptrest/advisor/task_spec.py \
  chatgptrest/api/routes_agent_v3.py \
  chatgptrest/api/routes_advisor_v3.py \
  tests/test_task_intake.py \
  tests/test_routes_agent_v3.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_system_optimization.py \
  tests/test_system_optimization_v2.py
```

## 最终判断

我的最终判断不是“Phase 1 失败”，而是：

- live ingress freeze 已经完成
- 文档里把 compatibility bridge 说成“已经完全 freeze”仍然偏强

如果下一步继续实现而不是只写文档，最自然的收口顺序是：

1. 先让 `task_intake_to_task_spec(...)` 保留 canonical `priority`
2. 再决定是否要把 `TaskSpec` 直接构造路径显式降级、告警，或最终收紧

## 产物

本轮新增：

- `docs/dev_log/2026-03-21_front_door_object_freeze_phase_completion_verification_v1.md`
- `docs/dev_log/2026-03-21_front_door_object_freeze_phase_completion_verification_walkthrough_v1.md`
