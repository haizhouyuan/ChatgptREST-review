# 2026-03-21 Front Door Object Freeze Phase Completion v2

## 结论

`Phase 1: Front Door Object Freeze` 的 **live ingress / canonical object** 实现面已完成，可以签字进入下一阶段核验；但 `task_spec.py` 的 compatibility surface 还没有完全 fail-closed。

## 与 v1 相比的修正

`v1` 有一句话说早了半步：

- “`task_spec.py` 已退为 canonical bridge”

更准确的说法应该是：

- `task_spec.py` 已成为 canonical intake 的主要 compatibility bridge
- 但 direct `TaskSpec(...)` 构造路径仍然存在
- `task_intake` 仍是 optional compatibility field

这说明它**已经不是 schema authority**，但也**还没完全只剩 bridge 唯一路径**。

## 本阶段完成的 4 件事

### 1. canonical front-door object 已冻结并落到代码

冻结对象是 versioned `Task Intake Spec v2`：

- [task_intake.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_intake.py)

### 2. live ingress 已统一消费同一 structured object

- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)

并且已收掉共享 normalizer 的实质性回归：

- seeded contract 不再丢 `goal_hint -> task_template / risk_class`
- 错误 `task_intake.spec_version` fail-closed
- source 误判精度已收紧

### 3. `standard_entry.py` 已降为 adapter / normalizer

- [standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py)

它现在是 legacy adapter + canonical task intake attachment producer。

### 4. `task_spec.py` 已通过 canonical intake bridge 生成兼容对象

- [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py)

它当前的正确状态是：

- `IntentEnvelope -> Task Intake Spec -> TaskSpec` 这条桥已经存在
- canonical `acceptance` 和 `priority` 已可桥接到 `TaskSpec`
- 但 compatibility direct construction path 仍保留

## 验收判断

这版把验收判断拆开：

### 已满足

- `routes_agent_v3` 与 `routes_advisor_v3` 都消费同一 structured object
- canonical front-door object 已经成为 live ingress truth
- 不再存在继续扩张的平行 schema authority

### 尚未完全收口

- `task_spec.py` 的 compatibility direct-construction path 仍在
- `TaskSpec.task_intake` 仍是 optional compatibility field

## 关键验证

本阶段回归包括：

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

下一步仍然应该进入：

- `Phase 2: Ingress Alignment`

但如果后续想继续清理 compatibility surface，`task_spec.py` direct construction path 可以单列成一个后续收口项，不再混进 `Phase 1` 的 live ingress 判断。
