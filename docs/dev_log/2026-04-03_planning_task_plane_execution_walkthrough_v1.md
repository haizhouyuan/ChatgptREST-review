# 2026-04-03 Planning Task Plane Execution Walkthrough v1

## 1. 本轮做了什么

本轮把之前“会议沉淀/人力规划/实施计划”三条 continuity slice，扩成一个更完整的 `planning task plane`。

具体动作：

1. 扩展 `meeting_task_store.py`
2. 在 `routes_agent_v3.py` 里增加 richer planning checkpoint seed 与 `/planning/tasks` list surface
3. 扩大 acceptance pack，从 3 个 scenario 提升到 7 个 scenario
4. 新增 route-level tests，证明 identity continue、branch、list/query 和新增 task types
5. 生成一份新的本地 evidence bundle：`planning_task_plane_acceptance_pack_20260403_v2`

## 2. 为什么要这样做

原因很直接：

1. 用户已经明确要求不要停在“最小实现”
2. 之前的 3 条 continuity slice 证明的是“能做一点”
3. 但对于 `planning/` 高频工作来说，只有三类任务不够，且没有 list/query、branch、identity continue 也不够
4. 所以这一轮不是再开新架构，而是把同一条 task truth/continuity 线扩成更接近真实 planning 工作的 task plane

## 3. 关键判断

### 3.1 我保留的判断

1. `publicagentmcp` 仍按 `ask wrapper` 收口，不往这里继续堆 orchestration
2. `Feishu` 主入口 owner 仍是 `OpenClaw/OpenClawBot`
3. 这条线当前仍不是 full `task_runtime`

### 3.2 我推进的判断

1. 不能只证明显式 `task_id` continue，必须证明 identity continue
2. 不能只证明“命令成功”，必须证明 writeback 内容真的落进 checkpoint
3. 不能只支持 3 类 task type，至少要覆盖更接近 `planning/` 主线的 7 类
4. 需要有 list/query，不然多任务管理还不成面

## 4. 实际验证

我实际跑了：

```bash
python3 -m py_compile \
  chatgptrest/api/routes_agent_v3.py \
  ops/export_planning_phase1_continuity_acceptance_pack.py \
  tests/test_routes_agent_v3_meeting_task_layer.py \
  tests/test_routes_agent_v3_planning_task_plane.py \
  tests/test_export_planning_phase1_continuity_acceptance_pack.py

./.venv/bin/pytest -q \
  tests/test_meeting_task_store.py \
  tests/test_planning_task_checkpoint_writeback.py \
  tests/test_planning_task_checkpoint_complete.py \
  tests/test_routes_agent_v3_meeting_task_layer.py \
  tests/test_routes_agent_v3_planning_task_plane.py \
  tests/test_export_planning_phase1_continuity_acceptance_pack.py \
  tests/test_agent_v3_routes.py \
  tests/test_public_agent_mcp_validation.py

./.venv/bin/python \
  ops/export_planning_phase1_continuity_acceptance_pack.py \
  --output-dir docs/dev_log/artifacts/planning_task_plane_acceptance_pack_20260403_v2
```

结果：

1. 编译通过
2. 回归通过
3. acceptance pack `overall_pass = true`
4. 七个 scenario 全通过

## 5. 这一步之后系统该怎么描述

更准确的说法是：

1. ChatgptREST 内部已经有一个更完整的 planning task plane
2. 它目前具备：
   - 多类 planning task type
   - identity continue
   - explicit continue
   - branch
   - retrieve
   - list/query
   - richer checkpoint writeback
3. 它仍然不是：
   - OpenClawBot ingress proof
   - full task runtime proof
   - final production sign-off

## 6. 下一步

下一步不该继续盲目加功能，而该：

1. 先把这一版提交
2. 再用 `claudegac` 对已提交版本做一次严格红队审查
3. 如果红队指出真实问题，再做下一轮代码修正
