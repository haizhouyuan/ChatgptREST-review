# 2026-04-03 Meeting Sedimentation Phase-1 Slice Execution Walkthrough v1

## 1. 为什么做这一步

`Step 0` 已经证明：

1. `Feishu/OpenClawBot -> openmind-advisor -> /v3/agent/turn` 的入口链是真能走通的

但那还不等于：

1. 同一场会议补材料时能继续旧任务
2. 深度执行后能留下一个可读 checkpoint

所以这一步的目标不是继续写计划，而是把第一条 continuity carrier 真正接出来。

## 2. 为什么没有走 full task_runtime

这次刻意没有把 `task_runtime` 拉进来，原因有两个：

1. 红队已经明确指出它现在还不是 phase-1 的现成承重层
2. 第一条切片只需要 `meeting_sedimentation`，没有必要先引一整套大平台

所以这次采取的是：

1. 新增 `meeting task store`
2. 只接 `meeting_summary / meeting_sedimentation`
3. 只落 `task_id + checkpoint`

## 3. 这次具体怎么接的

### 3.1 先做最窄 truth store

新增：

1. [meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py)

它负责：

1. 分配 `task_id`
2. 判断 `new / continue`
3. 持久化最小 checkpoint

### 3.2 再把它接到 agent_v3 主链

在 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py) 里做了三处注入：

1. task intake 完成后，若命中 `meeting_summary`，先 resolve task
2. clarify 或 completed 后，自动 update checkpoint
3. 把 `planning_task` 投影进 response / control_plane / session

### 3.3 保持现有 public surface 不扩张

这次没有新增 public MCP 工具，也没有新增新的大 REST 面。

所以它仍符合当前收口原则：

1. `publicagentmcp` 不继续长胖
2. 先用内部 canonical task plane 承载 phase-1 的 continuity sidecar

## 4. 实现中实际踩到的坑

### 4.1 第一次 pytest 抓到了闭包作用域错误

`_run_turn()` 里一边读一边更新 `planning_task_layer`，触发了 Python 的局部变量判定。

修法很简单：

1. 在 `_run_turn()` 里显式 `nonlocal planning_task_layer`

### 4.2 第二次 pytest 抓到了语义覆盖问题

第一次请求本来是 `resolution=new`，但 turn 完成后 checkpoint update 返回了 `continue`，把“本轮 task 判定结果”覆盖掉了。

所以后面改成：

1. checkpoint update 只更新 checkpoint 内容
2. 当前 turn 的 `resolution / reason` 仍沿用本轮 resolve 结果

## 5. 这次验证怎么做的

### 5.1 新增测试

1. [test_meeting_task_store.py](/vol1/1000/projects/ChatgptREST/tests/test_meeting_task_store.py)
2. [test_routes_agent_v3_meeting_task_layer.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_meeting_task_layer.py)

### 5.2 补跑回归

1. `meeting_summary` 自动 work memory capture
2. clarify handoff capture
3. public agent MCP validation

## 6. 这一步之后，计划状态怎么变

现在 phase-1 不再只是：

1. “入口链 smoke 已通过”

而是已经变成：

1. `meeting_sedimentation` 有第一条真实 continuity slice

下一步最该做的，不是立刻泛化，而是：

1. 让 `OpenClawBot` 有一个更明确的 continue/retrieve 使用面
2. 再决定深度工作台侧是否需要独立 checkpoint writeback 命令

