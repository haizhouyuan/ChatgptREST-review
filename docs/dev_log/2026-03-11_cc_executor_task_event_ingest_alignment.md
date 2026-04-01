# 2026-03-11 cc_executor task event ingest alignment

## Why

主线 `execution telemetry -> canonical EvoMap` 已经覆盖：

- 手工 `/v2/telemetry/ingest`
- `controller_lane_wrapper`
- OpenClaw `openmind-telemetry` plugin
- archive envelope (`agent.task.closeout` / `agent.git.commit`)
- `cc_native dispatch.task_*`

但 `cc_executor` 这条执行器路径虽然已经在发：

- `task.dispatched`
- `task.completed`
- `task.failed`

这些事件此前并没有被 `ActivityIngestService` 订阅，也不在
`ingest_activity_event()` 的相关白名单里。

结果是：

- `cc_executor` 的 live task lifecycle 没有进入 canonical EvoMap
- 现有 execution telemetry coverage 仍然缺一档

## What changed

文件：

- `chatgptrest/evomap/activity_ingest.py`
- `tests/test_activity_ingest.py`

调整：

- `register_bus_handlers()` 新增订阅：
  - `task.dispatched`
  - `task.completed`
  - `task.failed`

- `ingest_activity_event()` 的 `relevant_types` 白名单同步纳入以上三类事件

## Validation

执行：

```bash
./.venv/bin/pytest -q tests/test_activity_ingest.py
./.venv/bin/python -m py_compile \
  chatgptrest/evomap/activity_ingest.py \
  tests/test_activity_ingest.py
```

结果：

- 通过

新增覆盖：

- `tests/test_activity_ingest.py`
  - `task.completed` 经 `EventBus -> ActivityIngestService` materialize 为
    canonical `activity: task.completed`
  - 并验证：
    - `upstream_event_id` 保留
    - `event_id` 仍记录 bus event id

## Boundary

这次只收：

- `cc_executor task.*`

没有扩到：

- `gate.review_quality`
- `agent.selected`
- 任何新的 execution platform / registry / orchestration 层

这些继续留在后续 emitter coverage 的边界里逐个判断。
