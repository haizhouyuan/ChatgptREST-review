# 2026-03-21 Task Spec Canonical Bridge Alignment Walkthrough v1

## 为什么这一步是 Phase 1 的最后一块

如果只做：

- `routes_agent_v3`
- `routes_advisor_v3`
- `standard_entry`

而不处理 `task_spec.py`，系统里仍然存在一套“名字像 canonical schema、实现却不是”的对象层。

这会让后续所有人继续在两个地方找前门真相：

- `task_intake.py`
- `task_spec.py`

这是 `Phase 1` 最不该留的歧义。

## 风险判断

GitNexus impact 这轮整体是低风险：

- `AcceptanceSpec`: `LOW`
- `TaskSpec`: `LOW`
- `IntentEnvelope`: `MEDIUM`
- `envelope_to_task_spec`: `LOW`

而且实际调用面基本只在 [tests/test_system_optimization_v2.py](/vol1/1000/projects/ChatgptREST/tests/test_system_optimization_v2.py)。

所以这里适合做“结构收口”，不适合继续搁置。

## 关键实现决策

### 1. 不把 `TaskSpec` 删除

直接删掉它当然最干净，但这会把兼容调用面和系统优化测试一起炸掉。

这轮选择的是：

- 旧名字保留
- 旧对象保留
- 但生成路径必须经过 canonical intake

### 2. 不让 `task_spec.py` 再维持自己的 acceptance/source 逻辑

真正该冻结的是 canonical intake。

所以 `task_spec.py` 只保留桥接职责，不再继续发展自己的平行字段语义。

## 结果

这轮之后，`task_spec.py` 的角色终于讲得清了：

- 不是 live truth
- 不是第二套 front-door schema
- 是 canonical intake 的 compatibility bridge

这也是把 `Phase 1: Front Door Object Freeze` 从“方向对了”推进到“实现面闭环”的关键一步。
