# 2026-04-15 Graph 协议切分最小实现 v1

## 背景

前两步已经完成：

- `ContextResolver` 改为依赖 `ContextRuntimeDeps`
- `MemoryCaptureService` 改为依赖 `MemoryRuntimeDeps`

这一轮补齐 A 类服务的第三个收尾项：`GraphQueryService` 不再要求完整
`AdvisorRuntime` 类型，而只依赖 `GraphRuntimeDeps`。

## 代码改动

- `chatgptrest/cognitive/graph_service.py`
  - `GraphQueryService.__init__` 的 `runtime` 类型从 `AdvisorRuntime` 改为 `GraphRuntimeDeps`
- `tests/cognitive/test_graph_protocol_split.py`
  - 新增 fake runtime case：证明只要对象暴露 `evomap_knowledge_db` 字段，服务即可运行
  - 新增 real runtime adapter case：证明 `GraphRuntimeAdapter.from_runtime(...)` 投影出的最小面满足协议并可运行

## 为什么这一步成立

代码复核结果显示：

- `GraphQueryService` 在个人图谱路径中只读取 `self._runtime.evomap_knowledge_db`
- 它不依赖 `AdvisorRuntime` 的其他句柄
- 因此适合沿用前两步的协议切分策略

## 验证

执行：

```bash
.venv/bin/pytest -q \
  tests/cognitive/test_graph_protocol_split.py \
  tests/cognitive/test_context_protocol_split.py \
  tests/cognitive/test_memory_capture_protocol_split.py \
  tests/kernel/test_work_memory_manager_memory_substrate_contract.py
```

结果：

- `9 passed`

## 结论

A 类服务里当前最关键的三块都已经完成最小协议切分：

- context
- memory capture
- graph

这证明“先把大 runtime 切成最小协议面，再逐步原生化迁移”的技术路线在代码层面成立，不再只是架构文档上的判断。
