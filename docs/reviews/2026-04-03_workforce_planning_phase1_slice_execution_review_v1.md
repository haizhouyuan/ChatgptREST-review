# 2026-04-03 Workforce Planning Phase-1 Slice Execution Review v1

## 1. 这一步做了什么

这一步没有再扩大会话平台，而是在现有 `meeting_sedimentation` continuity sidecar 上补了第二条最接近的 planning 任务类型：

1. `workforce_planning`

落到代码上的变化是：

1. `meeting_task_store.py` 从“只承载会议沉淀”扩成“同一 sidecar 支持多种 phase-1 planning task type”
2. `/v3/agent/turn` 不再把 continuity 命中硬编码成 `meeting_sedimentation`
3. `/v3/agent/planning/task/{task_id}` 与 `planning_task_checkpoint_writeback.py` 现在都可服务 `workforce_planning`

## 2. 成立的事实

### 2.1 continuity sidecar 现在支持两类 task type

当前支持：

1. `meeting_sedimentation`
2. `workforce_planning`

二者现在都有：

1. 稳定 `task_id`
2. 最小 checkpoint
3. 显式 retrieve
4. 深度工作台显式 writeback

### 2.2 task id 与 checkpoint 已区分 task type

当前约定：

1. `mtg_` -> `meeting_sedimentation`
2. `wfp_` -> `workforce_planning`

且 checkpoint 也会带：

1. `task_type`
2. 对应的 `checkpoint_version`

### 2.3 agent_v3 已按 scenario/context 解析 planning task type

当前 `/v3/agent/turn` 的 planning continuity 命中逻辑是：

1. 优先读显式 `planning_task_type`
2. 否则读 `scenario_pack.profile`
3. 当前命中：
   - `meeting_summary -> meeting_sedimentation`
   - `workforce_planning -> workforce_planning`

## 3. 这一步为什么值得做

到 `v8` 为止，phase-1 continuity 只有会议沉淀一条线。

这会导致一个问题：

1. 总计划虽然已经把 `人员规划` 列为 P0 验收场景
2. 但任务层 continuity 仍然只证明了“会议”能继续

这一步的价值就是把第二个 P0 planning 类型也接入同一最小连续性规则，而不是继续让 phase-1 停留在单一会议特例。

## 4. 本地验证

已通过：

```bash
python3 -m py_compile \
  chatgptrest/planning/meeting_task_store.py \
  chatgptrest/api/routes_agent_v3.py \
  tests/test_meeting_task_store.py \
  tests/test_routes_agent_v3_meeting_task_layer.py \
  tests/test_planning_task_checkpoint_writeback.py

./.venv/bin/pytest -q \
  tests/test_meeting_task_store.py \
  tests/test_routes_agent_v3_meeting_task_layer.py \
  tests/test_planning_task_checkpoint_writeback.py

./.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py \
  tests/test_agent_v3_routes.py \
  tests/test_public_agent_mcp_validation.py \
  tests/test_openclaw_cognitive_plugins.py
```

## 5. 当前边界

这一步完成后，应准确表述为：

1. phase-1 continuity sidecar 已覆盖两类 planning task type
2. 但仍不是 full task runtime
3. 也还不是通用 planning task platform

## 6. 一句话结论

`meeting_sedimentation` 不再是 phase-1 continuity 的唯一切片；`workforce_planning` 已进入同一最小 `task_id + checkpoint + retrieve + writeback` 规则。
