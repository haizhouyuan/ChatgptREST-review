# 2026-03-21 Task Spec Canonical Bridge Alignment v1

## 1. 这轮做了什么

这轮把 [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py) 从“旧独立 schema 草稿”收成了 **canonical task intake 的兼容桥**。

现在它的定位是：

- `IntentEnvelope`：raw compatibility envelope
- `Task Intake Spec`：真正的 versioned canonical object
- `TaskSpec`：从 canonical intake 派生出来的 legacy-compatible dispatch object

这一步的目的不是把 `TaskSpec` 扶正，而是终止它继续作为第二套前门 schema 漂着长。

## 2. 独立判断

前面已经完成了两件关键事：

- live ingress 已统一到 shared `task_intake`
- `standard_entry.py` 已经退成 legacy adapter + canonical attachment

如果 `task_spec.py` 还继续维持旧的独立字段集，`Phase 1` 仍然不能算完成，因为 parallel schema 还在。

所以这轮的正确做法不是“再给旧 `TaskSpec` 打补丁”，而是：

- 保留旧 carrier 名字，避免系统优化测试和周边引用炸掉
- 但让它的生成路径必须经过 canonical intake

## 3. 具体实现

### 3.1 `AcceptanceSpec` 不再单独漂移

文件：

- [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py)

`task_spec.AcceptanceSpec` 现在直接桥到 canonical acceptance schema，上层兼容调用还可以继续 import 这个名字，但不再维持一套独立三档定义。

### 3.2 新增 canonical bridge helpers

新增两条桥接函数：

- `intent_envelope_to_task_intake(...)`
- `task_intake_to_task_spec(...)`

含义很明确：

- `IntentEnvelope` 先被归一成 versioned `Task Intake Spec`
- 再由 canonical intake 派生 legacy-compatible `TaskSpec`

### 3.3 `envelope_to_task_spec(...)` 不再直接发明第二套对象

它现在内部流程变成：

1. `IntentEnvelope`
2. `Task Intake Spec`
3. `TaskSpec`

这意味着：

- `TaskSpec.source` 现在是 canonical source，不再直接继承 legacy raw source
- `TaskSpec.acceptance` 现在来自 canonical intake
- `TaskSpec.task_intake` 会把 canonical object 一起带下来

### 3.4 文本启发式没有丢

为了不让旧系统优化测试退化，这轮保留了文本级启发式：

- 原来 `IntentEnvelope.raw_text` 能推到 `research_memo`
- 现在仍然会通过 `intent_envelope_to_task_intake(...)` 的 text fallback 把研究类文本导向 `scenario=research`

所以这是“通过 canonical bridge 保住旧行为”，不是“退回旧逻辑”。

## 4. 兼容策略

这轮是桥接，不是清场。

保留的旧面：

- `IntentEnvelope`
- `TaskSpec`
- `envelope_to_task_spec(...)`

新增但不强推替换的 canonical bridge：

- `intent_envelope_to_task_intake(...)`
- `task_intake_to_task_spec(...)`

## 5. 测试

更新了 [tests/test_system_optimization_v2.py](/vol1/1000/projects/ChatgptREST/tests/test_system_optimization_v2.py)，新增验证：

- `codex` legacy source 经 bridge 后会进入 canonical `cli`
- `AcceptanceSpec` 支持 canonical `research` profile
- `envelope_to_task_spec(...)` 产物里带 canonical `task_intake`
- `task_intake_to_task_spec(...)` 会继承 canonical acceptance/profile/source

通过：

```bash
./.venv/bin/pytest -q tests/test_system_optimization_v2.py
python3 -m py_compile chatgptrest/advisor/task_spec.py tests/test_system_optimization_v2.py
```

## 6. 结果

`task_spec.py` 现在不再是另一套平行 front-door schema，而是 canonical intake 的兼容桥。

这让 `Phase 1: Front Door Object Freeze` 的实现面基本闭环：

- live ingress 已统一
- `standard_entry` 已收成 adapter
- `task_spec.py` 已退成 canonical bridge
- `ask_contract` 已是 derived reasoning view
