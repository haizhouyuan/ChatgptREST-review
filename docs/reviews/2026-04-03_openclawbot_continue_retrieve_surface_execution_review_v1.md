# 2026-04-03 OpenClawBot Continue/Retrieve Surface Execution Review v1

## 1. 这一步做了什么

这一步没有扩成新的大平台，而是只把 `OpenClawBot` 侧最小的 `continue / retrieve` 面做出来。

本次新增成立的是：

1. `openmind_advisor_ask` 可以显式带 `taskId`
2. `openmind_advisor_ask` 可以显式带 `taskAction`
3. `meeting_sedimentation` 的 `checkpoint` 可以按 `task_id` 直接读回
4. `OpenClawBot` 不再只能依赖“同 identity + 材料重叠”的隐式继续

## 2. 实际代码改动

### 2.1 ChatgptREST 侧

新增了一个很窄的只读 surface：

1. `GET /v3/agent/planning/task/{task_id}`

它返回：

1. `task_id`
2. `planning_task`

其中 `planning_task` 当前至少包含：

1. `task_id`
2. `task_type`
3. `status`
4. `objective`
5. `latest_session_id`
6. `resolution`
7. `reason`
8. `checkpoint`

### 2.2 MeetingTaskStore 侧

`MeetingTaskStore` 新增：

1. `get_public(task_id)`

它不是新 truth layer，只是把当前 phase-1 的 durable sidecar 用统一公共投影形式读出来。

### 2.3 OpenClaw plugin 侧

`openmind-advisor` 新增两类能力：

1. `openmind_advisor_ask`
   - 新增 `taskId`
   - 新增 `taskAction`
   - 会把 `task_id / planning_task_id / logical_task_id / planning_task_action` 写进 runtime context
   - 会把 `task_id` 写进 `task_intake`
2. `openmind_advisor_task_get`
   - 按 `taskId` 读回当前 planning checkpoint

## 3. 为什么这一步是对的

这一步对，是因为它正好补在前面已经明确的 gap 上：

1. phase-1 之前只有 `task_id + checkpoint` 的 sidecar
2. 但 `OpenClawBot` 没有显式控制面去“继续某个 task”或“读回某个 task”

所以这一步做的不是：

1. 把 `task_runtime` 接进来
2. 把 `publicagentmcp` 继续做厚
3. 把 `OpenClawBot` 变成 orchestration facade

它做的只是：

1. 给 `OpenClawBot` 一条显式 `task_id continue` 面
2. 给 `OpenClawBot` 一条显式 `task_id retrieve` 面

## 4. 我对这一步的独立判断

### 4.1 成立的部分

成立：

1. 这一步已经把“显式 continue / retrieve surface”从文档口径变成了真实代码能力
2. 它仍然保持在 phase-1 窄切片范围内
3. 它没有把 `publicagentmcp` 拉回大杂烩方向

### 4.2 不能夸大的部分

不能夸大成：

1. `OpenClawBot` 已经完成统一逻辑任务层
2. `task_id` 已经成了 repo 级 canonical task truth
3. 所有 planning 任务类型都已经有 continue / retrieve 面

当前更准确的说法是：

1. `meeting_sedimentation` 这条 phase-1 切片现在已经有最小显式 continue / retrieve 面
2. 这个 surface 仍然是 sidecar truth，不是 full task runtime

## 5. 本地验证

本次直接通过：

1. `python3 -m py_compile chatgptrest/planning/meeting_task_store.py chatgptrest/api/routes_agent_v3.py tests/test_meeting_task_store.py tests/test_routes_agent_v3_meeting_task_layer.py tests/test_openclaw_cognitive_plugins.py`
2. `./.venv/bin/pytest -q tests/test_meeting_task_store.py tests/test_routes_agent_v3_meeting_task_layer.py tests/test_openclaw_cognitive_plugins.py tests/test_openclaw_dynamic_replay_gate.py`

新增验证点包括：

1. `MeetingTaskStore.get_public(...)` 投影可读
2. `/v3/agent/planning/task/{task_id}` 可以返回 checkpoint
3. `/v3/agent/planning/task/{task_id}` 对未知 task 返回 404
4. 显式 `task_id` 可以驱动 meeting task continue

## 6. Claude 红队状态

本次按要求再次发起了 `claudegac` 红队：

1. `ccjob_20260402T181640Z_72fd347f`

但这轮没有拿到有效 verdict，原因不是代码失败，而是：

1. `API Error: 402 {"error":"Insufficient credits"}`

所以这一步当前最准确的状态是：

1. 本地代码与测试已通过
2. 红队已发起
3. 最终外部 sign-off 因 credits 不足待补跑

## 7. 一句话结论

这一步已经把 `OpenClawBot` 对 `meeting_sedimentation` 的最小显式 `continue / retrieve` 面落成真实代码，但它仍然只是 phase-1 continuity sidecar，不是 full planning task platform。
