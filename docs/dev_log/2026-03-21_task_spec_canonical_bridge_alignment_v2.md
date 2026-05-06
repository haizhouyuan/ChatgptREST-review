# 2026-03-21 Task Spec Canonical Bridge Alignment v2

## 1. 这轮修正了什么

`v1` 的主方向是对的，但 reviewer 指出的两个点里，我独立判断后只把其中一个当作实实现缺口：

- `priority` 经过 `Task Intake Spec -> TaskSpec` 桥接时丢失：这是实 bug，已修
- `TaskSpec` 仍可直接实例化、`task_intake` 仍可选：这是 compatibility surface 仍在，不是这一轮必须强制 fail-closed 的实现 bug

所以这版做了两件事：

1. 修复 canonical `priority` 的桥接丢失
2. 收紧文档口径，不再把 compatibility surface 说成已经完全 freeze

## 2. 实现修复

文件：

- [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py)

`task_intake_to_task_spec(...)` 现在会显式继承 canonical `priority`：

- `intake.priority is not None -> TaskSpec.priority = intake.priority`
- 否则仍回落到兼容默认值 `5`

这意味着 canonical intake 里已经存在的优先级不会在 bridge 上被吃掉。

## 3. 测试

更新了 [tests/test_system_optimization_v2.py](/vol1/1000/projects/ChatgptREST/tests/test_system_optimization_v2.py)，新增：

- `test_task_intake_to_task_spec_preserves_canonical_priority`

通过：

```bash
./.venv/bin/pytest -q tests/test_system_optimization_v2.py
python3 -m py_compile chatgptrest/advisor/task_spec.py tests/test_system_optimization_v2.py
```

## 4. 文档口径修正

从 `v2` 开始，`task_spec.py` 的更准确表述是：

- 它已经成为 canonical intake 的主要 compatibility bridge
- 但 compatibility surface 还没有 fail-closed
- `TaskSpec(...)` 的 direct construction path 仍然存在
- `task_intake` 仍然是 optional compatibility field

这意味着：

- 不能再把它表述成“只剩 bridge、没有旁路”
- 但也不能因为旁路还在，就否定它已经不再是 schema authority 这件事

## 5. 结果

现在更准确的结论是：

- `Phase 1` 的 **live ingress freeze** 可以签字
- `task_spec.py` 的 **compatibility surface** 还没有完全收口
- 这不是 `Phase 1` 失败，而是下一轮兼容面裁剪时要继续处理的点
