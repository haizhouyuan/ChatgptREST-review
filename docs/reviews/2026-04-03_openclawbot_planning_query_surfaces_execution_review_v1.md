# 2026-04-03 OpenClawBot Planning Query Surfaces Execution Review v1

## 1. 这批改动解决了什么

这批不是再扩 surface，而是把已经暴露出来的 planning 查询面收紧到可继续使用的程度。

主要落点有三条：

1. `openmind_advisor_task_get` 不再把原始 planning task payload 直接回给 OpenClaw。
2. `openmind_advisor_task_list` / `openmind_advisor_session_get` 现在只返回摘要化后的 public fields。
3. planning task 的 `GET/list` read-path refresh 不再无条件写盘，也不再因为 refresh 异常把读接口拖死。

对应代码：

- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L2356)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L2411)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L2448)
- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L323)
- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L404)
- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L425)
- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L815)
- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L864)
- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L883)

## 2. 我独立确认成立的事实

### 2.1 Plugin 侧查询面已明显收紧

现在的 plugin 不再把 raw payload 原样透给 OpenClaw：

- `task_get` 经过 `summarizePlanningTaskPayload(...)`
- `task_list` 经过 `summarizePlanningTasks(...)`
- `session_get` 经过 `summarizeSessionPayload(...)`

另外，`session_get` 现在要求 runtime session 身份，且显式 cross-session lookup 会 fail-closed。

对应代码：

- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L323)
- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L404)
- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L425)
- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L883)

### 2.2 Read-path refresh 仍然存在，但已经从“硬 bug”收紧成“设计权衡”

红队第一次审稿里最硬的问题是：

1. `GET /planning/task/*`
2. `GET /planning/tasks`

会在每次读的时候刷新 session，并直接写回 planning task layer，导致：

- 普通 polling 也会改 durable state
- refresh 抛错会把 GET/list 直接拖死

这次我接受并修了其中的 bug 部分：

1. 只有当 `status / checkpoint / latest_output / artifact_refs / latest_session_id` 与 session 刷新后的期望值真的不一致时，才 writeback。
2. refresh 失败时记录 warning 并回退到 stored payload。

对应代码：

- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L2411)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L2448)

我不把这件事说成“完全解决”，因为 read-time refresh 这个设计本身还在。但它已经不再是无条件写盘 + 读接口脆断的 bug。

### 2.3 `cancelled` 映射现在已经打通

之前 `cancelled` 会在：

- live completion gate
- planning task store

两边落成错误 public status / checkpoint state。

这次已补齐：

- [meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py#L194)
- [meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py#L218)
- [meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py#L225)
- [live_completion_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/openclawbot_planning_task_plane_live_completion_gate.py#L379)

## 3. 验证

通过的测试：

- [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py#L430)
- [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py#L543)
- [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py#L661)
- [test_meeting_task_store.py](/vol1/1000/projects/ChatgptREST/tests/test_meeting_task_store.py#L153)
- [test_openclawbot_planning_task_plane_live_completion_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_openclawbot_planning_task_plane_live_completion_gate.py#L180)
- [test_run_openclawbot_planning_task_plane_live_completion_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py#L33)
- [test_openclaw_cognitive_plugins.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py#L58)

执行命令：

```bash
python3 -m py_compile \
  chatgptrest/api/routes_agent_v3.py \
  chatgptrest/planning/meeting_task_store.py \
  chatgptrest/eval/openclawbot_planning_task_plane_live_completion_gate.py \
  ops/run_openclawbot_planning_task_plane_live_completion_gate.py

./.venv/bin/pytest -q \
  tests/test_routes_agent_v3_planning_task_plane.py \
  tests/test_meeting_task_store.py \
  tests/test_openclawbot_planning_task_plane_live_completion_gate.py \
  tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py \
  tests/test_openclaw_cognitive_plugins.py
```

## 4. 还没解决的部分

我当前不把下面两条说成“已解决”：

1. `GET/list` 仍是 stateful read，只是已经不再无条件写盘。
2. `/v3/agent/session/{session_id}` 后端 REST surface 本身仍然比 plugin 侧更宽。

当前判断：

- 第一条是 phase-1 设计权衡，先留在计划里，不阻断这批收口。
- 第二条是后续需要单独收的 server-side boundary，不在这批里硬改。
