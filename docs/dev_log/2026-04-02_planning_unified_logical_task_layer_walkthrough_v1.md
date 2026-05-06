# 2026-04-02 Planning Unified Logical Task Layer Walkthrough v1

## 本轮做了什么

新增两份文档：

1. [2026-04-02_planning_unified_logical_task_layer_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_unified_logical_task_layer_v1.md)
2. 本 walkthrough

## 为什么做

前面的 surface matrix 和 task matrix 已经把“从哪个入口/工作台做事”梳清了，但还有一个更根的问题没有冻结：

1. 多端并存时，真正的任务真相源是什么
2. session 和记忆怎么分层
3. 什么算继续旧任务，什么算新任务

用户明确接受了“多端可以并存，但必须统一逻辑任务层”的方向，所以需要把这层定义先落盘。

## 这次核了哪些现有基座

### 1. 任务 intake

看了：

- [2026-03-21_task_intake_spec_v2.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_task_intake_spec_v2.json)

确认：

- schema 已经预留可选 `task_id`
- 这给“上游入口分配稳定任务线程标识”提供了现成落点

### 2. task runtime

看了：

- [task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/task_store.py)
- [task_initializer.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/task_initializer.py)
- [api_routes.py](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/api_routes.py)
- [2026-03-31_agent_harness_completion_report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-31_agent_harness_completion_report_v1.md)

确认：

1. `task_id` 和 `logical_task_key` 已存在
2. task runtime 已有 `resume / signals / operator` 这类 task 级对象
3. `phase / status / last_checkpoint_at / state_data_json` 已提供 checkpoint/state 语义

### 3. session 层

看了：

- [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py)
- [2026-03-20_session_truth_decision_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v3.md)

确认：

- repo 里已经明确过 session truth 不是唯一真相
- `state/agent_sessions/*` 更适合 facade session continuity，不适合直接当 planning 长任务真相源

### 4. planning 目标与 surface 冻结

延续使用：

- [planning_work_agent_effect_requirements_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_work_agent_effect_requirements_v1.md)
- [execution_surface_authority_and_retirement_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_execution_surface_authority_and_retirement_matrix_v1.md)
- [planning_task_surface_and_lane_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-01_planning_task_surface_and_lane_matrix_v1.md)

## 这次最终冻结了什么

### 1. `task_id`

冻结为：

- planning 工作线程真相源
- 可跨飞书、TUI、IDE、tmuxagent 连续
- 不等于 session/thread/window/pane

### 2. checkpoint

冻结为：

- 跨端 handoff artifact
- 负责说明“做到哪了、确认了什么、下一步做什么”
- 不负责保存全部聊天记录

### 3. memory scope

冻结为 4 层：

1. `L0 Session Scratch`
2. `L1 Task Working Memory`
3. `L2 Project / Topic Durable Memory`
4. `L3 Governance / EvoMap Memory`

### 4. 新任务 vs 继续任务

冻结了：

1. 继续任务的默认判断条件
2. 新任务的高权重判定条件
3. 推荐增加 `branch_from_existing_task` 中间态

## 这版文档的用途

这版不是让产品代码马上照着大改，而是让后续目标讨论、入口设计、记忆治理、checkpoint 设计有同一套词。

后续如果继续往下做，最自然的下一份文档会是：

1. `new / continue / branch decision policy v1`
2. `checkpoint schema for planning tasks v1`
3. `memory writeback policy v1`

## 结果

这轮把“统一入口”从界面问题改成了任务治理问题：

- 不再追求先把所有 surface 合并成一个 UI
- 而是先把多 surface 共享的 `task_id / checkpoint / memory scope` 固定下来

这更符合用户当前真实工作方式，也更符合 repo 里已经存在的 task/runtime/session 基座。
