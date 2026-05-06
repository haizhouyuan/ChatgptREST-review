# 2026-03-21 Front Door Object Freeze Phase Completion v1

## 结论

`Phase 1: Front Door Object Freeze` 的实现面已完成，可以进入独立核验。

## 本阶段完成的 4 件事

### 1. canonical front-door object 已冻结并落到代码

冻结对象是 versioned `Task Intake Spec v2`：

- [task_intake.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_intake.py)

它已经承载：

- `source`
- `trace_id`
- `session_id`
- `objective`
- `decision_to_support`
- `constraints`
- `available_inputs`
- `missing_inputs`
- `scenario`
- `output_shape`
- `evidence_required`
- `acceptance`

### 2. live ingress 已统一消费同一 structured object

两条 live 路径都已经接入 shared intake normalizer：

- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)

并且已经收掉了三类精度问题：

- seeded contract 不能再丢 `goal_hint -> task_template / risk_class`
- caller 传错 `task_intake.spec_version` 会 fail-closed
- generic `thread_id + agent_id` 不再误判为 `openclaw`

### 3. `standard_entry.py` 已降为 adapter / normalizer

- [standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py)

它现在是：

- legacy carrier
- canonical task intake attachment producer

不是另一套前门 schema。

### 4. `task_spec.py` 已退为 canonical bridge

- [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py)

它现在不再单独定义一套 parallel front-door truth，而是：

- `IntentEnvelope -> Task Intake Spec -> TaskSpec`

## 这意味着什么

到这一步，`Phase 1` 的验收条件已经满足：

- `routes_agent_v3` 与 `routes_advisor_v3` 都能消费同一 structured object
- 不再存在继续增长的平行 schema 主线

更准确地说，旧 carrier 还在，但已经都被降级成：

- adapter
- compatibility bridge
- derived reasoning view

而不是 schema authority。

## 关键验证

本阶段最终验证通过的回归包括：

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

## 下一阶段

下一步不该再继续补 `Phase 1` 文档，而应该进入：

- `Phase 2: Ingress Alignment`

重点对象会变成：

- OpenClaw bridge payload
- Feishu WS / webhook ingress
- 入口侧 source / session / task_intake 对齐
