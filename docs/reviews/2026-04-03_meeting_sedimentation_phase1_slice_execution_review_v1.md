# 2026-04-03 Meeting Sedimentation Phase-1 Slice Execution Review v1

## 1. 本次实际完成了什么

这次不是继续写规格，而是把 `会议沉淀` phase-1 的第一条最小 continuity slice 真正接到了运行代码里。

本次实现完成了 4 件事：

1. 新增一个独立的 `meeting task store`
2. 在 `/v3/agent/turn` 的 `meeting_summary / meeting_sedimentation` 路径上自动分配或继续 `task_id`
3. 在 turn 完成或 clarify 时自动写回最小 checkpoint
4. 把这层信息稳定投影到 response / session surface

## 2. 代码落点

### 2.1 新增模块

1. [meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py)
2. [__init__.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/__init__.py)

### 2.2 接线位置

1. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)

这次没有把 `task_runtime` 拉进来，也没有新增一套大而全的 task API。

## 3. 当前实现语义

### 3.1 命中条件

只有下面这些情况才会启用这条 continuity sidecar：

1. `scenario_pack.profile == meeting_summary`
2. `task_intake.output_shape == meeting_summary`
3. `context.planning_task_type == meeting_sedimentation`

所以这条实现当前是窄切片，不会污染其它 planning 场景。

### 3.2 新任务 / 继续任务

当前规则收得很窄：

1. caller 显式传 `task_id` 时，优先继续该任务
2. 同一 identity 且材料集合有重叠时，继续同一任务
3. 同一 identity 但材料完全不重叠时，分配新任务

这里的 identity 当前优先用：

1. `account_id + thread_id`
2. 不足时退到 `user_id / session_id`

### 3.3 最小 checkpoint

当前实际写回的 checkpoint 是：

1. `task_id`
2. `task_type=meeting_sedimentation`
3. `source_materials`
4. `current_state`
5. `latest_output`
6. `next_step`
7. `last_surface`
8. `last_session_id`
9. `last_updated_at`

这比最初冻结的最小 6 字段略多一点，但仍然是 handoff 快照，不是 transcript 备份。

## 4. 当前通过了哪些验证

### 4.1 新增测试

1. [test_meeting_task_store.py](/vol1/1000/projects/ChatgptREST/tests/test_meeting_task_store.py)
2. [test_routes_agent_v3_meeting_task_layer.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_meeting_task_layer.py)

覆盖点：

1. 材料重叠时继续旧任务
2. 材料完全不重叠时新开任务
3. completed turn 后 checkpoint 自动更新
4. `/v3/agent/turn` 响应和 `/v3/agent/session/{session_id}` 都能看到 `task_id + checkpoint`

### 4.2 回归点

已补跑并通过：

1. `tests/test_routes_agent_v3.py::test_agent_turn_auto_captures_post_call_triage_effect`
2. `tests/test_routes_agent_v3.py::test_agent_turn_clarify_gate_auto_captures_handoff_effect`
3. [test_public_agent_mcp_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_public_agent_mcp_validation.py)

## 5. 这次没有做什么

这次明确没有做：

1. 没把 `task_runtime` 升成生产承重层
2. 没做通用多任务平台
3. 没做复杂 branch 策略
4. 没把 `OpenClawBot` 改成完整 status/wait/task browser
5. 没做深度工作台主动写 checkpoint 的独立命令面

## 6. 独立判断

这一步已经满足了 phase-1 的一个关键门槛：

> `meeting_sedimentation` 不再只有“入口链已通”的证明，而已经有了第一条真实的 `task_id + checkpoint` continuity carrier。

但它还不能被夸大成“任务层已经完整落地”。

更准确的说法是：

1. `知识层` 继续补齐
2. `任务层` 已经从 paper design 进入第一条真实生产切片
3. 下一步应继续补 `OpenClawBot continue/retrieve surface`，而不是扩成通用大平台

## 7. 一句话结论

`会议沉淀` phase-1 已经从“只做 smoke gate”推进到了“有真实 continuity sidecar 的第一条生产切片”，而且当前实现仍然保持窄、可控、可验证。

