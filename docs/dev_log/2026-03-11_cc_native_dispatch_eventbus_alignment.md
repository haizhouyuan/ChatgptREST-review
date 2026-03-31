# 2026-03-11 cc_native dispatch EventBus alignment

## Why

主线 `execution telemetry -> canonical EvoMap` 已经打通了：

- 手工 `/v2/telemetry/ingest`
- `controller_lane_wrapper`
- OpenClaw `openmind-telemetry` plugin
- archive envelope (`agent.task.closeout` / `agent.git.commit`)

但 `cc_native` 这条执行器路径仍有一个明显断点：

- `dispatch.task_started` 走 `EventBus`
- `dispatch.task_completed` / `dispatch.task_failed` 只走 `_record_signal(...)`
- `ActivityIngestService.register_bus_handlers()` 也没有订阅 `dispatch.task_*`

结果是：

- `signals.py` 已经把 `dispatch.task_completed` / `dispatch.task_failed` 定义为 canonical signal
- 但 live canonical EvoMap 对这条执行器链的 coverage 不完整

## What changed

### 1. `cc_native.dispatch_headless()` success/failure 也发 `EventBus`

文件：

- `chatgptrest/kernel/cc_native.py`

调整：

- 成功时：在原有 `_record_signal("dispatch.task_completed", ...)` 之前，新增 `_emit_event("dispatch.task_completed", ...)`
- 失败时：在原有 `_record_signal("dispatch.task_failed", ...)` 之前，新增 `_emit_event("dispatch.task_failed", ...)`

保持不变：

- observer/signal 路径保留
- memory / routing_fabric 语义不变

### 2. `ActivityIngestService` 订阅 `dispatch.task_*`

文件：

- `chatgptrest/evomap/activity_ingest.py`

调整：

- `register_bus_handlers()` 新增：
  - `dispatch.task_started`
  - `dispatch.task_completed`
  - `dispatch.task_failed`
- `ingest_activity_event()` 的 `relevant_types` 白名单同步纳入以上三类事件

## Validation

执行：

```bash
./.venv/bin/pytest -q tests/test_activity_ingest.py tests/test_team_integration.py
./.venv/bin/python -m py_compile \
  chatgptrest/kernel/cc_native.py \
  chatgptrest/evomap/activity_ingest.py \
  tests/test_activity_ingest.py \
  tests/test_team_integration.py
```

结果：

- 通过

新增覆盖：

- `tests/test_activity_ingest.py`
  - `dispatch.task_completed` 通过 `EventBus -> ActivityIngestService` 进入 canonical atom
- `tests/test_team_integration.py`
  - `dispatch_headless()` success 会发 `dispatch.task_completed`
  - `dispatch_headless()` failure 会发 `dispatch.task_failed`

## Boundary

这次只收：

- `cc_native`
- `dispatch.task_*`

没有扩到：

- `cc_executor task.*`
- `gate.review_quality`
- `agent.selected`

这些留到下一轮 emitter coverage，再单独评估是否应该进 live canonical plane。
