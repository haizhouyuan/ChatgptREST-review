# 2026-04-03 Planning Task Plane Redteam Fix Execution Review v1

## 1. 这轮修了什么

这轮不是继续扩 task type，而是消化上一轮 `claudegac` 红队里我确认成立的高优先问题。

实际代码修复包括：

1. `MeetingTaskStore.list_public(...)` 现在在无 identity 查询条件时直接返回空列表。
2. `MeetingTaskStore.list_public(...)` 现在会收敛 `limit`，避免 list 面无限放大。
3. `resolve_planning_task_type(...)` 不再把 generic planning 的默认 `implementation_plan` pack profile 当成一票定性。
4. `implementation_plan` 兼容被改写成：
   - 显式 `goal_hint=implementation_planning`
   - 或真实实施语义关键词
5. `routes_agent_v3._planning_checkpoint_seed(...)` 现在对 context list 字段做安全归一化，不再对脏 shape 直接 `list(...)`。

## 2. 这轮没有做什么

1. 没有把 plain `管理层` 关键词加回去。
2. 没有扩大 `task plane` 的 task type 数量。
3. 没有把这轮说成 full `task_runtime` 接管。

## 3. 我为什么这样修

### 3.1 list 泄漏问题

这个是明确 bug。只要没带 identity 条件就列全盘任务，不能接受，必须 fail-closed。

### 3.2 implementation_plan 兼容问题

红队指出的风险方向是对的，但它给出的“profile-only 直接放过”方案不适合代码现实。

原因：

1. generic `planning` ask 的 scenario pack 很常见地就是 `implementation_plan`
2. 如果让 `profile-only` 直接判 impl，会把 `project_diagnosis / planning_general` 吞掉

所以我改成了更窄的兼容：

1. 保留显式 `implementation_planning`
2. 保留真实实施语义
3. 不让 generic planning 默认 pack profile 越权改写 task type

### 3.3 管理层关键词问题

我没有按红队原话回滚关键词，而是选择补测试锁住真实意图：

1. `workforce_planning + audience=管理层` 仍归 `workforce_planning`
2. “管理层汇报摘要”因为 `汇报` 命中，仍归 `leadership_report`

## 4. 回归结果

通过：

```bash
python3 -m py_compile \
  chatgptrest/planning/meeting_task_store.py \
  chatgptrest/api/routes_agent_v3.py \
  tests/test_meeting_task_store.py \
  tests/test_routes_agent_v3_planning_task_plane.py

./.venv/bin/pytest -q \
  tests/test_meeting_task_store.py \
  tests/test_routes_agent_v3_planning_task_plane.py

./.venv/bin/pytest -q \
  tests/test_routes_agent_v3_meeting_task_layer.py \
  tests/test_routes_agent_v3_planning_task_plane.py \
  tests/test_export_planning_phase1_continuity_acceptance_pack.py

./.venv/bin/pytest -q \
  tests/test_agent_v3_routes.py \
  tests/test_public_agent_mcp_validation.py
```

## 5. Evidence

真实 acceptance pack 已重导出：

- `docs/dev_log/artifacts/planning_task_plane_acceptance_pack_20260403_v3/manifest.json`
- `docs/dev_log/artifacts/planning_task_plane_acceptance_pack_20260403_v3/report_v1.md`

结果：

1. `overall_pass = true`
2. `7/7` scenario 继续全绿

## 6. 本轮结论

这轮修的是 task plane 的收口质量，不是新扩面。

最重要的结果有两个：

1. 空 identity list 泄漏已收掉
2. `implementation_plan` 的兼容改成了“显式/语义优先”，避免 generic planning 被 impl 吞掉
