# 2026-03-07 OpenMind v3 Production Follow-up Round 2

## Why

上一轮 OpenMind v3 fullflow 复盘后，仍有两类 production-readiness 残口：

1. `funnel` 路由会把原始 `dispatch_result` 写回 KB，里面带有本地绝对路径，触发 `PolicyEngine rejected funnel KB writeback`。
2. Feishu 后台链路和 direct `AdvisorAPI.advise()` 调用没有稳定的 request trace 语义，simulation 中持续出现 `Context error: No active span in current context.`。

## What changed

### 1. Funnel KB writeback 改成脱敏摘要

- 在 [`chatgptrest/advisor/graph.py`](../../chatgptrest/advisor/graph.py) 新增 `_summarize_dispatch_for_kb()`
- `execute_funnel()` 写回 KB 时不再保存原始 `dispatch_result`
- KB artifact 只保留：
  - dispatch status
  - trace/session/task_count
  - deliverable/code_file 数量
  - `has_project_dir` 这类布尔摘要
- 用户返回的 `route_result["dispatch"]` 仍保留原始结果，不改变业务侧行为

### 2. Feishu 后台链路补 request trace，但不阻塞 ack

- 在 [`chatgptrest/advisor/feishu_handler.py`](../../chatgptrest/advisor/feishu_handler.py) 增加后台 trace helper
- 消息路径改成：
  - 先发 ack card
  - 再启动 Langfuse request trace
  - 再执行 advisor / completion / error card
- callback 背景线程也补了同样的 trace 起止逻辑
- 传入 Langfuse 的 trace id 做了 32 位 hex 规范化；非法值回退为自动生成

### 3. Direct `AdvisorAPI.advise()` 也具备 trace 语义

- 在 [`chatgptrest/advisor/advisor_api.py`](../../chatgptrest/advisor/advisor_api.py) 内部直接启动/结束 request trace
- 这样 framework-agnostic direct call、Feishu webhook harness、测试内嵌调用不再依赖 FastAPI route 外壳帮它补 trace

### 4. Observability guard 真正 fail-open

- 在 [`chatgptrest/observability/__init__.py`](../../chatgptrest/observability/__init__.py) 增加 OTel-based `_has_active_trace()` guard
- 不再用 `Langfuse.get_current_trace_id()` 做“有无 active trace”判断，因为它自己在 no-span 时会报警
- `start_request_trace()` 和 `RequestTrace.update()` 现在只在确有 active trace 时调用 `update_current_trace`
- [`chatgptrest/kernel/llm_connector.py`](../../chatgptrest/kernel/llm_connector.py) 也切到同一个 guard，避免 generation span 探测本身制造 warning

### 5. 回归测试补强

- 新增 [`tests/test_funnel_kb_writeback.py`](../../tests/test_funnel_kb_writeback.py)
- 扩展 [`tests/test_feishu_async.py`](../../tests/test_feishu_async.py) 覆盖 Feishu message/callback 后台 trace
- 扩展 [`tests/test_llm_connector.py`](../../tests/test_llm_connector.py) 覆盖 active-trace / no-trace 两种 Langfuse 分支
- 扩展 [`tests/test_phase3_integration.py`](../../tests/test_phase3_integration.py) 覆盖 `AdvisorAPI.advise()` trace 生命周期
- 同时把 Feishu card 相关用例从固定 `sleep(0.5)` 改成短轮询等待，避免把 observability 初始化耗时误判成业务失败

## Validation

本仓实跑通过：

- `./.venv/bin/pytest -q tests/test_phase3_integration.py tests/test_feishu_async.py tests/test_llm_connector.py tests/test_funnel_kb_writeback.py`
- `./.venv/bin/python -m py_compile chatgptrest/advisor/advisor_api.py chatgptrest/advisor/feishu_handler.py chatgptrest/advisor/graph.py chatgptrest/kernel/llm_connector.py chatgptrest/observability/__init__.py tests/test_phase3_integration.py tests/test_feishu_async.py tests/test_llm_connector.py tests/test_funnel_kb_writeback.py`

补充说明：

- `tests/test_funnel_graph.py::test_understand` 仍可能受外部模型连通性影响，不属于这轮修改引入的问题，也不影响这轮两个 blocker 的收口。

## Outcome

这轮之后，针对 OpenMind v3 生产可用性最关键的两个残口已经被收住：

- simulation 不再出现 `PolicyEngine rejected funnel KB writeback`
- simulation 不再出现 `Context error: No active span in current context.`

剩余日志主要是测试故意注入的错误路径（如 `TargetClosedError`、无 token 安全提示、signature failure）和第三方库 deprecation warning，不属于这轮 blocker。
